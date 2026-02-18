"""
Orennia Data Center Ingestion Script
Ingests Orennia data center records from CSV into gold_buildings_full feature class.

Orennia provides comprehensive data center facility data with:
- 3,575 records (Feb 2026 vintage)
- High coordinate coverage (~100% geocoded)
- Power capacity, status, owner type
- US-centric with detailed state/county coverage

Schema Summary:
- Name: Facility name
- Data Center ID: Source unique identifier (or:data_center:NNNN format)
- Data Center Status: Operating, Under Construction, etc.
- State: US state abbreviation
- County: County name
- Owner: Company name
- Construction Date: Construction start date
- Country: Country name
- Detailed Status: Extended status detail
- First Power Date: Operational date
- Owner Type: Hyperscaler, Colocation, Enterprise
- Power Capacity (MW): Total power capacity in MW
- Reported First Power Date: Published operational date
- Square Footage (Sq Ft): Facility size
- Transmission Owner: Utility/grid operator
- Power Source: Actual or estimated
- Latitude (Degrees): Latitude
- Longitude (Degrees): Longitude

Author: Meta Data Center GIS Team
Last Updated: 2026-02-12
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

# Try to import SOURCE_CSV_FILES, but use fallback if not available (module caching issue)
try:
    from config import SOURCE_CSV_FILES
except ImportError:
    SOURCE_CSV_FILES = {}

# ============================================================================
# CONFIGURATION
# ============================================================================

# Default path - use SOURCE_CSV_FILES if available, otherwise use direct path
SOURCE_CSV = SOURCE_CSV_FILES.get('orennia',
    r"C:\Users\ptanderson\Downloads\Pipeline_Ingestion\Orennia - Data Centers-2026-02-02.csv")

TARGET_FC = GOLD_BUILDINGS
SOURCE_NAME = "Orennia"

# Status mapping - Orennia status to Gold status
STATUS_MAP = {
    'Operating': 'Active',
    'Under Construction': 'Under Construction',
    'Planned': 'Announced',
    'Proposed': 'Announced',
    'Cancelled': 'Cancelled',
    'On Hold': 'On Hold',
    'Decommissioned': 'Decommissioned',
}

# Owner Type mapping - used for company_clean_filter
OWNER_TYPE_MAP = {
    'Hyperscaler': 'Hyperscaler',
    'Colocation': 'Colo - All Other',
    'Enterprise': 'Enterprise',
    'Wholesale': 'Colo - All Other',
}

# Region mapping by country
COUNTRY_TO_REGION = {
    'United States': 'AMER', 'USA': 'AMER', 'Canada': 'AMER', 'Mexico': 'AMER',
    'Brazil': 'AMER', 'Chile': 'AMER', 'Colombia': 'AMER', 'Argentina': 'AMER',
    'United Kingdom': 'EMEA', 'UK': 'EMEA', 'Ireland': 'EMEA', 'Germany': 'EMEA',
    'France': 'EMEA', 'Netherlands': 'EMEA', 'Sweden': 'EMEA', 'Denmark': 'EMEA',
    'Finland': 'EMEA', 'Norway': 'EMEA', 'Spain': 'EMEA', 'Italy': 'EMEA',
    'Singapore': 'APAC', 'Japan': 'APAC', 'Australia': 'APAC', 'India': 'APAC',
    'Indonesia': 'APAC', 'Malaysia': 'APAC', 'Taiwan': 'APAC', 'South Korea': 'APAC',
    'China': 'APAC', 'Hong Kong': 'APAC', 'Thailand': 'APAC', 'Vietnam': 'APAC',
}

# Hyperscaler company detection (for company_clean_filter)
HYPERSCALER_KEYWORDS = [
    'amazon', 'aws', 'microsoft', 'azure', 'google', 'gcp', 'meta', 'facebook',
    'apple', 'oracle', 'alibaba', 'tencent', 'ibm cloud', 'bytedance',
    'xai', 'openai', 'anthropic', 'coreweave', 'crusoe'
]


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
        return float(str(val).replace(',', ''))
    except (ValueError, TypeError):
        return None


def safe_str(val, max_len=None):
    """Safely convert to string and optionally truncate."""
    if val is None or str(val).strip() in ['', 'nan', 'None']:
        return None
    s = str(val).strip()
    if max_len and len(s) > max_len:
        return s[:max_len]
    return s if s else None


def parse_date(date_str):
    """Parse date string to datetime object."""
    if not date_str or str(date_str).strip() in ['', 'nan', 'None']:
        return None
    try:
        # Try common formats
        for fmt in ['%Y-%m-%d', '%m/%d/%Y', '%Y/%m/%d', '%d/%m/%Y', '%Y']:
            try:
                return datetime.strptime(str(date_str).strip(), fmt)
            except ValueError:
                continue
        return None
    except Exception:
        return None


def standardize_status(status):
    """Standardize status value to gold schema."""
    if not status:
        return 'Unknown'
    status_clean = str(status).strip()
    return STATUS_MAP.get(status_clean, status_clean)


def get_region(country):
    """Get region from country."""
    if not country:
        return None
    return COUNTRY_TO_REGION.get(str(country).strip(), None)


def is_hyperscaler(company):
    """Detect if company is a hyperscaler for tier grouping."""
    if not company:
        return False
    company_lower = str(company).lower()
    return any(kw in company_lower for kw in HYPERSCALER_KEYWORDS)


def get_company_clean_filter(company, owner_type):
    """Determine company_clean_filter tier grouping."""
    if not company:
        return OWNER_TYPE_MAP.get(owner_type, 'Colo - All Other')

    company_lower = str(company).lower()

    # Check for specific hyperscalers
    if 'amazon' in company_lower or 'aws' in company_lower:
        return 'AWS'
    elif 'microsoft' in company_lower or 'azure' in company_lower:
        return 'Microsoft'
    elif 'google' in company_lower or 'gcp' in company_lower:
        return 'Google'
    elif 'meta' in company_lower or 'facebook' in company_lower:
        return 'Meta'
    elif 'apple' in company_lower:
        return 'Apple'
    elif 'oracle' in company_lower:
        return 'Oracle'
    elif 'alibaba' in company_lower:
        return 'Alibaba'
    elif 'xai' in company_lower:
        return 'xAI'
    elif 'openai' in company_lower:
        return 'OpenAI'
    elif 'anthropic' in company_lower:
        return 'Anthropic'
    elif 'bytedance' in company_lower:
        return 'ByteDance'
    elif 'coreweave' in company_lower:
        return 'CoreWeave'
    elif 'crusoe' in company_lower:
        return 'Crusoe'
    elif 'ibm' in company_lower:
        return 'IBM'

    # Fall back to owner type mapping
    return OWNER_TYPE_MAP.get(owner_type, 'Colo - All Other')


def generate_unique_id(dc_id, idx):
    """Generate unique_id for gold_buildings."""
    if dc_id:
        # Extract numeric part from or:data_center:NNNN format
        clean_id = str(dc_id).replace('or:data_center:', '').replace(':', '_')
        return f"OREN_{clean_id}"
    return f"OREN_{idx}"


# ============================================================================
# MAIN INGESTION
# ============================================================================

def main():
    print("=" * 70)
    print(f"ORENNIA INGESTION STARTED: {datetime.now()}")
    print("=" * 70)
    print(f"Source CSV: {SOURCE_CSV}")
    print(f"Target FC: {TARGET_FC}")

    # Verify source exists
    if not os.path.exists(SOURCE_CSV):
        raise Exception(f"Source CSV not found: {SOURCE_CSV}")

    # Delete existing records from this source
    delete_existing_records(TARGET_FC, SOURCE_NAME)

    # Target insert fields (matching gold_buildings schema)
    # NEW FIELDS ADDED: transmission_owner, power_source_confidence, status_detail
    insert_fields = [
        'SHAPE@XY', 'unique_id', 'source', 'source_unique_id', 'date_reported',
        'record_level', 'campus_id', 'campus_name', 'company_source', 'company_clean',
        'company_clean_filter', 'building_designation', 'address', 'postal_code',
        'city', 'market', 'state', 'state_abbr', 'county', 'country', 'region',
        'latitude', 'longitude', 'planned_power_mw', 'uc_power_mw',
        'commissioned_power_mw', 'full_capacity_mw', 'pue', 'actual_live_date',
        'construction_start_date', 'facility_status', 'cancelled', 'facility_sqft',
        'type_category', 'data_vintage', 'ingest_date',
        # NEW FIELDS (Orennia-specific)
        'transmission_owner',        # Grid operator / utility (e.g., ERCOT, PJM, Dominion)
        'power_source_confidence',   # "Actual" or "Estimated" - data quality indicator
        'status_detail',             # More granular status from Orennia
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

    # Data vintage from filename (2026-02-02)
    data_vintage_date = datetime(2026, 2, 2)

    with arcpy.da.InsertCursor(TARGET_FC, insert_fields) as insert_cursor:
        for idx, row in enumerate(rows, 1):
            # Extract values from CSV
            dc_id = safe_str(row.get('Data Center ID'))
            name = safe_str(row.get('Name'), 255)
            status = safe_str(row.get('Data Center Status'))
            detailed_status = safe_str(row.get('Detailed Status'))
            state_abbr = safe_str(row.get('State'), 10)
            county = safe_str(row.get('County'), 100)
            owner = safe_str(row.get('Owner'), 100)
            owner_type = safe_str(row.get('Owner Type'), 50)
            country = safe_str(row.get('Country'), 100)
            construction_date = row.get('Construction Date')
            first_power_date = row.get('First Power Date')
            reported_first_power = row.get('Reported First Power Date')
            power_mw = safe_float(row.get('Power Capacity (MW)'))
            sqft = safe_float(row.get('Square Footage (Sq Ft)'))
            transmission_owner = safe_str(row.get('Transmission Owner'), 100)
            power_source = safe_str(row.get('Power Source'), 50)
            lat = safe_float(row.get('Latitude (Degrees)'))
            lon = safe_float(row.get('Longitude (Degrees)'))

            # Skip if missing coordinates
            if lat is None or lon is None:
                skip_count += 1
                continue

            # Derive fields
            unique_id = generate_unique_id(dc_id, idx)
            facility_status = standardize_status(status)
            region = get_region(country)
            company_clean = owner  # Use owner as company_clean
            company_clean_filter = get_company_clean_filter(owner, owner_type)

            # Parse dates
            construction_start = parse_date(construction_date)
            actual_live = parse_date(first_power_date) or parse_date(reported_first_power)

            # Capacity assignment based on status
            if facility_status == 'Active':
                commissioned_mw = power_mw or 0
                uc_mw = 0
                planned_mw = 0
            elif facility_status == 'Under Construction':
                commissioned_mw = 0
                uc_mw = power_mw or 0
                planned_mw = 0
            else:  # Announced, Planned, etc.
                commissioned_mw = 0
                uc_mw = 0
                planned_mw = power_mw or 0

            full_capacity_mw = power_mw or (commissioned_mw + uc_mw + planned_mw)

            # Cancelled flag
            cancelled = 1 if facility_status == 'Cancelled' else 0

            # Type category from owner type
            type_category = owner_type

            # Geometry
            point = (lon, lat)

            # Insert row
            insert_cursor.insertRow([
                point,                          # SHAPE@XY
                unique_id,                      # unique_id
                SOURCE_NAME,                    # source
                dc_id,                          # source_unique_id
                None,                           # date_reported
                'Building',                     # record_level
                None,                           # campus_id (generated later by UCID script)
                name,                           # campus_name
                owner,                          # company_source
                company_clean,                  # company_clean
                company_clean_filter,           # company_clean_filter
                name,                           # building_designation
                None,                           # address
                None,                           # postal_code
                None,                           # city (not in Orennia - use name parsing if needed)
                None,                           # market (leave empty, transmission_owner is separate)
                None,                           # state (full name not available)
                state_abbr,                     # state_abbr
                county,                         # county
                country,                        # country
                region,                         # region
                lat,                            # latitude
                lon,                            # longitude
                planned_mw,                     # planned_power_mw
                uc_mw,                          # uc_power_mw
                commissioned_mw,                # commissioned_power_mw
                full_capacity_mw,               # full_capacity_mw
                None,                           # pue
                actual_live,                    # actual_live_date
                construction_start,             # construction_start_date
                facility_status,                # facility_status
                cancelled,                      # cancelled
                sqft,                           # facility_sqft
                type_category,                  # type_category
                data_vintage_date,              # data_vintage
                datetime.now(),                 # ingest_date
                # NEW FIELDS
                transmission_owner,             # transmission_owner (grid operator/utility)
                power_source,                   # power_source_confidence ("Actual" or "Estimated")
                detailed_status,                # status_detail (granular status from Orennia)
            ])

            insert_count += 1

            if insert_count % 500 == 0:
                print(f"  Processed {insert_count:,} records...")

    print("\n" + "=" * 70)
    print("ORENNIA INGESTION COMPLETE")
    print("=" * 70)
    print(f"Inserted: {insert_count:,} records")
    print(f"Skipped: {skip_count:,} records (missing lat/lon)")
    print(f"Completed: {datetime.now()}")

    # Show summary statistics
    print("\n" + "-" * 70)
    print("SUMMARY STATISTICS:")
    print("-" * 70)

    # Status distribution
    print("\nStatus Distribution:")
    status_counts = {}
    with arcpy.da.SearchCursor(TARGET_FC, ['facility_status'],
                               f"source = '{SOURCE_NAME}'") as cursor:
        for r in cursor:
            s = r[0] or 'Unknown'
            status_counts[s] = status_counts.get(s, 0) + 1
    for status, count in sorted(status_counts.items(), key=lambda x: -x[1]):
        print(f"  {status}: {count:,}")

    # Owner Type distribution
    print("\nOwner Type (company_clean_filter) Distribution:")
    owner_counts = {}
    with arcpy.da.SearchCursor(TARGET_FC, ['company_clean_filter'],
                               f"source = '{SOURCE_NAME}'") as cursor:
        for r in cursor:
            o = r[0] or 'Unknown'
            owner_counts[o] = owner_counts.get(o, 0) + 1
    for owner, count in sorted(owner_counts.items(), key=lambda x: -x[1])[:15]:
        print(f"  {owner}: {count:,}")

    # Total capacity
    total_capacity = 0
    with arcpy.da.SearchCursor(TARGET_FC, ['full_capacity_mw'],
                               f"source = '{SOURCE_NAME}'") as cursor:
        for r in cursor:
            if r[0]:
                total_capacity += r[0]
    print(f"\nTotal Capacity: {total_capacity:,.0f} MW")

    print("=" * 70)


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
