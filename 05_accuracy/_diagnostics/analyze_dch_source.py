"""
DCH Source Data Analysis - Determine actual granularity
Check if DCH source data is building-level or campus-level

Author: Data Center GIS Team
Date: December 11, 2024
"""

import arcpy
from collections import defaultdict

GDB = r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\Default.gdb"


def main():
    print("=" * 70)
    print("DCH SOURCE DATA ANALYSIS")
    print("Determining actual granularity of DCH data")
    print("=" * 70)
    print()

    # Check DCH source data
    source_fc = GDB + "/DCH_Hyper_MetaOracle_ConsensusXY"

    # Get all field names
    fields = [f.name for f in arcpy.ListFields(source_fc)]
    print("Available fields:")
    for f in fields:
        print(f"  {f}")
    print()

    # Sample some records
    print("[1] SAMPLE SOURCE RECORDS")
    print("-" * 60)

    sample_fields = ["datacenter_name", "campus_id", "capacity_commissioned_power"]
    available = [f for f in sample_fields if f in fields]

    print(f"Sampling fields: {available}")
    print()

    # Group by campus_id
    campus_data = defaultdict(list)

    with arcpy.da.SearchCursor(source_fc, available + ["SHAPE@XY"]) as cursor:
        for row in cursor:
            dc_name = row[0] if len(available) > 0 else None
            campus_id = row[1] if len(available) > 1 else None
            capacity = row[2] if len(available) > 2 else None
            xy = row[-1]

            campus_data[campus_id].append({
                "name": dc_name,
                "capacity": capacity,
                "xy": xy
            })

    print(f"Unique campus_ids in source: {len(campus_data)}")

    # Check how many have multiple records
    multi = [(k, v) for k, v in campus_data.items() if len(v) > 1]
    single = [(k, v) for k, v in campus_data.items() if len(v) == 1]

    print(f"Campus_ids with 1 record: {len(single)}")
    print(f"Campus_ids with multiple records: {len(multi)}")
    print()

    # Analyze multi-record campuses
    if multi:
        print("[2] MULTI-RECORD CAMPUS ANALYSIS")
        print("-" * 60)

        same_capacity_count = 0
        diff_capacity_count = 0
        same_coords_count = 0
        diff_coords_count = 0

        for campus_id, records in multi:
            # Check capacities
            caps = [r["capacity"] for r in records if r["capacity"]]
            if len(caps) > 1:
                if len(set(caps)) == 1:
                    same_capacity_count += 1
                else:
                    diff_capacity_count += 1

            # Check coordinates
            coords = [(round(r["xy"][0], 5), round(r["xy"][1], 5)) for r in records if r["xy"]]
            if len(coords) > 1:
                if len(set(coords)) == 1:
                    same_coords_count += 1
                else:
                    diff_coords_count += 1

        print("For campuses with multiple records:")
        print(f"  Same capacity across records: {same_capacity_count}")
        print(f"  Different capacities: {diff_capacity_count}")
        print(f"  Same coordinates: {same_coords_count}")
        print(f"  Different coordinates: {diff_coords_count}")
        print()

        # Show examples
        print("[3] SAMPLE MULTI-RECORD CAMPUSES")
        print("-" * 60)

        for campus_id, records in list(multi)[:3]:
            print(f"Campus: {campus_id}")
            for r in records[:4]:
                name = r["name"] or "unnamed"
                cap = r["capacity"] or 0
                xy = r["xy"]
                coord_str = f"({xy[0]:.4f}, {xy[1]:.4f})" if xy else "no coords"
                print(f"  - {name}: {cap} kW, {coord_str}")
            print()

    # Conclusion
    print("=" * 70)
    print("CONCLUSION")
    print("=" * 70)

    if multi:
        # Determine based on analysis
        same_cap = same_capacity_count
        diff_cap = diff_capacity_count
        same_coord = same_coords_count
        diff_coord = diff_coords_count

        if diff_coord > same_coord and diff_cap > same_cap:
            print("DCH appears to be BUILDING-LEVEL data:")
            print("  - Different coordinates per campus")
            print("  - Different capacities per building")
            print()
            print("RECOMMENDATION: Treat DCH as building-level for both spatial and capacity")
        elif same_coord > diff_coord and same_cap > diff_cap:
            print("DCH appears to be CAMPUS-LEVEL data:")
            print("  - Same coordinates duplicated across records")
            print("  - Same capacity duplicated across records")
            print()
            print("RECOMMENDATION: Deduplicate DCH to one record per campus")
        else:
            print("DCH has MIXED granularity:")
            print(f"  - Coordinates: {same_coord} same, {diff_coord} different")
            print(f"  - Capacities: {same_cap} same, {diff_cap} different")
            print()
            print("RECOMMENDATION: Further investigation needed")
    else:
        print("All DCH records have unique campus_ids - no multi-record campuses to analyze")


if __name__ == "__main__":
    main()
