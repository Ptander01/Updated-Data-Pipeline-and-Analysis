"""
Comprehensive Spatial Accuracy Analysis Report - UPDATED
Generates detailed statistical breakdowns for Meta Canonical vs. External Sources
(DEDUPLICATED RESULTS)

UPDATES:
- Fixed ranking bug in executive summary
- Added error handling and validation
- Added progress indicators
- Enhanced data quality checks
- Semianalysis-specific validation
- Improved executive summary formatting

Outputs:
- Campus-level statistics (62 campuses)
- Building-level statistics (276 buildings)
- Regional breakdown (AMER, APAC, EMEA)
- Build status breakdown (Complete, Active, Future)
- Threshold performance (% within distance bands)
- Worst-case error analysis
- Source comparison summary
- Executive summary report (TXT)
"""

import arcpy
import pandas as pd
import numpy as np
from datetime import datetime
import os

print("=" * 80)
print("📊 COMPREHENSIVE SPATIAL ACCURACY ANALYSIS - UPDATED")
print("=" * 80)
print(f"⏰ Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

# ============================================================================
# CONFIGURATION
# ============================================================================
gdb = r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\Default.gdb"
matches_fc = gdb + r"\accuracy_analysis_multi_source_REBUILT"  # Updated Dec 10, 2024 - uses current gold_buildings coords
canonical_fc = gdb + r"\meta_canonical_v2"
output_dir = r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\outputs\accuracy"
os.makedirs(output_dir, exist_ok=True)

timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
source_order = ['DataCenterHawk', 'Semianalysis', 'DataCenterMap',
                'NewProjectMedia', 'WoodMac', 'Synergy']

# ============================================================================
# STEP 0: Validate Input Data
# ============================================================================
print("🔍 STEP 0: Validating input data...")

try:
    if not arcpy.Exists(matches_fc):
        raise FileNotFoundError(f"Match feature class not found: {matches_fc}")
    if not arcpy.Exists(canonical_fc):
        raise FileNotFoundError(f"Canonical feature class not found: {canonical_fc}")

    print(f"   ✅ Matches feature class: {matches_fc}")
    print(f"   ✅ Canonical feature class: {canonical_fc}")

except Exception as e:
    print(f"   ❌ ERROR: {e}")
    raise

# ============================================================================
# STEP 1: Load Data
# ============================================================================
print("\n📋 STEP 1: Loading spatial accuracy data...")

try:
    # Load match records - using fields from meta_canonical_buildings-based join
    match_fields = ['source', 'distance_m', 'building_key', 'dc_code',
                    'region_derived', 'new_build_status']
    matches_data = []

    with arcpy.da.SearchCursor(matches_fc, match_fields) as cursor:
        for row in cursor:
            matches_data.append({
                'source': row[0],
                'distance_m': row[1],
                'building_key': row[2],
                'dc_code': row[3],
                'region_derived': row[4],
                'new_build_status': row[5]
            })

    df_matches = pd.DataFrame(matches_data)
    print(f"   ✅ Loaded {len(df_matches):,} total match records")

    # Validate source order against actual data
    actual_sources = df_matches['source'].unique().tolist()
    missing_sources = set(source_order) - set(actual_sources)
    extra_sources = set(actual_sources) - set(source_order)

    if missing_sources:
        print(f"   ⚠️  WARNING: Expected sources not found in data: {missing_sources}")
    if extra_sources:
        print(f"   ⚠️  WARNING: Unexpected sources found in data: {extra_sources}")

    # Use actual sources from data
    source_order = [s for s in source_order if s in actual_sources]
    print(f"   ✅ Analyzing {len(source_order)} sources: {', '.join(source_order)}")

    # Load canonical to get denominators
    canonical_fields = ['location_key', 'datacenter', 'dc_code', 'has_coordinates',
                        'region_derived', 'new_build_status']
    canonical_data = []

    with arcpy.da.SearchCursor(canonical_fc, canonical_fields) as cursor:
        for row in cursor:
            dc_code = row[2] if row[2] else ""
            datacenter = str(row[1]) if row[1] else ""
            building_key = f"{dc_code}-{datacenter}" if dc_code and datacenter else None
            canonical_data.append({
                'location_key': row[0],
                'building_key': building_key,
                'dc_code': row[2],
                'has_coordinates': row[3],
                'region_derived': row[4],
                'new_build_status': row[5]
            })

    df_canonical = pd.DataFrame(canonical_data)

    # Filter to valid coordinates
    df_canonical_valid = df_canonical[df_canonical['has_coordinates'] == 1].copy()
    total_campuses = df_canonical_valid['dc_code'].nunique()
    total_buildings = df_canonical_valid['building_key'].nunique()
    print(f"   ✅ Meta Canonical: {total_campuses} campuses, {total_buildings} buildings (has_coordinates=1)")

except Exception as e:
    print(f"   ❌ ERROR loading data: {e}")
    raise

# ============================================================================
# STEP 2: Deduplicate to Closest Match
# ============================================================================
print("\n🔧 STEP 2: Deduplicating to closest match per building/campus per source...")

df_clean = df_matches.dropna(subset=['distance_m', 'source'])

# Building-level deduplication
df_building = df_clean.dropna(subset=['building_key'])
df_building_dedup = df_building.loc[
    df_building.groupby(['building_key', 'source'])['distance_m'].idxmin()
].copy()

# Campus-level deduplication
df_campus = df_clean.dropna(subset=['dc_code'])
df_campus_dedup = df_campus.loc[
    df_campus.groupby(['dc_code', 'source'])['distance_m'].idxmin()
].copy()

print(f"   ✅ Building-level: {len(df_building_dedup):,} unique matches (from {len(df_building):,})")
print(f"   ✅ Campus-level: {len(df_campus_dedup):,} unique matches (from {len(df_campus):,})")

# ============================================================================
# STEP 2.5: Data Quality Checks
# ============================================================================
print("\n🔍 STEP 2.5: Data quality checks...")

# Check for missing building keys
missing_keys = df_matches[df_matches['building_key'].isna()].shape[0]
print(f"   Records with missing building_key: {missing_keys:,} ({missing_keys/len(df_matches)*100:.1f}%)")

# Check distance distribution
print(f"   Distance range: {df_matches['distance_m'].min():.0f}m - {df_matches['distance_m'].max():.0f}m")
print(f"   Overall median: {df_matches['distance_m'].median():.0f}m")

# Check for outliers (>50km)
outliers = df_matches[df_matches['distance_m'] > 50000].shape[0]
if outliers > 0:
    print(f"   ⚠️  WARNING: {outliers} matches >50km (possible data quality issues)")
    outlier_sources = df_matches[df_matches['distance_m'] > 50000]['source'].value_counts()
    print(f"   Outlier breakdown: {dict(outlier_sources)}")
else:
    print(f"   ✅ No extreme outliers (>50km) detected")

# ============================================================================
# HELPER FUNCTION: Calculate Comprehensive Stats
# ============================================================================
def calc_comprehensive_stats(df, source, total_count, granularity='building'):
    """Calculate full distribution statistics for a source"""
    src_data = df[df['source'] == source]['distance_m']

    if len(src_data) == 0:
        return {
            'source': source,
            'granularity': granularity,
            'recall_pct': 0.0,
            'count_detected': 0,
            'total_possible': total_count,
            'min': np.nan,
            'p10': np.nan,
            'p25': np.nan,
            'median': np.nan,
            'p75': np.nan,
            'p90': np.nan,
            'max': np.nan,
            'mean': np.nan,
            'std': np.nan,
            'mad': np.nan,
            'iqr': np.nan
        }

    return {
        'source': source,
        'granularity': granularity,
        'recall_pct': (len(src_data) / total_count * 100),
        'count_detected': len(src_data),
        'total_possible': total_count,
        'min': src_data.min(),
        'p10': src_data.quantile(0.10),
        'p25': src_data.quantile(0.25),
        'median': src_data.median(),
        'p75': src_data.quantile(0.75),
        'p90': src_data.quantile(0.90),
        'max': src_data.max(),
        'mean': src_data.mean(),
        'std': src_data.std(),
        'mad': (src_data - src_data.median()).abs().median(),
        'iqr': src_data.quantile(0.75) - src_data.quantile(0.25)
    }

# ============================================================================
# STEP 3: Campus-Level Statistics
# ============================================================================
print("\n📊 STEP 3: Calculating campus-level statistics...")

campus_stats = []
for i, source in enumerate(source_order, 1):
    print(f"   [{i}/{len(source_order)}] Processing {source}...".ljust(60), end='\r')
    stats = calc_comprehensive_stats(df_campus_dedup, source, total_campuses, 'campus')
    campus_stats.append(stats)

print(f"   ✅ Completed {len(source_order)} sources" + " " * 40)

df_campus_stats = pd.DataFrame(campus_stats)

# Save campus stats
campus_file = os.path.join(output_dir, f"campus_level_stats_{timestamp}.csv")
df_campus_stats.to_csv(campus_file, index=False, float_format='%.2f')
print(f"   ✅ Saved: campus_level_stats_{timestamp}.csv")

# ============================================================================
# STEP 4: Building-Level Statistics
# ============================================================================
print("\n📊 STEP 4: Calculating building-level statistics...")

building_stats = []
for i, source in enumerate(source_order, 1):
    print(f"   [{i}/{len(source_order)}] Processing {source}...".ljust(60), end='\r')
    stats = calc_comprehensive_stats(df_building_dedup, source, total_buildings, 'building')
    building_stats.append(stats)

print(f"   ✅ Completed {len(source_order)} sources" + " " * 40)

df_building_stats = pd.DataFrame(building_stats)

# Save building stats
building_file = os.path.join(output_dir, f"building_level_stats_{timestamp}.csv")
df_building_stats.to_csv(building_file, index=False, float_format='%.2f')
print(f"   ✅ Saved: building_level_stats_{timestamp}.csv")

# ============================================================================
# STEP 4.5: Semianalysis-Specific Validation
# ============================================================================
print("\n🔬 STEP 4.5: Semianalysis-specific validation...")

semi_data = df_building_dedup[df_building_dedup['source'] == 'Semianalysis']
if len(semi_data) > 0:
    print(f"   Buildings detected: {len(semi_data)}")
    print(f"   Campuses covered: {semi_data['dc_code'].nunique()}")
    print(f"   Median distance: {semi_data['distance_m'].median():.0f}m")
    print(f"   Expected ~178 buildings from ingestion")

    if len(semi_data) < 150:
        print(f"   ⚠️  WARNING: Lower than expected! Check matches_fc generation.")
    else:
        print(f"   ✅ Building count matches expectations")
else:
    print(f"   ❌ ERROR: No Semianalysis records found in matches!")
    print(f"   Check if accuracy_analysis_multi_source includes Semianalysis")

# ============================================================================
# STEP 5: Regional Breakdown
# ============================================================================
print("\n🌍 STEP 5: Calculating regional breakdown...")

regions = ['AMER', 'APAC', 'EMEA']
regional_stats = []

for region in regions:
    # Get denominators for this region
    region_canonical = df_canonical_valid[df_canonical_valid['region_derived'] == region]
    region_campuses = region_canonical['dc_code'].nunique()
    region_buildings = region_canonical['building_key'].nunique()

    # Get matches for this region
    region_matches = df_building_dedup[df_building_dedup['region_derived'] == region]

    for source in source_order:
        src_data = region_matches[region_matches['source'] == source]['distance_m']

        regional_stats.append({
            'region': region,
            'source': source,
            'campus_denominator': region_campuses,
            'building_denominator': region_buildings,
            'buildings_detected': len(src_data),
            'recall_pct': (len(src_data) / region_buildings * 100) if region_buildings > 0 else 0,
            'median_distance': src_data.median() if len(src_data) > 0 else np.nan,
            'mean_distance': src_data.mean() if len(src_data) > 0 else np.nan,
            'mad': (src_data - src_data.median()).abs().median() if len(src_data) > 0 else np.nan,
            'min': src_data.min() if len(src_data) > 0 else np.nan,
            'max': src_data.max() if len(src_data) > 0 else np.nan
        })

df_regional = pd.DataFrame(regional_stats)

# Save regional stats
regional_file = os.path.join(output_dir, f"stats_by_region_{timestamp}.csv")
df_regional.to_csv(regional_file, index=False, float_format='%.2f')
print(f"   ✅ Saved: stats_by_region_{timestamp}.csv")

# ============================================================================
# STEP 6: Build Status Breakdown
# ============================================================================
print("\n🏗️ STEP 6: Calculating build status breakdown...")

statuses = ['Complete Build', 'Active Build', 'Future Build']
status_stats = []

for status in statuses:
    # Get denominators for this status
    status_canonical = df_canonical_valid[df_canonical_valid['new_build_status'] == status]
    status_campuses = status_canonical['dc_code'].nunique()
    status_buildings = status_canonical['building_key'].nunique()

    # Get matches for this status
    status_matches = df_building_dedup[df_building_dedup['new_build_status'] == status]

    for source in source_order:
        src_data = status_matches[status_matches['source'] == source]['distance_m']

        status_stats.append({
            'build_status': status,
            'source': source,
            'campus_denominator': status_campuses,
            'building_denominator': status_buildings,
            'buildings_detected': len(src_data),
            'recall_pct': (len(src_data) / status_buildings * 100) if status_buildings > 0 else 0,
            'median_distance': src_data.median() if len(src_data) > 0 else np.nan,
            'mean_distance': src_data.mean() if len(src_data) > 0 else np.nan,
            'mad': (src_data - src_data.median()).abs().median() if len(src_data) > 0 else np.nan,
            'min': src_data.min() if len(src_data) > 0 else np.nan,
            'max': src_data.max() if len(src_data) > 0 else np.nan
        })

df_status = pd.DataFrame(status_stats)

# Save status stats
status_file = os.path.join(output_dir, f"stats_by_buildstatus_{timestamp}.csv")
df_status.to_csv(status_file, index=False, float_format='%.2f')
print(f"   ✅ Saved: stats_by_buildstatus_{timestamp}.csv")

# ============================================================================
# STEP 7: Threshold Performance
# ============================================================================
print("\n📏 STEP 7: Calculating threshold performance...")

thresholds = [100, 500, 1000, 3000, 5000]
threshold_stats = []

for source in source_order:
    src_data = df_building_dedup[df_building_dedup['source'] == source]['distance_m']

    if len(src_data) == 0:
        threshold_stats.append({
            'source': source,
            'total_matches': 0,
            'within_100m': 0,
            'within_500m': 0,
            'within_1km': 0,
            'within_3km': 0,
            'within_5km': 0,
            'pct_within_100m': 0,
            'pct_within_500m': 0,
            'pct_within_1km': 0,
            'pct_within_3km': 0,
            'pct_within_5km': 0,
            'excellent_lt1km': 0,
            'good_1to3km': 0,
            'fair_3to5km': 0
        })
        continue

    total = len(src_data)
    within_100 = (src_data <= 100).sum()
    within_500 = (src_data <= 500).sum()
    within_1k = (src_data <= 1000).sum()
    within_3k = (src_data <= 3000).sum()
    within_5k = (src_data <= 5000).sum()

    excellent = (src_data < 1000).sum()
    good = ((src_data >= 1000) & (src_data < 3000)).sum()
    fair = ((src_data >= 3000) & (src_data <= 5000)).sum()

    threshold_stats.append({
        'source': source,
        'total_matches': total,
        'within_100m': within_100,
        'within_500m': within_500,
        'within_1km': within_1k,
        'within_3km': within_3k,
        'within_5km': within_5k,
        'pct_within_100m': (within_100 / total * 100),
        'pct_within_500m': (within_500 / total * 100),
        'pct_within_1km': (within_1k / total * 100),
        'pct_within_3km': (within_3k / total * 100),
        'pct_within_5km': (within_5k / total * 100),
        'excellent_lt1km': excellent,
        'good_1to3km': good,
        'fair_3to5km': fair
    })

df_thresholds = pd.DataFrame(threshold_stats)

# Save threshold stats
threshold_file = os.path.join(output_dir, f"threshold_performance_{timestamp}.csv")
df_thresholds.to_csv(threshold_file, index=False, float_format='%.2f')
print(f"   ✅ Saved: threshold_performance_{timestamp}.csv")

# ============================================================================
# STEP 8: Worst-Case Analysis
# ============================================================================
print("\n⚠️ STEP 8: Identifying worst-case errors...")

worst_case = []
for source in source_order:
    src_matches = df_building_dedup[df_building_dedup['source'] == source].copy()
    src_matches = src_matches.nlargest(25, 'distance_m')[
        ['source', 'dc_code', 'building_key', 'distance_m', 'region_derived', 'new_build_status']
    ]
    worst_case.append(src_matches)

df_worst = pd.concat(worst_case, ignore_index=True)

# Save worst-case stats
worst_file = os.path.join(output_dir, f"worst_case_errors_{timestamp}.csv")
df_worst.to_csv(worst_file, index=False, float_format='%.2f')
print(f"   ✅ Saved: worst_case_errors_{timestamp}.csv")

# ============================================================================
# STEP 9: Granularity Comparison
# ============================================================================
print("\n📊 STEP 9: Creating granularity comparison table...")

granularity_comparison = []
for source in source_order:
    campus_row = df_campus_stats[df_campus_stats['source'] == source].iloc[0]
    building_row = df_building_stats[df_building_stats['source'] == source].iloc[0]

    granularity_comparison.append({
        'source': source,
        'campus_recall_pct': campus_row['recall_pct'],
        'campus_count': campus_row['count_detected'],
        'campus_median': campus_row['median'],
        'building_recall_pct': building_row['recall_pct'],
        'building_count': building_row['count_detected'],
        'building_median': building_row['median'],
        'recall_improvement_pct': building_row['recall_pct'] - campus_row['recall_pct']
    })

df_granularity = pd.DataFrame(granularity_comparison)

# Save granularity comparison
granularity_file = os.path.join(output_dir, f"granularity_comparison_{timestamp}.csv")
df_granularity.to_csv(granularity_file, index=False, float_format='%.2f')
print(f"   ✅ Saved: granularity_comparison_{timestamp}.csv")

# ============================================================================
# STEP 9.5: Source Comparison Summary
# ============================================================================
print("\n📊 STEP 9.5: Creating source comparison summary table...")

comparison_table = df_building_stats[['source', 'recall_pct', 'count_detected',
                                       'median', 'mad', 'min', 'max']].copy()
comparison_table.columns = ['Source', 'Recall %', 'Buildings', 'Median (m)',
                            'MAD (m)', 'Min (m)', 'Max (m)']
comparison_table = comparison_table.sort_values('Median (m)')

comparison_file = os.path.join(output_dir, f"source_comparison_summary_{timestamp}.csv")
comparison_table.to_csv(comparison_file, index=False, float_format='%.1f')
print(f"   ✅ Saved: source_comparison_summary_{timestamp}.csv")

# ============================================================================
# STEP 10: Executive Summary Report (TXT)
# ============================================================================
print("\n📝 STEP 10: Generating executive summary report...")

summary_file = os.path.join(output_dir, f"comprehensive_report_{timestamp}.txt")

# Calculate best performers for quick summary
best_recall = df_building_stats.loc[df_building_stats['recall_pct'].idxmax()]
best_spatial = df_building_stats.loc[df_building_stats['median'].idxmin()]
best_consistency = df_building_stats.loc[df_building_stats['mad'].idxmin()]
worst_source = df_building_stats.loc[df_building_stats['median'].idxmax()]

with open(summary_file, 'w', encoding='utf-8') as f:
    f.write("=" * 80 + "\n")
    f.write(" " * 20 + "SPATIAL ACCURACY ANALYSIS\n")
    f.write(" " * 15 + "Meta Canonical vs. External Sources\n")
    f.write(" " * 20 + "(DEDUPLICATED RESULTS)\n")
    f.write("=" * 80 + "\n")
    f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

    # QUICK METRICS SUMMARY
    f.write("QUICK METRICS:\n")
    f.write(f"  • Meta Canonical: {total_campuses} campuses, {total_buildings} buildings\n")
    f.write(f"  • External Matches: {len(df_building_dedup):,} deduplicated building-level\n")
    f.write(f"  • Best Recall: {best_recall['source']} ({best_recall['recall_pct']:.1f}%)\n")
    f.write(f"  • Best Spatial: {best_spatial['source']} ({best_spatial['median']:.0f}m median)\n")
    f.write(f"  • Best Consistency: {best_consistency['source']} ({best_consistency['mad']:.0f}m MAD)\n")
    f.write(f"  • Sources Evaluated: {len(source_order)}\n")
    f.write("\n")

    # Source Rankings
    f.write("=" * 80 + "\n")
    f.write("🏆 SOURCE RANKINGS\n")
    f.write("=" * 80 + "\n\n")

    # By Recall (FIXED RANKING BUG)
    f.write("BY RECALL (Building-Level):\n")
    df_building_stats_sorted = df_building_stats.sort_values('recall_pct', ascending=False)
    for rank, (idx, row) in enumerate(df_building_stats_sorted.iterrows()):
        medal = ['🥇', '🥈', '🥉', '4️⃣', '5️⃣', '6️⃣'][rank]
        f.write(f"  {medal} {row['source']:<20} {row['recall_pct']:>5.1f}% ({row['count_detected']}/{row['total_possible']} buildings)\n")
    f.write("\n")

    # By Spatial Accuracy (FIXED RANKING BUG)
    f.write("BY SPATIAL ACCURACY (Median Distance):\n")
    df_building_stats_sorted = df_building_stats.sort_values('median', ascending=True)
    for rank, (idx, row) in enumerate(df_building_stats_sorted.iterrows()):
        medal = ['🥇', '🥈', '🥉', '4️⃣', '5️⃣', '6️⃣'][rank]
        median_val = row['median'] if not pd.isna(row['median']) else 0
        f.write(f"  {medal} {row['source']:<20} {median_val:>6.0f}m\n")
    f.write("\n")

    # By Consistency (FIXED RANKING BUG)
    f.write("BY CONSISTENCY (MAD - Median Absolute Deviation):\n")
    df_building_stats_sorted = df_building_stats.sort_values('mad', ascending=True)
    for rank, (idx, row) in enumerate(df_building_stats_sorted.iterrows()):
        medal = ['🥇', '🥈', '🥉', '4️⃣', '5️⃣', '6️⃣'][rank]
        mad_val = row['mad'] if not pd.isna(row['mad']) else 0
        f.write(f"  {medal} {row['source']:<20} {mad_val:>6.0f}m\n")
    f.write("\n")

    # Campus-Level Statistics Table
    f.write("=" * 80 + "\n")
    f.write("📊 CAMPUS-LEVEL STATISTICS (62 campuses)\n")
    f.write("=" * 80 + "\n\n")
    f.write(df_campus_stats.to_string(index=False, float_format=lambda x: f'{x:.1f}'))
    f.write("\n\n")

    # Building-Level Statistics Table
    f.write("=" * 80 + "\n")
    f.write("📊 BUILDING-LEVEL STATISTICS (276 buildings)\n")
    f.write("=" * 80 + "\n\n")
    f.write(df_building_stats.to_string(index=False, float_format=lambda x: f'{x:.1f}'))
    f.write("\n\n")

    # Regional Performance
    f.write("=" * 80 + "\n")
    f.write("🌍 REGIONAL PERFORMANCE\n")
    f.write("=" * 80 + "\n\n")
    for region in regions:
        region_data = df_regional[df_regional['region'] == region]
        if len(region_data) > 0:
            region_denom = region_data.iloc[0]['building_denominator']
            f.write(f"{region} ({region_denom} buildings):\n")
            for _, row in region_data.iterrows():
                recall = row['recall_pct']
                median = row['median_distance'] if not pd.isna(row['median_distance']) else 0
                f.write(f"  {row['source']:<20} {recall:>5.1f}% recall, {median:>6.0f}m median\n")
            f.write("\n")

    # Build Status Performance
    f.write("=" * 80 + "\n")
    f.write("🏗️ BUILD STATUS PERFORMANCE\n")
    f.write("=" * 80 + "\n\n")
    for status in statuses:
        status_data = df_status[df_status['build_status'] == status]
        if len(status_data) > 0:
            status_denom = status_data.iloc[0]['building_denominator']
            f.write(f"{status} ({status_denom} buildings):\n")
            for _, row in status_data.iterrows():
                recall = row['recall_pct']
                median = row['median_distance'] if not pd.isna(row['median_distance']) else 0
                f.write(f"  {row['source']:<20} {recall:>5.1f}% recall, {median:>6.0f}m median\n")
            f.write("\n")

    # Threshold Performance
    f.write("=" * 80 + "\n")
    f.write("📏 THRESHOLD PERFORMANCE (% within distance)\n")
    f.write("=" * 80 + "\n\n")
    f.write(df_thresholds.to_string(index=False, float_format=lambda x: f'{x:.1f}'))
    f.write("\n\n")

    # Key Findings
    f.write("=" * 80 + "\n")
    f.write("📊 KEY FINDINGS\n")
    f.write("=" * 80 + "\n\n")

    f.write("✅ STRENGTHS:\n")
    f.write(f"  • {best_recall['source']}: Best recall ({best_recall['recall_pct']:.1f}%)\n")
    f.write(f"  • {best_spatial['source']}: Best spatial accuracy ({best_spatial['median']:.0f}m median)\n")
    f.write(f"  • {best_consistency['source']}: Most consistent ({best_consistency['mad']:.0f}m MAD)\n")
    f.write("\n")

    f.write("⚠️ WEAKNESSES:\n")
    f.write(f"  • {worst_source['source']}: Poorest spatial accuracy ({worst_source['median']:.0f}m median)\n")

    # Regional gaps
    non_us_sources = df_regional[
        (df_regional['region'].isin(['APAC', 'EMEA'])) &
        (df_regional['recall_pct'] == 0)
    ]['source'].unique()
    if len(non_us_sources) > 0:
        f.write(f"  • {', '.join(non_us_sources)}: 0% recall in APAC/EMEA (US-only coverage)\n")
    f.write("\n")

    f.write("🌍 REGIONAL COVERAGE GAPS:\n")
    for region in ['APAC', 'EMEA']:
        region_data = df_regional[df_regional['region'] == region]
        zero_recall = region_data[region_data['recall_pct'] == 0]['source'].tolist()
        if zero_recall:
            f.write(f"  • {region}: {', '.join(zero_recall)} have 0% recall\n")
    f.write("\n")

    # Recommendations
    f.write("=" * 80 + "\n")
    f.write("🎯 RECOMMENDATIONS FOR CONSENSUS MODEL\n")
    f.write("=" * 80 + "\n\n")

    f.write("SPATIAL COORDINATE PRIORITY (REVISED):\n")
    top3_spatial = df_building_stats.nsmallest(3, 'median')
    for rank, (idx, row) in enumerate(top3_spatial.iterrows(), 1):
        f.write(f"  {rank}. {row['source']} ({row['median']:.0f}m median)\n")
    f.write("\n")

    f.write("CAPACITY DATA PRIORITY:\n")
    f.write("  1. DataCenterHawk: current_capacity_mw (commissioned + UC)\n")
    f.write("  2. Semianalysis: ultimate_capacity_mw (mw_2032 forecast)\n")
    f.write("\n")

    f.write("EXCLUSIONS:\n")
    f.write("  • Synergy: Include in accuracy reports for transparency\n")
    f.write("  • Synergy: EXCLUDE from consensus scoring (poor spatial + low recall)\n")
    f.write("\n")

    f.write("QUALITY SCORE BANDS:\n")
    f.write("  • High Confidence: ≥3 sources, distance <1km, has capacity data\n")
    f.write("  • Medium Confidence: 2 sources, distance 1-3km\n")
    f.write("  • Low Confidence: 1 source, distance >3km (flag for manual review)\n")
    f.write("\n")

    f.write("=" * 80 + "\n")

print(f"   ✅ Saved: comprehensive_report_{timestamp}.txt")

# ============================================================================
# COMPLETION SUMMARY
# ============================================================================
print("\n" + "=" * 80)
print("✅ COMPREHENSIVE ANALYSIS COMPLETE!")
print("=" * 80)
print(f"⏰ Finished: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
print("📁 Generated files:")
print(f"   1. campus_level_stats_{timestamp}.csv")
print(f"   2. building_level_stats_{timestamp}.csv")
print(f"   3. stats_by_region_{timestamp}.csv")
print(f"   4. stats_by_buildstatus_{timestamp}.csv")
print(f"   5. threshold_performance_{timestamp}.csv")
print(f"   6. worst_case_errors_{timestamp}.csv")
print(f"   7. granularity_comparison_{timestamp}.csv")
print(f"   8. source_comparison_summary_{timestamp}.csv (NEW)")
print(f"   9. comprehensive_report_{timestamp}.txt (EXECUTIVE SUMMARY)")
print("\n📊 Summary Statistics:")
print(f"   • Total campuses analyzed: {total_campuses}")
print(f"   • Total buildings analyzed: {total_buildings}")
print(f"   • Total match records: {len(df_matches):,} → {len(df_building_dedup):,} deduplicated")
print(f"   • Sources evaluated: {len(source_order)}")
print(f"   • Regions covered: {len(regions)}")
print(f"   • Build statuses: {len(statuses)}")
print("\n🎯 Ready for supervisor presentation!")
print("=" * 80)
print("\n📊 Quick Summary:")
