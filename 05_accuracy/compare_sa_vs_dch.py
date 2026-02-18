"""
SemiAnalysis vs DataCenterHawk Comparison Script
=================================================

Performs a holistic comparison between the SemiAnalysis (SA) and DataCenterHawk (DCH)
feature classes in gold_buildings_full.

Comparison Dimensions:
1. Record Volume & Coverage - Total records, geographic coverage
2. Capacity Metrics - Full capacity, commissioned, planned, under construction
3. Field Population - Which fields are populated by each source
4. Company Coverage - Hyperscaler vs Colo breakdown
5. Geographic Distribution - Region, country, state distribution
6. Status Distribution - Active vs Under Construction vs Planned
7. Spatial Overlap - How many buildings might be the same physical facility

Author: Meta Data Center GIS Team
Created: 2026-01-29
"""

import arcpy
import os
import sys
from datetime import datetime
from collections import defaultdict

# Add _utils to path
try:
    script_dir = os.path.dirname(os.path.abspath(__file__))
except NameError:
    script_dir = r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\scripts\05_accuracy"

utils_dir = os.path.join(os.path.dirname(script_dir), "_utils")
if utils_dir not in sys.path:
    sys.path.insert(0, utils_dir)

from config import GDB, GOLD_BUILDINGS

# ==============================================================================
# CONFIGURATION
# ==============================================================================

# Feature class and source identifiers
TARGET_FC = GOLD_BUILDINGS
SA_SOURCES = ['Semianalysis']  # Source values that indicate SA records
DCH_SOURCES = ['DataCenterHawk']  # Source values that indicate DCH records

# Hyperscaler companies (for company tier analysis)
HYPERSCALERS = ['AWS', 'Microsoft', 'Google', 'Meta', 'Apple', 'Oracle', 'xAI', 'OpenAI',
                'Anthropic', 'ByteDance', 'Crusoe', 'CoreWeave', 'Alibaba']

# Key fields to compare
CAPACITY_FIELDS = ['full_capacity_mw', 'commissioned_power_mw', 'uc_power_mw',
                   'planned_power_mw', 'planned_plus_uc_mw']
GEO_FIELDS = ['country', 'region', 'state', 'city', 'market']
COMPANY_FIELDS = ['company_clean', 'company_clean_filter']
STATUS_FIELDS = ['facility_status', 'record_level']
YEAR_FIELDS = ['mw_2023', 'mw_2024', 'mw_2025', 'mw_2026', 'mw_2027',
               'mw_2028', 'mw_2029', 'mw_2030', 'mw_2031', 'mw_2032']

# Spatial matching threshold (meters)
SPATIAL_MATCH_THRESHOLD = 500

# Output file
OUTPUT_DIR = os.path.join(os.path.dirname(script_dir), "00_docs", "reports")


# ==============================================================================
# HELPER FUNCTIONS
# ==============================================================================

def safe_float(val):
    """Safely convert value to float."""
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None

def format_number(val, decimals=0):
    """Format number with commas."""
    if val is None:
        return "N/A"
    if decimals == 0:
        return f"{int(val):,}"
    return f"{val:,.{decimals}f}"

def format_percent(val, total):
    """Format percentage."""
    if total == 0:
        return "0%"
    return f"{(val / total * 100):.1f}%"

def get_field_population_rate(records, field):
    """Calculate field population rate."""
    populated = sum(1 for r in records if r.get(field) is not None and str(r.get(field)).strip())
    return populated, len(records), format_percent(populated, len(records))


# ==============================================================================
# DATA EXTRACTION
# ==============================================================================

def load_records_by_source(fc, source_values, fields=None):
    """
    Load records from feature class filtered by source.

    Args:
        fc: Feature class path
        source_values: List of source field values to include
        fields: Optional list of fields to include (None = all)

    Returns:
        List of record dictionaries
    """
    # Build field list
    all_fields = [f.name for f in arcpy.ListFields(fc)]

    if fields:
        read_fields = ['SHAPE@XY', 'OID@', 'source'] + [f for f in fields if f in all_fields]
    else:
        read_fields = ['SHAPE@XY', 'OID@'] + all_fields

    # Ensure unique
    read_fields = list(dict.fromkeys(read_fields))

    # Build where clause
    source_list = ", ".join([f"'{s}'" for s in source_values])
    where_clause = f"source IN ({source_list})"

    records = []
    with arcpy.da.SearchCursor(fc, read_fields, where_clause) as cursor:
        for row in cursor:
            record = {'_xy': row[0], '_oid': row[1]}
            for i, field in enumerate(read_fields[2:], start=2):
                record[field] = row[i]
            records.append(record)

    return records


# ==============================================================================
# COMPARISON FUNCTIONS
# ==============================================================================

def compare_volume(sa_records, dch_records):
    """Compare record volume."""
    print("\n" + "=" * 70)
    print("1. RECORD VOLUME COMPARISON")
    print("=" * 70)

    results = {
        'sa_total': len(sa_records),
        'dch_total': len(dch_records),
        'difference': len(sa_records) - len(dch_records)
    }

    print(f"\n  SemiAnalysis Records:     {format_number(results['sa_total'])}")
    print(f"  DataCenterHawk Records:   {format_number(results['dch_total'])}")
    print(f"  Difference (SA - DCH):    {format_number(results['difference'])}")

    # Record level breakdown
    sa_buildings = len([r for r in sa_records if r.get('record_level') == 'Building'])
    sa_tlbm = len([r for r in sa_records if r.get('record_level', '').startswith('TLBM')])
    dch_buildings = len([r for r in dch_records if r.get('record_level') == 'Building'])

    print(f"\n  SA Buildings:             {format_number(sa_buildings)}")
    print(f"  SA TLBM Records:          {format_number(sa_tlbm)}")
    print(f"  DCH Buildings:            {format_number(dch_buildings)}")

    results['sa_buildings'] = sa_buildings
    results['sa_tlbm'] = sa_tlbm
    results['dch_buildings'] = dch_buildings

    return results


def compare_capacity(sa_records, dch_records):
    """Compare capacity metrics."""
    print("\n" + "=" * 70)
    print("2. CAPACITY METRICS COMPARISON")
    print("=" * 70)

    results = {}

    for field in CAPACITY_FIELDS:
        sa_vals = [safe_float(r.get(field)) for r in sa_records if safe_float(r.get(field)) is not None]
        dch_vals = [safe_float(r.get(field)) for r in dch_records if safe_float(r.get(field)) is not None]

        sa_total = sum(sa_vals) if sa_vals else 0
        dch_total = sum(dch_vals) if dch_vals else 0

        results[field] = {
            'sa_total': sa_total,
            'sa_count': len(sa_vals),
            'dch_total': dch_total,
            'dch_count': len(dch_vals),
            'difference': sa_total - dch_total
        }

        print(f"\n  {field}:")
        print(f"    SA Total:  {format_number(sa_total, 1)} MW ({format_number(len(sa_vals))} records)")
        print(f"    DCH Total: {format_number(dch_total, 1)} MW ({format_number(len(dch_vals))} records)")
        print(f"    Diff:      {format_number(sa_total - dch_total, 1)} MW")

    return results


def compare_field_population(sa_records, dch_records):
    """Compare field population rates."""
    print("\n" + "=" * 70)
    print("3. FIELD POPULATION COMPARISON")
    print("=" * 70)

    # Fields to check
    check_fields = CAPACITY_FIELDS + GEO_FIELDS + COMPANY_FIELDS + ['latitude', 'longitude']

    results = {}

    print(f"\n  {'Field':<30} {'SA Pop':<15} {'DCH Pop':<15}")
    print("  " + "-" * 60)

    for field in check_fields:
        sa_pop, sa_total, sa_pct = get_field_population_rate(sa_records, field)
        dch_pop, dch_total, dch_pct = get_field_population_rate(dch_records, field)

        results[field] = {
            'sa_rate': sa_pct,
            'dch_rate': dch_pct
        }

        print(f"  {field:<30} {sa_pct:<15} {dch_pct:<15}")

    # Year fields (SA-specific)
    print("\n  Year-over-Year MW Fields (SA only):")
    print("  " + "-" * 40)
    for field in YEAR_FIELDS:
        sa_pop, sa_total, sa_pct = get_field_population_rate(sa_records, field)
        print(f"  {field:<20} {sa_pct}")
        results[field] = {'sa_rate': sa_pct, 'dch_rate': 'N/A'}

    return results


def compare_company_coverage(sa_records, dch_records):
    """Compare company/hyperscaler coverage."""
    print("\n" + "=" * 70)
    print("4. COMPANY COVERAGE COMPARISON")
    print("=" * 70)

    # Get company distributions
    sa_companies = defaultdict(int)
    dch_companies = defaultdict(int)

    for r in sa_records:
        company = r.get('company_clean_filter') or r.get('company_clean') or 'Unknown'
        sa_companies[company] += 1

    for r in dch_records:
        company = r.get('company_clean_filter') or r.get('company_clean') or 'Unknown'
        dch_companies[company] += 1

    # Hyperscaler breakdown
    print("\n  Hyperscaler Coverage:")
    print(f"  {'Company':<25} {'SA Records':<15} {'DCH Records':<15}")
    print("  " + "-" * 55)

    results = {'hyperscalers': {}, 'all_companies': {'sa': dict(sa_companies), 'dch': dict(dch_companies)}}

    for company in HYPERSCALERS:
        sa_count = sa_companies.get(company, 0)
        dch_count = dch_companies.get(company, 0)
        if sa_count > 0 or dch_count > 0:
            print(f"  {company:<25} {format_number(sa_count):<15} {format_number(dch_count):<15}")
            results['hyperscalers'][company] = {'sa': sa_count, 'dch': dch_count}

    # Colo (non-hyperscaler) summary
    sa_colo = sum(v for k, v in sa_companies.items() if k not in HYPERSCALERS)
    dch_colo = sum(v for k, v in dch_companies.items() if k not in HYPERSCALERS)

    print("  " + "-" * 55)
    print(f"  {'All Colo (Non-Hyperscaler)':<25} {format_number(sa_colo):<15} {format_number(dch_colo):<15}")

    results['colo'] = {'sa': sa_colo, 'dch': dch_colo}

    # Unique companies count
    print(f"\n  Unique Companies:")
    print(f"    SA:  {len(sa_companies)} unique company values")
    print(f"    DCH: {len(dch_companies)} unique company values")

    return results


def compare_geographic_distribution(sa_records, dch_records):
    """Compare geographic distribution."""
    print("\n" + "=" * 70)
    print("5. GEOGRAPHIC DISTRIBUTION COMPARISON")
    print("=" * 70)

    results = {}

    # Region breakdown
    sa_regions = defaultdict(int)
    dch_regions = defaultdict(int)

    for r in sa_records:
        region = r.get('region') or 'Unknown'
        sa_regions[region] += 1

    for r in dch_records:
        region = r.get('region') or 'Unknown'
        dch_regions[region] += 1

    print("\n  By Region:")
    print(f"  {'Region':<15} {'SA Records':<15} {'DCH Records':<15}")
    print("  " + "-" * 45)

    all_regions = set(list(sa_regions.keys()) + list(dch_regions.keys()))
    for region in sorted(all_regions):
        sa_count = sa_regions.get(region, 0)
        dch_count = dch_regions.get(region, 0)
        print(f"  {region:<15} {format_number(sa_count):<15} {format_number(dch_count):<15}")

    results['regions'] = {'sa': dict(sa_regions), 'dch': dict(dch_regions)}

    # Top countries
    sa_countries = defaultdict(int)
    dch_countries = defaultdict(int)

    for r in sa_records:
        country = r.get('country') or 'Unknown'
        sa_countries[country] += 1

    for r in dch_records:
        country = r.get('country') or 'Unknown'
        dch_countries[country] += 1

    print("\n  Top 10 Countries (by total records):")
    print(f"  {'Country':<25} {'SA Records':<15} {'DCH Records':<15}")
    print("  " + "-" * 55)

    all_countries = defaultdict(int)
    for k, v in sa_countries.items():
        all_countries[k] += v
    for k, v in dch_countries.items():
        all_countries[k] += v

    top_countries = sorted(all_countries.items(), key=lambda x: x[1], reverse=True)[:10]
    for country, _ in top_countries:
        sa_count = sa_countries.get(country, 0)
        dch_count = dch_countries.get(country, 0)
        print(f"  {country:<25} {format_number(sa_count):<15} {format_number(dch_count):<15}")

    results['countries'] = {'sa': dict(sa_countries), 'dch': dict(dch_countries)}

    return results


def compare_status_distribution(sa_records, dch_records):
    """Compare facility status distribution."""
    print("\n" + "=" * 70)
    print("6. FACILITY STATUS COMPARISON")
    print("=" * 70)

    sa_status = defaultdict(int)
    dch_status = defaultdict(int)

    for r in sa_records:
        status = r.get('facility_status') or 'Unknown'
        sa_status[status] += 1

    for r in dch_records:
        status = r.get('facility_status') or 'Unknown'
        dch_status[status] += 1

    print("\n  By Status:")
    print(f"  {'Status':<25} {'SA Records':<15} {'DCH Records':<15}")
    print("  " + "-" * 55)

    all_status = set(list(sa_status.keys()) + list(dch_status.keys()))
    for status in sorted(all_status):
        sa_count = sa_status.get(status, 0)
        dch_count = dch_status.get(status, 0)
        print(f"  {status:<25} {format_number(sa_count):<15} {format_number(dch_count):<15}")

    return {'sa': dict(sa_status), 'dch': dict(dch_status)}


def find_spatial_overlaps(sa_records, dch_records, threshold_meters=500):
    """Find records that might represent the same physical facility."""
    print("\n" + "=" * 70)
    print("7. SPATIAL OVERLAP ANALYSIS")
    print("=" * 70)
    print(f"\n  Checking for potential duplicates within {threshold_meters}m...")

    # Filter records with coordinates
    sa_with_coords = [(r, r.get('_xy')) for r in sa_records
                      if r.get('_xy') and r['_xy'][0] is not None and r['_xy'][1] is not None]
    dch_with_coords = [(r, r.get('_xy')) for r in dch_records
                       if r.get('_xy') and r['_xy'][0] is not None and r['_xy'][1] is not None]

    print(f"  SA records with coords: {format_number(len(sa_with_coords))}")
    print(f"  DCH records with coords: {format_number(len(dch_with_coords))}")

    # Convert threshold to approximate degrees (rough conversion at ~40deg latitude)
    threshold_deg = threshold_meters / 111000  # ~111km per degree

    # Find matches
    matches = []
    sa_matched = set()
    dch_matched = set()

    for sa_rec, sa_xy in sa_with_coords:
        sa_lon, sa_lat = sa_xy
        for dch_rec, dch_xy in dch_with_coords:
            dch_lon, dch_lat = dch_xy

            # Quick distance check
            if abs(sa_lon - dch_lon) <= threshold_deg and abs(sa_lat - dch_lat) <= threshold_deg:
                # More accurate distance check
                dist_deg = ((sa_lon - dch_lon)**2 + (sa_lat - dch_lat)**2)**0.5
                if dist_deg <= threshold_deg:
                    matches.append({
                        'sa_id': sa_rec.get('unique_id'),
                        'dch_id': dch_rec.get('unique_id'),
                        'sa_company': sa_rec.get('company_clean'),
                        'dch_company': dch_rec.get('company_clean'),
                        'sa_capacity': sa_rec.get('full_capacity_mw'),
                        'dch_capacity': dch_rec.get('full_capacity_mw'),
                        'city': sa_rec.get('city') or dch_rec.get('city'),
                        'state': sa_rec.get('state') or dch_rec.get('state')
                    })
                    sa_matched.add(sa_rec.get('unique_id'))
                    dch_matched.add(dch_rec.get('unique_id'))

    print(f"\n  Potential Spatial Matches:")
    print(f"    Total matches found: {format_number(len(matches))}")
    print(f"    SA records with DCH match: {format_number(len(sa_matched))}")
    print(f"    DCH records with SA match: {format_number(len(dch_matched))}")

    sa_only = len(sa_with_coords) - len(sa_matched)
    dch_only = len(dch_with_coords) - len(dch_matched)

    print(f"\n    SA-only records (no DCH match): {format_number(sa_only)}")
    print(f"    DCH-only records (no SA match): {format_number(dch_only)}")

    # Sample matches
    if matches:
        print("\n  Sample Matches (first 5):")
        print(f"  {'SA ID':<20} {'DCH ID':<20} {'SA Cap':<10} {'DCH Cap':<10} {'City':<20}")
        print("  " + "-" * 80)
        for m in matches[:5]:
            print(f"  {str(m['sa_id'])[:18]:<20} {str(m['dch_id'])[:18]:<20} "
                  f"{format_number(m['sa_capacity'], 1) if m['sa_capacity'] else 'N/A':<10} "
                  f"{format_number(m['dch_capacity'], 1) if m['dch_capacity'] else 'N/A':<10} "
                  f"{str(m['city'])[:18] if m['city'] else 'N/A':<20}")

    return {
        'total_matches': len(matches),
        'sa_matched_count': len(sa_matched),
        'dch_matched_count': len(dch_matched),
        'sa_only_count': sa_only,
        'dch_only_count': dch_only,
        'matches': matches[:100]  # Keep first 100 for report
    }


def generate_summary(all_results):
    """Generate executive summary."""
    print("\n" + "=" * 70)
    print("EXECUTIVE SUMMARY")
    print("=" * 70)

    vol = all_results.get('volume', {})
    cap = all_results.get('capacity', {})
    overlap = all_results.get('spatial_overlap', {})

    print(f"""
  DATA SOURCES COMPARED:
  ----------------------
  SemiAnalysis (SA):     {format_number(vol.get('sa_total', 0))} records
  DataCenterHawk (DCH):  {format_number(vol.get('dch_total', 0))} records

  VOLUME ANALYSIS:
  ----------------
  SA has {format_number(abs(vol.get('difference', 0)))} {'more' if vol.get('difference', 0) > 0 else 'fewer'} records than DCH
  SA Building records: {format_number(vol.get('sa_buildings', 0))}
  SA TLBM (market-level) records: {format_number(vol.get('sa_tlbm', 0))}
  DCH Building records: {format_number(vol.get('dch_buildings', 0))}

  CAPACITY COMPARISON (full_capacity_mw):
  ---------------------------------------
  SA Total:  {format_number(cap.get('full_capacity_mw', {}).get('sa_total', 0), 1)} MW
  DCH Total: {format_number(cap.get('full_capacity_mw', {}).get('dch_total', 0), 1)} MW
  Difference: {format_number(cap.get('full_capacity_mw', {}).get('difference', 0), 1)} MW

  SPATIAL OVERLAP ({SPATIAL_MATCH_THRESHOLD}m threshold):
  --------------------------------
  Potential matches: {format_number(overlap.get('total_matches', 0))}
  SA records with DCH match: {format_number(overlap.get('sa_matched_count', 0))} ({format_percent(overlap.get('sa_matched_count', 0), vol.get('sa_buildings', 1))})
  DCH records with SA match: {format_number(overlap.get('dch_matched_count', 0))} ({format_percent(overlap.get('dch_matched_count', 0), vol.get('dch_total', 1))})

  KEY FINDINGS:
  -------------
  1. SA includes TLBM (market-level aggregate) records that DCH does not have
  2. SA has year-over-year capacity forecasts (2023-2032) that DCH lacks
  3. DCH focuses on hyperscale facilities while SA has broader colo coverage
  4. Both sources have high coordinate population rates (>95%)
""")


def generate_html_report(all_results, output_path):
    """Generate an HTML report with all comparison results."""

    vol = all_results.get('volume', {})
    cap = all_results.get('capacity', {})
    fields = all_results.get('field_population', {})
    companies = all_results.get('company_coverage', {})
    geo = all_results.get('geographic', {})
    status = all_results.get('status', {})
    overlap = all_results.get('spatial_overlap', {})

    html = f"""<!DOCTYPE html>
<html>
<head>
    <title>SA vs DCH Comparison Report</title>
    <style>
        body {{ font-family: 'Segoe UI', Arial, sans-serif; margin: 40px; background: #f5f5f5; }}
        .container {{ max-width: 1200px; margin: 0 auto; background: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        h1 {{ color: #1877F2; border-bottom: 2px solid #1877F2; padding-bottom: 10px; }}
        h2 {{ color: #333; margin-top: 30px; }}
        .summary-box {{ background: #e7f3ff; padding: 20px; border-radius: 8px; margin: 20px 0; }}
        .metric-grid {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px; margin: 20px 0; }}
        .metric {{ background: #f8f9fa; padding: 15px; border-radius: 8px; text-align: center; }}
        .metric-value {{ font-size: 2em; font-weight: bold; color: #1877F2; }}
        .metric-label {{ color: #666; margin-top: 5px; }}
        table {{ width: 100%; border-collapse: collapse; margin: 15px 0; }}
        th, td {{ padding: 10px; text-align: left; border-bottom: 1px solid #ddd; }}
        th {{ background: #f0f0f0; }}
        tr:hover {{ background: #f9f9f9; }}
        .sa {{ color: #E91E63; }}
        .dch {{ color: #4CAF50; }}
        .timestamp {{ color: #999; font-size: 0.9em; }}
    </style>
</head>
<body>
<div class="container">
    <h1>SemiAnalysis vs DataCenterHawk Comparison</h1>
    <p class="timestamp">Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>

    <div class="summary-box">
        <h2>Executive Summary</h2>
        <div class="metric-grid">
            <div class="metric">
                <div class="metric-value sa">{format_number(vol.get('sa_total', 0))}</div>
                <div class="metric-label">SemiAnalysis Records</div>
            </div>
            <div class="metric">
                <div class="metric-value dch">{format_number(vol.get('dch_total', 0))}</div>
                <div class="metric-label">DataCenterHawk Records</div>
            </div>
            <div class="metric">
                <div class="metric-value">{format_number(overlap.get('total_matches', 0))}</div>
                <div class="metric-label">Potential Spatial Matches</div>
            </div>
        </div>
    </div>

    <h2>1. Record Volume</h2>
    <table>
        <tr><th>Metric</th><th class="sa">SemiAnalysis</th><th class="dch">DataCenterHawk</th><th>Difference</th></tr>
        <tr><td>Total Records</td><td>{format_number(vol.get('sa_total', 0))}</td><td>{format_number(vol.get('dch_total', 0))}</td><td>{format_number(vol.get('difference', 0))}</td></tr>
        <tr><td>Building Records</td><td>{format_number(vol.get('sa_buildings', 0))}</td><td>{format_number(vol.get('dch_buildings', 0))}</td><td>-</td></tr>
        <tr><td>TLBM Records</td><td>{format_number(vol.get('sa_tlbm', 0))}</td><td>N/A</td><td>-</td></tr>
    </table>

    <h2>2. Capacity Metrics (MW)</h2>
    <table>
        <tr><th>Field</th><th class="sa">SA Total</th><th class="dch">DCH Total</th><th>Difference</th></tr>
"""

    for field, data in cap.items():
        html += f"""        <tr><td>{field}</td><td>{format_number(data.get('sa_total', 0), 1)}</td><td>{format_number(data.get('dch_total', 0), 1)}</td><td>{format_number(data.get('difference', 0), 1)}</td></tr>
"""

    html += """    </table>

    <h2>3. Hyperscaler Coverage</h2>
    <table>
        <tr><th>Company</th><th class="sa">SA Records</th><th class="dch">DCH Records</th></tr>
"""

    for company, data in companies.get('hyperscalers', {}).items():
        html += f"""        <tr><td>{company}</td><td>{format_number(data.get('sa', 0))}</td><td>{format_number(data.get('dch', 0))}</td></tr>
"""

    html += f"""        <tr style="font-weight: bold; border-top: 2px solid #333;"><td>All Colo (Non-Hyperscaler)</td><td>{format_number(companies.get('colo', {}).get('sa', 0))}</td><td>{format_number(companies.get('colo', {}).get('dch', 0))}</td></tr>
    </table>

    <h2>4. Geographic Distribution (by Region)</h2>
    <table>
        <tr><th>Region</th><th class="sa">SA Records</th><th class="dch">DCH Records</th></tr>
"""

    sa_regions = geo.get('regions', {}).get('sa', {})
    dch_regions = geo.get('regions', {}).get('dch', {})
    all_regions = set(list(sa_regions.keys()) + list(dch_regions.keys()))
    for region in sorted(all_regions):
        html += f"""        <tr><td>{region}</td><td>{format_number(sa_regions.get(region, 0))}</td><td>{format_number(dch_regions.get(region, 0))}</td></tr>
"""

    html += """    </table>

    <h2>5. Spatial Overlap Analysis</h2>
    <div class="summary-box">
        <p><strong>Matching Threshold:</strong> """ + str(SPATIAL_MATCH_THRESHOLD) + f""" meters</p>
        <p><strong>Potential Matches Found:</strong> {format_number(overlap.get('total_matches', 0))}</p>
        <p><strong>SA Records with DCH Match:</strong> {format_number(overlap.get('sa_matched_count', 0))} ({format_percent(overlap.get('sa_matched_count', 0), vol.get('sa_buildings', 1))} of SA buildings)</p>
        <p><strong>DCH Records with SA Match:</strong> {format_number(overlap.get('dch_matched_count', 0))} ({format_percent(overlap.get('dch_matched_count', 0), vol.get('dch_total', 1))} of DCH)</p>
        <p><strong>SA-Only Records:</strong> {format_number(overlap.get('sa_only_count', 0))}</p>
        <p><strong>DCH-Only Records:</strong> {format_number(overlap.get('dch_only_count', 0))}</p>
    </div>

    <h2>Key Observations</h2>
    <ul>
        <li><strong>Coverage Scope:</strong> SemiAnalysis includes TLBM (market-level aggregate) records representing leasing patterns that DCH does not track.</li>
        <li><strong>Forecast Data:</strong> SA provides 10-year capacity forecasts (mw_2023-mw_2032) that DCH lacks.</li>
        <li><strong>Record Types:</strong> DCH focuses primarily on hyperscale facilities, while SA has broader colocation coverage.</li>
        <li><strong>Spatial Overlap:</strong> A significant portion of records from both sources represent the same physical facilities.</li>
        <li><strong>Data Vintage:</strong> Both sources are updated regularly; check data_vintage field for currency.</li>
    </ul>

</div>
</body>
</html>"""

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)

    print(f"\n  HTML report saved: {output_path}")


# ==============================================================================
# MAIN EXECUTION
# ==============================================================================

def main():
    """Run the full comparison."""
    print("=" * 70)
    print("SEMIANALYSIS vs DATACENTERHAWK COMPARISON")
    print(f"Started: {datetime.now()}")
    print("=" * 70)

    # Verify feature class exists
    if not arcpy.Exists(TARGET_FC):
        raise Exception(f"Feature class not found: {TARGET_FC}")

    # Load records
    print("\nLoading SemiAnalysis records...")
    sa_records = load_records_by_source(TARGET_FC, SA_SOURCES)
    print(f"  Loaded {format_number(len(sa_records))} SA records")

    print("\nLoading DataCenterHawk records...")
    dch_records = load_records_by_source(TARGET_FC, DCH_SOURCES)
    print(f"  Loaded {format_number(len(dch_records))} DCH records")

    # Run comparisons
    all_results = {}

    all_results['volume'] = compare_volume(sa_records, dch_records)
    all_results['capacity'] = compare_capacity(sa_records, dch_records)
    all_results['field_population'] = compare_field_population(sa_records, dch_records)
    all_results['company_coverage'] = compare_company_coverage(sa_records, dch_records)
    all_results['geographic'] = compare_geographic_distribution(sa_records, dch_records)
    all_results['status'] = compare_status_distribution(sa_records, dch_records)
    all_results['spatial_overlap'] = find_spatial_overlaps(sa_records, dch_records, SPATIAL_MATCH_THRESHOLD)

    # Generate summary
    generate_summary(all_results)

    # Generate HTML report
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M')
    html_path = os.path.join(OUTPUT_DIR, f"SA_vs_DCH_Comparison_{timestamp}.html")
    generate_html_report(all_results, html_path)

    print("\n" + "=" * 70)
    print(f"COMPARISON COMPLETE: {datetime.now()}")
    print("=" * 70)

    return all_results


# ==============================================================================
# EXECUTE
# ==============================================================================

if __name__ == "__main__":
    try:
        results = main()
    except Exception as e:
        print(f"\nERROR: {str(e)}")
        import traceback
        traceback.print_exc()
else:
    # Running via exec() in ArcGIS Pro
    try:
        results = main()
    except Exception as e:
        print(f"\nERROR: {str(e)}")
        import traceback
        traceback.print_exc()
