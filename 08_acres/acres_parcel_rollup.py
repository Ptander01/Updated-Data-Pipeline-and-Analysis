"""
ACRES Parcel-to-Campus Centroid Rollup Script
==============================================

Collapses adjacent parcel groups into single-point campus centroids,
creating the same functional relationship as building-to-campus rollups.

Logic:
1. Group parcels by entity (owner/company)
2. Within each entity, cluster spatially adjacent parcels (using spatial joins or buffer/dissolve)
3. Calculate centroid for each parcel group
4. Sum total acreage per group
5. Track earliest acquisition date per group
6. Output: acres_campus_centroids feature class with crosswalk to individual parcels

USAGE (in ArcGIS Pro Python window):
    exec(open(r"C:/Users/ptanderson/Documents/ArcGIS/Projects/Lean Consensus DC Model/scripts/08_acres/acres_parcel_rollup.py", encoding='utf-8').read())

Author: Meta Data Center GIS Team
Created: 2026-01-29
"""

import arcpy
import os
import sys
from datetime import datetime
from collections import defaultdict
import math
import re

# Add _utils to path
try:
    script_dir = os.path.dirname(os.path.abspath(__file__))
except NameError:
    script_dir = r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\scripts\08_acres"

utils_dir = os.path.join(os.path.dirname(script_dir), "_utils")
if utils_dir not in sys.path:
    sys.path.insert(0, utils_dir)

from config import GDB

arcpy.env.workspace = GDB
arcpy.env.overwriteOutput = True

# ==============================================================================
# CONFIGURATION
# ==============================================================================

# Input feature class (from ingest_acres.py)
INPUT_PARCELS_POLYGON = os.path.join(GDB, "acres_parcels_polygon")
INPUT_PARCEL_CHANGES = os.path.join(GDB, "acres_parcel_changes_polygon")
INPUT_TRANSACTIONS = os.path.join(GDB, "acres_transactions_polygon")

# Output feature classes
OUTPUT_CAMPUS_CENTROIDS = os.path.join(GDB, "acres_campus_centroids")
OUTPUT_PARCEL_CROSSWALK = os.path.join(GDB, "acres_parcel_campus_xwalk")

# Clustering parameters
ADJACENCY_BUFFER_METERS = 50  # Buffer distance for determining adjacency
PROXIMITY_TOLERANCE_METERS = 1000  # Max distance to group parcels not physically touching

# Entity name standardization (ACRES entity → clean company name)
# Based on official ACRES Data Delivery Summary (June 2025)
ENTITY_MAPPING = {
    # Primary entities from ACRES documentation
    'AMAZON_DATA_CENTERS': 'AWS',
    'MICROSOFT_DATA_CENTERS': 'Microsoft',
    'GOOGLE_DATA_CENTERS': 'Google',
    'META_DATA_CENTERS': 'Meta',
    'DIGITAL_REALTY_DATA_CENTERS': 'Digital Realty',
    'EQUINIX_DATA_CENTERS': 'Equinix',
    'QTS_DATA_CENTERS': 'QTS',
    'DATABANK_DATA_CENTERS': 'DataBank',
    'ALIGNED_DATA_CENTERS': 'Aligned',
    'VANTAGE_DATA_CENTERS': 'Vantage',

    # Additional entities from "Others" category
    'CYRUSONE_DATA_CENTERS': 'CyrusOne',
    'CORESITE_DATA_CENTERS': 'CoreSite',
    'T5_DATA_CENTERS': 'T5',
    'SWITCH_DATA_CENTERS': 'Switch',
    'APPLE_DATA_CENTERS': 'Apple',
    'ORACLE_DATA_CENTERS': 'Oracle',
    'XAI_DATA_CENTERS': 'xAI',
    'COLOGIX_DATA_CENTERS': 'Cologix',
    'IRON_MOUNTAIN_DATA_CENTERS': 'Iron Mountain',
    'NTT_DATA_CENTERS': 'NTT',
    'POWERHOUSE_DATA_CENTERS': 'Powerhouse',
    'COMPASS_DATA_CENTERS': 'Compass',
    'DCBLOX_DATA_CENTERS': 'DCBlox',
    'APPLIED_DIGITAL_DATA_CENTERS': 'Applied Digital',
    'FLEXENTIAL_DATA_CENTERS': 'Flexential',
    'TIERPOINT_DATA_CENTERS': 'TierPoint',
    'H5_DATA_CENTERS': 'H5',
    '365_MAIN_DATA_CENTERS': '365 Main Inc',

    # Partial match fallbacks
    'META DATA CENTERS': 'Meta',
    'MICROSOFT_DATA_CENT': 'Microsoft',
    'DIGITAL_REALTY_DATA_C': 'Digital Realty',
    'AMAZON DATA CENTERS': 'AWS',
    'GOOGLE DATA CENTERS': 'Google',
}


def standardize_entity(entity_raw):
    """Convert ACRES entity name to standardized company name."""
    if not entity_raw:
        return 'Unknown'

    # Clean up the raw name
    entity_clean = entity_raw.strip().upper().replace(' ', '_')

    # Direct mapping
    for key, value in ENTITY_MAPPING.items():
        if key.upper() in entity_clean or entity_clean in key.upper():
            return value

    # Partial match
    for key, value in ENTITY_MAPPING.items():
        key_parts = key.upper().split('_')
        if any(part in entity_clean for part in key_parts if len(part) > 3):
            return value

    # Fallback: clean up the raw name
    return entity_raw.strip().replace('_', ' ').title()


def haversine_distance(lat1, lon1, lat2, lon2):
    """Calculate great-circle distance between two points in meters."""
    R = 6371000  # Earth's radius in meters

    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)

    a = math.sin(delta_lat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

    return R * c


def load_parcels():
    """Load parcel data from the geodatabase."""
    print("\n   Loading parcel data...")

    parcels = []

    # Determine which source to use
    if arcpy.Exists(INPUT_PARCELS_POLYGON):
        input_fc = INPUT_PARCELS_POLYGON
    elif arcpy.Exists(INPUT_PARCEL_CHANGES):
        input_fc = INPUT_PARCEL_CHANGES
        print("   Using parcel_changes as source (parcels_polygon not found)")
    else:
        print("   ERROR: No parcel data found. Run ingest_acres.py first.")
        return []

    # Get available fields
    available_fields = [f.name for f in arcpy.ListFields(input_fc)]
    print(f"   Available fields: {available_fields[:15]}...")

    # Map expected fields to available fields (case-insensitive matching)
    field_map = {}
    expected_fields = ['entity', 'apn', 'state', 'county', 'change_date', 'computed_acres', 'owner_change_type']

    for expected in expected_fields:
        for actual in available_fields:
            if actual.lower() == expected.lower() or expected.lower() in actual.lower():
                field_map[expected] = actual
                break

    print(f"   Field mapping: {field_map}")

    # Build cursor field list
    cursor_fields = ['SHAPE@', 'OBJECTID']
    for expected, actual in field_map.items():
        if actual not in cursor_fields:
            cursor_fields.append(actual)

    # Read features
    with arcpy.da.SearchCursor(input_fc, cursor_fields) as cursor:
        for row in cursor:
            shape = row[0]
            if not shape:
                continue

            # Get centroid coordinates
            centroid = shape.centroid
            if not centroid:
                continue

            record = {
                'shape': shape,
                'oid': row[1],
                'lon': centroid.X,
                'lat': centroid.Y,
            }

            # Map field values
            for i, field in enumerate(cursor_fields[2:], 2):
                # Find the expected field name
                for expected, actual in field_map.items():
                    if actual == field:
                        record[expected] = row[i]
                        break

            # Standardize entity
            record['company_clean'] = standardize_entity(record.get('entity'))

            parcels.append(record)

    print(f"   Loaded {len(parcels):,} parcels")
    return parcels


def cluster_parcels_by_adjacency(parcels, buffer_meters=ADJACENCY_BUFFER_METERS):
    """
    Cluster parcels using spatial adjacency (touching or within buffer distance).
    Uses a simplified Python-based approach for speed.

    Returns list of clusters, each containing list of parcel records.
    """
    print(f"\n   Clustering parcels by adjacency (buffer: {buffer_meters}m)...")

    # Group by company first
    by_company = defaultdict(list)
    for parcel in parcels:
        company = parcel.get('company_clean', 'Unknown')
        by_company[company].append(parcel)

    print(f"   Companies found: {len(by_company)}")

    all_clusters = []

    for company, company_parcels in by_company.items():
        # Track which parcels have been assigned to a cluster
        assigned = set()

        for i, parcel in enumerate(company_parcels):
            if i in assigned:
                continue

            # Start new cluster with this parcel
            cluster = [parcel]
            assigned.add(i)

            # Find all adjacent parcels (transitive closure)
            changed = True
            while changed:
                changed = False
                for j, other in enumerate(company_parcels):
                    if j in assigned:
                        continue

                    # Check if adjacent to any parcel in cluster
                    for cluster_parcel in cluster:
                        dist = haversine_distance(
                            cluster_parcel['lat'], cluster_parcel['lon'],
                            other['lat'], other['lon']
                        )

                        # Use centroid distance + buffer for adjacency check
                        # This is a simplification - ideally we'd check polygon intersection
                        if dist <= PROXIMITY_TOLERANCE_METERS:
                            cluster.append(other)
                            assigned.add(j)
                            changed = True
                            break

            all_clusters.append({
                'company': company,
                'parcels': cluster
            })

    print(f"   Created {len(all_clusters):,} parcel clusters")
    return all_clusters


def cluster_parcels_spatial(parcels, use_arcpy=True):
    """
    Cluster parcels using ArcPy spatial analysis tools.

    Method:
    1. Buffer all parcels by adjacency distance
    2. Dissolve by entity (company)
    3. Each dissolved polygon represents a campus
    4. Assign parcels back to their containing campus polygon
    """
    if not use_arcpy:
        return cluster_parcels_by_adjacency(parcels)

    print(f"\n   Clustering parcels using spatial dissolve...")

    # Determine input feature class
    if arcpy.Exists(INPUT_PARCELS_POLYGON):
        input_fc = INPUT_PARCELS_POLYGON
    elif arcpy.Exists(INPUT_PARCEL_CHANGES):
        input_fc = INPUT_PARCEL_CHANGES
    else:
        print("   No polygon input available, falling back to centroid clustering")
        return cluster_parcels_by_adjacency(parcels)

    # Create temporary feature classes
    temp_buffer = os.path.join(GDB, "temp_parcel_buffer")
    temp_dissolve = os.path.join(GDB, "temp_parcel_dissolve")

    try:
        # Add company_clean field if it doesn't exist
        fields = [f.name for f in arcpy.ListFields(input_fc)]
        if 'company_clean' not in fields:
            print("   Adding company_clean field...")
            arcpy.management.AddField(input_fc, 'company_clean', 'TEXT', field_length=100)

            # Populate company_clean
            entity_field = None
            for f in fields:
                if 'entity' in f.lower():
                    entity_field = f
                    break

            if entity_field:
                with arcpy.da.UpdateCursor(input_fc, [entity_field, 'company_clean']) as cursor:
                    for row in cursor:
                        row[1] = standardize_entity(row[0])
                        cursor.updateRow(row)

        # Step 1: Buffer parcels to create adjacency
        print(f"   Buffering parcels by {ADJACENCY_BUFFER_METERS}m...")
        arcpy.analysis.Buffer(
            input_fc,
            temp_buffer,
            f"{ADJACENCY_BUFFER_METERS} Meters",
            dissolve_option="NONE"
        )

        # Step 2: Dissolve by company to create campus groups
        print("   Dissolving by company...")

        # Get fields to aggregate (sum acres, min date)
        stat_fields = []
        for f in arcpy.ListFields(temp_buffer):
            if 'acres' in f.name.lower() or 'area' in f.name.lower():
                stat_fields.append([f.name, "SUM"])
            elif 'date' in f.name.lower() and 'year' not in f.name.lower():
                stat_fields.append([f.name, "MIN"])

        if stat_fields:
            arcpy.management.Dissolve(
                temp_buffer,
                temp_dissolve,
                "company_clean",
                stat_fields,
                multi_part="SINGLE_PART"
            )
        else:
            arcpy.management.Dissolve(
                temp_buffer,
                temp_dissolve,
                "company_clean",
                multi_part="SINGLE_PART"
            )

        # Step 3: Generate cluster assignments
        # Join parcels back to dissolved polygons to get campus assignment
        print("   Assigning parcels to campus clusters...")

        dissolved_count = int(arcpy.management.GetCount(temp_dissolve)[0])
        print(f"   Created {dissolved_count:,} campus polygons")

        # Build clusters from dissolved polygons
        clusters = []

        with arcpy.da.SearchCursor(temp_dissolve, ['SHAPE@', 'company_clean', 'OBJECTID']) as cursor:
            for row in cursor:
                campus_shape = row[0]
                company = row[1]
                campus_id = row[2]

                # Find all parcels within this campus polygon
                cluster_parcels = []
                for parcel in parcels:
                    if parcel.get('company_clean') != company:
                        continue

                    # Check if parcel centroid is within campus polygon (with buffer)
                    parcel_point = arcpy.Point(parcel['lon'], parcel['lat'])
                    if campus_shape.contains(parcel_point) or \
                       campus_shape.distanceTo(arcpy.PointGeometry(parcel_point)) <= ADJACENCY_BUFFER_METERS:
                        cluster_parcels.append(parcel)

                if cluster_parcels:
                    clusters.append({
                        'company': company,
                        'parcels': cluster_parcels,
                        'campus_shape': campus_shape
                    })

        return clusters

    except Exception as e:
        print(f"   ERROR in spatial clustering: {e}")
        print("   Falling back to centroid-based clustering...")
        return cluster_parcels_by_adjacency(parcels)

    finally:
        # Cleanup temp files
        for temp_fc in [temp_buffer, temp_dissolve]:
            if arcpy.Exists(temp_fc):
                try:
                    arcpy.management.Delete(temp_fc)
                except:
                    pass


def calculate_cluster_attributes(clusters):
    """
    Calculate aggregate attributes for each cluster:
    - Total acreage
    - Parcel count
    - Earliest acquisition date
    - Centroid coordinates
    - State/County (most common)
    """
    print("\n   Calculating cluster attributes...")

    for cluster in clusters:
        parcels = cluster['parcels']

        # Centroid (average of parcel centroids)
        cluster['lat'] = sum(p['lat'] for p in parcels) / len(parcels)
        cluster['lon'] = sum(p['lon'] for p in parcels) / len(parcels)

        # Total acreage
        acreage_values = [p.get('computed_acres') for p in parcels if p.get('computed_acres')]
        cluster['total_acres'] = sum(v for v in acreage_values if v) if acreage_values else 0

        # Parcel count
        cluster['parcel_count'] = len(parcels)

        # APNs (list)
        cluster['apn_list'] = [p.get('apn') for p in parcels if p.get('apn')]

        # Earliest acquisition date
        dates = []
        for p in parcels:
            date_val = p.get('change_date')
            if date_val:
                # Handle various date formats
                if isinstance(date_val, str):
                    try:
                        # Try YYYY-MM-DD
                        dt = datetime.strptime(date_val[:10], '%Y-%m-%d')
                        dates.append(dt)
                    except:
                        pass
                elif hasattr(date_val, 'strftime'):
                    dates.append(date_val)

        cluster['earliest_date'] = min(dates) if dates else None
        cluster['latest_date'] = max(dates) if dates else None

        # State/County (most common)
        state_counts = defaultdict(int)
        county_counts = defaultdict(int)
        for p in parcels:
            if p.get('state'):
                state_counts[p['state']] += 1
            if p.get('county'):
                county_counts[p['county']] += 1

        cluster['state'] = max(state_counts, key=state_counts.get) if state_counts else None
        cluster['county'] = max(county_counts, key=county_counts.get) if county_counts else None

    return clusters


def generate_campus_id(cluster, index):
    """Generate a unique campus identifier for the cluster."""
    company = cluster.get('company', 'Unknown')
    state = cluster.get('state', 'XX')
    county = cluster.get('county', 'Unknown')

    # Clean up for ID
    company_code = re.sub(r'[^A-Za-z0-9]', '', company)[:8].upper()
    state_code = (state or 'XX')[:2].upper()
    county_code = re.sub(r'[^A-Za-z0-9]', '', county or 'UNK')[:8].upper()

    return f"ACRES_{company_code}_{state_code}_{county_code}_{index:04d}"


def create_campus_centroid_fc(clusters):
    """Create the campus centroids feature class."""
    print(f"\n   Creating campus centroids feature class...")

    # Delete existing
    if arcpy.Exists(OUTPUT_CAMPUS_CENTROIDS):
        arcpy.management.Delete(OUTPUT_CAMPUS_CENTROIDS)

    # Create feature class
    spatial_ref = arcpy.SpatialReference(4326)  # WGS84
    arcpy.management.CreateFeatureclass(
        GDB,
        os.path.basename(OUTPUT_CAMPUS_CENTROIDS),
        "POINT",
        spatial_reference=spatial_ref
    )

    # Add fields
    fields_to_add = [
        ('campus_id', 'TEXT', 50),
        ('company_clean', 'TEXT', 100),
        ('state', 'TEXT', 10),
        ('county', 'TEXT', 100),
        ('total_acres', 'DOUBLE', None),
        ('parcel_count', 'LONG', None),
        ('earliest_acquisition_date', 'DATE', None),
        ('latest_acquisition_date', 'DATE', None),
        ('apn_list', 'TEXT', 4000),
        ('latitude', 'DOUBLE', None),
        ('longitude', 'DOUBLE', None),
    ]

    for field_name, field_type, field_length in fields_to_add:
        if field_length:
            arcpy.management.AddField(OUTPUT_CAMPUS_CENTROIDS, field_name, field_type, field_length=field_length)
        else:
            arcpy.management.AddField(OUTPUT_CAMPUS_CENTROIDS, field_name, field_type)

    # Insert records
    insert_fields = ['SHAPE@XY'] + [f[0] for f in fields_to_add]

    with arcpy.da.InsertCursor(OUTPUT_CAMPUS_CENTROIDS, insert_fields) as cursor:
        for i, cluster in enumerate(clusters, 1):
            campus_id = generate_campus_id(cluster, i)

            # Format APN list (truncate if too long)
            apn_str = '; '.join(cluster.get('apn_list', []))[:3999]

            row = [
                (cluster['lon'], cluster['lat']),  # SHAPE@XY
                campus_id,
                cluster.get('company'),
                cluster.get('state'),
                cluster.get('county'),
                cluster.get('total_acres', 0),
                cluster.get('parcel_count', 0),
                cluster.get('earliest_date'),
                cluster.get('latest_date'),
                apn_str,
                cluster['lat'],
                cluster['lon'],
            ]

            cursor.insertRow(row)

            # Store campus_id back in cluster for crosswalk
            cluster['campus_id'] = campus_id

    count = int(arcpy.management.GetCount(OUTPUT_CAMPUS_CENTROIDS)[0])
    print(f"   Created {count:,} campus centroid records")

    return count


def create_parcel_crosswalk(clusters):
    """Create the parcel-to-campus crosswalk table."""
    print(f"\n   Creating parcel-to-campus crosswalk table...")

    # Delete existing
    if arcpy.Exists(OUTPUT_PARCEL_CROSSWALK):
        arcpy.management.Delete(OUTPUT_PARCEL_CROSSWALK)

    # Create table
    arcpy.management.CreateTable(GDB, os.path.basename(OUTPUT_PARCEL_CROSSWALK))

    # Add fields
    fields_to_add = [
        ('campus_id', 'TEXT', 50),
        ('apn', 'TEXT', 100),
        ('company_clean', 'TEXT', 100),
        ('state', 'TEXT', 10),
        ('county', 'TEXT', 100),
        ('parcel_acres', 'DOUBLE', None),
        ('change_date', 'DATE', None),
        ('parcel_oid', 'LONG', None),
    ]

    for field_name, field_type, field_length in fields_to_add:
        if field_length:
            arcpy.management.AddField(OUTPUT_PARCEL_CROSSWALK, field_name, field_type, field_length=field_length)
        else:
            arcpy.management.AddField(OUTPUT_PARCEL_CROSSWALK, field_name, field_type)

    # Insert records
    insert_fields = [f[0] for f in fields_to_add]

    total_records = 0
    with arcpy.da.InsertCursor(OUTPUT_PARCEL_CROSSWALK, insert_fields) as cursor:
        for cluster in clusters:
            campus_id = cluster.get('campus_id')

            for parcel in cluster['parcels']:
                # Parse date if string
                date_val = parcel.get('change_date')
                if isinstance(date_val, str):
                    try:
                        date_val = datetime.strptime(date_val[:10], '%Y-%m-%d')
                    except:
                        date_val = None

                row = [
                    campus_id,
                    parcel.get('apn'),
                    parcel.get('company_clean'),
                    parcel.get('state'),
                    parcel.get('county'),
                    parcel.get('computed_acres'),
                    date_val,
                    parcel.get('oid'),
                ]

                cursor.insertRow(row)
                total_records += 1

    print(f"   Created {total_records:,} crosswalk records")

    return total_records


def print_summary(clusters):
    """Print summary statistics."""
    print("\n" + "=" * 70)
    print("   PARCEL ROLLUP SUMMARY")
    print("=" * 70)

    # Company breakdown
    by_company = defaultdict(list)
    for cluster in clusters:
        by_company[cluster.get('company', 'Unknown')].append(cluster)

    print(f"\n   Campus Groups by Company:")
    print(f"   {'Company':<25} {'Campuses':>10} {'Total Parcels':>15} {'Total Acres':>15}")
    print(f"   {'-'*25} {'-'*10} {'-'*15} {'-'*15}")

    for company in sorted(by_company.keys()):
        company_clusters = by_company[company]
        total_parcels = sum(c['parcel_count'] for c in company_clusters)
        total_acres = sum(c.get('total_acres', 0) for c in company_clusters)
        print(f"   {company:<25} {len(company_clusters):>10,} {total_parcels:>15,} {total_acres:>15,.1f}")

    # Overall totals
    print(f"   {'-'*25} {'-'*10} {'-'*15} {'-'*15}")
    total_campuses = len(clusters)
    total_parcels = sum(c['parcel_count'] for c in clusters)
    total_acres = sum(c.get('total_acres', 0) for c in clusters)
    print(f"   {'TOTAL':<25} {total_campuses:>10,} {total_parcels:>15,} {total_acres:>15,.1f}")

    # State breakdown
    print(f"\n   Top 10 States by Campus Count:")
    by_state = defaultdict(int)
    for cluster in clusters:
        state = cluster.get('state', 'Unknown')
        by_state[state] += 1

    for state, count in sorted(by_state.items(), key=lambda x: -x[1])[:10]:
        print(f"   {state}: {count:,} campuses")


def main(use_spatial_clustering=False):
    """
    Main function to run the parcel rollup.

    Args:
        use_spatial_clustering: If True, use ArcPy spatial dissolve (more accurate but slower).
                               If False, use centroid-based proximity clustering (faster).
    """
    print("=" * 70)
    print("   ACRES PARCEL-TO-CAMPUS CENTROID ROLLUP")
    print("=" * 70)
    print(f"   Started: {datetime.now()}")
    print(f"\n   Input: {INPUT_PARCELS_POLYGON}")
    print(f"   Output: {OUTPUT_CAMPUS_CENTROIDS}")
    print(f"   Clustering method: {'Spatial dissolve' if use_spatial_clustering else 'Centroid proximity'}")

    # Step 1: Load parcels
    print("\n" + "-" * 70)
    print("[Step 1] Loading parcel data...")
    print("-" * 70)
    parcels = load_parcels()

    if not parcels:
        print("\n   ERROR: No parcels loaded. Exiting.")
        return

    # Step 2: Cluster parcels
    print("\n" + "-" * 70)
    print("[Step 2] Clustering parcels into campus groups...")
    print("-" * 70)

    if use_spatial_clustering:
        clusters = cluster_parcels_spatial(parcels, use_arcpy=True)
    else:
        clusters = cluster_parcels_by_adjacency(parcels)

    # Step 3: Calculate cluster attributes
    print("\n" + "-" * 70)
    print("[Step 3] Calculating cluster attributes...")
    print("-" * 70)
    clusters = calculate_cluster_attributes(clusters)

    # Step 4: Create output feature class
    print("\n" + "-" * 70)
    print("[Step 4] Creating campus centroids feature class...")
    print("-" * 70)
    campus_count = create_campus_centroid_fc(clusters)

    # Step 5: Create crosswalk table
    print("\n" + "-" * 70)
    print("[Step 5] Creating parcel-to-campus crosswalk...")
    print("-" * 70)
    xwalk_count = create_parcel_crosswalk(clusters)

    # Summary
    print_summary(clusters)

    print("\n" + "=" * 70)
    print("   ROLLUP COMPLETE")
    print("=" * 70)
    print(f"\n   Output feature classes:")
    print(f"     - {os.path.basename(OUTPUT_CAMPUS_CENTROIDS)}: {campus_count:,} campus centroids")
    print(f"     - {os.path.basename(OUTPUT_PARCEL_CROSSWALK)}: {xwalk_count:,} parcel records")

    print(f"\n   Next steps:")
    print(f"     1. Run analyze_land_to_mw_lag.py to calculate land acquisition → MW timeline")
    print(f"     2. Run analyze_transaction_history.py for multi-transaction analysis")
    print(f"\n   Completed: {datetime.now()}")
    print("=" * 70)


# ==============================================================================
# EXECUTE
# ==============================================================================

if __name__ == "__main__":
    main(use_spatial_clustering=False)
else:
    main(use_spatial_clustering=False)
