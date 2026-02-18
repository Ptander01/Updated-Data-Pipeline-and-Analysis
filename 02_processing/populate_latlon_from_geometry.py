"""
Populate Lat/Lon Fields from SHAPE Geometry
Fixes records that have geometry (points on map) but NULL latitude/longitude attribute values.

Applies to both gold_buildings_full and gold_campus_full.

Author: Meta Data Center GIS Team
Last Updated: 2024-12-16
"""

import arcpy
import os
import sys
from datetime import datetime

# Add _utils to path for config import
try:
    script_dir = os.path.dirname(os.path.abspath(__file__))
except NameError:
    script_dir = r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\scripts\02_processing"

utils_dir = os.path.join(os.path.dirname(script_dir), "_utils")
if utils_dir not in sys.path:
    sys.path.insert(0, utils_dir)

from config import GDB, GOLD_BUILDINGS, GOLD_CAMPUS

arcpy.env.workspace = GDB


def populate_latlon(fc_path, fc_name):
    """
    Populate latitude/longitude fields from SHAPE geometry.

    Args:
        fc_path: Path to feature class
        fc_name: Display name for logging

    Returns:
        Number of records updated
    """
    print(f"\n  Processing {fc_name}...")

    # Get available fields
    existing_fields = [f.name for f in arcpy.ListFields(fc_path)]

    # Determine which lat/lon fields exist
    lat_field = 'latitude' if 'latitude' in existing_fields else None
    lon_field = 'longitude' if 'longitude' in existing_fields else None
    gold_lat_field = 'gold_lat' if 'gold_lat' in existing_fields else None
    gold_lon_field = 'gold_lon' if 'gold_lon' in existing_fields else None

    if not lat_field and not gold_lat_field:
        print(f"    ⚠️ No latitude fields found in {fc_name}")
        return 0

    print(f"    Fields found: lat={lat_field}, lon={lon_field}, gold_lat={gold_lat_field}, gold_lon={gold_lon_field}")

    # Build update fields list
    update_fields = ['SHAPE@XY']
    field_indices = {}

    if lat_field:
        update_fields.append(lat_field)
        field_indices['lat'] = len(update_fields) - 1
    if lon_field:
        update_fields.append(lon_field)
        field_indices['lon'] = len(update_fields) - 1
    if gold_lat_field:
        update_fields.append(gold_lat_field)
        field_indices['gold_lat'] = len(update_fields) - 1
    if gold_lon_field:
        update_fields.append(gold_lon_field)
        field_indices['gold_lon'] = len(update_fields) - 1

    updated = 0
    skipped_no_geom = 0
    already_populated = 0

    with arcpy.da.UpdateCursor(fc_path, update_fields) as cursor:
        for row in cursor:
            shape_xy = row[0]

            # Skip if no geometry
            if not shape_xy or shape_xy[0] is None or shape_xy[1] is None:
                skipped_no_geom += 1
                continue

            lon_val = shape_xy[0]
            lat_val = shape_xy[1]

            # Check if any lat/lon fields need updating
            needs_update = False
            row_list = list(row)

            # Update latitude field if NULL
            if 'lat' in field_indices:
                if row[field_indices['lat']] is None:
                    row_list[field_indices['lat']] = lat_val
                    needs_update = True

            # Update longitude field if NULL
            if 'lon' in field_indices:
                if row[field_indices['lon']] is None:
                    row_list[field_indices['lon']] = lon_val
                    needs_update = True

            # Update gold_lat field if NULL
            if 'gold_lat' in field_indices:
                if row[field_indices['gold_lat']] is None:
                    row_list[field_indices['gold_lat']] = lat_val
                    needs_update = True

            # Update gold_lon field if NULL
            if 'gold_lon' in field_indices:
                if row[field_indices['gold_lon']] is None:
                    row_list[field_indices['gold_lon']] = lon_val
                    needs_update = True

            if needs_update:
                cursor.updateRow(row_list)
                updated += 1
            else:
                already_populated += 1

    print(f"    ✅ Updated: {updated} records")
    print(f"    Already populated: {already_populated}")
    if skipped_no_geom > 0:
        print(f"    ⚠️ Skipped (no geometry): {skipped_no_geom}")

    return updated


def main():
    print("=" * 80)
    print("   POPULATE LAT/LON FROM GEOMETRY")
    print("=" * 80)
    print(f"   Started: {datetime.now()}")
    print(f"   GDB: {GDB}")

    total_updated = 0

    # Process gold_buildings
    updated_buildings = populate_latlon(GOLD_BUILDINGS, "gold_buildings_full")
    total_updated += updated_buildings

    # Process gold_campus
    updated_campus = populate_latlon(GOLD_CAMPUS, "gold_campus_full")
    total_updated += updated_campus

    # Summary
    print("\n" + "=" * 80)
    print("   COMPLETE")
    print("=" * 80)
    print(f"   Total records updated: {total_updated}")
    print(f"     gold_buildings: {updated_buildings}")
    print(f"     gold_campus: {updated_campus}")
    print(f"   Completed: {datetime.now()}")
    print("=" * 80)

    return total_updated


# Execute
if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n❌ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()

# Also run when exec()'d
try:
    main()
except Exception as e:
    print(f"\n❌ ERROR: {str(e)}")
    import traceback
    traceback.print_exc()
