"""
NPM vs Orennia Deep Source Overlap Analysis
Investigates whether Orennia is sourcing data from NPM (or vice versa).

This analysis checks for:
1. Exact coordinate matches (0m distance) - strong indicator of shared source
2. Identical capacity values - suggests same underlying data
3. Name similarity - facility/project name matching
4. Attribute-level comparison across all matched pairs

Purpose: Answer Sam's question - "Are NPM and Orennia data center lists nearly identical?"

Author: Meta Data Center GIS Team
Created: 2026-02-17
"""

import arcpy
import os
import sys
from datetime import datetime
from collections import defaultdict
import math

# Add _utils to path
try:
    script_dir = os.path.dirname(os.path.abspath(__file__))
except NameError:
    script_dir = r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\scripts\05_accuracy"

utils_dir = os.path.join(os.path.dirname(script_dir), "_utils")
if utils_dir not in sys.path:
    sys.path.insert(0, utils_dir)

from config import GOLD_BUILDINGS, GDB

# ============================================================================
# CONFIGURATION
# ============================================================================

ORENNIA_SOURCE = 'Orennia'
NPM_SOURCE = 'NewProjectMedia'

# Distance thresholds for analysis
EXACT_MATCH_THRESHOLD = 1      # 1 meter - essentially identical coordinates
VERY_CLOSE_THRESHOLD = 10      # 10 meters - rounding differences
CLOSE_THRESHOLD = 100          # 100 meters - same building/site
CAMPUS_THRESHOLD = 500         # 500 meters - same campus

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def haversine_distance(lat1, lon1, lat2, lon2):
    """Calculate distance between two lat/lon points in meters."""
    if None in [lat1, lon1, lat2, lon2]:
        return float('inf')

    R = 6371000
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = math.sin(delta_phi/2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

    return R * c

def normalize_name(name):
    """Normalize facility name for comparison."""
    if not name:
        return ""
    name = str(name).lower().strip()
    # Remove common suffixes
    for suffix in [' data center', ' data centres', ' dc', ' datacenter', ' - phase', ' phase']:
        name = name.replace(suffix, '')
    # Remove company prefixes
    for prefix in ['microsoft - ', 'google - ', 'meta - ', 'amazon - ', 'aws - ', 'oracle - ']:
        if name.startswith(prefix):
            name = name[len(prefix):]
    return name.strip()

def name_similarity(name1, name2):
    """Calculate simple similarity between two names (0-1)."""
    if not name1 or not name2:
        return 0

    n1 = normalize_name(name1)
    n2 = normalize_name(name2)

    if n1 == n2:
        return 1.0

    # Check if one contains the other
    if n1 in n2 or n2 in n1:
        return 0.8

    # Word overlap
    words1 = set(n1.split())
    words2 = set(n2.split())
    if not words1 or not words2:
        return 0

    overlap = len(words1 & words2)
    total = len(words1 | words2)

    return overlap / total if total > 0 else 0

def load_source_data(source_name):
    """Load all records from gold_buildings for a given source."""
    fields = [
        'OID@', 'unique_id', 'company_source', 'company_clean', 'company_clean_filter',
        'state_abbr', 'county', 'country', 'latitude', 'longitude',
        'full_capacity_mw', 'commissioned_power_mw', 'uc_power_mw', 'planned_power_mw',
        'facility_status', 'campus_name', 'building_designation', 'facility_sqft'
    ]

    records = []
    where = f"source = '{source_name}'"

    with arcpy.da.SearchCursor(GOLD_BUILDINGS, fields, where) as cursor:
        for row in cursor:
            records.append({
                'oid': row[0],
                'unique_id': row[1],
                'company_source': row[2],
                'company_clean': row[3],
                'company_clean_filter': row[4],
                'state_abbr': row[5],
                'county': row[6],
                'country': row[7],
                'latitude': row[8],
                'longitude': row[9],
                'full_capacity_mw': row[10],
                'commissioned_mw': row[11],
                'uc_mw': row[12],
                'planned_mw': row[13],
                'status': row[14],
                'campus_name': row[15],
                'building_name': row[16],
                'sqft': row[17],
            })

    return records

# ============================================================================
# ANALYSIS FUNCTIONS
# ============================================================================

def find_all_matches(orennia_records, npm_records, threshold_m):
    """Find all matching pairs within threshold."""
    matches = []

    for n_rec in npm_records:
        n_lat = n_rec.get('latitude')
        n_lon = n_rec.get('longitude')

        if n_lat is None or n_lon is None:
            continue

        best_match = None
        best_dist = float('inf')

        for o_rec in orennia_records:
            o_lat = o_rec.get('latitude')
            o_lon = o_rec.get('longitude')

            if o_lat is None or o_lon is None:
                continue

            dist = haversine_distance(n_lat, n_lon, o_lat, o_lon)

            if dist <= threshold_m and dist < best_dist:
                best_dist = dist
                best_match = o_rec

        if best_match:
            # Calculate attribute comparisons
            o_cap = best_match.get('full_capacity_mw') or 0
            n_cap = n_rec.get('full_capacity_mw') or 0

            matches.append({
                'npm': n_rec,
                'orennia': best_match,
                'distance_m': best_dist,
                'exact_coords': best_dist < EXACT_MATCH_THRESHOLD,
                'very_close': best_dist < VERY_CLOSE_THRESHOLD,
                'capacity_identical': o_cap > 0 and n_cap > 0 and abs(o_cap - n_cap) < 0.01,
                'capacity_similar': o_cap > 0 and n_cap > 0 and abs(o_cap - n_cap) / max(o_cap, n_cap) < 0.05,
                'name_similarity': name_similarity(n_rec.get('campus_name'), best_match.get('campus_name')),
                'company_match': (n_rec.get('company_clean') or '').lower() == (best_match.get('company_clean') or '').lower(),
                'state_match': n_rec.get('state_abbr') == best_match.get('state_abbr'),
                'npm_capacity': n_cap,
                'orennia_capacity': o_cap,
            })

    return matches

def analyze_source_overlap(matches, npm_total, orennia_total):
    """Analyze the overlap to determine if sources share underlying data."""

    results = {
        'total_npm': npm_total,
        'total_orennia': orennia_total,
        'matched_pairs': len(matches),
        'npm_match_rate': len(matches) / npm_total * 100 if npm_total > 0 else 0,
    }

    # Distance distribution
    exact_coords = sum(1 for m in matches if m['exact_coords'])
    very_close = sum(1 for m in matches if m['very_close'])
    close = sum(1 for m in matches if m['distance_m'] < CLOSE_THRESHOLD)

    results['distance_analysis'] = {
        'exact_match_0m': exact_coords,
        'exact_match_pct': exact_coords / len(matches) * 100 if matches else 0,
        'within_10m': very_close,
        'within_10m_pct': very_close / len(matches) * 100 if matches else 0,
        'within_100m': close,
        'within_100m_pct': close / len(matches) * 100 if matches else 0,
    }

    # Capacity analysis
    cap_identical = sum(1 for m in matches if m['capacity_identical'])
    cap_similar = sum(1 for m in matches if m['capacity_similar'])
    both_have_cap = sum(1 for m in matches if m['npm_capacity'] > 0 and m['orennia_capacity'] > 0)

    results['capacity_analysis'] = {
        'both_have_capacity': both_have_cap,
        'identical_values': cap_identical,
        'identical_pct': cap_identical / both_have_cap * 100 if both_have_cap > 0 else 0,
        'within_5pct': cap_similar,
        'within_5pct_pct': cap_similar / both_have_cap * 100 if both_have_cap > 0 else 0,
    }

    # Name similarity analysis
    high_name_sim = sum(1 for m in matches if m['name_similarity'] >= 0.8)
    some_name_sim = sum(1 for m in matches if m['name_similarity'] >= 0.5)

    results['name_analysis'] = {
        'high_similarity_80pct': high_name_sim,
        'high_similarity_pct': high_name_sim / len(matches) * 100 if matches else 0,
        'some_similarity_50pct': some_name_sim,
        'some_similarity_pct': some_name_sim / len(matches) * 100 if matches else 0,
    }

    # Company match analysis
    company_matches = sum(1 for m in matches if m['company_match'])
    results['company_analysis'] = {
        'same_company': company_matches,
        'same_company_pct': company_matches / len(matches) * 100 if matches else 0,
    }

    # Combined "smoking gun" analysis - records that match on ALL criteria
    smoking_gun = sum(1 for m in matches if
                      m['exact_coords'] and
                      m['company_match'] and
                      (m['capacity_identical'] or m['capacity_similar']))

    results['smoking_gun'] = {
        'exact_coords_AND_company_AND_capacity': smoking_gun,
        'pct_of_matches': smoking_gun / len(matches) * 100 if matches else 0,
    }

    return results

def print_detailed_report(results, matches):
    """Print detailed analysis report."""

    print("\n" + "=" * 80)
    print("NPM vs ORENNIA: DEEP SOURCE OVERLAP ANALYSIS")
    print("Investigating whether sources share underlying data")
    print("=" * 80)
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")

    print(f"\n{'RECORD COUNTS':=^80}")
    print(f"  NPM Records:              {results['total_npm']:,}")
    print(f"  Orennia Records:          {results['total_orennia']:,}")
    print(f"  Matched Pairs (500m):     {results['matched_pairs']:,}")
    print(f"  NPM Match Rate:           {results['npm_match_rate']:.1f}%")

    print(f"\n{'COORDINATE ANALYSIS - Key Indicator of Shared Source':=^80}")
    da = results['distance_analysis']
    print(f"  Exact coordinate match (0-1m):    {da['exact_match_0m']:,} ({da['exact_match_pct']:.1f}%)")
    print(f"  Very close (within 10m):          {da['within_10m']:,} ({da['within_10m_pct']:.1f}%)")
    print(f"  Close (within 100m):              {da['within_100m']:,} ({da['within_100m_pct']:.1f}%)")

    if da['exact_match_pct'] > 30:
        print(f"\n  ⚠️  HIGH EXACT MATCH RATE ({da['exact_match_pct']:.1f}%) - Strong evidence of shared data source")
    elif da['exact_match_pct'] > 10:
        print(f"\n  ⚡ MODERATE EXACT MATCH RATE ({da['exact_match_pct']:.1f}%) - Possible shared data source")
    else:
        print(f"\n  ✓  LOW EXACT MATCH RATE ({da['exact_match_pct']:.1f}%) - Likely independent data collection")

    print(f"\n{'CAPACITY VALUE ANALYSIS':=^80}")
    ca = results['capacity_analysis']
    print(f"  Pairs with capacity in both:      {ca['both_have_capacity']:,}")
    print(f"  Identical capacity values:        {ca['identical_values']:,} ({ca['identical_pct']:.1f}%)")
    print(f"  Within 5% of each other:          {ca['within_5pct']:,} ({ca['within_5pct_pct']:.1f}%)")

    if ca['identical_pct'] > 30:
        print(f"\n  ⚠️  HIGH IDENTICAL CAPACITY RATE ({ca['identical_pct']:.1f}%) - Strong evidence of shared data")
    elif ca['identical_pct'] > 10:
        print(f"\n  ⚡ MODERATE IDENTICAL CAPACITY RATE ({ca['identical_pct']:.1f}%) - Possible shared data")
    else:
        print(f"\n  ✓  LOW IDENTICAL CAPACITY RATE ({ca['identical_pct']:.1f}%) - Different capacity methodologies")

    print(f"\n{'NAME SIMILARITY ANALYSIS':=^80}")
    na = results['name_analysis']
    print(f"  High name similarity (≥80%):      {na['high_similarity_80pct']:,} ({na['high_similarity_pct']:.1f}%)")
    print(f"  Some name similarity (≥50%):      {na['some_similarity_50pct']:,} ({na['some_similarity_pct']:.1f}%)")

    print(f"\n{'COMPANY NAME ANALYSIS':=^80}")
    coa = results['company_analysis']
    print(f"  Same company name:                {coa['same_company']:,} ({coa['same_company_pct']:.1f}%)")

    print(f"\n{'SMOKING GUN ANALYSIS':=^80}")
    sg = results['smoking_gun']
    print(f"  Records matching ALL criteria:")
    print(f"    (Exact coords + Same company + Same/similar capacity)")
    print(f"  Count: {sg['exact_coords_AND_company_AND_capacity']:,}")
    print(f"  Percent of matched pairs: {sg['pct_of_matches']:.1f}%")

    # Show examples of exact matches
    print(f"\n{'EXAMPLE EXACT MATCHES (Top 15)':=^80}")
    exact_matches = sorted([m for m in matches if m['exact_coords']], key=lambda x: x['distance_m'])[:15]

    print(f"\n  {'Dist':>6} | {'Cap Match':^10} | {'NPM Company':<20} | {'Orennia Company':<20}")
    print("  " + "-" * 70)

    for m in exact_matches:
        dist = f"{m['distance_m']:.1f}m"
        cap_match = "IDENTICAL" if m['capacity_identical'] else "~5%" if m['capacity_similar'] else "DIFF"
        npm_co = (m['npm'].get('company_source') or '')[:20]
        oren_co = (m['orennia'].get('company_source') or '')[:20]
        print(f"  {dist:>6} | {cap_match:^10} | {npm_co:<20} | {oren_co:<20}")

    # Conclusion
    print(f"\n{'CONCLUSION':=^80}")

    # Scoring system for evidence strength
    score = 0
    evidence = []

    if da['exact_match_pct'] > 30:
        score += 3
        evidence.append(f"• {da['exact_match_pct']:.0f}% exact coordinate matches (strong)")
    elif da['exact_match_pct'] > 10:
        score += 1
        evidence.append(f"• {da['exact_match_pct']:.0f}% exact coordinate matches (moderate)")

    if ca['identical_pct'] > 30:
        score += 3
        evidence.append(f"• {ca['identical_pct']:.0f}% identical capacity values (strong)")
    elif ca['identical_pct'] > 10:
        score += 1
        evidence.append(f"• {ca['identical_pct']:.0f}% identical capacity values (moderate)")

    if sg['pct_of_matches'] > 20:
        score += 3
        evidence.append(f"• {sg['pct_of_matches']:.0f}% match on ALL criteria (strong)")
    elif sg['pct_of_matches'] > 5:
        score += 1
        evidence.append(f"• {sg['pct_of_matches']:.0f}% match on ALL criteria (moderate)")

    print(f"\n  Evidence Score: {score}/9")
    print(f"\n  Evidence:")
    for e in evidence:
        print(f"  {e}")

    if score >= 6:
        conclusion = "STRONG EVIDENCE that NPM and Orennia share the same underlying data source"
        print(f"\n  🚨 {conclusion}")
        print(f"     Sam's hypothesis is likely CORRECT - Orennia may be sourcing from NPM or both")
        print(f"     are sourcing from a common third-party data provider.")
    elif score >= 3:
        conclusion = "MODERATE EVIDENCE of shared data - some overlap but not conclusive"
        print(f"\n  ⚡ {conclusion}")
        print(f"     The sources have significant overlap but also show differences in")
        print(f"     capacity values and naming conventions that suggest some independent data.")
    else:
        conclusion = "WEAK EVIDENCE of shared data - sources appear largely independent"
        print(f"\n  ✓  {conclusion}")
        print(f"     While there is geographic overlap (expected for DC data), the differences")
        print(f"     in coordinates and capacity values suggest independent data collection.")

    print("\n" + "=" * 80)

    return {
        'conclusion': conclusion,
        'score': score,
        'evidence': evidence,
    }


# ============================================================================
# MAIN EXECUTION
# ============================================================================

def main():
    print("=" * 80)
    print("NPM vs ORENNIA: DEEP SOURCE OVERLAP ANALYSIS")
    print(f"Started: {datetime.now()}")
    print("=" * 80)

    print(f"\nTarget: {GOLD_BUILDINGS}")

    # Load data
    print("\nLoading NPM records...")
    npm_records = load_source_data(NPM_SOURCE)
    print(f"  Loaded {len(npm_records):,} NPM records")

    print("\nLoading Orennia records...")
    orennia_records = load_source_data(ORENNIA_SOURCE)
    print(f"  Loaded {len(orennia_records):,} Orennia records")

    if not npm_records or not orennia_records:
        print("\nERROR: Missing source data!")
        return None

    # Find all matches within 500m
    print("\nFinding matches within 500m...")
    matches = find_all_matches(orennia_records, npm_records, CAMPUS_THRESHOLD)
    print(f"  Found {len(matches):,} matched pairs")

    # Analyze overlap
    print("\nAnalyzing source overlap...")
    results = analyze_source_overlap(matches, len(npm_records), len(orennia_records))

    # Print detailed report
    conclusion = print_detailed_report(results, matches)

    print(f"\nCompleted: {datetime.now()}")

    return {
        'results': results,
        'conclusion': conclusion,
        'matches': matches,
    }


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\nERROR: {str(e)}")
        import traceback
        traceback.print_exc()
else:
    try:
        analysis_results = main()
    except Exception as e:
        print(f"\nERROR: {str(e)}")
        import traceback
        traceback.print_exc()
