"""
WoodMac Data Center Ingestion Script (V2 - Feb 2025 Dataset)
Ingests WoodMackenzie DC site data with coordinates into gold_buildings_full.

WoodMac Feb 2025 dataset provides:
- 2,265 records (up from 999 in previous version)
- 96.7% geocoded (lat/lon coordinates available!)
- Global coverage: 17 countries (US, China, UK, Germany, Brazil, etc.)
- Rich status tracking and development timeline

Author: Meta Data Center GIS Team
Last Updated: 2026-02-12 (V2 - with coordinates)
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

# ============================================================================
# CONFIGURATION
# ============================================================================

SOURCE_CSV = r"C:\Users\ptanderson\Downloads\Pipeline_Ingestion\022025_WoodMac_DC_sites.csv"
TARGET_FC = GOLD_BUILDINGS
SOURCE_NAME = "WoodMac"

STATUS_MAP = {
    'Operational': 'Active',
    'Construction': 'Under Construction',
    'Disclosed': 'Announced',
    'Permitted': 'Announced',
    'Permitting': 'Announced',
    'Rezoning': 'Announced',
    'Land Acquired': 'Announced',
    'Cancelled': 'Cancelled',
    'Denied': 'Cancelled',
    'Withdrawn': 'Cancelled',
    'Unknown': 'Unknown',
}

DEVELOPER_MAP = {
    'amazon': 'AWS', 'aws': 'AWS',
    'microsoft': 'Microsoft',
    'google': 'Google',
    'meta': 'Meta', 'facebook': 'Meta',
    'apple': 'Apple',
    'oracle': 'Oracle',
    'alibaba': 'Alibaba',
    'tencent': 'Tencent',
}

SUPER_REGION_MAP = {
    'Americas': 'AMER', 'Europe': 'EMEA', 'Asia': 'APAC', 'Oceania': 'APAC',
}

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def delete_existing_records(target_fc, source_name):
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
    if val is None or val == '' or str(val).strip() in ['', 'nan', 'None', 'NaN', '-']:
        return None
    try:
        return float(str(val).replace(',', '').replace('$', '').strip())
    except (ValueError, TypeError):
        return None

def safe_str(val, max_len=None):
    if val is None or str(val).strip() in ['', 'nan', 'None', 'NaN']:
        return None
    s = str(val).strip()
    return s[:max_len] if max_len and len(s) > max_len else (s if s else None)

def parse_date(date_str):
    if not date_str or str(date_str).strip() in ['', 'nan', 'None', 'N/A', 'NaN']:
        return None
    try:
        date_str = str(date_str).strip()
        for fmt in ['%m/%d/%Y', '%Y-%m-%d', '%Y/%m/%d', '%d/%m/%Y', '%m/%Y', '%Y']:
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue
        return None
    except Exception:
        return None

def standardize_status(status):
    if not status:
        return 'Unknown'
    return STATUS_MAP.get(str(status).strip(), str(status).strip())

def get_region(super_region, country):
    if super_region:
        mapped = SUPER_REGION_MAP.get(str(super_region).strip())
        if mapped:
            return mapped
    return 'AMER'

def get_company_clean_filter(developer):
    if not developer:
        return 'Colo - All Other'
    developer_lower = str(developer).lower()
    for key, value in DEVELOPER_MAP.items():
        if key in developer_lower:
            return value
    return 'Colo - All Other'

# ============================================================================
# MAIN INGESTION
# ============================================================================

def main():
    print("=" * 70)
    print(f"WOODMAC V2 INGESTION STARTED: {datetime.now()}")
    print("=" * 70)
    print(f"Source CSV: {SOURCE_CSV}")
    print(f"Target FC: {TARGET_FC}")

    if not os.path.exists(SOURCE_CSV):
        raise Exception(f"Source CSV not found: {SOURCE_CSV}")

    delete_existing_records(TARGET_FC, SOURCE_NAME)

    insert_fields = [
        'SHAPE@XY', 'unique_id', 'source', 'source_unique_id', 'date_reported',
        'record_level', 'campus_id', 'campus_name', 'company_source', 'company_clean',
        'company_clean_filter', 'building_designation', 'address', 'postal_code',
        'city', 'market', 'state', 'state_abbr', 'county', 'country', 'region',
        'latitude', 'longitude', 'planned_power_mw', 'uc_power_mw',
        'commissioned_power_mw', 'full_capacity_mw', 'pue', 'actual_live_date',
        'construction_start_date', 'facility_status', 'cancelled', 'facility_sqft',
        'type_category', 'data_vintage', 'ingest_date',
        # NEW FIELDS (WoodMac-specific)
        'workload_type',             # AI, Cloud, Colo, HPC, etc.
        'cooling_type',              # air, liquid, hybrid, etc.
        'energy_source',             # Energy supply info
        'finance_partner',           # Investment/JV partner
        'disclosed_date',            # When project was first announced
        'land_acquisition_date',     # Land secured milestone
        'permitting_date',           # Permits approved milestone
        'cancelled_date',            # When project was cancelled
        'total_site_acres',          # Total site acreage
        'dc_acres',                  # Data center footprint acres
        'land_cost_usd_million',     # Land cost
        'development_cost_usd_million',  # Development cost
        'grid_zone',                 # Power grid zone
        'status_detail',             # Original granular status from WoodMac
    ]

    insert_count = 0
    skip_count = 0
    no_coords_count = 0

    print("\nReading CSV file...")
    with open(SOURCE_CSV, 'r', encoding='utf-8') as csvfile:
        rows = list(csv.DictReader(csvfile))

    print(f"Total CSV records: {len(rows):,}")
    print("\nProcessing records...")

    data_vintage_date = datetime.now()

    with arcpy.da.InsertCursor(TARGET_FC, insert_fields) as cursor:
        for idx, row in enumerate(rows, 1):
            site_id = safe_str(row.get('id_site'))
            site_name = safe_str(row.get('site_name'), 255)
            project_name = safe_str(row.get('project_name'), 255)
            developer = safe_str(row.get('developer_name'), 100)
            workload = safe_str(row.get('workload'), 100)
            status = safe_str(row.get('status'))

            lat = safe_float(row.get('latitude'))
            lon = safe_float(row.get('longitude'))
            country = safe_str(row.get('country_name'), 100)
            state = safe_str(row.get('state_province_name'), 100)
            county = safe_str(row.get('county_district_name'), 100)
            market_name = safe_str(row.get('market_name'), 100)
            super_region = safe_str(row.get('super_region'))

            existing_mw = safe_float(row.get('existing_capacity__mw'))
            dev_mw = safe_float(row.get('development_capacity__mw'))
            planned_mw = safe_float(row.get('planned_capacity__mw'))

            construction_date = row.get('construction_date')
            cod_date = row.get('commercial_operation_date')
            forecast_cod = row.get('forecast_commercial_operation_date')
            pub_date = row.get('publication_date')

            # NEW FIELDS extraction
            cooling = safe_str(row.get('cooling'), 50)
            energy_supply = safe_str(row.get('energy_supply'), 100)
            finance_partner = safe_str(row.get('finance_partner'), 100)
            disclosed_date = parse_date(row.get('disclosed_date'))
            land_acq_date = parse_date(row.get('land_acquisition_date'))
            permitting_date = parse_date(row.get('permitting_date'))
            cancelled_date_val = parse_date(row.get('cancelled_date'))
            total_site_acres = safe_float(row.get('total_site_acres'))
            dc_acres = safe_float(row.get('data_center_acres'))
            land_cost = safe_float(row.get('land_cost_usd_million'))
            dev_cost = safe_float(row.get('development_overall_cost_usd_million'))
            zone_name = safe_str(row.get('zone_name'), 100)
            original_status = status  # Keep original status as status_detail

            unique_id = f"WDMAC_{site_id}" if site_id else f"WDMAC_{idx}"
            facility_status = standardize_status(status)
            region = get_region(super_region, country)
            company_clean_filter = get_company_clean_filter(developer)

            if lat is not None and lon is not None:
                record_level = 'Building'
                point = (lon, lat)
            else:
                record_level = 'WoodMac_Project'
                point = None
                no_coords_count += 1

            if facility_status == 'Active':
                commissioned_mw = existing_mw or 0
                uc_mw = dev_mw or 0
                planned_power_mw = planned_mw or 0
            elif facility_status == 'Under Construction':
                commissioned_mw = existing_mw or 0
                uc_mw = dev_mw or 0
                planned_power_mw = planned_mw or 0
            else:
                commissioned_mw = existing_mw or 0
                uc_mw = 0
                planned_power_mw = (dev_mw or 0) + (planned_mw or 0)

            full_capacity_mw = (existing_mw or 0) + (dev_mw or 0) + (planned_mw or 0)
            if full_capacity_mw == 0:
                full_capacity_mw = None

            cancelled = 1 if facility_status == 'Cancelled' else 0
            construction_start = parse_date(construction_date)
            actual_live = parse_date(cod_date) or parse_date(forecast_cod)
            if pub_date:
                dv = parse_date(pub_date)
                if dv:
                    data_vintage_date = dv

            campus_name = site_name or project_name
            if not campus_name and not developer and full_capacity_mw is None:
                skip_count += 1
                continue

            try:
                cursor.insertRow([
                    point, unique_id, SOURCE_NAME, site_id, None,
                    record_level, None, campus_name, developer, developer,
                    company_clean_filter, project_name or campus_name, None, None,
                    None, market_name, state, None, county, country, region,
                    lat, lon, planned_power_mw, uc_mw,
                    commissioned_mw, full_capacity_mw, None, actual_live,
                    construction_start, facility_status, cancelled, None,
                    workload, data_vintage_date, datetime.now(),
                    # NEW FIELDS
                    workload,                # workload_type (AI, Cloud, Colo, etc.)
                    cooling,                 # cooling_type
                    energy_supply,           # energy_source
                    finance_partner,         # finance_partner
                    disclosed_date,          # disclosed_date
                    land_acq_date,           # land_acquisition_date
                    permitting_date,         # permitting_date
                    cancelled_date_val,      # cancelled_date
                    total_site_acres,        # total_site_acres
                    dc_acres,                # dc_acres
                    land_cost,               # land_cost_usd_million
                    dev_cost,                # development_cost_usd_million
                    zone_name,               # grid_zone
                    original_status,         # status_detail (original WoodMac status)
                ])
                insert_count += 1
            except Exception as e:
                print(f"  Error inserting record {idx}: {e}")
                skip_count += 1
                continue

            if insert_count % 500 == 0:
                print(f"  Processed {insert_count:,} records...")

    print("\n" + "=" * 70)
    print("WOODMAC V2 INGESTION COMPLETE")
    print("=" * 70)
    print(f"Inserted: {insert_count:,} records")
    print(f"Skipped: {skip_count:,} records")
    print(f"With Coordinates: {insert_count - no_coords_count:,}")
    print(f"Without Coordinates: {no_coords_count:,}")
    print(f"Completed: {datetime.now()}")

    # Summary stats
    print("\n" + "-" * 70)
    print("SUMMARY STATISTICS:")
    print("-" * 70)

    status_counts = {}
    with arcpy.da.SearchCursor(TARGET_FC, ['facility_status'], f"source = '{SOURCE_NAME}'") as cur:
        for r in cur:
            s = r[0] or 'Unknown'
            status_counts[s] = status_counts.get(s, 0) + 1
    print("\nStatus Distribution:")
    for status, count in sorted(status_counts.items(), key=lambda x: -x[1]):
        print(f"  {status}: {count:,}")

    total_capacity = 0
    with arcpy.da.SearchCursor(TARGET_FC, ['full_capacity_mw'], f"source = '{SOURCE_NAME}'") as cur:
        for r in cur:
            if r[0]:
                total_capacity += r[0]
    print(f"\nTotal Capacity: {total_capacity:,.0f} MW")
    print("=" * 70)


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
