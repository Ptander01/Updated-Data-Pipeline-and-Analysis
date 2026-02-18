"""
New Source Data Quality & Coverage Analysis Script
Analyzes Orennia, SemiAnalysis (clean), and WoodMac datasets for:
- Data quality metrics (completeness, geocoding rates)
- Coverage analysis (geographic, company, temporal)
- Strengths and weaknesses assessment
- Integration recommendations for consensus model

Author: Meta Data Center GIS Team
Created: 2026-02-12
"""

import csv
import os
from datetime import datetime
from collections import defaultdict
import json

# ============================================================================
# CONFIGURATION
# ============================================================================

SOURCE_DIR = r"C:\Users\ptanderson\Downloads\Pipeline_Ingestion"

SOURCES = {
    'Orennia': {
        'file': 'Orennia - Data Centers-2026-02-02.csv',
        'lat_col': 'Latitude (Degrees)',
        'lon_col': 'Longitude (Degrees)',
        'company_col': 'Owner',
        'status_col': 'Data Center Status',
        'capacity_col': 'Power Capacity (MW)',
        'sqft_col': 'Square Footage (Sq Ft)',
        'country_col': 'Country',
        'state_col': 'State',
        'city_col': None,  # Not directly available
        'date_col': 'First Power Date',
        'type_col': 'Owner Type',
    },
    'SemiAnalysis': {
        'file': 'SemiAnalysis Global Import.csv',
        'lat_col': 'Lat',
        'lon_col': 'Long',
        'company_col': 'Company',
        'status_col': None,  # Derived from capacity fields
        'capacity_col': 'Full Capacity',
        'sqft_col': 'Facility Square Footage',
        'country_col': 'Country',
        'state_col': 'US State',
        'city_col': 'City',
        'date_col': 'Actual Live Assumption',
        'type_col': 'Type',
        'installed_col': 'Installed Capacity MW (Q2 2025)',
        'uc_col': 'Total under Construction MW',
        'planned_col': 'Total Planned MW',
    },
    'WoodMac': {
        'file': '022025_WoodMac_DC_sites.csv',
        'lat_col': 'latitude',
        'lon_col': 'longitude',
        'company_col': 'developer_name',
        'status_col': 'status',
        'capacity_col': None,  # Multiple columns
        'sqft_col': None,
        'country_col': 'country_name',
        'state_col': 'state_province_name',
        'city_col': None,
        'date_col': 'commercial_operation_date',
        'type_col': 'workload',
        'existing_col': 'existing_capacity__mw',
        'dev_col': 'development_capacity__mw',
        'planned_col': 'planned_capacity__mw',
    }
}

# Hyperscaler keywords for classification
HYPERSCALER_KEYWORDS = [
    'amazon', 'aws', 'microsoft', 'azure', 'google', 'gcp', 'meta', 'facebook',
    'apple', 'oracle', 'alibaba', 'tencent', 'ibm', 'bytedance',
    'xai', 'openai', 'anthropic', 'coreweave', 'crusoe'
]

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def safe_float(val):
    """Safely convert to float."""
    if val is None or str(val).strip() in ['', 'nan', 'None', 'NaN', '-', 'N/A']:
        return None
    try:
        return float(str(val).replace(',', '').replace('$', '').strip())
    except (ValueError, TypeError):
        return None

def safe_str(val):
    """Safely convert to string."""
    if val is None or str(val).strip() in ['', 'nan', 'None', 'NaN']:
        return None
    return str(val).strip()

def is_hyperscaler(company):
    """Check if company is a hyperscaler."""
    if not company:
        return False
    company_lower = str(company).lower()
    return any(kw in company_lower for kw in HYPERSCALER_KEYWORDS)

def load_csv(filepath):
    """Load CSV file and return list of dicts."""
    # Try UTF-8 first, fall back to other encodings if needed
    for encoding in ['utf-8', 'utf-8-sig', 'latin-1', 'cp1252']:
        try:
            with open(filepath, 'r', encoding=encoding) as f:
                return list(csv.DictReader(f))
        except UnicodeDecodeError:
            continue
    # Last resort: ignore errors
    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        return list(csv.DictReader(f))

def format_pct(val, total):
    """Format percentage."""
    if total == 0:
        return "N/A"
    return f"{val/total*100:.1f}%"

# ============================================================================
# ANALYSIS FUNCTIONS
# ============================================================================

def analyze_source(name, config, rows):
    """Analyze a single data source and return metrics."""
    print(f"\n{'='*70}")
    print(f"ANALYZING: {name}")
    print(f"{'='*70}")

    total = len(rows)
    print(f"Total Records: {total:,}")

    metrics = {
        'name': name,
        'total_records': total,
        'strengths': [],
        'weaknesses': [],
        'coverage': {},
        'quality': {},
    }

    # ===== GEOCODING ANALYSIS =====
    lat_col = config['lat_col']
    lon_col = config['lon_col']

    geocoded = 0
    for row in rows:
        lat = safe_float(row.get(lat_col))
        lon = safe_float(row.get(lon_col))
        if lat is not None and lon is not None:
            geocoded += 1

    geocode_rate = geocoded / total * 100 if total > 0 else 0
    metrics['quality']['geocoded'] = geocoded
    metrics['quality']['geocode_rate'] = geocode_rate

    print(f"\n📍 GEOCODING:")
    print(f"   Geocoded: {geocoded:,} / {total:,} ({geocode_rate:.1f}%)")

    if geocode_rate >= 95:
        metrics['strengths'].append(f"Excellent geocoding rate ({geocode_rate:.1f}%)")
    elif geocode_rate >= 80:
        metrics['strengths'].append(f"Good geocoding rate ({geocode_rate:.1f}%)")
    elif geocode_rate < 50:
        metrics['weaknesses'].append(f"Poor geocoding rate ({geocode_rate:.1f}%)")

    # ===== GEOGRAPHIC COVERAGE =====
    countries = defaultdict(int)
    states = defaultdict(int)
    regions = {'AMER': 0, 'EMEA': 0, 'APAC': 0, 'Unknown': 0}

    country_col = config['country_col']
    state_col = config['state_col']

    for row in rows:
        country = safe_str(row.get(country_col))
        state = safe_str(row.get(state_col))

        if country:
            countries[country] += 1
            # Classify region
            country_lower = country.lower()
            if any(x in country_lower for x in ['united states', 'usa', 'canada', 'mexico', 'brazil']):
                regions['AMER'] += 1
            elif any(x in country_lower for x in ['uk', 'united kingdom', 'ireland', 'germany', 'france', 'netherlands', 'sweden']):
                regions['EMEA'] += 1
            elif any(x in country_lower for x in ['china', 'japan', 'singapore', 'india', 'australia', 'asia']):
                regions['APAC'] += 1
            else:
                regions['Unknown'] += 1

        if state:
            states[state] += 1

    metrics['coverage']['countries'] = len(countries)
    metrics['coverage']['country_dist'] = dict(sorted(countries.items(), key=lambda x: -x[1])[:10])
    metrics['coverage']['regions'] = dict(regions)
    metrics['coverage']['states_provinces'] = len(states)

    print(f"\n🌍 GEOGRAPHIC COVERAGE:")
    print(f"   Countries: {len(countries)}")
    print(f"   States/Provinces: {len(states)}")
    print(f"   Region Distribution:")
    for region, count in sorted(regions.items(), key=lambda x: -x[1]):
        print(f"      {region}: {count:,} ({format_pct(count, total)})")

    if len(countries) >= 10:
        metrics['strengths'].append(f"Global coverage ({len(countries)} countries)")
    elif len(countries) == 1:
        metrics['weaknesses'].append("Single-country coverage only")
        top_country = list(countries.keys())[0] if countries else 'Unknown'
        metrics['strengths'].append(f"Deep coverage in {top_country}")

    # ===== COMPANY/OWNER ANALYSIS =====
    companies = defaultdict(int)
    hyperscaler_count = 0
    colo_count = 0

    company_col = config['company_col']
    type_col = config.get('type_col')

    for row in rows:
        company = safe_str(row.get(company_col))
        owner_type = safe_str(row.get(type_col)) if type_col else None

        if company:
            companies[company] += 1

        if is_hyperscaler(company):
            hyperscaler_count += 1
        elif owner_type and 'colo' in str(owner_type).lower():
            colo_count += 1

    metrics['coverage']['companies'] = len(companies)
    metrics['coverage']['top_companies'] = dict(sorted(companies.items(), key=lambda x: -x[1])[:15])
    metrics['coverage']['hyperscaler_count'] = hyperscaler_count
    metrics['coverage']['colo_count'] = colo_count

    print(f"\n🏢 COMPANY COVERAGE:")
    print(f"   Unique Companies: {len(companies)}")
    print(f"   Hyperscaler Records: {hyperscaler_count:,} ({format_pct(hyperscaler_count, total)})")
    print(f"   Top 10 Companies:")
    for company, count in sorted(companies.items(), key=lambda x: -x[1])[:10]:
        print(f"      {company}: {count:,}")

    # ===== CAPACITY ANALYSIS =====
    total_capacity = 0
    capacity_populated = 0

    # Handle different capacity column configurations
    if name == 'SemiAnalysis':
        # SemiAnalysis stores capacity in year columns and Installed/UC/Planned columns
        # Use 2025 as current installed capacity reference
        for row in rows:
            installed = safe_float(row.get('Installed Capacity MW (Q2 2025)')) or 0
            uc = safe_float(row.get('Total under Construction MW')) or 0
            planned = safe_float(row.get('Total Planned MW')) or 0
            cap = installed + uc + planned
            if cap > 0:
                total_capacity += cap
                capacity_populated += 1
    elif name == 'WoodMac':
        for row in rows:
            existing = safe_float(row.get('existing_capacity__mw')) or 0
            dev = safe_float(row.get('development_capacity__mw')) or 0
            planned = safe_float(row.get('planned_capacity__mw')) or 0
            cap = existing + dev + planned
            if cap > 0:
                total_capacity += cap
                capacity_populated += 1
    else:  # Orennia
        cap_col = config['capacity_col']
        for row in rows:
            cap = safe_float(row.get(cap_col))
            if cap is not None and cap > 0:
                total_capacity += cap
                capacity_populated += 1

    capacity_rate = capacity_populated / total * 100 if total > 0 else 0
    metrics['quality']['capacity_populated'] = capacity_populated
    metrics['quality']['capacity_rate'] = capacity_rate
    metrics['quality']['total_capacity_mw'] = total_capacity

    print(f"\n⚡ CAPACITY DATA:")
    print(f"   Capacity Populated: {capacity_populated:,} / {total:,} ({capacity_rate:.1f}%)")
    print(f"   Total Capacity: {total_capacity:,.0f} MW")

    if capacity_rate >= 80:
        metrics['strengths'].append(f"Strong capacity data ({capacity_rate:.1f}% populated)")
    elif capacity_rate < 30:
        metrics['weaknesses'].append(f"Sparse capacity data ({capacity_rate:.1f}% populated)")

    # ===== STATUS ANALYSIS =====
    statuses = defaultdict(int)
    status_col = config.get('status_col')

    if status_col:
        for row in rows:
            status = safe_str(row.get(status_col))
            if status:
                statuses[status] += 1
    elif name == 'SemiAnalysis':
        # Derive status from capacity fields
        for row in rows:
            installed = safe_float(row.get('Installed Capacity MW (Q2 2025)')) or 0
            uc = safe_float(row.get('Total under Construction MW')) or 0
            planned = safe_float(row.get('Total Planned MW')) or 0

            if installed > 0:
                statuses['Active'] += 1
            elif uc > 0:
                statuses['Under Construction'] += 1
            elif planned > 0:
                statuses['Planned'] += 1
            else:
                statuses['Unknown'] += 1

    metrics['coverage']['statuses'] = dict(statuses)

    print(f"\n📊 STATUS DISTRIBUTION:")
    for status, count in sorted(statuses.items(), key=lambda x: -x[1]):
        print(f"   {status}: {count:,} ({format_pct(count, total)})")

    # ===== SQUARE FOOTAGE ANALYSIS =====
    sqft_col = config.get('sqft_col')
    sqft_populated = 0
    total_sqft = 0

    if sqft_col:
        for row in rows:
            sqft = safe_float(row.get(sqft_col))
            if sqft is not None and sqft > 0:
                sqft_populated += 1
                total_sqft += sqft

    sqft_rate = sqft_populated / total * 100 if total > 0 else 0
    metrics['quality']['sqft_populated'] = sqft_populated
    metrics['quality']['sqft_rate'] = sqft_rate
    metrics['quality']['total_sqft'] = total_sqft

    print(f"\n📐 SQUARE FOOTAGE DATA:")
    print(f"   SqFt Populated: {sqft_populated:,} / {total:,} ({sqft_rate:.1f}%)")
    if total_sqft > 0:
        print(f"   Total SqFt: {total_sqft:,.0f}")

    if sqft_rate >= 50:
        metrics['strengths'].append(f"Good square footage data ({sqft_rate:.1f}%)")

    # ===== DATE ANALYSIS =====
    date_col = config.get('date_col')
    date_populated = 0

    if date_col:
        for row in rows:
            date_val = safe_str(row.get(date_col))
            if date_val:
                date_populated += 1

    date_rate = date_populated / total * 100 if total > 0 else 0
    metrics['quality']['date_populated'] = date_populated
    metrics['quality']['date_rate'] = date_rate

    print(f"\n📅 DATE DATA:")
    print(f"   Date Populated: {date_populated:,} / {total:,} ({date_rate:.1f}%)")

    # ===== SOURCE-SPECIFIC ANALYSIS =====
    if name == 'SemiAnalysis':
        # Year-over-year MW forecasts
        year_cols = ['2023', '2024', '2025', '2026', '2027', '2028', '2029', '2030', '2031', '2032']
        print(f"\n📈 YEAR-OVER-YEAR MW FORECASTS:")
        for year in year_cols:
            populated = sum(1 for row in rows if safe_float(row.get(year)) is not None and safe_float(row.get(year)) > 0)
            total_mw = sum(safe_float(row.get(year)) or 0 for row in rows)
            if populated > 0:
                print(f"   {year}: {populated:,} records, {total_mw:,.0f} MW total")
        metrics['strengths'].append("Unique year-over-year capacity forecasts (2023-2032)")

        # Check for market-level data
        markets = set(safe_str(row.get('Market')) for row in rows if safe_str(row.get('Market')))
        if len(markets) > 20:
            metrics['strengths'].append(f"Detailed market coverage ({len(markets)} markets)")

    elif name == 'WoodMac':
        # Project tracking
        projects = set(safe_str(row.get('project_name')) for row in rows if safe_str(row.get('project_name')))
        metrics['coverage']['unique_projects'] = len(projects)
        print(f"\n📋 PROJECT TRACKING:")
        print(f"   Unique Projects: {len(projects)}")
        metrics['strengths'].append("Project-level tracking with development phases")

        # Workload types (AI/Cloud differentiation)
        workloads = defaultdict(int)
        for row in rows:
            workload = safe_str(row.get('workload'))
            if workload:
                workloads[workload] += 1
        if workloads:
            print(f"   Workload Types: {dict(workloads)}")
            if 'AI' in str(workloads) or 'Cloud' in str(workloads):
                metrics['strengths'].append("AI vs Cloud workload differentiation")

    elif name == 'Orennia':
        # Transmission owner / grid data
        transmission_owners = set(safe_str(row.get('Transmission Owner')) for row in rows if safe_str(row.get('Transmission Owner')))
        if len(transmission_owners) > 10:
            metrics['strengths'].append(f"Grid/utility mapping ({len(transmission_owners)} transmission owners)")
            print(f"\n⚡ GRID DATA:")
            print(f"   Transmission Owners: {len(transmission_owners)}")

    return metrics

def generate_comparison_report(all_metrics):
    """Generate comparative analysis report."""
    print("\n" + "="*70)
    print("COMPARATIVE ANALYSIS SUMMARY")
    print("="*70)

    # ===== RECORD COUNTS =====
    print("\n📊 RECORD COUNTS:")
    for m in all_metrics:
        print(f"   {m['name']}: {m['total_records']:,} records")

    # ===== GEOCODING COMPARISON =====
    print("\n📍 GEOCODING RATES:")
    for m in all_metrics:
        rate = m['quality'].get('geocode_rate', 0)
        status = "✅" if rate >= 95 else "⚠️" if rate >= 80 else "❌"
        print(f"   {m['name']}: {rate:.1f}% {status}")

    # ===== CAPACITY DATA =====
    print("\n⚡ TOTAL CAPACITY (MW):")
    for m in all_metrics:
        cap = m['quality'].get('total_capacity_mw', 0)
        rate = m['quality'].get('capacity_rate', 0)
        print(f"   {m['name']}: {cap:,.0f} MW ({rate:.1f}% populated)")

    # ===== GEOGRAPHIC COVERAGE =====
    print("\n🌍 GEOGRAPHIC COVERAGE:")
    for m in all_metrics:
        countries = m['coverage'].get('countries', 0)
        states = m['coverage'].get('states_provinces', 0)
        print(f"   {m['name']}: {countries} countries, {states} states/provinces")

    # ===== STRENGTHS/WEAKNESSES SUMMARY =====
    print("\n" + "="*70)
    print("STRENGTHS & WEAKNESSES BY SOURCE")
    print("="*70)

    for m in all_metrics:
        print(f"\n📌 {m['name'].upper()}:")
        print("   Strengths:")
        for s in m['strengths']:
            print(f"      ✅ {s}")
        print("   Weaknesses:")
        for w in m['weaknesses']:
            print(f"      ❌ {w}")
        if not m['weaknesses']:
            print(f"      (No major weaknesses identified)")

    return all_metrics

def generate_integration_recommendations(all_metrics):
    """Generate integration recommendations for consensus model."""
    print("\n" + "="*70)
    print("INTEGRATION RECOMMENDATIONS FOR CONSENSUS MODEL")
    print("="*70)

    recommendations = []

    # Orennia recommendations
    orennia = next((m for m in all_metrics if m['name'] == 'Orennia'), None)
    if orennia:
        print("\n🔷 ORENNIA:")
        print("   Best For:")
        print("      • US market deep-dive (state/county level detail)")
        print("      • Grid/utility relationships (transmission owner mapping)")
        print("      • Owner type classification (Hyperscaler/Colo/Enterprise)")
        print("   Use Case: Primary source for US facilities with grid context")
        print("   Priority: P1 for US coverage")
        recommendations.append({
            'source': 'Orennia',
            'priority': 'P1',
            'use_case': 'US market coverage with grid/utility mapping',
            'integration': 'Run ingest_orennia.py to load into gold_buildings_full'
        })

    # SemiAnalysis recommendations
    sa = next((m for m in all_metrics if m['name'] == 'SemiAnalysis'), None)
    if sa:
        print("\n🔷 SEMIANALYSIS:")
        print("   Best For:")
        print("      • Capacity forecasting (year-over-year MW projections)")
        print("      • Building-level granularity with cluster groupings")
        print("      • Market-level aggregations for business intelligence")
        print("   Use Case: Forward-looking capacity analysis and forecasting")
        print("   Priority: P1 for capacity forecasting, P2 for historical")
        recommendations.append({
            'source': 'SemiAnalysis',
            'priority': 'P1',
            'use_case': 'Capacity forecasting with year-over-year MW projections',
            'integration': 'Run ingest_semianalysis_v2.py with cleaned CSV'
        })

    # WoodMac recommendations
    woodmac = next((m for m in all_metrics if m['name'] == 'WoodMac'), None)
    if woodmac:
        print("\n🔷 WOODMAC:")
        print("   Best For:")
        print("      • Global coverage (multi-country perspective)")
        print("      • Project pipeline tracking (development phases)")
        print("      • AI vs Cloud workload differentiation")
        print("   Use Case: International market analysis and project tracking")
        print("   Priority: P1 for global coverage, P2 for US (redundant with Orennia)")
        recommendations.append({
            'source': 'WoodMac',
            'priority': 'P1',
            'use_case': 'Global coverage and project pipeline tracking',
            'integration': 'Run ingest_woodmac.py (projects ingested at site level)'
        })

    print("\n" + "-"*70)
    print("CONSENSUS MODEL INTEGRATION STRATEGY:")
    print("-"*70)
    print("""
1. LAYERED APPROACH:
   • Layer 1 (Foundation): DCH + Meta Canonical (existing trusted sources)
   • Layer 2 (Enrichment): SemiAnalysis (capacity forecasts, building detail)
   • Layer 3 (Coverage Expansion): Orennia + WoodMac (geographic gap fill)

2. DEDUPLICATION STRATEGY:
   • UCID-based campus matching (250m TIGHT threshold for urban, 500m standard)
   • Company name standardization across all sources
   • Priority weighting: Meta Canonical > DCH > SemiAnalysis > Orennia > WoodMac

3. FIELD INHERITANCE RULES:
   • Coordinates: Prefer geocoded sources (SA > Orennia > WoodMac)
   • Capacity: Prefer sources with capacity methodology (SA > DCH > Orennia)
   • Status: Prefer sources with explicit status tracking (WoodMac > Orennia > SA)
   • Dates: Cross-validate using all available sources

4. VALIDATION WORKFLOW:
   • Run compare_data_sources.py after ingestion
   • Generate campus distance analysis for overlap detection
   • Flag discrepancies > 20% capacity difference for manual review
""")

    return recommendations

# ============================================================================
# MAIN EXECUTION
# ============================================================================

def main():
    # Set stdout to UTF-8 encoding to handle emojis
    import sys
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

    print("="*70)
    print("NEW SOURCE DATA QUALITY & COVERAGE ANALYSIS")
    print(f"Analysis Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("="*70)

    all_metrics = []

    for name, config in SOURCES.items():
        filepath = os.path.join(SOURCE_DIR, config['file'])

        if not os.path.exists(filepath):
            print(f"\n⚠️ WARNING: {name} file not found: {filepath}")
            continue

        rows = load_csv(filepath)
        metrics = analyze_source(name, config, rows)
        all_metrics.append(metrics)

    # Generate comparative analysis
    generate_comparison_report(all_metrics)

    # Generate integration recommendations
    recommendations = generate_integration_recommendations(all_metrics)

    # Save metrics to JSON for later use
    output_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        'outputs',
        f'source_analysis_{datetime.now().strftime("%Y%m%d_%H%M")}.json'
    )

    # Ensure output directory exists
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    with open(output_path, 'w') as f:
        json.dump({
            'analysis_date': datetime.now().isoformat(),
            'sources': all_metrics,
            'recommendations': recommendations
        }, f, indent=2, default=str)

    print(f"\n📁 Analysis saved to: {output_path}")
    print("\n" + "="*70)
    print("ANALYSIS COMPLETE")
    print("="*70)

    return all_metrics

if __name__ == "__main__":
    main()
