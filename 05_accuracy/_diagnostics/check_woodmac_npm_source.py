"""
Check WoodMac and NPM source data for capacity fields
Diagnose why WoodMac has no capacity in gold_buildings

Author: Meta Data Center GIS Team
Date: December 11, 2024
"""

import arcpy
import os

GDB = r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\Default.gdb"

print("=" * 80)
print("CHECKING SOURCE DATA FOR CAPACITY FIELDS")
print("=" * 80)

# ============================================================================
# WOODMAC SOURCE
# ============================================================================

woodmac_source = os.path.join(GDB, "WoodMac_MetaOracle_Consensus")

if arcpy.Exists(woodmac_source):
    print("\n" + "=" * 40)
    print("WOODMAC SOURCE: WoodMac_MetaOracle_Consensus")
    print("=" * 40)

    # List all fields
    fields = arcpy.ListFields(woodmac_source)
    print(f"\nAll fields ({len(fields)}):")
    for f in fields:
        print(f"  - {f.name} ({f.type})")

    # Check capacity-related fields
    capacity_fields = ['existing_mw', 'new_mw', 'overall_cost_usd_million', 'total_site_acres']

    available = [f.name for f in fields]

    print("\n\nCapacity field values (first 10 records):")
    print("-" * 60)

    read_fields = ['project_name'] + [f for f in capacity_fields if f in available]

    if len(read_fields) > 1:
        with arcpy.da.SearchCursor(woodmac_source, read_fields) as cursor:
            for i, row in enumerate(cursor):
                if i < 10:
                    print(f"\n{row[0]}:")
                    for j, f in enumerate(read_fields[1:], 1):
                        print(f"  {f}: {row[j]}")
    else:
        print("  No capacity fields found in source!")

    # Check if fields exist but have no data
    print("\n\nField value summary:")
    for field in capacity_fields:
        if field in available:
            count = 0
            non_null = 0
            values = []
            with arcpy.da.SearchCursor(woodmac_source, [field]) as cursor:
                for row in cursor:
                    count += 1
                    if row[0] is not None and row[0] != '' and row[0] != 0:
                        non_null += 1
                        values.append(row[0])
            print(f"  {field}: {non_null}/{count} records have data")
            if values:
                print(f"    Sample values: {values[:5]}")
        else:
            print(f"  {field}: FIELD NOT FOUND")
else:
    print(f"\n❌ WoodMac source not found: {woodmac_source}")

# ============================================================================
# NPM SOURCE
# ============================================================================

npm_source = os.path.join(GDB, "NewProjectMedia_MetaOracle_ExportFeatures")

if arcpy.Exists(npm_source):
    print("\n\n" + "=" * 40)
    print("NPM SOURCE: NewProjectMedia_MetaOracle_ExportFeatures")
    print("=" * 40)

    # List fields
    fields = arcpy.ListFields(npm_source)
    capacity_fields_npm = ['total_mws', 'total_it', 'building_size__sq_ft_', 'land_size__acre_', 'cost']
    available = [f.name for f in fields]

    print(f"\nChecking capacity fields:")
    for field in capacity_fields_npm:
        if field in available:
            count = 0
            non_null = 0
            values = []
            with arcpy.da.SearchCursor(npm_source, [field]) as cursor:
                for row in cursor:
                    count += 1
                    if row[0] is not None and str(row[0]).strip() not in ['', '0', 'None']:
                        non_null += 1
                        values.append(row[0])
            print(f"  {field}: {non_null}/{count} records have data")
            if values[:5]:
                print(f"    Sample: {values[:5]}")
        else:
            print(f"  {field}: FIELD NOT FOUND")
            # Check for similar field names
            similar = [f for f in available if field.replace('_', '') in f.lower().replace('_', '')]
            if similar:
                print(f"    Similar fields: {similar}")
else:
    print(f"\n❌ NPM source not found: {npm_source}")

# ============================================================================
# DCM SOURCE
# ============================================================================

dcm_source = os.path.join(GDB, "DCM_MetaOracle_Consensus")

if arcpy.Exists(dcm_source):
    print("\n\n" + "=" * 40)
    print("DCM SOURCE: DCM_MetaOracle_Consensus")
    print("=" * 40)

    fields = arcpy.ListFields(dcm_source)
    capacity_fields_dcm = ['power_mw', 'design_power', 'capacity', 'mw']
    available = [f.name for f in fields]

    print(f"\nAll fields containing 'power', 'capacity', or 'mw':")
    for f in fields:
        if any(x in f.name.lower() for x in ['power', 'capacity', 'mw', 'watt']):
            print(f"  - {f.name} ({f.type})")

    print("\nChecking power_mw field:")
    if 'power_mw' in available:
        count = 0
        non_null = 0
        values = []
        with arcpy.da.SearchCursor(dcm_source, ['power_mw', 'name']) as cursor:
            for row in cursor:
                count += 1
                if row[0] is not None and row[0] > 0:
                    non_null += 1
                    values.append((row[1], row[0]))
        print(f"  power_mw: {non_null}/{count} records have data")
        if values[:5]:
            print(f"  Sample records with data:")
            for name, mw in values[:5]:
                print(f"    {name}: {mw} MW")
else:
    print(f"\n❌ DCM source not found: {dcm_source}")

print("\n" + "=" * 80)
print("DIAGNOSIS COMPLETE")
print("=" * 80)
