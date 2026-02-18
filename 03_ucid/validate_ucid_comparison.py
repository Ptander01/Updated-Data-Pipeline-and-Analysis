"""
UCID Validation & Comparison Script
Compares TIGHT vs LOOSE clustering results and identifies edge cases.

This script:
1. Compares campus_master_tight vs campus_master_loose
2. Identifies potential false merges in LOOSE
3. Identifies potential orphan splits in TIGHT
4. Exports edge cases for manual review
5. Validates against Meta Canonical

Author: Meta Data Center GIS Team
Created: December 18, 2024
"""

import arcpy
import os
import sys
import csv
from datetime import datetime
from collections import defaultdict
import math

# Add _utils to path for config import
try:
    script_dir = os.path.dirname(os.path.abspath(__file__))
except NameError:
    script_dir = r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\scripts\06_ucid"

utils_dir = os.path.join(os.path.dirname(script_dir), "_utils")
if utils_dir not in sys.path:
    sys.path.insert(0, utils_dir)

from config import (GDB, GOLD_CAMPUS,
                    CAMPUS_MASTER_TIGHT, CAMPUS_MASTER_LOOSE,
                    META_CANONICAL_CAMPUS)

# Output directory
OUTPUT_DIR = os.path.join(os.path.dirname(script_dir), "outputs")
if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

arcpy.env.workspace = GDB

# ==============================================================================
# HELPER FUNCTIONS
# ==============================================================================

def haversine_distance(lat1, lon1, lat2, lon2):
    """Calculate great-circle distance in meters."""
    R = 6371000
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)
    a = math.sin(delta_lat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return R * c

def load_ucid_data(fc_path):
    """Load UCID data from campus_master feature class."""
    records = {}

    fields = ['ucid', 'canonical_name', 'company_canonical', 'city', 'state_abbr',
              'region', 'latitude', 'longitude', 'source_count', 'sources',
              'campus_ids', 'total_capacity_mw', 'building_count', 'meta_canonical_match']

    with arcpy.da.SearchCursor(fc_path, fields) as cursor:
        for row in cursor:
            records[row[0]] = {
                'ucid': row[0],
                'canonical_name': row[1],
                'company': row[2],
                'city': row[3],
                'state_abbr': row[4],
                'region': row[5],
                'lat': row[6],
                'lon': row[7],
                'source_count': row[8],
                'sources': row[9],
                'campus_ids': row[10],
                'capacity_mw': row[11] or 0,
                'building_count': row[12] or 0,
                'meta_match': row[13],
            }

    return records

def load_gold_campus_lookup():
    """Load gold_campus records indexed by campus_id."""
    records = {}

    fields = ['campus_id', 'SHAPE@XY', 'company_clean', 'campus_name', 'city',
              'state_abbr', 'source', 'full_capacity_mw']

    with arcpy.da.SearchCursor(GOLD_CAMPUS, fields) as cursor:
        for row in cursor:
            xy = row[1]
            if xy and row[0]:
                records[row[0]] = {
                    'campus_id': row[0],
                    'lat': xy[1],
                    'lon': xy[0],
                    'company': row[2],
                    'campus_name': row[3],
                    'city': row[4],
                    'state_abbr': row[5],
                    'source': row[6],
                    'capacity_mw': row[7] or 0,
                }

    return records

def find_potential_false_merges(tight_data, loose_data, gold_lookup):
    """
    Find campuses that LOOSE merged together but TIGHT kept separate.
    These are potential FALSE MERGES (distinct campuses incorrectly combined).
    """

    false_merges = []

    # Build index: campus_id -> UCID for both methods
    tight_campus_to_ucid = {}
    for ucid, data in tight_data.items():
        if data['campus_ids']:
            for cid in data['campus_ids'].split('; '):
                tight_campus_to_ucid[cid] = ucid

    loose_campus_to_ucid = {}
    for ucid, data in loose_data.items():
        if data['campus_ids']:
            for cid in data['campus_ids'].split('; '):
                loose_campus_to_ucid[cid] = ucid

    # Find cases where LOOSE merged but TIGHT didn't
    # Group TIGHT UCIDs that map to same LOOSE UCID
    loose_to_tight_ucids = defaultdict(set)
    for campus_id, tight_ucid in tight_campus_to_ucid.items():
        loose_ucid = loose_campus_to_ucid.get(campus_id)
        if loose_ucid:
            loose_to_tight_ucids[loose_ucid].add(tight_ucid)

    # Where LOOSE has 1 UCID but TIGHT has multiple, that's a potential false merge
    for loose_ucid, tight_ucids in loose_to_tight_ucids.items():
        if len(tight_ucids) > 1:
            loose_info = loose_data[loose_ucid]

            # Calculate distance between the tight clusters
            tight_records = [tight_data[uid] for uid in tight_ucids if uid in tight_data]
            if len(tight_records) >= 2:
                max_dist = 0
                for i, r1 in enumerate(tight_records):
                    for r2 in tight_records[i+1:]:
                        dist = haversine_distance(r1['lat'], r1['lon'], r2['lat'], r2['lon'])
                        max_dist = max(max_dist, dist)

                false_merges.append({
                    'loose_ucid': loose_ucid,
                    'loose_name': loose_info['canonical_name'],
                    'company': loose_info['company'],
                    'city': loose_info['city'],
                    'state': loose_info['state_abbr'],
                    'tight_ucids': list(tight_ucids),
                    'tight_count': len(tight_ucids),
                    'max_distance_m': max_dist,
                    'sources': loose_info['sources'],
                    'capacity_mw': loose_info['capacity_mw'],
                    'issue': 'POTENTIAL_FALSE_MERGE',
                    'severity': 'HIGH' if max_dist > 500 else 'MEDIUM',
                })

    # Sort by distance (larger = more likely false merge)
    false_merges.sort(key=lambda x: -x['max_distance_m'])

    return false_merges

def find_potential_orphan_splits(tight_data, loose_data, gold_lookup):
    """
    Find campuses that TIGHT kept separate but LOOSE merged.
    If LOOSE merge seems correct, these are ORPHAN SPLITS in TIGHT.
    """

    orphan_splits = []

    # Cases where multiple TIGHT UCIDs → 1 LOOSE UCID and distance is small
    # (These might be the same campus that TIGHT incorrectly split)

    tight_campus_to_ucid = {}
    for ucid, data in tight_data.items():
        if data['campus_ids']:
            for cid in data['campus_ids'].split('; '):
                tight_campus_to_ucid[cid] = ucid

    loose_campus_to_ucid = {}
    for ucid, data in loose_data.items():
        if data['campus_ids']:
            for cid in data['campus_ids'].split('; '):
                loose_campus_to_ucid[cid] = ucid

    # Group by LOOSE UCID
    loose_to_tight_ucids = defaultdict(set)
    for campus_id, tight_ucid in tight_campus_to_ucid.items():
        loose_ucid = loose_campus_to_ucid.get(campus_id)
        if loose_ucid:
            loose_to_tight_ucids[loose_ucid].add(tight_ucid)

    for loose_ucid, tight_ucids in loose_to_tight_ucids.items():
        if len(tight_ucids) > 1:
            loose_info = loose_data[loose_ucid]
            tight_records = [tight_data[uid] for uid in tight_ucids if uid in tight_data]

            if len(tight_records) >= 2:
                # Find max distance
                max_dist = 0
                min_dist = float('inf')
                for i, r1 in enumerate(tight_records):
                    for r2 in tight_records[i+1:]:
                        dist = haversine_distance(r1['lat'], r1['lon'], r2['lat'], r2['lon'])
                        max_dist = max(max_dist, dist)
                        min_dist = min(min_dist, dist)

                # If max distance is < 500m, LOOSE merge is probably correct
                # and TIGHT has orphan splits
                if max_dist < 500:
                    orphan_splits.append({
                        'loose_ucid': loose_ucid,
                        'loose_name': loose_info['canonical_name'],
                        'company': loose_info['company'],
                        'city': loose_info['city'],
                        'state': loose_info['state_abbr'],
                        'tight_ucids': list(tight_ucids),
                        'tight_count': len(tight_ucids),
                        'max_distance_m': max_dist,
                        'min_distance_m': min_dist,
                        'sources': loose_info['sources'],
                        'capacity_mw': loose_info['capacity_mw'],
                        'issue': 'POTENTIAL_ORPHAN_SPLIT',
                        'severity': 'MEDIUM' if max_dist > 300 else 'LOW',
                    })

    return orphan_splits

def find_hyperscaler_clusters(data, hyperscalers=['AWS', 'Microsoft', 'Google', 'Meta', 'Apple', 'Oracle']):
    """Find large hyperscaler campus clusters for review."""

    clusters = []

    for ucid, info in data.items():
        if info['company'] in hyperscalers:
            if info['source_count'] >= 2 or info['capacity_mw'] >= 100:
                clusters.append({
                    'ucid': ucid,
                    'canonical_name': info['canonical_name'],
                    'company': info['company'],
                    'city': info['city'],
                    'state': info['state_abbr'],
                    'source_count': info['source_count'],
                    'sources': info['sources'],
                    'capacity_mw': info['capacity_mw'],
                    'building_count': info['building_count'],
                    'meta_match': info['meta_match'],
                    'lat': info['lat'],
                    'lon': info['lon'],
                })

    # Sort by capacity
    clusters.sort(key=lambda x: -x['capacity_mw'])

    return clusters

def export_to_csv(data, filename, fieldnames=None):
    """Export data to CSV."""
    if not data:
        print(f"   - No data to export for {filename}")
        return

    filepath = os.path.join(OUTPUT_DIR, filename)

    if not fieldnames:
        fieldnames = list(data[0].keys())

    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(data)

    print(f"   - Exported {len(data)} rows to {filename}")

def validate_meta_canonical(tight_data, loose_data):
    """Check how well each method captures Meta Canonical campuses."""

    if not arcpy.Exists(META_CANONICAL_CAMPUS):
        print("   - WARNING: meta_canonical_campus not found - skipping validation")
        return None

    meta_campuses = []
    fields = ['SHAPE@XY', 'campus_name', 'dc_code', 'it_load_total']

    with arcpy.da.SearchCursor(META_CANONICAL_CAMPUS, fields) as cursor:
        for row in cursor:
            xy = row[0]
            if xy:
                meta_campuses.append({
                    'campus_name': row[1],
                    'dc_code': row[2],
                    'it_load_mw': row[3] or 0,
                    'lat': xy[1],
                    'lon': xy[0],
                })

    results = []

    for meta in meta_campuses:
        tight_matches = []
        loose_matches = []

        # Find closest TIGHT match
        for ucid, data in tight_data.items():
            dist = haversine_distance(meta['lat'], meta['lon'], data['lat'], data['lon'])
            if dist <= 1000:  # Within 1km
                tight_matches.append((ucid, data, dist))

        # Find closest LOOSE match
        for ucid, data in loose_data.items():
            dist = haversine_distance(meta['lat'], meta['lon'], data['lat'], data['lon'])
            if dist <= 1000:
                loose_matches.append((ucid, data, dist))

        # Sort by distance
        tight_matches.sort(key=lambda x: x[2])
        loose_matches.sort(key=lambda x: x[2])

        result = {
            'meta_campus': meta['campus_name'],
            'meta_dc_code': meta['dc_code'],
            'meta_it_load_mw': meta['it_load_mw'],
            'tight_match_count': len(tight_matches),
            'tight_best_ucid': tight_matches[0][0] if tight_matches else None,
            'tight_best_distance_m': round(tight_matches[0][2], 1) if tight_matches else None,
            'tight_best_capacity_mw': tight_matches[0][1]['capacity_mw'] if tight_matches else None,
            'tight_best_sources': tight_matches[0][1]['sources'] if tight_matches else None,
            'loose_match_count': len(loose_matches),
            'loose_best_ucid': loose_matches[0][0] if loose_matches else None,
            'loose_best_distance_m': round(loose_matches[0][2], 1) if loose_matches else None,
            'loose_best_capacity_mw': loose_matches[0][1]['capacity_mw'] if loose_matches else None,
            'loose_best_sources': loose_matches[0][1]['sources'] if loose_matches else None,
        }

        # Determine which is better
        if tight_matches and loose_matches:
            t_dist = tight_matches[0][2]
            l_dist = loose_matches[0][2]
            if abs(t_dist - l_dist) < 10:  # Within 10m = same
                result['winner'] = 'TIE'
            elif t_dist < l_dist:
                result['winner'] = 'TIGHT'
            else:
                result['winner'] = 'LOOSE'
        elif tight_matches:
            result['winner'] = 'TIGHT'
        elif loose_matches:
            result['winner'] = 'LOOSE'
        else:
            result['winner'] = 'NO_MATCH'

        results.append(result)

    return results

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================

def main():
    print("="*80)
    print("UCID VALIDATION & COMPARISON")
    print(f"Started: {datetime.now()}")
    print("="*80)

    # Step 1: Load data
    print("\n[Step 1] Loading UCID data...")

    if not arcpy.Exists(CAMPUS_MASTER_TIGHT):
        print("   ERROR: campus_master_tight not found. Run generate_ucid_clusters.py first.")
        return

    if not arcpy.Exists(CAMPUS_MASTER_LOOSE):
        print("   ERROR: campus_master_loose not found. Run generate_ucid_clusters.py first.")
        return

    tight_data = load_ucid_data(CAMPUS_MASTER_TIGHT)
    loose_data = load_ucid_data(CAMPUS_MASTER_LOOSE)
    gold_lookup = load_gold_campus_lookup()

    print(f"   - Loaded {len(tight_data):,} TIGHT UCIDs")
    print(f"   - Loaded {len(loose_data):,} LOOSE UCIDs")
    print(f"   - Loaded {len(gold_lookup):,} source campus records")

    # Step 2: Find potential false merges (LOOSE)
    print("\n[Step 2] Identifying potential FALSE MERGES in LOOSE...")
    false_merges = find_potential_false_merges(tight_data, loose_data, gold_lookup)
    print(f"   - Found {len(false_merges)} potential false merges")

    if false_merges:
        print("\n   Top 10 Potential False Merges (largest distance):")
        for fm in false_merges[:10]:
            print(f"      {fm['loose_name']}: {fm['tight_count']} TIGHT clusters merged, "
                  f"max distance {fm['max_distance_m']:.0f}m, {fm['severity']}")

    # Step 3: Find potential orphan splits (TIGHT)
    print("\n[Step 3] Identifying potential ORPHAN SPLITS in TIGHT...")
    orphan_splits = find_potential_orphan_splits(tight_data, loose_data, gold_lookup)
    print(f"   - Found {len(orphan_splits)} potential orphan splits")

    if orphan_splits:
        print("\n   Top 10 Potential Orphan Splits (should be merged):")
        for os_item in orphan_splits[:10]:
            print(f"      {os_item['loose_name']}: {os_item['tight_count']} TIGHT clusters, "
                  f"max distance {os_item['max_distance_m']:.0f}m, {os_item['severity']}")

    # Step 4: Validate against Meta Canonical
    print("\n[Step 4] Validating against Meta Canonical...")
    meta_validation = validate_meta_canonical(tight_data, loose_data)

    if meta_validation:
        winners = defaultdict(int)
        for mv in meta_validation:
            winners[mv['winner']] += 1

        print(f"\n   Meta Canonical Match Results:")
        for w, count in sorted(winners.items()):
            print(f"      {w}: {count} campuses")

    # Step 5: Find hyperscaler clusters
    print("\n[Step 5] Analyzing hyperscaler campus clusters...")
    tight_hyperscalers = find_hyperscaler_clusters(tight_data)
    loose_hyperscalers = find_hyperscaler_clusters(loose_data)

    print(f"   - TIGHT: {len(tight_hyperscalers)} major hyperscaler campuses")
    print(f"   - LOOSE: {len(loose_hyperscalers)} major hyperscaler campuses")

    # Step 6: Export results
    print("\n[Step 6] Exporting validation results...")

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    export_to_csv(false_merges, f'ucid_false_merges_{timestamp}.csv')
    export_to_csv(orphan_splits, f'ucid_orphan_splits_{timestamp}.csv')

    if meta_validation:
        export_to_csv(meta_validation, f'ucid_meta_validation_{timestamp}.csv')

    export_to_csv(tight_hyperscalers, f'ucid_hyperscalers_tight_{timestamp}.csv')
    export_to_csv(loose_hyperscalers, f'ucid_hyperscalers_loose_{timestamp}.csv')

    # Step 7: Summary and Recommendation
    print("\n" + "="*80)
    print("VALIDATION SUMMARY")
    print("="*80)

    print(f"\n{'Metric':<40} {'TIGHT':<15} {'LOOSE':<15}")
    print("-"*70)
    print(f"{'Total UCIDs':<40} {len(tight_data):<15,} {len(loose_data):<15,}")
    print(f"{'Potential false merges':<40} {'-':<15} {len(false_merges):<15}")
    print(f"{'Potential orphan splits':<40} {len(orphan_splits):<15} {'-':<15}")
    print(f"{'Hyperscaler campuses':<40} {len(tight_hyperscalers):<15} {len(loose_hyperscalers):<15}")

    if meta_validation:
        tight_wins = sum(1 for mv in meta_validation if mv['winner'] == 'TIGHT')
        loose_wins = sum(1 for mv in meta_validation if mv['winner'] == 'LOOSE')
        ties = sum(1 for mv in meta_validation if mv['winner'] == 'TIE')
        no_match = sum(1 for mv in meta_validation if mv['winner'] == 'NO_MATCH')

        print(f"{'Meta Canonical - TIGHT wins':<40} {tight_wins:<15}")
        print(f"{'Meta Canonical - LOOSE wins':<40} {'':<15} {loose_wins:<15}")
        print(f"{'Meta Canonical - TIE':<40} {ties:<15} {ties:<15}")
        print(f"{'Meta Canonical - NO MATCH':<40} {no_match:<15} {no_match:<15}")

    # Recommendation
    print("\n" + "="*80)
    print("RECOMMENDATION")
    print("="*80)

    high_severity_merges = sum(1 for fm in false_merges if fm['severity'] == 'HIGH')

    if high_severity_merges > len(orphan_splits):
        print("\n⚠️  RECOMMEND: TIGHT (250m)")
        print(f"   Reason: {high_severity_merges} high-severity false merges in LOOSE")
        print("   LOOSE appears to over-merge distinct neighboring campuses")
    elif len(orphan_splits) > high_severity_merges * 2:
        print("\n⚠️  RECOMMEND: LOOSE (1000m)")
        print(f"   Reason: {len(orphan_splits)} orphan splits in TIGHT")
        print("   TIGHT appears to incorrectly split sprawling campuses")
    else:
        print("\n⚠️  RECOMMEND: Manual review needed")
        print("   Neither method is clearly better")
        print("   Consider a MEDIUM tolerance (500m) or manual curation")

    print(f"\nExported files to: {OUTPUT_DIR}")
    print(f"\nCompleted: {datetime.now()}")
    print("="*80)

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
