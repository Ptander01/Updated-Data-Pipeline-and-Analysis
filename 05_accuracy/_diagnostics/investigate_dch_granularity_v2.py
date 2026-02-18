"""
DCH Granularity Investigation - Part 2
Determine if DCH is actually building-level or campus-level

Author: Data Center GIS Team
Date: December 11, 2024
"""

import arcpy
from collections import defaultdict

GDB = r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\Default.gdb"


def main():
    print("=" * 70)
    print("DCH GRANULARITY INVESTIGATION - PART 2")
    print("Is DCH actually building-level or campus-level?")
    print("=" * 70)
    print()

    # 1. Check record_level in gold_buildings
    print("[1] DCH RECORD_LEVEL FIELD VALUES")
    print("-" * 60)

    levels = defaultdict(int)
    with arcpy.da.SearchCursor(
        GDB + "/gold_buildings",
        ["record_level"],
        "source = 'DataCenterHawk'"
    ) as cursor:
        for row in cursor:
            levels[row[0] or "NULL"] += 1

    for level, cnt in sorted(levels.items()):
        print(f"  {level}: {cnt}")

    # 2. Check if DCH has multiple records per campus_id
    print()
    print("[2] DCH RECORDS PER CAMPUS_ID")
    print("-" * 60)

    campus_records = defaultdict(list)
    with arcpy.da.SearchCursor(
        GDB + "/gold_buildings",
        ["campus_id", "building_name", "commissioned_power_mw"],
        "source = 'DataCenterHawk'"
    ) as cursor:
        for campus_id, bldg_name, capacity in cursor:
            campus_records[campus_id or "NULL"].append({
                "building": bldg_name,
                "capacity": capacity or 0
            })

    multi = [(k, v) for k, v in campus_records.items() if len(v) > 1]
    single = [(k, v) for k, v in campus_records.items() if len(v) == 1]

    print(f"Unique campus_ids: {len(campus_records)}")
    print(f"Campus_ids with 1 record: {len(single)}")
    print(f"Campus_ids with 2+ records: {len(multi)}")

    if multi:
        print()
        print("Sample campus_ids with multiple records (suggests BUILDING-level data):")
        for campus_id, records in sorted(multi, key=lambda x: -len(x[1]))[:5]:
            total_cap = sum(r["capacity"] for r in records)
            print(f"  {campus_id}: {len(records)} records, total {total_cap:.0f} MW")
            for r in records[:3]:
                bldg = r["building"] or "unnamed"
                print(f"    - {bldg}: {r['capacity']:.0f} MW")

    # 3. Check if capacity is duplicated across records in same campus
    print()
    print("[3] CAPACITY DUPLICATION CHECK")
    print("-" * 60)

    # If DCH reports campus-level, all records in same campus would have SAME capacity
    # If DCH reports building-level, each record would have DIFFERENT capacity

    same_cap_count = 0
    diff_cap_count = 0

    for campus_id, records in multi:
        capacities = [r["capacity"] for r in records if r["capacity"] > 0]
        if len(capacities) > 1:
            if len(set(capacities)) == 1:
                same_cap_count += 1  # All same = campus-level reporting
            else:
                diff_cap_count += 1  # Different = building-level reporting

    print(f"Multi-record campuses with SAME capacity (campus-level): {same_cap_count}")
    print(f"Multi-record campuses with DIFFERENT capacities (building-level): {diff_cap_count}")

    # 4. Check the ingestion script to see how record_level was set
    print()
    print("[4] CHECK INGESTION SCRIPT")
    print("-" * 60)

    ingest_path = r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\scripts\01_ingestion\ingest_dch.py"

    try:
        with open(ingest_path, "r") as f:
            content = f.read()

        # Look for record_level assignment
        if "record_level" in content:
            print("record_level field IS set in ingestion script")
            # Find the line
            for i, line in enumerate(content.split("\n")):
                if "record_level" in line.lower():
                    print(f"  Line {i+1}: {line.strip()[:80]}")
        else:
            print("record_level field NOT explicitly set in ingestion script")
    except Exception as e:
        print(f"Could not read ingestion script: {e}")

    # 5. Conclusion
    print()
    print("=" * 70)
    print("CONCLUSION")
    print("=" * 70)

    if diff_cap_count > same_cap_count:
        print("DCH appears to report BUILDING-LEVEL data:")
        print("  - Multiple records per campus with DIFFERENT capacities")
        print("  - Each capacity value represents a single building/data hall")
        print()
        print("The record_level='Campus' field may be INCORRECTLY SET")
        print("or represents something different (e.g., campus the building belongs to)")
    else:
        print("DCH appears to report CAMPUS-LEVEL data:")
        print("  - Capacity values are duplicated across records in same campus")
        print("  - Each record represents the same campus total")


if __name__ == "__main__":
    main()
