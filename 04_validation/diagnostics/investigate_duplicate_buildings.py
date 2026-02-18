"""
INVESTIGATE DUPLICATE BUILDING_KEYS IN SOURCE DATA
===================================================
Check meta_canonical_v2 to understand why dissolve is creating duplicates.

Possible causes:
1. Hidden whitespace/encoding differences in building_key
2. Multiple distinct geometries for same building_key
3. Source data has issues

Author: Meta Data Center GIS Team
Date: December 17, 2024
"""

import arcpy

gdb = r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\Default.gdb"
meta_canonical = f"{gdb}\\meta_canonical_v2"

print("="*70)
print("INVESTIGATE DUPLICATE BUILDING_KEYS IN SOURCE DATA")
print("="*70)

# Known duplicates from validation
duplicate_keys = ["AKN-1", "AKN-2", "CHY-1", "CHY-2", "MAL-1",
                  "MAL-2", "RIN-1", "RIN-2", "RMN-1", "RMN-2"]

print(f"\nInvestigating {len(duplicate_keys)} duplicate building_keys...")
print("-" * 70)

for bkey in duplicate_keys:
    print(f"\n📍 Building Key: {bkey}")

    where = f"building_key = '{bkey}'"
    fields = ["OBJECTID", "building_key", "location_key", "dc_code", "datacenter",
              "SHAPE@XY", "has_coordinates", "it_load", "building_type"]

    records = []
    geometries = set()

    with arcpy.da.SearchCursor(meta_canonical, fields, where) as cursor:
        for row in cursor:
            oid = row[0]
            bk = row[1]
            loc_key = row[2]
            dc = row[3]
            datacenter = row[4]
            shape = row[5]
            has_coords = row[6]
            it_load = row[7]
            btype = row[8]

            # Track unique geometries
            if shape:
                geom_key = (round(shape[0], 6), round(shape[1], 6))
                geometries.add(geom_key)
            else:
                geometries.add(("NULL", "NULL"))

            records.append({
                'oid': oid,
                'location_key': loc_key,
                'shape': shape,
                'has_coords': has_coords,
                'it_load': it_load,
                'btype': btype
            })

    print(f"   Source records: {len(records)}")
    print(f"   Unique geometries: {len(geometries)}")

    # Show geometry details
    print(f"   Geometries: {list(geometries)}")

    # Show first few location_keys
    loc_keys = [r['location_key'] for r in records[:5]]
    print(f"   Sample location_keys: {loc_keys}")

# Now check if the issue is MULTIPART vs multiple point features
print("\n" + "="*70)
print("CHECKING DISSOLVED OUTPUT FOR GEOMETRY ISSUES")
print("="*70)

meta_buildings = f"{gdb}\\meta_canonical_buildings"

for bkey in duplicate_keys[:3]:  # Check first 3
    print(f"\n📍 Building Key in meta_canonical_buildings: {bkey}")

    where = f"building_key = '{bkey}'"
    fields = ["OBJECTID", "building_key", "SHAPE@XY", "SHAPE@"]

    with arcpy.da.SearchCursor(meta_buildings, fields, where) as cursor:
        for row in cursor:
            oid = row[0]
            bk = row[1]
            shape_xy = row[2]
            shape = row[3]

            # Check geometry type
            geom_type = shape.type if shape else "NULL"
            part_count = shape.partCount if shape else 0
            point_count = shape.pointCount if shape else 0

            print(f"   OID={oid}: XY={shape_xy}, Type={geom_type}, "
                  f"Parts={part_count}, Points={point_count}")

print("\n" + "="*70)
print("DIAGNOSIS")
print("="*70)
