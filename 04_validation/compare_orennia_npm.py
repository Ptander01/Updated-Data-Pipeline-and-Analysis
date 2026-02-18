"""
Orennia vs NPM Overlap Analysis Script
Compares Orennia and NPM datasets to identify duplicate/overlapping records.

Analysis Includes:
1. Record counts by source
2. Spatial proximity matching (within 500m, 1km, 2km thresholds)
3. Company name matching
4. State/Region overlap
5. Capacity comparison at matched locations
6. Detailed match report

Run this script in ArcGIS Pro Python window after ingesting both sources.

Author: Meta Data Center GIS Team
Created: 2026-02-12
"""

import arcpy
import os
import sys
from datetime import datetime
from collections import defaultdict
import math

# Add _utils to path for config import
try:
    script_dir = os.path.dirname(os.path.abspath(__file__))
except NameError:
    script_dir = r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\scripts\04_validation"

utils_dir = os.path.join(os.path.dirname(script_dir), "_utils")
if utils_dir not in sys.path:
    sys.path.insert(0, utils_dir)

from config import GOLD_BUILDINGS, GDB

# ============================================================================
# CONFIGURATION
# ============================================================================

# Spatial matching thresholds (meters)
THRESHOLD_TIGHT = 250    # Very likely same building/site
THRESHOLD_MEDIUM = 500   # Likely same campus
THRESHOLD_LOOSE = 1000   # Possibly related
THRESHOLD_WIDE = 2000    # Check for clustering

# Company name normalization keywords
COMPANY_ALIASES = {
    'aws': ['amazon', 'aws', 'amazon web services'],
    'microsoft': ['microsoft', 'azure', 'msft'],
    'google': ['google', 'gcp', 'alphabet'],
    'meta': ['meta', 'facebook', 'fb'],
    'apple': ['apple'],
    'oracle': ['oracle', 'oci'],
    'equinix': ['equinix'],
    'digital realty': ['digital realty', 'digitalrealty', 'dlr'],
    'coreweave': ['coreweave', 'core weave'],
    'vantage': ['vantage'],
    'cyrusone': ['cyrusone', 'cyrus one'],
    'qts': ['qts', 'quality technology services'],
    'flexential': ['flexential', 'peak 10'],
    'cologix': ['cologix'],
    'compass': ['compass'],
    'stack': ['stack infrastructure', 'stack infra'],
}

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def haversine_distance(lat1, lon1, lat2, lon2):
    """Calculate distance between two lat/lon points in meters."""
    if None in [lat1, lon1, lat2, lon2]:
        return float('inf')

    R = 6371000  # Earth radius in meters

    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = math.sin(delta_phi/2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

    return R * c

def normalize_company(company):
    """Normalize company name for matching."""
    if not company:
        return None

    company_lower = str(company).lower().strip()

    for canonical, aliases in COMPANY_ALIASES.items():
        for alias in aliases:
            if alias in company_lower:
                return canonical

    # Return cleaned version if no alias found
    return company_lower.replace(',', '').replace('.', '').replace(' inc', '').replace(' llc', '').strip()

def safe_float(val):
    """Safely convert to float."""
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None

def safe_str(val):
    """Safely convert to string."""
    if val is None:
        return None
    s = str(val).strip()
    return s if s and s.lower() not in ['none', 'nan', ''] else None

# ============================================================================
# DATA LOADING
# ============================================================================

def load_source_data(source_name):
    """Load all records from gold_buildings for a given source."""
    fields = [
        'OID@', 'SHAPE@XY', 'unique_id', 'source', 'company_source', 'company_clean',
        'company_clean_filter', 'state_abbr', 'county', 'country', 'region',
        'latitude', 'longitude', 'full_capacity_mw', 'facility_status',
        'campus_name', 'building_designation'
    ]

    records = []
    where = f"source = '{source_name}'"

    try:
        with arcpy.da.SearchCursor(GOLD_BUILDINGS, fields, where) as cursor:
            for row in cursor:
                records.append({
                    'oid': row[0],
                    'xy': row[1],
                    'unique_id': row[2],
                    'source': row[3],
                    'company_source': row[4],
                    'company_clean': row[5],
                    'company_clean_filter': row[6],
                    'state_abbr': row[7],
                    'county': row[8],
                    'country': row[9],
                    'region': row[10],
                    'latitude': row[11],
                    'longitude': row[12],
                    'capacity_mw': row[13],
                    'status': row[14],
                    'campus_name': row[15],
                    'building_name': row[16],
                    'company_normalized': normalize_company(row[4] or row[5]),
                })
    except Exception as e:
        print(f"Error loading {source_name}: {e}")

    return records

# ============================================================================
# SPATIAL MATCHING
# ============================================================================

def find_spatial_matches(orennia_records, npm_records, threshold_m):
    """Find records within threshold distance of each other."""
    matches = []

    for o_rec in orennia_records:
        o_lat = o_rec.get('latitude')
        o_lon = o_rec.get('longitude')

        if o_lat is None or o_lon is None:
            continue

        for n_rec in npm_records:
            n_lat = n_rec.get('latitude')
            n_lon = n_rec.get('longitude')

            if n_lat is None or n_lon is None:
                continue

            dist = haversine_distance(o_lat, o_lon, n_lat, n_lon)

            if dist <= threshold_m:
                matches.append({
                    'orennia': o_rec,
                    'npm': n_rec,
                    'distance_m': dist,
                    'company_match': o_rec['company_normalized'] == n_rec['company_normalized'] if o_rec['company_normalized'] and n_rec['company_normalized'] else False,
                    'state_match': o_rec['state_abbr'] == n_rec['state_abbr'] if o_rec['state_abbr'] and n_rec['state_abbr'] else False,
                })

    return matches

def dedupe_matches(matches, by_orennia=True):
    """Deduplicate matches, keeping closest match for each Orennia or NPM record."""
    if by_orennia:
        key_func = lambda m: m['orennia']['unique_id']
    else:
        key_func = lambda m: m['npm']['unique_id']

    best_matches = {}
    for m in matches:
        key = key_func(m)
        if key not in best_matches or m['distance_m'] < best_matches[key]['distance_m']:
            best_matches[key] = m

    return list(best_matches.values())

# ============================================================================
# ANALYSIS FUNCTIONS
# ============================================================================

def analyze_overlap(orennia_records, npm_records):
    """Comprehensive overlap analysis."""
    results = {
        'orennia_count': len(orennia_records),
        'npm_count': len(npm_records),
        'spatial_matches': {},
        'company_overlap': {},
        'state_overlap': {},
        'detailed_matches': [],
    }

    # Spatial matches at different thresholds
    for threshold, label in [(THRESHOLD_TIGHT, '250m'), (THRESHOLD_MEDIUM, '500m'),
                              (THRESHOLD_LOOSE, '1km'), (THRESHOLD_WIDE, '2km')]:
        matches = find_spatial_matches(orennia_records, npm_records, threshold)
        deduped_by_orennia = dedupe_matches(matches, by_orennia=True)
        deduped_by_npm = dedupe_matches(matches, by_orennia=False)

        results['spatial_matches'][label] = {
            'raw_match_count': len(matches),
            'unique_orennia_matched': len(deduped_by_orennia),
            'unique_npm_matched': len(deduped_by_npm),
            'orennia_match_pct': len(deduped_by_orennia) / len(orennia_records) * 100 if orennia_records else 0,
            'npm_match_pct': len(deduped_by_npm) / len(npm_records) * 100 if npm_records else 0,
        }

        # Store detailed matches at 500m threshold
        if label == '500m':
            results['detailed_matches'] = deduped_by_orennia

    # Company overlap analysis
    orennia_companies = set(r['company_normalized'] for r in orennia_records if r['company_normalized'])
    npm_companies = set(r['company_normalized'] for r in npm_records if r['company_normalized'])
    common_companies = orennia_companies & npm_companies

    results['company_overlap'] = {
        'orennia_unique_companies': len(orennia_companies),
        'npm_unique_companies': len(npm_companies),
        'common_companies': len(common_companies),
        'common_company_list': sorted(common_companies)[:30],
    }

    # State overlap analysis
    orennia_states = defaultdict(int)
    npm_states = defaultdict(int)

    for r in orennia_records:
        if r['state_abbr']:
            orennia_states[r['state_abbr']] += 1

    for r in npm_records:
        if r['state_abbr']:
            npm_states[r['state_abbr']] += 1

    results['state_overlap'] = {
        'orennia_states': dict(orennia_states),
        'npm_states': dict(npm_states),
        'common_states': set(orennia_states.keys()) & set(npm_states.keys()),
    }

    # Capacity comparison at matched locations
    matched_capacity = {
        'orennia_total_mw': 0,
        'npm_total_mw': 0,
        'orennia_matched_mw': 0,
        'npm_matched_mw': 0,
    }

    for r in orennia_records:
        if r['capacity_mw']:
            matched_capacity['orennia_total_mw'] += r['capacity_mw']

    for r in npm_records:
        if r['capacity_mw']:
            matched_capacity['npm_total_mw'] += r['capacity_mw']

    for m in results['detailed_matches']:
        if m['orennia']['capacity_mw']:
            matched_capacity['orennia_matched_mw'] += m['orennia']['capacity_mw']
        if m['npm']['capacity_mw']:
            matched_capacity['npm_matched_mw'] += m['npm']['capacity_mw']

    results['capacity'] = matched_capacity

    return results

def print_report(results):
    """Print formatted overlap report."""
    print("\n" + "=" * 80)
    print("ORENNIA vs NPM OVERLAP ANALYSIS REPORT")
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 80)

    print(f"\n{'RECORD COUNTS':=^80}")
    print(f"  Orennia: {results['orennia_count']:,} records")
    print(f"  NPM:     {results['npm_count']:,} records")

    print(f"\n{'SPATIAL PROXIMITY MATCHING':=^80}")
    print(f"  {'Threshold':<12} | {'Raw Matches':>12} | {'Orennia Matched':>16} | {'NPM Matched':>12}")
    print("  " + "-" * 70)

    for threshold, data in results['spatial_matches'].items():
        print(f"  {threshold:<12} | {data['raw_match_count']:>12,} | "
              f"{data['unique_orennia_matched']:>6,} ({data['orennia_match_pct']:>5.1f}%) | "
              f"{data['unique_npm_matched']:>5,} ({data['npm_match_pct']:>5.1f}%)")

    print(f"\n{'COMPANY OVERLAP':=^80}")
    co = results['company_overlap']
    print(f"  Orennia unique companies: {co['orennia_unique_companies']:,}")
    print(f"  NPM unique companies:     {co['npm_unique_companies']:,}")
    print(f"  Common companies:         {co['common_companies']:,}")

    if co['common_company_list']:
        print(f"\n  Top common companies:")
        for c in co['common_company_list'][:20]:
            print(f"    - {c}")

    print(f"\n{'STATE DISTRIBUTION':=^80}")

    # Top states comparison
    orennia_top = sorted(results['state_overlap']['orennia_states'].items(), key=lambda x: -x[1])[:10]
    npm_top = sorted(results['state_overlap']['npm_states'].items(), key=lambda x: -x[1])[:10]

    print(f"\n  {'Orennia Top States':<25} | {'NPM Top States':<25}")
    print("  " + "-" * 55)

    for i in range(max(len(orennia_top), len(npm_top))):
        o_str = f"{orennia_top[i][0]}: {orennia_top[i][1]:,}" if i < len(orennia_top) else ""
        n_str = f"{npm_top[i][0]}: {npm_top[i][1]:,}" if i < len(npm_top) else ""
        print(f"  {o_str:<25} | {n_str:<25}")

    print(f"\n{'CAPACITY COMPARISON':=^80}")
    cap = results['capacity']
    print(f"  Orennia total capacity:   {cap['orennia_total_mw']:>12,.0f} MW")
    print(f"  NPM total capacity:       {cap['npm_total_mw']:>12,.0f} MW")
    print(f"  Orennia matched capacity: {cap['orennia_matched_mw']:>12,.0f} MW ({cap['orennia_matched_mw']/cap['orennia_total_mw']*100:.1f}% of Orennia)" if cap['orennia_total_mw'] else "")
    print(f"  NPM matched capacity:     {cap['npm_matched_mw']:>12,.0f} MW ({cap['npm_matched_mw']/cap['npm_total_mw']*100:.1f}% of NPM)" if cap['npm_total_mw'] else "")

    # Detailed match examples
    print(f"\n{'DETAILED MATCH EXAMPLES (closest 20)':=^80}")
    sorted_matches = sorted(results['detailed_matches'], key=lambda x: x['distance_m'])[:20]

    print(f"\n  {'Dist':>6} | {'Company Match':^14} | {'Orennia Company':<20} | {'NPM Company':<20}")
    print("  " + "-" * 75)

    for m in sorted_matches:
        dist = f"{m['distance_m']:.0f}m"
        co_match = "YES" if m['company_match'] else "no"
        o_co = (m['orennia']['company_source'] or '')[:20]
        n_co = (m['npm']['company_source'] or '')[:20]
        print(f"  {dist:>6} | {co_match:^14} | {o_co:<20} | {n_co:<20}")

    # Summary and recommendations
    print(f"\n{'SUMMARY & RECOMMENDATIONS':=^80}")

    match_500m = results['spatial_matches'].get('500m', {})
    orennia_pct = match_500m.get('orennia_match_pct', 0)
    npm_pct = match_500m.get('npm_match_pct', 0)

    if npm_pct > 70:
        severity = "HIGH OVERLAP"
        recommendation = """
  [!] HIGH OVERLAP DETECTED

  NPM appears to be largely redundant with Orennia at 500m threshold.

  RECOMMENDATIONS:
  1. PRIMARY: Use Orennia as main source (larger dataset, more attributes)
  2. NPM ENRICHMENT: Use NPM only for records that DON'T match Orennia
  3. DEDUPLICATION: Consider removing NPM source or flagging as secondary
  4. VALIDATION: Use NPM as validation layer for Orennia data quality
"""
    elif npm_pct > 40:
        severity = "MODERATE OVERLAP"
        recommendation = """
  [~] MODERATE OVERLAP DETECTED

  Significant overlap exists but both sources provide unique records.

  RECOMMENDATIONS:
  1. UCID DEDUPLICATION: Run UCID generation to cluster similar records
  2. PRIORITY: Set Orennia as primary, NPM as secondary for overlapping campuses
  3. GAP ANALYSIS: Identify NPM records NOT in Orennia for manual review
  4. FIELD ENRICHMENT: Use NPM fields not available in Orennia
"""
    else:
        severity = "LOW OVERLAP"
        recommendation = """
  [OK] LOW OVERLAP - Sources are complementary

  Both sources provide largely unique records.

  RECOMMENDATIONS:
  1. KEEP BOTH: Ingest both sources to maximize coverage
  2. UCID: Generate UCIDs to handle the small overlap
  3. REVIEW: Spot-check the matched records for data quality
"""

    print(f"\n  OVERLAP SEVERITY: {severity}")
    print(f"  - {orennia_pct:.1f}% of Orennia records match NPM within 500m")
    print(f"  - {npm_pct:.1f}% of NPM records match Orennia within 500m")
    print(recommendation)

    print("=" * 80)

    return results

# ============================================================================
# MAIN EXECUTION
# ============================================================================

def main():
    print("=" * 80)
    print("ORENNIA vs NPM OVERLAP ANALYSIS")
    print(f"Started: {datetime.now()}")
    print("=" * 80)

    print(f"\nTarget Feature Class: {GOLD_BUILDINGS}")

    # Check if feature class exists
    if not arcpy.Exists(GOLD_BUILDINGS):
        raise Exception(f"Feature class not found: {GOLD_BUILDINGS}")

    # Load data
    print("\nLoading Orennia records...")
    orennia_records = load_source_data('Orennia')
    print(f"  Loaded {len(orennia_records):,} Orennia records")

    print("\nLoading NPM records...")
    # NPM is stored with source='NewProjectMedia' in gold_buildings
    npm_records = load_source_data('NewProjectMedia')
    print(f"  Loaded {len(npm_records):,} NPM records")

    if len(npm_records) == 0:
        print("\n[WARNING] No NPM records found in gold_buildings_full!")
        print("  NPM may not be ingested yet. Run ingest_npm.py first.")
        print("\n  Checking npm_raw table...")

        npm_raw = os.path.join(GDB, "npm_raw")
        if arcpy.Exists(npm_raw):
            npm_raw_count = int(arcpy.GetCount_management(npm_raw)[0])
            print(f"  npm_raw has {npm_raw_count:,} records - needs ingestion to gold_buildings")
        else:
            print("  npm_raw table not found either!")
        return

    # Run analysis
    print("\nAnalyzing overlap...")
    results = analyze_overlap(orennia_records, npm_records)

    # Print report
    print_report(results)

    print(f"\nCompleted: {datetime.now()}")

    return results


# ============================================================================
# EXECUTE
# ============================================================================

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\nERROR: {str(e)}")
        import traceback
        traceback.print_exc()
else:
    # Running in ArcGIS Pro Python window
    try:
        main()
    except Exception as e:
        print(f"\nERROR: {str(e)}")
        import traceback
        traceback.print_exc()
