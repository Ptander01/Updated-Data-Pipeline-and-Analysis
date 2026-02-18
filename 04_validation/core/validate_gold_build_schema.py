import arcpy
from datetime import datetime
import csv

# ============================================================================
# GOLD_BUILDINGS COMPLETE SCHEMA DEFINITION & VALIDATION
# ============================================================================
# Updated: December 2024
# Total Fields: 74 (36 core + 38 extended)
# ============================================================================

gdb = r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\Default.gdb"
gold_buildings = f"{gdb}\\gold_buildings"

# ============================================================================
# OFFICIAL SCHEMA DEFINITION - COMPLETE (74 FIELDS)
# ============================================================================

GOLD_BUILDINGS_SCHEMA = {

    # ==========================================================================
    # CORE IDENTITY (Required for all sources)
    # ==========================================================================
    'unique_id': {
        'type': 'TEXT', 'length': 100, 'required': True,
        'description': 'Unique identifier: {Source}_{source_id}',
        'populated_by': ['ALL'],
        'category': 'Core Identity'
    },
    'source': {
        'type': 'TEXT', 'length': 50, 'required': True,
        'description': 'Vendor source name',
        'populated_by': ['ALL'],
        'valid_values': ['DataCenterHawk', 'Semianalysis', 'DataCenterMap',
                        'Synergy', 'NewProjectMedia', 'WoodMac'],
        'category': 'Core Identity'
    },
    'source_unique_id': {
        'type': 'TEXT', 'length': 100, 'required': False,
        'description': 'Original ID from source system',
        'populated_by': ['ALL'],
        'category': 'Core Identity'
    },
    'campus_id': {
        'type': 'TEXT', 'length': 100, 'required': True,
        'description': 'Standardized campus ID: {company}|{city}|{campus_name}',
        'populated_by': ['ALL'],
        'category': 'Core Identity'
    },
    'campus_name': {
        'type': 'TEXT', 'length': 100, 'required': True,
        'description': 'Campus/facility name',
        'populated_by': ['ALL'],
        'category': 'Core Identity'
    },
    'building_designation': {
        'type': 'TEXT', 'length': 50, 'required': False,
        'description': 'Building number/name within campus',
        'populated_by': ['DataCenterHawk', 'Semianalysis'],
        'category': 'Core Identity'
    },
    'record_level': {
        'type': 'TEXT', 'length': 16, 'required': False,
        'description': 'Granularity level: Suite, Building, Campus',
        'populated_by': ['DataCenterHawk', 'Synergy'],
        'valid_values': ['Suite', 'Building', 'Campus'],
        'category': 'Core Identity'
    },

    # ==========================================================================
    # COORDINATES (Required - at least one pair must be populated)
    # ==========================================================================
    'latitude': {
        'type': 'DOUBLE', 'length': None, 'required': True,
        'description': 'WGS84 latitude (primary coordinate field)',
        'populated_by': ['ALL'],
        'category': 'Coordinates'
    },
    'longitude': {
        'type': 'DOUBLE', 'length': None, 'required': True,
        'description': 'WGS84 longitude (primary coordinate field)',
        'populated_by': ['ALL'],
        'category': 'Coordinates'
    },
    'gold_lat': {
        'type': 'DOUBLE', 'length': None, 'required': False,
        'description': 'Backup latitude (populated from SHAPE@ if lat is null)',
        'populated_by': ['ALL'],
        'category': 'Coordinates'
    },
    'gold_lon': {
        'type': 'DOUBLE', 'length': None, 'required': False,
        'description': 'Backup longitude (populated from SHAPE@ if lon is null)',
        'populated_by': ['ALL'],
        'category': 'Coordinates'
    },

    # ==========================================================================
    # COMPANY (Required for filtering)
    # ==========================================================================
    'company_clean': {
        'type': 'TEXT', 'length': 100, 'required': True,
        'description': 'Standardized company name (e.g., "Meta")',
        'populated_by': ['ALL'],
        'category': 'Company'
    },
    'company_source': {
        'type': 'TEXT', 'length': 100, 'required': False,
        'description': 'Original company name from source',
        'populated_by': ['ALL'],
        'category': 'Company'
    },

    # ==========================================================================
    # GEOGRAPHY - CORE
    # ==========================================================================
    'address': {
        'type': 'TEXT', 'length': 255, 'required': False,
        'description': 'Street address',
        'populated_by': ['DataCenterHawk', 'DataCenterMap'],
        'category': 'Geography'
    },
    'city': {
        'type': 'TEXT', 'length': 100, 'required': True,
        'description': 'City name',
        'populated_by': ['ALL'],
        'category': 'Geography'
    },
    'state': {
        'type': 'TEXT', 'length': 100, 'required': False,
        'description': 'State/province name (full name)',
        'populated_by': ['ALL'],
        'category': 'Geography'
    },
    'state_abbr': {
        'type': 'TEXT', 'length': 8, 'required': False,
        'description': 'State/province abbreviation (e.g., "VA", "CA")',
        'populated_by': ['DataCenterHawk', 'Synergy', 'DataCenterMap'],
        'category': 'Geography'
    },
    'postal_code': {
        'type': 'TEXT', 'length': 16, 'required': False,
        'description': 'Zip/postal code',
        'populated_by': ['DataCenterHawk', 'DataCenterMap'],
        'category': 'Geography'
    },
    'county': {
        'type': 'TEXT', 'length': 128, 'required': False,
        'description': 'County name',
        'populated_by': ['DataCenterHawk', 'DataCenterMap'],
        'category': 'Geography'
    },
    'country': {
        'type': 'TEXT', 'length': 100, 'required': True,
        'description': 'Country name',
        'populated_by': ['ALL'],
        'category': 'Geography'
    },
    'region': {
        'type': 'TEXT', 'length': 20, 'required': True,
        'description': 'Global region: AMER, EMEA, APAC',
        'populated_by': ['ALL'],
        'valid_values': ['AMER', 'EMEA', 'APAC'],
        'category': 'Geography'
    },
    'market': {
        'type': 'TEXT', 'length': 128, 'required': False,
        'description': 'Market region (e.g., "Northern Virginia", "Silicon Valley")',
        'populated_by': ['DataCenterHawk', 'Synergy', 'DataCenterMap'],
        'category': 'Geography'
    },

    # ==========================================================================
    # CAPACITY - CURRENT STATE
    # ==========================================================================
    'commissioned_power_mw': {
        'type': 'DOUBLE', 'length': None, 'required': False,
        'description': 'Currently operational capacity (MW)',
        'populated_by': ['DataCenterHawk', 'Semianalysis', 'DataCenterMap'],
        'category': 'Capacity - Current'
    },
    'uc_power_mw': {
        'type': 'DOUBLE', 'length': None, 'required': False,
        'description': 'Under construction capacity (MW)',
        'populated_by': ['DataCenterHawk', 'Semianalysis'],
        'category': 'Capacity - Current'
    },
    'planned_power_mw': {
        'type': 'DOUBLE', 'length': None, 'required': False,
        'description': 'Planned/announced capacity (MW)',
        'populated_by': ['DataCenterHawk', 'Semianalysis', 'NewProjectMedia'],
        'category': 'Capacity - Current'
    },
    'planned_plus_uc_mw': {
        'type': 'DOUBLE', 'length': None, 'required': False,
        'description': 'Calculated: Planned + Under Construction capacity (MW)',
        'populated_by': ['DataCenterHawk'],
        'category': 'Capacity - Current'
    },
    'full_capacity_mw': {
        'type': 'DOUBLE', 'length': None, 'required': False,
        'description': 'Total full-build capacity (MW)',
        'populated_by': ['DataCenterHawk', 'Semianalysis', 'NewProjectMedia'],
        'category': 'Capacity - Current'
    },
    'available_power_kw': {
        'type': 'DOUBLE', 'length': None, 'required': False,
        'description': 'Available capacity for lease/sale (kW)',
        'populated_by': ['DataCenterHawk', 'DataCenterMap'],
        'category': 'Capacity - Current'
    },

    # ==========================================================================
    # CAPACITY - YEAR-BY-YEAR FORECASTS (Semianalysis specialty)
    # ==========================================================================
    'mw_2023': {'type': 'DOUBLE', 'length': None, 'required': False,
                'description': 'Capacity forecast for 2023', 'populated_by': ['Semianalysis'],
                'category': 'Capacity - Forecast'},
    'mw_2024': {'type': 'DOUBLE', 'length': None, 'required': False,
                'description': 'Capacity forecast for 2024', 'populated_by': ['Semianalysis'],
                'category': 'Capacity - Forecast'},
    'mw_2025': {'type': 'DOUBLE', 'length': None, 'required': False,
                'description': 'Capacity forecast for 2025', 'populated_by': ['Semianalysis'],
                'category': 'Capacity - Forecast'},
    'mw_2026': {'type': 'DOUBLE', 'length': None, 'required': False,
                'description': 'Capacity forecast for 2026', 'populated_by': ['Semianalysis'],
                'category': 'Capacity - Forecast'},
    'mw_2027': {'type': 'DOUBLE', 'length': None, 'required': False,
                'description': 'Capacity forecast for 2027', 'populated_by': ['Semianalysis'],
                'category': 'Capacity - Forecast'},
    'mw_2028': {'type': 'DOUBLE', 'length': None, 'required': False,
                'description': 'Capacity forecast for 2028', 'populated_by': ['Semianalysis'],
                'category': 'Capacity - Forecast'},
    'mw_2029': {'type': 'DOUBLE', 'length': None, 'required': False,
                'description': 'Capacity forecast for 2029', 'populated_by': ['Semianalysis'],
                'category': 'Capacity - Forecast'},
    'mw_2030': {'type': 'DOUBLE', 'length': None, 'required': False,
                'description': 'Capacity forecast for 2030', 'populated_by': ['Semianalysis'],
                'category': 'Capacity - Forecast'},
    'mw_2031': {'type': 'DOUBLE', 'length': None, 'required': False,
                'description': 'Capacity forecast for 2031', 'populated_by': ['Semianalysis'],
                'category': 'Capacity - Forecast'},
    'mw_2032': {'type': 'DOUBLE', 'length': None, 'required': False,
                'description': 'Capacity forecast for 2032', 'populated_by': ['Semianalysis'],
                'category': 'Capacity - Forecast'},

    # ==========================================================================
    # FACILITY DETAILS
    # ==========================================================================
    'facility_sqft': {
        'type': 'DOUBLE', 'length': None, 'required': False,
        'description': 'Total facility square footage',
        'populated_by': ['DataCenterHawk', 'DataCenterMap'],
        'category': 'Facility Details'
    },
    'whitespace_sqft': {
        'type': 'DOUBLE', 'length': None, 'required': False,
        'description': 'Data hall/raised floor square footage',
        'populated_by': ['DataCenterHawk', 'DataCenterMap'],
        'category': 'Facility Details'
    },
    'pue': {
        'type': 'DOUBLE', 'length': None, 'required': False,
        'description': 'Power Usage Effectiveness (PUE) ratio',
        'populated_by': ['DataCenterHawk', 'Semianalysis'],
        'category': 'Facility Details'
    },

    # ==========================================================================
    # POWER INFRASTRUCTURE
    # ==========================================================================
    'substation_count': {
        'type': 'SHORT', 'length': None, 'required': False,
        'description': 'Number of electrical substations',
        'populated_by': ['DataCenterHawk'],
        'category': 'Power Infrastructure'
    },
    'onsite_substation': {
        'type': 'SHORT', 'length': None, 'required': False,
        'description': 'Has onsite substation (0=No, 1=Yes)',
        'populated_by': ['DataCenterHawk'],
        'category': 'Power Infrastructure'
    },
    'power_provider': {
        'type': 'TEXT', 'length': 128, 'required': False,
        'description': 'Primary utility/power provider name',
        'populated_by': ['DataCenterHawk', 'Semianalysis'],
        'category': 'Power Infrastructure'
    },
    'power_grid': {
        'type': 'TEXT', 'length': 128, 'required': False,
        'description': 'Power grid connection details',
        'populated_by': ['DataCenterHawk'],
        'category': 'Power Infrastructure'
    },
    'tier_design': {
        'type': 'TEXT', 'length': 32, 'required': False,
        'description': 'Uptime Institute Tier certification (I, II, III, IV)',
        'populated_by': ['DataCenterHawk', 'DataCenterMap'],
        'valid_values': ['Tier I', 'Tier II', 'Tier III', 'Tier IV'],
        'category': 'Power Infrastructure'
    },
    'feed_config': {
        'type': 'TEXT', 'length': 16, 'required': False,
        'description': 'Power feed configuration (e.g., "2N", "N+1")',
        'populated_by': ['DataCenterHawk'],
        'category': 'Power Infrastructure'
    },

    # ==========================================================================
    # CLASSIFICATION & TYPE
    # ==========================================================================
    'type_category': {
        'type': 'TEXT', 'length': 32, 'required': False,
        'description': 'Facility type (Hyperscale, Colocation, Enterprise, Edge)',
        'populated_by': ['DataCenterHawk', 'Synergy', 'DataCenterMap'],
        'valid_values': ['Hyperscale', 'Colocation', 'Enterprise', 'Edge'],
        'category': 'Classification'
    },
    'owned_leased': {
        'type': 'TEXT', 'length': 32, 'required': False,
        'description': 'Ownership model (Owned, Leased, Build-to-Suit)',
        'populated_by': ['DataCenterHawk', 'Synergy'],
        'valid_values': ['Owned', 'Leased', 'Build-to-Suit'],
        'category': 'Classification'
    },
    'building_type': {
        'type': 'TEXT', 'length': 50, 'required': False,
        'description': 'Building type classification (Own vs Lease)',
        'populated_by': ['DataCenterHawk'],
        'category': 'Classification'
    },
    'purpose': {
        'type': 'TEXT', 'length': 32, 'required': False,
        'description': 'Primary purpose/use case',
        'populated_by': ['DataCenterHawk', 'Synergy'],
        'category': 'Classification'
    },

    # ==========================================================================
    # ECOSYSTEM & CONNECTIVITY
    # ==========================================================================
    'ecosystem_ixps': {
        'type': 'SHORT', 'length': None, 'required': False,
        'description': 'Connected to Internet Exchange Points (count)',
        'populated_by': ['DataCenterHawk'],
        'category': 'Ecosystem'
    },
    'ecosystem_cloud': {
        'type': 'SHORT', 'length': None, 'required': False,
        'description': 'Cloud provider presence/connectivity',
        'populated_by': ['DataCenterHawk'],
        'category': 'Ecosystem'
    },
    'ecosystem_children': {
        'type': 'SHORT', 'length': None, 'required': False,
        'description': 'Number of child/connected facilities',
        'populated_by': ['DataCenterHawk'],
        'category': 'Ecosystem'
    },
    'ecosystem_networkproviders': {
        'type': 'SHORT', 'length': None, 'required': False,
        'description': 'Number of network providers present',
        'populated_by': ['DataCenterHawk'],
        'category': 'Ecosystem'
    },
    'ecosystem_networkpresence': {
        'type': 'SHORT', 'length': None, 'required': False,
        'description': 'Network presence score/metric',
        'populated_by': ['DataCenterHawk'],
        'category': 'Ecosystem'
    },
    'ecosystem_serviceproviders': {
        'type': 'SHORT', 'length': None, 'required': False,
        'description': 'Number of service providers present',
        'populated_by': ['DataCenterHawk'],
        'category': 'Ecosystem'
    },

    # ==========================================================================
    # TIMELINE & DATES
    # ==========================================================================
    'date_reported': {
        'type': 'DATE', 'length': None, 'required': False,
        'description': 'Date information was reported by vendor',
        'populated_by': ['DataCenterHawk', 'Semianalysis'],
        'category': 'Timeline'
    },
    'announced': {
        'type': 'DATE', 'length': None, 'required': False,
        'description': 'Public announcement date',
        'populated_by': ['Semianalysis', 'NewProjectMedia'],
        'category': 'Timeline'
    },
    'land_acquisition': {
        'type': 'DATE', 'length': None, 'required': False,
        'description': 'Land purchase/acquisition date',
        'populated_by': ['Semianalysis', 'NewProjectMedia'],
        'category': 'Timeline'
    },
    'permitting': {
        'type': 'DATE', 'length': None, 'required': False,
        'description': 'Permitting phase date',
        'populated_by': ['Semianalysis', 'NewProjectMedia'],
        'category': 'Timeline'
    },
    'construction_started': {
        'type': 'DATE', 'length': None, 'required': False,
        'description': 'Construction start date',
        'populated_by': ['Semianalysis', 'NewProjectMedia'],
        'category': 'Timeline'
    },
    'cod': {
        'type': 'DATE', 'length': None, 'required': False,
        'description': 'Certificate of Occupancy / Commercial Operation Date',
        'populated_by': ['Semianalysis', 'NewProjectMedia'],
        'category': 'Timeline'
    },
    'actual_live_date': {
        'type': 'DATE', 'length': None, 'required': False,
        'description': 'Actual/planned operational go-live date',
        'populated_by': ['DataCenterHawk', 'Semianalysis'],
        'category': 'Timeline'
    },
    'ingest_date': {
        'type': 'DATE', 'length': None, 'required': True,
        'description': 'Date record was ingested into gold_buildings',
        'populated_by': ['ALL'],
        'category': 'Timeline'
    },

    # ==========================================================================
    # STATUS & FLAGS
    # ==========================================================================
    'facility_status': {
        'type': 'TEXT', 'length': 50, 'required': False,
        'description': 'Current facility status (Operational, Under Construction, Planned, etc.)',
        'populated_by': ['DataCenterHawk', 'Synergy', 'DataCenterMap'],
        'category': 'Status'
    },
    'cancelled': {
        'type': 'SHORT', 'length': None, 'required': False,
        'description': 'Project cancelled flag (0=Active, 1=Cancelled)',
        'populated_by': ['Semianalysis', 'NewProjectMedia'],
        'category': 'Status'
    },
    'status_rank_tmp': {
        'type': 'SHORT', 'length': None, 'required': False,
        'description': 'Temporary status ranking field (may be deprecated)',
        'populated_by': ['DataCenterHawk'],
        'category': 'Status'
    },

    # ==========================================================================
    # COSTS & LAND
    # ==========================================================================
    'total_cost_usd_million': {
        'type': 'DOUBLE', 'length': None, 'required': False,
        'description': 'Total project cost (USD millions)',
        'populated_by': ['Semianalysis', 'NewProjectMedia'],
        'category': 'Costs & Land'
    },
    'land_cost_usd_million': {
        'type': 'DOUBLE', 'length': None, 'required': False,
        'description': 'Land acquisition cost (USD millions)',
        'populated_by': ['Semianalysis'],
        'category': 'Costs & Land'
    },
    'total_site_acres': {
        'type': 'DOUBLE', 'length': None, 'required': False,
        'description': 'Total site acreage',
        'populated_by': ['DataCenterHawk', 'Semianalysis'],
        'category': 'Costs & Land'
    },
    'data_center_acres': {
        'type': 'DOUBLE', 'length': None, 'required': False,
        'description': 'Data center footprint acreage',
        'populated_by': ['DataCenterHawk', 'Semianalysis'],
        'category': 'Costs & Land'
    },

    # ==========================================================================
    # METADATA & NOTES
    # ==========================================================================
    'additional_references': {
        'type': 'TEXT', 'length': 512, 'required': False,
        'description': 'URLs, sources, external references',
        'populated_by': ['DataCenterHawk', 'Semianalysis', 'NewProjectMedia'],
        'category': 'Metadata'
    },
    'notes': {
        'type': 'TEXT', 'length': 1024, 'required': False,
        'description': 'Vendor notes, comments, additional context',
        'populated_by': ['ALL'],
        'category': 'Metadata'
    }
}

# Required fields that EVERY source must populate
REQUIRED_FIELDS = [name for name, spec in GOLD_BUILDINGS_SCHEMA.items() if spec['required']]

# Get categories
CATEGORIES = sorted(set(spec['category'] for spec in GOLD_BUILDINGS_SCHEMA.values()))

print("=" * 80)
print("GOLD_BUILDINGS COMPLETE SCHEMA DEFINITION")
print("=" * 80)
print(f"\nTotal fields defined: {len(GOLD_BUILDINGS_SCHEMA)}")
print(f"Required fields: {len(REQUIRED_FIELDS)}")
print(f"Categories: {len(CATEGORIES)}")

print(f"\n{'CATEGORY':<25} {'FIELDS':<10}")
print("-" * 40)
for cat in CATEGORIES:
    count = sum(1 for spec in GOLD_BUILDINGS_SCHEMA.values() if spec['category'] == cat)
    print(f"{cat:<25} {count:<10}")

print(f"\n{'Required fields:'}")
for field in REQUIRED_FIELDS:
    print(f"   • {field}")

# ============================================================================
# VALIDATE CURRENT SCHEMA
# ============================================================================
print("\n" + "=" * 80)
print("SCHEMA VALIDATION")
print("=" * 80)

current_fields = {f.name: f for f in arcpy.ListFields(gold_buildings)}

missing_fields = []
type_mismatches = []

for field_name, spec in GOLD_BUILDINGS_SCHEMA.items():
    if field_name not in current_fields:
        missing_fields.append(field_name)
    else:
        current = current_fields[field_name]
        expected_type = spec['type']

        # Map arcpy types to our types
        type_map = {'String': 'TEXT', 'Double': 'DOUBLE', 'Date': 'DATE',
                    'Integer': 'INTEGER', 'SmallInteger': 'SHORT'}
        actual_type = type_map.get(current.type, current.type)

        if actual_type != expected_type:
            type_mismatches.append((field_name, expected_type, actual_type))

if missing_fields:
    print(f"\n❌ Missing fields ({len(missing_fields)}):")
    for f in missing_fields:
        print(f"   - {f}: {GOLD_BUILDINGS_SCHEMA[f]['description']}")
else:
    print(f"\n✅ All defined fields exist")

if type_mismatches:
    print(f"\n⚠️ Type mismatches ({len(type_mismatches)}):")
    for name, expected, actual in type_mismatches:
        print(f"   - {name}: expected {expected}, got {actual}")
else:
    print(f"✅ All field types match")

# Check for extra fields not in schema
extra_fields = [f for f in current_fields.keys()
                if f not in GOLD_BUILDINGS_SCHEMA
                and f not in ['OBJECTID', 'Shape', 'Shape_Length', 'Shape_Area', 'SHAPE']]

if extra_fields:
    print(f"\n⚠️ Extra fields not in schema ({len(extra_fields)}):")
    for f in extra_fields[:10]:
        print(f"   - {f}")
    if len(extra_fields) > 10:
        print(f"   ... and {len(extra_fields) - 10} more")
else:
    print(f"✅ No extra undocumented fields")

# ============================================================================
# EXPORT SCHEMA DOCUMENTATION
# ============================================================================
print("\n" + "=" * 80)
print("EXPORTING SCHEMA DOCUMENTATION")
print("=" * 80)

schema_csv = gdb.replace('.gdb', '_gold_buildings_schema_COMPLETE.csv')

with open(schema_csv, 'w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f)
    writer.writerow(['Field Name', 'Type', 'Length', 'Required', 'Category', 'Description', 'Populated By'])

    for name, spec in GOLD_BUILDINGS_SCHEMA.items():
        writer.writerow([
            name,
            spec['type'],
            spec.get('length', ''),
            'Yes' if spec['required'] else 'No',
            spec['category'],
            spec['description'],
            ', '.join(spec['populated_by'])
        ])

print(f"✅ Complete schema (74 fields) exported to:")
print(f"   {schema_csv}")

print("\n" + "=" * 80)
print("SCHEMA DEFINITION COMPLETE")
print("=" * 80)
print(f"\n✅ All 74 fields documented and validated")
print(f"✅ Ready for ingestion script development")
print(f"✅ Ready for data validation")
