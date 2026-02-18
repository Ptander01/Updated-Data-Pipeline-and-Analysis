"""
META CANONICAL CAMPUS ROLLUP - Standalone Campus Aggregation
=============================================================
Purpose: Aggregate meta_canonical_buildings to campus-level for standalone
         authoritative reference (separate from gold_campus_full).

This creates a STANDALONE meta_canonical_campus feature class that:
- Contains ONLY Meta internal data (not mixed with vendor data)
- Serves as ground truth for validation against vendor estimates
- Groups buildings by dc_code (datacenter campus code)

For INTEGRATED campus data (mixed with vendors), use:
- ingest_meta_canonical.py → gold_buildings_full
- campus_rollup_new.py → gold_campus_full

USAGE (ArcGIS Pro Python window):
    exec(open(r"C:/Users/ptanderson/Documents/ArcGIS/Projects/Lean Consensus DC Model/scripts/02_processing/campus_rollup_meta_canonical.py", encoding='utf-8').read())

Author: Meta Data Center GIS Team
Created: January 2026
"""

import arcpy
import os
from datetime import datetime

# ============================================================================
# CONFIGURATION
# ============================================================================

GDB = r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\Default.gdb"
META_BUILDINGS = os.path.join(GDB, "meta_canonical_buildings")
META_CAMPUS = os.path.join(GDB, "meta_canonical_campus")

# Grouping field - use dc_code for Meta campus rollup
GROUPING_FIELD = 'dc_code'

print("=" * 80)
print("META CANONICAL CAMPUS ROLLUP - Standalone")
print("=" * 80)
print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print(f"\nSource: {META_BUILDINGS}")
print(f"Output: {META_CAMPUS}")
print(f"Grouping by: {GROUPING_FIELD}")

arcpy.env.workspace = GDB
arcpy.env.overwriteOutput = True

# ============================================================================
# STEP 1: Validate source data
# ============================================================================
print("\n[STEP 1] Validating source data...")

if not arcpy.Exists(META_BUILDINGS):
    raise ValueError(f"Source not found: {META_BUILDINGS}")

building_count = int(arcpy.management.GetCount(META_BUILDINGS)[0])
print(f"   ✅ Found {building_count:,} buildings in meta_canonical_buildings")

# Check fields
building_fields = [f.name for f in arcpy.ListFields(META_BUILDINGS)]
print(f"   Available fields: {len(building_fields)}")

# Check grouping field exists
if GROUPING_FIELD not in building_fields:
    raise ValueError(f"Grouping field '{GROUPING_FIELD}' not found in meta_canonical_buildings")

# ============================================================================
# STEP 2: Delete existing and create new feature class
# ============================================================================
print("\n[STEP 2] Creating output feature class...")

if arcpy.Exists(META_CAMPUS):
    print(f"   Deleting existing {os.path.basename(META_CAMPUS)}...")
    arcpy.management.Delete(META_CAMPUS)

# Create point feature class with WGS84
sr = arcpy.SpatialReference(4326)
arcpy.management.CreateFeatureclass(
    out_path=GDB,
    out_name="meta_canonical_campus",
    geometry_type="POINT",
    spatial_reference=sr
)
print(f"   ✅ Created meta_canonical_campus")

# Add fields
fields_to_add = [
    ('dc_code', 'TEXT', 10, 'Datacenter Code'),
    ('region_derived', 'TEXT', 10, 'Region (AMER/EMEA/APAC)'),
    ('building_count', 'LONG', None, 'Building Count'),
    ('suite_count', 'LONG', None, 'Suite Count'),
    ('it_load_total', 'DOUBLE', None, 'Total IT Load (MW)'),
    ('it_load_complete', 'DOUBLE', None, 'Complete Build IT Load (MW)'),
    ('it_load_active', 'DOUBLE', None, 'Active Build IT Load (MW)'),
    ('it_load_future', 'DOUBLE', None, 'Future Build IT Load (MW)'),
    ('owned_count', 'LONG', None, 'Owned Building Count'),
    ('leased_count', 'LONG', None, 'Leased Building Count'),
    ('has_coordinates', 'SHORT', None, 'Has Valid Coordinates (1=Yes, 0=No)'),
    ('import_date', 'DATE', None, 'Import Date'),
]

print("   Adding fields...")
for field_name, field_type, field_length, field_alias in fields_to_add:
    if field_type == 'TEXT':
        arcpy.management.AddField(META_CAMPUS, field_name, field_type,
                                  field_length=field_length, field_alias=field_alias)
    else:
        arcpy.management.AddField(META_CAMPUS, field_name, field_type,
                                  field_alias=field_alias)
print(f"   ✅ Added {len(fields_to_add)} fields")

# ============================================================================
# STEP 3: Aggregate buildings by dc_code
# ============================================================================
print("\n[STEP 3] Aggregating buildings by dc_code...")

# Build aggregation dictionary
campus_data = {}

# Read fields from buildings
read_fields = ['SHAPE@XY', 'dc_code', 'suite_count', 'it_load_total', 
               'new_build_status', 'owned_leased', 'region_derived', 'has_coordinates']

# Filter to only available fields
available_read_fields = ['SHAPE@XY']
for f in read_fields[1:]:
    if f in building_fields:
        available_read_fields.append(f)
    else:
        print(f"   ⚠️ Field not found: {f}")

print(f"   Reading {len(available_read_fields)} fields from buildings...")

with arcpy.da.SearchCursor(META_BUILDINGS, available_read_fields) as cursor:
    for row in cursor:
        shape = row[0]
        
        # Get field values by index
        def get_val(field_name):
            try:
                idx = available_read_fields.index(field_name)
                return row[idx]
            except (ValueError, IndexError):
                return None
        
        dc_code = get_val('dc_code')
        if not dc_code:
            continue
        
        # Initialize campus if not exists
        if dc_code not in campus_data:
            campus_data[dc_code] = {
                'coords': [],
                'region': None,
                'building_count': 0,
                'suite_count': 0,
                'it_load_total': 0,
                'it_load_complete': 0,
                'it_load_active': 0,
                'it_load_future': 0,
                'owned_count': 0,
                'leased_count': 0,
                'has_coordinates': 0,
            }
        
        campus = campus_data[dc_code]
        campus['building_count'] += 1
        
        # Sum suite count
        suite_count = get_val('suite_count')
        if suite_count:
            campus['suite_count'] += int(suite_count)
        
        # Sum IT load
        it_load = get_val('it_load_total')
        if it_load:
            campus['it_load_total'] += float(it_load)
        
        # IT load by status
        status = get_val('new_build_status')
        if it_load and status:
            if status == 'Complete Build':
                campus['it_load_complete'] += float(it_load)
            elif status == 'Active Build':
                campus['it_load_active'] += float(it_load)
            elif status == 'Future Build':
                campus['it_load_future'] += float(it_load)
        
        # Count owned vs leased
        owned_leased = get_val('owned_leased')
        if owned_leased:
            if 'own' in owned_leased.lower():
                campus['owned_count'] += 1
            elif 'lease' in owned_leased.lower():
                campus['leased_count'] += 1
        
        # Collect coordinates for centroid
        has_coords = get_val('has_coordinates')
        if has_coords == 1 and shape and shape[0] != 0 and shape[1] != 0:
            campus['coords'].append(shape)
            campus['has_coordinates'] = 1
        
        # Region (first non-null)
        region = get_val('region_derived')
        if region and not campus['region']:
            campus['region'] = region

print(f"   ✅ Aggregated {len(campus_data)} unique campuses")

# ============================================================================
# STEP 4: Insert campus records
# ============================================================================
print("\n[STEP 4] Inserting campus records...")

insert_fields = ['SHAPE@XY', 'dc_code', 'region_derived', 'building_count', 
                 'suite_count', 'it_load_total', 'it_load_complete', 
                 'it_load_active', 'it_load_future', 'owned_count', 
                 'leased_count', 'has_coordinates', 'import_date']

insert_count = 0
no_coords_count = 0

with arcpy.da.InsertCursor(META_CAMPUS, insert_fields) as cursor:
    for dc_code, campus in campus_data.items():
        # Calculate centroid from coordinates
        if campus['coords']:
            avg_lon = sum(c[0] for c in campus['coords']) / len(campus['coords'])
            avg_lat = sum(c[1] for c in campus['coords']) / len(campus['coords'])
            point = (avg_lon, avg_lat)
        else:
            point = (0, 0)  # Null island for no-coord campuses
            no_coords_count += 1
        
        values = [
            point,
            dc_code,
            campus['region'],
            campus['building_count'],
            campus['suite_count'],
            campus['it_load_total'],
            campus['it_load_complete'],
            campus['it_load_active'],
            campus['it_load_future'],
            campus['owned_count'],
            campus['leased_count'],
            campus['has_coordinates'],
            datetime.now(),
        ]
        
        cursor.insertRow(values)
        insert_count += 1

print(f"   ✅ Inserted {insert_count} campus records")
print(f"   ⚠️ {no_coords_count} campuses have no coordinates (at null island)")

# ============================================================================
# STEP 5: Summary statistics
# ============================================================================
print("\n[STEP 5] Summary statistics...")

total_it_load = sum(c['it_load_total'] for c in campus_data.values())
total_buildings = sum(c['building_count'] for c in campus_data.values())
total_suites = sum(c['suite_count'] for c in campus_data.values())

# Region breakdown
regions = {}
for dc_code, campus in campus_data.items():
    region = campus['region'] if campus['region'] else 'UNKNOWN'
    if region not in regions:
        regions[region] = {'campuses': 0, 'buildings': 0, 'it_load': 0}
    regions[region]['campuses'] += 1
    regions[region]['buildings'] += campus['building_count']
    regions[region]['it_load'] += campus['it_load_total']

print(f"\n   📊 TOTALS:")
print(f"   ├─ Campuses: {insert_count:,}")
print(f"   ├─ Buildings: {total_buildings:,}")
print(f"   ├─ Suites: {total_suites:,}")
print(f"   └─ IT Load: {total_it_load:,.1f} MW")

print(f"\n   📍 REGIONAL BREAKDOWN:")
for region, data in sorted(regions.items()):
    print(f"   ├─ {region}: {data['campuses']} campuses, {data['buildings']} buildings, {data['it_load']:,.0f} MW")

# Coordinate breakdown
with_coords = sum(1 for c in campus_data.values() if c['has_coordinates'] == 1)
without_coords = insert_count - with_coords
print(f"\n   📍 COORDINATE STATUS:")
print(f"   ├─ With coordinates: {with_coords}")
print(f"   └─ Without coordinates: {without_coords}")

# ============================================================================
# COMPLETION
# ============================================================================
print("\n" + "=" * 80)
print("✅ META CANONICAL CAMPUS ROLLUP COMPLETE!")
print("=" * 80)
print(f"Finished: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print(f"\nOutput: {META_CAMPUS}")
print(f"Records: {insert_count} campuses")
print(f"Total IT Load: {total_it_load:,.1f} MW")
print("\n" + "=" * 80)
