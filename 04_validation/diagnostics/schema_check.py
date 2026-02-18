"""
Quick Schema Check - Gold Buildings & Campus
=============================================
Lists all fields and their types for gold_buildings_full and gold_campus_full.

Run in ArcGIS Pro Python window.
"""

import arcpy
import os
import sys

# Add _utils to path
try:
    script_dir = os.path.dirname(os.path.abspath(__file__))
except NameError:
    script_dir = r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\scripts\04_validation"

utils_dir = os.path.join(os.path.dirname(script_dir), "_utils")
if utils_dir not in sys.path:
    sys.path.insert(0, utils_dir)

from config import GDB, GOLD_BUILDINGS, GOLD_CAMPUS

def print_schema(fc_path, fc_name):
    """Print schema for a feature class."""
    print(f"\n{'='*70}")
    print(f"  {fc_name}")
    print(f"{'='*70}")

    if not arcpy.Exists(fc_path):
        print(f"  ❌ NOT FOUND: {fc_path}")
        return

    # Get record count
    count = int(arcpy.management.GetCount(fc_path)[0])
    print(f"  Records: {count:,}")

    # Get geometry type
    desc = arcpy.Describe(fc_path)
    print(f"  Geometry: {desc.shapeType}")
    print(f"  Spatial Reference: {desc.spatialReference.name}")

    # Get fields
    fields = arcpy.ListFields(fc_path)
    print(f"  Total Fields: {len(fields)}")

    print(f"\n  {'#':<4} {'Field Name':<30} {'Type':<12} {'Length':<8} {'Alias'}")
    print(f"  {'-'*4} {'-'*30} {'-'*12} {'-'*8} {'-'*30}")

    for i, f in enumerate(fields, 1):
        length = f.length if f.type == 'String' else '-'
        alias = f.aliasName if f.aliasName != f.name else ''
        print(f"  {i:<4} {f.name:<30} {f.type:<12} {str(length):<8} {alias}")

def main():
    print("="*70)
    print("   GOLD SCHEMA CHECK")
    print("="*70)
    print(f"\n  GDB: {GDB}")

    # Check gold_buildings_full
    print_schema(GOLD_BUILDINGS, "gold_buildings_full")

    # Check gold_campus_full
    print_schema(GOLD_CAMPUS, "gold_campus_full")

    # Also check meta canonical layers
    meta_buildings = os.path.join(GDB, "meta_canonical_buildings")
    meta_campus = os.path.join(GDB, "meta_canonical_campus")

    print_schema(meta_buildings, "meta_canonical_buildings")
    print_schema(meta_campus, "meta_canonical_campus")

    print("\n" + "="*70)
    print("   SCHEMA CHECK COMPLETE")
    print("="*70)

# Execute
try:
    main()
except Exception as e:
    print(f"\n❌ ERROR: {str(e)}")
    import traceback
    traceback.print_exc()
