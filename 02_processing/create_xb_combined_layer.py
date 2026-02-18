"""
Create Combined XB Layer for Experience Builder
================================================

Purpose:
Creates a single feature class that combines gold_buildings_full and gold_campus_full
for use in ArcGIS Experience Builder (XB) with filtering capabilities.

Output: gold_combined_xb

Filterable Fields:
- record_level: 'Building' or 'Campus'
- company_clean_filter: Hyperscaler names or 'Colo - All Other'
- facility_status: Active, Under Construction, Announced, etc.
- region: AMER, EMEA, APAC
- country, state, city

Usage:
Run AFTER campus_rollup_new.py completes.

Run in ArcGIS Pro Python window:
exec(open(r"...scripts/07_visualization/create_xb_combined_layer.py", encoding='utf-8').read())

Author: Meta Data Center GIS Team
Created: December 30, 2025
"""

import arcpy
import os
import sys
from datetime import datetime

# Add _utils to path for config import
try:
    script_dir = os.path.dirname(os.path.abspath(__file__))
except NameError:
    script_dir = r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\scripts\07_visualization"

utils_dir = os.path.join(os.path.dirname(script_dir), "_utils")
if utils_dir not in sys.path:
    sys.path.insert(0, utils_dir)

from config import GDB, GOLD_BUILDINGS, GOLD_CAMPUS

arcpy.env.workspace = GDB
arcpy.env.overwriteOutput = True

# Output feature class
GOLD_COMBINED_XB = os.path.join(GDB, "gold_combined_xb")

# =============================================================================
# UNIFIED SCHEMA - All fields from both buildings and campus layers
# =============================================================================
# This schema includes ALL fields to ensure buildings and campus have the same
# structure when combined into gold_combined_xb.
#
# Field sources:
#   - BOTH: Field exists in both layers (possibly different names)
#   - BUILDING: Building-only field (NULL for campus records)
#   - CAMPUS: Campus-only field (aggregated from buildings)
#
# FIELD ORDER: Organized by category for easier attribute table navigation
# See FIELD_SCHEMA_AUDIT.md for complete documentation
# =============================================================================

UNIFIED_SCHEMA = [
    # =========================================================================
    # CATEGORY 1: IDENTIFIERS
    # =========================================================================
    ('record_level', 'TEXT', 20, 'Record Level'),           # 'Building' or 'Campus'
    ('ucid', 'TEXT', 75, 'Universal Campus ID'),            # BOTH (campus-level ID)
    ('building_ucid', 'TEXT', 100, 'Building UCID'),        # BUILDING only
    ('unique_id', 'TEXT', 100, 'Source Unique ID'),         # BUILDING only (source record ID)

    # =========================================================================
    # CATEGORY 2: COMPANY / OWNERSHIP
    # =========================================================================
    ('company_clean', 'TEXT', 100, 'Company (Standardized)'),  # BOTH - primary
    ('company_source', 'TEXT', 255, 'Company (Original)'),     # BOTH - raw from source
    ('company_clean_filter', 'TEXT', 100, 'Company Filter'),   # BOTH - XB filtering
    ('developer', 'TEXT', 100, 'Developer'),                   # BOTH (v2.0)
    ('tenant', 'TEXT', 100, 'Tenant'),                         # BOTH (v2.0)
    ('end_user', 'TEXT', 100, 'End User'),                     # BOTH (v2.0)
    ('developer_list', 'TEXT', 500, 'Developer List'),         # CAMPUS only
    ('tenant_list', 'TEXT', 500, 'Tenant List'),               # CAMPUS only
    ('end_user_list', 'TEXT', 500, 'End User List'),           # CAMPUS only

    # =========================================================================
    # CATEGORY 3: LOCATION
    # =========================================================================
    ('campus_name', 'TEXT', 255, 'Campus Name'),            # BOTH
    ('building_designation', 'TEXT', 100, 'Building'),      # BUILDING only
    ('address', 'TEXT', 255, 'Address'),                    # BOTH
    ('city', 'TEXT', 100, 'City'),                          # BOTH
    ('market', 'TEXT', 128, 'Market'),                      # BOTH (e.g., "Northern Virginia")
    ('county', 'TEXT', 128, 'County'),                      # BOTH
    ('state', 'TEXT', 100, 'State'),                        # BOTH
    ('state_abbr', 'TEXT', 10, 'State Abbr'),               # BOTH
    ('postal_code', 'TEXT', 16, 'Postal Code'),             # BOTH
    ('country', 'TEXT', 100, 'Country'),                    # BOTH
    ('region', 'TEXT', 20, 'Region'),                       # BOTH (AMER/EMEA/APAC)
    ('latitude', 'DOUBLE', None, 'Latitude'),               # BOTH
    ('longitude', 'DOUBLE', None, 'Longitude'),             # BOTH

    # =========================================================================
    # CATEGORY 4: CAPACITY - POWER (MW)
    # =========================================================================
    ('full_capacity_mw', 'DOUBLE', None, 'Full Capacity (MW)'),            # PRIMARY
    ('commissioned_power_mw', 'DOUBLE', None, 'Commissioned (MW)'),        # BOTH
    ('uc_power_mw', 'DOUBLE', None, 'Under Construction (MW)'),            # BOTH
    ('planned_power_mw', 'DOUBLE', None, 'Planned (MW)'),                  # BOTH

    # =========================================================================
    # CATEGORY 5: CAPACITY - AREA
    # =========================================================================
    ('facility_sqft', 'DOUBLE', None, 'Facility Area (sqft)'),  # BOTH

    # =========================================================================
    # CATEGORY 6: STATUS & FLAGS
    # =========================================================================
    ('facility_status', 'TEXT', 50, 'Facility Status'),     # BOTH
    ('is_essential', 'SHORT', None, 'Essential Site'),      # BOTH (0/1)
    ('type_category', 'TEXT', 50, 'Type Category'),         # BOTH (Hyperscale, Colocation, Enterprise, Edge)
    ('owned_leased', 'TEXT', 50, 'Owned/Leased'),           # BOTH

    # =========================================================================
    # CATEGORY 7: DATES / TIMELINE
    # =========================================================================
    ('construction_start_date', 'DATE', None, 'Construction Start'),  # BOTH
    ('construction_end_date', 'DATE', None, 'Construction End'),      # BOTH
    ('actual_live_date', 'DATE', None, 'Operational Date'),           # BOTH
    ('lease_start_date', 'DATE', None, 'Lease Start'),                # BOTH (v2.0)
    ('lease_end_date', 'DATE', None, 'Lease End'),                    # BOTH (v2.0)
    ('data_vintage', 'DATE', None, 'Data Vintage'),                   # BOTH
    ('ingest_date', 'DATE', None, 'Ingest Date'),                     # BOTH

    # =========================================================================
    # CATEGORY 8: ENERGY / INFRASTRUCTURE
    # =========================================================================
    ('energy_source', 'TEXT', 50, 'Energy Source'),         # BOTH (v2.0)
    ('ai_gpu_indicator', 'TEXT', 20, 'AI/GPU Workload'),    # BOTH (v2.0)

    # =========================================================================
    # CATEGORY 9: YEAR FORECAST (MW)
    # =========================================================================
    ('mw_2023', 'DOUBLE', None, 'MW 2023'),                 # BOTH
    ('mw_2024', 'DOUBLE', None, 'MW 2024'),                 # BOTH
    ('mw_2025', 'DOUBLE', None, 'MW 2025'),                 # BOTH
    ('mw_2026', 'DOUBLE', None, 'MW 2026'),                 # BOTH
    ('mw_2027', 'DOUBLE', None, 'MW 2027'),                 # BOTH
    ('mw_2028', 'DOUBLE', None, 'MW 2028'),                 # BOTH
    ('mw_2029', 'DOUBLE', None, 'MW 2029'),                 # BOTH
    ('mw_2030', 'DOUBLE', None, 'MW 2030'),                 # BOTH
    ('mw_2031', 'DOUBLE', None, 'MW 2031'),                 # BOTH
    ('mw_2032', 'DOUBLE', None, 'MW 2032'),                 # BOTH

    # =========================================================================
    # CATEGORY 10: CAMPUS AGGREGATES
    # =========================================================================
    ('building_count', 'LONG', None, 'Building Count'),     # CAMPUS (buildings = 1)
    ('source_count', 'LONG', None, 'Source Count'),         # CAMPUS only

    # =========================================================================
    # CATEGORY 10: SOURCE TRACKING
    # =========================================================================
    ('source', 'TEXT', 200, 'Data Source(s)'),              # BOTH
    ('source_id', 'TEXT', 100, 'Source Record ID'),         # BUILDING only

    # =========================================================================
    # CATEGORY 11: NOTES
    # =========================================================================
    ('notes', 'TEXT', 1000, 'Notes'),                       # BOTH
]

# Field name mappings: campus_field -> unified_field
# Used when campus layer has different field names than unified schema
CAMPUS_FIELD_MAPPINGS = {
    'facility_sqft': 'facility_sqft_sum',
    'facility_status': 'facility_status_agg',
    'unique_id': 'campus_id',
}


def create_output_feature_class():
    """Create the output feature class with proper schema."""
    print("\n[Step 1] Creating output feature class...")

    # Delete if exists
    if arcpy.Exists(GOLD_COMBINED_XB):
        arcpy.management.Delete(GOLD_COMBINED_XB)
        print("   Deleted existing gold_combined_xb")

    # Get spatial reference from buildings
    sr = arcpy.Describe(GOLD_BUILDINGS).spatialReference

    # Create as point feature class
    arcpy.management.CreateFeatureclass(
        out_path=GDB,
        out_name="gold_combined_xb",
        geometry_type="POINT",
        spatial_reference=sr
    )

    # Add fields from unified schema
    for field_def in UNIFIED_SCHEMA:
        field_name = field_def[0]
        field_type = field_def[1]
        field_length = field_def[2]
        field_alias = field_def[3]

        if field_type == 'TEXT':
            arcpy.management.AddField(GOLD_COMBINED_XB, field_name, field_type,
                                      field_length=field_length, field_alias=field_alias)
        elif field_type == 'LONG':
            arcpy.management.AddField(GOLD_COMBINED_XB, field_name, field_type,
                                      field_alias=field_alias)
        else:
            arcpy.management.AddField(GOLD_COMBINED_XB, field_name, field_type,
                                      field_alias=field_alias)

    print(f"   Created gold_combined_xb with {len(UNIFIED_SCHEMA)} fields")
    return GOLD_COMBINED_XB


def get_field_value(row, field_name, field_list):
    """Safely get field value from row."""
    try:
        idx = field_list.index(field_name)
        return row[idx]
    except (ValueError, IndexError):
        return None


def copy_buildings():
    """Copy building records to combined layer."""
    print("\n[Step 2] Copying building records...")

    # Get existing fields
    building_fields = [f.name for f in arcpy.ListFields(GOLD_BUILDINGS)]

    # Build read fields list (only include fields that exist)
    read_fields = ['SHAPE@']
    for field_def in UNIFIED_SCHEMA:
        field_name = field_def[0]
        if field_name in building_fields:
            read_fields.append(field_name)

    # Build insert fields list
    insert_fields = ['SHAPE@'] + [f[0] for f in UNIFIED_SCHEMA]

    count = 0
    with arcpy.da.SearchCursor(GOLD_BUILDINGS, read_fields) as s_cursor:
        with arcpy.da.InsertCursor(GOLD_COMBINED_XB, insert_fields) as i_cursor:
            for row in s_cursor:
                # Build insert row
                insert_row = [row[0]]  # SHAPE@

                for field_def in UNIFIED_SCHEMA:
                    field_name = field_def[0]

                    if field_name == 'record_level':
                        insert_row.append('Building')
                    elif field_name == 'building_count':
                        insert_row.append(1)  # Each building counts as 1
                    elif field_name == 'source_count':
                        insert_row.append(1)  # Each building is 1 source
                    elif field_name in ['developer_list', 'tenant_list', 'end_user_list']:
                        insert_row.append(None)  # Campus-only aggregated fields
                    elif field_name == 'facility_status':
                        # Try facility_status, fallback to status
                        val = get_field_value(row, 'facility_status', read_fields)
                        if not val:
                            val = get_field_value(row, 'status', read_fields)
                        insert_row.append(val)
                    elif field_name in read_fields:
                        insert_row.append(get_field_value(row, field_name, read_fields))
                    else:
                        insert_row.append(None)

                i_cursor.insertRow(insert_row)
                count += 1

    print(f"   Copied {count:,} building records")
    return count


def copy_campuses():
    """Copy campus records to combined layer."""
    print("\n[Step 3] Copying campus records...")

    # Get existing fields
    campus_fields = [f.name for f in arcpy.ListFields(GOLD_CAMPUS)]

    # Build read fields list with field mappings
    # Campus has different field names for some unified fields
    read_fields = ['SHAPE@']
    field_name_to_campus_field = {}  # Maps unified name -> actual campus field name

    for field_def in UNIFIED_SCHEMA:
        field_name = field_def[0]

        # Check if this field has a different name in campus layer
        if field_name in CAMPUS_FIELD_MAPPINGS:
            campus_field = CAMPUS_FIELD_MAPPINGS[field_name]
            if campus_field in campus_fields:
                read_fields.append(campus_field)
                field_name_to_campus_field[field_name] = campus_field
        elif field_name in campus_fields:
            read_fields.append(field_name)
            field_name_to_campus_field[field_name] = field_name

    # Build insert fields list
    insert_fields = ['SHAPE@'] + [f[0] for f in UNIFIED_SCHEMA]

    count = 0
    with arcpy.da.SearchCursor(GOLD_CAMPUS, read_fields) as s_cursor:
        with arcpy.da.InsertCursor(GOLD_COMBINED_XB, insert_fields) as i_cursor:
            for row in s_cursor:
                # Build insert row
                insert_row = [row[0]]  # SHAPE@

                for field_def in UNIFIED_SCHEMA:
                    field_name = field_def[0]

                    if field_name == 'record_level':
                        insert_row.append('Campus')
                    elif field_name == 'building_ucid':
                        insert_row.append(None)  # Campus doesn't have building_ucid
                    elif field_name in ['building_designation', 'source_id']:
                        insert_row.append(None)  # Building-only fields
                    elif field_name == 'ucid':
                        # Campus uses campus_id as UCID (after our changes)
                        insert_row.append(get_field_value(row, 'campus_id', read_fields))
                    elif field_name in field_name_to_campus_field:
                        # Use the mapped field name
                        campus_field = field_name_to_campus_field[field_name]
                        insert_row.append(get_field_value(row, campus_field, read_fields))
                    else:
                        insert_row.append(None)

                i_cursor.insertRow(insert_row)
                count += 1

    print(f"   Copied {count:,} campus records")
    return count


def add_indexes():
    """Add indexes for common filter fields."""
    print("\n[Step 4] Adding indexes for XB filtering...")

    index_fields = [
        'record_level',
        'ucid',
        'company_clean',
        'company_clean_filter',
        'facility_status',
        'region',
        'country',
        'state',
        'city',
    ]

    for field in index_fields:
        try:
            arcpy.management.AddIndex(GOLD_COMBINED_XB, field, f"idx_{field}")
            print(f"   Added index: idx_{field}")
        except Exception as e:
            print(f"   Warning: Could not add index for {field}: {e}")


def generate_summary():
    """Generate summary statistics."""
    print("\n[Step 5] Generating summary...")

    # Count by record level
    building_count = 0
    campus_count = 0

    with arcpy.da.SearchCursor(GOLD_COMBINED_XB, ['record_level']) as cursor:
        for row in cursor:
            if row[0] == 'Building':
                building_count += 1
            else:
                campus_count += 1

    # Count by company filter
    company_counts = {}
    with arcpy.da.SearchCursor(GOLD_COMBINED_XB, ['company_clean_filter']) as cursor:
        for row in cursor:
            company = row[0] or 'Unknown'
            company_counts[company] = company_counts.get(company, 0) + 1

    print("\n" + "=" * 70)
    print("   COMBINED XB LAYER SUMMARY")
    print("=" * 70)
    print(f"\n   Total records: {building_count + campus_count:,}")
    print(f"   - Buildings: {building_count:,}")
    print(f"   - Campuses: {campus_count:,}")

    print(f"\n   By Company Filter:")
    for company, count in sorted(company_counts.items(), key=lambda x: -x[1])[:10]:
        print(f"     {company}: {count:,}")

    print(f"\n   Output: {GOLD_COMBINED_XB}")
    print("=" * 70)


def main():
    print("=" * 70)
    print("   CREATE COMBINED XB LAYER")
    print("=" * 70)
    print(f"   Started: {datetime.now()}")
    print(f"\n   Combining gold_buildings_full + gold_campus_full")
    print(f"   Output: gold_combined_xb")

    # Verify inputs exist
    if not arcpy.Exists(GOLD_BUILDINGS):
        print(f"\n   ERROR: {GOLD_BUILDINGS} not found!")
        return
    if not arcpy.Exists(GOLD_CAMPUS):
        print(f"\n   ERROR: {GOLD_CAMPUS} not found!")
        return

    # Create output
    create_output_feature_class()

    # Copy records
    building_count = copy_buildings()
    campus_count = copy_campuses()

    # Add indexes
    add_indexes()

    # Generate summary
    generate_summary()

    print(f"\n   Completed: {datetime.now()}")
    print("=" * 70)


# Execute
if __name__ == "__main__":
    main()
else:
    main()
