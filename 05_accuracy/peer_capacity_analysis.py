"""
Peer Company DC Capacity Analysis (2025-2030)
==============================================

Purpose:
Analyzes data center capacity forecasts for peer companies (hyperscalers)
with US vs non-US breakdown.

Key Approach:
1. Uses BUILDING-level records (where SA year data and xAI exist)
2. Groups by UCID to avoid double-counting buildings in same campus
3. Prioritizes Semianalysis (SA) data where available for year forecasts
4. Checks both company_clean AND end_user fields (xAI often in end_user)
5. Splits by US vs Global (non-US)

Output: Summary table matching colleague's request format

Run in ArcGIS Pro Python window:
exec(open(r"C:/Users/ptanderson/Documents/ArcGIS/Projects/Lean Consensus DC Model/scripts/05_export/peer_capacity_analysis.py", encoding='utf-8').read())

Author: Data Center Consensus Model Team
Created: January 21, 2026
"""

import arcpy
import os
import sys
from datetime import datetime

# Add _utils to path
script_dir = os.path.dirname(os.path.abspath(__file__)) if '__file__' in dir() else \
             r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\scripts\05_export"
utils_dir = os.path.join(os.path.dirname(script_dir), "_utils")
if utils_dir not in sys.path:
    sys.path.insert(0, utils_dir)

from config import GDB

arcpy.env.workspace = GDB

# =============================================================================
# CONFIGURATION
# =============================================================================

# Target companies (mapped to company_clean values)
# Using company_clean (not company_clean_filter) to capture AI labs like xAI, OpenAI, Anthropic
# Also check end_user field for AI labs who lease from colos
# See migrate_company_fields_v2.py for canonical mappings
PEER_COMPANIES = {
    'xAI': ['xAI'],                    # xAI is a hyperscaler in company_clean
    'OpenAI': ['OpenAI'],              # OpenAI is a hyperscaler in company_clean
    'Amazon': ['AWS', 'Amazon'],       # AWS canonical name
    'Google': ['Google'],
    'Microsoft': ['Microsoft'],
    'Meta': ['Meta'],
}

# Years of interest
FORECAST_YEARS = [2025, 2026, 2027, 2028, 2029, 2030]

# Feature class to analyze
GOLD_COMBINED_XB = os.path.join(GDB, "gold_combined_xb")

# =============================================================================
# ANALYSIS FUNCTIONS
# =============================================================================

def analyze_peer_capacity():
    """
    Analyze DC capacity for peer companies with US vs non-US split.
    Returns capacity by company, region (US/non-US), and year.
    """

    print("\n" + "="*70)
    print("PEER COMPANY DC CAPACITY ANALYSIS (2025-2030)")
    print("="*70)
    print(f"\nTimestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Source: {GOLD_COMBINED_XB}")

    # Check if feature class exists
    if not arcpy.Exists(GOLD_COMBINED_XB):
        print(f"\nERROR: Feature class not found: {GOLD_COMBINED_XB}")
        print("Please run the full pipeline first to create gold_combined_xb")
        return None

    # Get list of fields
    fields = [f.name for f in arcpy.ListFields(GOLD_COMBINED_XB)]

    # Check for required fields
    required = ['company_clean', 'end_user', 'record_level', 'country', 'source', 'full_capacity_mw']
    year_fields = [f'mw_{year}' for year in FORECAST_YEARS]

    missing = [f for f in required if f not in fields]
    if missing:
        print(f"\nWARNING: Missing required fields: {missing}")
        print("Note: company_clean contains standardized names (xAI, OpenAI, AWS, etc.)")
        print("      end_user contains tenant/end-user (may also have xAI, OpenAI)")

    # Check which year fields exist
    available_years = {year: f'mw_{year}' for year in FORECAST_YEARS if f'mw_{year}' in fields}
    missing_years = [year for year in FORECAST_YEARS if f'mw_{year}' not in fields]

    print(f"\nAvailable year forecast fields: {list(available_years.keys())}")
    if missing_years:
        print(f"Missing year fields: {missing_years}")

    # Build query fields - include UCID for deduplication, plus company fields
    query_fields = [
        'ucid',                    # For grouping/deduplication
        'company_clean',           # Primary company field (has xAI, OpenAI, AWS, etc.)
        'end_user',                # End user/tenant field (may also have AI labs)
        'record_level',
        'country',
        'source',
        'full_capacity_mw',
        'commissioned_power_mw',
    ] + [f'mw_{year}' for year in available_years.keys()]

    # Initialize results structure
    results = {}
    for display_name, filter_name in PEER_COMPANIES.items():
        results[display_name] = {
            'US': {year: 0.0 for year in FORECAST_YEARS},
            'non-US': {year: 0.0 for year in FORECAST_YEARS},
            'US_campus_count': 0,
            'non-US_campus_count': 0,
            'US_sa_records': 0,
            'non-US_sa_records': 0,
        }

    # Also track OpenAI separately (may be under Oracle/Microsoft)
    openai_tracking = {
        'US': {year: 0.0 for year in FORECAST_YEARS},
        'non-US': {year: 0.0 for year in FORECAST_YEARS},
        'notes': []
    }

    # Count records
    total_records = 0
    building_records = 0
    sa_records = 0
    
    # Track UCIDs we've seen to deduplicate by campus
    # We'll use max capacity per UCID per company to avoid double-counting
    ucid_data = {}  # {(company, ucid, region): {year: max_mw, ...}}

    # Process records - BUILDING LEVEL (where SA data and xAI exist)
    where_clause = "record_level = 'Building'"

    print(f"\nProcessing Building-level records (where SA year data exists)...")
    print(f"Grouping by UCID to avoid double-counting within campuses...")

    with arcpy.da.SearchCursor(GOLD_COMBINED_XB, query_fields, where_clause) as cursor:
        for row in cursor:
            total_records += 1
            building_records += 1

            # Extract values - fields are:
            # ucid, company_clean, end_user, record_level, country, source, full_capacity_mw, commissioned_power_mw, mw_YEAR...
            idx = 0
            ucid = row[idx] or 'UNKNOWN'; idx += 1
            company_clean = row[idx] or ''; idx += 1
            end_user = row[idx] or ''; idx += 1
            record_level = row[idx]; idx += 1
            country = row[idx] or ''; idx += 1
            source = row[idx] or ''; idx += 1
            full_capacity = row[idx] or 0; idx += 1
            commissioned = row[idx] or 0; idx += 1

            # Year capacities
            year_values = {}
            for year in available_years.keys():
                year_values[year] = row[idx] or 0
                idx += 1

            # Determine region
            is_us = (country == 'United States')
            region_key = 'US' if is_us else 'non-US'

            # Check if Semianalysis source
            is_sa = 'Semianalysis' in source if source else False
            if is_sa:
                sa_records += 1

            # Find matching peer company - check BOTH company_clean AND end_user
            matched_company = None
            for display_name, filter_values in PEER_COMPANIES.items():
                # Check company_clean
                if company_clean in filter_values:
                    matched_company = display_name
                    break
                # Also check end_user field (for AI labs leasing from colos)
                if end_user in filter_values:
                    matched_company = display_name
                    break

            if matched_company:
                # Create key for this campus/company/region combination
                key = (matched_company, ucid, region_key)
                
                if key not in ucid_data:
                    ucid_data[key] = {
                        'years': {year: 0.0 for year in FORECAST_YEARS},
                        'full_capacity': 0.0,
                        'is_sa': False,
                        'source': source,
                    }
                
                # Update with max values (in case of multiple buildings per campus)
                # For SA data, we SUM because each building contributes to campus total
                # For non-SA, we take MAX to avoid double-counting
                if is_sa:
                    ucid_data[key]['is_sa'] = True
                    for year in FORECAST_YEARS:
                        if year in year_values:
                            ucid_data[key]['years'][year] += year_values[year]
                else:
                    # For non-SA, only update if we don't have SA data yet
                    if not ucid_data[key]['is_sa']:
                        for year in FORECAST_YEARS:
                            if year in year_values:
                                ucid_data[key]['years'][year] = max(
                                    ucid_data[key]['years'][year],
                                    year_values[year]
                                )
                
                ucid_data[key]['full_capacity'] = max(ucid_data[key]['full_capacity'], full_capacity)

    # Now aggregate by company and region
    for (company, ucid, region_key), data in ucid_data.items():
        results[company][f'{region_key}_campus_count'] += 1
        if data['is_sa']:
            results[company][f'{region_key}_sa_records'] += 1
        
        for year in FORECAST_YEARS:
            results[company][region_key][year] += data['years'][year]

    print(f"\nRecords processed:")
    print(f"  Total Building records: {building_records:,}")
    print(f"  Records with Semianalysis data: {sa_records:,}")
    print(f"  Unique UCID/Company combinations: {len(ucid_data):,}")

    return results, available_years

def calculate_growth(results, available_years):
    """
    Calculate 2025-2030 growth (delta) for each company.
    Growth = mw_2030 - mw_2025 (if both available)
    """

    growth_summary = {}

    for company, data in results.items():
        us_growth = 0
        non_us_growth = 0

        if 2025 in available_years and 2030 in available_years:
            us_growth = data['US'].get(2030, 0) - data['US'].get(2025, 0)
            non_us_growth = data['non-US'].get(2030, 0) - data['non-US'].get(2025, 0)

        # Total 2025-2030 values
        us_2025 = data['US'].get(2025, 0)
        us_2030 = data['US'].get(2030, 0)
        non_us_2025 = data['non-US'].get(2025, 0)
        non_us_2030 = data['non-US'].get(2030, 0)

        growth_summary[company] = {
            'US_2025': us_2025,
            'US_2030': us_2030,
            'US_growth_GW': us_growth / 1000,
            'non_US_2025': non_us_2025,
            'non_US_2030': non_us_2030,
            'non_US_growth_GW': non_us_growth / 1000,
            'total_growth_GW': (us_growth + non_us_growth) / 1000,
            'US_campus_count': data['US_campus_count'],
            'non_US_campus_count': data['non-US_campus_count'],
            'US_sa_records': data['US_sa_records'],
            'non_US_sa_records': data['non-US_sa_records'],
        }

    return growth_summary

def print_report(results, growth_summary, available_years):
    """Print formatted report matching colleague's request format."""

    print("\n" + "="*70)
    print("DC CAPACITY GROWTH 2025-2030 (GW)")
    print("="*70)

    # Header row
    print(f"\n{'Peer':<15} {'US Growth':<12} {'Non-US Growth':<14} {'Total Growth':<12} {'US Campuses':<12} {'Non-US Camp.'}")
    print("-"*75)

    # Data rows - ordered to match the image (xAI, OpenAI, Amazon, Google, Microsoft, Meta)
    display_order = ['xAI', 'Amazon', 'Google', 'Microsoft', 'Meta']

    for company in display_order:
        if company in growth_summary:
            g = growth_summary[company]
            us_growth = f"{g['US_growth_GW']:.1f}"
            non_us_growth = f"{g['non_US_growth_GW']:.1f}"
            total_growth = f"{g['total_growth_GW']:.1f}"
            us_camps = str(g['US_campus_count'])
            non_us_camps = str(g['non_US_campus_count'])

            print(f"{company:<15} {us_growth:<12} {non_us_growth:<14} {total_growth:<12} {us_camps:<12} {non_us_camps}")

    # OpenAI note
    print("\n" + "-"*75)
    print("NOTE: OpenAI capacity is often reported under Oracle or Microsoft partnerships.")
    print("      The 13.2 GW figure may be Oracle-provided capacity leased to OpenAI.")

    # Detailed breakdown by year
    print("\n\n" + "="*70)
    print("DETAILED YEAR-BY-YEAR CAPACITY (MW)")
    print("="*70)

    for company in display_order:
        if company in results:
            data = results[company]
            g = growth_summary[company]

            print(f"\n{company}")
            print("-"*50)

            # US data
            print(f"  US ({g['US_campus_count']} campuses, {g['US_sa_records']} with SA data):")
            year_line = "    "
            for year in [2025, 2026, 2027, 2028, 2029, 2030]:
                if year in available_years:
                    val = data['US'].get(year, 0)
                    year_line += f"{year}: {val:,.0f} MW  "
            print(year_line)

            # Non-US data
            print(f"  Non-US ({g['non_US_campus_count']} campuses, {g['non_US_sa_records']} with SA data):")
            year_line = "    "
            for year in [2025, 2026, 2027, 2028, 2029, 2030]:
                if year in available_years:
                    val = data['non-US'].get(year, 0)
                    year_line += f"{year}: {val:,.0f} MW  "
            print(year_line)

    # Data quality notes
    print("\n\n" + "="*70)
    print("DATA QUALITY NOTES")
    print("="*70)
    print("""
1. DEDUPLICATION: Uses Campus-level records only (no building double-counting)
2. SOURCE PRIORITY: Semianalysis (SA) data prioritized for year forecasts
3. COVERAGE: SA data has the most complete mw_2025-2030 fields
4. GAPS: Non-SA sources may only have current capacity, not forecasts
5. OPENAI: Not in company_clean_filter - check Oracle records for OpenAI-leased capacity
""")

def export_to_csv(growth_summary, output_path=None):
    """Export results to CSV for sharing."""

    if output_path is None:
        output_path = os.path.join(
            os.path.dirname(GDB),
            "exports",
            f"peer_capacity_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        )

    # Ensure directory exists
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    with open(output_path, 'w') as f:
        # Header
        f.write("Peer,US_2025_MW,US_2030_MW,US_Growth_GW,NonUS_2025_MW,NonUS_2030_MW,NonUS_Growth_GW,Total_Growth_GW,US_Campuses,NonUS_Campuses\n")

        for company in ['xAI', 'Amazon', 'Google', 'Microsoft', 'Meta']:
            if company in growth_summary:
                g = growth_summary[company]
                f.write(f"{company},{g['US_2025']:.0f},{g['US_2030']:.0f},{g['US_growth_GW']:.2f},")
                f.write(f"{g['non_US_2025']:.0f},{g['non_US_2030']:.0f},{g['non_US_growth_GW']:.2f},")
                f.write(f"{g['total_growth_GW']:.2f},{g['US_campus_count']},{g['non_US_campus_count']}\n")

    print(f"\nCSV exported to: {output_path}")
    return output_path

# =============================================================================
# MAIN EXECUTION
# =============================================================================

if __name__ == "__main__" or True:  # Run when executed via exec()

    # Run analysis
    results, available_years = analyze_peer_capacity()

    if results:
        # Calculate growth
        growth_summary = calculate_growth(results, available_years)

        # Print report
        print_report(results, growth_summary, available_years)

        # Export to CSV
        csv_path = export_to_csv(growth_summary)

        print("\n" + "="*70)
        print("ANALYSIS COMPLETE")
        print("="*70)
