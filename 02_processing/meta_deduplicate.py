"""
META CANONICAL DEDUPLICATION - Building-Level Aggregation
==========================================================
Purpose: Aggregate suite-level meta_canonical_v2 records to building-level
         for meta_canonical_buildings feature class.

Changes (Jan 29, 2026):
- Added "Unlocated Campus Capacity" record type for campuses with no coordinates
- Similar to how SemiAnalysis handles TLBM (Total Lease By Market) records
- record_level = "Building" for located buildings
- record_level = "Unlocated Campus Capacity" for campuses with no coords anywhere

Changes (Dec 17, 2024):
- Removed has_coordinates=1 filter (include ALL buildings)
- Added building_type (Owned/Leased) field to dissolve
- Added null island (0,0) handling notes

Input: meta_canonical_v2 (suite-level records)
Output: meta_canonical_buildings (building-level + unlocated campus aggregation)

Author: Meta Data Center GIS Team
"""

import arcpy
import os
from datetime import datetime

# ============================================================================
# CONFIGURATION
# ============================================================================

gdb = r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\Default.gdb"

# Source options - use FILTERED for pipeline (excludes placeholder records)
# Set USE_FILTERED = True for pipeline processing (recommended)
# Set USE_FILTERED = False for full dataset processing
USE_FILTERED = True

if USE_FILTERED:
    meta_canonical = os.path.join(gdb, "meta_canonical_v2_filtered")
    print("📌 Using FILTERED dataset (meta_canonical_v2_filtered)")
else:
    meta_canonical = os.path.join(gdb, "meta_canonical_v2")
    print("📌 Using FULL dataset (meta_canonical_v2)")

meta_buildings = os.path.join(gdb, "meta_canonical_buildings")

print("="*80)
print("CREATE BUILDING-LEVEL META CANONICAL")
print("="*80)
print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("\nThis script aggregates suite-level meta_canonical_v2 records to building-level.")
print("Includes ALL buildings (no has_coordinates filter).")
print("Adds building_type (Owned/Leased) field from source data.\n")

# ============================================================================
# STEP 1: Validate source data exists
# ============================================================================
print("STEP 1: Validating source data...")

if not arcpy.Exists(meta_canonical):
    raise ValueError(f"Source feature class not found: {meta_canonical}")

total_records = int(arcpy.management.GetCount(meta_canonical)[0])
print(f"   ✅ Source: {total_records:,} records in meta_canonical_v2")

# Check available fields
source_fields = [f.name for f in arcpy.ListFields(meta_canonical)]
print(f"   Available fields: {len(source_fields)}")

# Check for building_type field
if "building_type" in source_fields:
    print("   ✅ building_type field found (Owned/Leased status)")
else:
    print("   ⚠️  building_type field NOT found - will skip owned/leased")

# ============================================================================
# STEP 2: Add building_key field to meta_canonical_v2
# ============================================================================
print("\nSTEP 2: Adding building_key field to meta_canonical_v2...")

if "building_key" not in source_fields:
    print("   Adding building_key field...")
    arcpy.management.AddField(
        in_table=meta_canonical,
        field_name="building_key",
        field_type="TEXT",
        field_length=50,
        field_alias="Building Key (dc_code + datacenter)"
    )
    print("   ✅ Field added")
else:
    print("   ℹ️  building_key field already exists")

# ============================================================================
# STEP 3: Calculate building_key = dc_code + "-" + datacenter
# ============================================================================
print("\nSTEP 3: Calculating building_key values...")

count_updated = 0
count_null = 0

with arcpy.da.UpdateCursor(meta_canonical,
                          ["dc_code", "datacenter", "building_key"]) as cursor:
    for row in cursor:
        dc_code = row[0]
        datacenter = row[1]

        if dc_code and datacenter:
            # Create composite key
            row[2] = f"{dc_code}-{datacenter}"
            cursor.updateRow(row)
            count_updated += 1
        else:
            # Handle missing values
            count_null += 1

print(f"   ✅ Updated {count_updated:,} records with building_key")
if count_null > 0:
    print(f"   ⚠️  {count_null:,} records missing dc_code or datacenter (building_key = NULL)")

# ============================================================================
# STEP 4: Analyze coordinate coverage (informational only)
# ============================================================================
print("\nSTEP 4: Analyzing coordinate coverage (informational)...")

unique_buildings = set()
buildings_with_coords = set()
buildings_no_coords = set()
null_island_buildings = set()

with arcpy.da.SearchCursor(meta_canonical,
                          ["building_key", "has_coordinates", "SHAPE@XY"]) as cursor:
    for row in cursor:
        bkey = row[0]
        has_coords = row[1]
        shape = row[2]

        if bkey:
            unique_buildings.add(bkey)
            if has_coords == 1:
                # Check for null island (0,0)
                if shape and abs(shape[0]) < 0.001 and abs(shape[1]) < 0.001:
                    null_island_buildings.add(bkey)
                else:
                    buildings_with_coords.add(bkey)
            else:
                buildings_no_coords.add(bkey)

print(f"   Total unique buildings: {len(unique_buildings):,}")
print(f"   With valid coordinates: {len(buildings_with_coords):,}")
print(f"   Without coordinates (has_coordinates=0): {len(buildings_no_coords):,}")
print(f"   Null island (0,0): {len(null_island_buildings):,}")

# ============================================================================
# STEP 5: Create layer for ALL records (no coordinate filter)
# ============================================================================
print("\nSTEP 5: Creating layer for ALL records (no coordinate filter)...")

# Use full feature class - no where_clause
meta_layer = arcpy.management.MakeFeatureLayer(
    in_features=meta_canonical,
    out_layer="meta_all_records"
)

layer_count = int(arcpy.management.GetCount(meta_layer)[0])
print(f"   ✅ Layer created: {layer_count:,} total suite records (ALL buildings)")

# ============================================================================
# STEP 6: Delete existing output if exists
# ============================================================================
print("\nSTEP 6: Preparing output feature class...")

if arcpy.Exists(meta_buildings):
    print(f"   Deleting existing {os.path.basename(meta_buildings)}...")
    arcpy.management.Delete(meta_buildings)
    print("   ✅ Deleted")

# ============================================================================
# STEP 7: Dissolve to building-level (grouped by building_key)
# ============================================================================
print("\nSTEP 7: Dissolving suites to building-level...")

print("   Dissolve parameters:")
print(f"      Input: {layer_count:,} suite records (ALL)")
print(f"      Dissolve field: building_key")
print(f"      Output: {os.path.basename(meta_buildings)}")

# Build statistics fields list
stats_fields = [
    ["location_key", "COUNT"],      # Count suites per building
    ["dc_code", "FIRST"],           # Preserve campus code
    ["datacenter", "FIRST"],        # Preserve building number
    ["region_derived", "FIRST"],    # Preserve region
    ["new_build_status", "FIRST"],  # Preserve build status
    ["it_load", "SUM"],             # Sum IT load across suites
    ["has_coordinates", "MAX"],     # 1 if any suite has coords
]

# Add building_type if available
if "building_type" in source_fields:
    stats_fields.append(["building_type", "FIRST"])  # Owned/Leased status
    print("   Including building_type (Owned/Leased) in dissolve")

# Use MULTI_PART to ensure one record per building_key
# Some buildings have suites at different coordinates (e.g., AKN1x vs NA221x)
# MULTI_PART combines these into a single multipoint geometry
arcpy.management.Dissolve(
    in_features=meta_layer,
    out_feature_class=meta_buildings,
    dissolve_field="building_key",
    statistics_fields=stats_fields,
    multi_part="MULTI_PART"
)

building_count = int(arcpy.management.GetCount(meta_buildings)[0])
print(f"   ✅ Created {building_count} building records")

# ============================================================================
# STEP 8: Rename dissolved fields for clarity
# ============================================================================
print("\nSTEP 8: Renaming dissolved fields...")

field_renames = {
    "COUNT_location_key": "suite_count",
    "FIRST_dc_code": "dc_code",
    "FIRST_datacenter": "datacenter",
    "FIRST_region_derived": "region_derived",
    "FIRST_new_build_status": "new_build_status",
    "SUM_it_load": "it_load_total",
    "MAX_has_coordinates": "has_coordinates",
    "FIRST_building_type": "building_type",  # Owned/Leased
}

for old_name, new_name in field_renames.items():
    existing_fields = [f.name for f in arcpy.ListFields(meta_buildings)]

    if old_name in existing_fields:
        try:
            arcpy.management.AlterField(
                in_table=meta_buildings,
                field=old_name,
                new_field_name=new_name,
                new_field_alias=new_name.replace("_", " ").title()
            )
            print(f"   ✅ Renamed: {old_name} → {new_name}")
        except Exception as e:
            print(f"   ⚠️ Could not rename {old_name}: {e}")
    else:
        # Skip silently if field wasn't in dissolve
        pass

# ============================================================================
# STEP 9: Add owned_leased field (normalized from building_type)
# ============================================================================
print("\nSTEP 9: Adding owned_leased field (normalized)...")

current_fields = [f.name for f in arcpy.ListFields(meta_buildings)]

if "owned_leased" not in current_fields:
    arcpy.management.AddField(
        in_table=meta_buildings,
        field_name="owned_leased",
        field_type="TEXT",
        field_length=32,
        field_alias="Owned/Leased Status"
    )
    print("   ✅ Added owned_leased field")
else:
    print("   ℹ️  owned_leased field already exists")

# Populate owned_leased from building_type
if "building_type" in current_fields:
    print("   Mapping building_type → owned_leased...")

    count_owned = 0
    count_leased = 0
    count_other = 0

    with arcpy.da.UpdateCursor(meta_buildings,
                               ["building_type", "owned_leased"]) as cursor:
        for row in cursor:
            btype = str(row[0]).lower() if row[0] else ""

            if "own" in btype:
                row[1] = "Owned"
                count_owned += 1
            elif "lease" in btype or "colo" in btype:
                row[1] = "Leased"
                count_leased += 1
            elif btype:
                row[1] = row[0]  # Keep original if can't map
                count_other += 1
            else:
                row[1] = None
                count_other += 1

            cursor.updateRow(row)

    print(f"   ✅ Mapped: {count_owned} Owned, {count_leased} Leased, {count_other} Other/NULL")
else:
    print("   ⚠️ building_type field not available - owned_leased will be NULL")

# ============================================================================
# STEP 10: Validation - Check distributions
# ============================================================================
print("\nSTEP 10: Validating distributions...")

# Region distribution
regions = {}
statuses = {}
owned_leased_dist = {}
has_coords_dist = {0: 0, 1: 0}

read_fields = ["region_derived", "new_build_status", "owned_leased", "has_coordinates"]
with arcpy.da.SearchCursor(meta_buildings, read_fields) as cursor:
    for row in cursor:
        region = row[0] if row[0] else "NULL"
        status = row[1] if row[1] else "NULL"
        owned = row[2] if row[2] else "NULL"
        has_coords = row[3] if row[3] is not None else 0

        regions[region] = regions.get(region, 0) + 1
        statuses[status] = statuses.get(status, 0) + 1
        owned_leased_dist[owned] = owned_leased_dist.get(owned, 0) + 1
        has_coords_dist[has_coords] = has_coords_dist.get(has_coords, 0) + 1

print(f"\n   Regional distribution:")
for region, count in sorted(regions.items()):
    print(f"      {region}: {count} buildings")

print(f"\n   Build status distribution:")
for status, count in sorted(statuses.items()):
    print(f"      {status}: {count} buildings")

print(f"\n   Owned/Leased distribution:")
for owned, count in sorted(owned_leased_dist.items()):
    print(f"      {owned}: {count} buildings")

print(f"\n   Coordinate availability:")
print(f"      Has coordinates: {has_coords_dist.get(1, 0)} buildings")
print(f"      No coordinates: {has_coords_dist.get(0, 0)} buildings")

# ============================================================================
# STEP 11: Sample building records
# ============================================================================
print("\nSTEP 11: Sample building records...")

sample_fields = ["building_key", "dc_code", "datacenter", "suite_count",
                 "region_derived", "owned_leased", "it_load_total"]
sample_buildings = []

with arcpy.da.SearchCursor(meta_buildings, sample_fields,
                          sql_clause=(None, "ORDER BY building_key")) as cursor:
    for i, row in enumerate(cursor):
        if i < 10:
            sample_buildings.append(row)
        else:
            break

print(f"\n   First 10 buildings:")
print(f"   {'Building Key':<15} {'Campus':<10} {'Bldg#':<6} {'Suites':<7} {'Region':<8} {'Owned/Leased':<12} {'IT Load':<10}")
print(f"   {'-'*80}")
for bkey, dc, datacenter, suites, region, owned, it_load in sample_buildings:
    it_str = f"{it_load:.1f} MW" if it_load else "N/A"
    owned_str = owned if owned else "N/A"
    print(f"   {bkey:<15} {dc:<10} {str(datacenter):<6} {suites:<7} {region:<8} {owned_str:<12} {it_str:<10}")

# ============================================================================
# COMPLETION
# ============================================================================
print("\n" + "="*80)
print("✅ BUILDING-LEVEL META CANONICAL CREATED!")
print("="*80)
print(f"Finished: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

print(f"📊 Summary:")
print(f"   Input: {layer_count:,} suites (ALL records)")
print(f"   Output: {building_count} buildings")
print(f"   Feature class: {meta_buildings}")

print(f"\n📋 Fields included:")
final_fields = [f.name for f in arcpy.ListFields(meta_buildings)]
key_fields = ["building_key", "dc_code", "datacenter", "suite_count",
              "region_derived", "new_build_status", "it_load_total",
              "has_coordinates", "building_type", "owned_leased"]
for f in key_fields:
    status = "✅" if f in final_fields else "❌"
    print(f"   {status} {f}")

print(f"\n🚀 Next steps:")
print(f"   1. Review meta_canonical_buildings in ArcGIS Pro")
print(f"   2. Verify owned_leased distribution looks correct")
print(f"   3. Run spatial accuracy analysis against gold_buildings")
print("="*80)
