"""
UCID Cluster Generation Script
Generates Universal Campus IDs using spatial clustering with TWO tolerance levels.

This script:
1. Reads all campus records from gold_campus_full
2. Clusters them by company + spatial proximity (TIGHT=250m, LOOSE=1000m)
3. Creates campus_master_tight and campus_master_loose feature classes
4. Outputs comparison statistics to help choose the right tolerance

Author: Meta Data Center GIS Team
Created: December 18, 2024
Updated: December 30, 2025 - Changed to use company_clean (distinct names) for clustering
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
    script_dir = r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\scripts\06_ucid"

utils_dir = os.path.join(os.path.dirname(script_dir), "_utils")
if utils_dir not in sys.path:
    sys.path.insert(0, utils_dir)

from config import (GDB, GOLD_CAMPUS, GOLD_BUILDINGS,
                    CAMPUS_MASTER_TIGHT, CAMPUS_MASTER_LOOSE,
                    UCID_TOLERANCE_TIGHT, UCID_TOLERANCE_LOOSE,
                    META_CANONICAL_CAMPUS)

arcpy.env.workspace = GDB
arcpy.env.overwriteOutput = True

# ==============================================================================
# CONFIGURATION
# ==============================================================================

# Company name normalization mapping
COMPANY_NORMALIZATION = {
    'amazon': 'AWS',
    'amazon aws': 'AWS',
    'amazon web services': 'AWS',
    'aws': 'AWS',
    'microsoft': 'Microsoft',
    'microsoft corporation': 'Microsoft',
    'microsoft azure': 'Microsoft',
    'azure': 'Microsoft',
    'google': 'Google',
    'google cloud': 'Google',
    'alphabet': 'Google',
    'meta': 'Meta',
    'facebook': 'Meta',
    'apple': 'Apple',
    'oracle': 'Oracle',
    'oracle corporation': 'Oracle',
    'alibaba': 'Alibaba',
    'alibaba cloud': 'Alibaba',
    'xai': 'xAI',
    'x.ai': 'xAI',
}

# Spatial reference for distance calculations (WGS84 Geographic)
WGS84 = arcpy.SpatialReference(4326)

# ==============================================================================
# HELPER FUNCTIONS
# ==============================================================================

def normalize_company(company_name):
    """Normalize company name for matching."""
    if not company_name:
        return 'Unknown'
    clean = str(company_name).lower().strip()
    return COMPANY_NORMALIZATION.get(clean, company_name)

def haversine_distance(lat1, lon1, lat2, lon2):
    """
    Calculate the great-circle distance between two points in meters.
    Uses the Haversine formula.
    """
    R = 6371000  # Earth's radius in meters

    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)

    a = math.sin(delta_lat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

    return R * c

def create_campus_master_fc(fc_path):
    """Create the campus_master feature class with full schema."""

    if arcpy.Exists(fc_path):
        arcpy.management.Delete(fc_path)
        print(f"   - Deleted existing {os.path.basename(fc_path)}")

    arcpy.management.CreateFeatureclass(
        out_path=os.path.dirname(fc_path),
        out_name=os.path.basename(fc_path),
        geometry_type="POINT",
        spatial_reference=WGS84
    )

    fields = [
        ('ucid', 'TEXT', 20),
        ('canonical_name', 'TEXT', 150),
        ('company_canonical', 'TEXT', 50),
        ('company_clean', 'TEXT', 100),
        ('city', 'TEXT', 100),
        ('state_abbr', 'TEXT', 10),
        ('state', 'TEXT', 50),
        ('country', 'TEXT', 50),
        ('region', 'TEXT', 10),
        ('latitude', 'DOUBLE', None),
        ('longitude', 'DOUBLE', None),
        ('source_count', 'SHORT', None),
        ('sources', 'TEXT', 500),
        ('campus_ids', 'TEXT', 2000),
        ('total_capacity_mw', 'DOUBLE', None),
        ('commissioned_mw', 'DOUBLE', None),
        ('building_count', 'LONG', None),
        ('meta_canonical_match', 'TEXT', 1),
        ('match_tolerance_m', 'SHORT', None),
        ('cluster_method', 'TEXT', 20),
        ('created_date', 'DATE', None),
        ('notes', 'TEXT', 500),
    ]

    for field_name, field_type, field_length in fields:
        if field_length:
            arcpy.management.AddField(fc_path, field_name, field_type, field_length=field_length)
        else:
            arcpy.management.AddField(fc_path, field_name, field_type)

    print(f"   - Created {os.path.basename(fc_path)} with {len(fields)} fields")
    return fc_path

def load_campus_records():
    """
    Load all campus records from gold_campus_full.

    IMPORTANT (Updated December 30, 2025):
    Uses company_clean for clustering, which now contains DISTINCT canonical names
    (Equinix, Digital Realty, QTS, etc.) after the company fields migration.

    DO NOT use company_clean_filter for clustering - that groups all colos as
    'Colo - All Other' which causes false merges!
    """
    records = []

    # Use company_clean for clustering (now has DISTINCT canonical names after migration)
    # company_clean_filter is for XB filtering only (hyperscalers OR "Colo - All Other")
    fields = ['SHAPE@XY', 'campus_id', 'company_source', 'company_clean', 'campus_name', 'city',
              'state_abbr', 'state', 'country', 'region', 'source',
              'full_capacity_mw', 'commissioned_power_mw', 'building_count']

    with arcpy.da.SearchCursor(GOLD_CAMPUS, fields) as cursor:
        for row in cursor:
            xy = row[0]
            if xy and xy[0] and xy[1]:
                # company_source = raw vendor value (may have variations)
                company_source = row[2]
                # company_clean = standardized DISTINCT name (Equinix, Digital Realty, etc.)
                # This is what we use for clustering!
                company_clean = row[3] or 'Unknown'

                records.append({
                    'lon': xy[0],
                    'lat': xy[1],
                    'campus_id': row[1],
                    'company_source': company_source,
                    'company_clean': company_clean,    # Use for clustering (distinct names)
                    'company_canonical': normalize_company(company_clean),  # Normalized for grouping
                    'campus_name': row[4],
                    'city': row[5],
                    'state_abbr': row[6],
                    'state': row[7],
                    'country': row[8],
                    'region': row[9] or 'OTHER',
                    'source': row[10],
                    'full_capacity_mw': row[11] or 0,
                    'commissioned_mw': row[12] or 0,
                    'building_count': row[13] or 0,
                })

    return records

def load_meta_canonical_campuses():
    """Load Meta Canonical campus locations for matching."""
    meta_campuses = []

    if not arcpy.Exists(META_CANONICAL_CAMPUS):
        print("   - WARNING: meta_canonical_campus not found - skipping Meta match check")
        return meta_campuses

    fields = ['SHAPE@XY', 'campus_name', 'dc_code']

    with arcpy.da.SearchCursor(META_CANONICAL_CAMPUS, fields) as cursor:
        for row in cursor:
            xy = row[0]
            if xy and xy[0] and xy[1]:
                meta_campuses.append({
                    'lon': xy[0],
                    'lat': xy[1],
                    'campus_name': row[1],
                    'dc_code': row[2],
                })

    return meta_campuses

def cluster_campuses(records, tolerance_m):
    """
    Cluster campus records by company + spatial proximity.

    Algorithm (Updated December 30, 2025):
    1. Group by company_clean (standardized DISTINCT company names)
       - company_clean now has: Equinix, Digital Realty, QTS, AWS, Meta, etc.
       - NOT company_clean_filter (which groups all colos as 'Colo - All Other')
    2. Within each company, cluster by spatial proximity
    3. Each cluster becomes one UCID

    Returns: List of clusters, where each cluster is a dict with:
        - records: list of source campus records in this cluster
        - centroid: (lat, lon) of cluster centroid
        - company: canonical company name (from company_clean)
        - region: region code (AMER/EMEA/APAC/OTHER)
    """

    # Step 1: Group by company_clean (standardized DISTINCT company names)
    # After migration, company_clean has distinct names like Equinix, Digital Realty, etc.
    # DO NOT use company_clean_filter - that has 'Colo - All Other' which causes false merges!
    by_company = defaultdict(list)
    for rec in records:
        # Use company_clean for grouping (distinct canonical names)
        by_company[rec['company_clean']].append(rec)

    clusters = []

    # Step 2: Cluster within each company
    for company, company_records in by_company.items():
        # Track which records have been assigned to a cluster
        assigned = set()

        for i, rec in enumerate(company_records):
            if i in assigned:
                continue

            # Start a new cluster with this record
            cluster_records = [rec]
            assigned.add(i)

            # Find all records within tolerance of any record in this cluster
            # (transitive clustering)
            changed = True
            while changed:
                changed = False
                for j, other in enumerate(company_records):
                    if j in assigned:
                        continue

                    # Check distance to any record in the cluster
                    for cluster_rec in cluster_records:
                        dist = haversine_distance(
                            cluster_rec['lat'], cluster_rec['lon'],
                            other['lat'], other['lon']
                        )
                        if dist <= tolerance_m:
                            cluster_records.append(other)
                            assigned.add(j)
                            changed = True
                            break

            # Calculate cluster centroid
            avg_lat = sum(r['lat'] for r in cluster_records) / len(cluster_records)
            avg_lon = sum(r['lon'] for r in cluster_records) / len(cluster_records)

            # Determine region (most common)
            region_counts = defaultdict(int)
            for r in cluster_records:
                region_counts[r['region']] += 1
            region = max(region_counts, key=region_counts.get)

            clusters.append({
                'records': cluster_records,
                'centroid': (avg_lat, avg_lon),
                'company': company,
                'region': region,
            })

    return clusters

def generate_ucid(region, sequence):
    """Generate UCID string."""
    return f"UCID-{region}-{sequence:05d}"

def check_meta_match(cluster_centroid, meta_campuses, tolerance_m=500):
    """Check if cluster matches a Meta Canonical campus."""
    lat, lon = cluster_centroid

    for meta in meta_campuses:
        dist = haversine_distance(lat, lon, meta['lat'], meta['lon'])
        if dist <= tolerance_m:
            return 'Y'

    return 'N'

def write_clusters_to_fc(clusters, fc_path, tolerance_m, method_name, meta_campuses):
    """Write cluster results to campus_master feature class."""

    # Sort clusters by region for sequential UCID generation
    region_sequences = defaultdict(int)

    insert_fields = [
        'SHAPE@XY', 'ucid', 'canonical_name', 'company_canonical', 'company_clean',
        'city', 'state_abbr', 'state', 'country', 'region',
        'latitude', 'longitude', 'source_count', 'sources', 'campus_ids',
        'total_capacity_mw', 'commissioned_mw', 'building_count',
        'meta_canonical_match', 'match_tolerance_m', 'cluster_method', 'created_date'
    ]

    insert_count = 0

    with arcpy.da.InsertCursor(fc_path, insert_fields) as cursor:
        for cluster in clusters:
            records = cluster['records']
            lat, lon = cluster['centroid']
            company = cluster['company']
            region = cluster['region']

            # Generate UCID
            region_sequences[region] += 1
            ucid = generate_ucid(region, region_sequences[region])

            # Aggregate values from source records
            sources = sorted(set(r['source'] for r in records if r['source']))
            campus_ids = sorted(set(r['campus_id'] for r in records if r['campus_id']))
            cities = [r['city'] for r in records if r['city']]

            # Use first non-null values for location fields
            city = cities[0] if cities else None
            state_abbr = next((r['state_abbr'] for r in records if r['state_abbr']), None)
            state = next((r['state'] for r in records if r['state']), None)
            country = next((r['country'] for r in records if r['country']), None)

            # Generate canonical name
            if city:
                canonical_name = f"{company} {city}"
            else:
                canonical_name = f"{company} ({lat:.2f}, {lon:.2f})"

            # Aggregate capacity and building counts
            total_capacity = sum(r['full_capacity_mw'] for r in records)
            commissioned = sum(r['commissioned_mw'] for r in records)
            building_count = sum(r['building_count'] for r in records)

            # Check Meta match
            meta_match = check_meta_match((lat, lon), meta_campuses)

            # Truncate long strings
            sources_str = "; ".join(sources)[:500]
            campus_ids_str = "; ".join(campus_ids)[:2000]

            cursor.insertRow([
                (lon, lat),
                ucid,
                canonical_name[:150],
                company[:50],
                records[0]['company_clean'][:100] if records[0]['company_clean'] else None,
                city[:100] if city else None,
                state_abbr[:10] if state_abbr else None,
                state[:50] if state else None,
                country[:50] if country else None,
                region[:10],
                lat,
                lon,
                len(sources),
                sources_str,
                campus_ids_str,
                total_capacity,
                commissioned,
                building_count,
                meta_match,
                tolerance_m,
                method_name,
                datetime.now()
            ])
            insert_count += 1

    return insert_count, region_sequences

def generate_statistics(clusters, tolerance_m, method_name, meta_campuses):
    """Generate statistics about clustering results."""
    stats = {
        'method': method_name,
        'tolerance_m': tolerance_m,
        'total_ucids': len(clusters),
        'single_source': 0,
        'multi_source': 0,
        'source_distribution': defaultdict(int),
        'region_counts': defaultdict(int),
        'meta_matches': 0,
        'avg_sources_per_ucid': 0,
        'max_sources': 0,
        'avg_capacity_mw': 0,
        'total_capacity_mw': 0,
    }

    total_sources = 0

    for cluster in clusters:
        records = cluster['records']
        sources = set(r['source'] for r in records if r['source'])
        region = cluster['region']

        num_sources = len(sources)
        total_sources += num_sources

        if num_sources == 1:
            stats['single_source'] += 1
        else:
            stats['multi_source'] += 1

        stats['source_distribution'][num_sources] += 1
        stats['region_counts'][region] += 1
        stats['max_sources'] = max(stats['max_sources'], num_sources)

        capacity = sum(r['full_capacity_mw'] for r in records)
        stats['total_capacity_mw'] += capacity

        # Check Meta match
        if check_meta_match(cluster['centroid'], meta_campuses) == 'Y':
            stats['meta_matches'] += 1

    if clusters:
        stats['avg_sources_per_ucid'] = total_sources / len(clusters)
        stats['avg_capacity_mw'] = stats['total_capacity_mw'] / len(clusters)

    return stats

def print_statistics(stats_tight, stats_loose):
    """Print comparison statistics."""

    print("\n" + "="*80)
    print("UCID CLUSTERING COMPARISON: TIGHT vs LOOSE")
    print("="*80)

    print(f"\n{'Metric':<40} {'TIGHT (250m)':<20} {'LOOSE (1000m)':<20}")
    print("-"*80)

    print(f"{'Total Unique UCIDs':<40} {stats_tight['total_ucids']:<20,} {stats_loose['total_ucids']:<20,}")
    print(f"{'Reduction from source campuses':<40} {'':<20} {'':<20}")
    print(f"{'Single-source UCIDs':<40} {stats_tight['single_source']:<20,} {stats_loose['single_source']:<20,}")
    print(f"{'Multi-source UCIDs':<40} {stats_tight['multi_source']:<20,} {stats_loose['multi_source']:<20,}")
    print(f"{'Avg sources per UCID':<40} {stats_tight['avg_sources_per_ucid']:<20.2f} {stats_loose['avg_sources_per_ucid']:<20.2f}")
    print(f"{'Max sources in one UCID':<40} {stats_tight['max_sources']:<20} {stats_loose['max_sources']:<20}")
    print(f"{'Meta Canonical matches':<40} {stats_tight['meta_matches']:<20} {stats_loose['meta_matches']:<20}")

    print(f"\n{'Region Distribution:':<40}")
    all_regions = set(stats_tight['region_counts'].keys()) | set(stats_loose['region_counts'].keys())
    for region in sorted(all_regions):
        t_count = stats_tight['region_counts'].get(region, 0)
        l_count = stats_loose['region_counts'].get(region, 0)
        print(f"  {region:<38} {t_count:<20,} {l_count:<20,}")

    print(f"\n{'Source Count Distribution:':<40}")
    max_src = max(stats_tight['max_sources'], stats_loose['max_sources'])
    for n in range(1, min(max_src + 1, 7)):
        t_count = stats_tight['source_distribution'].get(n, 0)
        l_count = stats_loose['source_distribution'].get(n, 0)
        label = f"  {n} source(s)"
        print(f"{label:<40} {t_count:<20,} {l_count:<20,}")

    if max_src >= 7:
        t_count = sum(v for k, v in stats_tight['source_distribution'].items() if k >= 7)
        l_count = sum(v for k, v in stats_loose['source_distribution'].items() if k >= 7)
        print(f"{'  7+ sources':<40} {t_count:<20,} {l_count:<20,}")

    # Analysis
    print("\n" + "="*80)
    print("ANALYSIS")
    print("="*80)

    delta_ucids = stats_tight['total_ucids'] - stats_loose['total_ucids']
    merge_rate = (delta_ucids / stats_tight['total_ucids'] * 100) if stats_tight['total_ucids'] > 0 else 0

    print(f"\nLoose clustering merges {delta_ucids:,} more campuses ({merge_rate:.1f}% reduction)")
    print(f"Multi-source rate: TIGHT={stats_tight['multi_source']/stats_tight['total_ucids']*100:.1f}% vs LOOSE={stats_loose['multi_source']/stats_loose['total_ucids']*100:.1f}%")

    if stats_loose['multi_source'] > stats_tight['multi_source']:
        extra_merges = stats_loose['multi_source'] - stats_tight['multi_source']
        print(f"\nLOOSE found {extra_merges:,} more cross-source matches")
        print("→ Suggests sprawling campuses may benefit from larger tolerance")

    if delta_ucids > 0:
        print(f"\nHowever, LOOSE merged {delta_ucids:,} campus pairs that TIGHT kept separate")
        print("→ These could be false merges of neighboring distinct campuses")

    print("\n" + "="*80)

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================

def main():
    print("="*80)
    print("UCID CLUSTER GENERATION - DUAL TOLERANCE COMPARISON")
    print(f"Started: {datetime.now()}")
    print("="*80)

    # Step 1: Load campus records
    print("\n[Step 1] Loading campus records from gold_campus_full...")
    records = load_campus_records()
    print(f"   - Loaded {len(records):,} campus records with valid coordinates")

    # Step 2: Load Meta Canonical for matching
    print("\n[Step 2] Loading Meta Canonical campuses for match checking...")
    meta_campuses = load_meta_canonical_campuses()
    print(f"   - Loaded {len(meta_campuses)} Meta Canonical campuses")

    # Step 3: Create campus_master feature classes
    print("\n[Step 3] Creating campus_master feature classes...")
    create_campus_master_fc(CAMPUS_MASTER_TIGHT)
    create_campus_master_fc(CAMPUS_MASTER_LOOSE)

    # Step 4: Generate TIGHT clusters (250m)
    print(f"\n[Step 4] Clustering with TIGHT tolerance ({UCID_TOLERANCE_TIGHT}m)...")
    clusters_tight = cluster_campuses(records, UCID_TOLERANCE_TIGHT)
    print(f"   - Generated {len(clusters_tight):,} clusters")

    count_tight, regions_tight = write_clusters_to_fc(
        clusters_tight, CAMPUS_MASTER_TIGHT,
        UCID_TOLERANCE_TIGHT, "TIGHT", meta_campuses
    )
    print(f"   - Wrote {count_tight:,} UCIDs to campus_master_tight")

    # Step 5: Generate LOOSE clusters (1000m)
    print(f"\n[Step 5] Clustering with LOOSE tolerance ({UCID_TOLERANCE_LOOSE}m)...")
    clusters_loose = cluster_campuses(records, UCID_TOLERANCE_LOOSE)
    print(f"   - Generated {len(clusters_loose):,} clusters")

    count_loose, regions_loose = write_clusters_to_fc(
        clusters_loose, CAMPUS_MASTER_LOOSE,
        UCID_TOLERANCE_LOOSE, "LOOSE", meta_campuses
    )
    print(f"   - Wrote {count_loose:,} UCIDs to campus_master_loose")

    # Step 6: Generate and display statistics
    print("\n[Step 6] Generating comparison statistics...")
    stats_tight = generate_statistics(clusters_tight, UCID_TOLERANCE_TIGHT, "TIGHT", meta_campuses)
    stats_loose = generate_statistics(clusters_loose, UCID_TOLERANCE_LOOSE, "LOOSE", meta_campuses)

    print_statistics(stats_tight, stats_loose)

    # Step 7: Summary
    print("\n" + "="*80)
    print("UCID GENERATION COMPLETE")
    print("="*80)
    print(f"\nOutput Feature Classes:")
    print(f"   - campus_master_tight: {count_tight:,} UCIDs (250m tolerance)")
    print(f"   - campus_master_loose: {count_loose:,} UCIDs (1000m tolerance)")
    print(f"\nNext Steps:")
    print("   1. Review the comparison statistics above")
    print("   2. Examine edge cases with validate_ucid_comparison.py")
    print("   3. Choose TIGHT or LOOSE and run assign_ucid_to_gold.py")
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
