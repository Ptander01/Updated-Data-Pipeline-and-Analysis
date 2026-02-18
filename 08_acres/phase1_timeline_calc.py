"""
Phase 1: Timeline Calculation - Peer Self-Build Planning Timeline Analysis
===========================================================================

Calculates the time difference (in months) between land acquisition and first MW
for in-scope peer self-build DC sites.

PREREQUISITES:
1. Run phase1_scope_filter.py to create peer_selfbuild_2025_2027
2. Run phase1_acres_match.py to create peer_selfbuild_acres_matched

KEY OUTPUTS:
- timeline_months: Land sale date → First MW date
- timeline_years: Same in years
- Ownership determination: Hyperscaler vs Developer owned land

USAGE (in ArcGIS Pro Python window):
    exec(open(r"C:/Users/ptanderson/Documents/ArcGIS/Projects/Lean Consensus DC Model/scripts/08_acres/phase1_timeline_calc.py", encoding='utf-8').read())

Author: Meta Data Center GIS Team
Created: 2026-02-02
Project: Peer Planning Timeline Analysis (1-Week Sprint)
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
    script_dir = r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\scripts\08_acres"

utils_dir = os.path.join(os.path.dirname(script_dir), "_utils")
if utils_dir not in sys.path:
    sys.path.insert(0, utils_dir)

from config import GDB

arcpy.env.workspace = GDB
arcpy.env.overwriteOutput = True

# ==============================================================================
# CONFIGURATION
# ==============================================================================

# Input feature class
INPUT_MATCHED = os.path.join(GDB, "peer_selfbuild_acres_matched")

# Output feature class
OUTPUT_TIMELINE = os.path.join(GDB, "peer_selfbuild_timeline_analysis")

# Output report paths
REPORTS_DIR = os.path.join(os.path.dirname(script_dir), "00_docs", "reports")

# Company ownership keywords
HYPERSCALER_OWNER_KEYWORDS = {
    'AWS': ['AMAZON', 'AWS', 'AMAZON DATA', 'ADC', 'AMAZON.COM'],
    'Google': ['GOOGLE', 'ALPHABET', 'GCP'],
    'Microsoft': ['MICROSOFT', 'MSFT', 'AZURE'],
    'Oracle': ['ORACLE', 'OCI'],
}

# Developer/Other owner keywords (indicates NOT hyperscaler-owned)
DEVELOPER_KEYWORDS = [
    'VANTAGE', 'CLOVERLEAF', 'QTS', 'EQUINIX', 'DIGITAL REALTY', 'DLR',
    'CYRUSONE', 'CORESITE', 'ALIGNED', 'SWITCH', 'COMPASS', 'STACK',
    'EXPEDIENT', 'FLEXENTIAL', 'DATABANK', 'T5', 'STREAM', 'PRIME',
    'SABEY', 'LANDMARK', 'H5', 'TIERPOINT', 'COLOGIX', 'DCBLOX',
    'IRON MOUNTAIN', 'APPLIED DIGITAL', 'POWERHOUS', 'NTT',
]


def determine_land_ownership(company_normalized, acres_entity, acres_buyer, acres_seller):
    """
    Determine if land is owned by the hyperscaler or a developer/other entity.

    Returns: 'hyperscaler', 'developer', or 'unknown'
    """
    if not company_normalized:
        return 'unknown'

    # Get hyperscaler keywords
    hs_keywords = HYPERSCALER_OWNER_KEYWORDS.get(company_normalized, [company_normalized])

    # Check ACRES entity
    if acres_entity:
        entity_upper = str(acres_entity).upper()

        # Check if entity matches hyperscaler
        for kw in hs_keywords:
            if kw.upper() in entity_upper:
                return 'hyperscaler'

        # Check if entity matches known developer
        for dev_kw in DEVELOPER_KEYWORDS:
            if dev_kw.upper() in entity_upper:
                return 'developer'

    # Check buyer name
    if acres_buyer:
        buyer_upper = str(acres_buyer).upper()

        for kw in hs_keywords:
            if kw.upper() in buyer_upper:
                return 'hyperscaler'

        for dev_kw in DEVELOPER_KEYWORDS:
            if dev_kw.upper() in buyer_upper:
                return 'developer'

    return 'unknown'


def estimate_first_mw_date(site):
    """
    Estimate the first MW date based on mw_YYYY fields.

    Returns datetime representing Jan 1 of first year with MW > 0,
    or middle of year for more conservative estimate.
    """
    for year in range(2025, 2028):  # Only check in-scope years
        mw_field = f'mw_{year}'
        mw_value = site.get(mw_field)

        if mw_value and float(mw_value) > 0:
            # Return July 1 of that year as mid-year estimate
            return datetime(year, 7, 1)

    # Fallback: use first_mw_year if available
    first_year = site.get('first_mw_year')
    if first_year:
        return datetime(int(first_year), 7, 1)

    return None


def calculate_timeline(land_date, first_mw_date):
    """
    Calculate timeline from land acquisition to first MW.

    Returns dict with days, months, years.
    """
    if not land_date or not first_mw_date:
        return None

    # Handle string dates
    if isinstance(land_date, str):
        try:
            land_date = datetime.strptime(str(land_date)[:10], '%Y-%m-%d')
        except:
            return None

    # Calculate difference
    delta = first_mw_date - land_date

    days = delta.days
    months = days / 30.44  # Average days per month
    years = days / 365.25

    return {
        'days': days,
        'months': round(months, 1),
        'years': round(years, 2),
    }


def calculate_price_per_acre(transaction_amount, acres):
    """Calculate price per acre."""
    if not transaction_amount or not acres:
        return None

    try:
        amount = float(transaction_amount)
        acre_val = float(acres)

        if acre_val > 0:
            return round(amount / acre_val, 2)
    except:
        pass

    return None


def load_matched_sites():
    """Load matched sites from phase1_acres_match.py output."""
    print("\n" + "=" * 70)
    print("[Step 1] Loading matched sites...")
    print("=" * 70)

    if not arcpy.Exists(INPUT_MATCHED):
        print(f"   ERROR: {INPUT_MATCHED} not found.")
        print("   Run phase1_acres_match.py first.")
        return []

    sites = []
    fields = [f.name for f in arcpy.ListFields(INPUT_MATCHED)]

    # Build cursor fields
    cursor_fields = ['SHAPE@XY', 'OBJECTID']
    for field in fields:
        if field not in ['OBJECTID', 'Shape', 'SHAPE', 'Shape_Length', 'Shape_Area']:
            cursor_fields.append(field)

    with arcpy.da.SearchCursor(INPUT_MATCHED, cursor_fields) as cursor:
        for row in cursor:
            xy = row[0]

            record = {
                'lon': xy[0] if xy else None,
                'lat': xy[1] if xy else None,
                'oid': row[1],
            }

            for i, field in enumerate(cursor_fields[2:], 2):
                record[field] = row[i]

            sites.append(record)

    print(f"   Loaded {len(sites):,} sites")

    return sites


def analyze_timelines(sites):
    """
    Analyze land acquisition to first MW timelines.

    Returns list of sites with timeline analysis fields added.
    """
    print("\n" + "=" * 70)
    print("[Step 2] Analyzing timelines...")
    print("=" * 70)

    analyzed_sites = []

    stats = {
        'total': len(sites),
        'has_acres_match': 0,
        'has_land_date': 0,
        'has_first_mw': 0,
        'has_timeline': 0,
        'has_price': 0,
        'hyperscaler_owned': 0,
        'developer_owned': 0,
        'ownership_unknown': 0,
    }

    for site in sites:
        analyzed = site.copy()

        # Check ACRES match
        match_type = site.get('match_type')
        if match_type and match_type != 'no_match' and 'missing' not in str(match_type).lower():
            stats['has_acres_match'] += 1

        # Get land acquisition date
        land_date = site.get('acres_change_date')
        if land_date:
            stats['has_land_date'] += 1
            analyzed['land_acquisition_date'] = land_date
        else:
            analyzed['land_acquisition_date'] = None

        # Estimate first MW date
        first_mw_date = estimate_first_mw_date(site)
        if first_mw_date:
            stats['has_first_mw'] += 1
            analyzed['first_mw_date_est'] = first_mw_date
        else:
            analyzed['first_mw_date_est'] = None

        # Calculate timeline
        timeline = calculate_timeline(land_date, first_mw_date)
        if timeline:
            stats['has_timeline'] += 1
            analyzed['timeline_days'] = timeline['days']
            analyzed['timeline_months'] = timeline['months']
            analyzed['timeline_years'] = timeline['years']
        else:
            analyzed['timeline_days'] = None
            analyzed['timeline_months'] = None
            analyzed['timeline_years'] = None

        # Calculate price per acre
        price_per_acre = calculate_price_per_acre(
            site.get('acres_transaction_amount'),
            site.get('acres_acres')
        )
        if price_per_acre:
            stats['has_price'] += 1
            analyzed['price_per_acre'] = price_per_acre
        else:
            analyzed['price_per_acre'] = None

        # Determine land ownership
        ownership = determine_land_ownership(
            site.get('company_normalized'),
            site.get('acres_entity'),
            site.get('acres_buyer_name'),
            site.get('acres_seller_name')
        )
        analyzed['land_ownership'] = ownership

        if ownership == 'hyperscaler':
            stats['hyperscaler_owned'] += 1
        elif ownership == 'developer':
            stats['developer_owned'] += 1
        else:
            stats['ownership_unknown'] += 1

        analyzed_sites.append(analyzed)

    # Print stats
    print(f"\n   ANALYSIS SUMMARY:")
    print(f"   {'Metric':<40} {'Count':>10} {'%':>10}")
    print(f"   {'-'*40} {'-'*10} {'-'*10}")
    print(f"   {'Total sites':<40} {stats['total']:>10,} {'-':>10}")
    print(f"   {'With ACRES parcel match':<40} {stats['has_acres_match']:>10,} {stats['has_acres_match']/stats['total']*100:>9.1f}%")
    print(f"   {'With land acquisition date':<40} {stats['has_land_date']:>10,} {stats['has_land_date']/stats['total']*100:>9.1f}%")
    print(f"   {'With first MW estimate':<40} {stats['has_first_mw']:>10,} {stats['has_first_mw']/stats['total']*100:>9.1f}%")
    print(f"   {'With calculable timeline':<40} {stats['has_timeline']:>10,} {stats['has_timeline']/stats['total']*100:>9.1f}%")
    print(f"   {'With transaction price':<40} {stats['has_price']:>10,} {stats['has_price']/stats['total']*100:>9.1f}%")

    print(f"\n   LAND OWNERSHIP:")
    print(f"   {'Ownership Type':<40} {'Count':>10} {'%':>10}")
    print(f"   {'-'*40} {'-'*10} {'-'*10}")
    matched_total = stats['hyperscaler_owned'] + stats['developer_owned'] + stats['ownership_unknown']
    if matched_total > 0:
        print(f"   {'Hyperscaler-owned land':<40} {stats['hyperscaler_owned']:>10,} {stats['hyperscaler_owned']/matched_total*100:>9.1f}%")
        print(f"   {'Developer-owned land':<40} {stats['developer_owned']:>10,} {stats['developer_owned']/matched_total*100:>9.1f}%")
        print(f"   {'Unknown ownership':<40} {stats['ownership_unknown']:>10,} {stats['ownership_unknown']/matched_total*100:>9.1f}%")

    return analyzed_sites, stats


def create_output_feature_class(sites):
    """Create output feature class with timeline analysis."""
    print("\n" + "=" * 70)
    print("[Step 3] Creating output feature class...")
    print("=" * 70)

    # Delete existing
    if arcpy.Exists(OUTPUT_TIMELINE):
        arcpy.management.Delete(OUTPUT_TIMELINE)

    # Create feature class
    spatial_ref = arcpy.SpatialReference(4326)
    arcpy.management.CreateFeatureclass(
        GDB,
        os.path.basename(OUTPUT_TIMELINE),
        "POINT",
        spatial_reference=spatial_ref
    )

    # Add fields
    fields_to_add = [
        # Site identification
        ('unique_id', 'TEXT', 100),
        ('ucid', 'TEXT', 75),
        ('company_normalized', 'TEXT', 50),
        ('facility_name', 'TEXT', 200),
        ('city', 'TEXT', 100),
        ('state_abbr', 'TEXT', 10),
        ('market', 'TEXT', 100),

        # Capacity data
        ('mw_2025', 'DOUBLE', None),
        ('mw_2026', 'DOUBLE', None),
        ('mw_2027', 'DOUBLE', None),
        ('first_mw_year', 'SHORT', None),

        # ACRES data
        ('acres_entity', 'TEXT', 200),
        ('acres_apn', 'TEXT', 100),
        ('acres_acres', 'DOUBLE', None),
        ('acres_transaction_amount', 'DOUBLE', None),

        # Timeline analysis
        ('land_acquisition_date', 'DATE', None),
        ('first_mw_date_est', 'DATE', None),
        ('timeline_days', 'LONG', None),
        ('timeline_months', 'DOUBLE', None),
        ('timeline_years', 'DOUBLE', None),

        # Price analysis
        ('price_per_acre', 'DOUBLE', None),

        # Ownership analysis
        ('land_ownership', 'TEXT', 50),

        # Match metadata
        ('match_type', 'TEXT', 50),
    ]

    for field_name, field_type, field_length in fields_to_add:
        if field_length:
            arcpy.management.AddField(OUTPUT_TIMELINE, field_name, field_type, field_length=field_length)
        else:
            arcpy.management.AddField(OUTPUT_TIMELINE, field_name, field_type)

    # Insert records
    insert_fields = ['SHAPE@XY'] + [f[0] for f in fields_to_add]

    inserted = 0
    with arcpy.da.InsertCursor(OUTPUT_TIMELINE, insert_fields) as cursor:
        for site in sites:
            if not site.get('lon') or not site.get('lat'):
                continue

            row = [
                (site['lon'], site['lat']),
                site.get('unique_id'),
                site.get('ucid'),
                site.get('company_normalized'),
                site.get('facility_name'),
                site.get('city'),
                site.get('state_abbr'),
                site.get('market'),
                site.get('mw_2025'),
                site.get('mw_2026'),
                site.get('mw_2027'),
                site.get('first_mw_year'),
                site.get('acres_entity'),
                site.get('acres_apn'),
                site.get('acres_acres'),
                site.get('acres_transaction_amount'),
                site.get('land_acquisition_date'),
                site.get('first_mw_date_est'),
                site.get('timeline_days'),
                site.get('timeline_months'),
                site.get('timeline_years'),
                site.get('price_per_acre'),
                site.get('land_ownership'),
                site.get('match_type'),
            ]

            cursor.insertRow(row)
            inserted += 1

    print(f"   Created: {os.path.basename(OUTPUT_TIMELINE)}")
    print(f"   Records: {inserted:,}")

    return inserted


def print_timeline_statistics(sites):
    """Print detailed timeline statistics."""
    print("\n" + "=" * 70)
    print("TIMELINE ANALYSIS RESULTS")
    print("=" * 70)

    # Filter to sites with calculable timeline
    sites_with_timeline = [s for s in sites if s.get('timeline_months') is not None]

    if not sites_with_timeline:
        print("\n   No sites with calculable timelines.")
        print("   This may indicate:")
        print("   - ACRES parcel data not yet loaded")
        print("   - No transaction dates available in ACRES data")
        return

    # Overall statistics
    timelines = [s['timeline_months'] for s in sites_with_timeline]
    avg_timeline = sum(timelines) / len(timelines)
    min_timeline = min(timelines)
    max_timeline = max(timelines)

    print(f"\n   OVERALL TIMELINE STATISTICS (n={len(sites_with_timeline):,}):")
    print(f"   {'Metric':<35} {'Months':>12} {'Years':>12}")
    print(f"   {'-'*35} {'-'*12} {'-'*12}")
    print(f"   {'Average':<35} {avg_timeline:>12.1f} {avg_timeline/12:>12.2f}")
    print(f"   {'Minimum':<35} {min_timeline:>12.1f} {min_timeline/12:>12.2f}")
    print(f"   {'Maximum':<35} {max_timeline:>12.1f} {max_timeline/12:>12.2f}")

    # By company
    print(f"\n   TIMELINE BY COMPANY:")
    print(f"   {'Company':<15} {'Sites':>8} {'Avg Months':>12} {'Avg Years':>12}")
    print(f"   {'-'*15} {'-'*8} {'-'*12} {'-'*12}")

    by_company = defaultdict(list)
    for site in sites_with_timeline:
        company = site.get('company_normalized', 'Unknown')
        by_company[company].append(site['timeline_months'])

    for company in ['AWS', 'Google', 'Microsoft', 'Oracle']:
        if company in by_company:
            company_timelines = by_company[company]
            avg = sum(company_timelines) / len(company_timelines)
            print(f"   {company:<15} {len(company_timelines):>8,} {avg:>12.1f} {avg/12:>12.2f}")

    # By first MW year
    print(f"\n   TIMELINE BY FIRST MW YEAR:")
    print(f"   {'Year':<10} {'Sites':>8} {'Avg Months':>12}")
    print(f"   {'-'*10} {'-'*8} {'-'*12}")

    by_year = defaultdict(list)
    for site in sites_with_timeline:
        year = site.get('first_mw_year')
        if year:
            by_year[year].append(site['timeline_months'])

    for year in [2025, 2026, 2027]:
        if year in by_year:
            year_timelines = by_year[year]
            avg = sum(year_timelines) / len(year_timelines)
            print(f"   {year:<10} {len(year_timelines):>8,} {avg:>12.1f}")

    # Ownership breakdown
    print(f"\n   OWNERSHIP BREAKDOWN:")
    print(f"   {'Ownership':<25} {'Sites':>10} {'%':>10}")
    print(f"   {'-'*25} {'-'*10} {'-'*10}")

    by_ownership = defaultdict(int)
    for site in sites_with_timeline:
        ownership = site.get('land_ownership', 'unknown')
        by_ownership[ownership] += 1

    total = len(sites_with_timeline)
    for ownership, count in sorted(by_ownership.items()):
        pct = count / total * 100
        print(f"   {ownership.title():<25} {count:>10,} {pct:>9.1f}%")

    # Price per acre statistics
    sites_with_price = [s for s in sites if s.get('price_per_acre')]
    if sites_with_price:
        prices = [s['price_per_acre'] for s in sites_with_price]
        avg_price = sum(prices) / len(prices)

        print(f"\n   PRICE PER ACRE (n={len(sites_with_price):,}):")
        print(f"   Average: ${avg_price:,.0f}/acre")
        print(f"   Minimum: ${min(prices):,.0f}/acre")
        print(f"   Maximum: ${max(prices):,.0f}/acre")


def generate_summary_report(sites, stats):
    """Generate markdown summary report."""
    print("\n" + "=" * 70)
    print("[Step 4] Generating summary report...")
    print("=" * 70)

    # Ensure reports directory exists
    os.makedirs(REPORTS_DIR, exist_ok=True)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M')
    report_path = os.path.join(REPORTS_DIR, f"Peer_Timeline_Analysis_{timestamp}.md")

    sites_with_timeline = [s for s in sites if s.get('timeline_months') is not None]

    report = f"""# Peer Self-Build Planning Timeline Analysis Report

**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}
**Sprint:** February 9-13, 2026 (1-Week MVP)

---

## Executive Summary

This report analyzes the land acquisition to first MW timeline for peer hyperscaler
self-build data centers in North America with first MW scheduled for 2025-2027.

### Key Metrics

| Metric | Value |
|--------|-------|
| Total In-Scope Sites | {stats['total']:,} |
| Sites with ACRES Match | {stats['has_acres_match']:,} ({stats['has_acres_match']/stats['total']*100:.1f}%) |
| Sites with Calculable Timeline | {stats['has_timeline']:,} ({stats['has_timeline']/stats['total']*100:.1f}%) |

### Ownership Breakdown

| Land Ownership | Sites | % |
|----------------|-------|---|
| Hyperscaler-Owned | {stats['hyperscaler_owned']:,} | {stats['hyperscaler_owned']/(stats['hyperscaler_owned']+stats['developer_owned']+stats['ownership_unknown'])*100 if (stats['hyperscaler_owned']+stats['developer_owned']+stats['ownership_unknown']) > 0 else 0:.1f}% |
| Developer-Owned | {stats['developer_owned']:,} | {stats['developer_owned']/(stats['hyperscaler_owned']+stats['developer_owned']+stats['ownership_unknown'])*100 if (stats['hyperscaler_owned']+stats['developer_owned']+stats['ownership_unknown']) > 0 else 0:.1f}% |
| Unknown | {stats['ownership_unknown']:,} | {stats['ownership_unknown']/(stats['hyperscaler_owned']+stats['developer_owned']+stats['ownership_unknown'])*100 if (stats['hyperscaler_owned']+stats['developer_owned']+stats['ownership_unknown']) > 0 else 0:.1f}% |

---

## Timeline Analysis

"""

    if sites_with_timeline:
        timelines = [s['timeline_months'] for s in sites_with_timeline]
        avg_timeline = sum(timelines) / len(timelines)

        report += f"""### Overall Statistics

| Statistic | Months | Years |
|-----------|--------|-------|
| Average | {avg_timeline:.1f} | {avg_timeline/12:.2f} |
| Minimum | {min(timelines):.1f} | {min(timelines)/12:.2f} |
| Maximum | {max(timelines):.1f} | {max(timelines)/12:.2f} |

### By Company

| Company | Sites | Avg Timeline (months) |
|---------|-------|----------------------|
"""
        by_company = defaultdict(list)
        for site in sites_with_timeline:
            company = site.get('company_normalized', 'Unknown')
            by_company[company].append(site['timeline_months'])

        for company in ['AWS', 'Google', 'Microsoft', 'Oracle']:
            if company in by_company:
                company_timelines = by_company[company]
                avg = sum(company_timelines) / len(company_timelines)
                report += f"| {company} | {len(company_timelines)} | {avg:.1f} |\n"

    else:
        report += """### No Timeline Data Available

Timeline calculations require:
1. ACRES parcel data with transaction dates
2. Matched DC sites to parcels

**Next Steps:**
- Load ACRES data via `ingest_acres.py`
- Re-run `phase1_acres_match.py`
- Re-run this script

"""

    report += f"""
---

## Data Sources

- **Consensus Model:** gold_buildings_full (DC locations, capacity)
- **ACRES:** Land parcel ownership and transaction data
- **Scope:** AWS, Google, Microsoft, Oracle - North America - First MW 2025-2027

---

## Output Files

- `peer_selfbuild_2025_2027` - Scoped DC sites
- `peer_selfbuild_acres_matched` - Sites with ACRES parcel match
- `peer_selfbuild_timeline_analysis` - Final analysis output

---

*Report generated by phase1_timeline_calc.py*
"""

    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(report)

    print(f"   Report saved: {report_path}")

    return report_path


def main():
    """Main function for timeline calculation."""
    print("=" * 70)
    print("PHASE 1: TIMELINE CALCULATION")
    print("Peer Self-Build Planning Timeline Analysis")
    print("=" * 70)
    print(f"Started: {datetime.now()}")

    # Step 1: Load matched sites
    sites = load_matched_sites()

    if not sites:
        print("\n   ERROR: No matched sites found.")
        print("   Run phase1_scope_filter.py and phase1_acres_match.py first.")
        return

    # Step 2: Analyze timelines
    analyzed_sites, stats = analyze_timelines(sites)

    # Step 3: Create output
    count = create_output_feature_class(analyzed_sites)

    # Step 4: Print statistics
    print_timeline_statistics(analyzed_sites)

    # Step 5: Generate report
    report_path = generate_summary_report(analyzed_sites, stats)

    # Final output
    print("\n" + "=" * 70)
    print("PHASE 1 TIMELINE CALCULATION COMPLETE")
    print("=" * 70)
    print(f"\n   Output: {os.path.basename(OUTPUT_TIMELINE)} ({count:,} records)")
    print(f"   Report: {os.path.basename(report_path)}")
    print(f"\n   KEY FINDINGS:")
    print(f"   - Sites analyzed: {stats['total']:,}")
    print(f"   - With timeline: {stats['has_timeline']:,}")
    print(f"   - Hyperscaler-owned: {stats['hyperscaler_owned']:,}")
    print(f"   - Developer-owned: {stats['developer_owned']:,}")
    print(f"\n   Completed: {datetime.now()}")
    print("=" * 70)

    return analyzed_sites, stats


# ==============================================================================
# EXECUTE
# ==============================================================================

if __name__ == "__main__":
    main()
else:
    main()
