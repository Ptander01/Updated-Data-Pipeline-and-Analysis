"""
Phase 1: Scope Filter - Peer Self-Build Planning Timeline Analysis
===================================================================

Filters the Consensus Model (gold_buildings_full) to in-scope sites for the
Peer Self-Build Planning Timeline / Land Banking Assessment.

SCOPE:
- Companies: Amazon (AWS), Google, Microsoft, Oracle
- Geography: North America (US, Canada, Mexico)
- First MW: 2025-2027
- Type: Self-Build / On-Prem / Owned (excludes leased colo)

OUTPUT:
- peer_selfbuild_2025_2027 feature class with filtered sites
- Summary statistics by company

USAGE (in ArcGIS Pro Python window):
    exec(open(r"C:/Users/ptanderson/Documents/ArcGIS/Projects/Lean Consensus DC Model/scripts/08_acres/phase1_scope_filter.py", encoding='utf-8').read())

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

from config import GDB, GOLD_BUILDINGS

arcpy.env.workspace = GDB
arcpy.env.overwriteOutput = True

# ==============================================================================
# SCOPE CONFIGURATION
# ==============================================================================

# In-scope companies (hyperscalers only, no colo)
IN_SCOPE_COMPANIES = ['AWS', 'Google', 'Microsoft', 'Oracle']

# Company aliases for fuzzy matching
COMPANY_ALIASES = {
    'AWS': ['AWS', 'Amazon', 'Amazon Web Services', 'AMAZON_DATA_CENTERS'],
    'Google': ['Google', 'Alphabet', 'GOOGLE_DATA_CENTERS'],
    'Microsoft': ['Microsoft', 'MSFT', 'MICROSOFT_DATA_CENTERS'],
    'Oracle': ['Oracle', 'ORACLE_DATA_CENTERS'],
}

# Geographic scope
IN_SCOPE_REGION = 'AMER'
IN_SCOPE_COUNTRIES = ['United States', 'USA', 'US', 'Canada', 'Mexico']

# Temporal scope: First MW in 2025, 2026, or 2027
FIRST_MW_YEARS = [2025, 2026, 2027]

# Record level filter (self-build types)
IN_SCOPE_RECORD_LEVELS = ['Building', 'TLBM_Hyperscaler']

# Output feature class
OUTPUT_FC = os.path.join(GDB, "peer_selfbuild_2025_2027")


def normalize_company(company_value):
    """Normalize company name to standard form."""
    if not company_value:
        return None

    company_str = str(company_value).strip()

    for standard_name, aliases in COMPANY_ALIASES.items():
        for alias in aliases:
            if alias.lower() in company_str.lower() or company_str.lower() in alias.lower():
                return standard_name

    return company_str


def is_in_scope_company(company_value):
    """Check if company is in scope."""
    normalized = normalize_company(company_value)
    return normalized in IN_SCOPE_COMPANIES


def is_in_scope_geography(record):
    """Check if record is in North America."""
    region = record.get('region', '')
    country = record.get('country', '')

    # Check region
    if region and 'AMER' in str(region).upper():
        return True

    # Check country
    if country:
        for in_scope_country in IN_SCOPE_COUNTRIES:
            if in_scope_country.lower() in str(country).lower():
                return True

    # Check state (if US state abbreviation)
    state = record.get('state_abbr', '')
    if state and len(str(state)) == 2:
        # Assume 2-letter state codes are US
        return True

    return False


def get_first_mw_year(record):
    """
    Determine the first year with MW capacity > 0.

    Returns the year (int) or None if no capacity in 2025-2032.
    """
    for year in range(2023, 2033):
        field_name = f'mw_{year}'
        mw_value = record.get(field_name, 0)
        if mw_value and float(mw_value) > 0:
            return year
    return None


def is_in_scope_temporal(record):
    """Check if first MW is in 2025-2027."""
    first_mw_year = get_first_mw_year(record)
    return first_mw_year in FIRST_MW_YEARS


def is_in_scope_type(record):
    """Check if record is self-build type (not leased colo)."""
    record_level = record.get('record_level', '')

    # If record_level is available, use it
    if record_level:
        if record_level in IN_SCOPE_RECORD_LEVELS:
            return True
        # Exclude colo records
        if 'colo' in str(record_level).lower():
            return False

    # Otherwise, assume in-scope if company is hyperscaler
    # (hyperscalers' buildings are typically self-build)
    company = record.get('company_clean', '')
    if normalize_company(company) in IN_SCOPE_COMPANIES:
        return True

    return False


def load_and_filter_buildings():
    """
    Load gold_buildings_full and filter to in-scope records.

    Returns list of in-scope record dicts.
    """
    print("\n" + "=" * 70)
    print("[Step 1] Loading and filtering Consensus Model data...")
    print("=" * 70)

    if not arcpy.Exists(GOLD_BUILDINGS):
        print(f"   ERROR: {GOLD_BUILDINGS} not found.")
        return []

    # Get available fields
    fields = [f.name for f in arcpy.ListFields(GOLD_BUILDINGS)]
    print(f"   Available fields: {len(fields)}")

    # Required fields
    required_fields = ['SHAPE@XY', 'OBJECTID', 'unique_id']

    # Optional fields to include if available
    optional_fields = [
        'ucid', 'company_clean', 'company_clean_filter', 'record_level',
        'facility_name', 'facility_status', 'city', 'state_abbr', 'country', 'region',
        'full_capacity_mw', 'commissioned_power_mw',
        'mw_2023', 'mw_2024', 'mw_2025', 'mw_2026', 'mw_2027',
        'mw_2028', 'mw_2029', 'mw_2030', 'mw_2031', 'mw_2032',
        'source', 'market', 'latitude', 'longitude'
    ]

    cursor_fields = required_fields.copy()
    for field in optional_fields:
        if field in fields and field not in cursor_fields:
            cursor_fields.append(field)

    print(f"   Reading {len(cursor_fields)} fields...")

    all_records = []
    in_scope_records = []

    # Tracking for filtering stats
    filter_stats = {
        'total': 0,
        'company_pass': 0,
        'geography_pass': 0,
        'temporal_pass': 0,
        'type_pass': 0,
        'final_in_scope': 0,
    }

    with arcpy.da.SearchCursor(GOLD_BUILDINGS, cursor_fields) as cursor:
        for row in cursor:
            filter_stats['total'] += 1

            # Build record dict
            record = {}
            for i, field in enumerate(cursor_fields):
                if field == 'SHAPE@XY':
                    xy = row[i]
                    record['lon'] = xy[0] if xy else None
                    record['lat'] = xy[1] if xy else None
                else:
                    record[field] = row[i]

            all_records.append(record)

            # Apply filters
            company_ok = is_in_scope_company(record.get('company_clean'))
            if not company_ok:
                continue
            filter_stats['company_pass'] += 1

            geography_ok = is_in_scope_geography(record)
            if not geography_ok:
                continue
            filter_stats['geography_pass'] += 1

            temporal_ok = is_in_scope_temporal(record)
            if not temporal_ok:
                continue
            filter_stats['temporal_pass'] += 1

            type_ok = is_in_scope_type(record)
            if not type_ok:
                continue
            filter_stats['type_pass'] += 1

            # Record is in scope!
            record['company_normalized'] = normalize_company(record.get('company_clean'))
            record['first_mw_year'] = get_first_mw_year(record)
            in_scope_records.append(record)
            filter_stats['final_in_scope'] += 1

    # Print filter stats
    print(f"\n   FILTERING SUMMARY:")
    print(f"   {'Filter Stage':<30} {'Records':>10} {'Passed':>10}")
    print(f"   {'-'*30} {'-'*10} {'-'*10}")
    print(f"   {'Total records':<30} {filter_stats['total']:>10,} {'-':>10}")
    print(f"   {'Company filter (AWS/Google/MSFT/Oracle)':<30} {filter_stats['company_pass']:>10,} {filter_stats['company_pass']/filter_stats['total']*100:>9.1f}%")
    print(f"   {'Geography filter (North America)':<30} {filter_stats['geography_pass']:>10,} {filter_stats['geography_pass']/filter_stats['total']*100:>9.1f}%")
    print(f"   {'Temporal filter (2025-2027 first MW)':<30} {filter_stats['temporal_pass']:>10,} {filter_stats['temporal_pass']/filter_stats['total']*100:>9.1f}%")
    print(f"   {'Type filter (self-build)':<30} {filter_stats['type_pass']:>10,} {filter_stats['type_pass']/filter_stats['total']*100:>9.1f}%")
    print(f"   {'-'*30} {'-'*10} {'-'*10}")
    print(f"   {'FINAL IN-SCOPE':<30} {filter_stats['final_in_scope']:>10,} {filter_stats['final_in_scope']/filter_stats['total']*100:>9.1f}%")

    return in_scope_records


def create_output_feature_class(records):
    """Create output feature class with in-scope records."""
    print("\n" + "=" * 70)
    print("[Step 2] Creating output feature class...")
    print("=" * 70)

    # Delete existing
    if arcpy.Exists(OUTPUT_FC):
        print(f"   Deleting existing: {os.path.basename(OUTPUT_FC)}")
        arcpy.management.Delete(OUTPUT_FC)

    # Create feature class
    spatial_ref = arcpy.SpatialReference(4326)
    arcpy.management.CreateFeatureclass(
        GDB,
        os.path.basename(OUTPUT_FC),
        "POINT",
        spatial_reference=spatial_ref
    )

    # Add fields
    fields_to_add = [
        ('unique_id', 'TEXT', 100),
        ('ucid', 'TEXT', 75),
        ('company_clean', 'TEXT', 100),
        ('company_normalized', 'TEXT', 50),
        ('facility_name', 'TEXT', 200),
        ('facility_status', 'TEXT', 50),
        ('city', 'TEXT', 100),
        ('state_abbr', 'TEXT', 10),
        ('country', 'TEXT', 100),
        ('region', 'TEXT', 20),
        ('record_level', 'TEXT', 50),
        ('full_capacity_mw', 'DOUBLE', None),
        ('commissioned_power_mw', 'DOUBLE', None),
        ('mw_2025', 'DOUBLE', None),
        ('mw_2026', 'DOUBLE', None),
        ('mw_2027', 'DOUBLE', None),
        ('first_mw_year', 'SHORT', None),
        ('source', 'TEXT', 200),
        ('market', 'TEXT', 100),
        ('latitude', 'DOUBLE', None),
        ('longitude', 'DOUBLE', None),
    ]

    for field_name, field_type, field_length in fields_to_add:
        if field_length:
            arcpy.management.AddField(OUTPUT_FC, field_name, field_type, field_length=field_length)
        else:
            arcpy.management.AddField(OUTPUT_FC, field_name, field_type)

    # Insert records
    insert_fields = ['SHAPE@XY'] + [f[0] for f in fields_to_add]

    inserted = 0
    with arcpy.da.InsertCursor(OUTPUT_FC, insert_fields) as cursor:
        for record in records:
            if not record.get('lon') or not record.get('lat'):
                continue

            row = [
                (record['lon'], record['lat']),
                record.get('unique_id'),
                record.get('ucid'),
                record.get('company_clean'),
                record.get('company_normalized'),
                record.get('facility_name'),
                record.get('facility_status'),
                record.get('city'),
                record.get('state_abbr'),
                record.get('country'),
                record.get('region'),
                record.get('record_level'),
                record.get('full_capacity_mw'),
                record.get('commissioned_power_mw'),
                record.get('mw_2025'),
                record.get('mw_2026'),
                record.get('mw_2027'),
                record.get('first_mw_year'),
                record.get('source'),
                record.get('market'),
                record.get('lat'),
                record.get('lon'),
            ]

            cursor.insertRow(row)
            inserted += 1

    print(f"   Created: {os.path.basename(OUTPUT_FC)}")
    print(f"   Records: {inserted:,}")

    return inserted


def print_summary_statistics(records):
    """Print summary statistics for in-scope records."""
    print("\n" + "=" * 70)
    print("SCOPE FILTER SUMMARY STATISTICS")
    print("=" * 70)

    if not records:
        print("   No in-scope records found.")
        return

    # By Company
    print(f"\n   BY COMPANY:")
    print(f"   {'Company':<15} {'Sites':>10} {'Total MW (2027)':>18} {'Avg MW/Site':>15}")
    print(f"   {'-'*15} {'-'*10} {'-'*18} {'-'*15}")

    by_company = defaultdict(list)
    for r in records:
        company = r.get('company_normalized', 'Unknown')
        by_company[company].append(r)

    for company in IN_SCOPE_COMPANIES:
        company_records = by_company.get(company, [])
        total_mw = sum(r.get('mw_2027') or 0 for r in company_records)
        avg_mw = total_mw / len(company_records) if company_records else 0
        print(f"   {company:<15} {len(company_records):>10,} {total_mw:>18,.0f} {avg_mw:>15,.1f}")

    total_sites = len(records)
    total_mw = sum(r.get('mw_2027') or 0 for r in records)
    print(f"   {'-'*15} {'-'*10} {'-'*18} {'-'*15}")
    print(f"   {'TOTAL':<15} {total_sites:>10,} {total_mw:>18,.0f} {total_mw/total_sites:>15,.1f}")

    # By First MW Year
    print(f"\n   BY FIRST MW YEAR:")
    print(f"   {'Year':<10} {'Sites':>10} {'% of Total':>12}")
    print(f"   {'-'*10} {'-'*10} {'-'*12}")

    by_year = defaultdict(int)
    for r in records:
        year = r.get('first_mw_year')
        if year:
            by_year[year] += 1

    for year in FIRST_MW_YEARS:
        count = by_year.get(year, 0)
        pct = count / total_sites * 100 if total_sites > 0 else 0
        print(f"   {year:<10} {count:>10,} {pct:>11.1f}%")

    # By State (top 10)
    print(f"\n   TOP 10 STATES:")
    print(f"   {'State':<10} {'Sites':>10}")
    print(f"   {'-'*10} {'-'*10}")

    by_state = defaultdict(int)
    for r in records:
        state = r.get('state_abbr', 'Unknown')
        if state:
            by_state[state] += 1

    for state, count in sorted(by_state.items(), key=lambda x: -x[1])[:10]:
        print(f"   {state:<10} {count:>10,}")

    # By Company x First MW Year
    print(f"\n   COMPANY x FIRST MW YEAR MATRIX:")
    print(f"   {'Company':<15}", end='')
    for year in FIRST_MW_YEARS:
        print(f" {year:>8}", end='')
    print(f" {'Total':>10}")
    print(f"   {'-'*15}", end='')
    for _ in FIRST_MW_YEARS:
        print(f" {'-'*8}", end='')
    print(f" {'-'*10}")

    for company in IN_SCOPE_COMPANIES:
        company_records = by_company.get(company, [])
        print(f"   {company:<15}", end='')
        company_total = 0
        for year in FIRST_MW_YEARS:
            count = sum(1 for r in company_records if r.get('first_mw_year') == year)
            print(f" {count:>8,}", end='')
            company_total += count
        print(f" {company_total:>10,}")


def main():
    """Main function for Phase 1 scope filtering."""
    print("=" * 70)
    print("PHASE 1: SCOPE FILTER")
    print("Peer Self-Build Planning Timeline Analysis")
    print("=" * 70)
    print(f"Started: {datetime.now()}")

    print(f"\n   SCOPE CRITERIA:")
    print(f"   - Companies: {', '.join(IN_SCOPE_COMPANIES)}")
    print(f"   - Geography: North America (US, Canada, Mexico)")
    print(f"   - First MW: {', '.join(str(y) for y in FIRST_MW_YEARS)}")
    print(f"   - Type: Self-Build (excludes leased colo)")

    # Step 1: Load and filter
    records = load_and_filter_buildings()

    if not records:
        print("\n   ERROR: No in-scope records found.")
        print("   Check that gold_buildings_full has data for:")
        print(f"     - Companies: {IN_SCOPE_COMPANIES}")
        print(f"     - MW fields: mw_2025, mw_2026, mw_2027")
        return

    # Step 2: Create output feature class
    count = create_output_feature_class(records)

    # Step 3: Print summary
    print_summary_statistics(records)

    # Final output
    print("\n" + "=" * 70)
    print("PHASE 1 SCOPE FILTER COMPLETE")
    print("=" * 70)
    print(f"\n   Output: {os.path.basename(OUTPUT_FC)} ({count:,} records)")
    print(f"\n   Next Steps:")
    print(f"   1. Run phase1_acres_match.py to match sites to land parcels")
    print(f"   2. Run phase1_ownership_analysis.py for ownership breakdown")
    print(f"   3. Run phase1_timeline_calc.py for land-to-MW timeline")
    print(f"\n   Completed: {datetime.now()}")
    print("=" * 70)

    return records


# ==============================================================================
# EXECUTE
# ==============================================================================

if __name__ == "__main__":
    main()
else:
    main()
