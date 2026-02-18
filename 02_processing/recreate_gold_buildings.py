"""
Recreate gold_buildings_full Feature Class
Force-deletes and recreates the feature class from gold_buildings (lean) template.

Use this when the feature class is corrupted or inaccessible.

Author: Meta Data Center GIS Team
Last Updated: 2024-12-15
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

from config import GDB, GOLD_BUILDINGS_FULL, GOLD_BUILDINGS_LEAN

arcpy.env.workspace = GDB
arcpy.env.overwriteOutput = True

def main():
    print("=" * 70)
    print("RECREATE gold_buildings_full")
    print("=" * 70)

    template_fc = GOLD_BUILDINGS_LEAN
    output_fc = GOLD_BUILDINGS_FULL
    output_name = os.path.basename(output_fc)
    output_gdb = os.path.dirname(output_fc)

    # Check template exists
    if not arcpy.Exists(template_fc):
        raise Exception(f"Template not found: {template_fc}")

    print(f"Template: {os.path.basename(template_fc)}")
    print(f"Output: {output_name}")

    # Force delete if exists (no prompt)
    if arcpy.Exists(output_fc):
        print(f"\nDeleting existing {output_name}...")
        try:
            arcpy.management.Delete(output_fc)
            print("  Deleted successfully")
        except Exception as e:
            print(f"  Delete failed: {e}")
            print("  Trying to clear locks...")
            # Try to clear locks by compacting
            try:
                arcpy.management.Compact(GDB)
                arcpy.management.Delete(output_fc)
                print("  Deleted after compact")
            except Exception as e2:
                raise Exception(f"Cannot delete corrupted FC. Close ArcGIS Pro and try again. Error: {e2}")

    # Get template properties
    desc = arcpy.Describe(template_fc)
    spatial_ref = desc.spatialReference
    geometry_type = desc.shapeType
    has_m = "ENABLED" if desc.hasM else "DISABLED"
    has_z = "ENABLED" if desc.hasZ else "DISABLED"

    print(f"\nCreating new feature class...")
    print(f"  Geometry: {geometry_type}")
    print(f"  Spatial Ref: {spatial_ref.name}")

    # Create empty feature class
    arcpy.management.CreateFeatureclass(
        out_path=output_gdb,
        out_name=output_name,
        geometry_type=geometry_type.upper(),
        spatial_reference=spatial_ref,
        has_m=has_m,
        has_z=has_z
    )

    # Copy fields from template
    template_fields = arcpy.ListFields(template_fc)
    fields_added = 0

    for field in template_fields:
        # Skip system fields
        if field.name.upper() in ['OBJECTID', 'OID', 'SHAPE', 'SHAPE_LENGTH', 'SHAPE_AREA']:
            continue
        if field.type in ['OID', 'Geometry']:
            continue

        try:
            if field.type == 'String':
                arcpy.management.AddField(
                    output_fc,
                    field.name,
                    field.type,
                    field_length=field.length,
                    field_alias=field.aliasName,
                    field_is_nullable="NULLABLE" if field.isNullable else "NON_NULLABLE"
                )
            else:
                arcpy.management.AddField(
                    output_fc,
                    field.name,
                    field.type,
                    field_precision=field.precision,
                    field_scale=field.scale,
                    field_alias=field.aliasName,
                    field_is_nullable="NULLABLE" if field.isNullable else "NON_NULLABLE"
                )
            fields_added += 1
        except Exception as e:
            print(f"  Warning: Could not add field {field.name}: {e}")

    # Verify
    new_field_count = len(arcpy.ListFields(output_fc))
    record_count = int(arcpy.management.GetCount(output_fc)[0])

    print(f"\n{'='*70}")
    print("RECREATION COMPLETE")
    print(f"{'='*70}")
    print(f"  Feature Class: {output_name}")
    print(f"  Fields Added: {fields_added}")
    print(f"  Total Fields: {new_field_count}")
    print(f"  Records: {record_count} (empty, ready for ingestion)")
    print(f"{'='*70}")
    print("\nNEXT: Run ingestion scripts to populate the feature class.")

# Execute
try:
    main()
except Exception as e:
    print(f"\nERROR: {str(e)}")
    import traceback
    traceback.print_exc()
