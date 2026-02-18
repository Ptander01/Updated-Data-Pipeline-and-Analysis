"""
Spatial Accuracy Box Plots & Violin Plots - LIGHT THEME
Generates 6 publication-quality visualizations with deduplicated data
Author: Data Center Consensus GIS Model Team
Date: 2025-12-04 (Updated to light theme)
"""

import arcpy
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime
import os

# ============================================================================
# CONFIGURATION
# ============================================================================

# Paths
gdb_path = r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\Default.gdb"
accuracy_fc = os.path.join(gdb_path, "accuracy_analysis_multi_source_REBUILT")  # Updated Dec 10, 2024 - uses current building-level coords
meta_canonical_fc = os.path.join(gdb_path, "meta_canonical_v2")
output_dir = r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\outputs\accuracy\plots"

# Create output directory if it doesn't exist
os.makedirs(output_dir, exist_ok=True)

# Timestamp for output files
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

# Source display names (for consistent labeling)
source_labels = {
    'DataCenterHawk': 'DataCenterHawk',
    'Semianalysis': 'Semianalysis',
    'DataCenterMap': 'DataCenterMap',
    'NewProjectMedia': 'NewProjectMedia',
    'WoodMac': 'WoodMac',
    'Synergy': 'Synergy'
}

# Color palette (light theme - original aesthetic)
source_colors = {
    'DataCenterHawk': '#5dade2',      # Sky blue
    'Semianalysis': '#af7ac5',        # Purple
    'DataCenterMap': '#f4d03f',       # Gold
    'NewProjectMedia': '#ec7063',     # Coral/salmon
    'WoodMac': '#58d68d',             # Green
    'Synergy': '#cb4335'              # Dark red/maroon
}

print("=" * 80)
print("📊 SPATIAL ACCURACY VISUALIZATIONS - LIGHT THEME")
print("=" * 80)
print(f"⏰ Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

# ============================================================================
# STEP 1: LOAD DATA
# ============================================================================

print("📋 STEP 1: Loading spatial accuracy data...")

# Load accuracy analysis
fields = ['source', 'dc_code', 'datacenter', 'distance_m', 'region_derived', 'new_build_status']
data = []
with arcpy.da.SearchCursor(accuracy_fc, fields) as cursor:
    for row in cursor:
        data.append(row)

df = pd.DataFrame(data, columns=fields)
print(f"   ✅ Loaded {len(df):,} total match records")

# Load Meta canonical for denominators
meta_fields = ['dc_code', 'datacenter', 'has_coordinates']
meta_data = []
with arcpy.da.SearchCursor(meta_canonical_fc, meta_fields) as cursor:
    for row in cursor:
        meta_data.append(row)

df_meta = pd.DataFrame(meta_data, columns=meta_fields)
df_meta_valid = df_meta[df_meta['has_coordinates'] == 1].copy()

# Calculate denominators
unique_campuses = df_meta_valid['dc_code'].nunique()
df_meta_valid['building_key'] = df_meta_valid['dc_code'] + "-" + df_meta_valid['datacenter'].astype(str)
unique_buildings = df_meta_valid['building_key'].nunique()

print(f"   ✅ Meta Canonical: {unique_campuses} campuses, {unique_buildings} buildings (has_coordinates=1)\n")

# ============================================================================
# STEP 2: DEDUPLICATION
# ============================================================================

print("🔧 STEP 2: Deduplicating to closest match per building/campus per source...")

# Create composite building key
df['building_key'] = df['dc_code'] + "-" + df['datacenter'].astype(str)

# Building-level deduplication (closest match per building per source)
df_building_dedup = df.loc[
    df.groupby(['building_key', 'source'])['distance_m'].idxmin()
].copy()

# Campus-level deduplication (closest match per campus per source)
df_campus_dedup = df.loc[
    df.groupby(['dc_code', 'source'])['distance_m'].idxmin()
].copy()

print(f"   ✅ Building-level: {len(df_building_dedup):,} unique matches (from {len(df):,})")
print(f"   ✅ Campus-level: {len(df_campus_dedup):,} unique matches (from {len(df):,})\n")

# ============================================================================
# PLOT STYLING (LIGHT THEME)
# ============================================================================

# Set seaborn style for light theme
sns.set_style("whitegrid")
plt.rcParams.update({
    'figure.facecolor': 'white',
    'axes.facecolor': 'white',
    'axes.edgecolor': '#333333',
    'axes.labelcolor': '#333333',
    'text.color': '#333333',
    'xtick.color': '#333333',
    'ytick.color': '#333333',
    'grid.color': '#cccccc',
    'grid.linestyle': '--',
    'grid.alpha': 0.5,
    'font.size': 10,
    'axes.titlesize': 14,
    'axes.labelsize': 11,
    'xtick.labelsize': 10,
    'ytick.labelsize': 10,
    'legend.fontsize': 10,
    'figure.titlesize': 16
})

# ============================================================================
# PLOT 1: BUILDING-LEVEL BY SOURCE (BOX PLOT)
# ============================================================================

print("📊 PLOT 1: Building-level spatial accuracy by source (box plot)...")

fig, ax = plt.subplots(figsize=(14, 8))

# Prepare data
sources = ['DataCenterHawk', 'Semianalysis', 'DataCenterMap', 'NewProjectMedia', 'WoodMac', 'Synergy']
plot_data = [df_building_dedup[df_building_dedup['source'] == src]['distance_m'].values
             for src in sources]

# Create box plot
bp = ax.boxplot(plot_data,
                labels=[source_labels[s] for s in sources],
                patch_artist=True,
                widths=0.6,
                showmeans=True,
                meanprops=dict(marker='D', markerfacecolor='red', markeredgecolor='red', markersize=8))

# Color boxes
for patch, source in zip(bp['boxes'], sources):
    patch.set_facecolor(source_colors[source])
    patch.set_alpha(0.7)

# Add observation counts
for i, source in enumerate(sources, 1):
    count = len(df_building_dedup[df_building_dedup['source'] == source])
    mean_val = df_building_dedup[df_building_dedup['source'] == source]['distance_m'].mean()
    ax.text(i, ax.get_ylim()[1] * 0.95, f'n={count}',
            ha='center', va='top', fontsize=9, color='#333333')

# Reference lines
ax.axhline(y=1000, color='green', linestyle='--', linewidth=1.5, alpha=0.7, label='1km (Excellent)')
ax.axhline(y=3000, color='orange', linestyle='--', linewidth=1.5, alpha=0.7, label='3km (Good)')

# Labels and formatting
ax.set_ylabel('Distance Error (meters)', fontsize=12, fontweight='bold')
ax.set_xlabel('Source', fontsize=12, fontweight='bold')
ax.set_title('Spatial Accuracy by Source (Building-Level)\nRed ◆ = mean | Green line = median | Deduplicated to closest match per building',
             fontsize=14, fontweight='bold', pad=20)
ax.legend(loc='upper right', framealpha=0.9)
ax.grid(True, alpha=0.3)
plt.xticks(rotation=15, ha='right')
plt.tight_layout()

# Save
output_file = os.path.join(output_dir, f'building_level_by_source_{timestamp}.png')
plt.savefig(output_file, dpi=300, bbox_inches='tight', facecolor='white')
plt.close()
print(f"   ✅ Saved: {output_file}\n")

# ============================================================================
# PLOT 2: GRANULARITY COMPARISON (CAMPUS VS BUILDING)
# ============================================================================

print("📊 PLOT 2: Granularity comparison (campus vs building)...")

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 7))

# Campus-level (left panel)
campus_data = [df_campus_dedup[df_campus_dedup['source'] == src]['distance_m'].values
               for src in sources]
bp1 = ax1.boxplot(campus_data,
                  labels=[source_labels[s] for s in sources],
                  patch_artist=True,
                  widths=0.6,
                  showmeans=True,
                  meanprops=dict(marker='D', markerfacecolor='red', markeredgecolor='red', markersize=8))

for patch, source in zip(bp1['boxes'], sources):
    patch.set_facecolor(source_colors[source])
    patch.set_alpha(0.7)

for i, source in enumerate(sources, 1):
    count = len(df_campus_dedup[df_campus_dedup['source'] == source])
    ax1.text(i, ax1.get_ylim()[1] * 0.95, f'n={count}',
             ha='center', va='top', fontsize=9, color='#333333')

ax1.axhline(y=1000, color='green', linestyle='--', linewidth=1.5, alpha=0.7)
ax1.axhline(y=3000, color='orange', linestyle='--', linewidth=1.5, alpha=0.7)
ax1.set_ylabel('Distance Error (meters)', fontsize=12, fontweight='bold')
ax1.set_xlabel('Source', fontsize=12, fontweight='bold')
ax1.set_title(f'Campus-Level Spatial Accuracy\n({unique_campuses} unique campuses)',
              fontsize=13, fontweight='bold')
ax1.grid(True, alpha=0.3)
ax1.tick_params(axis='x', rotation=15)

# Building-level (right panel)
bp2 = ax2.boxplot(plot_data,
                  labels=[source_labels[s] for s in sources],
                  patch_artist=True,
                  widths=0.6,
                  showmeans=True,
                  meanprops=dict(marker='D', markerfacecolor='red', markeredgecolor='red', markersize=8))

for patch, source in zip(bp2['boxes'], sources):
    patch.set_facecolor(source_colors[source])
    patch.set_alpha(0.7)

for i, source in enumerate(sources, 1):
    count = len(df_building_dedup[df_building_dedup['source'] == source])
    ax2.text(i, ax2.get_ylim()[1] * 0.95, f'n={count}',
             ha='center', va='top', fontsize=9, color='#333333')

ax2.axhline(y=1000, color='green', linestyle='--', linewidth=1.5, alpha=0.7)
ax2.axhline(y=3000, color='orange', linestyle='--', linewidth=1.5, alpha=0.7)
ax2.set_ylabel('Distance Error (meters)', fontsize=12, fontweight='bold')
ax2.set_xlabel('Source', fontsize=12, fontweight='bold')
ax2.set_title(f'Building-Level Spatial Accuracy\n({unique_buildings} unique buildings)',
              fontsize=13, fontweight='bold')
ax2.grid(True, alpha=0.3)
ax2.tick_params(axis='x', rotation=15)

plt.suptitle('Spatial Accuracy Comparison: Campus-Level vs Building-Level',
             fontsize=15, fontweight='bold', y=1.00)
plt.tight_layout()

output_file = os.path.join(output_dir, f'granularity_comparison_{timestamp}.png')
plt.savefig(output_file, dpi=300, bbox_inches='tight', facecolor='white')
plt.close()
print(f"   ✅ Saved: {output_file}\n")

# ============================================================================
# PLOT 3: BY REGION
# ============================================================================

print("📊 PLOT 3: Spatial accuracy by region...")

fig, ax = plt.subplots(figsize=(16, 8))

# Prepare data by region
regions = ['AMER', 'APAC', 'EMEA']
x_positions = []
labels = []
colors = []
region_data = []

x = 0
for region in regions:
    df_region = df_building_dedup[df_building_dedup['region_derived'] == region]
    for source in sources:
        df_source = df_region[df_region['source'] == source]
        if len(df_source) > 0:
            region_data.append(df_source['distance_m'].values)
            x_positions.append(x)
            labels.append(f'{source_labels[source]}\n{region}')
            colors.append(source_colors[source])
            x += 1
    x += 0.5  # Gap between regions

# Create box plot
bp = ax.boxplot(region_data,
                positions=x_positions,
                patch_artist=True,
                widths=0.6,
                showmeans=True,
                meanprops=dict(marker='D', markerfacecolor='red', markeredgecolor='red', markersize=7))

for patch, color in zip(bp['boxes'], colors):
    patch.set_facecolor(color)
    patch.set_alpha(0.7)

ax.axhline(y=1000, color='green', linestyle='--', linewidth=1.5, alpha=0.7, label='1km')
ax.axhline(y=3000, color='orange', linestyle='--', linewidth=1.5, alpha=0.7, label='3km')

ax.set_xticks(x_positions)
ax.set_xticklabels(labels, rotation=45, ha='right', fontsize=9)
ax.set_ylabel('Distance Error (meters)', fontsize=12, fontweight='bold')
ax.set_xlabel('Source', fontsize=12, fontweight='bold')
ax.set_title('Spatial Accuracy by Region and Source (Building-Level, Deduplicated)',
             fontsize=14, fontweight='bold', pad=20)
ax.legend(loc='upper right', framealpha=0.9)
ax.grid(True, alpha=0.3, axis='y')
plt.tight_layout()

output_file = os.path.join(output_dir, f'by_region_{timestamp}.png')
plt.savefig(output_file, dpi=300, bbox_inches='tight', facecolor='white')
plt.close()
print(f"   ✅ Saved: {output_file}\n")

# ============================================================================
# PLOT 4: BY BUILD STATUS
# ============================================================================

print("📊 PLOT 4: Spatial accuracy by build status...")

fig, ax = plt.subplots(figsize=(18, 8))

# Prepare data by build status
build_statuses = ['Complete Build', 'Active Build', 'Future Build']
x_positions = []
labels = []
colors = []
status_data = []

x = 0
for status in build_statuses:
    df_status = df_building_dedup[df_building_dedup['new_build_status'] == status]
    for source in sources:
        df_source = df_status[df_status['source'] == source]
        if len(df_source) > 0:
            status_data.append(df_source['distance_m'].values)
            x_positions.append(x)
            # Use short source names for build status plot
            short_name = source.replace('DataCenterHawk', 'DataCe').replace('Semianalysis', 'Semian').replace('NewProjectMedia', 'NewPro').replace('WoodMac', 'WoodMa')
            labels.append(f'{short_name}\n{status.split()[0]}')
            colors.append(source_colors[source])
            x += 1
    x += 0.5

bp = ax.boxplot(status_data,
                positions=x_positions,
                patch_artist=True,
                widths=0.6,
                showmeans=True,
                meanprops=dict(marker='D', markerfacecolor='red', markeredgecolor='red', markersize=7))

for patch, color in zip(bp['boxes'], colors):
    patch.set_facecolor(color)
    patch.set_alpha(0.7)

ax.axhline(y=1000, color='green', linestyle='--', linewidth=1.5, alpha=0.7, label='1km')
ax.axhline(y=3000, color='orange', linestyle='--', linewidth=1.5, alpha=0.7, label='3km')

ax.set_xticks(x_positions)
ax.set_xticklabels(labels, rotation=45, ha='right', fontsize=9)
ax.set_ylabel('Distance Error (meters)', fontsize=12, fontweight='bold')
ax.set_xlabel('Source', fontsize=12, fontweight='bold')
ax.set_title('Spatial Accuracy by Build Status and Source (Building-Level, Deduplicated)',
             fontsize=14, fontweight='bold', pad=20)
ax.legend(loc='upper right', framealpha=0.9)
ax.grid(True, alpha=0.3, axis='y')
plt.tight_layout()

output_file = os.path.join(output_dir, f'by_buildstatus_{timestamp}.png')
plt.savefig(output_file, dpi=300, bbox_inches='tight', facecolor='white')
plt.close()
print(f"   ✅ Saved: {output_file}\n")

# ============================================================================
# PLOT 5: BUILDING-LEVEL VIOLIN PLOT
# ============================================================================

print("📊 PLOT 5: Building-level violin plot...")

fig, ax = plt.subplots(figsize=(16, 9))

# Create violin plot
parts = ax.violinplot(plot_data,
                      positions=range(1, len(sources) + 1),
                      widths=0.7,
                      showmeans=False,
                      showmedians=True)

# Color violins
for i, (pc, source) in enumerate(zip(parts['bodies'], sources)):
    pc.set_facecolor(source_colors[source])
    pc.set_alpha(0.7)
    pc.set_edgecolor('#333333')
    pc.set_linewidth(1.5)

# Style median lines
parts['cmedians'].set_edgecolor('blue')
parts['cmedians'].set_linewidth(2.5)

# Add observation counts
for i, source in enumerate(sources, 1):
    count = len(df_building_dedup[df_building_dedup['source'] == source])
    ax.text(i, ax.get_ylim()[1] * 0.98, f'n={count}',
            ha='center', va='top', fontsize=10, fontweight='bold', color='#333333')

# Reference lines
ax.axhline(y=1000, color='green', linestyle='--', linewidth=2, alpha=0.7, label='1km')
ax.axhline(y=3000, color='orange', linestyle='--', linewidth=2, alpha=0.7, label='3km')

ax.set_xticks(range(1, len(sources) + 1))
ax.set_xticklabels([source_labels[s] for s in sources], rotation=15, ha='right')
ax.set_ylabel('Distance Error (meters)', fontsize=13, fontweight='bold')
ax.set_xlabel('Source', fontsize=13, fontweight='bold')
ax.set_title('Spatial Accuracy Distribution by Source (Building-Level, Deduplicated)\nViolin plot shows full data distribution shape',
             fontsize=15, fontweight='bold', pad=20)
ax.legend(loc='upper right', fontsize=11, framealpha=0.9)
ax.grid(True, alpha=0.3, axis='y')
plt.tight_layout()

output_file = os.path.join(output_dir, f'building_violin_{timestamp}.png')
plt.savefig(output_file, dpi=300, bbox_inches='tight', facecolor='white')
plt.close()
print(f"   ✅ Saved: {output_file}\n")

# ============================================================================
# PLOT 6: CAMPUS-LEVEL VIOLIN PLOT (NEW!)
# ============================================================================

print("📊 PLOT 6: Campus-level violin plot (NEW)...")

fig, ax = plt.subplots(figsize=(16, 9))

# Prepare campus-level data
campus_plot_data = [df_campus_dedup[df_campus_dedup['source'] == src]['distance_m'].values
                    for src in sources]

# Create violin plot
parts = ax.violinplot(campus_plot_data,
                      positions=range(1, len(sources) + 1),
                      widths=0.7,
                      showmeans=False,
                      showmedians=True)

# Color violins
for i, (pc, source) in enumerate(zip(parts['bodies'], sources)):
    pc.set_facecolor(source_colors[source])
    pc.set_alpha(0.7)
    pc.set_edgecolor('#333333')
    pc.set_linewidth(1.5)

# Style median lines
parts['cmedians'].set_edgecolor('blue')
parts['cmedians'].set_linewidth(2.5)

# Add observation counts
for i, source in enumerate(sources, 1):
    count = len(df_campus_dedup[df_campus_dedup['source'] == source])
    ax.text(i, ax.get_ylim()[1] * 0.98, f'n={count}',
            ha='center', va='top', fontsize=10, fontweight='bold', color='#333333')

# Reference lines
ax.axhline(y=1000, color='green', linestyle='--', linewidth=2, alpha=0.7, label='1km')
ax.axhline(y=3000, color='orange', linestyle='--', linewidth=2, alpha=0.7, label='3km')

ax.set_xticks(range(1, len(sources) + 1))
ax.set_xticklabels([source_labels[s] for s in sources], rotation=15, ha='right')
ax.set_ylabel('Distance Error (meters)', fontsize=13, fontweight='bold')
ax.set_xlabel('Source', fontsize=13, fontweight='bold')
ax.set_title(f'Spatial Accuracy Distribution by Source (Campus-Level, Deduplicated)\nViolin plot shows full data distribution shape for {unique_campuses} campuses',
             fontsize=15, fontweight='bold', pad=20)
ax.legend(loc='upper right', fontsize=11, framealpha=0.9)
ax.grid(True, alpha=0.3, axis='y')
plt.tight_layout()

output_file = os.path.join(output_dir, f'campus_violin_{timestamp}.png')
plt.savefig(output_file, dpi=300, bbox_inches='tight', facecolor='white')
plt.close()
print(f"   ✅ Saved: {output_file}\n")

# ============================================================================
# COMPLETION MESSAGE
# ============================================================================

print("=" * 80)
print("✅ ALL VISUALIZATIONS COMPLETE (LIGHT THEME)!")
print("=" * 80)
print(f"⏰ Finished: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
print(f"📁 Generated 6 plots:")
print(f"   1. building_level_by_source_{timestamp}.png")
print(f"   2. granularity_comparison_{timestamp}.png")
print(f"   3. by_region_{timestamp}.png")
print(f"   4. by_buildstatus_{timestamp}.png")
print(f"   5. building_violin_{timestamp}.png")
print(f"   6. campus_violin_{timestamp}.png (NEW!)")
print(f"\n🎯 All plots use light theme with original aesthetic!")
