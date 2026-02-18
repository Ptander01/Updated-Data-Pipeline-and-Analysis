"""
UCID Confidence Analysis Script
Analyzes how confident we can be in each UCID based on source coverage.

Confidence Framework:
- 1 source  = LOW confidence (unverified)
- 2 sources = MEDIUM confidence (corroborated)
- 3+ sources = HIGH confidence (well-established)
- Meta Canonical match = VERIFIED (ground truth)

Author: Meta Data Center GIS Team
Created: December 18, 2024
"""

import arcpy
import os
import sys
import csv
from datetime import datetime
from collections import defaultdict

# Add _utils to path for config import
try:
    script_dir = os.path.dirname(os.path.abspath(__file__))
except NameError:
    script_dir = r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\scripts\06_ucid"

utils_dir = os.path.join(os.path.dirname(script_dir), "_utils")
if utils_dir not in sys.path:
    sys.path.insert(0, utils_dir)

from config import GDB, CAMPUS_MASTER_TIGHT, CAMPUS_MASTER_LOOSE, META_CANONICAL_CAMPUS

arcpy.env.workspace = GDB
arcpy.env.overwriteOutput = True

# Output directory
OUTPUT_DIR = os.path.join(os.path.dirname(script_dir), "outputs")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ==============================================================================
# CONFIDENCE TIER DEFINITIONS
# ==============================================================================

def get_confidence_tier(source_count, has_meta_match):
    """
    Determine confidence tier based on source count and Meta match.

    Tiers:
    - VERIFIED: Has Meta Canonical match (ground truth)
    - HIGH: 3+ independent sources
    - MEDIUM: 2 independent sources
    - LOW: 1 source only (unverified)
    """
    if has_meta_match:
        return 'VERIFIED'
    elif source_count >= 3:
        return 'HIGH'
    elif source_count == 2:
        return 'MEDIUM'
    else:
        return 'LOW'

# ==============================================================================
# ANALYSIS FUNCTIONS
# ==============================================================================

def load_ucid_data(campus_master_fc):
    """Load UCID data from campus_master feature class."""

    records = []

    fields = [
        'ucid', 'canonical_name', 'company_canonical', 'company_clean',
        'city', 'state_abbr', 'country', 'region',
        'source_count', 'sources', 'total_capacity_mw', 'commissioned_mw',
        'building_count', 'meta_canonical_match'
    ]

    with arcpy.da.SearchCursor(campus_master_fc, fields) as cursor:
        for row in cursor:
            has_meta = row[13] == 'Y' if row[13] else False
            source_count = row[8] or 1

            records.append({
                'ucid': row[0],
                'canonical_name': row[1],
                'company_canonical': row[2],
                'company_clean': row[3],
                'city': row[4],
                'state_abbr': row[5],
                'country': row[6],
                'region': row[7],
                'source_count': source_count,
                'sources': row[9],
                'total_capacity_mw': row[10] or 0,
                'commissioned_mw': row[11] or 0,
                'building_count': row[12] or 0,
                'has_meta_match': has_meta,
                'confidence_tier': get_confidence_tier(source_count, has_meta),
            })

    return records

def analyze_confidence_distribution(records):
    """Analyze confidence tier distribution."""

    stats = {
        'total': len(records),
        'by_tier': defaultdict(int),
        'by_tier_capacity': defaultdict(float),
        'by_tier_buildings': defaultdict(int),
        'by_source_count': defaultdict(int),
        'by_company': defaultdict(lambda: defaultdict(int)),
        'by_region': defaultdict(lambda: defaultdict(int)),
    }

    for rec in records:
        tier = rec['confidence_tier']
        company = rec['company_canonical'] or 'Unknown'
        region = rec['region'] or 'OTHER'
        source_count = rec['source_count']

        stats['by_tier'][tier] += 1
        stats['by_tier_capacity'][tier] += rec['total_capacity_mw']
        stats['by_tier_buildings'][tier] += rec['building_count']
        stats['by_source_count'][source_count] += 1
        stats['by_company'][company][tier] += 1
        stats['by_region'][region][tier] += 1

    return stats

def analyze_hyperscaler_coverage(records):
    """Analyze source coverage for hyperscaler campuses."""

    hyperscalers = ['AWS', 'Microsoft', 'Google', 'Meta', 'Apple', 'Oracle', 'xAI', 'Alibaba']

    results = {}

    for hs in hyperscalers:
        hs_records = [r for r in records if r['company_canonical'] == hs]

        if not hs_records:
            continue

        total = len(hs_records)
        verified = sum(1 for r in hs_records if r['confidence_tier'] == 'VERIFIED')
        high = sum(1 for r in hs_records if r['confidence_tier'] == 'HIGH')
        medium = sum(1 for r in hs_records if r['confidence_tier'] == 'MEDIUM')
        low = sum(1 for r in hs_records if r['confidence_tier'] == 'LOW')

        # Calculate average source coverage
        avg_sources = sum(r['source_count'] for r in hs_records) / total
        max_sources = max(r['source_count'] for r in hs_records)

        # Capacity by tier
        capacity_by_tier = defaultdict(float)
        for r in hs_records:
            capacity_by_tier[r['confidence_tier']] += r['total_capacity_mw']

        results[hs] = {
            'total_campuses': total,
            'verified': verified,
            'high': high,
            'medium': medium,
            'low': low,
            'avg_sources': avg_sources,
            'max_sources': max_sources,
            'pct_verified_or_high': (verified + high) / total * 100 if total > 0 else 0,
            'pct_multi_source': (total - low) / total * 100 if total > 0 else 0,
            'capacity_by_tier': dict(capacity_by_tier),
            'total_capacity_mw': sum(r['total_capacity_mw'] for r in hs_records),
        }

    return results

def analyze_source_combinations(records):
    """Analyze which source combinations appear most frequently."""

    combinations = defaultdict(int)

    for rec in records:
        if rec['sources']:
            # Normalize source list
            sources = sorted([s.strip() for s in rec['sources'].split(';')])
            combo_key = ' + '.join(sources)
            combinations[combo_key] += 1

    # Sort by frequency
    sorted_combos = sorted(combinations.items(), key=lambda x: x[1], reverse=True)

    return sorted_combos[:30]  # Top 30 combinations

def analyze_geographic_confidence(records):
    """Analyze confidence levels by geography."""

    by_country = defaultdict(lambda: {'total': 0, 'low': 0, 'medium': 0, 'high': 0, 'verified': 0})
    by_region = defaultdict(lambda: {'total': 0, 'low': 0, 'medium': 0, 'high': 0, 'verified': 0})

    for rec in records:
        country = rec['country'] or 'Unknown'
        region = rec['region'] or 'OTHER'
        tier = rec['confidence_tier']

        by_country[country]['total'] += 1
        by_country[country][tier.lower()] += 1

        by_region[region]['total'] += 1
        by_region[region][tier.lower()] += 1

    # Calculate percentages
    for country, data in by_country.items():
        total = data['total']
        data['pct_multi_source'] = (total - data['low']) / total * 100 if total > 0 else 0

    for region, data in by_region.items():
        total = data['total']
        data['pct_multi_source'] = (total - data['low']) / total * 100 if total > 0 else 0

    return dict(by_country), dict(by_region)

def export_confidence_report(records, stats, hyperscaler_stats, source_combos, geo_stats, output_prefix):
    """Export confidence analysis to CSV files."""

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # 1. Full UCID list with confidence tiers
    full_path = os.path.join(OUTPUT_DIR, f"{output_prefix}_full_{timestamp}.csv")
    with open(full_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([
            'ucid', 'canonical_name', 'company', 'city', 'country', 'region',
            'source_count', 'sources', 'confidence_tier', 'has_meta_match',
            'total_capacity_mw', 'building_count'
        ])
        for rec in sorted(records, key=lambda x: (x['confidence_tier'], -x['source_count'])):
            writer.writerow([
                rec['ucid'],
                rec['canonical_name'],
                rec['company_canonical'],
                rec['city'],
                rec['country'],
                rec['region'],
                rec['source_count'],
                rec['sources'],
                rec['confidence_tier'],
                'Yes' if rec['has_meta_match'] else 'No',
                round(rec['total_capacity_mw'], 2),
                rec['building_count'],
            ])
    print(f"   - Exported full UCID list: {os.path.basename(full_path)}")

    # 2. Hyperscaler summary
    hs_path = os.path.join(OUTPUT_DIR, f"{output_prefix}_hyperscalers_{timestamp}.csv")
    with open(hs_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([
            'company', 'total_campuses', 'verified', 'high', 'medium', 'low',
            'avg_sources', 'pct_multi_source', 'total_capacity_mw'
        ])
        for company, data in sorted(hyperscaler_stats.items(), key=lambda x: x[1]['total_campuses'], reverse=True):
            writer.writerow([
                company,
                data['total_campuses'],
                data['verified'],
                data['high'],
                data['medium'],
                data['low'],
                round(data['avg_sources'], 2),
                round(data['pct_multi_source'], 1),
                round(data['total_capacity_mw'], 2),
            ])
    print(f"   - Exported hyperscaler summary: {os.path.basename(hs_path)}")

    # 3. Source combinations
    combo_path = os.path.join(OUTPUT_DIR, f"{output_prefix}_source_combos_{timestamp}.csv")
    with open(combo_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['source_combination', 'count', 'pct_of_total'])
        total = len(records)
        for combo, count in source_combos:
            writer.writerow([combo, count, round(count/total*100, 2)])
    print(f"   - Exported source combinations: {os.path.basename(combo_path)}")

    # 4. Geographic summary
    by_country, by_region = geo_stats
    geo_path = os.path.join(OUTPUT_DIR, f"{output_prefix}_geography_{timestamp}.csv")
    with open(geo_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['level', 'name', 'total', 'verified', 'high', 'medium', 'low', 'pct_multi_source'])

        # Regions first
        for region, data in sorted(by_region.items(), key=lambda x: x[1]['total'], reverse=True):
            writer.writerow([
                'REGION', region, data['total'], data['verified'], data['high'],
                data['medium'], data['low'], round(data['pct_multi_source'], 1)
            ])

        # Top 20 countries
        top_countries = sorted(by_country.items(), key=lambda x: x[1]['total'], reverse=True)[:20]
        for country, data in top_countries:
            writer.writerow([
                'COUNTRY', country, data['total'], data['verified'], data['high'],
                data['medium'], data['low'], round(data['pct_multi_source'], 1)
            ])
    print(f"   - Exported geography summary: {os.path.basename(geo_path)}")

    return full_path, hs_path, combo_path, geo_path

def print_confidence_summary(stats, hyperscaler_stats, source_combos):
    """Print confidence analysis summary."""

    print("\n" + "="*80)
    print("UCID CONFIDENCE ANALYSIS")
    print("="*80)

    total = stats['total']

    # Tier distribution
    print("\n📊 CONFIDENCE TIER DISTRIBUTION")
    print("-"*60)
    print(f"{'Tier':<15} {'Count':<10} {'%':<10} {'Capacity (MW)':<15} {'Meaning':<30}")
    print("-"*60)

    tier_order = ['VERIFIED', 'HIGH', 'MEDIUM', 'LOW']
    tier_descriptions = {
        'VERIFIED': 'Meta ground truth match',
        'HIGH': '3+ independent sources',
        'MEDIUM': '2 independent sources',
        'LOW': '1 source only (unverified)',
    }

    for tier in tier_order:
        count = stats['by_tier'][tier]
        capacity = stats['by_tier_capacity'][tier]
        pct = count / total * 100 if total > 0 else 0
        print(f"{tier:<15} {count:<10,} {pct:<10.1f}% {capacity:<15,.0f} {tier_descriptions[tier]:<30}")

    print("-"*60)
    print(f"{'TOTAL':<15} {total:<10,} {'100%':<10}")

    # Multi-source rate
    multi_source = total - stats['by_tier']['LOW']
    print(f"\n✅ Multi-source rate: {multi_source:,} / {total:,} = {multi_source/total*100:.1f}%")
    print(f"   → {multi_source/total*100:.1f}% of campuses are corroborated by 2+ sources")

    # Source count distribution
    print("\n📈 SOURCE COUNT DISTRIBUTION")
    print("-"*40)
    for n in sorted(stats['by_source_count'].keys()):
        count = stats['by_source_count'][n]
        pct = count / total * 100
        bar = '█' * int(pct / 2)
        print(f"   {n} source(s): {count:>6,} ({pct:>5.1f}%) {bar}")

    # Hyperscaler coverage
    print("\n🏢 HYPERSCALER CONFIDENCE")
    print("-"*80)
    print(f"{'Company':<12} {'Campuses':<10} {'Verified':<10} {'High':<8} {'Medium':<8} {'Low':<8} {'Multi-Src%':<10}")
    print("-"*80)

    for company in ['Meta', 'AWS', 'Microsoft', 'Google', 'Apple', 'Oracle', 'xAI']:
        if company in hyperscaler_stats:
            data = hyperscaler_stats[company]
            print(f"{company:<12} {data['total_campuses']:<10} {data['verified']:<10} {data['high']:<8} {data['medium']:<8} {data['low']:<8} {data['pct_multi_source']:<10.1f}%")

    # Top source combinations
    print("\n🔗 TOP SOURCE COMBINATIONS (Multi-Source Only)")
    print("-"*60)
    multi_combos = [(c, n) for c, n in source_combos if '+' in c][:10]
    for combo, count in multi_combos:
        pct = count / total * 100
        print(f"   {combo:<45} {count:>5} ({pct:>4.1f}%)")

    # Key insights
    print("\n" + "="*80)
    print("KEY INSIGHTS")
    print("="*80)

    verified_pct = stats['by_tier']['VERIFIED'] / total * 100 if total > 0 else 0
    high_pct = stats['by_tier']['HIGH'] / total * 100 if total > 0 else 0
    low_pct = stats['by_tier']['LOW'] / total * 100 if total > 0 else 0

    print(f"\n1. VERIFICATION STATUS")
    print(f"   • {stats['by_tier']['VERIFIED']:,} campuses ({verified_pct:.1f}%) have Meta ground truth")
    print(f"   • {stats['by_tier']['HIGH']:,} campuses ({high_pct:.1f}%) have 3+ source corroboration")
    print(f"   • {stats['by_tier']['LOW']:,} campuses ({low_pct:.1f}%) are single-source (unverified)")

    print(f"\n2. RISK ASSESSMENT")
    if low_pct > 60:
        print(f"   ⚠️  HIGH RISK: {low_pct:.0f}% of campuses are unverified single-source")
        print(f"      Recommendation: Prioritize adding more data sources")
    elif low_pct > 40:
        print(f"   🟡 MEDIUM RISK: {low_pct:.0f}% of campuses are unverified")
        print(f"      Recommendation: Focus on high-priority markets for validation")
    else:
        print(f"   ✅ LOW RISK: Only {low_pct:.0f}% of campuses are unverified")
        print(f"      Most campuses have independent corroboration")

    print(f"\n3. SOURCE COVERAGE QUALITY")
    if 'DataCenterHawk' in str(source_combos) and 'Semianalysis' in str(source_combos):
        dch_semi = sum(n for c, n in source_combos if 'DataCenterHawk' in c and 'Semianalysis' in c)
        print(f"   • DCH + Semianalysis overlap: {dch_semi:,} campuses")
        print(f"   • This is your most valuable cross-validation pair")

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================

def main():
    print("="*80)
    print("UCID CONFIDENCE ANALYSIS")
    print(f"Started: {datetime.now()}")
    print("="*80)

    # Analyze TIGHT (primary)
    print("\n[Step 1] Loading UCID data from campus_master_tight...")
    if not arcpy.Exists(CAMPUS_MASTER_TIGHT):
        print("   ERROR: campus_master_tight not found. Run generate_ucid_clusters.py first.")
        return

    records = load_ucid_data(CAMPUS_MASTER_TIGHT)
    print(f"   - Loaded {len(records):,} UCIDs")

    # Run analyses
    print("\n[Step 2] Analyzing confidence distribution...")
    stats = analyze_confidence_distribution(records)

    print("\n[Step 3] Analyzing hyperscaler coverage...")
    hyperscaler_stats = analyze_hyperscaler_coverage(records)

    print("\n[Step 4] Analyzing source combinations...")
    source_combos = analyze_source_combinations(records)

    print("\n[Step 5] Analyzing geographic confidence...")
    geo_stats = analyze_geographic_confidence(records)

    # Print summary
    print_confidence_summary(stats, hyperscaler_stats, source_combos)

    # Export reports
    print("\n[Step 6] Exporting detailed reports...")
    export_confidence_report(records, stats, hyperscaler_stats, source_combos, geo_stats, "ucid_confidence")

    print(f"\nCompleted: {datetime.now()}")
    print("="*80)

    return stats, hyperscaler_stats, source_combos

# Execute
if __name__ == "__main__":
    main()
else:
    try:
        main()
    except Exception as e:
        print(f"\nERROR: {str(e)}")
        import traceback
        traceback.print_exc()
