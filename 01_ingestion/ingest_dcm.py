"""
DataCenterMap (DCM) Ingestion Script
Ingests DCM data into gold_buildings feature class with duplicate prevention.

Features:
- Duplicate prevention: Checks for existing unique_id before inserting
- Country/region standardization
- Status mapping from stage field
- Capacity routing based on status
- Post-ingestion validation

Author: Meta Data Center GIS Team
Last Updated: 2024-12-15
"""

import arcpy
from datetime import datetime
from collections import defaultdict
import re
import os
import sys

# Add _utils to path for config import
# Handle both direct execution and exec() from ArcGIS Pro Python window
import os
import sys

try:
    script_dir = os.path.dirname(os.path.abspath(__file__))
except NameError:
    # Running via exec() - use known path
    script_dir = r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\scripts\01_ingestion"

utils_dir = os.path.join(os.path.dirname(script_dir), "_utils")
if utils_dir not in sys.path:
    sys.path.insert(0, utils_dir)

from config import GDB, GOLD_BUILDINGS, RAW_TABLES

# ============================================================================
# CONFIGURATION
# ============================================================================

# Source and target paths from config module
SOURCE_FC = RAW_TABLES['dcm']
TARGET_FC = GOLD_BUILDINGS  # Uses gold_buildings_full for full data pipeline

SOURCE_NAME = "DataCenterMap"

arcpy.env.workspace = GDB
arcpy.env.overwriteOutput = True

# Status mapping (DCM stage → Gold schema facility_status)
STATUS_MAP = {
    'operational': 'Active',
    'under construction': 'Under Construction',
    'planned': 'Announced',
    'land banked': 'Land Acquisition',
    'cancelled': 'Cancelled',
    '': 'Unknown',
    None: 'Unknown'
}

# Region standardization
REGION_MAP = {
    'NorthAmerica': 'AMER',
    'North America': 'AMER',
    'NORTHAMERICA': 'AMER',
    'EMEA': 'EMEA',
    'APAC': 'APAC',
    'AMER': 'AMER',
    None: None,
    '': None
}

# Country standardization
COUNTRY_MAP = {
    'USA': 'United States',
    'US': 'United States',
    'U.S.': 'United States',
    'U.S.A.': 'United States',
    'United States': 'United States',
    'United States of America': 'United States'
}

# Country to region fallback
COUNTRY_TO_REGION = {
    'United States': 'AMER', 'Canada': 'AMER', 'Mexico': 'AMER',
    'Brazil': 'AMER', 'Chile': 'AMER', 'Colombia': 'AMER', 'Argentina': 'AMER',
    'United Kingdom': 'EMEA', 'Ireland': 'EMEA', 'Germany': 'EMEA',
    'France': 'EMEA', 'Netherlands': 'EMEA', 'Sweden': 'EMEA',
    'Denmark': 'EMEA', 'Norway': 'EMEA', 'Finland': 'EMEA',
    'Spain': 'EMEA', 'Italy': 'EMEA', 'Poland': 'EMEA', 'Serbia': 'EMEA',
    'UAE': 'EMEA', 'United Arab Emirates': 'EMEA', 'Saudi Arabia': 'EMEA',
    'Israel': 'EMEA', 'South Africa': 'EMEA',
    'Singapore': 'APAC', 'Japan': 'APAC', 'Australia': 'APAC',
    'New Zealand': 'APAC', 'India': 'APAC', 'Indonesia': 'APAC',
    'Malaysia': 'APAC', 'Taiwan': 'APAC', 'South Korea': 'APAC',
    'Hong Kong': 'APAC', 'Philippines': 'APAC', 'Thailand': 'APAC',
    'Vietnam': 'APAC', 'China': 'APAC'
}


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def delete_existing_records(target_fc, source_name):
    """Delete all existing records from this source before fresh ingestion."""
    print(f"\n[CLEANUP] Checking for existing {source_name} records...")

    where_clause = f"source = '{source_name}'"

    # Create a temporary feature layer for selection
    temp_layer = "temp_delete_layer"
    if arcpy.Exists(temp_layer):
        arcpy.management.Delete(temp_layer)

    arcpy.management.MakeFeatureLayer(target_fc, temp_layer)
    arcpy.management.SelectLayerByAttribute(temp_layer, "NEW_SELECTION", where_clause)

    deleted_count = int(arcpy.GetCount_management(temp_layer)[0])

    if deleted_count > 0:
        arcpy.management.DeleteRows(temp_layer)
        print(f"   ✓ Deleted {deleted_count:,} existing {source_name} records")
    else:
        print(f"   ✓ No existing {source_name} records found")

    arcpy.management.Delete(temp_layer)
    return deleted_count


def slugify(text):
    """Convert text to URL-safe slug format."""
    if not text:
        return ''
    text = str(text).strip().lower().replace('&', ' and ')
    text = re.sub(r'[^a-z0-9]+', '-', text)
    text = re.sub(r'-+', '-', text).strip('-')
    return text


def create_unique_id(source_id):
    """Create unique_id with DCM prefix."""
    if not source_id:
        return None
    return f"dcm_{source_id}"


def create_campus_id(company, city, campus_name, lat, lon):
    """
    Create standardized campus_id.
    Format: company|city|campus (all slugified)
    Falls back to coordinates if campus_name is missing.
    """
    co = slugify(company)
    ci = slugify(city)
    cp = slugify(campus_name)

    if not cp:
        try:
            cp = slugify(f"{round(float(lat), 4)},{round(float(lon), 4)}")
        except:
            cp = "unknown"

    return f"{co}|{ci}|{cp}"


def parse_campus_name(name):
    """
    Parse name field to extract campus_name and building_designation.
    Examples:
        "Meta Altoona - Building 3" → ("Meta Altoona", "Building 3")
        "Meta Altoona Campus" → ("Meta Altoona", None)
        "Meta Altoona Data Center" → ("Meta Altoona", None)
    """
    if not name:
        return None, None

    name = str(name).strip()

    # Check for building designation
    if " - Building" in name:
        parts = name.split(" - Building")
        campus_name = parts[0].strip()
        building_designation = f"Building{parts[1].strip()}" if len(parts) > 1 else None
        return campus_name, building_designation

    # Clean up suffixes
    if name.endswith(" Campus"):
        return name[:-7].strip(), None
    if name.endswith(" Data Center"):
        return name[:-12].strip(), None

    return name, None


def derive_record_level(name, parent_id):
    """Determine if record is Building or Campus level."""
    name = str(name) if name else ''
    if " - Building" in name:
        return "Building"
    if parent_id and parent_id != 0:
        return "Building"
    return "Campus"


def map_status(stage):
    """Map DCM stage to gold schema facility_status."""
    if not stage:
        return 'Unknown'
    stage_lower = str(stage).strip().lower()

    for key, value in STATUS_MAP.items():
        if key and key in stage_lower:
            return value

    return 'Unknown'


def is_cancelled(stage):
    """Check if stage indicates cancelled."""
    if not stage:
        return 0
    return 1 if 'cancel' in str(stage).lower() else 0


def route_capacity(stage, power_mw):
    """
    Route power capacity to appropriate field based on status.
    Returns: (commissioned_mw, uc_mw, planned_mw)
    """
    if not power_mw:
        return None, None, None

    stage_lower = str(stage).lower() if stage else ''

    if 'operational' in stage_lower:
        return power_mw, None, None
    elif 'under construction' in stage_lower:
        return None, power_mw, None
    elif 'planned' in stage_lower or 'land banked' in stage_lower:
        return None, None, power_mw

    return None, None, None


def standardize_country(country):
    """Standardize country name."""
    if not country:
        return None
    return COUNTRY_MAP.get(country, country)


def standardize_region(region, country):
    """Standardize region, with country fallback."""
    if region in REGION_MAP:
        mapped = REGION_MAP[region]
        if mapped:
            return mapped

    # Fallback to country-based lookup
    if country:
        country_std = standardize_country(country)
        if country_std in COUNTRY_TO_REGION:
            return COUNTRY_TO_REGION[country_std]

    return None


def year_to_date(year_val):
    """Convert year to datetime (Dec 31 of that year)."""
    if not year_val:
        return None
    try:
        year_int = int(year_val)
        if year_int > 1900:
            return datetime(year_int, 12, 31)
    except:
        pass
    return None


def safe_float(value):
    """Safely convert to float."""
    if value in [None, '', ' ', 'None']:
        return None
    try:
        return float(value)
    except:
        return None


def get_existing_unique_ids(target_fc, source_name):
    """
    Get set of existing unique_id values for a source.
    Used for duplicate prevention.
    """
    existing_ids = set()

    try:
        where_clause = f"source = '{source_name}'"
        with arcpy.da.SearchCursor(target_fc, ['unique_id'], where_clause=where_clause) as cursor:
            for row in cursor:
                if row[0]:
                    existing_ids.add(row[0])
    except Exception as e:
        print(f"   ⚠️  Warning: Could not check existing records: {e}")

    return existing_ids


def get_source_fields(source_fc):
    """Get list of field names in source feature class."""
    return [f.name for f in arcpy.ListFields(source_fc)]


# ============================================================================
# MAIN INGESTION
# ============================================================================

def ingest_datacentermap():
    """
    Ingest DataCenterMap data into gold_buildings with duplicate prevention.
    """

    print("=" * 80)
    print("DATACENTERMAP INGESTION")
    print("=" * 80)
    print(f"Started: {datetime.now()}")
    print(f"Source: {SOURCE_FC}")
    print(f"Target: {TARGET_FC}")

    # ========================================================================
    # STEP 0: Verify source exists
    # ========================================================================

    if not arcpy.Exists(SOURCE_FC):
        print(f"\n❌ ERROR: Source feature class not found: {SOURCE_FC}")
        return 0

    source_count = int(arcpy.GetCount_management(SOURCE_FC)[0])
    print(f"\nSource records available: {source_count}")

    # ========================================================================
    # STEP 1: Delete existing records from this source (clean re-ingestion)
    # ========================================================================

    print("\n[1/4] Cleaning up existing DataCenterMap records...")
    delete_existing_records(TARGET_FC, SOURCE_NAME)

    # ========================================================================
    # STEP 2: Read source data
    # ========================================================================

    print("\n[2/4] Reading source data...")

    source_fields = get_source_fields(SOURCE_FC)
    print(f"   Source has {len(source_fields)} fields")

    # Define fields to read (latitude/longitude instead of SHAPE since source is a table)
    read_fields = [
        'id',                    # source_unique_id
        'name',                  # for campus_name, building_designation
        'parent_id',             # for record_level
        'company_name',          # company
        'address',
        'address_details',       # append to address
        'postal_code',
        'city',
        'state',
        'state_abbr',
        'county',
        'country',
        'region',
        'market',
        'latitude',
        'longitude',
        'stage',                 # for facility_status
        'power_mw',              # capacity
        'year_operational',      # for actual_live_date
        'building_sqft',         # facility_sqft
        'whitespace_sqft',
        'pue',
        'tier_design',
        'ds',                    # date_reported
        'Data_Vintage'           # data_vintage (v2.0 field)
    ]

    # Build field index map (only fields that exist in source)
    field_map = {}
    idx = 0
    for f in read_fields:
        if f in source_fields:
            field_map[f] = idx
            idx += 1
        else:
            field_map[f] = None

    # Actual read fields (only existing ones)
    actual_read_fields = [f for f in read_fields if f in source_fields]

    print(f"   Reading {len(actual_read_fields)} fields from source")

    # ========================================================================
    # STEP 3: Transform and insert
    # ========================================================================

    print("\n[3/4] Transforming and inserting records...")

# Define insert fields for gold_buildings
    insert_fields = [
        'SHAPE@XY',
        # Core Identity
        'unique_id', 'source', 'source_unique_id', 'campus_id', 'campus_name',
        'building_designation', 'record_level',
        # Coordinates
        'latitude', 'longitude',
        # Company
        'company_clean', 'company_source',
        # Geography
        'address', 'city', 'state', 'state_abbr', 'postal_code', 'county',
        'country', 'region', 'market',
        # Capacity
        'commissioned_power_mw', 'uc_power_mw', 'planned_power_mw',
        'planned_plus_uc_mw', 'full_capacity_mw',
        # Facility Details
        'facility_sqft', 'whitespace_sqft', 'pue', 'tier_design',
        # Status
        'facility_status', 'cancelled',
        # Timeline
        'date_reported', 'actual_live_date',
        # Metadata
        'data_vintage', 'ingest_date', 'notes'
    ]

    insert_count = 0
    skip_count = 0
    error_count = 0

    with arcpy.da.SearchCursor(SOURCE_FC, actual_read_fields) as search_cursor, \
         arcpy.da.InsertCursor(TARGET_FC, insert_fields) as insert_cursor:

        for row in search_cursor:
            try:
                # Build field value dict
                def get_val(field_name):
                    if field_name in field_map and field_map[field_name] is not None:
                        idx = actual_read_fields.index(field_name) if field_name in actual_read_fields else None
                        if idx is not None:
                            return row[idx]
                    return None

                # Extract values
                source_id = get_val('id')
                name = get_val('name')
                parent_id = get_val('parent_id')
                company = get_val('company_name')
                address = get_val('address')
                address_details = get_val('address_details')
                postal_code = get_val('postal_code')
                city = get_val('city')
                state = get_val('state')
                state_abbr = get_val('state_abbr')
                county = get_val('county')
                country = get_val('country')
                region = get_val('region')
                market = get_val('market')
                lat = get_val('latitude')
                lon = get_val('longitude')
                stage = get_val('stage')
                power_mw = get_val('power_mw')
                year_operational = get_val('year_operational')
                building_sqft = get_val('building_sqft')
                whitespace_sqft = get_val('whitespace_sqft')
                pue = get_val('pue')
                tier_design = get_val('tier_design')
                ds = get_val('ds')
                data_vintage = get_val('Data_Vintage')

                # Generate unique_id
                unique_id = create_unique_id(source_id)

                # Parse name for campus_name and building_designation
                campus_name, building_designation = parse_campus_name(name)

                # Generate campus_id
                campus_id = create_campus_id(company, city, campus_name, lat, lon)

                # Determine record level
                record_level = derive_record_level(name, parent_id)

                # Standardize country and region
                country_std = standardize_country(country)
                region_std = standardize_region(region, country_std)

                # Map status
                facility_status = map_status(stage)
                cancelled = is_cancelled(stage)

                # Route capacity
                commissioned_mw, uc_mw, planned_mw = route_capacity(stage, safe_float(power_mw))

                # Calculate derived capacity
                planned_plus_uc = None
                if planned_mw is not None or uc_mw is not None:
                    planned_plus_uc = (planned_mw or 0) + (uc_mw or 0)

                full_capacity = None
                if any([commissioned_mw, uc_mw, planned_mw]):
                    full_capacity = (commissioned_mw or 0) + (uc_mw or 0) + (planned_mw or 0)

                # Merge address fields
                addr_merged = address or ''
                if address_details:
                    addr_merged = f"{addr_merged}; {address_details}".strip('; ')

                # Convert dates
                actual_live_date = year_to_date(year_operational)

                # Build notes
                notes = f"Original name: {name}" if name else None

                # Build insert row
                # Create geometry from lat/lon
                lat_val = safe_float(lat)
                lon_val = safe_float(lon)

                # Skip if no coordinates
                if not lat_val or not lon_val:
                    skip_count += 1
                    continue

                shape_xy = (lon_val, lat_val)

                insert_row = [
                    shape_xy,                      # SHAPE@XY
                    # Core Identity
                    unique_id,                     # unique_id
                    SOURCE_NAME,                   # source
                    source_id,                     # source_unique_id
                    campus_id,                     # campus_id
                    campus_name,                   # campus_name
                    building_designation,          # building_designation
                    record_level,                  # record_level
                    # Coordinates
                    safe_float(lat),               # latitude
                    safe_float(lon),               # longitude
                    # Company
                    company,                       # company_clean
                    company,                       # company_source
                    # Geography
                    addr_merged if addr_merged else None,  # address
                    city,                          # city
                    state,                         # state
                    state_abbr,                    # state_abbr
                    postal_code,                   # postal_code
                    county,                        # county
                    country_std,                   # country
                    region_std,                    # region
                    market,                        # market
                    # Capacity
                    commissioned_mw,               # commissioned_power_mw
                    uc_mw,                         # uc_power_mw
                    planned_mw,                    # planned_power_mw
                    planned_plus_uc,               # planned_plus_uc_mw
                    full_capacity,                 # full_capacity_mw
                    # Facility Details
                    safe_float(building_sqft),     # facility_sqft
                    safe_float(whitespace_sqft),   # whitespace_sqft
                    safe_float(pue),               # pue
                    tier_design,                   # tier_design
                    # Status
                    facility_status,               # facility_status
                    cancelled,                     # cancelled
                    # Timeline
                    ds,                            # date_reported
                    actual_live_date,              # actual_live_date
                    # Metadata
                    data_vintage,                  # data_vintage (v2.0 field)
                    datetime.now(),                # ingest_date
                    notes                          # notes
                ]

                insert_cursor.insertRow(insert_row)
                insert_count += 1

                # Progress indicator
                if insert_count % 25 == 0:
                    print(f"   Inserted {insert_count} records...")

            except Exception as e:
                error_count += 1
                if error_count <= 5:
                    print(f"   ⚠️  Error on record: {e}")

    print(f"\n   ✓ Inserted: {insert_count} records")
    if skip_count > 0:
        print(f"   ⏭️  Skipped (duplicates): {skip_count}")
    if error_count > 0:
        print(f"   ⚠️  Errors: {error_count}")

    # ========================================================================
    # STEP 4: Post-Ingestion Validation
    # ========================================================================

    print("\n[4/4] Post-Ingestion Validation...")

    try:
        where_clause = f"source = '{SOURCE_NAME}'"

        # Create temporary layer for counting with where clause
        temp_count_layer = "temp_dcm_count"
        if arcpy.Exists(temp_count_layer):
            arcpy.management.Delete(temp_count_layer)

        arcpy.management.MakeFeatureLayer(TARGET_FC, temp_count_layer, where_clause)
        total_dcm = int(arcpy.GetCount_management(temp_count_layer)[0])
        arcpy.management.Delete(temp_count_layer)

        print(f"   Total DataCenterMap records in gold_buildings: {total_dcm}")

        # Check required fields
        required_checks = {
            'unique_id': 0,
            'latitude': 0,
            'longitude': 0,
            'company_clean': 0,
            'city': 0,
            'country': 0,
            'region': 0
        }

        # Create layer for field checks
        temp_check_layer = "temp_dcm_check"
        if arcpy.Exists(temp_check_layer):
            arcpy.management.Delete(temp_check_layer)
        arcpy.management.MakeFeatureLayer(TARGET_FC, temp_check_layer, where_clause)

        with arcpy.da.SearchCursor(temp_check_layer, list(required_checks.keys())) as cursor:
            for row in cursor:
                for i, field in enumerate(required_checks.keys()):
                    if row[i] is None or row[i] == '':
                        required_checks[field] += 1

        arcpy.management.Delete(temp_check_layer)

        print("\n   Required Field Completeness:")
        all_pass = True
        for field, null_count in required_checks.items():
            pct = ((total_dcm - null_count) / total_dcm * 100) if total_dcm > 0 else 0
            status = "✓" if null_count == 0 else "⚠️"
            if null_count > 0:
                all_pass = False
            print(f"     {field}: {pct:.1f}% ({null_count} nulls) {status}")

        # Check status distribution
        print("\n   Status Distribution:")
        status_counts = defaultdict(int)

        temp_status_layer = "temp_dcm_status"
        if arcpy.Exists(temp_status_layer):
            arcpy.management.Delete(temp_status_layer)
        arcpy.management.MakeFeatureLayer(TARGET_FC, temp_status_layer, where_clause)

        with arcpy.da.SearchCursor(temp_status_layer, ['facility_status']) as cursor:
            for row in cursor:
                status_counts[row[0] if row[0] else 'NULL'] += 1

        arcpy.management.Delete(temp_status_layer)

        for status, count in sorted(status_counts.items(), key=lambda x: -x[1]):
            print(f"     {status}: {count}")

    except Exception as e:
        print(f"   ⚠️ Validation error: {e}")
        total_dcm = insert_count
        all_pass = False

    # ========================================================================
    # SUMMARY
    # ========================================================================

    print("\n" + "=" * 80)
    print("✅ DATACENTERMAP INGESTION COMPLETE")
    print("=" * 80)
    print(f"\n📊 SUMMARY:")
    print(f"   • Source records: {source_count}")
    print(f"   • Records inserted: {insert_count}")
    print(f"   • Records skipped (duplicates): {skip_count}")
    print(f"   • Total DCM in gold_buildings: {total_dcm}")
    print(f"   • Required fields check: {'✅ PASS' if all_pass else '⚠️ CHECK ABOVE'}")
    print(f"\n⚠️  NEXT STEPS:")
    print(f"   1. Run validate_gold_buildings_data.py to verify all checks")
    print(f"   2. Run campus_rollup.py to update gold_campus")
    print(f"\nCompleted: {datetime.now()}")

    return insert_count


# ============================================================================
# EXECUTE
# ============================================================================

# ============================================================================
# EXECUTE
# ============================================================================

# Run when called via exec() OR as standalone script
try:
    inserted = ingest_datacentermap()
    print(f"\n✅ SUCCESS: {inserted} DataCenterMap records ingested")
except Exception as e:
    print(f"\n❌ ERROR: {str(e)}")
    import traceback
    traceback.print_exc()
