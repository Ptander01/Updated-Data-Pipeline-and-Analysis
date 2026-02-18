"""
Meta Canonical Ingestion Script
================================
Ingests meta_canonical_buildings into gold_buildings_full feature class.

This adds Meta's internal authoritative data to the unified gold table
with source = "Meta Canonical" to distinguish from external vendor data.

Changes (Jan 29, 2026):
- Added "Unlocated Campus Capacity" record_level for buildings without coordinates
- Similar to how SemiAnalysis handles TLBM (Total Lease By Market) records
- record_level = "Building" for located buildings
- record_level = "Unlocated Campus Capacity" for buildings without valid coords
- This preserves all Meta capacity data while distinguishing spatial vs non-spatial

Author: Meta Data Center GIS Team
Created: December 17, 2024
Updated: January 29, 2026
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

from config import GDB, GOLD_BUILDINGS, META_CANONICAL_BUILDINGS

# ============================================================================
# CONFIGURATION
# ============================================================================

SOURCE_FC = META_CANONICAL_BUILDINGS
TARGET_FC = GOLD_BUILDINGS
SOURCE_NAME = "Meta Canonical"

# Build status mapping (meta_canonical -> gold schema)
STATUS_MAP = {
    'Complete Build': 'Active',
    'Active Build': 'Under Construction',
    'Future Build': 'Announced',
    None: 'Unknown',
    '': 'Unknown'
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


def slug(text):
    """Generate URL-safe slug from text."""
    if not text:
        return ''
    return re.sub(r'[^a-z0-9]+', '', str(text).lower())


def generate_campus_id(company, dc_code, region):
    """
    Generate campus_id for Meta canonical buildings.
    Uses dc_code as the campus identifier since Meta uses 3-letter codes.

    Format: meta|{region}|{dc_code}
    """
    region_slug = slug(region) if region else 'unknown'
    dc_slug = slug(dc_code) if dc_code else 'unknown'
    return f"meta|{region_slug}|{dc_slug}"


def generate_campus_name(dc_code, region):
    """
    Generate human-readable campus name.
    Format: Meta {dc_code} ({region})
    """
    if dc_code:
        if region:
            return f"Meta {dc_code}"
        return f"Meta {dc_code}"
    return "Meta Unknown"


# ============================================================================
# MAIN INGESTION
# ============================================================================

def main():
    print("=" * 70)
    print(f"META CANONICAL INGESTION STARTED: {datetime.now()}")
    print("=" * 70)
    print(f"\nSource: {SOURCE_FC}")
    print(f"Target: {TARGET_FC}")
    print(f"Source Label: {SOURCE_NAME}")

    # Verify source exists
    if not arcpy.Exists(SOURCE_FC):
        raise Exception(f"Source feature class not found: {SOURCE_FC}")

    # Verify target exists
    if not arcpy.Exists(TARGET_FC):
        raise Exception(f"Target feature class not found: {TARGET_FC}")

    # Delete existing records from this source (clean re-ingestion)
    delete_existing_records(TARGET_FC, SOURCE_NAME)

    # Get count
    total_records = int(arcpy.management.GetCount(SOURCE_FC)[0])
    print(f"\nTotal Meta Canonical records to process: {total_records}")

    # Get source fields
    source_fields = [f.name for f in arcpy.ListFields(SOURCE_FC)]
    print(f"Source has {len(source_fields)} fields: {source_fields}")

    # Define read fields from meta_canonical_buildings
    read_fields = [
        'SHAPE@',           # Geometry (multipoint from dissolve)
        'building_key',     # e.g., "ATN-1"
        'dc_code',          # e.g., "ATN"
        'datacenter',       # e.g., "1" (building number)
        'suite_count',      # Number of suites
        'region_derived',   # AMER, EMEA, APAC
        'new_build_status', # Complete Build, Active Build, Future Build
        'it_load_total',    # Total IT load in MW
        'has_coordinates',  # 1 or 0
        'building_type',    # Own or Lease (original)
        'owned_leased',     # Owned or Leased (normalized)
    ]

    # Check which fields exist
    available_read_fields = ['SHAPE@']
    for f in read_fields[1:]:  # Skip SHAPE@
        if f in source_fields:
            available_read_fields.append(f)
        else:
            print(f"   ⚠️ Field not found: {f}")

    print(f"\nReading {len(available_read_fields)} fields from source")

    # Define insert fields for gold_buildings
    insert_fields = [
        'SHAPE@XY',             # Point geometry
        'unique_id',            # Meta_Canonical_{building_key}
        'source',               # "Meta Canonical"
        'source_unique_id',     # building_key
        'date_reported',        # NULL (internal data)
        'record_level',         # "Building"
        'campus_id',            # meta|{region}|{dc_code}
        'campus_name',          # Meta {dc_code}
        'company_source',       # "Meta"
        'company_clean',        # "Meta"
        'building_designation', # datacenter number
        'address',              # NULL
        'postal_code',          # NULL
        'city',                 # NULL (could derive from dc_code mapping)
        'market',               # NULL
        'state',                # NULL
        'state_abbr',           # NULL
        'county',               # NULL
        'country',              # NULL (could derive from region)
        'region',               # region_derived
        'latitude',             # From SHAPE@
        'longitude',            # From SHAPE@
        'planned_power_mw',     # 0 (IT load is commissioned)
        'uc_power_mw',          # Derive from status
        'commissioned_power_mw',# it_load_total (if Complete Build)
        'full_capacity_mw',     # it_load_total
        'planned_plus_uc_mw',   # Derive from status
        'pue',                  # NULL
        'actual_live_date',     # NULL
        'facility_status',      # Mapped from new_build_status
        'cancelled',            # 0
        'facility_sqft',        # NULL
        'type_category',        # "Hyperscale"
        'owned_leased',         # From owned_leased field
        'data_vintage',         # Today's date (internal data, no vintage in source)
        'ingest_date',          # Now
    ]

    # Build index map for field access
    def get_field_idx(field_name):
        try:
            return available_read_fields.index(field_name)
        except ValueError:
            return None

    insert_count = 0
    skip_count = 0
    no_coords_count = 0

    print("\nProcessing records...")

    with arcpy.da.SearchCursor(SOURCE_FC, available_read_fields) as search_cursor, \
         arcpy.da.InsertCursor(TARGET_FC, insert_fields) as insert_cursor:

        for row in search_cursor:
            # Extract values
            shape = row[0]  # SHAPE@ is always first

            building_key_idx = get_field_idx('building_key')
            building_key = row[building_key_idx] if building_key_idx else None

            dc_code_idx = get_field_idx('dc_code')
            dc_code = row[dc_code_idx] if dc_code_idx else None

            datacenter_idx = get_field_idx('datacenter')
            datacenter = row[datacenter_idx] if datacenter_idx else None

            suite_count_idx = get_field_idx('suite_count')
            suite_count = row[suite_count_idx] if suite_count_idx else None

            region_idx = get_field_idx('region_derived')
            region = row[region_idx] if region_idx else None

            status_idx = get_field_idx('new_build_status')
            new_build_status = row[status_idx] if status_idx else None

            it_load_idx = get_field_idx('it_load_total')
            it_load_total = row[it_load_idx] if it_load_idx else None

            has_coords_idx = get_field_idx('has_coordinates')
            has_coordinates = row[has_coords_idx] if has_coords_idx else None

            owned_leased_idx = get_field_idx('owned_leased')
            owned_leased = row[owned_leased_idx] if owned_leased_idx else None

            # Skip if no building_key
            if not building_key:
                skip_count += 1
                continue

            # Get coordinates from geometry
            if shape and not shape.isMultipart:
                centroid = shape.centroid
                longitude = centroid.X
                latitude = centroid.Y
            elif shape and shape.isMultipart:
                # For multipoint, use centroid
                centroid = shape.centroid
                longitude = centroid.X
                latitude = centroid.Y
            else:
                # No geometry - use NULL coordinates
                longitude = None
                latitude = None
                no_coords_count += 1

            # Check for valid coordinates (not null island)
            if latitude is not None and longitude is not None:
                if abs(latitude) < 0.01 and abs(longitude) < 0.01:
                    # Null island - treat as no coordinates
                    latitude = None
                    longitude = None
                    no_coords_count += 1

            # Generate derived fields
            unique_id = f"MetaCanonical_{building_key}"
            campus_id = generate_campus_id("Meta", dc_code, region)
            campus_name = generate_campus_name(dc_code, region)

            # Map status
            facility_status = STATUS_MAP.get(new_build_status, 'Unknown')

            # Capacity fields based on status
            it_load = it_load_total if it_load_total else 0

            if new_build_status == 'Complete Build':
                commissioned_mw = it_load
                uc_mw = 0
                planned_mw = 0
            elif new_build_status == 'Active Build':
                commissioned_mw = 0
                uc_mw = it_load
                planned_mw = 0
            elif new_build_status == 'Future Build':
                commissioned_mw = 0
                uc_mw = 0
                planned_mw = it_load
            else:
                # Unknown status - assume commissioned
                commissioned_mw = it_load
                uc_mw = 0
                planned_mw = 0

            full_capacity_mw = it_load
            planned_plus_uc_mw = planned_mw + uc_mw

            # Building designation from datacenter number
            building_designation = str(datacenter) if datacenter else None

            # Country from region
            if region == 'AMER':
                country = 'United States'  # Assumption - most Meta AMER is US
            elif region == 'EMEA':
                country = None  # Could be multiple countries
            elif region == 'APAC':
                country = None  # Could be multiple countries
            else:
                country = None

            # Create point geometry (if we have coordinates)
            if latitude and longitude:
                point = (longitude, latitude)
            else:
                point = (0, 0)  # Will be flagged as no coords

            # Data vintage - use today's date for Meta internal data
            data_vintage = datetime.now()

            # Determine record_level based on coordinate availability
            # Similar to how SemiAnalysis uses "TLBM" for unlocated market aggregates
            # Note: Using shorter value due to field length constraint in gold_buildings_full
            if latitude and longitude and not (abs(latitude) < 0.01 and abs(longitude) < 0.01):
                record_level = "Building"
            else:
                record_level = "Unlocated"  # Short for "Unlocated Campus Capacity"

            # Insert row
            insert_cursor.insertRow([
                point,                  # SHAPE@XY
                unique_id,              # unique_id
                SOURCE_NAME,            # source
                building_key,           # source_unique_id
                None,                   # date_reported
                record_level,           # record_level - "Building" or "Unlocated Campus Capacity"
                campus_id,              # campus_id
                campus_name,            # campus_name
                'Meta',                 # company_source
                'Meta',                 # company_clean
                building_designation,   # building_designation
                None,                   # address
                None,                   # postal_code
                None,                   # city
                None,                   # market
                None,                   # state
                None,                   # state_abbr
                None,                   # county
                country,                # country
                region,                 # region
                latitude,               # latitude
                longitude,              # longitude
                planned_mw,             # planned_power_mw
                uc_mw,                  # uc_power_mw
                commissioned_mw,        # commissioned_power_mw
                full_capacity_mw,       # full_capacity_mw
                planned_plus_uc_mw,     # planned_plus_uc_mw
                None,                   # pue
                None,                   # actual_live_date
                facility_status,        # facility_status
                0,                      # cancelled
                None,                   # facility_sqft
                'Hyperscale',           # type_category
                owned_leased,           # owned_leased
                data_vintage,           # data_vintage (v2.0 field)
                datetime.now(),         # ingest_date
            ])

            insert_count += 1

            # Progress indicator
            if insert_count % 50 == 0:
                print(f"  Processed {insert_count} / {total_records} records...")

    print("\n" + "=" * 70)
    print("META CANONICAL INGESTION COMPLETE")
    print("=" * 70)
    print(f"Inserted: {insert_count} records")
    print(f"Skipped (no building_key): {skip_count} records")
    print(f"No coordinates: {no_coords_count} records")
    print(f"Source label: {SOURCE_NAME}")
    print(f"Completed: {datetime.now()}")
    print("=" * 70)

    # Verify insertion
    total_gold = int(arcpy.management.GetCount(TARGET_FC)[0])
    print(f"\nTotal records in gold_buildings_full: {total_gold:,}")


# ============================================================================
# EXECUTE
# ============================================================================

try:
    main()
except Exception as e:
    print(f"\n❌ ERROR: {str(e)}")
    import traceback
    traceback.print_exc()
