"""
Full Data Source Audit Script
Analyzes all CSV source files for the Full Data Pipeline transition.

Author: Meta Data Center GIS Team
Date: December 15, 2024
"""

import pandas as pd
import numpy as np
from datetime import datetime
import os
import json

# ============================================================================
# CONFIGURATION
# ============================================================================

CSV_DIR = r"C:\Users\ptanderson\Downloads\Pipeline_Ingestion"
OUTPUT_DIR = r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\outputs\full_data_audit"
TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")

os.makedirs(OUTPUT_DIR, exist_ok=True)

CSV_FILES = {
    'DCH_Hyper_full.csv': 'DataCenterHawk_Hyper',
    'DCH_Lease.csv': 'DataCenterHawk_Lease',
    'SemiAnalysis Global Import.csv': 'Semianalysis',
    'Synergy Hyperscale DC.csv': 'Synergy',
    'Datacentermap.csv': 'DataCenterMap',
    'NPM_DC_11_12_25.csv': 'NewProjectMedia',
    'WoodMac_Campus.csv': 'WoodMac_Campus',
    'WoodMac_DC.csv': 'WoodMac_DC'
}

LEAN_BENCHMARKS = {
    'DataCenterHawk': {'records': 224, 'spatial_recall': 89.9, 'capacity_mape': 17.6},
    'Semianalysis': {'records': 178, 'spatial_recall': 88.8, 'capacity_mape': 11.9},
    'Synergy': {'records': 152, 'spatial_recall': 78.6, 'capacity_mape': None},
    'DataCenterMap': {'records': 67, 'spatial_recall': 53.3, 'capacity_mape': None},
    'NewProjectMedia': {'records': 33, 'spatial_recall': None, 'capacity_mape': None},
    'WoodMac': {'records': 9, 'spatial_recall': None, 'capacity_mape': None}
}


def load_csv_safe(filepath):
    """Load CSV with encoding fallback."""
    for enc in ['utf-8', 'latin-1', 'cp1252']:
        try:
            return pd.read_csv(filepath, encoding=enc, low_memory=False)
        except UnicodeDecodeError:
            continue
    raise ValueError(f"Could not load {filepath}")


def find_fields(columns, keywords):
    """Find columns matching keywords."""
    return [c for c in columns if any(k in c.lower() for k in keywords)]


def analyze_source(filepath, source_name):
    """Analyze a single CSV source."""
    print(f"\n{'='*60}\nAnalyzing: {source_name}\n{'='*60}")

    df = load_csv_safe(filepath)
    n = len(df)

    result = {
        'source': source_name,
        'file': os.path.basename(filepath),
        'records': n,
        'columns': len(df.columns),
        'column_list': list(df.columns),
        'strengths': [],
        'weaknesses': []
    }

    print(f"   Records: {n:,}")
    print(f"   Columns: {len(df.columns)}")

    # Field completeness
    completeness = {c: round(df[c].notna().sum() / n * 100, 1) for c in df.columns}
    result['field_completeness'] = completeness
    high = sum(1 for v in completeness.values() if v >= 90)
    low = sum(1 for v in completeness.values() if v < 50)
    print(f"   Fields >=90% complete: {high}")
    print(f"   Fields <50% complete: {low}")

    # Coordinates
    lat_cols = find_fields(df.columns, ['lat', 'latitude'])
    lon_cols = find_fields(df.columns, ['lon', 'long', 'longitude'])

    if lat_cols and lon_cols:
        lat_col, lon_col = lat_cols[0], lon_cols[0]
        coord_pct = round(df[[lat_col, lon_col]].notna().all(axis=1).sum() / n * 100, 1)
        result['coordinate_coverage'] = coord_pct
        result['lat_field'] = lat_col
        result['lon_field'] = lon_col
        print(f"   Coordinates: {coord_pct}% coverage ({lat_col}, {lon_col})")
        if coord_pct >= 95:
            result['strengths'].append(f"Excellent coordinates ({coord_pct}%)")
        elif coord_pct < 80:
            result['weaknesses'].append(f"Low coordinate coverage ({coord_pct}%)")
    else:
        result['coordinate_coverage'] = 0
        result['weaknesses'].append("Missing coordinate fields")
        print("   Coordinates: MISSING")

    # Capacity
    cap_cols = find_fields(df.columns, ['mw', 'power', 'capacity', 'kw', 'load'])
    result['capacity_fields'] = cap_cols

    if cap_cols:
        cap_stats = {}
        for c in cap_cols[:5]:
            vals = pd.to_numeric(df[c], errors='coerce').dropna()
            if len(vals) > 0:
                cap_stats[c] = {
                    'count': len(vals),
                    'pct': round(len(vals) / n * 100, 1),
                    'min': round(vals.min(), 1),
                    'max': round(vals.max(), 1),
                    'mean': round(vals.mean(), 1)
                }
        result['capacity_stats'] = cap_stats
        best_cap = max([s['pct'] for s in cap_stats.values()]) if cap_stats else 0
        result['best_capacity_coverage'] = best_cap
        print(f"   Capacity fields: {len(cap_cols)} ({best_cap}% best coverage)")
        if best_cap >= 70:
            result['strengths'].append(f"Good capacity data ({best_cap}%)")
        elif best_cap < 30:
            result['weaknesses'].append(f"Low capacity coverage ({best_cap}%)")
    else:
        result['best_capacity_coverage'] = 0
        result['weaknesses'].append("No capacity fields")
        print("   Capacity fields: NONE")

    # Company
    company_cols = find_fields(df.columns, ['company', 'owner', 'operator', 'customer', 'tenant'])
    if company_cols:
        c = company_cols[0]
        unique = df[c].dropna().nunique()
        result['company_field'] = c
        result['unique_companies'] = unique
        sample = list(df[c].dropna().unique()[:5])
        result['company_sample'] = [str(x) for x in sample]
        print(f"   Companies: {unique} unique ({c})")
        print(f"   Sample: {', '.join(str(x) for x in sample)}")
    else:
        result['unique_companies'] = 0
        print("   Companies: No field found")

    # Geography
    country_cols = find_fields(df.columns, ['country'])
    region_cols = find_fields(df.columns, ['region'])

    if country_cols:
        countries = df[country_cols[0]].dropna().nunique()
        top = list(df[country_cols[0]].value_counts().head(5).index)
        result['unique_countries'] = countries
        result['top_countries'] = [str(x) for x in top]
        print(f"   Countries: {countries} ({', '.join(str(x) for x in top[:3])})")

    if region_cols:
        regions = list(df[region_cols[0]].dropna().unique())
        result['regions'] = [str(r) for r in regions]
        print(f"   Regions: {', '.join(str(r) for r in regions[:5])}")

        r_upper = [str(r).upper() for r in regions]
        has_amer = any('AMER' in r or 'US' in r or 'NORTH' in r for r in r_upper)
        has_emea = any('EMEA' in r or 'EURO' in r for r in r_upper)
        has_apac = any('APAC' in r or 'ASIA' in r for r in r_upper)

        if has_amer and has_emea and has_apac:
            result['strengths'].append("Global coverage (AMER/EMEA/APAC)")
        elif has_amer and not has_emea and not has_apac:
            result['weaknesses'].append("Americas only - no EMEA/APAC")

    # Duplicates
    dup_pct = round(df.duplicated().sum() / n * 100, 1)
    result['duplicate_pct'] = dup_pct
    if dup_pct > 5:
        result['weaknesses'].append(f"High duplicates ({dup_pct}%)")

    print(f"\n   Strengths: {', '.join(result['strengths']) or 'None identified'}")
    print(f"   Weaknesses: {', '.join(result['weaknesses']) or 'None identified'}")

    return result


def main():
    """Run the full audit."""
    print("=" * 80)
    print("FULL DATA SOURCE AUDIT")
    print("=" * 80)
    print(f"Started: {datetime.now()}")
    print(f"CSV Directory: {CSV_DIR}\n")

    results = {}

    for filename, source_name in CSV_FILES.items():
        filepath = os.path.join(CSV_DIR, filename)
        if os.path.exists(filepath):
            try:
                results[source_name] = analyze_source(filepath, source_name)
            except Exception as e:
                print(f"\nERROR with {source_name}: {e}")
        else:
            print(f"\nWARNING: {filename} not found")

    # Comparison to Lean
    print("\n" + "=" * 80)
    print("FULL vs LEAN COMPARISON")
    print("=" * 80)
    print(f"\n{'Source':<25} {'Lean':>10} {'Full':>10} {'Multiplier':>12}")
    print("-" * 60)

    for source, data in results.items():
        for lean_key in LEAN_BENCHMARKS:
            if lean_key.lower() in source.lower():
                lean_n = LEAN_BENCHMARKS[lean_key]['records']
                full_n = data['records']
                mult = round(full_n / lean_n, 1) if lean_n else 0
                print(f"{source:<25} {lean_n:>10,} {full_n:>10,} {mult:>11}x")
                break

    # Summary
    print("\n" + "=" * 80)
    print("EXECUTIVE SUMMARY")
    print("=" * 80)

    total = sum(r['records'] for r in results.values())
    print(f"\nTotal records across all sources: {total:,}")
    print(f"Lean model had: ~663 records (Meta/Oracle only)")
    print(f"Expansion factor: ~{total // 663}x\n")

    print(f"{'Source':<25} {'Records':>10} {'Coord%':>8} {'Cap%':>8} {'Companies':>10}")
    print("-" * 70)
    for name, r in sorted(results.items(), key=lambda x: -x[1]['records']):
        coord = r.get('coordinate_coverage', 0)
        cap = r.get('best_capacity_coverage', 0)
        comp = r.get('unique_companies', 0)
        print(f"{name:<25} {r['records']:>10,} {coord:>7.1f}% {cap:>7.1f}% {comp:>10}")

    # Save outputs
    print("\n" + "=" * 80)
    print("SAVING OUTPUTS")
    print("=" * 80)

    # JSON
    json_path = os.path.join(OUTPUT_DIR, f"audit_results_{TIMESTAMP}.json")
    with open(json_path, 'w') as f:
        json.dump(results, f, indent=2, default=str)
    print(f"   Saved: {json_path}")

    # CSV summary
    summary_rows = []
    for name, r in results.items():
        summary_rows.append({
            'source': name,
            'records': r['records'],
            'columns': r['columns'],
            'coord_coverage': r.get('coordinate_coverage', 0),
            'capacity_coverage': r.get('best_capacity_coverage', 0),
            'unique_companies': r.get('unique_companies', 0),
            'strengths': '; '.join(r.get('strengths', [])),
            'weaknesses': '; '.join(r.get('weaknesses', []))
        })

    csv_path = os.path.join(OUTPUT_DIR, f"audit_summary_{TIMESTAMP}.csv")
    pd.DataFrame(summary_rows).to_csv(csv_path, index=False)
    print(f"   Saved: {csv_path}")

    print(f"\nCompleted: {datetime.now()}")
    return results


if __name__ == "__main__":
    results = main()
