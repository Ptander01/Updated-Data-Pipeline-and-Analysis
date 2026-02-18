import arcpy
import os
import sys
from datetime import datetime

# ============================================================================
# CAMPUS ROLLUP WORKFLOW - GROUPS BY UCID (Source-Agnostic)
# ============================================================================
#
# This script aggregates buildings into campuses using UCID as the grouping key.
# This creates ONE campus record per physical location, merging data from all sources.
#
# PREREQUISITE: Run generate_text_ucid.py BEFORE this script to populate the
# 'ucid' field in gold_buildings_full.
#
# Pipeline Order:
#   1. Ingest sources → gold_buildings_full
#   2. Company standardization → migrate_company_fields_v2.py
#   3. UCID generation → generate_text_ucid.py (assigns ucid to buildings)
#   4. Campus rollup → THIS SCRIPT (groups by ucid)
#
# ============================================================================

# Add _utils to path for config import
try:
    script_dir = os.path.dirname(os.path.abspath(__file__))
except NameError:
    # Running via exec() - use known path
    script_dir = r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\scripts\02_processing"

utils_dir = os.path.join(os.path.dirname(script_dir), "_utils")
if utils_dir not in sys.path:
    sys.path.insert(0, utils_dir)

from config import GDB, GOLD_BUILDINGS, GOLD_CAMPUS

arcpy.env.workspace = GDB
arcpy.env.overwriteOutput = True

# Use feature class paths from config module
gold_buildings = GOLD_BUILDINGS  # Uses gold_buildings_full for full data pipeline
gold_campus = GOLD_CAMPUS  # Uses gold_campus_full for full data pipeline

# Grouping field - use UCID for source-agnostic campus rollup
GROUPING_FIELD = 'ucid'

print("="*80)
print("CAMPUS ROLLUP WORKFLOW - GROUPS BY UCID (Source-Agnostic)")
print("="*80)

# Verify gold_buildings exists and has records
if not arcpy.Exists(gold_buildings):
    print(f"ERROR: gold_buildings does not exist")
    exit()

building_count = int(arcpy.management.GetCount(gold_buildings)[0])
print(f"\nStarting with {building_count} building records")

# Check if ucid field exists and is populated
building_fields = [f.name for f in arcpy.ListFields(gold_buildings)]
if GROUPING_FIELD not in building_fields:
    print(f"\nERROR: '{GROUPING_FIELD}' field not found in gold_buildings!")
    print("       Run generate_text_ucid.py first to assign UCIDs to buildings.")
    exit()

# Check if ucid is populated
ucid_count = 0
null_ucid_count = 0
with arcpy.da.SearchCursor(gold_buildings, [GROUPING_FIELD]) as cursor:
    for row in cursor:
        if row[0]:
            ucid_count += 1
        else:
            null_ucid_count += 1

if ucid_count == 0:
    print(f"\nERROR: No buildings have UCID values!")
    print("       Run generate_text_ucid.py first to assign UCIDs to buildings.")
    exit()

if null_ucid_count > 0:
    print(f"\n   WARNING: {null_ucid_count} buildings have NULL ucid values")
    print(f"            These will be excluded from campus rollup")

print(f"   {ucid_count} buildings have valid UCIDs")

# Step 0: Build source lookup dictionary (by UCID instead of campus_id)
print(f"\nStep 0: Building source lookup by {GROUPING_FIELD}...")
source_lookup = {}
company_source_lookup = {}
company_clean_lookup = {}
company_clean_filter_lookup = {}

with arcpy.da.SearchCursor(gold_buildings, [GROUPING_FIELD, 'source', 'company_source', 'company_clean', 'company_clean_filter']) as cursor:
    for row in cursor:
        ucid = row[0]
        source = row[1]
        company_source = row[2]
        company_clean = row[3]
        company_clean_filter = row[4]

        if not ucid:
            continue

        if ucid not in source_lookup:
            source_lookup[ucid] = set()
            company_source_lookup[ucid] = company_source  # First one wins
            company_clean_lookup[ucid] = company_clean    # First one wins
            company_clean_filter_lookup[ucid] = company_clean_filter  # First one wins

        if source:  # Only add non-null sources
            source_lookup[ucid].add(source)

# Convert sets to sorted semicolon-separated strings
for ucid in source_lookup:
    source_lookup[ucid] = "; ".join(sorted(source_lookup[ucid]))

print(f"   - Built source lookup for {len(source_lookup)} campuses (by UCID)")
print(f"   - Sample UCIDs: {list(source_lookup.keys())[:5]}")

# Step 1: Clear gold_campus
print("\nStep 1: Clearing gold_campus...")
arcpy.management.TruncateTable(gold_campus)
print("   - gold_campus truncated")

# Step 2: Pairwise Dissolve by UCID (source-agnostic)
print(f"\nStep 2: Dissolving buildings by {GROUPING_FIELD}...")

dissolved_fc = os.path.join(GDB, "temp_dissolved_campus")

if arcpy.Exists(dissolved_fc):
    arcpy.management.Delete(dissolved_fc)
    print("   - Deleted existing temp_dissolved_campus")

# Check if new fields exist in gold_buildings
building_fields = [f.name for f in arcpy.ListFields(gold_buildings)]
has_cost_fields = all(f in building_fields for f in ['total_cost_usd_million', 'land_cost_usd_million',
                                                       'total_site_acres', 'data_center_acres'])

# Check for year MW fields
has_year_fields = all(f in building_fields for f in [f'mw_{year}' for year in range(2023, 2033)])

# Check for data_vintage field
has_data_vintage = 'data_vintage' in building_fields

# Check for is_essential field
has_is_essential = 'is_essential' in building_fields

# Check for type_category field
has_type_category = 'type_category' in building_fields

# Define statistics fields
stats_fields = [
    ['company_clean', 'FIRST'],
    ['campus_name', 'FIRST'],
    ['city', 'FIRST'],
    ['market', 'FIRST'],
    ['state', 'FIRST'],
    ['state_abbr', 'FIRST'],
    ['county', 'FIRST'],
    ['country', 'FIRST'],
    ['region', 'FIRST'],
    ['postal_code', 'FIRST'],
    ['address', 'FIRST'],
    ['planned_power_mw', 'SUM'],
    ['uc_power_mw', 'SUM'],
    ['commissioned_power_mw', 'SUM'],
    ['full_capacity_mw', 'SUM'],
    ['facility_sqft', 'SUM'],
    ['whitespace_sqft', 'SUM'],
    ['actual_live_date', 'MIN'],
    ['construction_start_date', 'MIN'],
    ['status_rank_tmp', 'MIN'],
    ['cancelled', 'MAX'],
    ['pue', 'MEAN'],
    ['unique_id', 'COUNT']
]

# Add data_vintage if it exists (aggregate as MAX = most recent)
if has_data_vintage:
    stats_fields.append(['data_vintage', 'MAX'])
    print("   - Including data_vintage field in dissolve (MAX = most recent)")
else:
    print("   - data_vintage field not found - skipping in dissolve")

# Add is_essential if it exists (aggregate as MAX = if any building is essential, campus is essential)
if has_is_essential:
    ['is_essential', 'MAX'],
    print("   - Including is_essential field in dissolve (MAX = any essential building marks campus)")
else:
    print("   - is_essential field not found - skipping in dissolve")

# Add type_category if it exists (aggregate as FIRST - use first building's type)
if has_type_category:
    stats_fields.append(['type_category', 'FIRST'])
    print("   - Including type_category field in dissolve (FIRST = first building's type)")
else:
    print("   - type_category field not found - skipping in dissolve")

# Add cost/acreage fields if they exist
if has_cost_fields:
    stats_fields.extend([
        ['total_cost_usd_million', 'SUM'],
        ['land_cost_usd_million', 'SUM'],
        ['total_site_acres', 'SUM'],
        ['data_center_acres', 'SUM']
    ])
    print("   - Including cost/acreage fields in dissolve")
else:
    print("   - Cost/acreage fields not found - skipping in dissolve")

# Add year MW fields if they exist (CRITICAL FOR SEMIANALYSIS DATA)
if has_year_fields:
    for year in range(2023, 2033):
        stats_fields.append([f'mw_{year}', 'SUM'])
    print("   - Including mw_2023-2032 year fields in dissolve")
else:
    print("   - Year MW fields not found - skipping in dissolve")

try:
    # Use UCID as the dissolve field (source-agnostic grouping)
    arcpy.analysis.PairwiseDissolve(
        in_features=gold_buildings,
        out_feature_class=dissolved_fc,
        dissolve_field=[GROUPING_FIELD],  # Changed from campus_id to ucid
        statistics_fields=stats_fields,
        multi_part="MULTI_PART"
    )

    if not arcpy.Exists(dissolved_fc):
        print("   ERROR: Dissolve failed - output not created")
        exit()

    dissolved_count = int(arcpy.management.GetCount(dissolved_fc)[0])
    print(f"   - Dissolve complete - {dissolved_count} campus polygons created (grouped by {GROUPING_FIELD})")

except Exception as e:
    print(f"   ERROR during dissolve: {str(e)}")
    exit()

# Step 3: Feature To Point (INSIDE)
print("\nStep 3: Creating representative points...")

point_fc = os.path.join(GDB, "temp_campus_points")

if arcpy.Exists(point_fc):
    arcpy.management.Delete(point_fc)

try:
    arcpy.management.FeatureToPoint(
        in_features=dissolved_fc,
        out_feature_class=point_fc,
        point_location="INSIDE"
    )

    if not arcpy.Exists(point_fc):
        print("   ERROR: FeatureToPoint failed - output not created")
        exit()

    point_count = int(arcpy.management.GetCount(point_fc)[0])
    print(f"   - Points created - {point_count} campus points")

except Exception as e:
    print(f"   ERROR during FeatureToPoint: {str(e)}")
    exit()

# Step 4: Map fields and insert into gold_campus
print("\nStep 4: Mapping fields to gold_campus schema...")

dissolved_fields = [f.name for f in arcpy.ListFields(point_fc)]
print(f"   - Point feature class has {len(dissolved_fields)} fields")

# Check if gold_campus has cost/acreage fields
campus_fields = [f.name for f in arcpy.ListFields(gold_campus)]
campus_has_cost_fields = all(f in campus_fields for f in ['total_cost_usd_million', 'land_cost_usd_million',
                                                            'total_site_acres', 'data_center_acres'])

# Check if gold_campus has year MW fields
campus_has_year_fields = all(f in campus_fields for f in [f'mw_{year}' for year in range(2023, 2033)])

# Check if gold_campus has source field
campus_has_source = 'source' in campus_fields

# Check if gold_campus has company_source field
campus_has_company_source = 'company_source' in campus_fields

# Define insert fields
insert_fields = [
    'SHAPE@', 'campus_id', 'company_clean', 'campus_name', 'city', 'market',
    'state', 'state_abbr', 'county', 'country', 'region', 'postal_code',
    'address', 'planned_power_mw', 'uc_power_mw', 'commissioned_power_mw',
    'full_capacity_mw', 'planned_plus_uc_mw', 'facility_sqft_sum',
    'whitespace_sqft_sum', 'building_count', 'first_live_date',
    'facility_status_agg', 'cancelled', 'pue_avg', 'record_level',
    'ingest_date'
]

# Add source field if it exists in gold_campus
if campus_has_source:
    insert_fields.append('source')
    print("   - Including source field in insert")
else:
    print("   - WARNING: source field not in gold_campus - need to add it first")
    print("   - Run: arcpy.management.AddField(gold_campus, 'source', 'TEXT', field_length=200)")

# Add company_source field if it exists in gold_campus
if campus_has_company_source:
    insert_fields.append('company_source')
    print("   - Including company_source field in insert")

# Check if gold_campus has company_clean_filter field
campus_has_company_clean_filter = 'company_clean_filter' in campus_fields
if campus_has_company_clean_filter:
    insert_fields.append('company_clean_filter')
    print("   - Including company_clean_filter field in insert")
else:
    print("   - WARNING: company_clean_filter field not in gold_campus - need to add it first")

# Add cost/acreage fields to insert if they exist in gold_campus
if campus_has_cost_fields:
    insert_fields.extend(['total_cost_usd_million', 'land_cost_usd_million',
                          'total_site_acres', 'data_center_acres'])
    print("   - Including cost/acreage fields in insert")

# Add year MW fields to insert if they exist in gold_campus
if campus_has_year_fields:
    for year in range(2023, 2033):
        insert_fields.append(f'mw_{year}')
    print("   - Including mw_2023-2032 fields in insert")

# Check if gold_campus has data_vintage field
campus_has_data_vintage = 'data_vintage' in campus_fields
if has_data_vintage and campus_has_data_vintage:
    insert_fields.append('data_vintage')
    print("   - Including data_vintage field in insert (MAX = most recent)")

# Check if gold_campus has is_essential field
campus_has_is_essential = 'is_essential' in campus_fields
if has_is_essential and campus_has_is_essential:
    insert_fields.append('is_essential')
    print("   - Including is_essential field in insert (MAX = any essential building)")

# Check if gold_campus has construction_start_date field
has_construction_start = 'construction_start_date' in building_fields
campus_has_construction_start = 'construction_start_date' in campus_fields
if has_construction_start and campus_has_construction_start:
    insert_fields.append('construction_start_date')
    print("   - Including construction_start_date field in insert (MIN = earliest start)")
elif has_construction_start and not campus_has_construction_start:
    print("   - WARNING: construction_start_date not in gold_campus - add field first")
else:
    print("   - construction_start_date field not found in buildings - skipping")

# Check if gold_campus has type_category field
campus_has_type_category = 'type_category' in campus_fields
if has_type_category and campus_has_type_category:
    insert_fields.append('type_category')
    print("   - Including type_category field in insert (FIRST = first building's type)")
elif has_type_category and not campus_has_type_category:
    print("   - WARNING: type_category not in gold_campus - add field first")
else:
    print("   - type_category field not found in buildings - skipping")

# Status rank to status mapping
status_map = {
    1: 'Active',
    2: 'Under Construction',
    3: 'Permitting',
    4: 'Announced',
    5: 'Land Acquisition',
    6: 'Rumor',
    7: 'Unknown'
}

current_date = datetime.now()
campus_count = 0

# Helper function to safely get field value
def get_field_value(row, field_name, fields_list):
    """Safely get field value from row"""
    try:
        idx = fields_list.index(field_name)
        return row[idx + 1]  # +1 because SHAPE@ is position 0
    except (ValueError, IndexError):
        return None

try:
    with arcpy.da.SearchCursor(point_fc, ['SHAPE@'] + dissolved_fields) as s_cursor:
        with arcpy.da.InsertCursor(gold_campus, insert_fields) as i_cursor:

            for row in s_cursor:
                geom = row[0]

                # Get UCID from the dissolved record (this is now the grouping key)
                ucid = get_field_value(row, GROUPING_FIELD, dissolved_fields)

                # Extract dissolved stats
                company = get_field_value(row, 'FIRST_company_clean', dissolved_fields)
                campus_name = get_field_value(row, 'FIRST_campus_name', dissolved_fields)
                city = get_field_value(row, 'FIRST_city', dissolved_fields)
                market = get_field_value(row, 'FIRST_market', dissolved_fields)
                state = get_field_value(row, 'FIRST_state', dissolved_fields)
                state_abbr = get_field_value(row, 'FIRST_state_abbr', dissolved_fields)
                county = get_field_value(row, 'FIRST_county', dissolved_fields)
                country = get_field_value(row, 'FIRST_country', dissolved_fields)
                region = get_field_value(row, 'FIRST_region', dissolved_fields)
                postal = get_field_value(row, 'FIRST_postal_code', dissolved_fields)
                address = get_field_value(row, 'FIRST_address', dissolved_fields)

                # Capacity sums
                planned_mw = get_field_value(row, 'SUM_planned_power_mw', dissolved_fields)
                uc_mw = get_field_value(row, 'SUM_uc_power_mw', dissolved_fields)
                commissioned_mw = get_field_value(row, 'SUM_commissioned_power_mw', dissolved_fields)
                full_cap_mw = get_field_value(row, 'SUM_full_capacity_mw', dissolved_fields)

                # Area sums
                sqft_sum = get_field_value(row, 'SUM_facility_sqft', dissolved_fields)
                whitespace_sum = get_field_value(row, 'SUM_whitespace_sqft', dissolved_fields)

                # Aggregations
                building_count = get_field_value(row, 'COUNT_unique_id', dissolved_fields)
                first_live = get_field_value(row, 'MIN_actual_live_date', dissolved_fields)
                min_status_rank = get_field_value(row, 'MIN_status_rank_tmp', dissolved_fields)
                cancelled = get_field_value(row, 'MAX_cancelled', dissolved_fields)
                pue_avg = get_field_value(row, 'MEAN_pue', dissolved_fields)

                # Get source from lookup dictionary (now using UCID)
                source_str = source_lookup.get(ucid, None)

                # Cost and acreage sums (if available)
                if has_cost_fields and campus_has_cost_fields:
                    total_cost = get_field_value(row, 'SUM_total_cost_usd_million', dissolved_fields)
                    land_cost = get_field_value(row, 'SUM_land_cost_usd_million', dissolved_fields)
                    site_acres = get_field_value(row, 'SUM_total_site_acres', dissolved_fields)
                    dc_acres = get_field_value(row, 'SUM_data_center_acres', dissolved_fields)
                else:
                    total_cost = None
                    land_cost = None
                    site_acres = None
                    dc_acres = None

                # Year MW values (if available)
                year_mw_values = []
                if has_year_fields and campus_has_year_fields:
                    for year in range(2023, 2033):
                        year_mw = get_field_value(row, f'SUM_mw_{year}', dissolved_fields)
                        year_mw_values.append(year_mw)

                # Calculate derived fields
                planned_plus_uc = (planned_mw or 0) + (uc_mw or 0) if (planned_mw or uc_mw) else None
                facility_status = status_map.get(int(min_status_rank) if min_status_rank else 7, 'Unknown')

                # Build insert row - use UCID as the campus_id value
                insert_row = [
                    geom,                # SHAPE@
                    ucid,                # campus_id (now contains the UCID)
                    company,             # company_clean
                    campus_name,         # campus_name
                    city,                # city
                    market,              # market
                    state,               # state
                    state_abbr,          # state_abbr
                    county,              # county
                    country,             # country
                    region,              # region
                    postal,              # postal_code
                    address,             # address
                    planned_mw,          # planned_power_mw
                    uc_mw,               # uc_power_mw
                    commissioned_mw,     # commissioned_power_mw
                    full_cap_mw,         # full_capacity_mw
                    planned_plus_uc,     # planned_plus_uc_mw
                    sqft_sum,            # facility_sqft_sum
                    whitespace_sum,      # whitespace_sqft_sum
                    building_count,      # building_count
                    first_live,          # first_live_date
                    facility_status,     # facility_status_agg
                    cancelled,           # cancelled
                    pue_avg,             # pue_avg
                    'Campus',            # record_level
                    current_date         # ingest_date
                ]

                # Add source if field exists
                if campus_has_source:
                    insert_row.append(source_str)

                # Add company_source if field exists
                if campus_has_company_source:
                    company_source_str = company_source_lookup.get(ucid, None)
                    insert_row.append(company_source_str)

                # Add company_clean_filter if field exists
                if campus_has_company_clean_filter:
                    company_filter_str = company_clean_filter_lookup.get(ucid, None)
                    insert_row.append(company_filter_str)

                # Add cost/acreage if fields exist
                if campus_has_cost_fields:
                    insert_row.extend([total_cost, land_cost, site_acres, dc_acres])

                # Add year MW values if fields exist
                if campus_has_year_fields:
                    insert_row.extend(year_mw_values)

# Add data_vintage if field exists (MAX = most recent)
                if has_data_vintage and campus_has_data_vintage:
                    data_vintage_val = get_field_value(row, 'MAX_data_vintage', dissolved_fields)
                    insert_row.append(data_vintage_val)

                # Add is_essential if field exists (MAX = any essential building)
                if has_is_essential and campus_has_is_essential:
                    is_essential_val = get_field_value(row, 'MAX_is_essential', dissolved_fields)
                    insert_row.append(is_essential_val)

                # Add construction_start_date if field exists (MIN = earliest start)
                if has_construction_start and campus_has_construction_start:
                    construction_start_val = get_field_value(row, 'MIN_construction_start_date', dissolved_fields)
                    insert_row.append(construction_start_val)

                # Add type_category if field exists (FIRST = first building's type)
                if has_type_category and campus_has_type_category:
                    type_category_val = get_field_value(row, 'FIRST_type_category', dissolved_fields)
                    insert_row.append(type_category_val)

                i_cursor.insertRow(insert_row)
                campus_count += 1

    print(f"   - Inserted {campus_count} campus records")

except Exception as e:
    print(f"   ERROR during insert: {str(e)}")
    import traceback
    traceback.print_exc()
    exit()

# Step 5: Cleanup temp layers
print("\nStep 5: Cleaning up temporary layers...")
try:
    if arcpy.Exists(dissolved_fc):
        arcpy.management.Delete(dissolved_fc)
        print("   - Deleted temp_dissolved_campus")
    if arcpy.Exists(point_fc):
        arcpy.management.Delete(point_fc)
        print("   - Deleted temp_campus_points")
except Exception as e:
    print(f"   Warning during cleanup: {str(e)}")

print("\n" + "="*80)
print(f"CAMPUS ROLLUP COMPLETE")
print(f"   - gold_campus: {campus_count} records")
if campus_has_source:
    print(f"   - Source field populated with concatenated sources")
if campus_has_cost_fields:
    print(f"   - Cost/acreage fields aggregated via SUM")
if campus_has_year_fields:
    print(f"   - Year MW fields (2023-2032) aggregated via SUM")
print("="*80)
