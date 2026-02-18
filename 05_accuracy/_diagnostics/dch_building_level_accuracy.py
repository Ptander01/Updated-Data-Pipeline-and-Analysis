"""
DCH Building-Level Capacity Accuracy Analysis
Compare DCH as building-level (not campus-level)

Author: Data Center GIS Team
Date: December 11, 2024
"""

import arcpy
import numpy as np
from collections import defaultdict

GDB = r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\Default.gdb"


def main():
    print("=" * 70)
    print("DCH BUILDING-LEVEL CAPACITY ACCURACY")
    print("Comparing DCH as building-level (not campus)")
    print("=" * 70)
    print()

    # Get Meta buildings with IT load
    meta_bldgs = {}
    with arcpy.da.SearchCursor(
        GDB + "/meta_canonical_buildings",
        ["building_key", "it_load_total", "new_build_status"]
    ) as cursor:
        for bkey, it_load, status in cursor:
            if it_load and it_load > 0:
                meta_bldgs[bkey] = {"it_load": it_load, "status": status}

    print(f"Meta buildings with IT load: {len(meta_bldgs)}")

    # Get DCH matches - building level, dedupe to closest
    dch_matches = {}
    with arcpy.da.SearchCursor(
        GDB + "/accuracy_analysis_multi_source_REBUILT",
        ["building_key", "source", "commissioned_power_mw", "distance_m"],
        "source = 'DataCenterHawk'"
    ) as cursor:
        for bkey, source, capacity, dist in cursor:
            dist_val = dist if dist else 999999
            if bkey not in dch_matches or dist_val < dch_matches[bkey]["dist"]:
                dch_matches[bkey] = {
                    "capacity": capacity or 0,
                    "dist": dist_val
                }

    print(f"Meta buildings with DCH match: {len(dch_matches)}")

    # Calculate accuracy - building-level (with PUE adjustment)
    errors_all = []
    errors_complete = []
    comparisons = []

    for bkey, match in dch_matches.items():
        if bkey in meta_bldgs:
            meta_it = meta_bldgs[bkey]["it_load"]
            status = meta_bldgs[bkey]["status"]
            dch_cap_raw = match["capacity"]
            dch_cap_adjusted = dch_cap_raw / 1.3  # PUE adjust

            if meta_it > 0 and dch_cap_adjusted > 0:
                error = abs(dch_cap_adjusted - meta_it) / meta_it
                errors_all.append(error)

                comparisons.append({
                    "bkey": bkey,
                    "meta_it": meta_it,
                    "dch_raw": dch_cap_raw,
                    "dch_adjusted": dch_cap_adjusted,
                    "error_pct": error * 100,
                    "status": status
                })

                if status == "Complete Build":
                    errors_complete.append(error)

    print()
    print("DCH BUILDING-LEVEL RESULTS (with PUE/1.3 adjustment):")
    print("-" * 60)

    if errors_all:
        mape_all = np.mean(errors_all) * 100
        print(f"  All statuses:     MAPE = {mape_all:.1f}% (n={len(errors_all)})")

    if errors_complete:
        mape_complete = np.mean(errors_complete) * 100
        print(f"  Complete builds:  MAPE = {mape_complete:.1f}% (n={len(errors_complete)})")

    # Compare to Semianalysis
    print()
    print("COMPARISON TO SEMIANALYSIS:")
    print("-" * 60)

    # Get Semianalysis matches
    semi_matches = {}
    with arcpy.da.SearchCursor(
        GDB + "/accuracy_analysis_multi_source_REBUILT",
        ["building_key", "source", "mw_2023", "distance_m"],
        "source = 'Semianalysis'"
    ) as cursor:
        for bkey, source, capacity, dist in cursor:
            dist_val = dist if dist else 999999
            if bkey not in semi_matches or dist_val < semi_matches[bkey]["dist"]:
                semi_matches[bkey] = {
                    "capacity": capacity or 0,
                    "dist": dist_val
                }

    semi_errors_complete = []
    for bkey, match in semi_matches.items():
        if bkey in meta_bldgs:
            meta_it = meta_bldgs[bkey]["it_load"]
            status = meta_bldgs[bkey]["status"]
            semi_cap = match["capacity"]

            if meta_it > 0 and semi_cap > 0 and status == "Complete Build":
                error = abs(semi_cap - meta_it) / meta_it
                semi_errors_complete.append(error)

    if semi_errors_complete:
        semi_mape = np.mean(semi_errors_complete) * 100
        print(f"  Semianalysis mw_2023: MAPE = {semi_mape:.1f}% (n={len(semi_errors_complete)})")

    if errors_complete:
        print(f"  DCH building-level:   MAPE = {mape_complete:.1f}% (n={len(errors_complete)})")

    # Sample comparisons
    print()
    print("SAMPLE BUILDING COMPARISONS (Complete Builds):")
    print("-" * 60)

    complete_comps = [c for c in comparisons if c["status"] == "Complete Build"]
    complete_comps.sort(key=lambda x: x["meta_it"], reverse=True)

    print(f"{'Building':<15} {'Meta IT':>10} {'DCH Raw':>10} {'DCH/1.3':>10} {'Error':>8}")
    print("-" * 55)
    for c in complete_comps[:10]:
        print(f"{c['bkey'][:15]:<15} {c['meta_it']:>10.1f} {c['dch_raw']:>10.1f} {c['dch_adjusted']:>10.1f} {c['error_pct']:>7.1f}%")

    print()
    print("=" * 70)
    print("CONCLUSION")
    print("=" * 70)

    if errors_complete and semi_errors_complete:
        dch_mape = np.mean(errors_complete) * 100
        semi_mape = np.mean(semi_errors_complete) * 100

        if dch_mape < semi_mape:
            print(f"DCH building-level ({dch_mape:.1f}%) is MORE accurate than Semianalysis ({semi_mape:.1f}%)")
        else:
            print(f"Semianalysis ({semi_mape:.1f}%) is MORE accurate than DCH ({dch_mape:.1f}%)")


if __name__ == "__main__":
    main()
