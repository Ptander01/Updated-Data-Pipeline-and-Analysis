"""
Data Center Hawk LEASE Ingestion Script
Ingests DCH Lease (colocation/leased) data into gold_buildings feature class.

DCH Lease has 77 fields vs DCH Hyper's 25 fields.
This script skips compliance/service/security fields and focuses on:
- Core identity and location
- Capacity (kW -> MW conversion)
- Space metrics
- UPS and fiber info

Capacity Note: DCH reports IT capacity (same as Meta), no PUE adjustment needed.

Author: Meta Data Center GIS Team
Last Updated: 2024-12-15
"""

import arcpy
from datetime import datetime
import re
import os
import sys

# Add _utils to path for config import
try:
    script_dir = os.path.dirname(os.path.abspath(__file__))
except NameError:
    script_dir = r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\scripts\01_ingestion"

utils_dir = os.path.join(os.path.dirname(script_dir), "_utils")
if utils_dir not in sys.path:
    sys.path.insert(0, utils_dir)

from config import GDB, GOLD_BUILDINGS, RAW_TABLES

# ====== CONFIGURATION ======
SOURCE_FC = RAW_TABLES['dch_lease']
TARGET_FC = GOLD_BUILDINGS
SOURCE_NAME = "DataCenterHawk"

# Conversion factors
KW_TO_MW = 0.001

# Status vocabulary mapping (DCH -> Gold schema)
STATUS_MAP = {
    'Owned': 'Active',
    'Leased': 'Active',
    'Under Construction': 'Under Construction',
    'Planned': 'Announced',
    None: 'Unknown',
    '': 'Unknown'
}

# Fields to SKIP (compliance, service, security - not needed)
SKIP_PREFIXES = ['compliance_', 'service_', 'security_']


# ====== HELPER FUNCTIONS ======

def delete_existing_records(target_fc, source_name, unique_id_prefix="DCH_L_"):
    """
    Delete existing DCH Lease records before fresh ingestion.

    IMPORTANT: Both DCH Hyper and DCH Lease use source='DataCenterHawk'.
    We distinguish them by unique_id prefix:
    - DCH Hyper: unique_id LIKE 'DCH_%' (NOT 'DCH_L_%')
    - DCH Lease: unique_id LIKE 'DCH_L_%'

    This function only deletes DCH LEASE records (DCH_L_ prefix) to avoid
    accidentally deleting DCH Hyper records when re-running ingestion.
    """
    print(f"\n[CLEANUP] Checking for existing DCH Lease records (prefix: {unique_id_prefix})...")

    # Use unique_id prefix to identify DCH Lease records specifically
    where_clause = f"unique_id LIKE '{unique_id_prefix}%'"

    # Create a temporary feature layer for selection
    temp_layer = "temp_delete_layer"
    if arcpy.Exists(temp_layer):
        arcpy.management.Delete(temp_layer)

    arcpy.management.MakeFeatureLayer(target_fc, temp_layer)
    arcpy.management.SelectLayerByAttribute(temp_layer, "NEW_SELECTION", where_clause)

    deleted_count = int(arcpy.GetCount_management(temp_layer)[0])

    if deleted_count > 0:
        arcpy.management.DeleteRows(temp_layer)
        print(f"   ✓ Deleted {deleted_count:,} existing DCH Lease records")
    else:
        print(f"   ✓ No existing DCH Lease records found")

    arcpy.management.Delete(temp_layer)
    return deleted_count


def slug(text):
    """Generate URL-safe slug from text."""
    if not text:
        return ''
    return re.sub(r'[^a-z0-9]+', '', str(text).lower())


def generate_campus_id(company, city, campus_name, lat, lon):
    """Generate unique campus_id using company|city|campus convention."""
    name_slug = slug(campus_name) if campus_name else \
                f"{round(lat,3)}{round(lon,3)}".replace('.', '').replace('-', 'n')
    return f"{slug(company)}|{slug(city)}|{name_slug}"


def derive_record_level(facility_type, name):
    """DCH Lease reports at building/facility level."""
    if facility_type and 'campus' in str(facility_type).lower():
        return 'Campus'
    if name and 'campus' in str(name).lower():
        return 'Campus'
    return 'Building'


def safe_float(val):
    """Safely convert to float."""
    if val is None or val == '' or str(val).strip() == '':
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def truncate_str(val, max_len):
    """Truncate string to max length (handles bad source data)."""
    if val is None:
        return None
    s = str(val).strip()
    if len(s) > max_len:
        return s[:max_len]
    return s


# ====== MAIN INGESTION ======
def main():
    print("=" * 70)
    print(f"DCH LEASE INGESTION STARTED: {datetime.now()}")
    print("=" * 70)

    # Verify source exists
    if not arcpy.Exists(SOURCE_FC):
        raise Exception(f"Source feature class not found: {SOURCE_FC}")

    # Delete existing records from this source (clean re-ingestion)
    delete_existing_records(TARGET_FC, SOURCE_NAME)

    total_records = int(arcpy.management.GetCount(SOURCE_FC)[0])
    print(f"\nTotal DCH Lease records: {total_records}")

    # Get actual field names from source
    source_fields = [f.name for f in arcpy.ListFields(SOURCE_FC)]
    print(f"Source has {len(source_fields)} fields")

    # Count skipped fields
    skipped_fields = [f for f in source_fields
                      if any(f.lower().startswith(p) for p in SKIP_PREFIXES)]
    print(f"Skipping {len(skipped_fields)} compliance/service/security fields")

    # Helper to find field with or without F_ prefix
    def find_field(name):
        if name in source_fields:
            return name
        elif f"F_{name}" in source_fields:
            return f"F_{name}"
        # Handle the ? prefix from CSV import
        elif f"?{name}" in source_fields:
            return f"?{name}"
        elif name.lower() in [f.lower() for f in source_fields]:
            return [f for f in source_fields if f.lower() == name.lower()][0]
        else:
            return None

    # Build field mapping for DCH Lease schema
    field_mapping = {
        'facility_id': find_field('facility_id'),
        'provider_name': find_field('provider_name'),  # DCH Lease uses provider_name, not company_name
        'company_code': find_field('company_code'),
        'address': find_field('address'),
        'city': find_field('city'),
        'state': find_field('state'),
        'postal_code': find_field('postal_code'),
        'country': find_field('country'),
        'market_id': find_field('market_id'),
        'market_name': find_field('market_name'),
        'latitude': find_field('latitude'),
        'longitude': find_field('longitude'),
        'facility_type': find_field('facility_type'),
        'status': find_field('status'),
        'date_updated': find_field('date_updated'),
        'building_size': find_field('building_size'),
        # Capacity fields (in kW)
        'capacity_commissioned_power': find_field('capacity_commissioned_power'),
        'capacity_available_power': find_field('capacity_available_power'),
        'capacity_under_construction_power': find_field('capacity_under_construction_power'),
        'capacity_planned_power': find_field('capacity_planned_power'),
        # Space fields
        'capacity_commissioned_space': find_field('capacity_commissioned_space'),
        'capacity_available_space': find_field('capacity_available_space'),
        # UPS info
        'ups_redundancy': find_field('ups_redundancy'),
        'ups_description': find_field('ups_description'),
        # Fiber
        'fiber_provider_names': find_field('fiber_provider_names'),
    }

    # Check for missing required fields
    missing = [k for k, v in field_mapping.items()
               if v is None and k in ['facility_id', 'provider_name', 'latitude', 'longitude']]
    if missing:
        print(f"\nWARNING: Missing required fields: {missing}")
        print(f"Available fields (first 20): {source_fields[:20]}...")

    # Build read_fields list
    read_fields = [v for v in field_mapping.values() if v is not None]
    print(f"Reading {len(read_fields)} fields from source")

    # Insert fields for gold_buildings
    insert_fields = [
        'SHAPE@XY', 'unique_id', 'source', 'source_unique_id', 'date_reported',
        'record_level', 'campus_id', 'campus_name', 'company_source', 'company_clean',
        'building_designation', 'address', 'postal_code', 'city', 'market',
        'state', 'state_abbr', 'county', 'country', 'region', 'latitude', 'longitude',
        'planned_power_mw', 'uc_power_mw', 'commissioned_power_mw', 'full_capacity_mw',
        'planned_plus_uc_mw', 'available_power_kw', 'pue', 'actual_live_date',
        'facility_status', 'cancelled', 'facility_sqft', 'whitespace_sqft',
        'type_category', 'owned_leased', 'notes', 'data_vintage', 'ingest_date'
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
            # Extract values
            facility_id = get_val(row, 'facility_id')
            provider_name = get_val(row, 'provider_name')
            company_code = get_val(row, 'company_code')
            address = truncate_str(get_val(row, 'address'), 255)
            city = truncate_str(get_val(row, 'city'), 100)
            state = truncate_str(get_val(row, 'state'), 100)
            postal_code = truncate_str(get_val(row, 'postal_code'), 10)  # GDB field is short, truncate aggressively
            country = truncate_str(get_val(row, 'country'), 100)
            market_name = get_val(row, 'market_name')
            latitude = get_val(row, 'latitude')
            longitude = get_val(row, 'longitude')
            facility_type = get_val(row, 'facility_type')
            status = get_val(row, 'status')
            date_updated = get_val(row, 'date_updated')
            building_size = get_val(row, 'building_size')
            cap_comm = get_val(row, 'capacity_commissioned_power')
            cap_avail = get_val(row, 'capacity_available_power')
            cap_uc = get_val(row, 'capacity_under_construction_power')
            cap_plan = get_val(row, 'capacity_planned_power')
            space_comm = get_val(row, 'capacity_commissioned_space')
            space_avail = get_val(row, 'capacity_available_space')
            ups_redundancy = get_val(row, 'ups_redundancy')
            ups_desc = get_val(row, 'ups_description')
            fiber = get_val(row, 'fiber_provider_names')

            # Skip if missing critical fields
            if not latitude or not longitude or not provider_name:
                skip_count += 1
                continue

            # ===== DERIVE FIELDS =====

            # Unique ID (use DCH_L prefix for lease to distinguish from hyper)
            unique_id = f"DCH_L_{facility_id}"

            # Company name (DCH Lease uses provider_name)
            company_name = str(provider_name).strip() if provider_name else 'Unknown'

            # Campus name
            if company_code and str(company_code).strip() and str(company_code) != 'None':
                name = f"{company_name} {company_code}".strip()
                campus_name = f"{company_name} {city}".strip()
            else:
                name = f"{company_name} {city}".strip()
                campus_name = name

            campus_name = campus_name.replace(' Data Center', '').replace(' Campus', '').strip()
            campus_id = generate_campus_id(company_name, city, campus_name, latitude, longitude)

            # Status mapping
            facility_status = STATUS_MAP.get(status, 'Unknown')

            # Capacity conversion (kW -> MW)
            # DCH reports IT capacity, no PUE adjustment needed
            commissioned_mw = safe_float(cap_comm) * KW_TO_MW if safe_float(cap_comm) else 0
            planned_mw = safe_float(cap_plan) * KW_TO_MW if safe_float(cap_plan) else 0
            uc_mw = safe_float(cap_uc) * KW_TO_MW if safe_float(cap_uc) else 0
            available_kw = safe_float(cap_avail)  # Keep in kW for available_power_kw field

            full_capacity_mw = commissioned_mw + planned_mw + uc_mw
            planned_plus_uc_mw = planned_mw + uc_mw

            # Space metrics
            facility_sqft = safe_float(building_size) or safe_float(space_comm)
            whitespace_sqft = safe_float(space_avail)

            # Record level
            record_level = derive_record_level(facility_type, name)

            # Notes - include UPS and fiber info (truncate to fit field)
            notes_parts = []
            if ups_redundancy:
                notes_parts.append(f"UPS: {ups_redundancy}")
            if ups_desc:
                notes_parts.append(f"UPS Desc: {str(ups_desc)[:50]}")
            if fiber:
                # Fiber list can be huge - just note count
                fiber_str = str(fiber)
                if len(fiber_str) > 100:
                    # Count providers if it's a list
                    try:
                        import json
                        fiber_list = json.loads(fiber_str.replace("'", '"'))
                        notes_parts.append(f"Fiber: {len(fiber_list)} providers")
                    except:
                        notes_parts.append(f"Fiber: Multiple providers")
                else:
                    notes_parts.append(f"Fiber: {fiber_str[:100]}")
            notes = truncate_str(" | ".join(notes_parts), 255) if notes_parts else None

            # Data vintage (v2.0 field) - use date_updated from source
            data_vintage = date_updated

            # Geometry
            point = (longitude, latitude)

            # Insert row
            insert_cursor.insertRow([
                point,                    # SHAPE@XY
                unique_id,                # unique_id
                SOURCE_NAME,              # source
                facility_id,              # source_unique_id
                date_updated,             # date_reported
                record_level,             # record_level
                campus_id,                # campus_id
                campus_name,              # campus_name
                company_name,             # company_source
                company_name,             # company_clean
                company_code,             # building_designation
                address,                  # address
                postal_code,              # postal_code
                city,                     # city
                market_name,              # market
                state,                    # state
                None,                     # state_abbr (could derive)
                None,                     # county
                country,                  # country
                None,                     # region (could derive from country)
                latitude,                 # latitude
                longitude,                # longitude
                planned_mw,               # planned_power_mw
                uc_mw,                    # uc_power_mw
                commissioned_mw,          # commissioned_power_mw
                full_capacity_mw,         # full_capacity_mw
                planned_plus_uc_mw,       # planned_plus_uc_mw
                available_kw,             # available_power_kw
                None,                     # pue
                None,                     # actual_live_date
                facility_status,          # facility_status
                0,                        # cancelled
                facility_sqft,            # facility_sqft
                whitespace_sqft,          # whitespace_sqft
                facility_type,            # type_category
                'Leased',                 # owned_leased (all DCH Lease are leased)
                notes,                    # notes
                data_vintage,             # data_vintage (v2.0 field from date_updated)
                datetime.now()            # ingest_date
            ])

            insert_count += 1

            if insert_count % 500 == 0:
                print(f"  Processed {insert_count} / {total_records} records...")

    print("\n" + "=" * 70)
    print("DCH LEASE INGESTION COMPLETE")
    print("=" * 70)
    print(f"Inserted: {insert_count} records")
    print(f"Skipped: {skip_count} records (missing lat/lon/provider)")
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
