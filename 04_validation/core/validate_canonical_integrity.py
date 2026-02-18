"""
Meta Canonical Data Integrity Validation
Verifies that suite-level IT load aggregates correctly to building-level.

Run this in ArcGIS Pro Python window to validate data before capacity accuracy analysis.

Author: Meta Data Center GIS Team
Date: December 10, 2024
"""

import arcpy
import os
from collections import defaultdict

# ============================================================================
# CONFIGURATION
# ============================================================================

GDB = r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\Default.gdb"
META_CANONICAL_V2 = os.path.join(GDB, "meta_canonical_v2")
META_BUILDINGS = os.path.join(GDB, "meta_canonical_buildings")

# ============================================================================
# VALIDATION
# ============================================================================

def validate_canonical_integrity():
    """
    Validate that suite-level IT load sums match building-level totals.
    """

    print("=" * 70)
    print("META CANONICAL DATA INTEGRITY VALIDATION")
    print("Verifying Suite -> Building IT Load Aggregation")
    print("=" * 70)
    print()

    # ========================================================================
    # Step 1: Read suite-level data
    # ========================================================================

    print("[1/4] Reading suite-level data (meta_canonical_v2)...")

    # Check available fields
    suite_fields = [f.name for f in arcpy.ListFields(META_CANONICAL_V2)]
    print(f"   Fields containing 'it' or 'load': ", end="")
    it_fields = [f for f in suite_fields if 'it' in f.lower() or 'load' in f.lower()]
    print(it_fields)

    # Read suites - using actual field names from schema
    suite_it_field = 'it_load'  # Actual field name (was IT_Load_MW)

    suites_by_building = defaultdict(lambda: {'it_load': 0, 'count': 0, 'status': None})
    suite_total = 0
    suite_count = 0

    try:
        with arcpy.da.SearchCursor(META_CANONICAL_V2,
            ['building_key', 'new_build_status', suite_it_field]) as cursor:
            for row in cursor:
                building_key, status, it_load = row

                if it_load:
                    suites_by_building[building_key]['it_load'] += it_load
                    suite_total += it_load
                suites_by_building[building_key]['count'] += 1
                suites_by_building[building_key]['status'] = status
                suite_count += 1
    except Exception as e:
        print(f"   ERROR reading suites: {e}")
        print(f"   Check field name - tried: {suite_it_field}")
        return False

    print(f"   Total suites: {suite_count}")
    print(f"   Unique buildings (from suites): {len(suites_by_building)}")
    print(f"   Total IT Load (suite sum): {suite_total:.2f} MW")

    # ========================================================================
    # Step 2: Read building-level data
    # ========================================================================

    print()
    print("[2/4] Reading building-level data (meta_canonical_buildings)...")

    bldg_fields = [f.name for f in arcpy.ListFields(META_BUILDINGS)]
    print(f"   Fields containing 'it' or 'load': ", end="")
    it_bldg_fields = [f for f in bldg_fields if 'it' in f.lower() or 'load' in f.lower()]
    print(it_bldg_fields)

    bldg_it_field = 'it_load_total'  # Adjust if different

    buildings_data = {}
    bldg_total = 0
    bldg_count = 0

    try:
        with arcpy.da.SearchCursor(META_BUILDINGS,
            ['building_key', 'new_build_status', bldg_it_field, 'suite_count']) as cursor:
            for row in cursor:
                bkey, status, it_load, suite_ct = row
                buildings_data[bkey] = {
                    'it_load': it_load or 0,
                    'status': status,
                    'suite_count': suite_ct or 0
                }
                if it_load:
                    bldg_total += it_load
                bldg_count += 1
    except Exception as e:
        print(f"   ERROR reading buildings: {e}")
        print(f"   Check field name - tried: {bldg_it_field}")
        return False

    print(f"   Total buildings: {bldg_count}")
    print(f"   Total IT Load (building table): {bldg_total:.2f} MW")

    # ========================================================================
    # Step 3: Compare suite aggregation vs building table
    # ========================================================================

    print()
    print("[3/4] Comparing suite aggregations vs building table...")

    mismatches = []
    perfect_matches = 0

    # Check each building
    all_keys = set(suites_by_building.keys()) | set(buildings_data.keys())

    for bkey in all_keys:
        suite_sum = suites_by_building.get(bkey, {}).get('it_load', 0)
        bldg_value = buildings_data.get(bkey, {}).get('it_load', 0)

        diff = abs(suite_sum - bldg_value)

        if diff > 0.01:  # Allow tiny floating point differences
            mismatches.append({
                'building_key': bkey,
                'suite_sum': suite_sum,
                'bldg_value': bldg_value,
                'diff': diff
            })
        else:
            perfect_matches += 1

    print()
    print("   VALIDATION RESULTS:")
    print("   " + "-" * 50)

    if len(mismatches) == 0:
        print("   ✅ PASS: All building IT loads match suite aggregations!")
        print(f"   Perfect matches: {perfect_matches}/{len(all_keys)}")
    else:
        print(f"   ⚠️  MISMATCH: {len(mismatches)} buildings have different values")
        print(f"   Perfect matches: {perfect_matches}/{len(all_keys)}")
        print()
        print("   Sample mismatches (top 10 by difference):")
        mismatches.sort(key=lambda x: -x['diff'])
        for m in mismatches[:10]:
            print(f"      {m['building_key'][:30]}: Suite={m['suite_sum']:.2f}, Bldg={m['bldg_value']:.2f}, Diff={m['diff']:.2f}")

    # ========================================================================
    # Step 4: Validate by build status
    # ========================================================================

    print()
    print("[4/4] Validating by build status...")
    print()
    print("-" * 70)
    print(f"{'Status':<20} {'Suite Sum (MW)':>15} {'Bldg Sum (MW)':>15} {'Diff':>10} {'Check':>8}")
    print("-" * 70)

    status_pass = True

    for status in ['Complete Build', 'Active Build', 'Future Build']:
        # Suite aggregation for this status
        suite_status_sum = sum(
            data['it_load'] for bkey, data in suites_by_building.items()
            if data['status'] == status
        )

        # Building table for this status
        bldg_status_sum = sum(
            data['it_load'] for bkey, data in buildings_data.items()
            if data['status'] == status
        )

        diff = abs(suite_status_sum - bldg_status_sum)
        check = "✅ PASS" if diff < 0.1 else "⚠️ DIFF"

        if diff >= 0.1:
            status_pass = False

        print(f"{status:<20} {suite_status_sum:>15.2f} {bldg_status_sum:>15.2f} {diff:>10.2f} {check:>8}")

    # Totals
    print("-" * 70)
    total_diff = abs(suite_total - bldg_total)
    total_check = "✅ PASS" if total_diff < 0.1 else "⚠️ DIFF"
    print(f"{'TOTAL':<20} {suite_total:>15.2f} {bldg_total:>15.2f} {total_diff:>10.2f} {total_check:>8}")

    # ========================================================================
    # Summary
    # ========================================================================

    print()
    print("=" * 70)
    print("VALIDATION SUMMARY")
    print("=" * 70)

    all_pass = len(mismatches) == 0 and status_pass and total_diff < 0.1

    if all_pass:
        print("✅ ALL CHECKS PASSED")
        print("   Meta canonical data is internally consistent.")
        print("   Suite-level IT load correctly aggregates to building-level.")
        print("   Safe to use for capacity accuracy analysis.")
    else:
        print("⚠️  SOME CHECKS FAILED")
        print("   Review mismatches above before proceeding with analysis.")

    print()
    print("=" * 70)

    return all_pass


# ============================================================================
# EXECUTE
# ============================================================================

if __name__ == "__main__":
    result = validate_canonical_integrity()
    print(f"\nValidation result: {'PASSED' if result else 'NEEDS REVIEW'}")
