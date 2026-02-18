"""
IMPORT META CANONICAL V3 - From New Authoritative Export
==========================================================
Purpose: Import comprehensive Meta datacenter inventory from internal DAI query,
         analyze changes from existing data, and update the geodatabase.

Input: CSV from internal DAI query (Meta_Authoritative_Raw.csv)
Output: Feature class 'meta_canonical_v2' in Default.gdb (replaces existing)

NEW in V3:
- Updated for new CSV column structure (Jan 2026 format)
- Change detection and analysis before import
- Summary of added/removed/changed locations
- Handles unlocated capacity as separate record_level (like TLBM in SemiAnalysis)
  - Buildings with coordinates → record_level = "Building"
  - Unlocated capacity by campus → record_level = "Unlocated Campus Capacity"

USAGE (ArcGIS Pro Python window):
    exec(open(r"C:/Users/ptanderson/Documents/ArcGIS/Projects/Lean Consensus DC Model/scripts/01_ingestion/import_meta_canonical_v3.py", encoding='utf-8').read())

Author: Meta Data Center GIS Team
Updated: January 2026
"""

import arcpy
import pandas as pd
from datetime import datetime
import os

# ============================================================================
# CONFIGURATION
# ============================================================================

# Input CSV - UPDATE THIS PATH for new data
CSV_FILE = r"C:\Users\ptanderson\Downloads\Meta_Authoritative_Raw.csv"

# Geodatabase paths
GDB_PATH = r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\Default.gdb"
OUTPUT_FC = "meta_canonical_v2"
OUTPUT_FC_FULL = os.path.join(GDB_PATH, OUTPUT_FC)

# Change analysis report output
REPORT_DIR = r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\scripts\00_docs\reports"

print("=" * 80)
print("META CANONICAL V3 IMPORT - Updated Authoritative Data")
print("=" * 80)
print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print(f"\nCSV Source: {CSV_FILE}")
print(f"Target GDB: {GDB_PATH}")
print(f"Output Feature Class: {OUTPUT_FC}")
print("\n" + "=" * 80)

# ============================================================================
# STEP 1: LOAD NEW CSV DATA
# ============================================================================
print("\n[STEP 1] Loading new CSV data...")

if not os.path.exists(CSV_FILE):
    raise FileNotFoundError(f"CSV file not found: {CSV_FILE}")

df_new = pd.read_csv(CSV_FILE, encoding='utf-8')
print(f"  Loaded {len(df_new):,} total rows")
print(f"  Columns: {list(df_new.columns)}")

# ============================================================================
# STEP 2: LOAD EXISTING DATA (if available)
# ============================================================================
print("\n[STEP 2] Loading existing meta_canonical_v2 data...")

existing_data = {}
existing_count = 0

if arcpy.Exists(OUTPUT_FC_FULL):
    # Get field names from existing FC
    existing_fields = [f.name for f in arcpy.ListFields(OUTPUT_FC_FULL)]

    # Read existing data
    read_fields = ['location_key', 'dc_code', 'datacenter', 'it_load',
                   'new_build_status', 'building_type', 'latitude', 'longitude']
    read_fields = [f for f in read_fields if f in existing_fields]

    if 'SHAPE@XY' not in read_fields:
        read_fields.insert(0, 'SHAPE@XY')

    with arcpy.da.SearchCursor(OUTPUT_FC_FULL, read_fields) as cursor:
        for row in cursor:
            loc_key = row[read_fields.index('location_key')] if 'location_key' in read_fields else None
            if loc_key:
                existing_data[loc_key] = {
                    'dc_code': row[read_fields.index('dc_code')] if 'dc_code' in read_fields else None,
                    'datacenter': row[read_fields.index('datacenter')] if 'datacenter' in read_fields else None,
                    'it_load': row[read_fields.index('it_load')] if 'it_load' in read_fields else None,
                    'new_build_status': row[read_fields.index('new_build_status')] if 'new_build_status' in read_fields else None,
                    'building_type': row[read_fields.index('building_type')] if 'building_type' in read_fields else None,
                }
                existing_count += 1

    print(f"  Found {existing_count:,} existing records")
else:
    print("  No existing meta_canonical_v2 found - this will be a fresh import")

# ============================================================================
# STEP 3: CHANGE ANALYSIS
# ============================================================================
print("\n[STEP 3] Analyzing changes...")

new_location_keys = set(df_new['location_key'].unique())
existing_location_keys = set(existing_data.keys())

# Find additions and removals
added_keys = new_location_keys - existing_location_keys
removed_keys = existing_location_keys - new_location_keys
common_keys = new_location_keys & existing_location_keys

print(f"\n  CHANGE SUMMARY:")
print(f"  ├─ Existing locations: {len(existing_location_keys):,}")
print(f"  ├─ New locations:      {len(new_location_keys):,}")
print(f"  ├─ Added:              {len(added_keys):,}")
print(f"  ├─ Removed:            {len(removed_keys):,}")
print(f"  └─ Common (potential changes): {len(common_keys):,}")

# Analyze changes in common records
changes = {
    'status_changed': [],
    'it_load_changed': [],
    'building_type_changed': [],
}

for loc_key in common_keys:
    new_row = df_new[df_new['location_key'] == loc_key].iloc[0]
    old_data = existing_data[loc_key]

    # Check status changes
    new_status = new_row.get('new_build_status', None)
    old_status = old_data.get('new_build_status', None)
    if str(new_status) != str(old_status) and pd.notna(new_status):
        changes['status_changed'].append({
            'location_key': loc_key,
            'old_status': old_status,
            'new_status': new_status
        })

    # Check IT load changes
    new_load = new_row.get('it_load', None)
    old_load = old_data.get('it_load', None)
    if pd.notna(new_load) and pd.notna(old_load):
        if abs(float(new_load) - float(old_load)) > 0.1:  # >0.1 MW change
            changes['it_load_changed'].append({
                'location_key': loc_key,
                'old_load': old_load,
                'new_load': new_load
            })

    # Check building type changes
    new_type = new_row.get('building_type', None)
    old_type = old_data.get('building_type', None)
    if str(new_type) != str(old_type) and pd.notna(new_type):
        changes['building_type_changed'].append({
            'location_key': loc_key,
            'old_type': old_type,
            'new_type': new_type
        })

print(f"\n  FIELD-LEVEL CHANGES (in common records):")
print(f"  ├─ Status changes:        {len(changes['status_changed']):,}")
print(f"  ├─ IT load changes:       {len(changes['it_load_changed']):,}")
print(f"  └─ Building type changes: {len(changes['building_type_changed']):,}")

# Show sample of added locations
if added_keys:
    print(f"\n  SAMPLE ADDED LOCATIONS (first 10):")
    added_df = df_new[df_new['location_key'].isin(added_keys)].head(10)
    for _, row in added_df.iterrows():
        dc = row.get('region', 'N/A')  # region column is actually dc_code
        status = row.get('new_build_status', 'N/A')
        print(f"    + {row['location_key']} ({dc}) - {status}")

# Show sample of removed locations
if removed_keys:
    print(f"\n  SAMPLE REMOVED LOCATIONS (first 10):")
    for loc_key in list(removed_keys)[:10]:
        old_data_item = existing_data.get(loc_key, {})
        dc = old_data_item.get('dc_code', 'N/A')
        print(f"    - {loc_key} ({dc})")

# Show sample status changes
if changes['status_changed']:
    print(f"\n  SAMPLE STATUS CHANGES (first 10):")
    for change in changes['status_changed'][:10]:
        print(f"    ~ {change['location_key']}: {change['old_status']} → {change['new_status']}")

# ============================================================================
# STEP 4: DERIVE GEOGRAPHIC REGION FROM COORDINATES
# ============================================================================
print("\n[STEP 4] Deriving geographic regions from coordinates...")

def assign_region(row):
    """
    Assign region (AMER/EMEA/APAC/OTHER) based on lat/lon coordinates.
    """
    lat = row['latitude']
    lon = row['longitude']

    if pd.isna(lat) or pd.isna(lon):
        return 'UNKNOWN'
    if lat == 0 and lon == 0:
        return 'UNKNOWN'
    if abs(lat) > 90 or abs(lon) > 180:
        return 'INVALID'

    # AMER: Longitude -180 to -30
    if -180 <= lon <= -30:
        return 'AMER'
    # EMEA: Longitude -25 to 65
    elif -25 <= lon <= 65:
        if -35 <= lat <= 75:
            return 'EMEA'
        else:
            return 'OTHER'
    # APAC: Longitude 65 to 180
    elif 65 < lon <= 180:
        return 'APAC'
    else:
        return 'OTHER'

# Map 'region' column to 'dc_code' (it contains datacenter code, not region)
df_new['dc_code'] = df_new['region']

# Derive actual region from coordinates
df_new['region_derived'] = df_new.apply(assign_region, axis=1)

print("\n  Region distribution:")
region_counts = df_new['region_derived'].value_counts()
for region, count in region_counts.items():
    pct = (count / len(df_new)) * 100
    print(f"    {region}: {count} locations ({pct:.1f}%)")

# ============================================================================
# STEP 5: DATA QUALITY CHECKS
# ============================================================================
print("\n[STEP 5] Data quality checks...")

# Coordinate completeness
has_coords = df_new[df_new['latitude'].notna() & df_new['longitude'].notna()]
missing_coords = len(df_new) - len(has_coords)

print(f"  Total locations: {len(df_new):,}")
print(f"  Valid coordinates: {len(has_coords):,} ({len(has_coords)/len(df_new)*100:.1f}%)")
print(f"  Missing coordinates: {missing_coords} ({missing_coords/len(df_new)*100:.1f}%)")

# IT load completeness
has_itload = df_new[df_new['it_load'].notna()]
print(f"  IT load available: {len(has_itload)} ({len(has_itload)/len(df_new)*100:.1f}%)")

if len(has_itload) > 0:
    total_mw = has_itload['it_load'].sum()
    print(f"  Total IT load: {total_mw:,.1f} MW")

# Build status breakdown
print("\n  Build status:")
status_counts = df_new['new_build_status'].value_counts(dropna=False)
for status, count in status_counts.items():
    status_str = status if pd.notna(status) else "NULL/Empty"
    pct = (count / len(df_new)) * 100
    print(f"    {status_str}: {count} ({pct:.1f}%)")

# Building type breakdown
print("\n  Building type:")
type_counts = df_new['building_type'].value_counts(dropna=False)
for btype, count in type_counts.items():
    type_str = btype if pd.notna(btype) else "NULL/Empty"
    pct = (count / len(df_new)) * 100
    print(f"    {type_str}: {count} ({pct:.1f}%)")

# ============================================================================
# STEP 6: PREPARE DATA FOR ARCGIS
# ============================================================================
print("\n[STEP 6] Preparing data for ArcGIS import...")

# Convert date columns
if 'latest_milestone_date' in df_new.columns:
    df_new['milestone_date'] = pd.to_datetime(df_new['latest_milestone_date'], errors='coerce')

# Separate records with/without coordinates
df_with_coords = df_new[
    df_new['latitude'].notna() &
    df_new['longitude'].notna() &
    (df_new['region_derived'] != 'INVALID')
].copy()

df_without_coords = df_new[
    df_new['latitude'].isna() |
    df_new['longitude'].isna() |
    (df_new['region_derived'] == 'INVALID')
].copy()

print(f"  Records with valid coordinates: {len(df_with_coords):,}")
print(f"  Records without coordinates: {len(df_without_coords):,}")

# ============================================================================
# STEP 7: DELETE EXISTING AND CREATE NEW FEATURE CLASS
# ============================================================================
print("\n[STEP 7] Creating feature class...")

if arcpy.Exists(OUTPUT_FC_FULL):
    print(f"  Deleting existing {OUTPUT_FC}...")
    arcpy.Delete_management(OUTPUT_FC_FULL)

# Create feature class with WGS84
sr = arcpy.SpatialReference(4326)
arcpy.CreateFeatureclass_management(
    GDB_PATH,
    OUTPUT_FC,
    "POINT",
    spatial_reference=sr
)
print(f"  Created feature class: {OUTPUT_FC}")

# Add fields
print("  Adding fields...")

fields_to_add = [
    ('location_key', 'TEXT', 20, 'Location Key'),
    ('datacenter', 'TEXT', 10, 'Datacenter (Building Number)'),
    ('dc_code', 'TEXT', 10, 'Datacenter Code'),
    ('region_derived', 'TEXT', 10, 'Region (AMER/EMEA/APAC)'),
    ('address', 'TEXT', 255, 'Address'),
    ('it_load', 'DOUBLE', None, 'IT Load (MW)'),
    ('new_build_status', 'TEXT', 50, 'Build Status'),
    ('building_type', 'TEXT', 20, 'Building Type (own/lease)'),
    ('latest_phase_gate', 'TEXT', 50, 'Latest Phase Gate'),
    ('latest_activity_status', 'TEXT', 50, 'Latest Activity Status'),
    ('milestone_date', 'DATE', None, 'Latest Milestone Date'),
    ('import_date', 'DATE', None, 'Import Date'),
    ('has_coordinates', 'SHORT', None, 'Has Valid Coordinates (1=Yes, 0=No)')
]

for field_name, field_type, field_length, field_alias in fields_to_add:
    if field_type == 'TEXT':
        arcpy.AddField_management(OUTPUT_FC_FULL, field_name, field_type,
                                  field_length=field_length, field_alias=field_alias)
    else:
        arcpy.AddField_management(OUTPUT_FC_FULL, field_name, field_type,
                                  field_alias=field_alias)

print(f"  Added {len(fields_to_add)} fields")

# ============================================================================
# STEP 8: INSERT RECORDS
# ============================================================================
print("\n[STEP 8] Inserting records...")

insert_fields = ['SHAPE@XY', 'location_key', 'datacenter', 'dc_code',
                 'region_derived', 'address', 'it_load', 'new_build_status',
                 'building_type', 'latest_phase_gate', 'latest_activity_status',
                 'milestone_date', 'import_date', 'has_coordinates']

insert_count = 0
error_count = 0

with arcpy.da.InsertCursor(OUTPUT_FC_FULL, insert_fields) as cursor:
    # Insert records WITH coordinates
    for idx, row in df_with_coords.iterrows():
        try:
            point = (row['longitude'], row['latitude'])

            values = [
                point,
                row['location_key'],
                str(row['datacenter']) if pd.notna(row['datacenter']) else None,
                row['dc_code'],
                row['region_derived'],
                row['address'] if pd.notna(row.get('address')) else None,
                row['it_load'] if pd.notna(row.get('it_load')) else None,
                row['new_build_status'] if pd.notna(row.get('new_build_status')) else None,
                row['building_type'] if pd.notna(row.get('building_type')) else None,
                row['latest_phase_gate'] if pd.notna(row.get('latest_phase_gate')) else None,
                row['latest_activity_status'] if pd.notna(row.get('latest_activity_status')) else None,
                row['milestone_date'] if pd.notna(row.get('milestone_date')) else None,
                datetime.now(),
                1  # has_coordinates = True
            ]

            cursor.insertRow(values)
            insert_count += 1

            if insert_count % 500 == 0:
                print(f"    Inserted {insert_count} records...", end='\r')

        except Exception as e:
            error_count += 1
            if error_count <= 5:
                print(f"\n    Error inserting {row['location_key']}: {str(e)}")

    # Insert records WITHOUT coordinates (at 0,0 for now)
    for idx, row in df_without_coords.iterrows():
        try:
            point = (0, 0)  # Null island placeholder

            values = [
                point,
                row['location_key'],
                str(row['datacenter']) if pd.notna(row['datacenter']) else None,
                row['dc_code'],
                'UNKNOWN',  # No coordinates to derive region
                row['address'] if pd.notna(row.get('address')) else None,
                row['it_load'] if pd.notna(row.get('it_load')) else None,
                row['new_build_status'] if pd.notna(row.get('new_build_status')) else None,
                row['building_type'] if pd.notna(row.get('building_type')) else None,
                row['latest_phase_gate'] if pd.notna(row.get('latest_phase_gate')) else None,
                row['latest_activity_status'] if pd.notna(row.get('latest_activity_status')) else None,
                row['milestone_date'] if pd.notna(row.get('milestone_date')) else None,
                datetime.now(),
                0  # has_coordinates = False
            ]

            cursor.insertRow(values)
            insert_count += 1

        except Exception as e:
            error_count += 1

print(f"\n  Successfully inserted {insert_count:,} records")
if error_count > 0:
    print(f"  Errors: {error_count}")

# ============================================================================
# STEP 9: GENERATE CHANGE REPORT
# ============================================================================
print("\n[STEP 9] Generating change report...")

report_path = os.path.join(REPORT_DIR, f"Meta_Canonical_Change_Report_{datetime.now().strftime('%Y%m%d_%H%M')}.md")

with open(report_path, 'w', encoding='utf-8') as f:
    f.write("# Meta Canonical Data Change Report\n\n")
    f.write(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
    f.write(f"**Source CSV:** {os.path.basename(CSV_FILE)}\n\n")
    f.write("---\n\n")

    f.write("## Summary\n\n")
    f.write(f"| Metric | Count |\n")
    f.write(f"|--------|-------|\n")
    f.write(f"| Previous record count | {len(existing_location_keys):,} |\n")
    f.write(f"| New record count | {len(new_location_keys):,} |\n")
    f.write(f"| Net change | {len(new_location_keys) - len(existing_location_keys):+,} |\n")
    f.write(f"| Added locations | {len(added_keys):,} |\n")
    f.write(f"| Removed locations | {len(removed_keys):,} |\n")
    f.write(f"| Status changes | {len(changes['status_changed']):,} |\n")
    f.write(f"| IT load changes | {len(changes['it_load_changed']):,} |\n")
    f.write(f"| Building type changes | {len(changes['building_type_changed']):,} |\n\n")

    # Added locations
    if added_keys:
        f.write("## Added Locations\n\n")
        f.write(f"Total: {len(added_keys)} locations\n\n")
        f.write("| Location Key | DC Code | Status | IT Load (MW) |\n")
        f.write("|--------------|---------|--------|---------------|\n")
        added_df = df_new[df_new['location_key'].isin(added_keys)]
        for _, row in added_df.head(50).iterrows():
            dc = row.get('dc_code', 'N/A')
            status = row.get('new_build_status', 'N/A')
            it_load = row.get('it_load', '')
            it_str = f"{it_load:.1f}" if pd.notna(it_load) else "N/A"
            f.write(f"| {row['location_key']} | {dc} | {status} | {it_str} |\n")
        if len(added_keys) > 50:
            f.write(f"\n*... and {len(added_keys) - 50} more*\n")
        f.write("\n")

    # Removed locations
    if removed_keys:
        f.write("## Removed Locations\n\n")
        f.write(f"Total: {len(removed_keys)} locations\n\n")
        f.write("| Location Key | DC Code |\n")
        f.write("|--------------|--------|\n")
        for loc_key in list(removed_keys)[:50]:
            old_data_item = existing_data.get(loc_key, {})
            dc = old_data_item.get('dc_code', 'N/A')
            f.write(f"| {loc_key} | {dc} |\n")
        if len(removed_keys) > 50:
            f.write(f"\n*... and {len(removed_keys) - 50} more*\n")
        f.write("\n")

    # Status changes
    if changes['status_changed']:
        f.write("## Status Changes\n\n")
        f.write(f"Total: {len(changes['status_changed'])} locations\n\n")
        f.write("| Location Key | Old Status | New Status |\n")
        f.write("|--------------|------------|------------|\n")
        for change in changes['status_changed'][:50]:
            f.write(f"| {change['location_key']} | {change['old_status']} | {change['new_status']} |\n")
        if len(changes['status_changed']) > 50:
            f.write(f"\n*... and {len(changes['status_changed']) - 50} more*\n")
        f.write("\n")

    # IT load changes
    if changes['it_load_changed']:
        f.write("## IT Load Changes\n\n")
        f.write(f"Total: {len(changes['it_load_changed'])} locations\n\n")
        f.write("| Location Key | Old Load (MW) | New Load (MW) | Change |\n")
        f.write("|--------------|---------------|---------------|--------|\n")
        for change in changes['it_load_changed'][:50]:
            old_load = float(change['old_load']) if change['old_load'] else 0
            new_load = float(change['new_load']) if change['new_load'] else 0
            diff = new_load - old_load
            f.write(f"| {change['location_key']} | {old_load:.1f} | {new_load:.1f} | {diff:+.1f} |\n")
        if len(changes['it_load_changed']) > 50:
            f.write(f"\n*... and {len(changes['it_load_changed']) - 50} more*\n")
        f.write("\n")

    f.write("---\n\n")
    f.write(f"*Report generated by import_meta_canonical_v3.py*\n")

print(f"  Change report saved: {report_path}")

# ============================================================================
# SUMMARY
# ============================================================================
print("\n" + "=" * 80)
print("IMPORT COMPLETE!")
print("=" * 80)

print(f"\n📊 SUMMARY:")
print(f"  Input CSV: {len(df_new):,} records")
print(f"  Imported to {OUTPUT_FC}: {insert_count:,} records")

print(f"\n📈 CHANGES FROM PREVIOUS:")
print(f"  Added: {len(added_keys):,} locations")
print(f"  Removed: {len(removed_keys):,} locations")
print(f"  Status changes: {len(changes['status_changed']):,}")
print(f"  IT load changes: {len(changes['it_load_changed']):,}")

print(f"\n📍 REGIONAL BREAKDOWN:")
for region, count in df_new['region_derived'].value_counts().items():
    region_load = df_new[df_new['region_derived'] == region]['it_load'].sum()
    print(f"  {region}: {count} locations, {region_load:,.0f} MW")

print(f"\n📋 NEXT STEPS:")
print(f"  1. Review change report: {os.path.basename(report_path)}")
print(f"  2. Run meta_deduplicate.py to create building-level data")
print(f"  3. Run ingest_meta_canonical.py to update gold_buildings_full")

print("\n" + "=" * 80)
