"""
Hypothesis Test: Semianalysis Aggregated vs DCH Campus
Which is more accurate for campus-level capacity estimation?

Author: Data Center GIS Team
Date: December 11, 2024
"""

import arcpy
import numpy as np
from collections import defaultdict

GDB = r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\Default.gdb"


def main():
    print("=" * 70)
    print("HYPOTHESIS TEST: Semianalysis Aggregated vs DCH Campus")
    print("Which is more accurate for campus-level capacity?")
    print("=" * 70)
    print()

    # 1. Get Meta campus totals (ground truth)
    print("[1] META CAMPUS TOTALS")
    print("-" * 60)

    meta_campus = {}
    with arcpy.da.SearchCursor(
        GDB + "/meta_canonical_buildings",
        ["dc_code", "it_load_total", "new_build_status"]
    ) as cursor:
        for dc_code, it_load, status in cursor:
            if dc_code not in meta_campus:
                meta_campus[dc_code] = {"it_load": 0, "status": status, "bldg_count": 0}
            meta_campus[dc_code]["it_load"] += (it_load or 0)
            meta_campus[dc_code]["bldg_count"] += 1

    total_meta_it = sum(c["it_load"] for c in meta_campus.values())
    print(f"Meta campuses: {len(meta_campus)}")
    print(f"Total Meta IT load: {total_meta_it:.0f} MW")

    # 2. Get Semianalysis by campus (aggregated from buildings)
    print()
    print("[2] SEMIANALYSIS AGGREGATED TO CAMPUS")
    print("-" * 60)

    # First, get the spatial matches for Semianalysis, dedupe to closest per building
    bldg_matches = {}

    with arcpy.da.SearchCursor(
        GDB + "/accuracy_analysis_multi_source_REBUILT",
        ["dc_code", "building_key", "source", "mw_2023", "distance_m"],
        "source = 'Semianalysis'"
    ) as cursor:
        for dc_code, bkey, source, mw_2023, dist in cursor:
            dist_val = dist if dist else 999999
            if bkey not in bldg_matches or dist_val < bldg_matches[bkey]["dist"]:
                bldg_matches[bkey] = {
                    "dc_code": dc_code,
                    "mw_2023": mw_2023 or 0,
                    "dist": dist_val
                }

    # Now aggregate to campus
    semi_by_meta_campus = defaultdict(lambda: {"capacity": 0, "bldg_count": 0})
    for bkey, data in bldg_matches.items():
        dc_code = data["dc_code"]
        semi_by_meta_campus[dc_code]["capacity"] += data["mw_2023"]
        semi_by_meta_campus[dc_code]["bldg_count"] += 1

    print(f"Meta campuses with Semianalysis matches: {len(semi_by_meta_campus)}")

    # 3. Get DCH by campus (direct campus-level)
    print()
    print("[3] DCH CAMPUS-LEVEL (DIRECT)")
    print("-" * 60)

    dch_by_meta_campus = {}

    with arcpy.da.SearchCursor(
        GDB + "/accuracy_analysis_multi_source_REBUILT",
        ["dc_code", "source", "commissioned_power_mw"],
        "source = 'DataCenterHawk'"
    ) as cursor:
        # DCH is already campus level, just take first match per dc_code
        for dc_code, source, capacity in cursor:
            if dc_code not in dch_by_meta_campus:
                # Apply PUE adjustment (facility power -> IT load)
                dch_by_meta_campus[dc_code] = {
                    "capacity": (capacity or 0) / 1.3,
                    "raw_capacity": capacity or 0
                }

    print(f"Meta campuses with DCH matches: {len(dch_by_meta_campus)}")

    # 4. Compare accuracy
    print()
    print("[4] CAMPUS-LEVEL ACCURACY COMPARISON")
    print("-" * 60)

    # Find campuses with both Semi and DCH matches
    common_campuses = (
        set(semi_by_meta_campus.keys()) &
        set(dch_by_meta_campus.keys()) &
        set(meta_campus.keys())
    )
    print(f"Campuses with both Semi and DCH matches: {len(common_campuses)}")

    # Calculate MAPE for each
    semi_errors = []
    dch_errors = []
    comparison_details = []

    for dc_code in common_campuses:
        meta_it = meta_campus[dc_code]["it_load"]
        if meta_it > 0:
            semi_cap = semi_by_meta_campus[dc_code]["capacity"]
            dch_cap = dch_by_meta_campus[dc_code]["capacity"]

            semi_error = abs(semi_cap - meta_it) / meta_it
            dch_error = abs(dch_cap - meta_it) / meta_it

            semi_errors.append(semi_error)
            dch_errors.append(dch_error)

            comparison_details.append({
                "dc_code": dc_code,
                "meta_it": meta_it,
                "semi_cap": semi_cap,
                "dch_cap": dch_cap,
                "semi_error": semi_error * 100,
                "dch_error": dch_error * 100
            })

    semi_mape = np.mean(semi_errors) * 100 if semi_errors else 0
    dch_mape = np.mean(dch_errors) * 100 if dch_errors else 0

    print()
    print("RESULTS (campuses with both sources):")
    print(f"  Semianalysis (aggregated): {semi_mape:.1f}% MAPE (n={len(semi_errors)})")
    print(f"  DataCenterHawk (direct):   {dch_mape:.1f}% MAPE (n={len(dch_errors)})")
    print()

    if semi_mape < dch_mape:
        improvement = ((dch_mape - semi_mape) / dch_mape) * 100
        print(f">>> SEMIANALYSIS AGGREGATED IS BETTER!")
        print(f">>> {improvement:.0f}% more accurate than DCH at campus level")
    else:
        improvement = ((semi_mape - dch_mape) / semi_mape) * 100
        print(f">>> DCH is better for campus-level")
        print(f">>> {improvement:.0f}% more accurate than Semianalysis aggregated")

    # 5. All Semianalysis campuses (not just common)
    print()
    print("[5] SEMIANALYSIS CAMPUS ACCURACY (ALL MATCHES)")
    print("-" * 60)

    semi_all_errors = []
    for dc_code in semi_by_meta_campus.keys():
        if dc_code in meta_campus:
            meta_it = meta_campus[dc_code]["it_load"]
            if meta_it > 0:
                semi_cap = semi_by_meta_campus[dc_code]["capacity"]
                semi_error = abs(semi_cap - meta_it) / meta_it
                semi_all_errors.append(semi_error)

    semi_all_mape = np.mean(semi_all_errors) * 100 if semi_all_errors else 0
    print(f"Semianalysis aggregated (all matches): {semi_all_mape:.1f}% MAPE (n={len(semi_all_errors)})")

    # 6. Sample comparisons
    print()
    print("[6] SAMPLE CAMPUS COMPARISONS")
    print("-" * 60)
    print(f"{'Campus':<12} {'Meta IT':>10} {'Semi Agg':>10} {'DCH':>10} {'Semi Err':>10} {'DCH Err':>10}")
    print("-" * 62)

    # Sort by Meta IT load (largest first)
    sorted_details = sorted(comparison_details, key=lambda x: -x["meta_it"])
    for d in sorted_details[:10]:
        print(f"{d['dc_code']:<12} {d['meta_it']:>10.1f} {d['semi_cap']:>10.1f} {d['dch_cap']:>10.1f} {d['semi_error']:>9.1f}% {d['dch_error']:>9.1f}%")

    print()
    print("=" * 70)
    print("CONCLUSION")
    print("=" * 70)
    if semi_mape < dch_mape:
        print("Semianalysis aggregated to campus level IS more accurate than DCH.")
        print(f"Recommendation: Use Semianalysis for BOTH building and campus analysis.")
    else:
        print("DCH is more accurate at campus level despite being less granular.")
        print("Recommendation: Use Semianalysis for buildings, DCH for campuses.")


if __name__ == "__main__":
    main()
