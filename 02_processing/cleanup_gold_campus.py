"""
Gold Campus Cleanup Script
===========================

Fixes several issues with gold_campus_full:

1. Removes legacy cluster fields (cluster_id, cluster_source_count, cluster_campus_name)
2. Populates latitude/longitude from geometry
3. Adds ucid field if missing (campus_id now contains UCID)
4. Cleans up state/state_abbr consistency

Run in ArcGIS Pro Python window:
exec(open(r"...scripts/02_processing/cleanup_gold_campus.py", encoding='utf-8').read())

Author: Meta Data Center GIS Team
Created: December 30, 2025
"""

import arcpy
import os
import sys

# Add _utils to path for config import
try:
    script_dir = os.path.dirname(os.path.abspath(__file__))
except NameError:
    script_dir = r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\scripts\02_processing"

utils_dir = os.path.join(os.path.dirname(script_dir), "_utils")
if utils_dir not in sys.path:
    sys.path.insert(0, utils_dir)

from config import GDB, GOLD_CAMPUS

arcpy.env.workspace = GDB
arcpy.env.overwriteOutput = True

print("=" * 70)
print("   GOLD CAMPUS CLEANUP")
print("=" * 70)

# Get existing fields
existing_fields = [f.name for f in arcpy.ListFields(GOLD_CAMPUS)]
print(f"\nExisting fields: {len(existing_fields)}")

# =============================================================================
# STEP 1: Remove legacy cluster fields
# =============================================================================
print("\n[Step 1] Checking for legacy cluster fields...")

legacy_fields = ['cluster_id', 'cluster_source_count', 'cluster_campus_name']
fields_to_delete = [f for f in legacy_fields if f in existing_fields]

if fields_to_delete:
    print(f"   Found legacy fields: {fields_to_delete}")
    for field in fields_to_delete:
        try:
            arcpy.management.DeleteField(GOLD_CAMPUS, field)
            print(f"   ✅ Deleted: {field}")
        except Exception as e:
            print(f"   ⚠️ Could not delete {field}: {e}")
else:
    print("   No legacy cluster fields found")

# =============================================================================
# STEP 2: Add ucid field if missing (alias for campus_id which now contains UCID)
# =============================================================================
print("\n[Step 2] Checking ucid field...")

# Refresh field list
existing_fields = [f.name for f in arcpy.ListFields(GOLD_CAMPUS)]

if 'ucid' not in existing_fields:
    arcpy.management.AddField(GOLD_CAMPUS, 'ucid', 'TEXT', field_length=75,
                              field_alias='Universal Campus ID')
    print("   ✅ Added 'ucid' field")

    # Copy campus_id to ucid (since campus_id now contains UCID values)
    with arcpy.da.UpdateCursor(GOLD_CAMPUS, ['campus_id', 'ucid']) as cursor:
        count = 0
        for row in cursor:
            row[1] = row[0]  # Copy campus_id to ucid
            cursor.updateRow(row)
            count += 1
    print(f"   ✅ Copied campus_id values to ucid ({count} records)")
else:
    print("   ucid field already exists")

# =============================================================================
# STEP 3: Populate latitude/longitude from geometry
# =============================================================================
print("\n[Step 3] Populating latitude/longitude from geometry...")

# Add fields if missing
existing_fields = [f.name for f in arcpy.ListFields(GOLD_CAMPUS)]

if 'latitude' not in existing_fields:
    arcpy.management.AddField(GOLD_CAMPUS, 'latitude', 'DOUBLE', field_alias='Latitude')
    print("   ✅ Added 'latitude' field")

if 'longitude' not in existing_fields:
    arcpy.management.AddField(GOLD_CAMPUS, 'longitude', 'DOUBLE', field_alias='Longitude')
    print("   ✅ Added 'longitude' field")

# Populate from geometry
with arcpy.da.UpdateCursor(GOLD_CAMPUS, ['SHAPE@XY', 'latitude', 'longitude']) as cursor:
    count = 0
    for row in cursor:
        xy = row[0]
        if xy and xy[0] is not None and xy[1] is not None:
            row[1] = xy[1]  # latitude = Y
            row[2] = xy[0]  # longitude = X
            cursor.updateRow(row)
            count += 1

print(f"   ✅ Populated lat/lon for {count} records")

# =============================================================================
# STEP 4: Check and report state/state_abbr consistency
# =============================================================================
print("\n[Step 4] Checking state/state_abbr consistency...")

# Count records where state looks like an abbreviation (2 chars, uppercase)
abbr_in_state = 0
missing_state_abbr = 0

with arcpy.da.SearchCursor(GOLD_CAMPUS, ['state', 'state_abbr']) as cursor:
    for row in cursor:
        state = row[0] or ''
        state_abbr = row[1] or ''

        # Check if state is 2-char abbreviation
        if len(state) == 2 and state.isupper():
            abbr_in_state += 1

        if not state_abbr and state:
            missing_state_abbr += 1

print(f"   Records with abbreviation in 'state' field: {abbr_in_state}")
print(f"   Records missing 'state_abbr': {missing_state_abbr}")

if abbr_in_state > 0:
    print(f"   ⚠️ Consider running state standardization script")

# =============================================================================
# STEP 5: Summary
# =============================================================================
print("\n" + "=" * 70)
print("   CLEANUP COMPLETE")
print("=" * 70)

final_count = int(arcpy.management.GetCount(GOLD_CAMPUS)[0])
final_fields = [f.name for f in arcpy.ListFields(GOLD_CAMPUS)]

print(f"\n   gold_campus_full: {final_count} records")
print(f"   Total fields: {len(final_fields)}")
print(f"\n   Key fields present:")
print(f"     ✓ ucid: {'ucid' in final_fields}")
print(f"     ✓ latitude: {'latitude' in final_fields}")
print(f"     ✓ longitude: {'longitude' in final_fields}")

print("\n" + "=" * 70)
