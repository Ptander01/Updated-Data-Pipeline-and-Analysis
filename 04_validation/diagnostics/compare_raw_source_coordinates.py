"""
Compare Raw Source Coordinates
Check if DCH and Semianalysis SOURCE feature classes have shared coordinates.
This validates whether the consensus coordinates were applied BEFORE our pipeline.

Author: Meta Data Center GIS Team
Date: December 11, 2024
"""

import arcpy
import math
from collections import defaultdict
import os

GDB = r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\Default.gdb"

# Source feature classes (BEFORE ingestion)
DCH_SOURCE = os.path.join(GDB, "DCH_Hyper_MetaOracle_ConsensusXY")
SEMI_SOURCE = os.path.join(GDB, "SemiAnalysis_Building_MetaOracle_ExportFeatures")

print("=" * 80)
print("RAW SOURCE COORDINATE COMPARISON")
print("Comparing SOURCE feature classes (before ingestion pipeline)")
print("=" * 80)

# ============================================================================
# STEP 1: Check source feature class existence and fields
# ============================================================================

print("\n[1/4] Checking source feature classes...")

for source_name, source_fc in [("DCH", DCH_SOURCE), ("Semianalysis", SEMI_SOURCE)]:
    if arcpy.Exists(source_fc):
        count = int(arcpy.management.GetCount(source_fc)[0])
        fields = [f.name for f in arcpy.ListFields(source_fc)]
        coord_fields = [f for f in fields if any(x in f.lower() for x in ['lat', 'lon', 'long', 'x', 'y'])]
        print(f"\n   {source_name}:")
        print(f"      Feature class: {os.path.basename(source_fc)}")
        print(f"      Records: {count}")
        print(f"      Coordinate fields: {coord_fields}")
        if 'consensus' in source_fc.lower():
            print(f"      ⚠️  NAME CONTAINS 'CONSENSUS' - coords may be modified")
    else:
        print(f"\n   {source_name}: ❌ NOT FOUND - {source_fc}")

# ============================================================================
# STEP 2: Load coordinates from each source
# ============================================================================

print("\n[2/4] Loading coordinates from source feature classes...")

def load_source_coords(fc, lat_field, lon_field, company_filter=None):
    """Load coordinates from a source feature class."""
    points = []
    fields = [lat_field, lon_field, 'SHAPE@XY']

    # Add company field if filtering
    all_fields = [f.name for f in arcpy.ListFields(fc)]
    company_field = None
    for f in ['company', 'company_name']:
        if f in all_fields:
            company_field = f
            break

    if company_field:
        fields.append(company_field)

    where_clause = None
    if company_filter and company_field:
        where_clause = f"{company_field} IN ('Meta', 'Facebook', 'Oracle')"

    with arcpy.da.SearchCursor(fc, fields, where_clause=where_clause) as cursor:
        for row in cursor:
            lat = row[0]
            lon = row[1]
            shape_xy = row[2]
            company = row[3] if len(row) > 3 else None

            if lat and lon:
                points.append({
                    'lat': lat,
                    'lon': lon,
                    'shape_lat': shape_xy[1] if shape_xy else None,
                    'shape_lon': shape_xy[0] if shape_xy else None,
                    'company': company
                })

    return points

# Load DCH source
dch_fields = [f.name for f in arcpy.ListFields(DCH_SOURCE)]
dch_lat = 'latitude' if 'latitude' in dch_fields else 'lat'
dch_lon = 'longitude' if 'longitude' in dch_fields else 'long'
dch_points = load_source_coords(DCH_SOURCE, dch_lat, dch_lon, company_filter=True)
print(f"   DCH source points (Meta/Oracle): {len(dch_points)}")

# Load Semianalysis source (already filtered for Meta/Facebook in our ingestion)
semi_fields = [f.name for f in arcpy.ListFields(SEMI_SOURCE)]
semi_lat = 'lat' if 'lat' in semi_fields else 'latitude'
semi_lon = 'long' if 'long' in semi_fields else 'longitude'
semi_points = load_source_coords(SEMI_SOURCE, semi_lat, semi_lon, company_filter=True)
print(f"   Semianalysis source points (Meta/Oracle): {len(semi_points)}")

# ============================================================================
# STEP 3: Compare coordinates using proximity matching
# ============================================================================

print("\n[3/4] Matching points by proximity (within 1km)...")

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

    for match in matches:
        lat_diff = abs(match['semi_lat'] - match['dch_lat'])
        lon_diff = abs(match['semi_lon'] - match['dch_lon'])

        is_identical = lat_diff < 0.0001 and lon_diff < 0.0001  # ~11m tolerance

        if is_identical:
            identical_count += 1
        else:
            different_count += 1

    identical_pct = identical_count / len(matches) * 100

    print(f"\n   Results (SOURCE feature classes):")
    print(f"   ✅ Identical coordinates (<11m): {identical_count} ({identical_pct:.1f}%)")
    print(f"   ❌ Different coordinates: {different_count} ({100-identical_pct:.1f}%)")
else:
    identical_pct = 0
    print("\n   ⚠️  No matches found within 1km threshold!")

# ============================================================================
# STEP 4: Diagnosis
# ============================================================================

print("\n" + "=" * 80)
print("📋 DIAGNOSIS - SOURCE DATA ANALYSIS")
print("=" * 80)

if len(matches) > 0 and identical_pct > 80:
    print(f"""
⚠️  CONFIRMED: CONSENSUS COORDINATES ARE IN THE SOURCE DATA

{identical_pct:.1f}% of matching points have IDENTICAL coordinates in the
RAW SOURCE feature classes (before our ingestion pipeline).

This confirms:
✅ Our pipeline is NOT causing the coordinate sharing
✅ The consensus coordinates were applied BEFORE the data reached us
✅ The DCH source file name contains 'ConsensusXY' - confirming pre-processing

ROOT CAUSE:
The data was pre-processed with consensus coordinates before being
imported into the geodatabase. This happened UPSTREAM of our pipeline.

RECOMMENDATIONS:
1. Obtain ORIGINAL source exports with native coordinates
2. The native DCH export should have different field name (no 'ConsensusXY')
3. Re-run spatial accuracy with native coordinates for valid comparison
""")
elif len(matches) > 0:
    print(f"""
✅ COORDINATES ARE MOSTLY INDEPENDENT IN SOURCE DATA

Only {identical_pct:.1f}% of matching points have identical coordinates.
The sources appear to have independent coordinate data.

If gold_buildings shows higher sharing, the issue may be in our pipeline.
""")
else:
    print("""
⚠️  INCONCLUSIVE - No overlapping locations found within 1km

The source feature classes may have:
- Different company filters
- Different coordinate precision
- Non-overlapping data

Recommend manual inspection of source data.
""")

# ============================================================================
# BONUS: Show sample coordinates from each source
# ============================================================================

print("\n[BONUS] Sample coordinates from each source (first 5):")

print("\n   DCH Source (first 5):")
for i, pt in enumerate(dch_points[:5]):
    print(f"      {i+1}. lat={pt['lat']:.6f}, lon={pt['lon']:.6f}")

print("\n   Semianalysis Source (first 5):")
for i, pt in enumerate(semi_points[:5]):
    print(f"      {i+1}. lat={pt['lat']:.6f}, lon={pt['lon']:.6f}")

print("\n" + "=" * 80)
print("VALIDATION COMPLETE")
print("=" * 80)
