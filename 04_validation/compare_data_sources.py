"""
Data Source Comparison Analysis Script
Compares new pipeline outputs against previous versions for:
1. SemiAnalysis (Hive test pipeline vs local Excel pipeline)
2. WoodMac (new 2025 dataset vs previous version)
3. Synergy business intelligence recommendations

Author: Meta Data Center GIS Team
Last Updated: 2026-02-12
"""

import csv
import os
from datetime import datetime
from collections import defaultdict

# ============================================================================
# FILE PATHS
# ============================================================================

SA_NEW_HIVE = r"C:\Users\ptanderson\Downloads\Pipeline_Ingestion\Test_SemiAnalysis_2_12.csv"
SA_PREVIOUS = r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\scripts\outputs\semianalysis_FINAL_20260203_0916.csv"

WM_NEW = r"C:\Users\ptanderson\Downloads\Pipeline_Ingestion\022025_WoodMac_DC_sites.csv"
WM_OLD = r"C:\Users\ptanderson\Downloads\Pipeline_Ingestion\WoodMac_DC.csv"

SYNERGY = r"C:\Users\ptanderson\Downloads\Pipeline_Ingestion\Synergy Hyperscale DC.csv"

OUTPUT_DIR = r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\scripts\outputs"

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def safe_str(val, max_len=None):
    if val is None or str(val).strip() in ['', 'nan', 'None', 'NaN']:
        return None
    s = str(val).strip()
    return s[:max_len] if max_len and len(s) > max_len else (s if s else None)

def safe_float(val):
    if val is None or val == '' or str(val).strip() in ['', 'nan', 'None', 'NaN']:
        return None
    try:
        return float(str(val).replace(',', ''))
    except (ValueError, TypeError):
        return None

def read_csv_data(filepath):
    if not os.path.exists(filepath):
        print(f"  [ERROR] File not found: {filepath}")
        return []
    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
        return list(csv.DictReader(f))

def grade_population(pct):
    if pct >= 95: return 'A'
    elif pct >= 80: return 'B'
    elif pct >= 60: return 'C'
    elif pct >= 40: return 'D'
    else: return 'F'

# ============================================================================
# SEMIANALYSIS COMPARISON
# ============================================================================

def compare_semianalysis():
    print("\n" + "=" * 80)
    print("SEMIANALYSIS COMPARISON: Hive Pipeline vs Local Excel Pipeline")
    print("=" * 80)

    new_rows = read_csv_data(SA_NEW_HIVE)
    old_rows = read_csv_data(SA_PREVIOUS) if os.path.exists(SA_PREVIOUS) else []

    print(f"\n  NEW (Hive): {len(new_rows):,} records")
    print(f"  OLD (Local): {len(old_rows):,} records")

    if old_rows:
        diff = len(new_rows) - len(old_rows)
        print(f"  Difference: {diff:+,} records")

    # Schema comparison
    new_fields = set(new_rows[0].keys()) if new_rows else set()
    old_fields = set(old_rows[0].keys()) if old_rows else set()

    print(f"\n--- SCHEMA ---")
    print(f"NEW: {len(new_fields)} fields | OLD: {len(old_fields)} fields")

    new_only = new_fields - old_fields
    if new_only:
        print(f"\n[NEW FIELDS] ({len(new_only)}):")
        for f in sorted(new_only)[:15]:
            print(f"  + {f}")
        if len(new_only) > 15:
            print(f"  ... and {len(new_only)-15} more")

    # Data structure check - CRITICAL
    print(f"\n--- DATA STRUCTURE (CRITICAL) ---")
    if new_rows:
        cluster_ids = [r.get('clusterid') for r in new_rows if r.get('clusterid') and safe_str(r.get('clusterid'))]
        unique_clusters = len(set(cluster_ids))
        print(f"  Total rows: {len(new_rows):,}")
        print(f"  Rows with clusterid: {len(cluster_ids):,}")
        print(f"  Unique cluster IDs: {unique_clusters:,}")

        if unique_clusters > 0:
            print(f"  Rows per cluster: {len(cluster_ids)/unique_clusters:.1f} avg")

            if unique_clusters < len(cluster_ids) / 2:
                print("\n  [ALERT] Data is in LONG/PIVOTED format!")
                print("  Each cluster has multiple rows (one per year-quarter)")
                print("  This differs from OLD wide format (one row per building)")
        else:
            print("\n  [WARN] No valid clusterid values found!")

        # Year distribution
        years = defaultdict(int)
        for r in new_rows:
            yr = safe_str(r.get('year'))
            if yr: years[yr] += 1
        if years:
            print(f"\n  Years in data: {sorted(years.keys())}")

    # Coordinate coverage
    print(f"\n--- COORDINATE COVERAGE ---")
    if new_rows:
        new_coords = sum(1 for r in new_rows if safe_float(r.get('lat')) and safe_float(r.get('long')))
        print(f"  NEW: {new_coords:,}/{len(new_rows):,} ({new_coords/len(new_rows)*100:.1f}%)")

    if old_rows:
        old_coords = sum(1 for r in old_rows if safe_float(r.get('Lat')) and safe_float(r.get('Long')))
        print(f"  OLD: {old_coords:,}/{len(old_rows):,} ({old_coords/len(old_rows)*100:.1f}%)")

    # Capacity totals (deduplicated by cluster)
    print(f"\n--- CAPACITY TOTALS ---")
    if new_rows:
        cluster_cap = defaultdict(lambda: {'uc': 0, 'planned': 0})
        for r in new_rows:
            cid = r.get('clusterid')
            if cid:
                cluster_cap[cid]['uc'] = max(cluster_cap[cid]['uc'], safe_float(r.get('total_under_construction_mw')) or 0)
                cluster_cap[cid]['planned'] = max(cluster_cap[cid]['planned'], safe_float(r.get('total_planned_mw')) or 0)

        print(f"  NEW (unique clusters): {len(cluster_cap):,}")
        print(f"    UC MW: {sum(c['uc'] for c in cluster_cap.values()):,.0f}")
        print(f"    Planned MW: {sum(c['planned'] for c in cluster_cap.values()):,.0f}")

    # Key field population
    print(f"\n--- KEY FIELD POPULATION (NEW) ---")
    key_fields = ['clusterid', 'lat', 'long', 'company', 'state', 'city', 'end_user', 'tenant', 'value']
    for field in key_fields:
        if field in new_fields:
            pop = sum(1 for r in new_rows if safe_str(r.get(field)))
            pct = pop/len(new_rows)*100
            print(f"  {field:25s}: {pop:>6,}/{len(new_rows):>6,} ({pct:>5.1f}%) [{grade_population(pct)}]")

    return {'new': len(new_rows), 'old': len(old_rows), 'new_clusters': unique_clusters if new_rows else 0}


# ============================================================================
# WOODMAC COMPARISON
# ============================================================================

def compare_woodmac():
    print("\n" + "=" * 80)
    print("WOODMAC COMPARISON: New Feb 2025 vs Previous Version")
    print("=" * 80)

    new_rows = read_csv_data(WM_NEW)
    old_rows = read_csv_data(WM_OLD)

    print(f"\n  NEW: {len(new_rows):,} records")
    print(f"  OLD: {len(old_rows):,} records")

    # Schema
    new_fields = set(new_rows[0].keys()) if new_rows else set()
    old_fields = set(old_rows[0].keys()) if old_rows else set()

    new_only = new_fields - old_fields
    print(f"\n--- NEW FIELDS ({len(new_only)}) ---")
    for f in sorted(new_only)[:20]:
        print(f"  + {f}")

    # CRITICAL: Coordinate coverage
    print(f"\n--- COORDINATE COVERAGE (CRITICAL) ---")
    if new_rows:
        new_coords = sum(1 for r in new_rows if safe_float(r.get('latitude')) and safe_float(r.get('longitude')))
        pct = new_coords/len(new_rows)*100
        print(f"  NEW: {new_coords:,}/{len(new_rows):,} ({pct:.1f}%)")
        if pct > 50:
            print("  [EXCELLENT] Can be ingested as spatial data!")

    # Geographic scope
    print(f"\n--- GEOGRAPHIC SCOPE ---")
    if new_rows:
        countries = defaultdict(int)
        for r in new_rows:
            countries[safe_str(r.get('country_name')) or 'Unknown'] += 1
        print(f"  Countries: {len(countries)}")
        for c, n in sorted(countries.items(), key=lambda x: -x[1])[:10]:
            print(f"    {c:30s}: {n:>5,}")

    # Status distribution
    print(f"\n--- STATUS DISTRIBUTION ---")
    if new_rows:
        statuses = defaultdict(int)
        for r in new_rows:
            statuses[safe_str(r.get('status')) or 'Unknown'] += 1
        for s, n in sorted(statuses.items(), key=lambda x: -x[1]):
            print(f"  {s:25s}: {n:>5,} ({n/len(new_rows)*100:>5.1f}%)")

    # Capacity
    print(f"\n--- CAPACITY DATA ---")
    if new_rows:
        for field in ['existing_capacity__mw', 'development_capacity__mw', 'planned_capacity__mw']:
            if field in new_fields:
                has = sum(1 for r in new_rows if safe_float(r.get(field)))
                total = sum(safe_float(r.get(field)) or 0 for r in new_rows)
                print(f"  {field:35s}: {has:>5,} records | {total:>10,.0f} MW")

    # Developer distribution
    print(f"\n--- TOP DEVELOPERS ---")
    if new_rows:
        devs = defaultdict(int)
        for r in new_rows:
            devs[safe_str(r.get('developer_name')) or 'Unknown'] += 1
        for d, n in sorted(devs.items(), key=lambda x: -x[1])[:15]:
            print(f"  {d:40s}: {n:>4,}")

    # Enrichment fields
    print(f"\n--- ENRICHMENT POTENTIAL ---")
    enrich_fields = ['workload', 'finance_partner', 'total_site_acres', 'data_center_acres',
                     'land_cost_usd_million', 'development_overall_cost_usd_million']
    for field in enrich_fields:
        if field in new_fields:
            has = sum(1 for r in new_rows if safe_str(r.get(field)))
            print(f"  {field:40s}: {has:>5,} ({has/len(new_rows)*100:>5.1f}%)")

    return {'new': len(new_rows), 'old': len(old_rows), 'coords': new_coords if new_rows else 0}


# ============================================================================
# SYNERGY BUSINESS RECOMMENDATIONS
# ============================================================================

def synergy_business_recommendations():
    print("\n" + "=" * 80)
    print("SYNERGY BUSINESS INTELLIGENCE RECOMMENDATIONS")
    print("=" * 80)

    rows = read_csv_data(SYNERGY)
    print(f"\n  Records: {len(rows):,}")

    hyperscalers = ['Amazon', 'Microsoft', 'Google', 'Meta', 'Apple', 'Oracle', 'Alibaba', 'Tencent']

    # Ownership analysis
    print(f"\n--- OWNERSHIP MODEL BY HYPERSCALER ---")
    ownership = defaultdict(lambda: {'O': 0, 'L': 0, 'P': 0})
    for r in rows:
        company = safe_str(r.get('Company')) or 'Unknown'
        own_type = safe_str(r.get('Owned or\nLeased/Partner')) or 'U'
        qty = int(safe_float(r.get('Quantity')) or 0)
        if own_type in ['O', 'L', 'P']:
            ownership[company][own_type] += qty

    print(f"  {'Company':<12} | {'Owned':>6} | {'Leased':>6} | {'Partner':>6} | {'% Owned':>7}")
    print("  " + "-" * 55)
    for hs in hyperscalers:
        d = ownership.get(hs, {'O': 0, 'L': 0, 'P': 0})
        total = d['O'] + d['L'] + d['P']
        pct = (d['O']/total*100) if total > 0 else 0
        print(f"  {hs:<12} | {d['O']:>6} | {d['L']:>6} | {d['P']:>6} | {pct:>6.1f}%")

    # Regional footprint
    print(f"\n--- REGIONAL FOOTPRINT ---")
    regions = defaultdict(lambda: defaultdict(int))
    for r in rows:
        company = safe_str(r.get('Company')) or 'Unknown'
        region = safe_str(r.get('Region')) or 'Unknown'
        qty = int(safe_float(r.get('Quantity')) or 0)
        if company in hyperscalers:
            regions[company][region] += qty

    print(f"  {'Company':<12} | {'AMER':>6} | {'APAC':>6} | {'EMEA':>6}")
    print("  " + "-" * 45)
    for hs in hyperscalers:
        d = regions.get(hs, {})
        print(f"  {hs:<12} | {d.get('AMER',0):>6} | {d.get('APAC',0):>6} | {d.get('EMEA',0):>6}")

    print(f"""
================================================================================
SYNERGY BEST USE CASES FOR BUSINESS DECISIONS
================================================================================

1. COMPETITIVE POSITIONING
   - Compare Meta's owned vs leased ratio to competitors
   - Track shifts in ownership strategy over time
   - Benchmark against industry trends

2. MARKET ENTRY INTELLIGENCE
   - Identify where competitors are expanding (region trends)
   - Track first-mover advantage opportunities
   - Inform land acquisition strategy

3. OWNERSHIP MODEL DECISIONS
   - Validate build vs buy decisions
   - Understand competitor leasing patterns
   - Correlate with CapEx/OpEx strategies

4. VALIDATION OF CONSENSUS MODEL
   - Cross-check hyperscaler facility counts
   - Flag gaps in coverage (SA/DCH missing sites)
   - Validate regional distribution

RECOMMENDED IMPLEMENTATION:
   - Keep as ENRICHMENT TABLE (not in gold_buildings - no coords)
   - Create synergy_ownership_summary table
   - Build quarterly trend dashboard
   - Add validation checks vs consensus counts
""")

    return {'records': len(rows)}


# ============================================================================
# MAIN
# ============================================================================

def main():
    print("=" * 80)
    print("DATA SOURCE COMPARISON ANALYSIS")
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 80)

    sa_results = compare_semianalysis()
    wm_results = compare_woodmac()
    synergy_results = synergy_business_recommendations()

    print("\n" + "=" * 80)
    print("EXECUTIVE SUMMARY & RECOMMENDATIONS")
    print("=" * 80)

    print(f"""
SEMIANALYSIS (Hive Pipeline Test)
---------------------------------
Records: {sa_results['new']:,} total rows, {sa_results.get('new_clusters', 'N/A'):,} unique clusters
Previous: {sa_results['old']:,} records

KEY FINDING: Data is in LONG/PIVOTED format (one row per cluster-year-quarter)
ACTION NEEDED:
  1. Pivot data back to wide format for ingestion
  2. Or create new time-series ingestion approach
  3. Update field mappings (lowercase_underscore naming)

WOODMAC (New Feb 2025 Dataset)
------------------------------
Records: {wm_results['new']:,} (up from {wm_results['old']:,})
Coordinates: {wm_results.get('coords', 0):,} records with lat/lon

KEY FINDING: New dataset has coordinates! Global coverage (not just US)
ACTION NEEDED:
  1. Update ingest_woodmac.py to use coordinates
  2. Can now ingest as spatial features to gold_buildings
  3. Add enrichment fields (cost, acreage, workload)

SYNERGY
-------
Records: {synergy_results['records']:,}
Coordinates: 0 (no geocoding)

BEST USES:
  1. Ownership intelligence (Owned/Leased/Partner ratios)
  2. Competitive positioning analysis
  3. Validation of consensus model counts
  4. Market expansion trend tracking
""")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
