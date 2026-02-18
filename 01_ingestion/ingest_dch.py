"""
Data Center Hawk Ingestion Script
Ingests DCH hyperscale data into gold_buildings feature class.

Author: Meta Data Center GIS Team
Last Updated: 2024-12-15
"""

import arcpy
from datetime import datetime
import re
import os
import sys

# Add _utils to path for config import
# Handle both direct execution and exec() from ArcGIS Pro Python window
try:
    script_dir = os.path.dirname(os.path.abspath(__file__))
except NameError:
    # Running via exec() - use known path
    script_dir = r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\scripts\01_ingestion"

utils_dir = os.path.join(os.path.dirname(script_dir), "_utils")
if utils_dir not in sys.path:
    sys.path.insert(0, utils_dir)

from config import GDB, GOLD_BUILDINGS, RAW_TABLES

# ====== CONFIGURATION ======
# Source and target paths from config module
SOURCE_FC = RAW_TABLES['dch_hyper']
TARGET_FC = GOLD_BUILDINGS  # Uses gold_buildings_full for full data pipeline
SOURCE_NAME = "DataCenterHawk"

# Conversion factors
KW_TO_MW = 0.001

# Status vocabulary mapping (DCH -> Gold schema)
STATUS_MAP = {
    'Owned': 'Active',
    'Under Construction': 'Under Construction',
    'Planned': 'Announced',
    None: 'Unknown',
    '': 'Unknown'
}

# ====== HELPER FUNCTIONS ======

def delete_existing_records(target_fc, source_name, unique_id_prefix="DCH_"):
    """
    Delete existing DCH Hyper records before fresh ingestion.

    IMPORTANT: Both DCH Hyper and DCH Lease use source='DataCenterHawk'.
    We distinguish them by unique_id prefix:
    - DCH Hyper: unique_id LIKE 'DCH_%' AND NOT LIKE 'DCH_L_%'
    - DCH Lease: unique_id LIKE 'DCH_L_%'

    This function only deletes DCH HYPER records to avoid accidentally
    deleting DCH Lease records when re-running ingestion.
    """
    print(f"\n[CLEANUP] Checking for existing DCH Hyper records (prefix: {unique_id_prefix}, excluding DCH_L_)...")

    # Use unique_id prefix to identify DCH Hyper records specifically
    # Exclude DCH_L_ prefix which is used by DCH Lease
    where_clause = f"unique_id LIKE '{unique_id_prefix}%' AND unique_id NOT LIKE 'DCH_L_%'"

    # Create a temporary feature layer for selection
    temp_layer = "temp_delete_layer"
    if arcpy.Exists(temp_layer):
        arcpy.management.Delete(temp_layer)

    arcpy.management.MakeFeatureLayer(target_fc, temp_layer)
    arcpy.management.SelectLayerByAttribute(temp_layer, "NEW_SELECTION", where_clause)

    deleted_count = int(arcpy.GetCount_management(temp_layer)[0])

    if deleted_count > 0:
        arcpy.management.DeleteRows(temp_layer)
        print(f"   ✓ Deleted {deleted_count:,} existing DCH Hyper records")
    else:
        print(f"   ✓ No existing DCH Hyper records found")

    arcpy.management.Delete(temp_layer)
    return deleted_count


def slug(text):
    """Generate URL-safe slug from text."""
    if not text:
        return ''
    return re.sub(r'[^a-z0-9]+', '', str(text).lower())

def generate_campus_id(company, city, campus_name, lat, lon):
    """
    Generate unique campus_id using convention:
    company|city|campus_name (slugified)

    Fallback to coordinates if campus_name missing.
    """
    name_slug = slug(campus_name) if campus_name else \
                f"{round(lat,3)}{round(lon,3)}".replace('.', '').replace('-', 'n')
    return f"{slug(company)}|{slug(city)}|{name_slug}"

def year_to_date(year_val):
    """Convert commissioned_year (Double) to datetime (Dec 31)."""
    if year_val and year_val > 1900:
        return datetime(int(year_val), 12, 31)
    return None

def derive_record_level(facility_type, name):
    """
    Determine if record represents Building or Campus level.
    DCH reports at building level - default to Building.
    """
    if facility_type and 'campus' in str(facility_type).lower():
        return 'Campus'
    if name and 'campus' in str(name).lower():
        return 'Campus'
    return 'Building'  # DCH default is building-level

# ====== MAIN INGESTION ======
def main():
    print("=" * 70)
    print(f"DCH INGESTION STARTED: {datetime.now()}")
    print("=" * 70)

    # Verify source exists
    if not arcpy.Exists(SOURCE_FC):
        raise Exception(f"Source feature class not found: {SOURCE_FC}")

    # Delete existing records from this source (clean re-ingestion)
    delete_existing_records(TARGET_FC, SOURCE_NAME)

    # Get count
    total_records = int(arcpy.management.GetCount(SOURCE_FC)[0])
    print(f"\nTotal DCH records to process: {total_records}")

    # Get actual field names from source (handle F_ prefix from CSV import)
    source_fields = [f.name for f in arcpy.ListFields(SOURCE_FC)]
    print(f"Source has {len(source_fields)} fields")

    # Helper to find field with or without F_ prefix
    def find_field(name):
        if name in source_fields:
            return name
        elif f"F_{name}" in source_fields:
            return f"F_{name}"
        elif name.lower() in [f.lower() for f in source_fields]:
            return [f for f in source_fields if f.lower() == name.lower()][0]
        else:
            return None

    # Build read fields list with actual field names
    field_mapping = {
        'facility_id': find_field('facility_id'),
        'company_name': find_field('company_name'),
        'company_code': find_field('company_code'),
        'address': find_field('address'),
        'city': find_field('city'),
        'state': find_field('state'),
        'state_abbr': find_field('State_Abbr') or find_field('state_abbr'),
        'postal_code': find_field('postal_code'),
        'country': find_field('country'),
        'market_name': find_field('market_name'),
        'region': find_field('Region') or find_field('region'),
        'county': find_field('County') or find_field('county'),
        'latitude': find_field('latitude'),
        'longitude': find_field('longitude'),
        'facility_type': find_field('facility_type'),
        'status': find_field('status'),
        'capacity_commissioned_power': find_field('capacity_commissioned_power'),
        'capacity_planned_power': find_field('capacity_planned_power'),
        'capacity_under_construction_power': find_field('capacity_under_construction_power'),
        'capacity_building_sf': find_field('capacity_building_sf'),
        'commissioned_year': find_field('commissioned_year'),
        'date_updated': find_field('date_updated'),
    }

    # Check for missing required fields
    missing = [k for k, v in field_mapping.items() if v is None and k in ['facility_id', 'company_name', 'latitude', 'longitude']]
    if missing:
        print(f"\nWARNING: Missing required fields: {missing}")
        print(f"Available fields: {source_fields[:20]}...")

    # Build read_fields list (only include fields that exist)
    read_fields = [v for v in field_mapping.values() if v is not None]
    print(f"Reading {len(read_fields)} fields from source")

    # Field mappings for insert
    insert_fields = [
        'SHAPE@XY', 'unique_id', 'source', 'source_unique_id', 'date_reported',
        'record_level', 'campus_id', 'campus_name', 'company_source', 'company_clean',
        'building_designation', 'address', 'postal_code', 'city', 'market',
        'state', 'state_abbr', 'county', 'country', 'region', 'latitude', 'longitude',
        'planned_power_mw', 'uc_power_mw', 'commissioned_power_mw', 'full_capacity_mw',
        'planned_plus_uc_mw', 'pue', 'actual_live_date', 'facility_status', 'cancelled',
        'facility_sqft', 'type_category', 'data_vintage', 'ingest_date'
    ]

    insert_count = 0
    skip_count = 0

    print("\nProcessing records...")

    # Build index map for field access
    field_idx = {k: read_fields.index(v) if v in read_fields else None
                 for k, v in field_mapping.items()}

    def get_val(row, field_name):
        idx = field_idx.get(field_name)
        if idx is not None:
            return row[idx]
        return None

    with arcpy.da.SearchCursor(SOURCE_FC, read_fields) as search_cursor, \
         arcpy.da.InsertCursor(TARGET_FC, insert_fields) as insert_cursor:

        for row in search_cursor:
            # Extract values using field index
            facility_id = get_val(row, 'facility_id')
            company_name = get_val(row, 'company_name')
            company_code = get_val(row, 'company_code')
            address = get_val(row, 'address')
            city = get_val(row, 'city')
            state = get_val(row, 'state')
            state_abbr = get_val(row, 'state_abbr')
            postal_code = get_val(row, 'postal_code')
            country = get_val(row, 'country')
            market_name = get_val(row, 'market_name')
            region = get_val(row, 'region')
            county = get_val(row, 'county')
            latitude = get_val(row, 'latitude')
            longitude = get_val(row, 'longitude')
            facility_type = get_val(row, 'facility_type')
            status = get_val(row, 'status')
            cap_comm = get_val(row, 'capacity_commissioned_power')
            cap_plan = get_val(row, 'capacity_planned_power')
            cap_uc = get_val(row, 'capacity_under_construction_power')
            cap_sf = get_val(row, 'capacity_building_sf')
            commissioned_year = get_val(row, 'commissioned_year')
            date_updated = get_val(row, 'date_updated')

            # Skip if missing critical fields
            if not latitude or not longitude or not company_name:
                skip_count += 1
                continue

            # ===== DERIVE FIELDS =====

            # Unique ID
            unique_id = f"DCH_{facility_id}"

            # Name & Campus Logic
            if company_code and str(company_code).strip() and str(company_code) != 'None':
                name = f"{company_name} {company_code}".strip()
                campus_name = f"{company_name} {city}".strip()
            else:
                name = f"{company_name} {city}".strip()
                campus_name = name

            # Clean campus_name
            campus_name = campus_name.replace(' Data Center', '').replace(' Campus', '').strip()

            # Generate campus_id
            campus_id = generate_campus_id(company_name, city, campus_name, latitude, longitude)

            # Status mapping
            facility_status = STATUS_MAP.get(status, 'Unknown')

            # Capacity conversion (kW -> MW)
            commissioned_mw = (cap_comm * KW_TO_MW) if cap_comm else 0
            planned_mw = (cap_plan * KW_TO_MW) if cap_plan else 0
            uc_mw = (cap_uc * KW_TO_MW) if cap_uc else 0
            full_capacity_mw = commissioned_mw + planned_mw + uc_mw
            planned_plus_uc_mw = planned_mw + uc_mw

            # Dates
            actual_live_date = year_to_date(commissioned_year)
            ingest_date = datetime.now()

            # Record level
            record_level = derive_record_level(facility_type, name)

            # Geometry
            point = (longitude, latitude)

            # Handle DCH state field - DCH sometimes has full state names, sometimes abbreviations
            # State abbreviation lookup
            STATE_TO_ABBR = {
                'Alabama': 'AL', 'Alaska': 'AK', 'Arizona': 'AZ', 'Arkansas': 'AR',
                'California': 'CA', 'Colorado': 'CO', 'Connecticut': 'CT', 'Delaware': 'DE',
                'Florida': 'FL', 'Georgia': 'GA', 'Hawaii': 'HI', 'Idaho': 'ID',
                'Illinois': 'IL', 'Indiana': 'IN', 'Iowa': 'IA', 'Kansas': 'KS',
                'Kentucky': 'KY', 'Louisiana': 'LA', 'Maine': 'ME', 'Maryland': 'MD',
                'Massachusetts': 'MA', 'Michigan': 'MI', 'Minnesota': 'MN', 'Mississippi': 'MS',
                'Missouri': 'MO', 'Montana': 'MT', 'Nebraska': 'NE', 'Nevada': 'NV',
                'New Hampshire': 'NH', 'New Jersey': 'NJ', 'New Mexico': 'NM', 'New York': 'NY',
                'North Carolina': 'NC', 'North Dakota': 'ND', 'Ohio': 'OH', 'Oklahoma': 'OK',
                'Oregon': 'OR', 'Pennsylvania': 'PA', 'Rhode Island': 'RI', 'South Carolina': 'SC',
                'South Dakota': 'SD', 'Tennessee': 'TN', 'Texas': 'TX', 'Utah': 'UT',
                'Vermont': 'VT', 'Virginia': 'VA', 'Washington': 'WA', 'West Virginia': 'WV',
                'Wisconsin': 'WI', 'Wyoming': 'WY', 'District of Columbia': 'DC'
            }

            final_state = None
            final_state_abbr = None

            state_val = str(state).strip() if state else ''
            state_abbr_val = str(state_abbr).strip() if state_abbr else ''

            # If state is a 2-char abbreviation, use it directly
            if len(state_val) == 2 and state_val.isupper():
                final_state_abbr = state_val
                final_state = None  # Will be enriched later
            # If state is a full name, look up the abbreviation
            elif state_val in STATE_TO_ABBR:
                final_state = state_val
                final_state_abbr = STATE_TO_ABBR[state_val]
            # Check case-insensitive match
            elif state_val.title() in STATE_TO_ABBR:
                final_state = state_val.title()
                final_state_abbr = STATE_TO_ABBR[state_val.title()]
            # If state_abbr field has a valid abbreviation, use it
            elif len(state_abbr_val) == 2:
                final_state_abbr = state_abbr_val.upper()
                final_state = state_val if len(state_val) > 2 else None
            else:
                # Fallback - truncate if needed
                final_state = state_val[:100] if state_val else None
                final_state_abbr = state_abbr_val[:10] if state_abbr_val else None

            # Data vintage (v2.0 field) - use date_updated from source
            data_vintage = date_updated

            # Insert row
            insert_cursor.insertRow([
                point, unique_id, SOURCE_NAME, facility_id, date_updated,
                record_level, campus_id, campus_name, company_name, company_name,
                company_code, address, postal_code, city, market_name,
                final_state, final_state_abbr, county, country, region, latitude, longitude,
                planned_mw, uc_mw, commissioned_mw, full_capacity_mw, planned_plus_uc_mw,
                None, actual_live_date, facility_status, 0, cap_sf, facility_type,
                data_vintage, ingest_date
            ])

            insert_count += 1

            # Progress indicator
            if insert_count % 100 == 0:
                print(f"  Processed {insert_count} / {total_records} records...")

    print("\n" + "=" * 70)
    print("DCH INGESTION COMPLETE")
    print("=" * 70)
    print(f"Inserted: {insert_count} records")
    print(f"Skipped: {skip_count} records (missing lat/lon/company)")
    print(f"Completed: {datetime.now()}")
    print("=" * 70)

# ====== EXECUTE ======
# Runs when called via exec() OR as standalone script
try:
    main()
except Exception as e:
    print(f"\nERROR: {str(e)}")
    import traceback
    traceback.print_exc()
