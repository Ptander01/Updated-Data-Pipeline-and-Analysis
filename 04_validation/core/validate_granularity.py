"""
Granularity Validation Script
Validates record_level assignments and prevents data misappropriation.

This script should be run:
1. BEFORE ingestion: Audit raw data granularity
2. AFTER ingestion: Validate record_level assignments in gold_buildings

Key Principles:
- gold_buildings_full: Contains BUILDING-level records only
- gold_campus_full: Contains CAMPUS-level aggregations (derived from buildings)
- record_level field: Must accurately reflect the granularity of each record
- WoodMac has SEPARATE Campus and DC tables - handle appropriately

Author: Meta Data Center GIS Team
Last Updated: 2024-12-15
"""

import arcpy
import os
import sys
from datetime import datetime
from collections import defaultdict

# Add _utils to path for config import
# Handle both direct execution and exec() from ArcGIS Pro Python window
import os
import sys

try:
    script_dir = os.path.dirname(os.path.abspath(__file__))
except NameError:
    # Running via exec() - use known path
    script_dir = r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\scripts\04_validation"

utils_dir = os.path.join(os.path.dirname(script_dir), "_utils")
if utils_dir not in sys.path:
    sys.path.insert(0, utils_dir)

from config import GDB, GOLD_BUILDINGS, GOLD_CAMPUS, RAW_TABLES

arcpy.env.workspace = GDB

# ============================================================================
# GRANULARITY DEFINITIONS BY SOURCE
# ============================================================================

SOURCE_GRANULARITY = {
    'DataCenterHawk': {
        'expected_level': 'Building',
        'description': 'DCH reports at building level with facility_id per building',
        'indicators': ['facility_type', 'company_code'],  # company_code like CLN1, CLN2
        'validation': 'Building-level if company_code exists (e.g., ODN1, CLN2)'
    },
    'Semianalysis': {
        'expected_level': 'Building',
        'description': 'Semianalysis cluster field contains building designations',
        'indicators': ['cluster'],  # e.g., Meta_Altoona_1, Meta_Altoona_2
        'validation': 'Building-level - cluster field has building numbers'
    },
    'DataCenterMap': {
        'expected_level': 'Mixed',
        'description': 'DCM has both building and campus records',
        'indicators': ['parent_id', 'name'],
        'validation': 'Building if has parent_id or "Building X" in name'
    },
    'NewProjectMedia': {
        'expected_level': 'Project',
        'description': 'NPM reports announced projects, often campus-level',
        'indicators': ['project'],
        'validation': 'Typically project/campus level - review before treating as building'
    },
    'Synergy': {
        'expected_level': 'Facility',
        'description': 'Synergy reports facility counts, unclear granularity',
        'indicators': ['quantity'],
        'validation': 'Counts facilities - may be campus or building level'
    },
    'WoodMac': {
        'expected_level': 'Building',
        'description': 'WoodMac DC table is building-level',
        'indicators': ['project_id'],
        'validation': 'Building-level from woodmac_dc_raw'
    },
    'WoodMac_Campus': {
        'expected_level': 'Campus',
        'description': 'WoodMac Campus table is campus-level aggregations',
        'indicators': ['campus_id'],
        'validation': 'Campus-level from woodmac_campus_raw - DO NOT mix with buildings'
    }
}


# ============================================================================
# PRE-INGESTION AUDIT
# ============================================================================

def audit_raw_tables():
    """
    Audit raw tables BEFORE ingestion to understand granularity.
    Returns dict with granularity analysis per source.
    """
    print("=" * 80)
    print("PRE-INGESTION GRANULARITY AUDIT")
    print("=" * 80)
    print(f"Started: {datetime.now()}\n")

    results = {}

    for key, table_path in RAW_TABLES.items():
        if not arcpy.Exists(table_path):
            print(f"⚠️  {key}: Table not found - {table_path}")
            continue

        count = int(arcpy.GetCount_management(table_path)[0])
        fields = [f.name for f in arcpy.ListFields(table_path)]

        # Analyze key fields for granularity detection
        analysis = {
            'table': os.path.basename(table_path),
            'record_count': count,
            'field_count': len(fields),
            'granularity_indicators': {}
        }

        # Check for building-level indicators
        building_indicators = ['building', 'facility_id', 'building_id', 'bldg']
        campus_indicators = ['campus', 'site', 'project']

        for ind in building_indicators:
            matching = [f for f in fields if ind in f.lower()]
            if matching:
                analysis['granularity_indicators']['building_fields'] = matching

        for ind in campus_indicators:
            matching = [f for f in fields if ind in f.lower()]
            if matching:
                analysis['granularity_indicators']['campus_fields'] = matching

        # Specific checks per source
        if 'woodmac_campus' in key:
            analysis['recommended_destination'] = 'gold_campus OR separate handling'
            analysis['warning'] = '⚠️ CAMPUS DATA - Do not ingest into gold_buildings!'
        elif 'woodmac_dc' in key:
            analysis['recommended_destination'] = 'gold_buildings'
            analysis['expected_level'] = 'Building'
        elif 'dch' in key:
            analysis['recommended_destination'] = 'gold_buildings'
            analysis['expected_level'] = 'Building'
        elif 'semianalysis' in key:
            analysis['recommended_destination'] = 'gold_buildings'
            analysis['expected_level'] = 'Building'
        elif 'dcm' in key:
            analysis['recommended_destination'] = 'gold_buildings (with level detection)'
            analysis['expected_level'] = 'Mixed - use derive_record_level()'
        elif 'npm' in key:
            analysis['recommended_destination'] = 'gold_buildings'
            analysis['expected_level'] = 'Project/Campus (review)'
        elif 'synergy' in key:
            analysis['recommended_destination'] = 'gold_buildings'
            analysis['expected_level'] = 'Facility (unclear)'

        results[key] = analysis

        # Print summary
        dest = analysis.get('recommended_destination', 'Unknown')
        level = analysis.get('expected_level', 'Unknown')
        warning = analysis.get('warning', '')

        print(f"\n{'='*60}")
        print(f"📊 {key.upper()}")
        print(f"{'='*60}")
        print(f"   Records: {count:,}")
        print(f"   Fields: {len(fields)}")
        print(f"   Expected Level: {level}")
        print(f"   Destination: {dest}")
        if warning:
            print(f"   {warning}")

        # Show granularity indicators
        if analysis['granularity_indicators']:
            print(f"   Granularity Fields:")
            for k, v in analysis['granularity_indicators'].items():
                print(f"     - {k}: {v}")

    # CRITICAL: Check for WoodMac Campus gap
    print("\n" + "=" * 80)
    print("⚠️  CRITICAL CHECK: WoodMac Campus Data")
    print("=" * 80)

    if 'woodmac_campus' in RAW_TABLES:
        campus_path = RAW_TABLES['woodmac_campus']
        if arcpy.Exists(campus_path):
            campus_count = int(arcpy.GetCount_management(campus_path)[0])
            print(f"   woodmac_campus_raw: {campus_count} records")
            print(f"   ❌ This data is NOT being ingested by any script!")
            print(f"   📋 ACTION REQUIRED:")
            print(f"      Option A: Create ingest_woodmac_campus.py for gold_campus")
            print(f"      Option B: Add campus handling to existing ingestion")
            print(f"      Option C: Document why this data is excluded")

    return results


# ============================================================================
# POST-INGESTION VALIDATION
# ============================================================================

def validate_gold_buildings_granularity():
    """
    Validate record_level assignments in gold_buildings AFTER ingestion.
    Checks for potential misassignments.
    """
    print("\n" + "=" * 80)
    print("POST-INGESTION GRANULARITY VALIDATION")
    print("=" * 80)
    print(f"Target: {GOLD_BUILDINGS}")

    if not arcpy.Exists(GOLD_BUILDINGS):
        print("❌ gold_buildings does not exist!")
        return None

    total = int(arcpy.GetCount_management(GOLD_BUILDINGS)[0])
    print(f"Total records: {total:,}\n")

    if total == 0:
        print("⚠️  No records to validate - run ingestion first")
        return None

    results = {
        'total_records': total,
        'by_source': defaultdict(lambda: {'Building': 0, 'Campus': 0, 'Other': 0}),
        'potential_issues': [],
        'campus_records_in_buildings': []
    }

    # Analyze record_level by source
    print("📊 Record Level Distribution by Source:")
    print("-" * 60)

    with arcpy.da.SearchCursor(
        GOLD_BUILDINGS,
        ['source', 'record_level', 'unique_id', 'campus_name', 'campus_id']
    ) as cursor:
        for row in cursor:
            source = row[0] or 'Unknown'
            level = row[1] or 'NULL'
            unique_id = row[2]
            campus_name = row[3]
            campus_id = row[4]

            # Categorize
            if level == 'Building':
                results['by_source'][source]['Building'] += 1
            elif level == 'Campus':
                results['by_source'][source]['Campus'] += 1
                # Flag: Campus records should NOT be in gold_buildings
                results['campus_records_in_buildings'].append({
                    'source': source,
                    'unique_id': unique_id,
                    'campus_name': campus_name,
                    'campus_id': campus_id
                })
            else:
                results['by_source'][source]['Other'] += 1

    # Print distribution
    for source in sorted(results['by_source'].keys()):
        counts = results['by_source'][source]
        total_source = sum(counts.values())
        building_pct = (counts['Building'] / total_source * 100) if total_source > 0 else 0

        status = "✅" if counts['Campus'] == 0 else "⚠️"
        print(f"{status} {source:25s} Building: {counts['Building']:>5} ({building_pct:.1f}%)  "
              f"Campus: {counts['Campus']:>5}  Other: {counts['Other']:>5}")

    # Report campus records that shouldn't be here
    if results['campus_records_in_buildings']:
        print(f"\n{'='*60}")
        print(f"⚠️  WARNING: {len(results['campus_records_in_buildings'])} Campus-level records in gold_buildings!")
        print(f"{'='*60}")
        print("These should be in gold_campus, not gold_buildings:")

        for i, record in enumerate(results['campus_records_in_buildings'][:10]):
            print(f"   {i+1}. {record['source']}: {record['campus_name']} ({record['unique_id']})")

        if len(results['campus_records_in_buildings']) > 10:
            print(f"   ... and {len(results['campus_records_in_buildings']) - 10} more")

        results['potential_issues'].append(
            f"{len(results['campus_records_in_buildings'])} campus records incorrectly in gold_buildings"
        )

    # Check for NULL record_level
    null_count = sum(c['Other'] for c in results['by_source'].values())
    if null_count > 0:
        print(f"\n⚠️  WARNING: {null_count} records have NULL/Other record_level")
        results['potential_issues'].append(f"{null_count} records with NULL record_level")

    return results


# ============================================================================
# CROSS-VALIDATION: Buildings vs Campus
# ============================================================================

def validate_campus_derivation():
    """
    Validate that gold_campus records are properly derived from gold_buildings.
    Checks for orphan campus records not linked to buildings.
    """
    print("\n" + "=" * 80)
    print("CAMPUS DERIVATION VALIDATION")
    print("=" * 80)

    if not arcpy.Exists(GOLD_BUILDINGS) or not arcpy.Exists(GOLD_CAMPUS):
        print("❌ One or both feature classes don't exist!")
        return None

    # Get all campus_ids from buildings
    building_campus_ids = set()
    with arcpy.da.SearchCursor(GOLD_BUILDINGS, ['campus_id']) as cursor:
        for row in cursor:
            if row[0]:
                building_campus_ids.add(row[0])

    print(f"Unique campus_id in gold_buildings: {len(building_campus_ids)}")

    # Get all campus_ids from campus
    campus_ids = set()
    with arcpy.da.SearchCursor(GOLD_CAMPUS, ['campus_id']) as cursor:
        for row in cursor:
            if row[0]:
                campus_ids.add(row[0])

    print(f"Records in gold_campus: {len(campus_ids)}")

    # Check for orphans
    orphan_campuses = campus_ids - building_campus_ids
    missing_campuses = building_campus_ids - campus_ids

    if orphan_campuses:
        print(f"\n⚠️  WARNING: {len(orphan_campuses)} campus records NOT derived from buildings!")
        print("   These may have been directly inserted (e.g., WoodMac Campus data)")
        for campus_id in list(orphan_campuses)[:5]:
            print(f"     - {campus_id}")

    if missing_campuses:
        print(f"\n⚠️  WARNING: {len(missing_campuses)} building campus_ids NOT in gold_campus!")
        print("   Run campus_rollup.py to update gold_campus")

    if not orphan_campuses and not missing_campuses:
        print("\n✅ gold_campus perfectly derived from gold_buildings")

    return {
        'building_campus_ids': len(building_campus_ids),
        'campus_records': len(campus_ids),
        'orphan_campuses': len(orphan_campuses),
        'missing_from_campus': len(missing_campuses)
    }


# ============================================================================
# DUPLICATE DETECTION
# ============================================================================

def detect_cross_source_duplicates():
    """
    Detect potential duplicates across sources based on campus_id.
    This is expected (same facility in multiple sources) but should be documented.
    """
    print("\n" + "=" * 80)
    print("CROSS-SOURCE DUPLICATE DETECTION")
    print("=" * 80)

    if not arcpy.Exists(GOLD_BUILDINGS):
        print("❌ gold_buildings does not exist!")
        return None

    # Group records by campus_id
    campus_sources = defaultdict(lambda: {'sources': set(), 'count': 0, 'records': []})

    with arcpy.da.SearchCursor(
        GOLD_BUILDINGS,
        ['campus_id', 'source', 'unique_id', 'campus_name']
    ) as cursor:
        for row in cursor:
            campus_id = row[0] or 'NULL'
            source = row[1] or 'Unknown'
            unique_id = row[2]
            campus_name = row[3]

            campus_sources[campus_id]['sources'].add(source)
            campus_sources[campus_id]['count'] += 1
            campus_sources[campus_id]['records'].append({
                'source': source,
                'unique_id': unique_id,
                'campus_name': campus_name
            })

    # Find multi-source campuses
    multi_source = {k: v for k, v in campus_sources.items()
                    if len(v['sources']) > 1}

    print(f"Total unique campus_ids: {len(campus_sources)}")
    print(f"Campuses in multiple sources: {len(multi_source)}")

    if multi_source:
        print(f"\n📊 Top 10 campuses appearing in most sources:")
        print("-" * 70)

        sorted_multi = sorted(multi_source.items(),
                              key=lambda x: len(x[1]['sources']), reverse=True)

        for campus_id, data in sorted_multi[:10]:
            sources_str = ", ".join(sorted(data['sources']))
            name = data['records'][0]['campus_name'] if data['records'] else 'Unknown'
            print(f"   {name[:40]:<40} ({len(data['sources'])} sources)")
            print(f"      Sources: {sources_str}")
            print(f"      Records: {data['count']}")

    return {
        'total_campus_ids': len(campus_sources),
        'multi_source_campuses': len(multi_source),
        'details': multi_source
    }


# ============================================================================
# MAIN VALIDATION WORKFLOW
# ============================================================================

def run_full_validation(mode='post'):
    """
    Run full validation suite.

    Args:
        mode: 'pre' for pre-ingestion audit, 'post' for post-ingestion validation, 'all' for both
    """
    print("=" * 80)
    print("GRANULARITY VALIDATION SUITE")
    print("=" * 80)
    print(f"Mode: {mode.upper()}")
    print(f"Started: {datetime.now()}")
    print(f"GDB: {GDB}")

    results = {}

    if mode in ['pre', 'all']:
        results['raw_audit'] = audit_raw_tables()

    if mode in ['post', 'all']:
        results['buildings_validation'] = validate_gold_buildings_granularity()
        results['campus_derivation'] = validate_campus_derivation()
        results['duplicates'] = detect_cross_source_duplicates()

    # Summary
    print("\n" + "=" * 80)
    print("VALIDATION SUMMARY")
    print("=" * 80)

    issues = []

    if 'buildings_validation' in results and results['buildings_validation']:
        issues.extend(results['buildings_validation'].get('potential_issues', []))

    if issues:
        print("\n⚠️  ISSUES FOUND:")
        for issue in issues:
            print(f"   - {issue}")
    else:
        print("\n✅ No critical issues found")

    print(f"\nCompleted: {datetime.now()}")

    return results


# ============================================================================
# EXECUTE
# ============================================================================

if __name__ == "__main__":
    # Default to post-ingestion validation
    # Change to 'pre' before ingestion, 'all' for complete validation
    results = run_full_validation(mode='pre')
