"""
Synergy Hyperscale Data Center Analysis Script
Analyzes Synergy data to evaluate usefulness for the consensus model.

Synergy provides hyperscale facility data with:
- 1,003 records (Feb 2026 vintage)
- NO coordinates (0% geocoded)
- Company-level aggregates by location (City/Country/Region)
- Time series data (Opened quarter/year)
- Ownership type (Owned/Leased/Partner)

Integration Status: EXCLUDED from gold_buildings
Reason: 0% coordinate coverage - cannot be used for spatial analysis

Key Value Proposition:
- Hyperscaler facility counts by region/country/city
- Temporal analysis (when facilities opened)
- Ownership model tracking (owned vs leased)
- Market trend analysis

Schema Summary:
- Company: Hyperscaler name (Alibaba, Amazon, Google, Meta, Microsoft, etc.)
- Region: AMER, APAC, EMEA
- Country: Country name
- City or US State: City for international, state for US
- City or Sub-region: Sub-city detail
- Owned or Leased/Partner: O, L, P
- Quantity: Number of facilities (+1 = new, -1 = closed/moved)
- Opened: Quarter opened (Q1-Q4 + year)
- Year Opened: Year opened
- Data Vintage: Data vintage date

This script provides analysis to determine if Synergy can supplement the consensus model
even without spatial coordinates.

Author: Meta Data Center GIS Team
Last Updated: 2026-02-12
"""

import csv
from datetime import datetime
from collections import defaultdict
import os
import sys

# Add _utils to path for config import
try:
    script_dir = os.path.dirname(os.path.abspath(__file__))
except NameError:
    script_dir = r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\scripts\01_ingestion"

utils_dir = os.path.join(os.path.dirname(script_dir), "_utils")
if utils_dir not in sys.path:
    sys.path.insert(0, utils_dir)

from config import SOURCE_CSV_FILES

# ============================================================================
# CONFIGURATION
# ============================================================================

SOURCE_CSV = SOURCE_CSV_FILES.get('synergy',
    r"C:\Users\ptanderson\Downloads\Pipeline_Ingestion\Synergy Hyperscale DC.csv")

OUTPUT_DIR = r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\scripts\outputs"

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def safe_str(val, max_len=None):
    """Safely convert to string and optionally truncate."""
    if val is None or str(val).strip() in ['', 'nan', 'None']:
        return None
    s = str(val).strip()
    if max_len and len(s) > max_len:
        return s[:max_len]
    return s if s else None


def safe_int(val):
    """Safely convert to integer."""
    if val is None or val == '' or str(val).strip() == '':
        return None
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return None


def safe_float(val):
    """Safely convert to float."""
    if val is None or val == '' or str(val).strip() == '':
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def parse_quarter(quarter_str, year):
    """Parse quarter string (Q116, Q424) to year."""
    if not quarter_str:
        return year
    quarter_str = str(quarter_str).strip().upper()
    if quarter_str.startswith('Q'):
        # Format: Q116 = Q1 2016, Q424 = Q4 2024
        try:
            quarter = int(quarter_str[1])
            yr_suffix = quarter_str[2:]
            if len(yr_suffix) == 2:
                yr = 2000 + int(yr_suffix)
            elif len(yr_suffix) == 4:
                yr = int(yr_suffix)
            else:
                yr = year
            return yr
        except:
            return year
    elif 'pre-' in quarter_str.lower():
        # Format: pre-2013
        try:
            return int(quarter_str.lower().replace('pre-', ''))
        except:
            return year
    return year


# ============================================================================
# ANALYSIS FUNCTIONS
# ============================================================================

def analyze_synergy_data():
    """Comprehensive analysis of Synergy data quality and usefulness."""
    print("=" * 70)
    print("SYNERGY HYPERSCALE DATA CENTER ANALYSIS")
    print("=" * 70)
    print(f"Source: {SOURCE_CSV}")
    print(f"Analysis Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}")

    # Verify source exists
    if not os.path.exists(SOURCE_CSV):
        raise Exception(f"Source CSV not found: {SOURCE_CSV}")

    # Read data
    with open(SOURCE_CSV, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    print(f"\nTotal Records: {len(rows):,}")

    # ===================================================================
    # 1. COMPANY DISTRIBUTION
    # ===================================================================
    print("\n" + "-" * 70)
    print("1. COMPANY DISTRIBUTION")
    print("-" * 70)

    company_counts = defaultdict(int)
    company_net = defaultdict(int)  # Net facilities (accounting for +1/-1)

    for row in rows:
        company = safe_str(row.get('Company')) or 'Unknown'
        quantity = safe_int(row.get('Quantity')) or 0
        company_counts[company] += 1
        company_net[company] += quantity

    print("\nCompany | Records | Net Facilities")
    print("-" * 50)
    for company in sorted(company_counts.keys()):
        count = company_counts[company]
        net = company_net[company]
        pct = count / len(rows) * 100
        print(f"{company:20s} | {count:>6,} ({pct:>5.1f}%) | Net: {net:>+4}")

    # ===================================================================
    # 2. REGION DISTRIBUTION
    # ===================================================================
    print("\n" + "-" * 70)
    print("2. REGION DISTRIBUTION")
    print("-" * 70)

    region_counts = defaultdict(int)
    region_net = defaultdict(int)

    for row in rows:
        region = safe_str(row.get('Region')) or 'Unknown'
        quantity = safe_int(row.get('Quantity')) or 0
        region_counts[region] += 1
        region_net[region] += quantity

    print("\nRegion | Records | Net Facilities")
    print("-" * 40)
    for region in sorted(region_counts.keys()):
        count = region_counts[region]
        net = region_net[region]
        pct = count / len(rows) * 100
        print(f"{region:10s} | {count:>6,} ({pct:>5.1f}%) | Net: {net:>+4}")

    # ===================================================================
    # 3. COUNTRY DISTRIBUTION (Top 20)
    # ===================================================================
    print("\n" + "-" * 70)
    print("3. TOP 20 COUNTRIES")
    print("-" * 70)

    country_counts = defaultdict(int)
    country_net = defaultdict(int)

    for row in rows:
        country = safe_str(row.get('Country')) or 'Unknown'
        quantity = safe_int(row.get('Quantity')) or 0
        country_counts[country] += 1
        country_net[country] += quantity

    print("\nCountry | Records | Net Facilities")
    print("-" * 50)
    for country, count in sorted(country_counts.items(), key=lambda x: -x[1])[:20]:
        net = country_net[country]
        pct = count / len(rows) * 100
        print(f"{country:25s} | {count:>5,} ({pct:>5.1f}%) | Net: {net:>+4}")

    # ===================================================================
    # 4. OWNERSHIP TYPE DISTRIBUTION
    # ===================================================================
    print("\n" + "-" * 70)
    print("4. OWNERSHIP TYPE DISTRIBUTION")
    print("-" * 70)

    ownership_counts = defaultdict(int)
    ownership_net = defaultdict(int)

    for row in rows:
        ownership = safe_str(row.get('Owned or\nLeased/Partner')) or 'Unknown'
        quantity = safe_int(row.get('Quantity')) or 0
        ownership_counts[ownership] += 1
        ownership_net[ownership] += quantity

    ownership_labels = {
        'O': 'Owned',
        'L': 'Leased',
        'P': 'Partner',
    }

    print("\nOwnership | Records | Net Facilities")
    print("-" * 45)
    for ownership, count in sorted(ownership_counts.items(), key=lambda x: -x[1]):
        label = ownership_labels.get(ownership, ownership)
        net = ownership_net[ownership]
        pct = count / len(rows) * 100
        print(f"{label:15s} | {count:>6,} ({pct:>5.1f}%) | Net: {net:>+4}")

    # ===================================================================
    # 5. TEMPORAL ANALYSIS (Facilities by Year)
    # ===================================================================
    print("\n" + "-" * 70)
    print("5. TEMPORAL ANALYSIS (Facilities Opened by Year)")
    print("-" * 70)

    year_counts = defaultdict(int)
    year_net = defaultdict(int)

    for row in rows:
        opened_str = safe_str(row.get('Opened'))
        year = safe_int(row.get('Year\nOpened'))
        parsed_year = parse_quarter(opened_str, year)
        quantity = safe_int(row.get('Quantity')) or 0

        if parsed_year:
            year_counts[parsed_year] += 1
            year_net[parsed_year] += quantity

    print("\nYear | Records | Net New Facilities")
    print("-" * 40)
    for year in sorted(year_counts.keys()):
        count = year_counts[year]
        net = year_net[year]
        bar = '+' * max(0, net // 2) if net > 0 else '-' * max(0, -net // 2)
        print(f"{year:>4} | {count:>5,} | Net: {net:>+4} {bar}")

    # ===================================================================
    # 6. HYPERSCALER-SPECIFIC ANALYSIS
    # ===================================================================
    print("\n" + "-" * 70)
    print("6. HYPERSCALER-SPECIFIC ANALYSIS")
    print("-" * 70)

    hyperscalers = ['Amazon', 'Microsoft', 'Google', 'Meta', 'Apple', 'Oracle', 'Alibaba', 'Tencent']

    for hs in hyperscalers:
        hs_rows = [r for r in rows if safe_str(r.get('Company')) == hs]
        if not hs_rows:
            continue

        net_total = sum(safe_int(r.get('Quantity')) or 0 for r in hs_rows)
        regions = defaultdict(int)
        ownership = defaultdict(int)

        for r in hs_rows:
            region = safe_str(r.get('Region')) or 'Unknown'
            own = safe_str(r.get('Owned or\nLeased/Partner')) or 'Unknown'
            qty = safe_int(r.get('Quantity')) or 0
            regions[region] += qty
            ownership[own] += qty

        print(f"\n{hs}:")
        print(f"  Records: {len(hs_rows):,} | Net Facilities: {net_total:+}")
        print(f"  Regions: {dict(regions)}")
        print(f"  Ownership: {dict(ownership)}")

    # ===================================================================
    # 7. DATA QUALITY ASSESSMENT
    # ===================================================================
    print("\n" + "-" * 70)
    print("7. DATA QUALITY ASSESSMENT")
    print("-" * 70)

    # Field population rates
    fields_to_check = [
        ('Company', 'Company'),
        ('Region', 'Region'),
        ('Country', 'Country'),
        ('City or US State', 'City or \nUS State'),
        ('Ownership', 'Owned or\nLeased/Partner'),
        ('Quantity', 'Quantity'),
        ('Year Opened', 'Year\nOpened'),
    ]

    print("\nField Population Rates:")
    for label, field in fields_to_check:
        populated = sum(1 for r in rows if safe_str(r.get(field)))
        pct = populated / len(rows) * 100
        status = "[OK]" if pct > 80 else "[WARN]" if pct > 50 else "[LOW]"
        print(f"  {label:20s}: {populated:>5}/{len(rows):>5} ({pct:>5.1f}%) {status}")

    # ===================================================================
    # 8. INTEGRATION RECOMMENDATIONS
    # ===================================================================
    print("\n" + "-" * 70)
    print("8. INTEGRATION RECOMMENDATIONS")
    print("-" * 70)

    total_net = sum(safe_int(r.get('Quantity')) or 0 for r in rows)

    print(f"""
SYNERGY DATA SUMMARY:
- Total Records: {len(rows):,}
- Net Facilities Tracked: {total_net:+,}
- Companies: {len(company_counts)}
- Countries: {len(country_counts)}
- Temporal Range: {min(year_counts.keys())} - {max(year_counts.keys())}

COORDINATE STATUS:
- Synergy has 0% coordinate coverage
- Cannot be spatially joined to other sources
- Cannot be displayed on maps

UNIQUE VALUE PROPOSITION:
1. Hyperscaler-specific facility counts (not available elsewhere)
2. Owned vs Leased tracking (strategic intelligence)
3. Temporal opening data (market expansion trends)
4. Country/region level aggregates

INTEGRATION OPTIONS:

Option A: EXCLUDE (Current Status)
- Keep excluded from gold_buildings
- Use for manual validation/comparison only

Option B: ENRICHMENT LAYER
- Create separate enrichment table (not spatial)
- Use for attributing ownership type to matched records
- Cross-reference with spatially enabled sources

Option C: MARKET-LEVEL AGGREGATES
- Roll up to market/region level summaries
- Compare against our own rollups
- Validate hyperscaler counts

RECOMMENDATION:
Given the lack of coordinates, Synergy is best used as:
1. An enrichment layer for ownership intelligence (O/L/P)
2. A validation source for hyperscaler counts
3. A trend analysis dataset for market growth

DO NOT ingest into gold_buildings - keep as reference dataset.
""")

    print("=" * 70)
    print("ANALYSIS COMPLETE")
    print("=" * 70)

    return {
        'total_records': len(rows),
        'net_facilities': total_net,
        'companies': len(company_counts),
        'countries': len(country_counts),
        'year_range': (min(year_counts.keys()), max(year_counts.keys())),
        'company_distribution': dict(company_net),
        'region_distribution': dict(region_net),
    }


def export_synergy_summary(results=None):
    """Export Synergy analysis summary to CSV for reference."""
    if results is None:
        results = analyze_synergy_data()

    # Export company summary
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    output_file = os.path.join(OUTPUT_DIR, f"synergy_analysis_summary_{timestamp}.csv")

    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['Metric', 'Value'])
        writer.writerow(['Total Records', results['total_records']])
        writer.writerow(['Net Facilities', results['net_facilities']])
        writer.writerow(['Companies', results['companies']])
        writer.writerow(['Countries', results['countries']])
        writer.writerow(['Year Range', f"{results['year_range'][0]}-{results['year_range'][1]}"])
        writer.writerow([])
        writer.writerow(['Company', 'Net Facilities'])
        for company, net in sorted(results['company_distribution'].items(), key=lambda x: -x[1]):
            writer.writerow([company, net])
        writer.writerow([])
        writer.writerow(['Region', 'Net Facilities'])
        for region, net in sorted(results['region_distribution'].items(), key=lambda x: -x[1]):
            writer.writerow([region, net])

    print(f"\nSummary exported to: {output_file}")


# ============================================================================
# MAIN FUNCTION
# ============================================================================

def main():
    """Run Synergy data analysis."""
    results = analyze_synergy_data()
    export_synergy_summary(results)
    return results


# ====== EXECUTE ======
if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\nERROR: {str(e)}")
        import traceback
        traceback.print_exc()
else:
    try:
        main()
    except Exception as e:
        print(f"\nERROR: {str(e)}")
        import traceback
        traceback.print_exc()
