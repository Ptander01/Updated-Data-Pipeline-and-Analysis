"""
VERIFY NO DUPLICATE BUILDINGS IN META_CANONICAL_BUILDINGS
==========================================================
Quick validation to ensure dissolve worked correctly and there are
no duplicate building_key values in the output.

Author: Meta Data Center GIS Team
Date: December 17, 2024
"""

import arcpy
from collections import Counter

gdb = r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\Default.gdb"
meta_buildings = f"{gdb}\\meta_canonical_buildings"

print("="*70)
print("VERIFY NO DUPLICATE BUILDINGS")
print("="*70)

# Check if feature class exists
if not arcpy.Exists(meta_buildings):
    print("❌ ERROR: meta_canonical_buildings not found!")
    raise SystemExit

# Count total records
total_count = int(arcpy.management.GetCount(meta_buildings)[0])
print(f"\nTotal records in meta_canonical_buildings: {total_count}")

# Collect all building_key values
building_keys = []
with arcpy.da.SearchCursor(meta_buildings, ["building_key", "OBJECTID"]) as cursor:
    for row in cursor:
        building_keys.append((row[0], row[1]))

# Count occurrences
key_counts = Counter([k[0] for k in building_keys])

# Find duplicates
duplicates = {k: v for k, v in key_counts.items() if v > 1}

print(f"Unique building_key values: {len(key_counts)}")

if duplicates:
    print(f"\n❌ DUPLICATES FOUND: {len(duplicates)} building_keys appear more than once!")
    print("\nDuplicate building_keys:")
    print("-" * 50)

    for bkey, count in sorted(duplicates.items(), key=lambda x: -x[1]):
        print(f"   {bkey}: {count} occurrences")

    # Show details of first 5 duplicates
    print("\nDetails of first 5 duplicates:")
    print("-" * 70)

    dup_keys = list(duplicates.keys())[:5]
    for bkey in dup_keys:
        print(f"\n   Building Key: {bkey}")
        # Get OBJECTIDs for this building_key
        oids = [oid for k, oid in building_keys if k == bkey]

        # Get full record details
        where = f"building_key = '{bkey}'"
        fields = ["OBJECTID", "building_key", "dc_code", "datacenter",
                  "suite_count", "it_load_total", "owned_leased"]

        with arcpy.da.SearchCursor(meta_buildings, fields, where) as cursor:
            for row in cursor:
                oid, bk, dc, datacenter, suites, it_load, owned = row
                it_str = f"{it_load:.1f} MW" if it_load else "N/A"
                print(f"      OID={oid}: dc={dc}, bldg={datacenter}, "
                      f"suites={suites}, IT={it_str}, {owned}")

    print("\n⚠️  ACTION NEEDED: Investigate why dissolve created duplicates")

else:
    print(f"\n✅ NO DUPLICATES! All {len(key_counts)} building_key values are unique.")

# Check for NULL building_key
null_keys = sum(1 for k, _ in building_keys if k is None or k == "" or k == "None")
if null_keys > 0:
    print(f"\n⚠️  {null_keys} records have NULL/empty building_key")

# Summary statistics
print("\n" + "="*70)
print("SUMMARY")
print("="*70)
print(f"   Total records: {total_count}")
print(f"   Unique building_keys: {len(key_counts)}")
print(f"   Duplicates: {len(duplicates)}")
print(f"   NULL building_keys: {null_keys}")

if len(duplicates) == 0 and null_keys == 0:
    print("\n✅ VALIDATION PASSED - No issues found!")
else:
    print("\n❌ VALIDATION FAILED - Issues found above")

print("="*70)
