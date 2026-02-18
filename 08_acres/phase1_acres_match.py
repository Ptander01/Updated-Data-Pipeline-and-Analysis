"""
Phase 1: ACRES Parcel Match - Peer Self-Build Planning Timeline Analysis
=========================================================================

Matches in-scope DC sites (from phase1_scope_filter.py) to ACRES land parcels
using spatial join (point-in-polygon) and company name validation.

PREREQUISITES:
1. Run ingest_acres.py to load ACRES data
2. Run phase1_scope_filter.py to create peer_selfbuild_2025_2027

MATCHING METHOD:
1. Spatial join: DC points → ACRES parcel polygons (point-in-polygon)
2. Buffer fallback: 500m radius for edge cases
3. Company name validation: Match ACRES entity to Consensus company_clean

OUTPUT:
- peer_selfbuild_acres_matched feature class with matched sites
- Match statistics (% matched, % unmatched)

USAGE (in ArcGIS Pro Python window):
    exec(open(r"C:/Users/ptanderson/Documents/ArcGIS/Projects/Lean Consensus DC Model/scripts/08_acres/phase1_acres_match.py", encoding='utf-8').read())

Author: Meta Data Center GIS Team
Created: 2026-02-02
Project: Peer Planning Timeline Analysis (1-Week Sprint)
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

# Input feature classes
INPUT_DC_SITES = os.path.join(GDB, "peer_selfbuild_2025_2027")

# ACRES sources (try in order of priority)
ACRES_SOURCES = [
    os.path.join(GDB, "acres_parcels_polygon"),
    os.path.join(GDB, "acres_parcel_changes_polygon"),
    os.path.join(GDB, "acres_transactions_polygon"),
]

# Output feature class
OUTPUT_MATCHED = os.path.join(GDB, "peer_selfbuild_acres_matched")

# Matching parameters
BUFFER_DISTANCE_METERS = 500  # Buffer radius for edge case matching
SPATIAL_TOLERANCE_METERS = 1000  # Max distance for spatial match

# Company name mapping (Consensus → ACRES entity patterns)
COMPANY_TO_ACRES_ENTITY = {
    'AWS': ['AMAZON', 'AWS', 'AMAZON_DATA_CENTERS'],
    'Google': ['GOOGLE', 'ALPHABET', 'GOOGLE_DATA_CENTERS'],
    'Microsoft': ['MICROSOFT', 'MSFT', 'MICROSOFT_DATA_CENTERS'],
    'Oracle': ['ORACLE', 'ORACLE_DATA_CENTERS'],
}


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


def find_acres_source():
    """Find available ACRES parcel source."""
    for source in ACRES_SOURCES:
        if arcpy.Exists(source):
            count = int(arcpy.management.GetCount(source)[0])
            if count > 0:
                print(f"   Found ACRES source: {os.path.basename(source)} ({count:,} records)")
                return source
    return None


def company_matches_entity(consensus_company, acres_entity):
    """Check if Consensus company matches ACRES entity."""
    if not consensus_company or not acres_entity:
        return False

    consensus_company = str(consensus_company).upper()
    acres_entity = str(acres_entity).upper()

    # Get expected entity patterns for this company
    expected_patterns = COMPANY_TO_ACRES_ENTITY.get(consensus_company, [consensus_company])

    for pattern in expected_patterns:
        if pattern.upper() in acres_entity or acres_entity in pattern.upper():
            return True

    return False


def load_dc_sites():
    """Load in-scope DC sites."""
    print("\n" + "=" * 70)
    print("[Step 1] Loading in-scope DC sites...")
    print("=" * 70)

    if not arcpy.Exists(INPUT_DC_SITES):
        print(f"   ERROR: {INPUT_DC_SITES} not found.")
        print("   Run phase1_scope_filter.py first.")
        return []

    sites = []
    fields = [f.name for f in arcpy.ListFields(INPUT_DC_SITES)]

    # Build cursor fields
    cursor_fields = ['SHAPE@', 'OBJECTID']
    optional_fields = [
        'unique_id', 'ucid', 'company_clean', 'company_normalized',
        'facility_name', 'facility_status', 'city', 'state_abbr', 'country',
        'full_capacity_mw', 'mw_2025', 'mw_2026', 'mw_2027', 'first_mw_year',
        'source', 'market', 'latitude', 'longitude'
    ]

    for field in optional_fields:
        if field in fields:
            cursor_fields.append(field)

    with arcpy.da.SearchCursor(INPUT_DC_SITES, cursor_fields) as cursor:
        for row in cursor:
            shape = row[0]
            if not shape:
                continue

            centroid = shape.centroid if hasattr(shape, 'centroid') else shape

            record = {
                'shape': shape,
                'oid': row[1],
                'lon': centroid.X if centroid else None,
                'lat': centroid.Y if centroid else None,
            }

            for i, field in enumerate(cursor_fields[2:], 2):
                record[field] = row[i]

            sites.append(record)

    print(f"   Loaded {len(sites):,} DC sites")

    # Summary by company
    by_company = defaultdict(int)
    for site in sites:
        company = site.get('company_normalized', site.get('company_clean', 'Unknown'))
        by_company[company] += 1

    print(f"   By company: {dict(by_company)}")

    return sites


def load_acres_parcels(acres_source):
    """Load ACRES parcel data."""
    print("\n" + "=" * 70)
    print("[Step 2] Loading ACRES parcel data...")
    print("=" * 70)

    parcels = []
    fields = [f.name for f in arcpy.ListFields(acres_source)]
    print(f"   Available fields: {fields[:15]}...")

    # Build cursor fields
    cursor_fields = ['SHAPE@', 'OBJECTID']

    # Map expected fields
    field_map = {
        'entity': ['entity', 'owner'],
        'apn': ['apn', 'parcel_number'],
        'state': ['state', 'state_abbr'],
        'county': ['county'],
        'acres': ['computed_acres', 'acres'],
        'change_date': ['change_date', 'transaction_date'],
        'transaction_amount': ['transaction_amount', 'sale_price'],
        'buyer_name': ['buyer_name'],
        'seller_name': ['seller_name'],
    }

    actual_field_map = {}
    for target, candidates in field_map.items():
        for candidate in candidates:
            for actual in fields:
                if actual.lower() == candidate.lower():
                    actual_field_map[target] = actual
                    if actual not in cursor_fields:
                        cursor_fields.append(actual)
                    break
            if target in actual_field_map:
                break

    print(f"   Field mapping: {actual_field_map}")

    with arcpy.da.SearchCursor(acres_source, cursor_fields) as cursor:
        for row in cursor:
            shape = row[0]
            if not shape:
                continue

            centroid = shape.centroid if hasattr(shape, 'centroid') else None

            record = {
                'shape': shape,
                'oid': row[1],
                'lon': centroid.X if centroid else None,
                'lat': centroid.Y if centroid else None,
            }

            for i, field in enumerate(cursor_fields[2:], 2):
                for target, actual in actual_field_map.items():
                    if actual == field:
                        record[target] = row[i]
                        break

            parcels.append(record)

    print(f"   Loaded {len(parcels):,} ACRES parcels")

    # Summary by entity
    by_entity = defaultdict(int)
    for parcel in parcels:
        entity = parcel.get('entity', 'Unknown')
        if entity:
            entity_short = str(entity)[:30]
            by_entity[entity_short] += 1

    print(f"   Top entities: {dict(sorted(by_entity.items(), key=lambda x: -x[1])[:10])}")

    return parcels, actual_field_map


def match_sites_to_parcels(sites, parcels):
    """
    Match DC sites to ACRES parcels using spatial join and company validation.

    Returns list of matched site records with ACRES data appended.
    """
    print("\n" + "=" * 70)
    print("[Step 3] Matching DC sites to ACRES parcels...")
    print("=" * 70)

    matched_sites = []
    unmatched_sites = []

    match_stats = {
        'total': len(sites),
        'point_in_polygon': 0,
        'buffer_match': 0,
        'company_validated': 0,
        'no_match': 0,
    }

    for site in sites:
        site_point = arcpy.Point(site['lon'], site['lat'])
        site_company = site.get('company_normalized', site.get('company_clean'))

        best_match = None
        best_distance = float('inf')
        match_type = None

        # Method 1: Point-in-polygon
        for parcel in parcels:
            parcel_shape = parcel.get('shape')
            if not parcel_shape:
                continue

            try:
                if parcel_shape.contains(site_point):
                    # Check company match
                    parcel_entity = parcel.get('entity')
                    if company_matches_entity(site_company, parcel_entity):
                        best_match = parcel
                        best_distance = 0
                        match_type = 'point_in_polygon_company_match'
                        break
                    elif best_match is None:
                        best_match = parcel
                        best_distance = 0
                        match_type = 'point_in_polygon'
            except:
                pass

        # Method 2: Centroid distance (if no point-in-polygon match)
        if best_match is None or match_type == 'point_in_polygon':
            for parcel in parcels:
                if not parcel.get('lat') or not parcel.get('lon'):
                    continue

                # Only consider parcels for same company
                parcel_entity = parcel.get('entity')
                if not company_matches_entity(site_company, parcel_entity):
                    continue

                dist = haversine_distance(
                    site['lat'], site['lon'],
                    parcel['lat'], parcel['lon']
                )

                if dist < best_distance and dist <= SPATIAL_TOLERANCE_METERS:
                    best_match = parcel
                    best_distance = dist
                    match_type = 'buffer_match_company'

        # Record match result
        if best_match:
            site_with_match = site.copy()
            site_with_match['match_type'] = match_type
            site_with_match['match_distance_m'] = best_distance

            # Copy ACRES fields
            site_with_match['acres_entity'] = best_match.get('entity')
            site_with_match['acres_apn'] = best_match.get('apn')
            site_with_match['acres_state'] = best_match.get('state')
            site_with_match['acres_county'] = best_match.get('county')
            site_with_match['acres_acres'] = best_match.get('acres')
            site_with_match['acres_change_date'] = best_match.get('change_date')
            site_with_match['acres_transaction_amount'] = best_match.get('transaction_amount')
            site_with_match['acres_buyer_name'] = best_match.get('buyer_name')
            site_with_match['acres_seller_name'] = best_match.get('seller_name')
            site_with_match['acres_parcel_lat'] = best_match.get('lat')
            site_with_match['acres_parcel_lon'] = best_match.get('lon')

            matched_sites.append(site_with_match)

            if 'point_in_polygon' in match_type:
                match_stats['point_in_polygon'] += 1
            else:
                match_stats['buffer_match'] += 1

            if 'company' in match_type:
                match_stats['company_validated'] += 1
        else:
            site_with_match = site.copy()
            site_with_match['match_type'] = 'no_match'
            site_with_match['match_distance_m'] = None
            unmatched_sites.append(site_with_match)
            match_stats['no_match'] += 1

    # Print match stats
    print(f"\n   MATCHING SUMMARY:")
    print(f"   {'Match Type':<35} {'Count':>10} {'%':>10}")
    print(f"   {'-'*35} {'-'*10} {'-'*10}")
    print(f"   {'Point-in-polygon match':<35} {match_stats['point_in_polygon']:>10,} {match_stats['point_in_polygon']/match_stats['total']*100:>9.1f}%")
    print(f"   {'Buffer/proximity match':<35} {match_stats['buffer_match']:>10,} {match_stats['buffer_match']/match_stats['total']*100:>9.1f}%")
    print(f"   {'Company validated':<35} {match_stats['company_validated']:>10,} {match_stats['company_validated']/match_stats['total']*100:>9.1f}%")
    print(f"   {'No match found':<35} {match_stats['no_match']:>10,} {match_stats['no_match']/match_stats['total']*100:>9.1f}%")
    print(f"   {'-'*35} {'-'*10} {'-'*10}")
    print(f"   {'TOTAL MATCHED':<35} {len(matched_sites):>10,} {len(matched_sites)/match_stats['total']*100:>9.1f}%")

    return matched_sites, unmatched_sites, match_stats


def create_output_feature_class(matched_sites, unmatched_sites):
    """Create output feature class with matched sites."""
    print("\n" + "=" * 70)
    print("[Step 4] Creating output feature class...")
    print("=" * 70)

    # Combine matched and unmatched
    all_sites = matched_sites + unmatched_sites

    # Delete existing
    if arcpy.Exists(OUTPUT_MATCHED):
        arcpy.management.Delete(OUTPUT_MATCHED)

    # Create feature class
    spatial_ref = arcpy.SpatialReference(4326)
    arcpy.management.CreateFeatureclass(
        GDB,
        os.path.basename(OUTPUT_MATCHED),
        "POINT",
        spatial_reference=spatial_ref
    )

    # Add fields
    fields_to_add = [
        # DC site fields
        ('unique_id', 'TEXT', 100),
        ('ucid', 'TEXT', 75),
        ('company_clean', 'TEXT', 100),
        ('company_normalized', 'TEXT', 50),
        ('facility_name', 'TEXT', 200),
        ('facility_status', 'TEXT', 50),
        ('city', 'TEXT', 100),
        ('state_abbr', 'TEXT', 10),
        ('full_capacity_mw', 'DOUBLE', None),
        ('mw_2025', 'DOUBLE', None),
        ('mw_2026', 'DOUBLE', None),
        ('mw_2027', 'DOUBLE', None),
        ('first_mw_year', 'SHORT', None),
        ('source', 'TEXT', 200),
        ('market', 'TEXT', 100),

        # Match fields
        ('match_type', 'TEXT', 50),
        ('match_distance_m', 'DOUBLE', None),

        # ACRES fields
        ('acres_entity', 'TEXT', 200),
        ('acres_apn', 'TEXT', 100),
        ('acres_state', 'TEXT', 10),
        ('acres_county', 'TEXT', 100),
        ('acres_acres', 'DOUBLE', None),
        ('acres_change_date', 'DATE', None),
        ('acres_transaction_amount', 'DOUBLE', None),
        ('acres_buyer_name', 'TEXT', 200),
        ('acres_seller_name', 'TEXT', 200),
    ]

    for field_name, field_type, field_length in fields_to_add:
        if field_length:
            arcpy.management.AddField(OUTPUT_MATCHED, field_name, field_type, field_length=field_length)
        else:
            arcpy.management.AddField(OUTPUT_MATCHED, field_name, field_type)

    # Insert records
    insert_fields = ['SHAPE@XY'] + [f[0] for f in fields_to_add]

    inserted = 0
    with arcpy.da.InsertCursor(OUTPUT_MATCHED, insert_fields) as cursor:
        for site in all_sites:
            if not site.get('lon') or not site.get('lat'):
                continue

            row = [
                (site['lon'], site['lat']),
                site.get('unique_id'),
                site.get('ucid'),
                site.get('company_clean'),
                site.get('company_normalized'),
                site.get('facility_name'),
                site.get('facility_status'),
                site.get('city'),
                site.get('state_abbr'),
                site.get('full_capacity_mw'),
                site.get('mw_2025'),
                site.get('mw_2026'),
                site.get('mw_2027'),
                site.get('first_mw_year'),
                site.get('source'),
                site.get('market'),
                site.get('match_type'),
                site.get('match_distance_m'),
                site.get('acres_entity'),
                site.get('acres_apn'),
                site.get('acres_state'),
                site.get('acres_county'),
                site.get('acres_acres'),
                site.get('acres_change_date'),
                site.get('acres_transaction_amount'),
                site.get('acres_buyer_name'),
                site.get('acres_seller_name'),
            ]

            cursor.insertRow(row)
            inserted += 1

    print(f"   Created: {os.path.basename(OUTPUT_MATCHED)}")
    print(f"   Records: {inserted:,}")

    return inserted


def print_match_summary(matched_sites, unmatched_sites):
    """Print detailed match summary."""
    print("\n" + "=" * 70)
    print("ACRES MATCH SUMMARY")
    print("=" * 70)

    total = len(matched_sites) + len(unmatched_sites)

    # By company
    print(f"\n   MATCH RATE BY COMPANY:")
    print(f"   {'Company':<15} {'Total':>8} {'Matched':>10} {'Match %':>10}")
    print(f"   {'-'*15} {'-'*8} {'-'*10} {'-'*10}")

    all_sites = matched_sites + unmatched_sites
    by_company = defaultdict(lambda: {'total': 0, 'matched': 0})

    for site in all_sites:
        company = site.get('company_normalized', site.get('company_clean', 'Unknown'))
        by_company[company]['total'] += 1
        if site.get('match_type') and site['match_type'] != 'no_match':
            by_company[company]['matched'] += 1

    for company in sorted(by_company.keys()):
        stats = by_company[company]
        pct = stats['matched'] / stats['total'] * 100 if stats['total'] > 0 else 0
        print(f"   {company:<15} {stats['total']:>8,} {stats['matched']:>10,} {pct:>9.1f}%")

    # Sites with transaction data
    print(f"\n   SITES WITH TRANSACTION DATA:")
    has_transaction = sum(1 for s in matched_sites if s.get('acres_transaction_amount'))
    has_date = sum(1 for s in matched_sites if s.get('acres_change_date'))

    print(f"   - Sites with transaction amount: {has_transaction:,} of {len(matched_sites):,} matched ({has_transaction/len(matched_sites)*100:.1f}%)" if matched_sites else "   - No matched sites")
    print(f"   - Sites with transaction date: {has_date:,} of {len(matched_sites):,} matched ({has_date/len(matched_sites)*100:.1f}%)" if matched_sites else "")

    # Top unmatched
    if unmatched_sites:
        print(f"\n   TOP UNMATCHED SITES (by MW):")
        sorted_unmatched = sorted(unmatched_sites, key=lambda x: -(x.get('mw_2027') or 0))[:10]
        for site in sorted_unmatched:
            mw = site.get('mw_2027') or 0
            print(f"   - {site.get('company_normalized', 'Unknown')}: {site.get('city', 'Unknown')}, {site.get('state_abbr', 'XX')} ({mw:.0f} MW)")


def main():
    """Main function for ACRES parcel matching."""
    print("=" * 70)
    print("PHASE 1: ACRES PARCEL MATCH")
    print("Peer Self-Build Planning Timeline Analysis")
    print("=" * 70)
    print(f"Started: {datetime.now()}")

    # Step 1: Load DC sites
    sites = load_dc_sites()

    if not sites:
        print("\n   ERROR: No DC sites found. Run phase1_scope_filter.py first.")
        return

    # Step 2: Find and load ACRES parcels
    acres_source = find_acres_source()

    if not acres_source:
        print("\n   ERROR: No ACRES data found.")
        print("   Run ingest_acres.py first to load ACRES parcel data.")
        print("\n   Alternative: The script will continue without ACRES matching")
        print("   to allow analysis of scope even without parcel data.")

        # Create output with unmatched sites
        for site in sites:
            site['match_type'] = 'acres_data_missing'

        create_output_feature_class([], sites)
        return

    parcels, field_map = load_acres_parcels(acres_source)

    if not parcels:
        print("\n   WARNING: No ACRES parcels loaded. Continuing without matching.")
        for site in sites:
            site['match_type'] = 'acres_data_empty'
        create_output_feature_class([], sites)
        return

    # Step 3: Match sites to parcels
    matched_sites, unmatched_sites, match_stats = match_sites_to_parcels(sites, parcels)

    # Step 4: Create output
    count = create_output_feature_class(matched_sites, unmatched_sites)

    # Step 5: Print summary
    print_match_summary(matched_sites, unmatched_sites)

    # Final output
    print("\n" + "=" * 70)
    print("PHASE 1 ACRES MATCH COMPLETE")
    print("=" * 70)
    print(f"\n   Output: {os.path.basename(OUTPUT_MATCHED)} ({count:,} records)")
    print(f"   Matched: {len(matched_sites):,} ({len(matched_sites)/len(sites)*100:.1f}%)")
    print(f"   Unmatched: {len(unmatched_sites):,} ({len(unmatched_sites)/len(sites)*100:.1f}%)")
    print(f"\n   Next Steps:")
    print(f"   1. Run phase1_ownership_analysis.py for ownership breakdown")
    print(f"   2. Run phase1_timeline_calc.py for land-to-MW timeline")
    print(f"\n   Completed: {datetime.now()}")
    print("=" * 70)

    return matched_sites, unmatched_sites


# ==============================================================================
# EXECUTE
# ==============================================================================

if __name__ == "__main__":
    main()
else:
    main()
