"""
Capacity Accuracy - Variance Analysis Experiments
Quick experiments to understand sources of error in capacity comparison.

Author: Meta Data Center GIS Team
Date: December 10, 2024
"""

import arcpy
import pandas as pd
import numpy as np
from collections import defaultdict

GDB = r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\Default.gdb"

def calc_mape(actual, predicted):
    """Calculate MAPE and sample size."""
    mask = ~(np.isnan(actual) | np.isnan(predicted)) & (actual > 0) & (predicted > 0)
    if mask.sum() < 5:
        return None, None, 0
    a, p = actual[mask], predicted[mask]
    mape = np.mean(np.abs((a - p) / a)) * 100
    bias = np.mean(p - a) / np.mean(a) * 100
    return mape, bias, mask.sum()


def main():
    print("=" * 70)
    print("CAPACITY ACCURACY - VARIANCE ANALYSIS EXPERIMENTS")
    print("=" * 70)
    print()

    # Load Meta buildings
    meta_fields = ['building_key', 'dc_code', 'new_build_status', 'it_load_total']
    meta_data = []
    with arcpy.da.SearchCursor(GDB + '/meta_canonical_buildings', meta_fields) as c:
        for row in c:
            meta_data.append(dict(zip(meta_fields, row)))
    df_meta = pd.DataFrame(meta_data)
    df_meta = df_meta[df_meta['it_load_total'].notna() & (df_meta['it_load_total'] > 0)]

    # Load spatial matches
    match_fields = ['building_key', 'dc_code', 'source', 'distance_m',
                    'commissioned_power_mw', 'mw_2023', 'mw_2024', 'mw_2025']
    available = [f.name for f in arcpy.ListFields(GDB + '/accuracy_analysis_multi_source_REBUILT')]
    match_fields = [f for f in match_fields if f in available]

    match_data = []
    with arcpy.da.SearchCursor(GDB + '/accuracy_analysis_multi_source_REBUILT', match_fields) as c:
        for row in c:
            match_data.append(dict(zip(match_fields, row)))
    df_matches = pd.DataFrame(match_data)

    # Filter to Semianalysis only
    df_semi = df_matches[df_matches['source'] == 'Semianalysis'].copy()
    df_semi['distance_m'] = pd.to_numeric(df_semi['distance_m'], errors='coerce')

    # Dedupe to closest match per building
    df_semi = df_semi.loc[df_semi.groupby('building_key')['distance_m'].idxmin()]

    # Join with Meta
    df_analysis = df_semi.merge(df_meta[['building_key', 'it_load_total', 'new_build_status']], on='building_key')
    df_complete = df_analysis[df_analysis['new_build_status'] == 'Complete Build'].copy()
    df_active = df_analysis[df_analysis['new_build_status'] == 'Active Build'].copy()

    print("EXPERIMENT 1: Year Field Comparison (Complete Builds Only)")
    print("-" * 60)
    for field in ['mw_2023', 'mw_2024', 'mw_2025', 'commissioned_power_mw']:
        if field in df_complete.columns:
            mape, bias, n = calc_mape(df_complete['it_load_total'].values, df_complete[field].values)
            if mape:
                print(f"  {field:25s}: MAPE = {mape:.1f}%, Bias = {bias:+.1f}% (n={n})")

    print()
    print("EXPERIMENT 2: Utilization Adjustment (mw_2024 * factor)")
    print("-" * 60)
    print("  Testing if Semianalysis reports installed capacity vs actual load...")
    for factor in [1.0, 0.95, 0.90, 0.85, 0.80, 0.75]:
        adjusted = df_complete['mw_2024'].values * factor
        mape, bias, n = calc_mape(df_complete['it_load_total'].values, adjusted)
        if mape:
            marker = " <-- " if abs(bias) < 3 else ""
            print(f"  Factor {factor:.2f}: MAPE = {mape:.1f}%, Bias = {bias:+.1f}%{marker}")

    print()
    print("EXPERIMENT 3: Distance Threshold Impact")
    print("-" * 60)
    print("  Testing if tighter spatial matching improves accuracy...")
    for threshold in [50000, 20000, 10000, 5000, 2000, 1000]:
        df_thresh = df_analysis[(df_analysis['distance_m'] <= threshold) &
                                (df_analysis['new_build_status'] == 'Complete Build')]
        if len(df_thresh) >= 5:
            mape, bias, n = calc_mape(df_thresh['it_load_total'].values, df_thresh['mw_2024'].values)
            if mape:
                print(f"  <={threshold/1000:.0f}km: MAPE = {mape:.1f}%, Bias = {bias:+.1f}% (n={n})")

    print()
    print("EXPERIMENT 4: Error Distribution Analysis (Complete Builds)")
    print("-" * 60)
    df_err = df_complete[df_complete['mw_2024'].notna() & (df_complete['mw_2024'] > 0)].copy()
    df_err['error_pct'] = (df_err['mw_2024'] - df_err['it_load_total']) / df_err['it_load_total'] * 100
    df_err['abs_error_pct'] = np.abs(df_err['error_pct'])

    print(f"  Sample size: {len(df_err)}")
    print(f"  Mean error: {df_err['error_pct'].mean():+.1f}%")
    print(f"  Median error: {df_err['error_pct'].median():+.1f}%")
    print(f"  Std dev: {df_err['error_pct'].std():.1f}%")
    print()
    print("  Error percentiles:")
    for p in [10, 25, 50, 75, 90]:
        val = np.percentile(df_err['error_pct'].dropna(), p)
        print(f"    P{p}: {val:+.1f}%")

    print()
    print("EXPERIMENT 5: Outlier Impact Analysis")
    print("-" * 60)
    # Buildings with >50% error
    outliers = df_err[df_err['abs_error_pct'] > 50]
    good = df_err[df_err['abs_error_pct'] <= 25]
    moderate = df_err[(df_err['abs_error_pct'] > 25) & (df_err['abs_error_pct'] <= 50)]

    print(f"  Error bands:")
    print(f"    <25% error (Good):     {len(good):3d} buildings ({100*len(good)/len(df_err):.0f}%)")
    print(f"    25-50% error (Moderate): {len(moderate):3d} buildings ({100*len(moderate)/len(df_err):.0f}%)")
    print(f"    >50% error (Outliers):  {len(outliers):3d} buildings ({100*len(outliers)/len(df_err):.0f}%)")

    # MAPE without outliers
    df_no_outliers = df_err[df_err['abs_error_pct'] <= 50]
    if len(df_no_outliers) >= 5:
        mape_no_out, bias_no_out, n_no_out = calc_mape(
            df_no_outliers['it_load_total'].values,
            df_no_outliers['mw_2024'].values
        )
        print()
        print(f"  MAPE excluding >50% outliers: {mape_no_out:.1f}% (n={n_no_out})")

    print()
    print("EXPERIMENT 6: Worst Outliers Deep Dive")
    print("-" * 60)
    print("  Top 5 Over-estimates (vendor > Meta):")
    over = df_err.nlargest(5, 'error_pct')[['building_key', 'it_load_total', 'mw_2024', 'error_pct', 'distance_m']]
    for _, r in over.iterrows():
        bk = str(r['building_key'])[:12]
        print(f"    {bk:12s}: Meta={r['it_load_total']:5.0f}MW, Semi={r['mw_2024']:5.0f}MW, Err={r['error_pct']:+5.0f}%, Dist={r['distance_m']:6.0f}m")

    print()
    print("  Top 5 Under-estimates (vendor < Meta):")
    under = df_err.nsmallest(5, 'error_pct')[['building_key', 'it_load_total', 'mw_2024', 'error_pct', 'distance_m']]
    for _, r in under.iterrows():
        bk = str(r['building_key'])[:12]
        print(f"    {bk:12s}: Meta={r['it_load_total']:5.0f}MW, Semi={r['mw_2024']:5.0f}MW, Err={r['error_pct']:+5.0f}%, Dist={r['distance_m']:6.0f}m")

    print()
    print("EXPERIMENT 7: Active Builds Analysis")
    print("-" * 60)
    if len(df_active) >= 5:
        for field in ['mw_2024', 'mw_2025', 'commissioned_power_mw']:
            if field in df_active.columns:
                mape, bias, n = calc_mape(df_active['it_load_total'].values, df_active[field].values)
                if mape:
                    print(f"  {field:25s}: MAPE = {mape:.1f}%, Bias = {bias:+.1f}% (n={n})")

        # Check if future year is better for active
        print()
        print("  Active builds might be better predicted by future year fields")
        print("  (since they're still ramping up)")

    print()
    print("=" * 70)
    print("VARIANCE ANALYSIS SUMMARY")
    print("=" * 70)
    print()
    print("Key findings:")
    print("  1. Year field impact: Check which year aligns best with Meta data timing")
    print("  2. Utilization: If bias is positive, vendors report higher than actual")
    print("  3. Distance: Tighter matching may filter false positives")
    print("  4. Outliers: A few bad matches can skew MAPE significantly")
    print()


if __name__ == "__main__":
    main()
