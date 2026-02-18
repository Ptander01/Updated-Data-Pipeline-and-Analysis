"""
Validate Geographic Coordinate Independence
Check if DCH and Semianalysis are using their own native coordinates
or if they're sharing consensus/synthetic coordinates.

Also checks for redundancy between latitude/longitude and gold_lat/gold_lon fields.

Author: Meta Data Center GIS Team
Date: December 11, 2024
"""

import arcpy
from collections import defaultdict
import os

GDB = r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\Default.gdb"
GOLD_BUILDINGS = os.path.join(GDB, "gold_buildings")

print("=" * 80)
print("COORDINATE INDEPENDENCE VALIDATION (v2)")
print("Check ALL coordinate fields: latitude/longitude AND gold_lat/gold_lon")
print("=" * 80)

# ============================================================================
# STEP 0: Check what coordinate fields exist and their relationship
# ============================================================================

print("\n[0/5] Checking coordinate field redundancy within each record...")

# Check if gold_lat/gold_lon exist
available_fields = [f.name for f in arcpy.ListFields(GOLD_BUILDINGS)]
has_gold_coords = 'gold_lat' in available_fields and 'gold_lon' in available_fields

print(f"   Fields available: latitude, longitude: YES")
print(f"   Fields available: gold_lat, gold_lon: {'YES' if has_gold_coords else 'NO'}")

if has_gold_coords:
    # Check if lat/lon equals gold_lat/gold_lon within each record
    check_fields = ['source', 'unique_id', 'latitude', 'longitude', 'gold_lat', 'gold_lon', 'SHAPE@XY']

    redundancy_stats = {
        'DataCenterHawk': {'same': 0, 'different': 0, 'one_null': 0},
        'Semianalysis': {'same': 0, 'different': 0, 'one_null': 0}
    }

    shape_vs_lat_lon = {
        'DataCenterHawk': {'matches_lat_lon': 0, 'matches_gold': 0, 'matches_neither': 0},
        'Semianalysis': {'matches_lat_lon': 0, 'matches_gold': 0, 'matches_neither': 0}
    }

    with arcpy.da.SearchCursor(GOLD_BUILDINGS, check_fields) as cursor:
        for row in cursor:
            source, uid, lat, lon, gold_lat, gold_lon, shape_xy = row

            if source not in ['DataCenterHawk', 'Semianalysis']:
                continue

            # Check lat/lon vs gold_lat/gold_lon
            if lat and lon and gold_lat and gold_lon:
                lat_same = abs(lat - gold_lat) < 0.0001
                lon_same = abs(lon - gold_lon) < 0.0001
                if lat_same and lon_same:
                    redundancy_stats[source]['same'] += 1
                else:
                    redundancy_stats[source]['different'] += 1
            else:
                redundancy_stats[source]['one_null'] += 1

            # Check which field matches SHAPE@XY
            if shape_xy and shape_xy[0] and shape_xy[1]:
                shape_lon, shape_lat = shape_xy

                lat_lon_match = False
                gold_match = False

                if lat and lon:
                    lat_lon_match = abs(shape_lat - lat) < 0.0001 and abs(shape_lon - lon) < 0.0001

                if gold_lat and gold_lon:
                    gold_match = abs(shape_lat - gold_lat) < 0.0001 and abs(shape_lon - gold_lon) < 0.0001

                if lat_lon_match:
                    shape_vs_lat_lon[source]['matches_lat_lon'] += 1
                elif gold_match:
                    shape_vs_lat_lon[source]['matches_gold'] += 1
                else:
                    shape_vs_lat_lon[source]['matches_neither'] += 1

    print("\n   Lat/Lon vs Gold_Lat/Gold_Lon (within each record):")
    print("-" * 60)
    for source in ['DataCenterHawk', 'Semianalysis']:
        stats = redundancy_stats[source]
        total = stats['same'] + stats['different'] + stats['one_null']
        if total > 0:
            same_pct = stats['same'] / total * 100
            diff_pct = stats['different'] / total * 100
            print(f"   {source}:")
            print(f"      Same coords: {stats['same']} ({same_pct:.1f}%)")
            print(f"      Different:   {stats['different']} ({diff_pct:.1f}%)")
            print(f"      One null:    {stats['one_null']}")

    print("\n   SHAPE@XY geometry matches which field?:")
    print("-" * 60)
    for source in ['DataCenterHawk', 'Semianalysis']:
        stats = shape_vs_lat_lon[source]
        total = stats['matches_lat_lon'] + stats['matches_gold'] + stats['matches_neither']
        if total > 0:
            print(f"   {source}:")
            print(f"      Matches latitude/longitude: {stats['matches_lat_lon']} ({stats['matches_lat_lon']/total*100:.1f}%)")
            print(f"      Matches gold_lat/gold_lon:  {stats['matches_gold']} ({stats['matches_gold']/total*100:.1f}%)")
            print(f"      Matches neither:            {stats['matches_neither']}")

# ============================================================================
# STEP 1: Get coordinates from gold_buildings by source and campus
# ============================================================================

print("\n[1/5] Loading ALL coordinate fields by source and campus...")

coords_by_source_campus = defaultdict(lambda: defaultdict(list))

# Include both coordinate pairs AND the shape geometry
fields = ['source', 'campus_name', 'city', 'latitude', 'longitude', 'unique_id', 'SHAPE@XY']
if has_gold_coords:
    fields = ['source', 'campus_name', 'city', 'latitude', 'longitude', 'gold_lat', 'gold_lon', 'unique_id', 'SHAPE@XY']

with arcpy.da.SearchCursor(GOLD_BUILDINGS, fields) as cursor:
    for row in cursor:
        if has_gold_coords:
            source, campus_name, city, lat, lon, gold_lat, gold_lon, uid, shape_xy = row
        else:
            source, campus_name, city, lat, lon, uid, shape_xy = row
            gold_lat, gold_lon = None, None

        if source in ['DataCenterHawk', 'Semianalysis']:
            # Create a location key (campus + city)
            loc_key = f"{campus_name}|{city}" if campus_name else f"unknown|{city}"

            # Get shape coordinates
            shape_lon, shape_lat = shape_xy if shape_xy else (None, None)

            coords_by_source_campus[source][loc_key].append({
                'lat': lat,
                'lon': lon,
                'gold_lat': gold_lat,
                'gold_lon': gold_lon,
                'shape_lat': shape_lat,
                'shape_lon': shape_lon,
                'uid': uid
            })

print(f"   DCH locations: {len(coords_by_source_campus['DataCenterHawk'])}")
print(f"   Semianalysis locations: {len(coords_by_source_campus['Semianalysis'])}")

# ============================================================================
# STEP 2: Find matching campuses between sources - USE COORDINATE PROXIMITY
# ============================================================================

print("\n[2/5] Finding matching locations using COORDINATE PROXIMITY...")
print("   (Campus names differ between sources, so using lat/lon matching)")

# Build a list of all coordinates from each source
dch_points = []
for loc_key, coords_list in coords_by_source_campus['DataCenterHawk'].items():
    for coord in coords_list:
        if coord['lat'] and coord['lon']:
            dch_points.append({
                'loc_key': loc_key,
                'lat': coord['lat'],
                'lon': coord['lon'],
                'uid': coord['uid']
            })

semi_points = []
for loc_key, coords_list in coords_by_source_campus['Semianalysis'].items():
    for coord in coords_list:
        if coord['lat'] and coord['lon']:
            semi_points.append({
                'loc_key': loc_key,
                'lat': coord['lat'],
                'lon': coord['lon'],
                'uid': coord['uid']
            })

print(f"   DCH points with coordinates: {len(dch_points)}")
print(f"   Semianalysis points with coordinates: {len(semi_points)}")

# ============================================================================
# STEP 3: Compare coordinates using proximity matching
# ============================================================================

print("\n[3/5] Matching by coordinate proximity (within 1km)...")

import math

def haversine_distance(lat1, lon1, lat2, lon2):
    """Calculate distance in meters between two points."""
    R = 6371000  # Earth radius in meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = math.sin(delta_phi/2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

    return R * c

# For each Semi point, find closest DCH point
matches = []
MATCH_THRESHOLD = 1000  # 1km threshold

for semi_pt in semi_points:
    best_match = None
    best_distance = float('inf')

    for dch_pt in dch_points:
        dist = haversine_distance(semi_pt['lat'], semi_pt['lon'],
                                   dch_pt['lat'], dch_pt['lon'])
        if dist < best_distance:
            best_distance = dist
            best_match = dch_pt

    if best_match and best_distance < MATCH_THRESHOLD:
        matches.append({
            'semi_loc': semi_pt['loc_key'],
            'dch_loc': best_match['loc_key'],
            'semi_lat': semi_pt['lat'],
            'semi_lon': semi_pt['lon'],
            'dch_lat': best_match['lat'],
            'dch_lon': best_match['lon'],
            'distance_m': best_distance
        })

print(f"   Matches found within 1km: {len(matches)}")

# Analyze coordinate similarity
if len(matches) > 0:
    identical_count = 0
    different_count = 0
    comparisons = []

    for match in matches:
        lat_diff = abs(match['semi_lat'] - match['dch_lat'])
        lon_diff = abs(match['semi_lon'] - match['dch_lon'])

        is_identical = lat_diff < 0.0001 and lon_diff < 0.0001  # ~11m tolerance

        comparisons.append({
            'semi_loc': match['semi_loc'],
            'dch_loc': match['dch_loc'],
            'semi_lat': match['semi_lat'],
            'semi_lon': match['semi_lon'],
            'dch_lat': match['dch_lat'],
            'dch_lon': match['dch_lon'],
            'lat_diff': lat_diff,
            'lon_diff': lon_diff,
            'distance_m': match['distance_m'],
            'is_identical': is_identical
        })

        if is_identical:
            identical_count += 1
        else:
            different_count += 1

    print(f"\n   Results:")
    print(f"   ✅ Identical coordinates (<11m): {identical_count} ({identical_count/len(comparisons)*100:.1f}%)")
    print(f"   ❌ Different coordinates: {different_count} ({different_count/len(comparisons)*100:.1f}%)")
else:
    comparisons = []
    identical_count = 0
    different_count = 0
    print("\n   ⚠️  No matches found within 1km threshold!")
    print("   This suggests coordinates are VERY different between sources.")

# ============================================================================
# STEP 4: Show sample comparisons
# ============================================================================

print("\n[4/5] Sample Comparisons...")

if len(comparisons) > 0:
    print("\n   IDENTICAL COORDINATES (sample 5):")
    print("-" * 100)
    print(f"   {'Semi Location':<25} {'DCH Location':<25} {'Dist':>8}")
    print("-" * 100)

    identical_samples = [c for c in comparisons if c['is_identical']][:5]
    for comp in identical_samples:
        semi_loc = comp['semi_loc'][:25] if comp['semi_loc'] else 'N/A'
        dch_loc = comp['dch_loc'][:25] if comp['dch_loc'] else 'N/A'
        print(f"   {semi_loc:<25} {dch_loc:<25} {comp['distance_m']:>7.1f}m")

    if len(identical_samples) == 0:
        print("   (No identical coordinates found)")

    print("\n   DIFFERENT COORDINATES (sample 5):")
    print("-" * 100)
    print(f"   {'Semi Location':<25} {'DCH Location':<25} {'Dist':>8} {'Δ Lat':>10} {'Δ Lon':>10}")
    print("-" * 100)

    different_samples = [c for c in comparisons if not c['is_identical']][:5]
    for comp in different_samples:
        semi_loc = comp['semi_loc'][:25] if comp['semi_loc'] else 'N/A'
        dch_loc = comp['dch_loc'][:25] if comp['dch_loc'] else 'N/A'
        print(f"   {semi_loc:<25} {dch_loc:<25} {comp['distance_m']:>7.1f}m {comp['lat_diff']:>10.6f} {comp['lon_diff']:>10.6f}")

    if len(different_samples) == 0:
        print("   (No different coordinates found)")
else:
    print("   No comparisons available - sources don't have overlapping locations within 1km")

# ============================================================================
# DIAGNOSIS
# ============================================================================

print("\n" + "=" * 80)
print("📋 DIAGNOSIS")
print("=" * 80)

if identical_count / len(comparisons) > 0.8:
    print("""
⚠️  WARNING: COORDINATES APPEAR TO BE SHARED/CONSENSUS

More than 80% of matching campuses have IDENTICAL coordinates between
DCH and Semianalysis. This suggests:

1. The source data was pre-processed with consensus coordinates
   (Note: DCH source file is named 'DCH_Hyper_MetaOracle_ConsensusXY')

2. One source's coordinates were copied to the other during data prep

3. Both sources independently got the same coordinates (unlikely)

IMPACT ON SPATIAL ACCURACY ANALYSIS:
- Spatial accuracy metrics may be ARTIFICIALLY SIMILAR between sources
- Cannot independently validate which source has better native coordinates
- The 233m (DCH) vs 307m (Semianalysis) difference may be due to
  other factors, not native coordinate quality

RECOMMENDATION:
- Obtain ORIGINAL source exports before consensus XY was applied
- Re-run spatial accuracy analysis with native coordinates
- Compare native vs consensus coordinate accuracy
""")
else:
    print("""
✅ COORDINATES APPEAR TO BE INDEPENDENT

Less than 80% of matching campuses have identical coordinates.
The sources appear to be using their own native coordinates.
Spatial accuracy comparison is valid.
""")

# ============================================================================
# CHECK SOURCE FEATURE CLASS NAMES
# ============================================================================

print("\n[BONUS] Checking source feature class names...")

# List all feature classes in GDB
arcpy.env.workspace = GDB
fcs = arcpy.ListFeatureClasses()

dch_sources = [fc for fc in fcs if 'DCH' in fc.upper()]
semi_sources = [fc for fc in fcs if 'SEMI' in fc.upper()]

print(f"\n   DCH-related feature classes:")
for fc in dch_sources:
    count = int(arcpy.management.GetCount(fc)[0])
    print(f"   - {fc} ({count} records)")
    if 'consensus' in fc.lower():
        print(f"     ⚠️  Contains 'Consensus' in name - may have modified coordinates")

print(f"\n   Semianalysis-related feature classes:")
for fc in semi_sources:
    count = int(arcpy.management.GetCount(fc)[0])
    print(f"   - {fc} ({count} records)")
    if 'consensus' in fc.lower():
        print(f"     ⚠️  Contains 'Consensus' in name - may have modified coordinates")

print("\n" + "=" * 80)
print("VALIDATION COMPLETE")
print("=" * 80)
