"""
Capacity Accuracy Analysis V2
Apples-to-Apples Comparison of Vendor Capacity vs Meta IT Load

This script performs granularity-aware, definition-matched capacity comparisons.

Key Improvements over V1:
1. Deduplicates to closest match per building (not 1:many)
2. Separates comparisons by granularity (building vs campus)
3. Uses correct capacity definitions (IT load vs facility power)
4. Aligns time horizons (current vs forecast)
5. Applies PUE adjustment where needed (facility → IT conversion)

See CAPACITY_FIELD_DEFINITIONS.md for detailed field definitions.

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

# Feature classes
META_BUILDINGS = os.path.join(GDB, "meta_canonical_buildings")
META_SUITES = os.path.join(GDB, "meta_canonical_v2")
SPATIAL_MATCHES = os.path.join(GDB, "accuracy_analysis_multi_source_REBUILT")
GOLD_BUILDINGS = os.path.join(GDB, "gold_buildings")
GOLD_CAMPUS = os.path.join(GDB, "gold_campus")

# Output
OUTPUT_DIR = r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\outputs\capacity_accuracy"
TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")

os.makedirs(OUTPUT_DIR, exist_ok=True)

# PUE adjustment factor (facility power → IT load)
# Industry average for hyperscale = 1.2-1.4, we use 1.3
DEFAULT_PUE = 1.3

# Comparison configurations
# NOTE: mw_2023 is the best field based on variance analysis (11.9% MAPE vs 14.7% for mw_2024)
# Meta's IT load data appears to reflect 2023 state
# DCH reports BUILDING-level data (confirmed Dec 2024) - no PUE adjustment needed
#
# CAPACITY DATA AVAILABILITY (Dec 11, 2024 audit):
#   ✅ Semianalysis: 53-96% coverage - PRIMARY SOURCE
#   ✅ DataCenterHawk: 54-100% coverage - PRIMARY SOURCE
#   ❌ NewProjectMedia: 24% coverage (8 records) - TOO SPARSE
#   ❌ DataCenterMap: 1.5% coverage (1 record) - UNUSABLE
#   ❌ WoodMac: 0% coverage - NO DATA
#   ❌ Synergy: 0% - No capacity fields in source
#
COMPARISONS = {
    # =========================================================================
    # SEMIANALYSIS - Building-level, IT capacity (same definition as Meta)
    # PRIMARY SOURCE - Best capacity data coverage
    # =========================================================================
    'semianalysis_building': {
        'description': 'Semianalysis: Building-level IT capacity vs Meta IT load',
        'sources': ['Semianalysis'],
        'vendor_fields': {
            'mw_2023': {'desc': '2023 IT capacity (BEST - aligns with Meta data)', 'pue_adjust': False},
            'mw_2024': {'desc': '2024 IT capacity forecast', 'pue_adjust': False},
            'commissioned_power_mw': {'desc': 'Current installed IT capacity', 'pue_adjust': False},
        },
        'meta_field': 'it_load_total',
        'granularity': 'Building',
        'match_method': 'closest_building'
    },

    # =========================================================================
    # DATACETERHAWK - Building-level, IT capacity (no PUE adjustment needed)
    # PRIMARY SOURCE - Updated Dec 2024: DCH is building-level, reports IT capacity
    # =========================================================================
    'dch_building': {
        'description': 'DataCenterHawk: Building-level IT capacity vs Meta IT load',
        'sources': ['DataCenterHawk'],
        'vendor_fields': {
            'commissioned_power_mw': {'desc': 'Commissioned IT capacity (no PUE adj)', 'pue_adjust': False},
            'full_capacity_mw': {'desc': 'Full capacity (commissioned + planned + UC)', 'pue_adjust': False},
        },
        'meta_field': 'it_load_total',
        'granularity': 'Building',
        'match_method': 'closest_building'
    },

    # =========================================================================
    # CAMPUS-LEVEL COMPARISONS (aggregate vendor data to Meta campus)
    # =========================================================================
    'semianalysis_campus': {
        'description': 'Semianalysis: Campus-level aggregate vs Meta campus IT load',
        'sources': ['Semianalysis'],
        'vendor_fields': {
            'mw_2023': {'desc': '2023 IT capacity aggregated to campus', 'pue_adjust': False},
        },
        'meta_field': 'campus_it_load_total',
        'granularity': 'Campus',
        'match_method': 'campus_aggregate'
    },
    'dch_campus': {
        'description': 'DataCenterHawk: Campus-level aggregate vs Meta campus IT load',
        'sources': ['DataCenterHawk'],
        'vendor_fields': {
            'commissioned_power_mw': {'desc': 'Commissioned capacity aggregated to campus', 'pue_adjust': False},
        },
        'meta_field': 'campus_it_load_total',
        'granularity': 'Campus',
        'match_method': 'campus_aggregate'
    },
}


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def calculate_metrics(actual, predicted, min_samples=5):
    """
    Calculate accuracy metrics between actual and predicted values.
    Returns dict with MAE, MAPE, bias, correlation, etc.
    """
    # Filter to valid pairs
    mask = ~(np.isnan(actual) | np.isnan(predicted)) & (actual > 0) & (predicted > 0)
    actual_valid = actual[mask]
    predicted_valid = predicted[mask]

    n = len(actual_valid)

    if n < min_samples:
        return {
            'n': n,
            'mae': None,
            'mape': None,
            'bias': None,
            'bias_pct': None,
            'rmse': None,
            'correlation': None,
            'actual_mean': np.mean(actual_valid) if n > 0 else None,
            'predicted_mean': np.mean(predicted_valid) if n > 0 else None,
            'actual_sum': np.sum(actual_valid) if n > 0 else None,
            'predicted_sum': np.sum(predicted_valid) if n > 0 else None
        }

    # Mean Absolute Error
    mae = np.mean(np.abs(actual_valid - predicted_valid))

    # Mean Absolute Percentage Error
    mape = np.mean(np.abs((actual_valid - predicted_valid) / actual_valid)) * 100

    # Bias (positive = over-prediction, negative = under-prediction)
    bias = np.mean(predicted_valid - actual_valid)
    bias_pct = (bias / np.mean(actual_valid)) * 100 if np.mean(actual_valid) > 0 else None

    # Root Mean Square Error
    rmse = np.sqrt(np.mean((actual_valid - predicted_valid) ** 2))

    # Correlation
    if n > 2 and np.std(actual_valid) > 0 and np.std(predicted_valid) > 0:
        correlation = np.corrcoef(actual_valid, predicted_valid)[0, 1]
    else:
        correlation = None

    return {
        'n': n,
        'mae': mae,
        'mape': mape,
        'bias': bias,
        'bias_pct': bias_pct,
        'rmse': rmse,
        'correlation': correlation,
        'actual_mean': np.mean(actual_valid),
        'predicted_mean': np.mean(predicted_valid),
        'actual_sum': np.sum(actual_valid),
        'predicted_sum': np.sum(predicted_valid)
    }


def load_meta_buildings():
    """Load Meta canonical building data with IT load."""
    print("[1/6] Loading Meta canonical buildings...")

    fields = ['building_key', 'dc_code', 'datacenter', 'region_derived',
              'new_build_status', 'it_load_total', 'suite_count']

    data = []
    with arcpy.da.SearchCursor(META_BUILDINGS, fields) as cursor:
        for row in cursor:
            data.append(dict(zip(fields, row)))

    df = pd.DataFrame(data)
    df_valid = df[df['it_load_total'].notna() & (df['it_load_total'] > 0)].copy()

    print(f"   Total Meta buildings: {len(df)}")
    print(f"   Buildings with IT load: {len(df_valid)}")
    print(f"   IT load range: {df_valid['it_load_total'].min():.1f} - {df_valid['it_load_total'].max():.1f} MW")

    return df_valid


def create_meta_campus_aggregates(df_meta):
    """Aggregate Meta building IT loads to campus level (by dc_code)."""
    print("\n[2/6] Creating Meta campus-level aggregates...")

    campus_agg = df_meta.groupby('dc_code').agg({
        'it_load_total': 'sum',
        'building_key': 'count',
        'region_derived': 'first',
        'new_build_status': 'first'
    }).reset_index()

    campus_agg.columns = ['dc_code', 'campus_it_load_total', 'building_count',
                          'region_derived', 'new_build_status']

    print(f"   Unique Meta campuses: {len(campus_agg)}")
    print(f"   Campus IT load range: {campus_agg['campus_it_load_total'].min():.1f} - {campus_agg['campus_it_load_total'].max():.1f} MW")

    return campus_agg


def load_spatial_matches():
    """Load spatial match data and deduplicate to closest match per building/source."""
    print("\n[3/6] Loading spatial matches and deduplicating...")

    # Get available fields
    available_fields = [f.name for f in arcpy.ListFields(SPATIAL_MATCHES)]

    # Required fields
    base_fields = ['building_key', 'dc_code', 'source', 'distance_m', 'record_level']

    # Capacity fields (check for _1 suffix from spatial join)
    capacity_fields = ['commissioned_power_mw', 'full_capacity_mw', 'planned_power_mw',
                       'uc_power_mw', 'mw_2023', 'mw_2024', 'mw_2025', 'mw_2026',
                       'mw_2027', 'mw_2028', 'mw_2029', 'mw_2030', 'mw_2031', 'mw_2032',
                       'campus_id', 'campus_name']

    read_fields = []
    field_mapping = {}

    for f in base_fields:
        if f in available_fields:
            read_fields.append(f)
            field_mapping[f] = f
        elif f + '_1' in available_fields:
            read_fields.append(f + '_1')
            field_mapping[f + '_1'] = f

    for f in capacity_fields:
        if f in available_fields:
            read_fields.append(f)
            field_mapping[f] = f
        elif f + '_1' in available_fields:
            read_fields.append(f + '_1')
            field_mapping[f + '_1'] = f

    # Read data
    data = []
    with arcpy.da.SearchCursor(SPATIAL_MATCHES, read_fields) as cursor:
        for row in cursor:
            record = {}
            for i, field in enumerate(read_fields):
                clean_field = field_mapping.get(field, field)
                record[clean_field] = row[i]
            data.append(record)

    df = pd.DataFrame(data)
    print(f"   Total spatial matches: {len(df)}")

    # Filter to valid matches with source
    df = df[df['source'].notna()].copy()
    print(f"   Matches with source: {len(df)}")

    # Deduplicate: keep closest match per building_key + source
    df['distance_m'] = pd.to_numeric(df['distance_m'], errors='coerce')
    df_deduped = df.loc[df.groupby(['building_key', 'source'])['distance_m'].idxmin()]

    print(f"   After dedup (closest per building/source): {len(df_deduped)}")

    return df_deduped


def run_building_level_comparison(df_matches, df_meta, config):
    """Run building-level capacity comparison."""

    results = []

    # Join Meta IT load to matches
    df_analysis = df_matches.merge(
        df_meta[['building_key', 'it_load_total', 'new_build_status', 'region_derived']],
        on='building_key',
        how='inner'
    )

    # Apply any filters
    if 'filter' in config:
        filter_col, filter_val = config['filter'].split(' = ')
        filter_val = filter_val.strip("'")
        df_analysis = df_analysis[df_analysis[filter_col] == filter_val]

    for source in config['sources']:
        source_df = df_analysis[df_analysis['source'] == source].copy()

        if len(source_df) == 0:
            continue

        for vendor_field, field_config in config['vendor_fields'].items():
            if vendor_field not in source_df.columns:
                continue

            # Apply PUE adjustment if needed
            if field_config['pue_adjust']:
                predicted = source_df[vendor_field].values / DEFAULT_PUE
            else:
                predicted = source_df[vendor_field].values

            actual = source_df['it_load_total'].values

            # Overall metrics
            metrics = calculate_metrics(actual, predicted)

            if metrics['n'] > 0:
                results.append({
                    'comparison_type': config['description'],
                    'granularity': config['granularity'],
                    'source': source,
                    'vendor_field': vendor_field,
                    'field_description': field_config['desc'],
                    'pue_adjusted': field_config['pue_adjust'],
                    'build_status': 'ALL',
                    **metrics
                })

            # By build status
            for status in ['Complete Build', 'Active Build', 'Future Build']:
                status_df = source_df[source_df['new_build_status'] == status]

                if len(status_df) > 0:
                    if field_config['pue_adjust']:
                        pred_s = status_df[vendor_field].values / DEFAULT_PUE
                    else:
                        pred_s = status_df[vendor_field].values

                    actual_s = status_df['it_load_total'].values
                    metrics_s = calculate_metrics(actual_s, pred_s)

                    if metrics_s['n'] > 0:
                        results.append({
                            'comparison_type': config['description'],
                            'granularity': config['granularity'],
                            'source': source,
                            'vendor_field': vendor_field,
                            'field_description': field_config['desc'],
                            'pue_adjusted': field_config['pue_adjust'],
                            'build_status': status,
                            **metrics_s
                        })

    return results


def run_campus_level_comparison(df_matches, df_meta_campus, config):
    """Run campus-level capacity comparison with aggregation."""

    results = []

    # For campus comparison, we need to aggregate vendor data by campus
    # and match to Meta campus aggregates

    for source in config['sources']:
        source_df = df_matches[df_matches['source'] == source].copy()

        if len(source_df) == 0:
            continue

        # Aggregate vendor capacity by Meta dc_code (campus)
        for vendor_field, field_config in config['vendor_fields'].items():
            if vendor_field not in source_df.columns:
                continue

            # Sum vendor capacity per dc_code
            vendor_by_campus = source_df.groupby('dc_code').agg({
                vendor_field: 'sum',
                'building_key': 'count'
            }).reset_index()
            vendor_by_campus.columns = ['dc_code', 'vendor_capacity', 'matched_buildings']

            # Join with Meta campus data
            campus_comparison = vendor_by_campus.merge(
                df_meta_campus[['dc_code', 'campus_it_load_total', 'building_count',
                               'region_derived', 'new_build_status']],
                on='dc_code',
                how='inner'
            )

            if len(campus_comparison) == 0:
                continue

            # Apply PUE adjustment if needed
            if field_config['pue_adjust']:
                predicted = campus_comparison['vendor_capacity'].values / DEFAULT_PUE
            else:
                predicted = campus_comparison['vendor_capacity'].values

            actual = campus_comparison['campus_it_load_total'].values

            # Overall metrics
            metrics = calculate_metrics(actual, predicted)

            if metrics['n'] > 0:
                results.append({
                    'comparison_type': config['description'],
                    'granularity': config['granularity'],
                    'source': source,
                    'vendor_field': vendor_field,
                    'field_description': field_config['desc'],
                    'pue_adjusted': field_config['pue_adjust'],
                    'build_status': 'ALL',
                    **metrics
                })

            # By build status
            for status in ['Complete Build', 'Active Build', 'Future Build']:
                status_df = campus_comparison[campus_comparison['new_build_status'] == status]

                if len(status_df) > 0:
                    if field_config['pue_adjust']:
                        pred_s = status_df['vendor_capacity'].values / DEFAULT_PUE
                    else:
                        pred_s = status_df['vendor_capacity'].values

                    actual_s = status_df['campus_it_load_total'].values
                    metrics_s = calculate_metrics(actual_s, pred_s)

                    if metrics_s['n'] > 0:
                        results.append({
                            'comparison_type': config['description'],
                            'granularity': config['granularity'],
                            'source': source,
                            'vendor_field': vendor_field,
                            'field_description': field_config['desc'],
                            'pue_adjusted': field_config['pue_adjust'],
                            'build_status': status,
                            **metrics_s
                        })

    return results


def generate_report(df_results, output_path):
    """Generate comprehensive text report."""

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("=" * 80 + "\n")
        f.write("       CAPACITY ACCURACY ANALYSIS V2 - APPLES-TO-APPLES COMPARISON\n")
        f.write("=" * 80 + "\n")
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"PUE adjustment factor: {DEFAULT_PUE}\n")
        f.write("\n")

        # Executive Summary
        f.write("=" * 80 + "\n")
        f.write("📋 EXECUTIVE SUMMARY\n")
        f.write("=" * 80 + "\n\n")

        f.write("This analysis compares vendor capacity data against Meta's actual IT load,\n")
        f.write("ensuring apples-to-apples comparisons by:\n")
        f.write("  • Matching granularity (building vs campus level)\n")
        f.write("  • Using correct capacity definitions (IT load vs facility power)\n")
        f.write("  • Applying PUE adjustment where facility power → IT load conversion needed\n")
        f.write("  • Deduplicating to closest spatial match (not 1:many)\n")
        f.write("\n")

        f.write("See CAPACITY_FIELD_DEFINITIONS.md for detailed field definitions.\n\n")

        # Key Findings
        f.write("=" * 80 + "\n")
        f.write("🏆 KEY FINDINGS\n")
        f.write("=" * 80 + "\n\n")

        # Best building-level result
        bldg_results = df_results[(df_results['granularity'] == 'Building') &
                                   (df_results['build_status'] == 'ALL') &
                                   (df_results['mape'].notna())]
        if len(bldg_results) > 0:
            best_bldg = bldg_results.loc[bldg_results['mape'].idxmin()]
            f.write(f"BEST BUILDING-LEVEL COMPARISON:\n")
            f.write(f"  Source: {best_bldg['source']}\n")
            f.write(f"  Field: {best_bldg['vendor_field']} ({best_bldg['field_description']})\n")
            f.write(f"  MAPE: {best_bldg['mape']:.1f}%\n")
            f.write(f"  Bias: {best_bldg['bias_pct']:+.1f}%\n")
            f.write(f"  Correlation: {best_bldg['correlation']:.2f}\n")
            f.write(f"  Sample size: {best_bldg['n']}\n\n")

        # Best campus-level result
        campus_results = df_results[(df_results['granularity'] == 'Campus') &
                                     (df_results['build_status'] == 'ALL') &
                                     (df_results['mape'].notna())]
        if len(campus_results) > 0:
            best_campus = campus_results.loc[campus_results['mape'].idxmin()]
            f.write(f"BEST CAMPUS-LEVEL COMPARISON:\n")
            f.write(f"  Source: {best_campus['source']}\n")
            f.write(f"  Field: {best_campus['vendor_field']} ({best_campus['field_description']})\n")
            f.write(f"  PUE Adjusted: {best_campus['pue_adjusted']}\n")
            f.write(f"  MAPE: {best_campus['mape']:.1f}%\n")
            f.write(f"  Bias: {best_campus['bias_pct']:+.1f}%\n")
            f.write(f"  Sample size: {best_campus['n']}\n\n")

        # Detailed Results by Comparison Type
        f.write("=" * 80 + "\n")
        f.write("📊 DETAILED RESULTS BY COMPARISON TYPE\n")
        f.write("=" * 80 + "\n\n")

        for comp_type in df_results['comparison_type'].unique():
            comp_df = df_results[df_results['comparison_type'] == comp_type]

            f.write(f"\n{comp_type}\n")
            f.write("-" * 70 + "\n")

            # All statuses first
            all_status = comp_df[comp_df['build_status'] == 'ALL']
            if len(all_status) > 0:
                f.write(f"\n{'Vendor Field':<25} {'MAPE':>8} {'Bias%':>8} {'r':>6} {'n':>6} {'Meta MW':>10} {'Vendor MW':>10}\n")
                f.write("-" * 75 + "\n")

                for _, row in all_status.iterrows():
                    mape_str = f"{row['mape']:.1f}%" if pd.notna(row['mape']) else "-"
                    bias_str = f"{row['bias_pct']:+.1f}%" if pd.notna(row['bias_pct']) else "-"
                    corr_str = f"{row['correlation']:.2f}" if pd.notna(row['correlation']) else "-"
                    actual_str = f"{row['actual_sum']:.0f}" if pd.notna(row['actual_sum']) else "-"
                    pred_str = f"{row['predicted_sum']:.0f}" if pd.notna(row['predicted_sum']) else "-"

                    f.write(f"{row['vendor_field']:<25} {mape_str:>8} {bias_str:>8} {corr_str:>6} {row['n']:>6} {actual_str:>10} {pred_str:>10}\n")

            # By build status
            f.write("\n  By Build Status:\n")
            for status in ['Complete Build', 'Active Build', 'Future Build']:
                status_df = comp_df[comp_df['build_status'] == status]
                if len(status_df) > 0:
                    f.write(f"\n  {status}:\n")
                    for _, row in status_df.iterrows():
                        if pd.notna(row['mape']):
                            f.write(f"    {row['vendor_field']}: MAPE={row['mape']:.1f}%, n={row['n']}\n")

        # Interpretation Guide
        f.write("\n\n")
        f.write("=" * 80 + "\n")
        f.write("📈 INTERPRETATION GUIDE\n")
        f.write("=" * 80 + "\n\n")

        f.write("MAPE (Mean Absolute Percentage Error):\n")
        f.write("   • <10%: Excellent - vendor and Meta closely aligned\n")
        f.write("   • 10-20%: Good - minor differences, likely utilization variance\n")
        f.write("   • 20-40%: Moderate - may indicate definition differences\n")
        f.write("   • >40%: Poor - likely comparing different metrics\n\n")

        f.write("Bias:\n")
        f.write("   • Positive: Vendor over-estimates compared to Meta actual\n")
        f.write("   • Negative: Vendor under-estimates compared to Meta actual\n")
        f.write("   • Expected: Slight positive bias (vendor reports capacity, Meta reports load)\n\n")

        f.write("Sample Size (n):\n")
        f.write("   • Minimum 5 required for metrics calculation\n")
        f.write("   • <20: Results may not be statistically significant\n")
        f.write("   • >50: High confidence in results\n\n")

        f.write("PUE Adjustment:\n")
        f.write(f"   • Factor used: {DEFAULT_PUE}\n")
        f.write("   • Applied when vendor reports facility power, Meta reports IT load\n")
        f.write("   • Formula: IT Load ≈ Facility Power / PUE\n\n")

        f.write("=" * 80 + "\n")
        f.write("END OF CAPACITY ACCURACY REPORT V2\n")
        f.write("=" * 80 + "\n")


# ============================================================================
# MAIN EXECUTION
# ============================================================================

def main():
    """Main execution function."""

    print("=" * 80)
    print("CAPACITY ACCURACY ANALYSIS V2")
    print("Apples-to-Apples Comparison")
    print("=" * 80)
    print(f"Started: {datetime.now()}")
    print()

    # Step 1: Load Meta building data
    df_meta = load_meta_buildings()

    # Step 2: Create campus aggregates
    df_meta_campus = create_meta_campus_aggregates(df_meta)

    # Step 3: Load and deduplicate spatial matches
    df_matches = load_spatial_matches()

    # Step 4: Run comparisons
    print("\n[4/6] Running comparisons...")

    all_results = []

    for comp_name, config in COMPARISONS.items():
        print(f"\n   {config['description']}...")

        if config['match_method'] == 'closest_building':
            results = run_building_level_comparison(df_matches, df_meta, config)
        elif config['match_method'] == 'campus_aggregate':
            results = run_campus_level_comparison(df_matches, df_meta_campus, config)

        all_results.extend(results)
        print(f"      Generated {len(results)} metric records")

    df_results = pd.DataFrame(all_results)

    # Step 5: Generate outputs
    print("\n[5/6] Generating outputs...")

    # CSV output
    csv_path = os.path.join(OUTPUT_DIR, f"capacity_accuracy_v2_{TIMESTAMP}.csv")
    df_results.to_csv(csv_path, index=False)
    print(f"   Saved: {csv_path}")

    # Text report
    report_path = os.path.join(OUTPUT_DIR, f"CAPACITY_ACCURACY_V2_REPORT_{TIMESTAMP}.txt")
    generate_report(df_results, report_path)
    print(f"   Saved: {report_path}")

    # Step 6: Console summary
    print("\n[6/6] Summary...")
    print()
    print("=" * 80)
    print("✅ CAPACITY ACCURACY ANALYSIS V2 COMPLETE")
    print("=" * 80)
    print()

    # Quick summary
    print("QUICK SUMMARY (ALL statuses, best per granularity):")
    print("-" * 70)

    for granularity in ['Building', 'Campus']:
        gran_df = df_results[(df_results['granularity'] == granularity) &
                              (df_results['build_status'] == 'ALL') &
                              (df_results['mape'].notna())]

        if len(gran_df) > 0:
            best = gran_df.loc[gran_df['mape'].idxmin()]
            pue_note = " (PUE-adjusted)" if best['pue_adjusted'] else ""
            print(f"\n{granularity}-level{pue_note}:")
            print(f"  Best: {best['source']} {best['vendor_field']}")
            print(f"  MAPE: {best['mape']:.1f}%")
            print(f"  Bias: {best['bias_pct']:+.1f}%")
            print(f"  Correlation: {best['correlation']:.2f}")
            print(f"  Sample: {best['n']} comparisons")
            print(f"  Meta total: {best['actual_sum']:.0f} MW")
            print(f"  Vendor total: {best['predicted_sum']:.0f} MW")

    print()
    print(f"📁 Output files saved to: {OUTPUT_DIR}")
    print(f"Completed: {datetime.now()}")

    return df_results


# ============================================================================
# EXECUTE
# ============================================================================

if __name__ == "__main__":
    results = main()
