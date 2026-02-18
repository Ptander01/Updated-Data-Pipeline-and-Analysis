"""
Attribute Accuracy Audit Script
Audits field completeness and data quality by source for gold_buildings.

Analyzes:
- Capacity fields (commissioned_power_mw, uc_power_mw, planned_power_mw, full_capacity_mw)
- Facility details (facility_sqft, whitespace_sqft, pue)
- Cost data (total_cost_usd_million, land_cost_usd_million)
- Land data (total_site_acres, data_center_acres)
- Infrastructure (power_provider, tier_design, feed_config)
- Timeline (announced, construction_started, cod, actual_live_date)
- Classification (facility_status, owned_leased, building_type)

Author: Meta Data Center GIS Team
Date: December 10, 2024
"""

import arcpy
import pandas as pd
import numpy as np
from datetime import datetime
from collections import defaultdict
import os

# ============================================================================
# CONFIGURATION
# ============================================================================

GDB = r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\Default.gdb"
GOLD_BUILDINGS = os.path.join(GDB, "gold_buildings")
OUTPUT_DIR = r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\outputs\attribute_audit"
TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")

os.makedirs(OUTPUT_DIR, exist_ok=True)

# Define field categories for audit
FIELD_CATEGORIES = {
    'capacity_current': [
        'commissioned_power_mw',
        'uc_power_mw',
        'planned_power_mw',
        'planned_plus_uc_mw',
        'full_capacity_mw',
        'available_power_kw'
    ],
    'capacity_forecast': [
        'mw_2023', 'mw_2024', 'mw_2025', 'mw_2026', 'mw_2027',
        'mw_2028', 'mw_2029', 'mw_2030', 'mw_2031', 'mw_2032'
    ],
    'facility_details': [
        'facility_sqft',
        'whitespace_sqft',
        'pue'
    ],
    'cost_data': [
        'total_cost_usd_million',
        'land_cost_usd_million'
    ],
    'land_data': [
        'total_site_acres',
        'data_center_acres'
    ],
    'infrastructure': [
        'power_provider',
        'power_grid',
        'tier_design',
        'feed_config',
        'substation_count',
        'onsite_substation'
    ],
    'timeline': [
        'announced',
        'land_acquisition',
        'permitting',
        'construction_started',
        'cod',
        'actual_live_date',
        'date_reported'
    ],
    'classification': [
        'facility_status',
        'owned_leased',
        'building_type',
        'type_category',
        'purpose'
    ],
    'ecosystem': [
        'ecosystem_ixps',
        'ecosystem_cloud',
        'ecosystem_children',
        'ecosystem_networkproviders',
        'ecosystem_networkpresence',
        'ecosystem_serviceproviders'
    ]
}

SOURCES = ['DataCenterHawk', 'Semianalysis', 'DataCenterMap', 'Synergy', 'NewProjectMedia', 'WoodMac']

# ============================================================================
# MAIN FUNCTIONS
# ============================================================================

def get_available_fields(fc):
    """Get list of actual field names in feature class."""
    return [f.name for f in arcpy.ListFields(fc)]


def calculate_field_completeness(fc, sources):
    """Calculate field completeness (non-null %) by source."""

    available_fields = get_available_fields(fc)

    # Build list of all fields to audit
    all_audit_fields = []
    for category, fields in FIELD_CATEGORIES.items():
        for f in fields:
            if f in available_fields:
                all_audit_fields.append(f)

    print(f"📊 Auditing {len(all_audit_fields)} fields across {len(sources)} sources...")
    print(f"   Available fields in gold_buildings: {len(available_fields)}")

    # Read data
    read_fields = ['source'] + all_audit_fields

    data = []
    with arcpy.da.SearchCursor(fc, read_fields) as cursor:
        for row in cursor:
            record = {'source': row[0]}
            for i, field in enumerate(all_audit_fields):
                record[field] = row[i + 1]
            data.append(record)

    df = pd.DataFrame(data)
    print(f"   Total records: {len(df)}")

    # Calculate completeness by source
    results = []

    for source in sources:
        source_df = df[df['source'] == source]
        source_count = len(source_df)

        if source_count == 0:
            continue

        for category, fields in FIELD_CATEGORIES.items():
            for field in fields:
                if field not in all_audit_fields:
                    continue

                non_null = source_df[field].notna().sum()
                pct = (non_null / source_count * 100) if source_count > 0 else 0

                # Get value stats if numeric
                if source_df[field].dtype in ['float64', 'int64']:
                    values = source_df[field].dropna()
                    if len(values) > 0:
                        min_val = values.min()
                        max_val = values.max()
                        mean_val = values.mean()
                        median_val = values.median()
                    else:
                        min_val = max_val = mean_val = median_val = None
                else:
                    min_val = max_val = mean_val = median_val = None

                results.append({
                    'source': source,
                    'category': category,
                    'field': field,
                    'total_records': source_count,
                    'non_null_count': non_null,
                    'completeness_pct': round(pct, 1),
                    'min_value': min_val,
                    'max_value': max_val,
                    'mean_value': mean_val,
                    'median_value': median_val
                })

    return pd.DataFrame(results)


def create_summary_pivot(completeness_df):
    """Create pivot table summary of completeness by source and category."""

    # Average completeness by source and category
    summary = completeness_df.groupby(['source', 'category'])['completeness_pct'].mean().unstack()
    summary = summary.round(1)

    # Add overall average
    summary['OVERALL'] = summary.mean(axis=1).round(1)

    return summary


def identify_best_sources_by_field(completeness_df):
    """Identify which source is best for each field."""

    best_sources = []

    for field in completeness_df['field'].unique():
        field_data = completeness_df[completeness_df['field'] == field]

        # Get source with highest completeness
        best_row = field_data.loc[field_data['completeness_pct'].idxmax()]

        # Get all sources with >0% completeness
        sources_with_data = field_data[field_data['completeness_pct'] > 0]['source'].tolist()

        best_sources.append({
            'field': field,
            'category': best_row['category'],
            'best_source': best_row['source'],
            'best_completeness': best_row['completeness_pct'],
            'sources_with_data': ', '.join(sources_with_data),
            'num_sources': len(sources_with_data)
        })

    return pd.DataFrame(best_sources).sort_values(['category', 'best_completeness'], ascending=[True, False])


def generate_audit_report(completeness_df, summary_df, best_sources_df):
    """Generate text report."""

    report_path = os.path.join(OUTPUT_DIR, f"attribute_audit_report_{TIMESTAMP}.txt")

    with open(report_path, 'w', encoding='utf-8') as f:
        f.write("=" * 80 + "\n")
        f.write("           ATTRIBUTE ACCURACY AUDIT REPORT\n")
        f.write("         Data Center Consensus GIS Model - Meta\n")
        f.write("=" * 80 + "\n")
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Feature Class: gold_buildings\n")
        f.write("\n")

        # Executive Summary
        f.write("=" * 80 + "\n")
        f.write("📋 EXECUTIVE SUMMARY\n")
        f.write("=" * 80 + "\n\n")

        f.write("FIELD COMPLETENESS BY SOURCE (Average % across all fields):\n")
        f.write("-" * 60 + "\n")

        overall = summary_df['OVERALL'].sort_values(ascending=False)
        for source, pct in overall.items():
            bar = "█" * int(pct / 5) + "░" * (20 - int(pct / 5))
            f.write(f"  {source:20s} │ {bar} │ {pct:5.1f}%\n")

        f.write("\n")

        # Category Summary
        f.write("=" * 80 + "\n")
        f.write("📊 COMPLETENESS BY CATEGORY\n")
        f.write("=" * 80 + "\n\n")

        for category in FIELD_CATEGORIES.keys():
            if category in summary_df.columns:
                f.write(f"\n{category.upper().replace('_', ' ')}:\n")
                f.write("-" * 50 + "\n")

                cat_data = summary_df[category].sort_values(ascending=False)
                for source, pct in cat_data.items():
                    if pd.notna(pct):
                        bar = "█" * int(pct / 5) + "░" * (20 - int(pct / 5))
                        f.write(f"  {source:20s} │ {bar} │ {pct:5.1f}%\n")

        f.write("\n")

        # Best Source by Field
        f.write("=" * 80 + "\n")
        f.write("🏆 BEST SOURCE FOR EACH FIELD\n")
        f.write("=" * 80 + "\n\n")

        for category in FIELD_CATEGORIES.keys():
            cat_fields = best_sources_df[best_sources_df['category'] == category]
            if len(cat_fields) > 0:
                f.write(f"\n{category.upper().replace('_', ' ')}:\n")
                f.write("-" * 70 + "\n")
                f.write(f"{'Field':<30} {'Best Source':<18} {'%':>6} {'# Sources':>10}\n")
                f.write("-" * 70 + "\n")

                for _, row in cat_fields.iterrows():
                    f.write(f"{row['field']:<30} {row['best_source']:<18} {row['best_completeness']:>5.1f}% {row['num_sources']:>10}\n")

        f.write("\n")

        # Capacity Deep Dive
        f.write("=" * 80 + "\n")
        f.write("⚡ CAPACITY DATA DEEP DIVE\n")
        f.write("=" * 80 + "\n\n")

        capacity_fields = FIELD_CATEGORIES['capacity_current'] + FIELD_CATEGORIES['capacity_forecast']
        capacity_data = completeness_df[completeness_df['field'].isin(capacity_fields)]

        for source in SOURCES:
            source_cap = capacity_data[capacity_data['source'] == source]
            if len(source_cap) == 0:
                continue

            f.write(f"\n{source}:\n")
            f.write("-" * 60 + "\n")

            for _, row in source_cap.iterrows():
                if row['completeness_pct'] > 0:
                    stats = ""
                    if row['median_value'] is not None:
                        stats = f" [median: {row['median_value']:.1f}, range: {row['min_value']:.1f}-{row['max_value']:.1f}]"
                    f.write(f"  {row['field']:<25} {row['completeness_pct']:>5.1f}% ({row['non_null_count']:>3} records){stats}\n")

        f.write("\n")

        # Recommendations
        f.write("=" * 80 + "\n")
        f.write("🎯 RECOMMENDATIONS FOR CONSENSUS MODEL\n")
        f.write("=" * 80 + "\n\n")

        f.write("CAPACITY DATA PRIORITY:\n")
        f.write("-" * 50 + "\n")
        f.write("  1. Current Capacity: DataCenterHawk (commissioned_power_mw)\n")
        f.write("  2. Forecast Capacity: Semianalysis (mw_2023-2032)\n")
        f.write("  3. Full Capacity: DataCenterHawk + Semianalysis\n")
        f.write("\n")

        f.write("FACILITY DETAILS PRIORITY:\n")
        f.write("-" * 50 + "\n")
        f.write("  1. Square Footage: DataCenterHawk or DataCenterMap\n")
        f.write("  2. PUE: DataCenterMap (if available)\n")
        f.write("\n")

        f.write("COST DATA PRIORITY:\n")
        f.write("-" * 50 + "\n")
        f.write("  1. Total Cost: NewProjectMedia or WoodMac\n")
        f.write("  2. Land Cost: WoodMac\n")
        f.write("\n")

        f.write("TIMELINE DATA PRIORITY:\n")
        f.write("-" * 50 + "\n")
        f.write("  1. COD/Live Date: DataCenterHawk or Semianalysis\n")
        f.write("  2. Announced: WoodMac or NewProjectMedia\n")
        f.write("\n")

        f.write("=" * 80 + "\n")
        f.write("END OF ATTRIBUTE AUDIT REPORT\n")
        f.write("=" * 80 + "\n")

    return report_path


def main():
    """Main execution."""

    print("=" * 80)
    print("ATTRIBUTE ACCURACY AUDIT")
    print("gold_buildings - Field Completeness by Source")
    print("=" * 80)
    print(f"Started: {datetime.now()}")
    print()

    # Step 1: Calculate field completeness
    print("[1/4] Calculating field completeness by source...")
    completeness_df = calculate_field_completeness(GOLD_BUILDINGS, SOURCES)

    # Step 2: Create summary pivot
    print("[2/4] Creating summary pivot table...")
    summary_df = create_summary_pivot(completeness_df)

    # Step 3: Identify best sources
    print("[3/4] Identifying best source for each field...")
    best_sources_df = identify_best_sources_by_field(completeness_df)

    # Step 4: Generate reports
    print("[4/4] Generating reports...")

    # Save CSVs
    completeness_csv = os.path.join(OUTPUT_DIR, f"field_completeness_by_source_{TIMESTAMP}.csv")
    summary_csv = os.path.join(OUTPUT_DIR, f"completeness_summary_pivot_{TIMESTAMP}.csv")
    best_sources_csv = os.path.join(OUTPUT_DIR, f"best_source_by_field_{TIMESTAMP}.csv")

    completeness_df.to_csv(completeness_csv, index=False)
    summary_df.to_csv(summary_csv)
    best_sources_df.to_csv(best_sources_csv, index=False)

    # Generate text report
    report_path = generate_audit_report(completeness_df, summary_df, best_sources_df)

    print()
    print("=" * 80)
    print("✅ ATTRIBUTE AUDIT COMPLETE")
    print("=" * 80)
    print()
    print("📁 Output files:")
    print(f"   • {completeness_csv}")
    print(f"   • {summary_csv}")
    print(f"   • {best_sources_csv}")
    print(f"   • {report_path}")
    print()

    # Print quick summary
    print("📊 Quick Summary - Overall Completeness by Source:")
    print("-" * 50)
    for source, pct in summary_df['OVERALL'].sort_values(ascending=False).items():
        print(f"   {source:20s}: {pct:5.1f}%")

    print()
    print(f"Completed: {datetime.now()}")

    return completeness_df, summary_df, best_sources_df


# ============================================================================
# EXECUTE
# ============================================================================

if __name__ == "__main__":
    completeness_df, summary_df, best_sources_df = main()
