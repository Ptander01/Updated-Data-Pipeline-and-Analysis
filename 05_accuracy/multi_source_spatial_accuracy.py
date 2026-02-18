import arcpy
import pandas as pd
from datetime import datetime
import math

# ============================================================================
# MULTI-SOURCE SPATIAL ACCURACY ANALYSIS (v5 - FIXED)
# ============================================================================
# Fixes:
# 1. Distance conversion from degrees to meters
# 2. Removed company filter (match by proximity only)
# 3. Added geodesic distance calculation
# ============================================================================

gdb_path = r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\Default.gdb"
meta_canonical = "meta_canonical_buildings"
gold_buildings = "gold_buildings"
output_matches = "accuracy_analysis_buildings_v4"

TOTAL_META_BUILDINGS = 276

print("="*80)
print("MULTI-SOURCE SPATIAL ACCURACY ANALYSIS (v5 - FIXED)")
print("="*80)
print(f"\nFixes applied:")
print(f"   ✅ Geodesic distance calculation (meters)")
print(f"   ✅ No company filter (match by proximity)")
print(f"   ✅ All 6 vendors included")
print("\n" + "="*80)

arcpy.env.workspace = gdb_path
arcpy.ClearWorkspaceCache_management()

# ============================================================================
# STEP 1: SPATIAL JOIN WITHOUT COMPANY FILTER
# ============================================================================
print("\n[STEP 1] Performing spatial join (ALL vendor records)...")

temp_join = "temp_spatial_join_v5"
if arcpy.Exists(temp_join):
    arcpy.Delete_management(temp_join)

# Spatial join - NO company filter, get closest match per source
arcpy.analysis.SpatialJoin(
    target_features=meta_canonical,
    join_features=gold_buildings,
    out_feature_class=temp_join,
    join_operation="JOIN_ONE_TO_MANY",
    join_type="KEEP_ALL",
    match_option="CLOSEST",
    search_radius="50 Kilometers",
    distance_field_name="distance_degrees"  # Will be in degrees for WGS84
)

join_count = int(arcpy.GetCount_management(temp_join)[0])
print(f"   Total matches (all vendors, all companies): {join_count:,}")

# ============================================================================
# STEP 2: CALCULATE GEODESIC DISTANCE IN METERS
# ============================================================================
print("\n[STEP 2] Calculating geodesic distances in meters...")

# Add distance_m field
all_fields = [f.name for f in arcpy.ListFields(temp_join)]
if 'distance_m' not in all_fields:
    arcpy.AddField_management(temp_join, "distance_m", "DOUBLE")

def haversine_distance(lat1, lon1, lat2, lon2):
    """Calculate geodesic distance in meters using Haversine formula."""
    if any(v is None for v in [lat1, lon1, lat2, lon2]):
        return None

    R = 6371000  # Earth's radius in meters

    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)

    a = math.sin(delta_lat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon/2)**2
    c = 2 * math.asin(math.sqrt(a))

    return R * c

# Find coordinate fields for external data
lat_field = 'latitude_1' if 'latitude_1' in all_fields else 'latitude'
lon_field = 'longitude_1' if 'longitude_1' in all_fields else 'longitude'

print(f"   Using coordinate fields: {lat_field}, {lon_field}")

update_count = 0
with arcpy.da.UpdateCursor(temp_join,
                          ['SHAPE@Y', 'SHAPE@X', lat_field, lon_field, 'distance_m']) as cursor:
    for row in cursor:
        meta_lat, meta_lon = row[0], row[1]
        ext_lat, ext_lon = row[2], row[3]

        distance = haversine_distance(meta_lat, meta_lon, ext_lat, ext_lon)
        row[4] = distance
        cursor.updateRow(row)
        update_count += 1

print(f"   Calculated geodesic distance for {update_count:,} records")

# ============================================================================
# STEP 3: COPY TO OUTPUT (NO COMPANY FILTER)
# ============================================================================
print("\n[STEP 3] Creating output feature class...")

if arcpy.Exists(output_matches):
    arcpy.Delete_management(output_matches)

arcpy.CopyFeatures_management(temp_join, output_matches)

output_count = int(arcpy.GetCount_management(output_matches)[0])
print(f"   Created {output_matches}: {output_count:,} records")

# ============================================================================
# STEP 4: ANALYZE BY SOURCE
# ============================================================================
print("\n[STEP 4] Analyzing accuracy by source...")

# Build field mapping
output_fields = [f.name for f in arcpy.ListFields(output_matches)]

# Identify key fields
building_key_field = 'building_key' if 'building_key' in output_fields else None
source_field = 'source_1' if 'source_1' in output_fields else 'source'
region_field = 'region_derived' if 'region_derived' in output_fields else None

if not building_key_field:
    print("   ❌ ERROR: building_key field not found!")
    # List available fields
    print(f"   Available fields: {output_fields[:20]}")

# Read data
read_fields = ['distance_m', source_field]
if building_key_field:
    read_fields.append(building_key_field)
if region_field:
    read_fields.append(region_field)

data = []
with arcpy.da.SearchCursor(output_matches, read_fields) as cursor:
    for row in cursor:
        data.append(dict(zip(read_fields, row)))

df = pd.DataFrame(data)

print(f"\n   Total records: {len(df):,}")
print(f"   Sources found: {df[source_field].unique().tolist()}")

# Get Meta building counts by region
meta_by_region = {}
if region_field:
    with arcpy.da.SearchCursor(meta_canonical, [region_field]) as cursor:
        for row in cursor:
            region = row[0] if row[0] else 'UNKNOWN'
            if region != 'UNKNOWN':
                meta_by_region[region] = meta_by_region.get(region, 0) + 1

# ============================================================================
# CALCULATE METRICS BY SOURCE
# ============================================================================
print("\n" + "="*80)
print("ACCURACY METRICS BY SOURCE (FIXED)")
print("="*80)

sources = ['DataCenterHawk', 'Semianalysis', 'DataCenterMap', 'Synergy', 'NewProjectMedia', 'WoodMac']
summary_results = []

for source in sources:
    source_data = df[df[source_field] == source].copy()

    print(f"\n{'='*60}")
    print(f"SOURCE: {source}")
    print(f"{'='*60}")

    if len(source_data) == 0:
        print(f"   ❌ No matches found")
        summary_results.append({
            'source': source,
            'buildings_detected': 0,
            'recall_pct': 0,
            'total_matches': 0,
            'median_distance_m': None,
            'mean_distance_m': None,
            'within_500m': 0,
            'within_1km': 0,
            'within_5km': 0
        })
        continue

    # Recall
    if building_key_field:
        buildings_detected = source_data[building_key_field].nunique()
    else:
        buildings_detected = len(source_data)

    recall = (buildings_detected / TOTAL_META_BUILDINGS) * 100

    print(f"\n   📊 RECALL:")
    print(f"      Buildings detected: {buildings_detected} / {TOTAL_META_BUILDINGS}")
    print(f"      Recall: {recall:.1f}%")

    # Distance accuracy
    distances = source_data['distance_m'].dropna()

    if len(distances) > 0:
        median_dist = distances.median()
        mean_dist = distances.mean()
        min_dist = distances.min()
        max_dist = distances.max()

        within_100m = (distances <= 100).sum()
        within_500m = (distances <= 500).sum()
        within_1km = (distances <= 1000).sum()
        within_5km = (distances <= 5000).sum()

        print(f"\n   📍 DISTANCE ACCURACY:")
        print(f"      Median: {median_dist:,.0f} meters")
        print(f"      Mean: {mean_dist:,.0f} meters")
        print(f"      Range: {min_dist:,.0f}m - {max_dist:,.0f}m")

        print(f"\n   📏 THRESHOLD ANALYSIS:")
        print(f"      ≤100m:  {within_100m:,} ({within_100m/len(distances)*100:.1f}%)")
        print(f"      ≤500m:  {within_500m:,} ({within_500m/len(distances)*100:.1f}%)")
        print(f"      ≤1km:   {within_1km:,} ({within_1km/len(distances)*100:.1f}%)")
        print(f"      ≤5km:   {within_5km:,} ({within_5km/len(distances)*100:.1f}%)")
    else:
        median_dist = mean_dist = None
        within_500m = within_1km = within_5km = 0

    # Regional breakdown
    if region_field and region_field in source_data.columns:
        print(f"\n   🌍 REGIONAL RECALL:")
        for region in ['AMER', 'EMEA', 'APAC']:
            region_total = meta_by_region.get(region, 0)
            if region_total > 0 and building_key_field:
                region_detected = source_data[source_data[region_field] == region][building_key_field].nunique()
                region_recall = (region_detected / region_total) * 100
                print(f"      {region}: {region_detected}/{region_total} ({region_recall:.1f}%)")

    summary_results.append({
        'source': source,
        'buildings_detected': buildings_detected,
        'recall_pct': recall,
        'total_matches': len(source_data),
        'median_distance_m': median_dist,
        'mean_distance_m': mean_dist,
        'within_500m': within_500m,
        'within_1km': within_1km,
        'within_5km': within_5km
    })

# ============================================================================
# SUMMARY TABLE
# ============================================================================
print("\n" + "="*80)
print("SUMMARY TABLE")
print("="*80)

summary_df = pd.DataFrame(summary_results)
summary_df = summary_df.sort_values('recall_pct', ascending=False)

print(f"\n{summary_df.to_string(index=False)}")

# Rankings
print("\n" + "="*80)
print("🏆 VENDOR RANKINGS")
print("="*80)

print("\n📊 By Recall (Coverage):")
for i, (_, row) in enumerate(summary_df.iterrows()):
    medals = ['🥇', '🥈', '🥉', '4.', '5.', '6.']
    print(f"   {medals[i]} {row['source']}: {row['recall_pct']:.1f}% ({row['buildings_detected']}/276)")

print("\n📍 By Spatial Accuracy (Median Distance):")
accuracy_df = summary_df[summary_df['median_distance_m'].notna()].sort_values('median_distance_m')
for i, (_, row) in enumerate(accuracy_df.iterrows()):
    medals = ['🥇', '🥈', '🥉', '4.', '5.', '6.']
    print(f"   {medals[i]} {row['source']}: {row['median_distance_m']:,.0f}m")

# Cleanup
if arcpy.Exists(temp_join):
    arcpy.Delete_management(temp_join)

# Export
csv_path = gdb_path.replace('.gdb', f'_accuracy_summary_FIXED_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv')
summary_df.to_csv(csv_path, index=False)
print(f"\n📊 Exported: {csv_path}")

print("\n" + "="*80)
print("✅ ANALYSIS COMPLETE")
print("="*80)
