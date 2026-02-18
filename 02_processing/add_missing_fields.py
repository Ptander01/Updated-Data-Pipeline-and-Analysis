"""
Add Missing Fields to Gold Feature Classes
===========================================
Adds type_category field to gold_campus_full that was missing from schema.

Run in ArcGIS Pro Python window:
exec(open(r"...scripts/02_processing/add_missing_fields.py", encoding='utf-8').read())

Author: Meta Data Center GIS Team
Created: 2026-01-20
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

from config import GDB, GOLD_CAMPUS, GOLD_BUILDINGS

arcpy.env.workspace = GDB
arcpy.env.overwriteOutput = True

print("=" * 70)
print("ADD MISSING FIELDS TO GOLD FEATURE CLASSES")
print("=" * 70)

# Fields to add to gold_campus
CAMPUS_FIELDS_TO_ADD = [
    # (field_name, field_type, field_length, field_alias)
    ('type_category', 'TEXT', 50, 'Type Category'),
]

# Fields to add to gold_buildings (if any missing)
BUILDING_FIELDS_TO_ADD = [
    # Add any missing building fields here if needed
]

def add_fields_if_missing(fc_path, fields_to_add):
    """Add fields to feature class if they don't already exist."""
    fc_name = os.path.basename(fc_path)
    existing_fields = [f.name.lower() for f in arcpy.ListFields(fc_path)]

    added = 0
    for field_name, field_type, field_length, field_alias in fields_to_add:
        if field_name.lower() not in existing_fields:
            if field_type == 'TEXT':
                arcpy.management.AddField(
                    fc_path, field_name, field_type,
                    field_length=field_length, field_alias=field_alias
                )
            else:
                arcpy.management.AddField(
                    fc_path, field_name, field_type,
                    field_alias=field_alias
                )
            print(f"   ✅ Added {field_name} ({field_type}) to {fc_name}")
            added += 1
        else:
            print(f"   ⏭️  {field_name} already exists in {fc_name}")

    return added

# Add fields to gold_campus
print(f"\n[gold_campus_full]")
if arcpy.Exists(GOLD_CAMPUS):
    added_campus = add_fields_if_missing(GOLD_CAMPUS, CAMPUS_FIELDS_TO_ADD)
    print(f"   Added {added_campus} new field(s)")
else:
    print(f"   ❌ Feature class not found: {GOLD_CAMPUS}")

# Add fields to gold_buildings (if any)
if BUILDING_FIELDS_TO_ADD:
    print(f"\n[gold_buildings_full]")
    if arcpy.Exists(GOLD_BUILDINGS):
        added_buildings = add_fields_if_missing(GOLD_BUILDINGS, BUILDING_FIELDS_TO_ADD)
        print(f"   Added {added_buildings} new field(s)")
    else:
        print(f"   ❌ Feature class not found: {GOLD_BUILDINGS}")

print("\n" + "=" * 70)
print("✅ FIELD ADDITIONS COMPLETE")
print("   Re-run campus_rollup_new.py to populate type_category")
print("=" * 70)
