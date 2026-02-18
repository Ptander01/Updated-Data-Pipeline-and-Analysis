import arcpy
import pandas as pd
from datetime import datetime
import json

# ============================================================================
# POST-INGESTION VALIDATION SCRIPT
# ============================================================================
# Run this after EVERY ingestion to validate data quality
# Returns PASS/FAIL status with detailed error report
# ============================================================================

gdb = r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\Default.gdb"
gold_buildings = f"{gdb}\\gold_buildings"

# Required fields that must be populated for ALL records
REQUIRED_FIELDS = [
    'unique_id', 'source', 'campus_id', 'campus_name',
    'latitude', 'longitude', 'company_clean',
    'city', 'country', 'region', 'ingest_date'
]

# Valid values for categorical fields
VALID_VALUES = {
    'source': ['DataCenterHawk', 'Semianalysis', 'DataCenterMap',
               'Synergy', 'NewProjectMedia', 'WoodMac'],
    'region': ['AMER', 'EMEA', 'APAC']
}

# Coordinate bounds (WGS84)
COORD_BOUNDS = {
    'latitude': (-90, 90),
    'longitude': (-180, 180)
}

def validate_gold_buildings(source_filter=None):
    """
    Validate gold_buildings data quality.

    Args:
        source_filter: Optional - validate only this source (e.g., 'Semianalysis')

    Returns:
        tuple: (passed: bool, report: dict)
    """

    print("=" * 80)
    print("GOLD_BUILDINGS DATA VALIDATION")
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    if source_filter:
        print(f"Filtering to source: {source_filter}")
    print("=" * 80)

    where_clause = f"source = '{source_filter}'" if source_filter else None

    # Get all fields
    fields = [f.name for f in arcpy.ListFields(gold_buildings)]

    # Fields to read
    read_fields = ['OID@', 'source'] + [f for f in REQUIRED_FIELDS if f in fields and f != 'source']

    # Add coordinate backup fields if they exist
    if 'gold_lat' in fields:
        read_fields.append('gold_lat')
    if 'gold_lon' in fields:
        read_fields.append('gold_lon')

    # Read all data
    records = []
    with arcpy.da.SearchCursor(gold_buildings, read_fields, where_clause=where_clause) as cursor:
        for row in cursor:
            records.append(dict(zip(read_fields, row)))

    total_records = len(records)
    print(f"\nTotal records to validate: {total_records:,}")

    # Initialize report
    report = {
        'total_records': total_records,
        'validation_timestamp': datetime.now().isoformat(),
        'source_filter': source_filter,
        'checks': {},
        'errors': [],
        'warnings': []
    }

    all_passed = True

    # =========================================================================
    # CHECK 1: Required Fields Population
    # =========================================================================
    print("\n" + "-" * 60)
    print("CHECK 1: Required Fields Population")
    print("-" * 60)

    field_completeness = {}

    for field in REQUIRED_FIELDS:
        if field not in read_fields:
            continue

        populated = sum(1 for r in records if r.get(field) is not None and r.get(field) != '')
        pct = (populated / total_records * 100) if total_records > 0 else 0
        field_completeness[field] = {'populated': populated, 'total': total_records, 'pct': pct}

        # Check for coordinate backup
        if field in ['latitude', 'longitude'] and pct < 100:
            backup_field = 'gold_lat' if field == 'latitude' else 'gold_lon'
            if backup_field in read_fields:
                backup_populated = sum(1 for r in records
                                       if (r.get(field) is None or r.get(field) == '')
                                       and r.get(backup_field) is not None)
                if backup_populated > 0:
                    report['warnings'].append(
                        f"{field}: {total_records - populated} records missing, "
                        f"but {backup_populated} have backup in {backup_field}"
                    )

        status = "✅ PASS" if pct >= 99 else ("⚠️ WARN" if pct >= 90 else "❌ FAIL")
        print(f"   {field:<25} {populated:>6,}/{total_records:<6,} ({pct:>5.1f}%) {status}")

        if pct < 99:
            all_passed = False
            report['errors'].append(f"{field}: Only {pct:.1f}% populated (required: 99%+)")

    report['checks']['field_completeness'] = field_completeness

    # =========================================================================
    # CHECK 2: Valid Values for Categorical Fields
    # =========================================================================
    print("\n" + "-" * 60)
    print("CHECK 2: Valid Categorical Values")
    print("-" * 60)

    for field, valid_values in VALID_VALUES.items():
        if field not in read_fields:
            continue

        invalid_records = []
        for r in records:
            val = r.get(field)
            if val is not None and val not in valid_values:
                invalid_records.append({'oid': r['OID@'], 'value': val})

        if invalid_records:
            all_passed = False
            unique_invalid = set(r['value'] for r in invalid_records)
            print(f"   {field:<25} ❌ FAIL - {len(invalid_records)} records with invalid values")
            print(f"      Invalid values: {unique_invalid}")
            report['errors'].append(
                f"{field}: {len(invalid_records)} records with invalid values: {unique_invalid}"
            )
        else:
            print(f"   {field:<25} ✅ PASS - All values valid")

    # =========================================================================
    # CHECK 3: Coordinate Validity
    # =========================================================================
    print("\n" + "-" * 60)
    print("CHECK 3: Coordinate Validity")
    print("-" * 60)

    coord_issues = {
        'null_coords': [],
        'out_of_bounds': [],
        'zero_coords': []
    }

    for r in records:
        oid = r['OID@']
        lat = r.get('latitude')
        lon = r.get('longitude')

        # Check for nulls (use backup if available)
        if lat is None or lat == '':
            lat = r.get('gold_lat')
        if lon is None or lon == '':
            lon = r.get('gold_lon')

        if lat is None or lon is None:
            coord_issues['null_coords'].append(oid)
        elif lat == 0 and lon == 0:
            coord_issues['zero_coords'].append(oid)
        elif not (COORD_BOUNDS['latitude'][0] <= lat <= COORD_BOUNDS['latitude'][1]):
            coord_issues['out_of_bounds'].append({'oid': oid, 'lat': lat, 'lon': lon})
        elif not (COORD_BOUNDS['longitude'][0] <= lon <= COORD_BOUNDS['longitude'][1]):
            coord_issues['out_of_bounds'].append({'oid': oid, 'lat': lat, 'lon': lon})

    for issue_type, issues in coord_issues.items():
        count = len(issues)
        pct = (count / total_records * 100) if total_records > 0 else 0

        if count > 0:
            status = "❌ FAIL" if pct > 1 else "⚠️ WARN"
            print(f"   {issue_type:<25} {count:>6} records ({pct:>5.1f}%) {status}")
            if pct > 1:
                all_passed = False
                report['errors'].append(f"Coordinates: {count} records with {issue_type}")
        else:
            print(f"   {issue_type:<25} ✅ PASS - None found")

    report['checks']['coordinate_issues'] = {k: len(v) for k, v in coord_issues.items()}

    # =========================================================================
    # CHECK 4: Duplicate Detection
    # =========================================================================
    print("\n" + "-" * 60)
    print("CHECK 4: Duplicate Detection")
    print("-" * 60)

    unique_ids = {}
    duplicates = []

    for r in records:
        uid = r.get('unique_id')
        if uid:
            if uid in unique_ids:
                duplicates.append({'oid': r['OID@'], 'unique_id': uid})
            else:
                unique_ids[uid] = r['OID@']

    if duplicates:
        all_passed = False
        print(f"   unique_id duplicates      ❌ FAIL - {len(duplicates)} duplicates found")
        report['errors'].append(f"Duplicates: {len(duplicates)} duplicate unique_id values")
    else:
        print(f"   unique_id duplicates      ✅ PASS - All unique")

    report['checks']['duplicates'] = len(duplicates)

    # =========================================================================
    # CHECK 5: Source Distribution
    # =========================================================================
    print("\n" + "-" * 60)
    print("CHECK 5: Source Distribution")
    print("-" * 60)

    source_counts = {}
    for r in records:
        src = r.get('source', 'NULL')
        source_counts[src] = source_counts.get(src, 0) + 1

    expected_counts = {
        'DataCenterHawk': 224,
        'Semianalysis': 178,
        'Synergy': 152,
        'DataCenterMap': 67,
        'NewProjectMedia': 33,
        'WoodMac': 9
    }

    for src in sorted(expected_counts.keys()):
        expected = expected_counts[src]
        actual = source_counts.get(src, 0)

        if source_filter and src != source_filter:
            continue

        if actual == expected:
            print(f"   {src:<25} {actual:>6} ✅")
        elif actual == 0:
            print(f"   {src:<25} {actual:>6} (expected {expected}) ⚠️ MISSING")
        else:
            diff = actual - expected
            print(f"   {src:<25} {actual:>6} (expected {expected}, diff: {diff:+d}) ⚠️")

    report['checks']['source_distribution'] = source_counts

    # =========================================================================
    # FINAL RESULT
    # =========================================================================
    print("\n" + "=" * 80)
    if all_passed:
        print("✅ VALIDATION PASSED - All checks passed")
    else:
        print("❌ VALIDATION FAILED - See errors above")
        print(f"\nErrors ({len(report['errors'])}):")
        for error in report['errors']:
            print(f"   • {error}")

    if report['warnings']:
        print(f"\nWarnings ({len(report['warnings'])}):")
        for warning in report['warnings']:
            print(f"   • {warning}")

    print("=" * 80)

    report['passed'] = all_passed

    return all_passed, report

def validate_source(source_name):
    """Convenience function to validate a single source."""
    return validate_gold_buildings(source_filter=source_name)

# ============================================================================
# EXECUTE
# ============================================================================
if __name__ == "__main__":
    # Validate all sources
    passed, report = validate_gold_buildings()

    # Export report
    report_path = gdb.replace('.gdb', f'_validation_report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json')
    with open(report_path, 'w') as f:
        json.dump(report, f, indent=2, default=str)
    print(f"\n📄 Report exported to: {report_path}")
