"""
Create Filtered Meta Canonical Dataset
======================================

Purpose:
Creates a filtered version of meta_canonical_v2 that excludes placeholder records
(records with NULL status AND no IT load) for use as pipeline input.

Filter Logic:
Include records where: it_load > 0 OR new_build_status IS NOT NULL

This produces a clean dataset with:
- ~1,106 records with valid build status
- ~1,145 records with IT load data
- Combined: records that have EITHER status OR capacity

Output:
- meta_canonical_v2_filtered (Point Feature Class in GDB)

Run in ArcGIS Pro Python window:
exec(open(r"C:\\Users\\ptanderson\\Documents\\ArcGIS\\Projects\\Lean Consensus DC Model\\scripts\\04_validation\\create_filtered_meta_canonical.py", encoding='utf-8').read())

Author: DC GIS Team
Created: January 30, 2026
"""

import arcpy
import os
import sys
from datetime import datetime

# Add _utils to path for config import
try:
    script_dir = os.path.dirname(os.path.abspath(__file__))
except NameError:
    script_dir = r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\scripts\04_validation"

utils_dir = os.path.join(os.path.dirname(script_dir), "_utils")
if utils_dir not in sys.path:
    sys.path.insert(0, utils_dir)

from config import GDB, META_CANONICAL_V2

arcpy.env.workspace = GDB
arcpy.env.overwriteOutput = True

# ============================================================================
# CONFIGURATION
# ============================================================================

# Output feature class name
OUTPUT_FC_NAME = "meta_canonical_v2_filtered"
OUTPUT_FC = os.path.join(GDB, OUTPUT_FC_NAME)

# Filter criteria - include records that have EITHER:
# 1. Valid IT load (> 0), OR
# 2. Valid build status (not null/empty)
FILTER_WHERE_CLAUSE = "(it_load > 0) OR (new_build_status IS NOT NULL AND new_build_status <> '')"

# ============================================================================
# MAIN FUNCTION
# ============================================================================

def create_filtered_dataset():
    """Create filtered meta canonical dataset excluding placeholder records."""

    print("\n")
    print("╔" + "═" * 68 + "╗")
    print("║" + " " * 12 + "CREATE FILTERED META CANONICAL DATASET" + " " * 12 + "║")
    print("╚" + "═" * 68 + "╝")
    print(f"\n   Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # ========================================================================
    # Step 1: Validate source exists
    # ========================================================================

    print("\n" + "=" * 70)
    print("   1. VALIDATING SOURCE DATA")
    print("=" * 70)

    if not arcpy.Exists(META_CANONICAL_V2):
        print(f"   ❌ Source not found: {META_CANONICAL_V2}")
        return False

    source_count = int(arcpy.management.GetCount(META_CANONICAL_V2)[0])
    print(f"   Source: {META_CANONICAL_V2}")
    print(f"   Total records: {source_count:,}")

    # ========================================================================
    # Step 2: Analyze what will be filtered
    # ========================================================================

    print("\n" + "=" * 70)
    print("   2. ANALYZING FILTER CRITERIA")
    print("=" * 70)

    print(f"\n   Filter: {FILTER_WHERE_CLAUSE}")

    # Count records matching filter
    with arcpy.da.SearchCursor(META_CANONICAL_V2, ['OBJECTID', 'it_load', 'new_build_status', 'SHAPE@XY']) as cursor:
        total = 0
        included = 0
        excluded = 0

        # Detailed counts
        has_load_only = 0
        has_status_only = 0
        has_both = 0
        has_neither = 0

        included_capacity = 0
        excluded_capacity = 0

        for row in cursor:
            oid, it_load, status, shape_xy = row
            total += 1

            has_load = it_load is not None and it_load > 0
            has_status = status is not None and str(status).strip() != ''

            if has_load or has_status:
                included += 1
                if has_load:
                    included_capacity += it_load

                if has_load and has_status:
                    has_both += 1
                elif has_load:
                    has_load_only += 1
                else:
                    has_status_only += 1
            else:
                excluded += 1
                has_neither += 1

    print(f"\n   {'─' * 66}")
    print(f"   FILTER BREAKDOWN")
    print(f"   {'─' * 66}")
    print(f"   {'Records with both status AND load':<40} {has_both:>12,}")
    print(f"   {'Records with load only (no status)':<40} {has_load_only:>12,}")
    print(f"   {'Records with status only (no load)':<40} {has_status_only:>12,}")
    print(f"   {'─' * 66}")
    print(f"   {'TOTAL TO INCLUDE':<40} {included:>12,} ({included/total*100:.1f}%)")
    print(f"   {'─' * 66}")
    print(f"   {'Records with neither (EXCLUDED)':<40} {excluded:>12,} ({excluded/total*100:.1f}%)")

    print(f"\n   {'─' * 66}")
    print(f"   CAPACITY SUMMARY")
    print(f"   {'─' * 66}")
    print(f"   {'Capacity in filtered dataset':<40} {included_capacity:>12,.1f} MW")
    print(f"   {'Capacity excluded (no load value)':<40} {'0.0':>12} MW")

    # ========================================================================
    # Step 3: Create filtered feature class
    # ========================================================================

    print("\n" + "=" * 70)
    print("   3. CREATING FILTERED FEATURE CLASS")
    print("=" * 70)

    # Delete existing if present
    if arcpy.Exists(OUTPUT_FC):
        print(f"   Deleting existing: {OUTPUT_FC_NAME}")
        arcpy.management.Delete(OUTPUT_FC)

    # Create feature layer with filter
    print(f"   Applying filter...")
    temp_layer = "meta_canonical_filtered_layer"
    arcpy.management.MakeFeatureLayer(META_CANONICAL_V2, temp_layer, FILTER_WHERE_CLAUSE)

    # Get count from layer
    layer_count = int(arcpy.management.GetCount(temp_layer)[0])
    print(f"   Records matching filter: {layer_count:,}")

    # Copy to new feature class
    print(f"   Creating: {OUTPUT_FC_NAME}")
    arcpy.management.CopyFeatures(temp_layer, OUTPUT_FC)

    # Clean up temp layer
    arcpy.management.Delete(temp_layer)

    # Verify output
    output_count = int(arcpy.management.GetCount(OUTPUT_FC)[0])
    print(f"   ✅ Created: {output_count:,} records")

    # ========================================================================
    # Step 4: Validate output
    # ========================================================================

    print("\n" + "=" * 70)
    print("   4. VALIDATING OUTPUT")
    print("=" * 70)

    # Analyze output dataset
    status_counts = {}
    total_capacity = 0
    with_coords = 0

    with arcpy.da.SearchCursor(OUTPUT_FC, ['new_build_status', 'it_load', 'SHAPE@XY']) as cursor:
        for row in cursor:
            status, it_load, shape_xy = row

            # Status
            status_key = status if status else 'NULL/Empty'
            status_counts[status_key] = status_counts.get(status_key, 0) + 1

            # Capacity
            if it_load:
                total_capacity += it_load

            # Coordinates
            if shape_xy and shape_xy[0] and shape_xy[1]:
                lon, lat = shape_xy
                if abs(lat) > 0.01 and abs(lon) > 0.01:
                    with_coords += 1

    print(f"\n   {'─' * 66}")
    print(f"   STATUS DISTRIBUTION (Filtered)")
    print(f"   {'─' * 66}")
    print(f"   {'Status':<30} {'Count':>12} {'Percentage':>12}")
    print(f"   {'─' * 66}")

    for status in ['Complete Build', 'Active Build', 'Future Build', 'NULL/Empty']:
        count = status_counts.get(status, 0)
        pct = (count / output_count * 100) if output_count > 0 else 0
        print(f"   {status:<30} {count:>12,} {pct:>11.1f}%")

    print(f"\n   {'─' * 66}")
    print(f"   QUALITY METRICS (Filtered)")
    print(f"   {'─' * 66}")
    print(f"   {'Total capacity':<40} {total_capacity:>12,.1f} MW")
    print(f"   {'Records with coordinates':<40} {with_coords:>12,} ({with_coords/output_count*100:.1f}%)")

    # ========================================================================
    # Step 5: Summary
    # ========================================================================

    print("\n" + "=" * 70)
    print("   SUMMARY")
    print("=" * 70)

    print(f"\n   ┌{'─' * 66}┐")
    print(f"   │ {'INPUT':<30} {'OUTPUT':<33} │")
    print(f"   ├{'─' * 66}┤")
    print(f"   │ {source_count:,} records{' ' * (22 - len(f'{source_count:,}'))} {output_count:,} records ({output_count/source_count*100:.0f}% retained){' ' * 5} │")
    print(f"   │ meta_canonical_v2{' ' * 13} {OUTPUT_FC_NAME}{' ' * (33 - len(OUTPUT_FC_NAME))} │")
    print(f"   └{'─' * 66}┘")

    print(f"\n   ✅ Filtered dataset ready for pipeline input")
    print(f"   📍 Location: {OUTPUT_FC}")

    # Recommendation
    print(f"\n   {'─' * 66}")
    print(f"   NEXT STEPS")
    print(f"   {'─' * 66}")
    print(f"   1. Update pipeline config to use: {OUTPUT_FC_NAME}")
    print(f"   2. Or create view in config.py:")
    print(f"      META_CANONICAL_FILTERED = os.path.join(GDB, '{OUTPUT_FC_NAME}')")
    print(f"   3. Run pipeline with filtered dataset")

    print(f"\n   Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

    return True


# ============================================================================
# EXECUTE
# ============================================================================

if __name__ == "__main__":
    success = create_filtered_dataset()
    print(f"\nResult: {'SUCCESS' if success else 'FAILED'}")
else:
    success = create_filtered_dataset()
