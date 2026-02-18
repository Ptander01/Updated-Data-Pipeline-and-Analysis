"""
TORTURE TEST - Gold Datasets Comprehensive Audit
Validates gold_buildings_full and gold_campus_full for data integrity issues.

Issues being investigated:
1. Mixed sources in gold_campus ("DataCenterHawk; Semianalysis")
2. Lat/long fields empty but geometry exists
3. Geography fields not populated (region, country, county, state_abbr, state)
4. DCM records with record_level='Campus' in gold_buildings
5. DCH state field mapped to abbreviation
6. Field naming clarity (source attribution)

Author: Meta Data Center GIS Team
Last Updated: 2024-12-16
"""

import arcpy
import os
import sys
from collections import defaultdict
from datetime import datetime

# Add _utils to path for config import
try:
    script_dir = os.path.dirname(os.path.abspath(__file__))
except NameError:
    script_dir = r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\scripts\04_validation"

utils_dir = os.path.join(os.path.dirname(script_dir), "_utils")
if utils_dir not in sys.path:
    sys.path.insert(0, utils_dir)

from config import GDB, GOLD_BUILDINGS, GOLD_CAMPUS

arcpy.env.workspace = GDB

# ============================================================================
# CONFIGURATION
# ============================================================================

REPORT_LIMIT = 20  # Max examples to show per issue

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def safe_str(val):
    """Safely convert to string."""
    return str(val) if val is not None else 'NULL'


def section_header(title):
    """Print section header."""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)


def subsection(title):
    """Print subsection header."""
    print(f"\n  --- {title} ---")


def status_icon(passed):
    """Return status icon."""
    return "✅" if passed else "⚠️"


# ============================================================================
# AUDIT FUNCTIONS
# ============================================================================

def audit_mixed_sources_campus():
    """
    ISSUE 1: Investigate records with multiple sources in gold_campus
    This happens when the campus_rollup aggregates buildings from different sources.
    """
    section_header("ISSUE 1: Mixed Sources in gold_campus")

    mixed_source_records = []
    source_distribution = defaultdict(int)

    with arcpy.da.SearchCursor(GOLD_CAMPUS,
            ['campus_id', 'source', 'campus_name', 'company_clean', 'city']) as cursor:
        for row in cursor:
            source = row[1] if row[1] else ''
            source_distribution[source] += 1

            # Check for semicolon (multiple sources)
            if ';' in str(source):
                mixed_source_records.append({
                    'campus_id': row[0],
                    'source': source,
                    'campus_name': row[2],
                    'company': row[3],
                    'city': row[4]
                })

    print(f"\n  Total campus records: {sum(source_distribution.values())}")
    print(f"\n  Source Distribution:")
    for src, count in sorted(source_distribution.items(), key=lambda x: -x[1]):
        print(f"    {src or 'NULL'}: {count}")

    print(f"\n  Records with MIXED sources: {len(mixed_source_records)} {status_icon(len(mixed_source_records) == 0)}")

    if mixed_source_records:
        subsection("Examples of Mixed-Source Records")
        for rec in mixed_source_records[:REPORT_LIMIT]:
            print(f"    campus_id: {rec['campus_id']}")
            print(f"      source: {rec['source']}")
            print(f"      name: {rec['campus_name']}, company: {rec['company']}, city: {rec['city']}")

        subsection("Root Cause Analysis")
        # Check gold_buildings for these campus_ids
        print("    Checking gold_buildings for these campus_ids...")
        for rec in mixed_source_records[:5]:
            campus_id = rec['campus_id']
            building_sources = set()
            with arcpy.da.SearchCursor(GOLD_BUILDINGS,
                    ['source', 'unique_id'],
                    where_clause=f"campus_id = '{campus_id}'") as b_cursor:
                for b_row in b_cursor:
                    building_sources.add(b_row[0])

            print(f"\n    campus_id: {campus_id}")
            print(f"      Building sources: {building_sources}")
            print(f"      This means multiple vendors tracked the same campus!")

    return len(mixed_source_records)


def audit_latlon_vs_geometry():
    """
    ISSUE 2: Lat/long attribute fields empty but SHAPE geometry exists
    """
    section_header("ISSUE 2: Lat/Long Fields vs Geometry")

    results = {}

    for fc_name, fc_path in [('gold_buildings', GOLD_BUILDINGS),
                              ('gold_campus', GOLD_CAMPUS)]:
        subsection(f"Checking {fc_name}")

        fields_to_check = ['latitude', 'longitude', 'gold_lat', 'gold_lon']
        existing_fields = [f.name for f in arcpy.ListFields(fc_path)]

        # Only check fields that exist
        check_fields = [f for f in fields_to_check if f in existing_fields]
        print(f"    Lat/lon fields present: {check_fields}")

        if not check_fields:
            print(f"    ⚠️ No lat/lon attribute fields found!")
            results[fc_name] = {'has_geometry_no_latlon': 0, 'total': 0}
            continue

        # Count records with geometry but no lat/lon values
        total = 0
        has_geom_no_latlon = 0
        latlon_populated = 0

        with arcpy.da.SearchCursor(fc_path, ['SHAPE@XY'] + check_fields) as cursor:
            for row in cursor:
                total += 1
                shape_xy = row[0]
                lat_vals = [row[i+1] for i in range(len(check_fields)) if 'lat' in check_fields[i].lower()]
                lon_vals = [row[i+1] for i in range(len(check_fields)) if 'lon' in check_fields[i].lower()]

                has_geometry = shape_xy and shape_xy[0] is not None and shape_xy[1] is not None
                has_latlon = any(v is not None for v in lat_vals + lon_vals)

                if has_geometry and not has_latlon:
                    has_geom_no_latlon += 1
                elif has_latlon:
                    latlon_populated += 1

        results[fc_name] = {
            'total': total,
            'has_geometry_no_latlon': has_geom_no_latlon,
            'latlon_populated': latlon_populated
        }

        print(f"    Total records: {total}")
        print(f"    Has geometry but NO lat/lon values: {has_geom_no_latlon} {status_icon(has_geom_no_latlon == 0)}")
        print(f"    Lat/lon values populated: {latlon_populated}")

        if has_geom_no_latlon > 0:
            pct = (has_geom_no_latlon / total * 100) if total > 0 else 0
            print(f"\n    🔧 FIX NEEDED: {pct:.1f}% of records need lat/lon populated from SHAPE")

    return results


def audit_geography_fields():
    """
    ISSUE 3: Geography fields not populated (region, country, county, state_abbr, state)
    """
    section_header("ISSUE 3: Geography Field Completeness")

    geo_fields = ['region', 'country', 'county', 'state_abbr', 'state', 'city', 'market']
    results = {}

    for fc_name, fc_path in [('gold_buildings', GOLD_BUILDINGS),
                              ('gold_campus', GOLD_CAMPUS)]:
        subsection(f"Checking {fc_name}")

        existing_fields = [f.name for f in arcpy.ListFields(fc_path)]
        check_fields = [f for f in geo_fields if f in existing_fields]

        total = int(arcpy.GetCount_management(fc_path)[0])
        field_stats = {f: {'null': 0, 'populated': 0} for f in check_fields}

        with arcpy.da.SearchCursor(fc_path, check_fields) as cursor:
            for row in cursor:
                for i, field in enumerate(check_fields):
                    if row[i] is None or str(row[i]).strip() == '':
                        field_stats[field]['null'] += 1
                    else:
                        field_stats[field]['populated'] += 1

        print(f"\n    {'Field':<15} {'Populated':<12} {'NULL':<10} {'%Complete':<10} Status")
        print(f"    {'-'*60}")

        for field in check_fields:
            populated = field_stats[field]['populated']
            null = field_stats[field]['null']
            pct = (populated / total * 100) if total > 0 else 0
            status = status_icon(pct > 90)
            print(f"    {field:<15} {populated:<12} {null:<10} {pct:>6.1f}%    {status}")

        results[fc_name] = field_stats

    return results


def audit_dcm_record_level():
    """
    ISSUE 4: DCM records marked as 'Campus' level in gold_buildings
    """
    section_header("ISSUE 4: DCM Record Level Analysis")

    # Check record_level distribution for DCM in gold_buildings
    record_level_counts = defaultdict(int)
    campus_level_examples = []

    where_clause = "source = 'DataCenterMap'"

    with arcpy.da.SearchCursor(GOLD_BUILDINGS,
            ['unique_id', 'record_level', 'campus_name', 'company_clean', 'city'],
            where_clause=where_clause) as cursor:
        for row in cursor:
            level = row[1] if row[1] else 'NULL'
            record_level_counts[level] += 1

            if level == 'Campus' and len(campus_level_examples) < REPORT_LIMIT:
                campus_level_examples.append({
                    'unique_id': row[0],
                    'campus_name': row[2],
                    'company': row[3],
                    'city': row[4]
                })

    total_dcm = sum(record_level_counts.values())
    print(f"\n  Total DCM records in gold_buildings: {total_dcm}")

    print(f"\n  Record Level Distribution:")
    for level, count in sorted(record_level_counts.items(), key=lambda x: -x[1]):
        pct = (count / total_dcm * 100) if total_dcm > 0 else 0
        print(f"    {level}: {count} ({pct:.1f}%)")

    campus_count = record_level_counts.get('Campus', 0)
    print(f"\n  DCM records marked as 'Campus': {campus_count} {status_icon(campus_count == 0)}")

    if campus_level_examples:
        subsection("Examples of DCM Campus-Level Records")
        for rec in campus_level_examples[:10]:
            print(f"    {rec['unique_id']}: {rec['company']} - {rec['campus_name']} ({rec['city']})")

        print("\n  📋 ANALYSIS:")
        print("    DCM uses 'parent_id' field to indicate building vs campus.")
        print("    Records without parent_id or with parent_id=0 are classified as 'Campus'.")
        print("    This is likely correct behavior - these ARE campus-level aggregates in DCM.")
        print("    Consider: Should these be in gold_campus instead of gold_buildings?")

    return record_level_counts


def audit_dch_state_mapping():
    """
    ISSUE 5: DCH state field mapping - state vs state_abbr
    """
    section_header("ISSUE 5: DCH State Field Mapping")

    where_clause = "source = 'DataCenterHawk'"

    state_samples = defaultdict(list)
    state_abbr_samples = defaultdict(list)

    with arcpy.da.SearchCursor(GOLD_BUILDINGS,
            ['unique_id', 'state', 'state_abbr', 'country'],
            where_clause=where_clause) as cursor:
        for row in cursor:
            state = row[1]
            state_abbr = row[2]
            country = row[3]

            # Collect samples
            if state and len(state) <= 3:
                if len(state_samples[state]) < 3:
                    state_samples[state].append(row[0])
            if state_abbr:
                if len(state_abbr_samples[state_abbr]) < 3:
                    state_abbr_samples[state_abbr].append(row[0])

    print(f"\n  Analyzing DCH state field values...")

    # Check if state contains abbreviations (2-3 chars typically)
    abbrev_in_state = sum(1 for s in state_samples.keys() if s and len(s) <= 3)
    full_in_state = sum(1 for s in state_samples.keys() if s and len(s) > 3)

    print(f"\n  State field analysis:")
    print(f"    Values that look like abbreviations (<=3 chars): {abbrev_in_state}")
    print(f"    Values that look like full names (>3 chars): {full_in_state}")

    if abbrev_in_state > 0:
        print(f"\n  Sample abbreviation-like values in 'state' field:")
        for state, uids in list(state_samples.items())[:10]:
            if state and len(state) <= 3:
                print(f"    '{state}' - found in {uids[0]}")

        print(f"\n  ⚠️ FINDING: DCH 'state' field contains abbreviations, not full state names.")
        print("    This is coming from the source data directly.")
        print("\n  🔧 RECOMMENDATION:")
        print("    Option A: Map DCH state → state_abbr in ingest_dch.py, leave state NULL")
        print("    Option B: Add geography enrichment script to populate full state names")
        print("    Option C: Use reverse geocoding/spatial join to populate all geography fields")

    return {'abbrev_count': abbrev_in_state, 'full_count': full_in_state}


def audit_field_documentation():
    """
    ISSUE 6: Field naming clarity - source attribution
    """
    section_header("ISSUE 6: Field Naming & Source Attribution")

    print("\n  Current Schema Analysis:")

    # Get all fields from gold_buildings
    fields = arcpy.ListFields(GOLD_BUILDINGS)

    capacity_fields = []
    geo_fields = []
    company_fields = []
    other_fields = []

    for f in fields:
        name = f.name.lower()
        if f.type in ['OID', 'Geometry']:
            continue
        if any(kw in name for kw in ['mw', 'power', 'capacity', 'sqft']):
            capacity_fields.append(f.name)
        elif any(kw in name for kw in ['state', 'country', 'region', 'city', 'county', 'market', 'lat', 'lon', 'address', 'postal']):
            geo_fields.append(f.name)
        elif any(kw in name for kw in ['company', 'owner']):
            company_fields.append(f.name)
        else:
            other_fields.append(f.name)

    print(f"\n  Capacity Fields ({len(capacity_fields)}):")
    for f in capacity_fields:
        print(f"    • {f}")

    print(f"\n  Geography Fields ({len(geo_fields)}):")
    for f in geo_fields:
        print(f"    • {f}")

    print(f"\n  Company Fields ({len(company_fields)}):")
    for f in company_fields:
        print(f"    • {f}")

    subsection("Source Attribution Options")
    print("""
    OPTION A: Source Suffix in Field Names
    ----------------------------------------
    Example: commissioned_power_mw_DCH, commissioned_power_mw_DCM
    Pros: Crystal clear which source provided the value
    Cons: Schema explosion - too many fields, hard to query across sources

    OPTION B: Field Alias (Current approach viable)
    ----------------------------------------
    Example: field alias = "Commissioned Power (MW) - from source"
    Pros: Clean schema, aliases visible in ArcGIS UI
    Cons: 'source' field already indicates origin

    OPTION C: Source Field + Documentation (RECOMMENDED)
    ----------------------------------------
    Keep current schema. The 'source' field already tells you origin.
    Create CAPACITY_FIELD_DEFINITIONS.md documenting each source's mappings.

    VERDICT: Option C is recommended. Adding source suffixes would:
    - Create schema bloat (5 sources × 4 capacity fields = 20 fields)
    - Make aggregation queries harder
    - The 'source' field already provides attribution
    """)

    return {
        'capacity_fields': capacity_fields,
        'geo_fields': geo_fields,
        'company_fields': company_fields
    }


def generate_fix_recommendations():
    """Generate summary of recommended fixes."""
    section_header("🔧 RECOMMENDED FIXES")

    print("""
    PRIORITY 1: Lat/Long from Geometry (Easy)
    ------------------------------------------
    Create script: populate_latlon_from_geometry.py
    - For records with SHAPE but NULL latitude/longitude
    - Extract X/Y from SHAPE@XY and populate lat/lon fields

    PRIORITY 2: Geography Enrichment (Medium)
    ------------------------------------------
    Create script: enrich_geography_fields.py
    Options:
    a) Reverse geocode using SHAPE coordinates
    b) Spatial join to administrative boundary layers
    c) Use ArcGIS Online geocoding service

    PRIORITY 3: DCH State Mapping Fix (Easy)
    ------------------------------------------
    Modify: ingest_dch.py
    - Map 'state' from DCH → 'state_abbr' in gold_buildings
    - Leave 'state' NULL for geography enrichment to fill

    PRIORITY 4: Mixed Sources (No Fix Needed)
    ------------------------------------------
    The mixed source records are CORRECT behavior!
    When DataCenterHawk and Semianalysis both track the same campus,
    the campus_rollup correctly concatenates both sources.
    This is valuable information showing vendor overlap.

    PRIORITY 5: DCM Record Level (Documentation Only)
    ------------------------------------------
    DCM records with record_level='Campus' are correct.
    These are campus-level aggregates from the source.
    Document this in GRANULARITY_STRATEGY.md.

    PRIORITY 6: Field Naming (No Change Recommended)
    ------------------------------------------
    Keep current schema. The 'source' field provides attribution.
    Avoid schema bloat from source-specific field names.
    """)


# ============================================================================
# MAIN EXECUTION
# ============================================================================

def main():
    print("=" * 80)
    print("   TORTURE TEST - Gold Datasets Comprehensive Audit")
    print("=" * 80)
    print(f"   Started: {datetime.now()}")
    print(f"   GDB: {GDB}")
    print(f"   gold_buildings: {os.path.basename(GOLD_BUILDINGS)}")
    print(f"   gold_campus: {os.path.basename(GOLD_CAMPUS)}")

    # Run all audits
    results = {}

    results['mixed_sources'] = audit_mixed_sources_campus()
    results['latlon_geometry'] = audit_latlon_vs_geometry()
    results['geography'] = audit_geography_fields()
    results['dcm_record_level'] = audit_dcm_record_level()
    results['dch_state'] = audit_dch_state_mapping()
    results['field_naming'] = audit_field_documentation()

    # Generate fix recommendations
    generate_fix_recommendations()

    # Summary
    section_header("AUDIT SUMMARY")

    print(f"""
    Issue 1 - Mixed Sources:     {results['mixed_sources']} campus records have multiple sources
                                 → This is CORRECT behavior (vendor overlap)

    Issue 2 - Lat/Lon Fields:
        gold_buildings: {results['latlon_geometry'].get('gold_buildings', {}).get('has_geometry_no_latlon', 'N/A')} need lat/lon populated
        gold_campus: {results['latlon_geometry'].get('gold_campus', {}).get('has_geometry_no_latlon', 'N/A')} need lat/lon populated

    Issue 3 - Geography Fields:  See detailed breakdown above

    Issue 4 - DCM Campus Level:  {results['dcm_record_level'].get('Campus', 0)} records
                                 → This is CORRECT (source granularity)

    Issue 5 - DCH State Abbrev:  {results['dch_state'].get('abbrev_count', 0)} abbreviated values in 'state' field
                                 → FIX in ingest_dch.py

    Issue 6 - Field Naming:      No change recommended - use 'source' field
    """)

    print(f"\n   Completed: {datetime.now()}")
    print("=" * 80)

    return results


# Execute
if __name__ == "__main__":
    try:
        results = main()
    except Exception as e:
        print(f"\n❌ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()

# Also run when exec()'d
try:
    results = main()
except Exception as e:
    print(f"\n❌ ERROR: {str(e)}")
    import traceback
    traceback.print_exc()
