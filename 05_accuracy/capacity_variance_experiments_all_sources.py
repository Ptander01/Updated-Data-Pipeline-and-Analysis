"""
Capacity Variance Experiments - All Sources
Tests different configurations to find optimal capacity comparison for each vendor.

Experiments per source:
1. Which capacity field is most accurate?
2. Is PUE adjustment needed?
3. Which build status filter works best?
4. Building vs Campus granularity comparison

Author: Meta Data Center GIS Team
Date: December 11, 2024
"""

import arcpy
import pandas as pd
import numpy as np
from datetime import datetime
import os

# ============================================================================
# CONFIGURATION
# ============================================================================

GDB = r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\Default.gdb"

META_BUILDINGS = os.path.join(GDB, "meta_canonical_buildings")
SPATIAL_MATCHES = os.path.join(GDB, "accuracy_analysis_multi_source_REBUILT")
GOLD_BUILDINGS = os.path.join(GDB, "gold_buildings")

OUTPUT_DIR = r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\outputs\capacity_accuracy"
TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")

os.makedirs(OUTPUT_DIR, exist_ok=True)

# Sources to analyze
SOURCES = ['Semianalysis', 'DataCenterHawk', 'DataCenterMap', 'NewProjectMedia', 'WoodMac']

# Capacity fields to test
CAPACITY_FIELDS = [
    'commissioned_power_mw',
    'planned_power_mw',
    'uc_power_mw',
    'full_capacity_mw',
    'planned_plus_uc_mw',
    'mw_2023',
    'mw_2024',
    'mw_2025',
]

# PUE factors to test
PUE_FACTORS = [1.0, 1.2, 1.3, 1.4]

# Build status filters
STATUS_FILTERS = ['ALL', 'Complete Build', 'Active Build', 'Future Build']


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def calculate_metrics(actual, predicted):
    """Calculate accuracy metrics."""
    mask = ~(np.isnan(actual) | np.isnan(predicted)) & (actual > 0) & (predicted > 0)
    actual_valid = actual[mask]
    predicted_valid = predicted[mask]
    n = len(actual_valid)

    if n < 3:
        return {'n': n, 'mape': None, 'bias_pct': None, 'ratio': None, 'correlation': None}

    mape = np.mean(np.abs((actual_valid - predicted_valid) / actual_valid)) * 100
    bias = np.mean(predicted_valid - actual_valid)
    bias_pct = (bias / np.mean(actual_valid)) * 100 if np.mean(actual_valid) > 0 else None
    ratio = np.mean(predicted_valid / actual_valid)

    if np.std(actual_valid) > 0 and np.std(predicted_valid) > 0:
        correlation = np.corrcoef(actual_valid, predicted_valid)[0, 1]
    else:
        correlation = None

    return {
        'n': n,
        'mape': mape,
        'bias_pct': bias_pct,
        'ratio': ratio,
        'correlation': correlation,
        'actual_sum': np.sum(actual_valid),
        'predicted_sum': np.sum(predicted_valid)
    }


def load_data():
    """Load Meta buildings and spatial matches."""
    print("[1/3] Loading data...")

    # Meta buildings
    meta_fields = ['building_key', 'dc_code', 'it_load_total', 'new_build_status', 'region_derived']
    meta_data = []
    with arcpy.da.SearchCursor(META_BUILDINGS, meta_fields) as cursor:
        for row in cursor:
            meta_data.append(dict(zip(meta_fields, row)))
    df_meta = pd.DataFrame(meta_data)
    df_meta = df_meta[df_meta['it_load_total'].notna() & (df_meta['it_load_total'] > 0)]
    print(f"   Meta buildings with IT load: {len(df_meta)}")

    # Spatial matches
    available_fields = [f.name for f in arcpy.ListFields(SPATIAL_MATCHES)]

    read_fields = ['building_key', 'dc_code', 'source', 'distance_m', 'record_level']
    for cf in CAPACITY_FIELDS:
        if cf in available_fields:
            read_fields.append(cf)
        elif cf + '_1' in available_fields:
            read_fields.append(cf + '_1')

    # Remove duplicates
    read_fields = list(dict.fromkeys(read_fields))

    match_data = []
    with arcpy.da.SearchCursor(SPATIAL_MATCHES, read_fields) as cursor:
        for row in cursor:
            record = {}
            for i, f in enumerate(read_fields):
                clean_name = f.replace('_1', '') if f.endswith('_1') else f
                record[clean_name] = row[i]
            match_data.append(record)

    df_matches = pd.DataFrame(match_data)
    df_matches = df_matches[df_matches['source'].notna()]

    # Deduplicate to closest match per building/source
    df_matches['distance_m'] = pd.to_numeric(df_matches['distance_m'], errors='coerce')
    df_matches = df_matches.loc[df_matches.groupby(['building_key', 'source'])['distance_m'].idxmin()]

    print(f"   Spatial matches (deduped): {len(df_matches)}")

    # Source breakdown
    print(f"\n   Matches by source:")
    for source in SOURCES:
        count = len(df_matches[df_matches['source'] == source])
        print(f"      {source}: {count}")

    return df_meta, df_matches


def run_experiments(df_meta, df_matches):
    """Run all variance experiments."""
    print("\n[2/3] Running experiments...")

    # Merge Meta IT load
    df_analysis = df_matches.merge(
        df_meta[['building_key', 'it_load_total', 'new_build_status', 'region_derived']],
        on='building_key',
        how='inner'
    )

    results = []

    for source in SOURCES:
        source_df = df_analysis[df_analysis['source'] == source].copy()

        if len(source_df) == 0:
            print(f"\n   {source}: No matches - SKIPPING")
            continue

        print(f"\n   {source}: {len(source_df)} matches")

        # Test each capacity field
        for field in CAPACITY_FIELDS:
            if field not in source_df.columns:
                continue

            # Check if field has data
            has_data = source_df[field].notna() & (source_df[field] > 0)
            if has_data.sum() == 0:
                continue

            # Test each PUE factor
            for pue in PUE_FACTORS:
                # Test each status filter
                for status in STATUS_FILTERS:
                    if status == 'ALL':
                        test_df = source_df
                    else:
                        test_df = source_df[source_df['new_build_status'] == status]

                    if len(test_df) == 0:
                        continue

                    actual = test_df['it_load_total'].values
                    predicted = test_df[field].values / pue

                    metrics = calculate_metrics(actual, predicted)

                    if metrics['n'] >= 3:
                        results.append({
                            'source': source,
                            'field': field,
                            'pue_factor': pue,
                            'status_filter': status,
                            **metrics
                        })

    return pd.DataFrame(results)


def generate_report(df_results):
    """Generate variance experiment report."""
    print("\n[3/3] Generating report...")

    report_path = os.path.join(OUTPUT_DIR, f"capacity_variance_experiments_{TIMESTAMP}.md")

    with open(report_path, 'w', encoding='utf-8') as f:
        f.write("# Capacity Variance Experiments - All Sources\n\n")
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

        f.write("## Executive Summary\n\n")
        f.write("| Source | Best Field | Best PUE | MAPE (Complete) | Vendor/Meta Ratio | n |\n")
        f.write("|--------|-----------|----------|-----------------|-------------------|---|\n")

        # Find best configuration per source (Complete Build, or ALL if no Complete Build)
        for source in SOURCES:
            source_df = df_results[df_results['source'] == source]

            if len(source_df) == 0:
                f.write(f"| {source} | N/A | N/A | No data | N/A | 0 |\n")
                continue

            # Prefer Complete Build
            complete_df = source_df[source_df['status_filter'] == 'Complete Build']
            if len(complete_df) > 0 and complete_df['mape'].notna().any():
                best_df = complete_df
            else:
                best_df = source_df[source_df['status_filter'] == 'ALL']

            if len(best_df) == 0 or not best_df['mape'].notna().any():
                f.write(f"| {source} | N/A | N/A | No valid data | N/A | 0 |\n")
                continue

            best = best_df.loc[best_df['mape'].idxmin()]
            pue_str = "None" if best['pue_factor'] == 1.0 else f"÷{best['pue_factor']}"
            f.write(f"| **{source}** | {best['field']} | {pue_str} | {best['mape']:.1f}% | {best['ratio']:.2f} | {best['n']} |\n")

        f.write("\n\n")

        # Detailed results per source
        f.write("## Detailed Results by Source\n\n")

        for source in SOURCES:
            source_df = df_results[df_results['source'] == source]

            if len(source_df) == 0:
                f.write(f"### {source}\n\n")
                f.write("No spatial matches found for this source.\n\n")
                continue

            f.write(f"### {source}\n\n")

            # Top 10 configurations sorted by MAPE
            top_10 = source_df.nsmallest(10, 'mape')

            f.write("**Top 10 Configurations (by MAPE):**\n\n")
            f.write("| Field | PUE | Status | MAPE | Bias% | Ratio | n |\n")
            f.write("|-------|-----|--------|------|-------|-------|---|\n")

            for _, row in top_10.iterrows():
                pue_str = "1.0" if row['pue_factor'] == 1.0 else f"{row['pue_factor']}"
                bias_str = f"{row['bias_pct']:+.1f}%" if pd.notna(row['bias_pct']) else "-"
                ratio_str = f"{row['ratio']:.2f}" if pd.notna(row['ratio']) else "-"
                f.write(f"| {row['field']} | {pue_str} | {row['status_filter']} | {row['mape']:.1f}% | {bias_str} | {ratio_str} | {row['n']} |\n")

            f.write("\n")

            # PUE sensitivity analysis
            f.write("**PUE Sensitivity (best field, Complete Build if available):**\n\n")

            # Find best field for this source
            complete_df = source_df[source_df['status_filter'] == 'Complete Build']
            if len(complete_df) > 0 and complete_df['mape'].notna().any():
                best_field_row = complete_df.loc[complete_df['mape'].idxmin()]
            else:
                all_df = source_df[source_df['status_filter'] == 'ALL']
                if len(all_df) > 0 and all_df['mape'].notna().any():
                    best_field_row = all_df.loc[all_df['mape'].idxmin()]
                else:
                    best_field_row = None

            if best_field_row is not None:
                best_field = best_field_row['field']
                best_status = best_field_row['status_filter']

                pue_test = source_df[(source_df['field'] == best_field) &
                                      (source_df['status_filter'] == best_status)]

                f.write(f"Field: `{best_field}` | Status: {best_status}\n\n")
                f.write("| PUE Factor | MAPE | Ratio | Conclusion |\n")
                f.write("|------------|------|-------|------------|\n")

                for _, row in pue_test.sort_values('pue_factor').iterrows():
                    pue = row['pue_factor']
                    mape = row['mape']
                    ratio = row['ratio']

                    if pue == 1.0:
                        conclusion = "No adjustment"
                    elif ratio and 0.9 <= ratio <= 1.1:
                        conclusion = "✅ Good alignment"
                    elif ratio and ratio > 1.1:
                        conclusion = "Over-estimates"
                    else:
                        conclusion = "Under-estimates"

                    # Mark best
                    if pue == best_field_row['pue_factor']:
                        conclusion = f"🏆 BEST - {conclusion}"

                    f.write(f"| {pue} | {mape:.1f}% | {ratio:.2f} | {conclusion} |\n")

                f.write("\n")

            f.write("---\n\n")

        # Recommendations
        f.write("## Recommendations\n\n")
        f.write("Based on the variance experiments, here are the recommended configurations:\n\n")

        f.write("```python\n")
        f.write("RECOMMENDED_CONFIG = {\n")

        for source in SOURCES:
            source_df = df_results[df_results['source'] == source]

            if len(source_df) == 0:
                f.write(f"    '{source}': None,  # No data available\n")
                continue

            # Best Complete Build config, fallback to ALL
            complete_df = source_df[source_df['status_filter'] == 'Complete Build']
            if len(complete_df) > 0 and complete_df['mape'].notna().any():
                best = complete_df.loc[complete_df['mape'].idxmin()]
            else:
                all_df = source_df[source_df['status_filter'] == 'ALL']
                if len(all_df) > 0 and all_df['mape'].notna().any():
                    best = all_df.loc[all_df['mape'].idxmin()]
                else:
                    f.write(f"    '{source}': None,  # No valid comparisons\n")
                    continue

            pue_str = "None" if best['pue_factor'] == 1.0 else best['pue_factor']
            f.write(f"    '{source}': {{\n")
            f.write(f"        'field': '{best['field']}',\n")
            f.write(f"        'pue_adjust': {pue_str != 'None'},\n")
            f.write(f"        'pue_factor': {best['pue_factor']},\n")
            f.write(f"        'mape': {best['mape']:.1f},\n")
            f.write(f"        'n': {best['n']}\n")
            f.write(f"    }},\n")

        f.write("}\n")
        f.write("```\n\n")

        # Key findings
        f.write("## Key Findings\n\n")

        # Sources that report IT capacity (no PUE needed)
        no_pue_sources = []
        pue_sources = []

        for source in SOURCES:
            source_df = df_results[df_results['source'] == source]
            if len(source_df) == 0:
                continue

            complete_df = source_df[source_df['status_filter'] == 'Complete Build']
            if len(complete_df) > 0 and complete_df['mape'].notna().any():
                best = complete_df.loc[complete_df['mape'].idxmin()]
                if best['pue_factor'] == 1.0:
                    no_pue_sources.append(source)
                else:
                    pue_sources.append((source, best['pue_factor']))

        if no_pue_sources:
            f.write(f"**Sources reporting IT capacity (no PUE adjustment needed):**\n")
            for s in no_pue_sources:
                f.write(f"- {s}\n")
            f.write("\n")

        if pue_sources:
            f.write(f"**Sources requiring PUE adjustment:**\n")
            for s, pue in pue_sources:
                f.write(f"- {s}: ÷{pue}\n")
            f.write("\n")

    print(f"   Saved: {report_path}")

    # Also save CSV
    csv_path = os.path.join(OUTPUT_DIR, f"capacity_variance_experiments_{TIMESTAMP}.csv")
    df_results.to_csv(csv_path, index=False)
    print(f"   Saved: {csv_path}")

    return report_path


def print_summary(df_results):
    """Print summary to console."""
    print("\n" + "=" * 80)
    print("📊 CAPACITY VARIANCE EXPERIMENTS - SUMMARY")
    print("=" * 80)

    print("\nBest Configuration per Source (Complete Build priority):")
    print("-" * 70)
    print(f"{'Source':<18} {'Field':<25} {'PUE':>6} {'MAPE':>8} {'Ratio':>7} {'n':>5}")
    print("-" * 70)

    for source in SOURCES:
        source_df = df_results[df_results['source'] == source]

        if len(source_df) == 0:
            print(f"{source:<18} {'(no data)':<25} {'-':>6} {'-':>8} {'-':>7} {0:>5}")
            continue

        complete_df = source_df[source_df['status_filter'] == 'Complete Build']
        if len(complete_df) > 0 and complete_df['mape'].notna().any():
            best = complete_df.loc[complete_df['mape'].idxmin()]
        else:
            all_df = source_df[source_df['status_filter'] == 'ALL']
            if len(all_df) > 0 and all_df['mape'].notna().any():
                best = all_df.loc[all_df['mape'].idxmin()]
            else:
                print(f"{source:<18} {'(no valid data)':<25} {'-':>6} {'-':>8} {'-':>7} {0:>5}")
                continue

        pue_str = "1.0" if best['pue_factor'] == 1.0 else f"{best['pue_factor']}"
        print(f"{source:<18} {best['field']:<25} {pue_str:>6} {best['mape']:>7.1f}% {best['ratio']:>7.2f} {best['n']:>5}")

    print("-" * 70)
    print("\n✅ See full report in outputs/capacity_accuracy/")


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    print("=" * 80)
    print("CAPACITY VARIANCE EXPERIMENTS - ALL SOURCES")
    print("=" * 80)
    print(f"Started: {datetime.now()}")

    df_meta, df_matches = load_data()
    df_results = run_experiments(df_meta, df_matches)

    if len(df_results) > 0:
        report_path = generate_report(df_results)
        print_summary(df_results)
    else:
        print("\n❌ No valid comparisons could be made. Check:")
        print("   1. Do sources have capacity data?")
        print("   2. Are there spatial matches for each source?")
        print("   3. Do Meta buildings have it_load_total?")

    print(f"\nCompleted: {datetime.now()}")
