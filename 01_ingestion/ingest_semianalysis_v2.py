"""
Semianalysis Building Ingestion Script (V2 - CSV-based)
Ingests Semianalysis data from cleaned CSV into gold_buildings feature class.

This version reads from the cleaned CSV file produced by clean_semianalysis_excel.py
and includes new V2 fields: end_user, tenant, gpu_cloud, workload_type

Author: Meta Data Center GIS Team
Last Updated: 2026-01-12
"""

import arcpy
from datetime import datetime
import os
import sys
import csv

# Add _utils to path for config import
try:
    script_dir = os.path.dirname(os.path.abspath(__file__))
except NameError:
    script_dir = r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\scripts\01_ingestion"

utils_dir = os.path.join(os.path.dirname(script_dir), "_utils")
if utils_dir not in sys.path:
    sys.path.insert(0, utils_dir)

from config import GDB, GOLD_BUILDINGS
from date_helpers import parse_date_flexible

# ============================================================================
# CONFIGURATION
# ============================================================================

# Source CSV file - UPDATE THIS to point to the latest cleaned/merged export
# This is the output from semianalysis_pipeline.py (merged NA + Overseas + AI Labs + TLBM)
SOURCE_CSV = r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\scripts\outputs\semianalysis_FINAL_20260203_0916.csv"

TARGET_FC = os.path.join(GDB, GOLD_BUILDINGS)
SOURCE_NAME = "Semianalysis"

# TLBM (Total Lease by Market) record handling
# TLBM records are market-level aggregates. With centroid geocoding in the pipeline,
# most TLBM records will now have coordinates from market centroid lookup.
# Options: 'include' = ingest with centroid coords, 'skip' = don't ingest
TLBM_HANDLING = 'include'  # Include TLBM records with their market centroid coordinates

# CSV column to Gold field mapping
# Keys are CSV column names (after cleaning), values are (gold_field, transform_func or None)
CSV_TO_GOLD_MAP = {
    # Identifiers
    'Unique_ID': 'source_unique_id',

    # Location
    'Lat': 'latitude',
    'Long': 'longitude',
    'State': 'state',  # Column name in merged file
    'City': 'city',
    'ZIP Code': 'postal_code',
    'Cluster': 'building_designation',
    'Country': 'country',
    'Region': 'region',
    'Company': 'company_source',
    'Type': 'type_category',
    'Market': 'market',

    # Capacity
    'Installed Capacity (Q1 2024)': 'commissioned_power_mw',  # Or Q1 2025 depending on version
    'Total under Construction MW': 'uc_power_mw',
    'Total Planned MW': 'planned_power_mw',
    'Full Capacity': 'full_capacity_mw',
    'Planned + UC': 'planned_plus_uc_mw',
    'Facility Square Footage': 'facility_sqft',

    # Dates
    'Start of operations': 'construction_start_date',
    'Actual Live Assumption': 'actual_live_date',

    # NEW V2 FIELDS (using actual column names from merged file)
    'Estimated End User (based on Mosaic Theory when not public)': 'end_user',
    'Estimated Tenant (based on Mosaic Theory when not public)': 'tenant',
    'GPU Cloud': 'gpu_cloud',
    # Note: Workload Type may not exist in this version

    # Source tracking
    'Source Sheet': '_source_sheet',  # Temporary, used for record_level
}

# Region standardization
REGION_MAP = {
    'NorthAmerica': 'AMER', 'North America': 'AMER', 'NORTHAMERICA': 'AMER',
    'EMEA': 'EMEA', 'APAC': 'APAC', 'AMER': 'AMER',
}

# Country standardization
COUNTRY_MAP = {
    'USA': 'United States', 'US': 'United States', 'U.S.': 'United States',
    'U.S.A.': 'United States', 'United States': 'United States'
}

# Country to region mapping
COUNTRY_TO_REGION = {
    'United States': 'AMER', 'USA': 'AMER', 'Canada': 'AMER', 'Mexico': 'AMER',
    'United Kingdom': 'EMEA', 'UK': 'EMEA', 'Ireland': 'EMEA', 'Germany': 'EMEA',
    'France': 'EMEA', 'Netherlands': 'EMEA', 'Sweden': 'EMEA', 'Denmark': 'EMEA',
    'Finland': 'EMEA', 'Norway': 'EMEA', 'Spain': 'EMEA', 'Italy': 'EMEA',
    'Singapore': 'APAC', 'Japan': 'APAC', 'Australia': 'APAC', 'India': 'APAC',
    'Indonesia': 'APAC', 'Malaysia': 'APAC', 'Taiwan': 'APAC', 'South Korea': 'APAC',
    'China': 'APAC', 'Hong Kong': 'APAC', 'Thailand': 'APAC', 'Vietnam': 'APAC',
}

# State abbreviations
STATE_ABBR = {
    'Alabama': 'AL', 'Alaska': 'AK', 'Arizona': 'AZ', 'Arkansas': 'AR',
    'California': 'CA', 'Colorado': 'CO', 'Connecticut': 'CT', 'Delaware': 'DE',
    'Florida': 'FL', 'Georgia': 'GA', 'Hawaii': 'HI', 'Idaho': 'ID',
    'Illinois': 'IL', 'Indiana': 'IN', 'Iowa': 'IA', 'Kansas': 'KS',
    'Kentucky': 'KY', 'Louisiana': 'LA', 'Maine': 'ME', 'Maryland': 'MD',
    'Massachusetts': 'MA', 'Michigan': 'MI', 'Minnesota': 'MN', 'Mississippi': 'MS',
    'Missouri': 'MO', 'Montana': 'MT', 'Nebraska': 'NE', 'Nevada': 'NV',
    'New Hampshire': 'NH', 'New Jersey': 'NJ', 'New Mexico': 'NM', 'New York': 'NY',
    'North Carolina': 'NC', 'North Dakota': 'ND', 'Ohio': 'OH', 'Oklahoma': 'OK',
    'Oregon': 'OR', 'Pennsylvania': 'PA', 'Rhode Island': 'RI', 'South Carolina': 'SC',
    'South Dakota': 'SD', 'Tennessee': 'TN', 'Texas': 'TX', 'Utah': 'UT',
    'Vermont': 'VT', 'Virginia': 'VA', 'Washington': 'WA', 'West Virginia': 'WV',
    'Wisconsin': 'WI', 'Wyoming': 'WY'
}


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def delete_existing_records(target_fc, source_name):
    """Delete all existing records from this source before fresh ingestion."""
    print(f"\n[CLEANUP] Checking for existing {source_name} records...")

    where_clause = f"source = '{source_name}'"

    temp_layer = "temp_delete_layer"
    if arcpy.Exists(temp_layer):
        arcpy.management.Delete(temp_layer)

    arcpy.management.MakeFeatureLayer(target_fc, temp_layer)
    arcpy.management.SelectLayerByAttribute(temp_layer, "NEW_SELECTION", where_clause)

    deleted_count = int(arcpy.GetCount_management(temp_layer)[0])

    if deleted_count > 0:
        arcpy.management.DeleteRows(temp_layer)
        print(f"   [OK] Deleted {deleted_count:,} existing {source_name} records")
    else:
        print(f"   [OK] No existing {source_name} records found")

    arcpy.management.Delete(temp_layer)
    return deleted_count


def safe_float(val):
    """Safely convert to float."""
    if val is None or val == '' or str(val).strip() == '':
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def safe_str(val, max_len=None):
    """Safely convert to string and optionally truncate."""
    if val is None or str(val).strip() in ['', 'nan', 'None', '0']:
        return None
    s = str(val).strip()
    if max_len and len(s) > max_len:
        return s[:max_len]
    return s if s else None


def get_state_abbr(state):
    """Get state abbreviation."""
    if not state:
        return None
    state_str = str(state).strip()
    if len(state_str) == 2:
        return state_str.upper()
    return STATE_ABBR.get(state_str)


def standardize_country(country):
    """Standardize country name."""
    if not country:
        return None
    return COUNTRY_MAP.get(str(country).strip(), str(country).strip())


def standardize_region(region, country):
    """Standardize region value."""
    if region:
        mapped = REGION_MAP.get(str(region).strip())
        if mapped:
            return mapped
    if country:
        return COUNTRY_TO_REGION.get(country, COUNTRY_TO_REGION.get(COUNTRY_MAP.get(country)))
    return None


def generate_campus_id(company, city, cluster, lat, lon):
    """Generate unique campus_id."""
    import re
    def slug(text):
        if not text:
            return ''
        return re.sub(r'[^a-z0-9]+', '', str(text).lower())

    name_slug = slug(cluster) if cluster else f"{round(float(lat),3)}{round(float(lon),3)}".replace('.','').replace('-','n')
    return f"{slug(company)}|{slug(city)}|{name_slug}"


def determine_status(installed_mw, uc_mw, planned_mw):
    """Determine facility status based on capacity fields."""
    installed = safe_float(installed_mw) or 0
    uc = safe_float(uc_mw) or 0
    planned = safe_float(planned_mw) or 0

    if installed > 0:
        return 'Active'
    elif uc > 0:
        return 'Under Construction'
    elif planned > 0:
        return 'Announced'
    return 'Unknown'


# ============================================================================
# MAIN INGESTION
# ============================================================================

def main():
    print("=" * 70)
    print(f"SEMIANALYSIS V2 INGESTION STARTED: {datetime.now()}")
    print("=" * 70)
    print(f"Source CSV: {SOURCE_CSV}")
    print(f"Target FC: {TARGET_FC}")

    # Verify source exists
    if not os.path.exists(SOURCE_CSV):
        raise Exception(f"Source CSV not found: {SOURCE_CSV}")

    # Delete existing records from this source
    delete_existing_records(TARGET_FC, SOURCE_NAME)

    # Target insert fields (including new V2 fields and year-over-year MW)
    insert_fields = [
        'SHAPE@XY', 'unique_id', 'source', 'source_unique_id', 'date_reported',
        'record_level', 'campus_id', 'campus_name', 'company_source', 'company_clean',
        'building_designation', 'address', 'postal_code', 'city', 'market',
        'state', 'state_abbr', 'county', 'country', 'region', 'latitude', 'longitude',
        'planned_power_mw', 'uc_power_mw', 'commissioned_power_mw', 'full_capacity_mw',
        'planned_plus_uc_mw',
        # Year-over-year MW forecasts (SA unique)
        'mw_2023', 'mw_2024', 'mw_2025', 'mw_2026', 'mw_2027',
        'mw_2028', 'mw_2029', 'mw_2030', 'mw_2031', 'mw_2032',
        'pue', 'actual_live_date', 'construction_start_date', 'facility_status', 'cancelled',
        'facility_sqft', 'type_category', 'data_vintage', 'ingest_date',
        # NEW V2 FIELDS
        'end_user', 'tenant', 'gpu_cloud', 'workload_type'
    ]

    insert_count = 0
    skip_count = 0

    print("\nReading CSV file...")

    with open(SOURCE_CSV, 'r', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        rows = list(reader)

    total_records = len(rows)
    print(f"Total CSV records: {total_records:,}")
    print("\nProcessing records...")

    with arcpy.da.InsertCursor(TARGET_FC, insert_fields) as insert_cursor:
        for row in rows:
            # Check record_level - skip TLBM records if configured
            record_level = safe_str(row.get('record_level'))
            if record_level and record_level.startswith('TLBM'):
                if TLBM_HANDLING == 'skip':
                    skip_count += 1
                    continue
                # Future: handle 'centroid' or 'null_geom' options here

            # Extract values from CSV
            src_unique_id = safe_str(row.get('Unique_ID'))
            lat = safe_float(row.get('Lat'))
            lon = safe_float(row.get('Long'))

            # Skip if missing coordinates
            if not lat or not lon:
                skip_count += 1
                continue

            # Location fields (handle both possible column names)
            us_state = safe_str(row.get('State') or row.get('US State'), 100)
            city = safe_str(row.get('City'), 100)
            zip_code = safe_str(row.get('ZIP Code'), 10)
            cluster = safe_str(row.get('Cluster'), 50)  # Truncate to 50 chars for building_designation field
            country = safe_str(row.get('Country'), 100)
            region = safe_str(row.get('Region'), 50)
            company = safe_str(row.get('Company'), 100)
            fac_type = safe_str(row.get('Type'), 50)
            market = safe_str(row.get('Market'), 100)

            # Capacity fields (handle multiple possible column names)
            installed_mw = safe_float(
                row.get('Installed Capacity (Q1 2024)') or
                row.get('Installed Capacity (Q1 2025)') or
                row.get('Installed Capacity MW (Q2 2025)') or
                row.get('Installed Capacity MW')
            )
            uc_mw = safe_float(row.get('Total under Construction MW'))
            planned_mw = safe_float(row.get('Total Planned MW'))
            full_cap = safe_float(row.get('Full Capacity'))
            planned_plus_uc = safe_float(row.get('Planned + UC'))
            sqft = safe_float(row.get('Facility Square Footage'))

            # Date fields
            start_ops = row.get('Start of operations')
            live_assumption = row.get('Actual Live Assumption')
            data_vintage_str = row.get('data_vintage')  # Added 2026-02-02: Read from CSV

            # NEW V2 FIELDS (use actual column names from merged file)
            end_user = safe_str(
                row.get('Estimated End User (based on Mosaic Theory when not public)') or
                row.get('End User'), 100
            )
            tenant = safe_str(
                row.get('Estimated Tenant (based on Mosaic Theory when not public)') or
                row.get('Tenant'), 100
            )
            gpu_cloud = safe_str(row.get('GPU Cloud'), 50)
            workload_type = safe_str(row.get('Workload Type'), 50)

            # YEAR-OVER-YEAR MW FIELDS (SA unique)
            # Now that upstream pipeline normalizes columns (2023.0 -> 2023),
            # we just need to check the standard column name
            mw_2023 = safe_float(row.get('2023'))
            mw_2024 = safe_float(row.get('2024'))
            mw_2025 = safe_float(row.get('2025'))
            mw_2026 = safe_float(row.get('2026'))
            mw_2027 = safe_float(row.get('2027'))
            mw_2028 = safe_float(row.get('2028'))
            mw_2029 = safe_float(row.get('2029'))
            mw_2030 = safe_float(row.get('2030'))
            mw_2031 = safe_float(row.get('2031'))
            mw_2032 = safe_float(row.get('2032'))

            # Clean up values that are just "0"
            if end_user == '0':
                end_user = None
            if tenant == '0':
                tenant = None
            if gpu_cloud == '0':
                gpu_cloud = None

            # ===== DERIVE FIELDS =====

            # Unique ID for gold_buildings
            unique_id = f"SEMI_{src_unique_id}" if src_unique_id else f"SEMI_{insert_count}"

            # Company clean (detect Meta/Facebook)
            company_clean = company
            if company:
                company_lower = company.lower()
                if 'meta' in company_lower or 'facebook' in company_lower:
                    company_clean = 'Meta'

            # Campus
            campus_name = cluster if cluster else f"{company_clean} {city}" if company_clean and city else None
            campus_id = generate_campus_id(company_clean, city, cluster, lat, lon) if company_clean else None

            # Standardize geography
            country_std = standardize_country(country)
            region_std = standardize_region(region, country_std)
            state_abbr = get_state_abbr(us_state)

            # Status
            facility_status = determine_status(installed_mw, uc_mw, planned_mw)

            # Capacity calculations
            commissioned_mw = installed_mw or 0
            full_capacity_mw = full_cap or (commissioned_mw + (uc_mw or 0) + (planned_mw or 0))
            planned_plus_uc_mw = planned_plus_uc if planned_plus_uc is not None else ((planned_mw or 0) + (uc_mw or 0))

            # Parse dates
            construction_start_date = parse_date_flexible(start_ops)
            actual_live_date = parse_date_flexible(live_assumption)

            # Geometry
            point = (lon, lat)

            # Determine record_level from CSV or default to 'Building'
            record_level_value = record_level if record_level else 'Building'

            # Insert row
            insert_cursor.insertRow([
                point,                    # SHAPE@XY
                unique_id,                # unique_id
                SOURCE_NAME,              # source
                src_unique_id,            # source_unique_id
                None,                     # date_reported
                record_level_value,       # record_level (from CSV for TLBM, else 'Building')
                campus_id,                # campus_id
                campus_name,              # campus_name
                company,                  # company_source
                company_clean,            # company_clean
                cluster,                  # building_designation
                None,                     # address
                zip_code,                 # postal_code
                city,                     # city
                market,                   # market
                us_state,                 # state
                state_abbr,               # state_abbr
                None,                     # county
                country_std,              # country
                region_std,               # region
                lat,                      # latitude
                lon,                      # longitude
                planned_mw or 0,          # planned_power_mw
                uc_mw or 0,               # uc_power_mw
                commissioned_mw,          # commissioned_power_mw
                full_capacity_mw,         # full_capacity_mw
                planned_plus_uc_mw,       # planned_plus_uc_mw
                # Year-over-year MW forecasts (SA unique)
                mw_2023,                  # mw_2023
                mw_2024,                  # mw_2024
                mw_2025,                  # mw_2025
                mw_2026,                  # mw_2026
                mw_2027,                  # mw_2027
                mw_2028,                  # mw_2028
                mw_2029,                  # mw_2029
                mw_2030,                  # mw_2030
                mw_2031,                  # mw_2031
                mw_2032,                  # mw_2032
                None,                     # pue
                actual_live_date,         # actual_live_date
                construction_start_date,  # construction_start_date
                facility_status,          # facility_status
                0,                        # cancelled
                sqft,                     # facility_sqft
                fac_type,                 # type_category
                parse_date_flexible(data_vintage_str),  # data_vintage - read from CSV
                datetime.now(),           # ingest_date
                # NEW V2 FIELDS
                end_user,                 # end_user
                tenant,                   # tenant
                gpu_cloud,                # gpu_cloud
                workload_type,            # workload_type
            ])

            insert_count += 1

            if insert_count % 500 == 0:
                print(f"  Processed {insert_count:,} records...")

    print("\n" + "=" * 70)
    print("SEMIANALYSIS V2 INGESTION COMPLETE")
    print("=" * 70)
    print(f"Inserted: {insert_count:,} records")
    print(f"Skipped: {skip_count:,} records (missing lat/lon)")
    print(f"Completed: {datetime.now()}")

    # Show new field stats
    print("\n" + "-" * 70)
    print("NEW FIELD POPULATION (V2 Fields):")
    print("-" * 70)

    for field in ['end_user', 'tenant', 'gpu_cloud', 'workload_type']:
        where = f"source = '{SOURCE_NAME}' AND {field} IS NOT NULL AND {field} <> ''"
        with arcpy.da.SearchCursor(TARGET_FC, ['OID@'], where) as cursor:
            count = sum(1 for _ in cursor)
        pct = (count / insert_count * 100) if insert_count > 0 else 0
        print(f"  {field}: {count:,} / {insert_count:,} ({pct:.1f}%)")

    # Show year-over-year MW stats
    print("\n" + "-" * 70)
    print("YEAR-OVER-YEAR MW FIELD POPULATION:")
    print("-" * 70)

    year_fields = ['mw_2023', 'mw_2024', 'mw_2025', 'mw_2026', 'mw_2027',
                   'mw_2028', 'mw_2029', 'mw_2030', 'mw_2031', 'mw_2032']

    for field in year_fields:
        where = f"source = '{SOURCE_NAME}' AND {field} IS NOT NULL AND {field} > 0"
        with arcpy.da.SearchCursor(TARGET_FC, [field], where) as cursor:
            values = [row[0] for row in cursor]
        count = len(values)
        pct = (count / insert_count * 100) if insert_count > 0 else 0
        total_mw = sum(values) if values else 0
        status = "[OK]" if pct > 5 else "[WARN]" if pct > 0 else "[LOW]"
        print(f"  {field}: {count:,} ({pct:>5.1f}%) | Total: {total_mw:>12,.0f} MW {status}")

    print("=" * 70)

    # Run full validation if available
    print("\n" + "=" * 70)
    print("RUNNING DATA VALIDATION...")
    print("=" * 70)

    try:
        from validate_sa_ingestion import validate_ingestion
        validation_results = validate_ingestion(SOURCE_CSV, print_output=True)

        if validation_results['status'] == 'FAIL':
            print("\n[ERROR] VALIDATION FAILED - Review issues above")
        elif validation_results['status'] == 'WARN':
            print("\n[WARN] VALIDATION PASSED WITH WARNINGS - Review issues above")
        else:
            print("\n[OK] VALIDATION PASSED - All checks OK")
    except ImportError:
        print("  (Validation module not available - run validate_sa_ingestion.py separately)")
    except Exception as e:
        print(f"  Validation error: {e}")

    print("\n" + "=" * 70)


# ====== EXECUTE ======
try:
    main()
except Exception as e:
    print(f"\nERROR: {str(e)}")
    import traceback
    traceback.print_exc()
