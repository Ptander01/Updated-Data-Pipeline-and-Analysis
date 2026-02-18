"""
Meta Canonical Schema Diagnostic
================================
Quick diagnostic to identify field names and sample values in meta_canonical_v2.
Run this to understand why coordinates show 0% coverage.

Run in ArcGIS Pro Python window:
exec(open(r"C:\\Users\\ptanderson\\Documents\\ArcGIS\\Projects\\Lean Consensus DC Model\\scripts\\04_validation\\diagnose_meta_canonical_schema.py", encoding='utf-8').read())
"""

import arcpy
import os

GDB = r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\Default.gdb"
META_CANONICAL_V2 = os.path.join(GDB, "meta_canonical_v2")

def diagnose_schema():
    print("\n" + "=" * 70)
    print("   META CANONICAL V2 - SCHEMA DIAGNOSTIC")
    print("=" * 70)

    if not arcpy.Exists(META_CANONICAL_V2):
        print(f"   ❌ Table not found: {META_CANONICAL_V2}")
        return

    # Get all fields
    fields = arcpy.ListFields(META_CANONICAL_V2)

    print(f"\n   Total Fields: {len(fields)}")
    print("\n   " + "-" * 66)
    print(f"   {'Field Name':<30} {'Type':<15} {'Length':<10}")
    print("   " + "-" * 66)

    coord_candidates = []
    for f in fields:
        # Highlight potential coordinate fields
        name_lower = f.name.lower()
        is_coord = any(x in name_lower for x in ['lat', 'lon', 'x', 'y', 'coord', 'geom'])
        marker = " 📍" if is_coord else ""

        if is_coord:
            coord_candidates.append(f.name)

        print(f"   {f.name:<30} {f.type:<15} {str(f.length):<10}{marker}")

    # Check for Shape field (geometry)
    print("\n   " + "-" * 66)
    print("   COORDINATE FIELD CANDIDATES")
    print("   " + "-" * 66)

    if coord_candidates:
        for field in coord_candidates:
            print(f"   📍 {field}")
    else:
        print("   ⚠️  No obvious coordinate fields found!")

    # Sample values from coordinate-like fields
    print("\n   " + "-" * 66)
    print("   SAMPLE VALUES (first 10 records)")
    print("   " + "-" * 66)

    # Get fields that might contain coordinates
    sample_fields = ['OBJECTID']
    for f in fields:
        name_lower = f.name.lower()
        if any(x in name_lower for x in ['lat', 'lon', 'x', 'y', 'location', 'address', 'key', 'code', 'status', 'load']):
            if f.name not in sample_fields:
                sample_fields.append(f.name)

    # Limit to 10 fields for readability
    sample_fields = sample_fields[:10]

    print(f"\n   Sampling fields: {sample_fields}")
    print()

    with arcpy.da.SearchCursor(META_CANONICAL_V2, sample_fields) as cursor:
        row_count = 0
        for row in cursor:
            if row_count < 10:
                print(f"   Row {row_count + 1}: {row}")
                row_count += 1
            else:
                break

    # Check if it's a feature class with geometry
    print("\n   " + "-" * 66)
    print("   GEOMETRY CHECK")
    print("   " + "-" * 66)

    desc = arcpy.Describe(META_CANONICAL_V2)

    if hasattr(desc, 'shapeType'):
        print(f"   Shape Type: {desc.shapeType}")
        print(f"   Has M: {desc.hasM}")
        print(f"   Has Z: {desc.hasZ}")

        # Sample geometry
        print("\n   First 5 geometries:")
        with arcpy.da.SearchCursor(META_CANONICAL_V2, ['SHAPE@XY', 'OBJECTID']) as cursor:
            count = 0
            null_geom = 0
            valid_geom = 0
            for row in cursor:
                xy, oid = row
                if count < 5:
                    print(f"   OID {oid}: {xy}")
                if xy and xy[0] and xy[1]:
                    valid_geom += 1
                else:
                    null_geom += 1
                count += 1

        print(f"\n   Total records: {count}")
        print(f"   With valid geometry: {valid_geom}")
        print(f"   With null/empty geometry: {null_geom}")
    else:
        print("   ⚠️  This is a TABLE, not a Feature Class (no geometry)")
        print("   Coordinates may be stored as attribute fields only.")

    # Check for lat/lon attribute values
    print("\n   " + "-" * 66)
    print("   CHECKING LAT/LON ATTRIBUTE FIELDS")
    print("   " + "-" * 66)

    lat_field = None
    lon_field = None

    for f in fields:
        name_lower = f.name.lower()
        if 'lat' in name_lower and not lat_field:
            lat_field = f.name
        if 'lon' in name_lower and not lon_field:
            lon_field = f.name

    if lat_field and lon_field:
        print(f"   Found: {lat_field}, {lon_field}")

        # Count valid vs invalid coordinates
        valid = 0
        null_coords = 0
        zero_coords = 0
        total = 0

        with arcpy.da.SearchCursor(META_CANONICAL_V2, [lat_field, lon_field]) as cursor:
            for row in cursor:
                lat, lon = row
                total += 1

                if lat is None or lon is None:
                    null_coords += 1
                elif lat == 0 and lon == 0:
                    zero_coords += 1
                elif abs(lat) < 0.01 and abs(lon) < 0.01:
                    zero_coords += 1
                else:
                    valid += 1

        print(f"\n   Total records: {total}")
        print(f"   With valid lat/lon: {valid} ({valid/total*100:.1f}%)")
        print(f"   With NULL lat/lon: {null_coords} ({null_coords/total*100:.1f}%)")
        print(f"   With 0,0 lat/lon: {zero_coords} ({zero_coords/total*100:.1f}%)")

        # Sample some valid coordinates
        print("\n   Sample valid coordinates:")
        with arcpy.da.SearchCursor(META_CANONICAL_V2, ['OBJECTID', lat_field, lon_field]) as cursor:
            count = 0
            for row in cursor:
                oid, lat, lon = row
                if lat and lon and abs(lat) > 0.01 and abs(lon) > 0.01:
                    print(f"   OID {oid}: ({lat}, {lon})")
                    count += 1
                    if count >= 5:
                        break
    else:
        print(f"   ⚠️  Could not find lat/lon fields")
        print(f"   Searched for fields containing 'lat' or 'lon'")

    print("\n" + "=" * 70)

# Run diagnostic
diagnose_schema()
