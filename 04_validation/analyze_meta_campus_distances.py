"""
Analyze distances between buildings at Meta Canonical campuses.
Helps determine optimal UCID clustering tolerance.

Author: Meta Data Center GIS Team
Created: 2026-02-11
"""

import arcpy
import os
import math
from collections import defaultdict

# Configuration
GDB = r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\Default.gdb"

# Use FILTERED dataset - only active sites with capacity or build status
# Per META_CANONICAL_WORKFLOW.md: 340 buildings, excludes placeholder/future records
META_BUILDINGS = os.path.join(GDB, "meta_canonical_v2_filtered")

arcpy.env.workspace = GDB


def haversine_distance(lat1, lon1, lat2, lon2):
    """Calculate great-circle distance in meters."""
    R = 6371000
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)
    a = math.sin(delta_lat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return R * c


def main():
    print("=" * 80)
    print("META CANONICAL CAMPUS DISTANCE ANALYSIS")
    print("=" * 80)

    # Load buildings grouped by dc_code (campus)
    print("\nLoading Meta Canonical buildings...")

    campus_buildings = defaultdict(list)

    # meta_canonical_v2_filtered schema: location_key, dc_code, datacenter, it_load, new_build_status, etc.
    # dc_code = campus code (e.g., ATN, LCO)
    # datacenter = building number within campus (e.g., 0, 1, 2)
    fields = ['SHAPE@XY', 'dc_code', 'datacenter', 'it_load']

    with arcpy.da.SearchCursor(META_BUILDINGS, fields) as cursor:
        for row in cursor:
            xy = row[0]
            dc_code = row[1]
            datacenter = row[2]
            it_load = row[3]

            # Skip null island (0,0) or records without coordinates
            if xy and xy[0] and xy[1] and not (abs(xy[0]) < 0.01 and abs(xy[1]) < 0.01):
                if dc_code:
                    campus_buildings[dc_code].append({
                        'lat': xy[1],
                        'lon': xy[0],
                        'building': datacenter or 'Unknown',
                        'it_load': it_load or 0,
                    })

    print(f"Loaded {sum(len(b) for b in campus_buildings.values())} buildings across {len(campus_buildings)} campuses")

    # Calculate distances within each campus
    print("\nCalculating inter-building distances...")

    campus_stats = []
    all_distances = []

    for dc_code, buildings in campus_buildings.items():
        if len(buildings) < 2:
            # Single building campus - no inter-building distance
            campus_stats.append({
                'dc_code': dc_code,
                'building_count': len(buildings),
                'min_distance': 0,
                'max_distance': 0,
                'avg_distance': 0,
            })
            continue

        # Calculate all pairwise distances
        distances = []
        for i, b1 in enumerate(buildings):
            for b2 in buildings[i+1:]:
                dist = haversine_distance(b1['lat'], b1['lon'], b2['lat'], b2['lon'])
                distances.append(dist)
                all_distances.append(dist)

        campus_stats.append({
            'dc_code': dc_code,
            'building_count': len(buildings),
            'min_distance': min(distances),
            'max_distance': max(distances),
            'avg_distance': sum(distances) / len(distances),
        })

    # Sort by max distance (largest campus footprints first)
    campus_stats.sort(key=lambda x: -x['max_distance'])

    # Print results
    print("\n" + "=" * 80)
    print("RESULTS: INTER-BUILDING DISTANCES AT META CAMPUSES")
    print("=" * 80)

    # Overall statistics
    if all_distances:
        print(f"\nOVERALL STATISTICS (all {len(all_distances):,} building pairs):")
        print("-" * 60)
        print(f"  Minimum distance:  {min(all_distances):,.0f} m")
        print(f"  Maximum distance:  {max(all_distances):,.0f} m")
        print(f"  Average distance:  {sum(all_distances)/len(all_distances):,.0f} m")
        print(f"  Median distance:   {sorted(all_distances)[len(all_distances)//2]:,.0f} m")

    # Distribution buckets
    print(f"\nDISTANCE DISTRIBUTION:")
    print("-" * 60)
    buckets = [
        (0, 100, "0-100m"),
        (100, 250, "100-250m"),
        (250, 500, "250-500m"),
        (500, 1000, "500-1000m"),
        (1000, 2000, "1-2km"),
        (2000, float('inf'), ">2km"),
    ]

    for low, high, label in buckets:
        count = sum(1 for d in all_distances if low <= d < high)
        pct = count / len(all_distances) * 100 if all_distances else 0
        bar = "*" * int(pct / 2)
        print(f"  {label:>10}: {count:>5} ({pct:>5.1f}%) {bar}")

    # Tolerance analysis
    print(f"\nTOLERANCE IMPACT ANALYSIS:")
    print("-" * 60)
    print("  If we use X tolerance, what % of building pairs would be grouped?")

    tolerances = [100, 250, 500, 750, 1000, 1500, 2000]
    for tol in tolerances:
        grouped = sum(1 for d in all_distances if d <= tol)
        pct = grouped / len(all_distances) * 100 if all_distances else 0
        print(f"  {tol:>5}m tolerance: {pct:>5.1f}% of pairs grouped")

    # Campus-level max distance analysis
    print(f"\nCAMPUS MAX DISTANCE ANALYSIS:")
    print("-" * 60)
    print("  What tolerance would capture ALL buildings at X% of campuses?")

    multi_building_campuses = [c for c in campus_stats if c['building_count'] > 1]
    max_distances = [c['max_distance'] for c in multi_building_campuses]

    if max_distances:
        for tol in tolerances:
            covered = sum(1 for d in max_distances if d <= tol)
            pct = covered / len(max_distances) * 100
            print(f"  {tol:>5}m tolerance: {pct:>5.1f}% of campuses fully covered")

    # Top 15 largest campus footprints
    print(f"\nTOP 15 LARGEST CAMPUS FOOTPRINTS (by max inter-building distance):")
    print("-" * 80)
    print(f"{'DC Code':<10} {'Buildings':<10} {'Min (m)':<12} {'Max (m)':<12} {'Avg (m)':<12}")
    print("-" * 80)

    for c in campus_stats[:15]:
        if c['building_count'] > 1:
            print(f"{c['dc_code']:<10} {c['building_count']:<10} {c['min_distance']:<12,.0f} {c['max_distance']:<12,.0f} {c['avg_distance']:<12,.0f}")

    # Recommendation
    print("\n" + "=" * 80)
    print("RECOMMENDATION")
    print("=" * 80)

    if all_distances:
        median = sorted(all_distances)[len(all_distances)//2]
        p75 = sorted(all_distances)[int(len(all_distances)*0.75)]
        p90 = sorted(all_distances)[int(len(all_distances)*0.90)]

        print(f"\n  Median inter-building distance: {median:,.0f}m")
        print(f"  75th percentile: {p75:,.0f}m")
        print(f"  90th percentile: {p90:,.0f}m")

        if median > 250:
            print(f"\n  [FINDING] Your current 250m tolerance is BELOW the median ({median:,.0f}m)")
            print(f"  [SUGGEST] Consider increasing to {int(p75/100)*100}m - {int(p90/100)*100}m")
        else:
            print(f"\n  [FINDING] Your current 250m tolerance covers the median")

    print("\n" + "=" * 80)


# Execute
try:
    main()
except Exception as e:
    print(f"\nERROR: {str(e)}")
    import traceback
    traceback.print_exc()
