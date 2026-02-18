"""
SA Cluster vs UCID Clustering Validation Script (Phase 1)
Compares SemiAnalysis native cluster field against our UCID clustering.
Validates both methods against Meta Canonical ground truth.

This script implements the Phase 1 validation study from UCID_SA_DCH_IMPROVEMENT_PLAN.md:
- Method A: SA Native Cluster (company + city + cluster field)
- Method B: Our UCID Clustering (company + 250m spatial proximity)
- Ground Truth: Meta Canonical campuses

Author: Meta Data Center GIS Team
Created: 2026-02-11
"""

import arcpy
import os
import sys
import csv
import math
from datetime import datetime
from collections import defaultdict

# Add _utils to path for config import
try:
    script_dir = os.path.dirname(os.path.abspath(__file__))
except NameError:
    script_dir = r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\scripts\04_validation"

utils_dir = os.path.join(os.path.dirname(script_dir), "_utils")
if utils_dir not in sys.path:
    sys.path.insert(0, utils_dir)

from config import (GDB, GOLD_BUILDINGS, GOLD_CAMPUS,
                    META_CANONICAL_V2_FILTERED, META_CANONICAL_CAMPUS,
                    CAMPUS_MASTER_TIGHT, UCID_TOLERANCE_TIGHT)

# Output directory
OUTPUT_DIR = os.path.join(os.path.dirname(script_dir), "outputs")
if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

arcpy.env.workspace = GDB

# Configuration
MATCH_RADIUS_M = 500  # Match SA records within 500m of Meta Canonical campus


# ==============================================================================
# HAVERSINE DISTANCE
# ==============================================================================

def haversine_distance(lat1, lon1, lat2, lon2):
    """
    Calculate great-circle distance between two points in meters.
    Used for accurate spatial matching across the globe.
    """
    R = 6371000  # Earth's radius in meters

    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)

    a = math.sin(delta_lat/2)**2 + \
        math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

    return R * c


# ==============================================================================
# DATA LOADING FUNCTIONS
# ==============================================================================

def load_sa_records():
    """
    Load SemiAnalysis records from gold_buildings.
    Returns list of dicts with coordinates, company, city, and cluster field.
    """
    print("   Loading SemiAnalysis records from gold_buildings...")

    records = []
    fields = ['unique_id', 'SHAPE@XY', 'company_clean', 'city', 'state_abbr',
              'building_designation', 'campus_id', 'full_capacity_mw', 'ucid']

    where_clause = "source = 'Semianalysis'"

    with arcpy.da.SearchCursor(GOLD_BUILDINGS, fields, where_clause) as cursor:
        for row in cursor:
            xy = row[1]
            if xy and xy[0] and xy[1]:
                records.append({
                    'unique_id': row[0],
                    'lat': xy[1],
                    'lon': xy[0],
                    'company': row[2],
                    'city': row[3],
                    'state': row[4],
                    'cluster': row[5],  # building_designation = SA's Cluster field
                    'campus_id': row[6],
                    'capacity_mw': row[7] or 0,
                    'ucid': row[8],  # Our assigned UCID
                })

    print(f"   Loaded {len(records):,} SA records with coordinates")
    return records


def load_meta_canonical_campuses():
    """
    Load Meta Canonical campuses as ground truth.
    First tries META_CANONICAL_CAMPUS, then falls back to META_CANONICAL_V2_FILTERED.
    """
    print("   Loading Meta Canonical campuses (ground truth)...")

    campuses = []

    # Try the campus-level table first
    source_fc = None
    if arcpy.Exists(META_CANONICAL_CAMPUS):
        source_fc = META_CANONICAL_CAMPUS
        # Schema: dc_code, region_derived, building_count, it_load_total, etc.
        fields = ['SHAPE@XY', 'dc_code', 'it_load_total', 'region_derived']
    elif arcpy.Exists(META_CANONICAL_V2_FILTERED):
        source_fc = META_CANONICAL_V2_FILTERED
        fields = ['SHAPE@XY', 'site_code', 'it_power_mw_current', 'region']
    else:
        print("   WARNING: No Meta Canonical feature class found!")
        return campuses

    print(f"   Using: {os.path.basename(source_fc)}")

    with arcpy.da.SearchCursor(source_fc, fields) as cursor:
        for row in cursor:
            xy = row[0]
            # Skip records at null island (0,0) or without coordinates
            if xy and xy[0] and xy[1] and not (xy[0] == 0 and xy[1] == 0):
                dc_code = row[1]
                campuses.append({
                    'campus_name': dc_code,  # Use dc_code as campus name
                    'dc_code': dc_code,
                    'it_load_mw': row[2] or 0,
                    'company': 'Meta',  # All Meta Canonical are Meta
                    'region': row[3],
                    'lat': xy[1],
                    'lon': xy[0],
                })

    print(f"   Loaded {len(campuses):,} Meta Canonical campuses")
    return campuses


def load_ucid_assignments():
    """
    Load UCID assignments from campus_master_tight if available.
    Returns dict mapping campus_id -> ucid.
    """
    print("   Loading UCID assignments...")

    if not arcpy.Exists(CAMPUS_MASTER_TIGHT):
        print("   WARNING: campus_master_tight not found - will use UCIDs from gold_buildings")
        return {}

    ucid_map = {}
    fields = ['ucid', 'campus_ids']

    with arcpy.da.SearchCursor(CAMPUS_MASTER_TIGHT, fields) as cursor:
        for row in cursor:
            ucid = row[0]
            campus_ids = row[1]
            if campus_ids:
                for cid in campus_ids.split('; '):
                    ucid_map[cid] = ucid

    print(f"   Loaded {len(ucid_map):,} campus_id -> UCID mappings")
    return ucid_map


# ==============================================================================
# CLUSTERING METHOD IMPLEMENTATIONS
# ==============================================================================

def build_sa_native_cluster_ids(sa_records):
    """
    Build SA Native Cluster IDs using SA's own cluster field.
    Format: {company}|{city}|{cluster}

    This uses SemiAnalysis's native grouping from their data.
    """
    print("\n[Method A] Building SA Native Cluster IDs...")

    cluster_map = {}
    cluster_stats = defaultdict(int)

    for rec in sa_records:
        company = rec['company'] or 'Unknown'
        city = rec['city'] or 'Unknown'
        cluster = rec['cluster'] or ''

        # Create SA native cluster ID
        native_id = f"{company}|{city}|{cluster}".lower()
        cluster_map[rec['unique_id']] = native_id
        cluster_stats[native_id] += 1

    unique_clusters = len(cluster_stats)
    avg_per_cluster = len(sa_records) / unique_clusters if unique_clusters > 0 else 0

    print(f"   Generated {unique_clusters:,} unique SA native cluster IDs")
    print(f"   Average records per cluster: {avg_per_cluster:.1f}")

    # Show distribution
    sizes = list(cluster_stats.values())
    print(f"   Single-record clusters: {sum(1 for s in sizes if s == 1):,}")
    print(f"   Multi-record clusters: {sum(1 for s in sizes if s > 1):,}")
    print(f"   Largest cluster: {max(sizes)} records")

    return cluster_map


def build_ucid_cluster_ids(sa_records, ucid_map):
    """
    Build UCID Cluster IDs using our spatial clustering methodology.
    Uses the UCID assigned during campus rollup (company + 250m proximity).
    """
    print("\n[Method B] Building UCID Cluster IDs...")

    cluster_map = {}
    cluster_stats = defaultdict(int)
    missing_ucid = 0

    for rec in sa_records:
        # Get UCID from the record or from the ucid_map
        ucid = rec['ucid']
        if not ucid and rec['campus_id'] in ucid_map:
            ucid = ucid_map[rec['campus_id']]

        if ucid:
            cluster_map[rec['unique_id']] = ucid
            cluster_stats[ucid] += 1
        else:
            # Fallback: use campus_id if no UCID assigned
            fallback_id = rec['campus_id'] or f"NO_UCID_{rec['unique_id']}"
            cluster_map[rec['unique_id']] = fallback_id
            cluster_stats[fallback_id] += 1
            missing_ucid += 1

    unique_clusters = len(cluster_stats)
    avg_per_cluster = len(sa_records) / unique_clusters if unique_clusters > 0 else 0

    print(f"   Generated {unique_clusters:,} unique UCIDs")
    print(f"   Records without UCID (using campus_id): {missing_ucid:,}")
    print(f"   Average records per cluster: {avg_per_cluster:.1f}")

    # Show distribution
    sizes = list(cluster_stats.values())
    print(f"   Single-record clusters: {sum(1 for s in sizes if s == 1):,}")
    print(f"   Multi-record clusters: {sum(1 for s in sizes if s > 1):,}")
    print(f"   Largest cluster: {max(sizes)} records")

    return cluster_map


# ==============================================================================
# VALIDATION AGAINST META CANONICAL
# ==============================================================================

def find_sa_records_near_meta(meta_campus, sa_records, radius_m):
    """Find all SA records within radius of a Meta Canonical campus."""
    nearby = []

    for rec in sa_records:
        dist = haversine_distance(
            meta_campus['lat'], meta_campus['lon'],
            rec['lat'], rec['lon']
        )
        if dist <= radius_m:
            nearby.append({**rec, 'distance_m': dist})

    return nearby


def validate_against_meta_canonical(sa_records, sa_native_clusters, ucid_clusters, meta_campuses):
    """
    Compare both clustering methods against Meta Canonical ground truth.

    For each Meta Canonical campus:
    1. Find SA records within 500m
    2. Check if all nearby SA records have the same SA native cluster ID
    3. Check if all nearby SA records have the same UCID
    4. Determine which method better matches ground truth
    """
    print("\n[Validation] Comparing methods against Meta Canonical...")

    results = []

    for meta in meta_campuses:
        # Find SA records within match radius
        nearby_sa = find_sa_records_near_meta(meta, sa_records, MATCH_RADIUS_M)

        if not nearby_sa:
            results.append({
                'meta_campus': meta['campus_name'],
                'meta_dc_code': meta['dc_code'],
                'meta_company': meta['company'],
                'meta_it_load_mw': meta['it_load_mw'],
                'sa_records_found': 0,
                'sa_native_clusters': 0,
                'sa_native_consistent': None,
                'ucid_clusters': 0,
                'ucid_consistent': None,
                'winner': 'NO_SA_DATA',
                'notes': 'No SA records within 500m',
            })
            continue

        # Get cluster IDs for nearby SA records
        sa_native_ids = set()
        ucid_ids = set()

        for rec in nearby_sa:
            uid = rec['unique_id']
            if uid in sa_native_clusters:
                sa_native_ids.add(sa_native_clusters[uid])
            if uid in ucid_clusters:
                ucid_ids.add(ucid_clusters[uid])

        # Check consistency
        sa_native_consistent = len(sa_native_ids) == 1
        ucid_consistent = len(ucid_ids) == 1

        # Determine winner
        if sa_native_consistent and ucid_consistent:
            winner = 'TIE'
            notes = 'Both methods group all nearby SA records together'
        elif sa_native_consistent and not ucid_consistent:
            winner = 'SA_NATIVE'
            notes = f'SA grouped correctly, UCID split into {len(ucid_ids)} clusters'
        elif ucid_consistent and not sa_native_consistent:
            winner = 'UCID'
            notes = f'UCID grouped correctly, SA split into {len(sa_native_ids)} clusters'
        else:
            winner = 'BOTH_SPLIT'
            notes = f'Both methods split: SA={len(sa_native_ids)}, UCID={len(ucid_ids)} clusters'

        # Calculate capacity match
        total_sa_capacity = sum(rec['capacity_mw'] for rec in nearby_sa)

        results.append({
            'meta_campus': meta['campus_name'],
            'meta_dc_code': meta['dc_code'],
            'meta_company': meta['company'],
            'meta_it_load_mw': meta['it_load_mw'],
            'sa_records_found': len(nearby_sa),
            'sa_total_capacity_mw': total_sa_capacity,
            'sa_native_clusters': len(sa_native_ids),
            'sa_native_consistent': sa_native_consistent,
            'sa_native_cluster_ids': '; '.join(sorted(sa_native_ids)[:3]),  # First 3 for readability
            'ucid_clusters': len(ucid_ids),
            'ucid_consistent': ucid_consistent,
            'ucid_cluster_ids': '; '.join(sorted(ucid_ids)[:3]),
            'winner': winner,
            'notes': notes,
            'closest_sa_distance_m': min(rec['distance_m'] for rec in nearby_sa),
            'farthest_sa_distance_m': max(rec['distance_m'] for rec in nearby_sa),
        })

    return results


# ==============================================================================
# SUMMARY AND REPORTING
# ==============================================================================

def calculate_summary_metrics(validation_results):
    """Calculate summary metrics from validation results."""

    total = len(validation_results)
    with_sa_data = sum(1 for r in validation_results if r['winner'] != 'NO_SA_DATA')

    winners = defaultdict(int)
    for r in validation_results:
        winners[r['winner']] += 1

    return {
        'total_meta_campuses': total,
        'with_sa_data': with_sa_data,
        'no_sa_data': winners['NO_SA_DATA'],
        'tie': winners['TIE'],
        'sa_native_wins': winners['SA_NATIVE'],
        'ucid_wins': winners['UCID'],
        'both_split': winners['BOTH_SPLIT'],
        'sa_match_rate': (winners['SA_NATIVE'] + winners['TIE']) / with_sa_data * 100 if with_sa_data > 0 else 0,
        'ucid_match_rate': (winners['UCID'] + winners['TIE']) / with_sa_data * 100 if with_sa_data > 0 else 0,
    }


def export_to_csv(data, filename, fieldnames=None):
    """Export data to CSV."""
    if not data:
        print(f"   - No data to export for {filename}")
        return

    filepath = os.path.join(OUTPUT_DIR, filename)

    if not fieldnames:
        fieldnames = list(data[0].keys())

    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(data)

    print(f"   - Exported {len(data)} rows to {filename}")
    return filepath


def generate_markdown_report(summary, validation_results, timestamp):
    """Generate a Markdown report with findings."""

    report_path = os.path.join(
        os.path.dirname(script_dir),
        "00_docs", "workflows", "SA_CLUSTER_VALIDATION_RESULTS.md"
    )

    content = f"""# SA Cluster vs UCID Validation Results

**Generated:** {timestamp}
**Status:** COMPLETE

---

## Executive Summary

This report compares SemiAnalysis's native `cluster` field against our UCID spatial clustering methodology, validated against Meta Canonical ground truth.

| Metric | SA Native Cluster | UCID (250m) |
|--------|-------------------|-------------|
| **Match Rate** | {summary['sa_match_rate']:.1f}% | {summary['ucid_match_rate']:.1f}% |
| **Clear Wins** | {summary['sa_native_wins']} campuses | {summary['ucid_wins']} campuses |

---

## Methodology

### Method A: SA Native Cluster
- Uses SemiAnalysis's native `Cluster` field (stored in `building_designation`)
- Format: `{{company}}|{{city}}|{{cluster}}`
- Represents SA's own grouping of buildings into sites

### Method B: UCID Clustering
- Uses our spatial clustering with 250m tolerance
- Groups by: company_clean + proximity (Haversine distance)
- Transitive clustering assigns same UCID to nearby same-company buildings

### Ground Truth: Meta Canonical
- Internal authoritative list of data center campuses
- Each campus should ideally map to exactly one cluster in each method

---

## Results Breakdown

| Result | Count | Percentage |
|--------|-------|------------|
| Total Meta Canonical Campuses | {summary['total_meta_campuses']} | 100% |
| With SA Data (within 500m) | {summary['with_sa_data']} | {summary['with_sa_data']/summary['total_meta_campuses']*100:.1f}% |
| No SA Data | {summary['no_sa_data']} | {summary['no_sa_data']/summary['total_meta_campuses']*100:.1f}% |

### Of campuses WITH SA data:

| Winner | Count | Percentage |
|--------|-------|------------|
| TIE (both correct) | {summary['tie']} | {summary['tie']/summary['with_sa_data']*100:.1f}% |
| SA Native Wins | {summary['sa_native_wins']} | {summary['sa_native_wins']/summary['with_sa_data']*100:.1f}% |
| UCID Wins | {summary['ucid_wins']} | {summary['ucid_wins']/summary['with_sa_data']*100:.1f}% |
| Both Split (both wrong) | {summary['both_split']} | {summary['both_split']/summary['with_sa_data']*100:.1f}% |

---

## Interpretation

"""

    # Determine recommendation
    if summary['ucid_match_rate'] > summary['sa_match_rate'] + 5:
        content += """### Recommendation: Continue with UCID

Our UCID spatial clustering outperforms SA's native cluster field:
- Higher match rate against Meta Canonical ground truth
- Cross-source capability (can group SA + DCH + other sources)
- More consistent results across different data versions

"""
    elif summary['sa_match_rate'] > summary['ucid_match_rate'] + 5:
        content += """### Recommendation: Consider SA Cluster Integration

SA's native cluster field shows better performance:
- Consider incorporating SA's cluster field into UCID generation
- May indicate SA has better visibility into building-to-campus relationships
- Review cases where SA wins to understand the pattern

"""
    else:
        content += """### Recommendation: Methods are Comparable

Both methods show similar performance:
- Continue with UCID for cross-source capability
- Consider using SA cluster as validation/confidence boost
- Manual review of "Both Split" cases may reveal edge patterns

"""

    content += f"""---

## Key Findings

### Cases Where SA Native Won
These are campuses where SA's cluster field correctly grouped buildings that UCID split apart.
This may indicate:
- Buildings > 250m apart that SA knows belong together
- Same-company neighboring sites that UCID correctly separated

### Cases Where UCID Won
These are campuses where our spatial clustering correctly grouped buildings that SA's data split.
This may indicate:
- SA's cluster field is more granular (building-level vs campus-level)
- Inconsistent cluster naming in SA's data

### Cases Where Both Split
These campuses had SA records split by both methods - may indicate:
- Multiple distinct sites near a Meta campus
- Data quality issues in either source

---

## Files Generated

| File | Purpose |
|------|---------|
| `sa_cluster_validation_{timestamp}.csv` | Full validation results |
| `SA_CLUSTER_VALIDATION_RESULTS.md` | This report |

---

## Next Steps

Based on these results:

1. **Review "SA Native Wins" cases** - Understand why SA's grouping was better
2. **Review "Both Split" cases** - May need manual curation
3. **Proceed to Phase 2** - Add company-aware matching to SA vs DCH comparison

---

*Report generated by `validate_clustering_methods.py`*
"""

    # Write report
    os.makedirs(os.path.dirname(report_path), exist_ok=True)
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(content)

    print(f"\n[REPORT] Markdown report written to:\n   {report_path}")

    return report_path


# ==============================================================================
# MAIN EXECUTION
# ==============================================================================

def main():
    print("=" * 80)
    print("SA CLUSTER vs UCID CLUSTERING VALIDATION (Phase 1)")
    print(f"Started: {datetime.now()}")
    print("=" * 80)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    # Step 1: Load data
    print("\n[Step 1] Loading data...")

    sa_records = load_sa_records()
    if not sa_records:
        print("ERROR: No SemiAnalysis records found in gold_buildings!")
        return

    meta_campuses = load_meta_canonical_campuses()
    if not meta_campuses:
        print("ERROR: No Meta Canonical campuses found!")
        return

    ucid_map = load_ucid_assignments()

    # Step 2: Build cluster IDs for both methods
    print("\n" + "-" * 80)
    sa_native_clusters = build_sa_native_cluster_ids(sa_records)
    ucid_clusters = build_ucid_cluster_ids(sa_records, ucid_map)

    # Step 3: Validate against Meta Canonical
    print("\n" + "-" * 80)
    validation_results = validate_against_meta_canonical(
        sa_records, sa_native_clusters, ucid_clusters, meta_campuses
    )

    # Step 4: Calculate summary metrics
    print("\n" + "-" * 80)
    print("[Summary] Calculating metrics...")
    summary = calculate_summary_metrics(validation_results)

    # Step 5: Display results
    print("\n" + "=" * 80)
    print("VALIDATION RESULTS SUMMARY")
    print("=" * 80)

    print(f"\n{'Metric':<40} {'Value':<20}")
    print("-" * 60)
    print(f"{'Total Meta Canonical Campuses':<40} {summary['total_meta_campuses']:<20}")
    print(f"{'Campuses with SA data (within 500m)':<40} {summary['with_sa_data']:<20}")
    print(f"{'Campuses without SA data':<40} {summary['no_sa_data']:<20}")

    print(f"\n{'Of campuses WITH SA data:':<40}")
    print("-" * 60)
    print(f"{'  TIE (both methods correct)':<40} {summary['tie']:<20}")
    print(f"{'  SA Native Wins':<40} {summary['sa_native_wins']:<20}")
    print(f"{'  UCID Wins':<40} {summary['ucid_wins']:<20}")
    print(f"{'  Both Split (both wrong)':<40} {summary['both_split']:<20}")

    print(f"\n{'MATCH RATES:':<40}")
    print("-" * 60)
    print(f"{'  SA Native Cluster Match Rate':<40} {summary['sa_match_rate']:.1f}%")
    print(f"{'  UCID Match Rate':<40} {summary['ucid_match_rate']:.1f}%")

    # Step 6: Export results
    print("\n" + "-" * 80)
    print("[Step 6] Exporting results...")

    csv_path = export_to_csv(validation_results, f'sa_cluster_validation_{timestamp}.csv')

    # Step 7: Generate Markdown report
    report_path = generate_markdown_report(summary, validation_results, timestamp)

    # Step 8: Show sample of interesting cases
    print("\n" + "=" * 80)
    print("SAMPLE CASES FOR REVIEW")
    print("=" * 80)

    # Show SA wins
    sa_wins = [r for r in validation_results if r['winner'] == 'SA_NATIVE']
    if sa_wins:
        print(f"\nSA Native Wins ({len(sa_wins)} cases) - First 5:")
        for r in sa_wins[:5]:
            print(f"   - {r['meta_campus']}: {r['notes']}")

    # Show UCID wins
    ucid_wins = [r for r in validation_results if r['winner'] == 'UCID']
    if ucid_wins:
        print(f"\nUCID Wins ({len(ucid_wins)} cases) - First 5:")
        for r in ucid_wins[:5]:
            print(f"   - {r['meta_campus']}: {r['notes']}")

    # Show both split
    both_split = [r for r in validation_results if r['winner'] == 'BOTH_SPLIT']
    if both_split:
        print(f"\nBoth Split ({len(both_split)} cases) - First 5:")
        for r in both_split[:5]:
            print(f"   - {r['meta_campus']}: {r['notes']}")

    # Final recommendation
    print("\n" + "=" * 80)
    print("RECOMMENDATION")
    print("=" * 80)

    if summary['ucid_match_rate'] > summary['sa_match_rate'] + 5:
        print("\n[OK] UCID METHODOLOGY IS SUPERIOR")
        print(f"   UCID: {summary['ucid_match_rate']:.1f}% match rate")
        print(f"   SA Native: {summary['sa_match_rate']:.1f}% match rate")
        print("   -> Continue with UCID for cross-source clustering")
    elif summary['sa_match_rate'] > summary['ucid_match_rate'] + 5:
        print("\n[WARN] SA NATIVE CLUSTER MAY BE BETTER")
        print(f"   SA Native: {summary['sa_match_rate']:.1f}% match rate")
        print(f"   UCID: {summary['ucid_match_rate']:.1f}% match rate")
        print("   -> Consider incorporating SA cluster field into UCID generation")
    else:
        print("\n[INFO] METHODS ARE COMPARABLE")
        print(f"   UCID: {summary['ucid_match_rate']:.1f}% match rate")
        print(f"   SA Native: {summary['sa_match_rate']:.1f}% match rate")
        print("   -> Continue with UCID for cross-source capability")
        print("   -> Use SA cluster as validation/confidence signal")

    print(f"\n[OUTPUT] Results exported to: {OUTPUT_DIR}")
    print(f"[OUTPUT] Report written to: {report_path}")
    print(f"\nCompleted: {datetime.now()}")
    print("=" * 80)

    return {
        'summary': summary,
        'validation_results': validation_results,
        'csv_path': csv_path,
        'report_path': report_path,
    }


# Execute
if __name__ == "__main__":
    main()
else:
    try:
        results = main()
    except Exception as e:
        print(f"\nERROR: {str(e)}")
        import traceback
        traceback.print_exc()
