"""
DCH Capacity Granularity Investigation
Investigating why DCH capacity predictions appear inaccurate

Author: Data Center GIS Team
Date: December 11, 2024
"""

import arcpy
from collections import defaultdict

GDB = r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\Default.gdb"


def main():
    print("=" * 70)
    print("DCH GRANULARITY INVESTIGATION")
    print("Why are DCH capacity predictions showing 38.9% MAPE?")
    print("=" * 70)
    print()

    # 1. Check DCH record_level in gold_buildings
    print("[1] DCH RECORD LEVEL IN GOLD_BUILDINGS")
    print("-" * 60)

    dch_levels = defaultdict(int)
    dch_by_campus = defaultdict(list)
    dch_total_capacity = 0

    with arcpy.da.SearchCursor(
        GDB + "/gold_buildings",
        ["record_level", "campus_id", "campus_name", "building_name", "commissioned_power_mw"],
        "source = 'DataCenterHawk'"
    ) as cursor:
        for level, campus_id, campus_name, bldg_name, capacity in cursor:
            dch_levels[level or "NULL"] += 1
            key = campus_id or campus_name or "UNKNOWN"
            dch_by_campus[key].append({
                "building": bldg_name,
                "capacity": capacity or 0
            })
            dch_total_capacity += (capacity or 0)

    print("Record level distribution:")
    for level, cnt in sorted(dch_levels.items()):
        print(f"  {level}: {cnt}")

    print(f"\nTotal DCH capacity in gold_buildings: {dch_total_capacity:.1f} MW")

    # 2. Check campus distribution
    print()
    print("[2] DCH RECORDS PER CAMPUS")
    print("-" * 60)

    multi_bldg = [(k, v) for k, v in dch_by_campus.items() if len(v) > 1]
    single_bldg = [(k, v) for k, v in dch_by_campus.items() if len(v) == 1]

    print(f"Campuses with 1 record: {len(single_bldg)}")
    print(f"Campuses with 2+ records: {len(multi_bldg)}")

    # 3. Check Meta buildings per campus
    print()
    print("[3] META BUILDINGS PER CAMPUS (dc_code)")
    print("-" * 60)

    meta_by_campus = defaultdict(lambda: {"count": 0, "it_load": 0})

    with arcpy.da.SearchCursor(
        GDB + "/meta_canonical_buildings",
        ["dc_code", "it_load_total"]
    ) as cursor:
        for dc_code, it_load in cursor:
            meta_by_campus[dc_code]["count"] += 1
            meta_by_campus[dc_code]["it_load"] += (it_load or 0)

    multi_bldg_meta = [k for k, v in meta_by_campus.items() if v["count"] > 1]
    single_bldg_meta = [k for k, v in meta_by_campus.items() if v["count"] == 1]

    print(f"Campuses with 1 building: {len(single_bldg_meta)}")
    print(f"Campuses with 2+ buildings: {len(multi_bldg_meta)}")

    print("\nSample multi-building Meta campuses:")
    for dc_code in sorted(multi_bldg_meta)[:5]:
        data = meta_by_campus[dc_code]
        print(f"  {dc_code}: {data['count']} buildings, {data['it_load']:.1f} MW total")

    # 4. Check the spatial join - are we comparing apples to apples?
    print()
    print("[4] SPATIAL JOIN ANALYSIS - DCH MATCHES")
    print("-" * 60)

    # For each Meta building, how many DCH records match?
    dch_matches_per_meta = defaultdict(list)

    with arcpy.da.SearchCursor(
        GDB + "/accuracy_analysis_multi_source_REBUILT",
        ["building_key", "dc_code", "source", "commissioned_power_mw", "distance_m"],
        "source = 'DataCenterHawk'"
    ) as cursor:
        for bkey, dc_code, source, capacity, dist in cursor:
            dch_matches_per_meta[bkey].append({
                "capacity": capacity or 0,
                "distance": dist or 0
            })

    print(f"Meta buildings with DCH matches: {len(dch_matches_per_meta)}")

    # Check for duplicates
    dup_matches = {k: v for k, v in dch_matches_per_meta.items() if len(v) > 1}
    print(f"Meta buildings with multiple DCH matches: {len(dup_matches)}")

    if dup_matches:
        print("\nSample buildings with multiple DCH matches:")
        for bkey, matches in list(dup_matches.items())[:3]:
            print(f"  {bkey}:")
            for m in matches[:3]:
                print(f"    - {m['capacity']:.1f} MW at {m['distance']:.0f}m")

    # 5. The key question: Is DCH reporting CAMPUS total on each record?
    print()
    print("[5] HYPOTHESIS TEST: Is DCH capacity CAMPUS-level?")
    print("-" * 60)

    # Compare: DCH capacity for a campus vs sum of Meta buildings in that campus

    # Get Meta campus totals
    meta_campus_totals = {}
    for dc_code, data in meta_by_campus.items():
        meta_campus_totals[dc_code] = data["it_load"]

    # For each DCH-matched Meta building, what's the DCH capacity vs Meta campus total?
    comparisons = []

    with arcpy.da.SearchCursor(
        GDB + "/accuracy_analysis_multi_source_REBUILT",
        ["building_key", "dc_code", "source", "commissioned_power_mw", "it_load_total"],
        "source = 'DataCenterHawk'"
    ) as cursor:
        for bkey, dc_code, source, dch_cap, meta_bldg_it in cursor:
            if dch_cap and meta_bldg_it:
                meta_campus_it = meta_campus_totals.get(dc_code, 0)
                comparisons.append({
                    "bkey": bkey,
                    "dc_code": dc_code,
                    "dch_cap": dch_cap,
                    "meta_bldg": meta_bldg_it,
                    "meta_campus": meta_campus_it
                })

    print(f"Valid comparisons: {len(comparisons)}")
    print()

    # Calculate what MAPE would be if DCH is campus-level
    if comparisons:
        # Current approach: DCH vs Meta building (this is what we're doing)
        errors_bldg = []
        for c in comparisons:
            if c["meta_bldg"] > 0:
                pue_adjusted = c["dch_cap"] / 1.3  # Facility -> IT
                error = abs(pue_adjusted - c["meta_bldg"]) / c["meta_bldg"]
                errors_bldg.append(error)

        mape_bldg = sum(errors_bldg) / len(errors_bldg) * 100 if errors_bldg else 0

        # Alternative: DCH vs Meta campus total
        # But we need to dedupe DCH to one record per campus first
        campus_comparisons = {}
        for c in comparisons:
            dc_code = c["dc_code"]
            if dc_code not in campus_comparisons:
                campus_comparisons[dc_code] = {
                    "dch_cap": c["dch_cap"],
                    "meta_campus": c["meta_campus"]
                }

        errors_campus = []
        for dc_code, data in campus_comparisons.items():
            if data["meta_campus"] > 0:
                pue_adjusted = data["dch_cap"] / 1.3
                error = abs(pue_adjusted - data["meta_campus"]) / data["meta_campus"]
                errors_campus.append(error)

        mape_campus = sum(errors_campus) / len(errors_campus) * 100 if errors_campus else 0

        print("MAPE Comparison:")
        print(f"  DCH vs Meta BUILDING (current): {mape_bldg:.1f}% (n={len(errors_bldg)})")
        print(f"  DCH vs Meta CAMPUS (alternative): {mape_campus:.1f}% (n={len(errors_campus)})")
        print()

        if mape_campus < mape_bldg:
            print(">>> DCH appears to report CAMPUS-level capacity!")
            print(">>> Should compare aggregated to aggregated.")
        else:
            print(">>> Campus-level comparison doesn't improve MAPE.")
            print(">>> Issue may be elsewhere (PUE, timing, data quality).")

    # 6. Sample comparison
    print()
    print("[6] SAMPLE COMPARISONS")
    print("-" * 60)

    if comparisons:
        print("\nSample (first 5):")
        print(f"{'Building':<15} {'DC Code':<10} {'DCH Cap':>10} {'DCH/1.3':>10} {'Meta Bldg':>10} {'Meta Camp':>10}")
        print("-" * 65)
        for c in comparisons[:5]:
            print(f"{c['bkey'][:15]:<15} {c['dc_code']:<10} {c['dch_cap']:>10.1f} {c['dch_cap']/1.3:>10.1f} {c['meta_bldg']:>10.1f} {c['meta_campus']:>10.1f}")


if __name__ == "__main__":
    main()
