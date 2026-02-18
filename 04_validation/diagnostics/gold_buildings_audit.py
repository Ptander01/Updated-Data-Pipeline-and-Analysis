import arcpy
import pandas as pd
from datetime import datetime
from collections import defaultdict

# ============================================================================
# GOLD_BUILDINGS COMPREHENSIVE AUDIT
# ============================================================================

gdb_path = r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\Default.gdb"
gold_buildings = f"{gdb_path}\\gold_buildings"

print("="*80)
print("GOLD_BUILDINGS COMPREHENSIVE AUDIT")
print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("="*80)

# ============================================================================
# SECTION 1: SCHEMA ANALYSIS
# ============================================================================
print("\n" + "="*80)
print("SECTION 1: COMPLETE SCHEMA")
print("="*80)

fields = arcpy.ListFields(gold_buildings)

print(f"\n📋 Total fields: {len(fields)}")
print("\n" + "-"*80)
print(f"{'#':<4} {'Field Name':<30} {'Type':<12} {'Length':<8} {'Alias'}")
print("-"*80)

# Categorize fields
coord_fields = []
capacity_fields = []
id_fields = []
date_fields = []
status_fields = []
other_fields = []

for i, f in enumerate(fields, 1):
    length = f.length if f.type == 'String' else 'N/A'
    print(f"{i:<4} {f.name:<30} {f.type:<12} {str(length):<8} {f.aliasName}")

    # Categorize
    name_lower = f.name.lower()
    if any(x in name_lower for x in ['lat', 'lon', 'x', 'y', 'coord', 'gold_lat', 'gold_lon']):
        coord_fields.append(f.name)
    elif any(x in name_lower for x in ['mw', 'capacity', 'power', 'load']):
        capacity_fields.append(f.name)
    elif any(x in name_lower for x in ['id', 'key', 'unique']):
        id_fields.append(f.name)
    elif f.type == 'Date' or 'date' in name_lower:
        date_fields.append(f.name)
    elif any(x in name_lower for x in ['status', 'type', 'phase']):
        status_fields.append(f.name)
    else:
        other_fields.append(f.name)

print("\n" + "-"*80)
print("FIELD CATEGORIES:")
print("-"*80)
print(f"\n🌍 Coordinate fields ({len(coord_fields)}):")
for f in coord_fields:
    print(f"   • {f}")

print(f"\n⚡ Capacity/Power fields ({len(capacity_fields)}):")
for f in capacity_fields:
    print(f"   • {f}")

print(f"\n🔑 ID/Key fields ({len(id_fields)}):")
for f in id_fields:
    print(f"   • {f}")

print(f"\n📅 Date fields ({len(date_fields)}):")
for f in date_fields:
    print(f"   • {f}")

print(f"\n📊 Status fields ({len(status_fields)}):")
for f in status_fields:
    print(f"   • {f}")

# ============================================================================
# SECTION 2: RECORD COUNTS BY SOURCE
# ============================================================================
print("\n" + "="*80)
print("SECTION 2: RECORD COUNTS BY SOURCE")
print("="*80)

source_counts = {}
with arcpy.da.SearchCursor(gold_buildings, ['source']) as cursor:
    for row in cursor:
        source = row[0] if row[0] else 'NULL'
        source_counts[source] = source_counts.get(source, 0) + 1

print(f"\n{'Source':<20} {'Count':<10} {'Pct'}")
print("-"*40)
total = sum(source_counts.values())
for source, count in sorted(source_counts.items(), key=lambda x: -x[1]):
    pct = count / total * 100
    print(f"{source:<20} {count:<10} {pct:.1f}%")
print("-"*40)
print(f"{'TOTAL':<20} {total:<10}")

# ============================================================================
# SECTION 3: DATA COMPLETENESS BY SOURCE
# ============================================================================
print("\n" + "="*80)
print("SECTION 3: DATA COMPLETENESS BY SOURCE")
print("="*80)

# Key fields to check
key_fields = [
    # Coordinates
    'latitude', 'longitude', 'gold_lat', 'gold_lon', 'gold_long',
    # IDs
    'unique_id', 'campus_id', 'campus_name', 'building_designation',
    # Location
    'city', 'state', 'country', 'region', 'address',
    # Company
    'company_clean', 'company_source',
    # Capacity - current
    'commissioned_power_mw', 'operational_power_mw', 'full_capacity_mw',
    # Capacity - pipeline
    'uc_power_mw', 'planned_power_mw',
    # Capacity - forecasts
    'mw_2023', 'mw_2024', 'mw_2025', 'mw_2026', 'mw_2027',
    'mw_2028', 'mw_2029', 'mw_2030', 'mw_2031', 'mw_2032',
    # Status
    'facility_status', 'building_type',
    # Dates
    'ingest_date', 'actual_live_date', 'construction_started'
]

# Filter to fields that actually exist
existing_fields = [f.name for f in fields]
fields_to_check = ['source'] + [f for f in key_fields if f in existing_fields]

print(f"\n📋 Checking {len(fields_to_check)-1} key fields across all sources...")

# Read all data
data = []
with arcpy.da.SearchCursor(gold_buildings, fields_to_check) as cursor:
    for row in cursor:
        data.append(dict(zip(fields_to_check, row)))

df = pd.DataFrame(data)

# Calculate completeness by source
sources = df['source'].unique()

print("\n" + "-"*100)
print("DATA COMPLETENESS MATRIX (% of records with non-null values)")
print("-"*100)

# Create completeness matrix
completeness = {}
for source in sorted(sources):
    source_df = df[df['source'] == source]
    source_count = len(source_df)
    completeness[source] = {'_count': source_count}

    for field in fields_to_check[1:]:  # Skip 'source'
        non_null = source_df[field].notna().sum()
        pct = (non_null / source_count * 100) if source_count > 0 else 0
        completeness[source][field] = pct

# Print as table - split into sections for readability

# Section 3a: Coordinate fields
print("\n📍 COORDINATE FIELDS:")
print("-"*80)
coord_check = [f for f in ['latitude', 'longitude', 'gold_lat', 'gold_lon', 'gold_long'] if f in fields_to_check]
header = f"{'Source':<18} {'Count':<8}" + "".join([f"{f:<12}" for f in coord_check])
print(header)
print("-"*80)
for source in sorted(sources):
    row = f"{source:<18} {completeness[source]['_count']:<8}"
    for field in coord_check:
        pct = completeness[source].get(field, 0)
        status = "✅" if pct > 90 else ("⚠️" if pct > 0 else "❌")
        row += f"{pct:>5.0f}% {status}   "
    print(row)

# Section 3b: ID fields
print("\n🔑 IDENTIFICATION FIELDS:")
print("-"*80)
id_check = [f for f in ['unique_id', 'campus_id', 'campus_name', 'building_designation'] if f in fields_to_check]
header = f"{'Source':<18} {'Count':<8}" + "".join([f"{f:<20}" for f in id_check])
print(header)
print("-"*80)
for source in sorted(sources):
    row = f"{source:<18} {completeness[source]['_count']:<8}"
    for field in id_check:
        pct = completeness[source].get(field, 0)
        status = "✅" if pct > 90 else ("⚠️" if pct > 0 else "❌")
        row += f"{pct:>5.0f}% {status}          "
    print(row)

# Section 3c: Location fields
print("\n📍 LOCATION FIELDS:")
print("-"*80)
loc_check = [f for f in ['city', 'state', 'country', 'region', 'company_clean'] if f in fields_to_check]
header = f"{'Source':<18} {'Count':<8}" + "".join([f"{f:<14}" for f in loc_check])
print(header)
print("-"*80)
for source in sorted(sources):
    row = f"{source:<18} {completeness[source]['_count']:<8}"
    for field in loc_check:
        pct = completeness[source].get(field, 0)
        status = "✅" if pct > 90 else ("⚠️" if pct > 0 else "❌")
        row += f"{pct:>5.0f}% {status}    "
    print(row)

# Section 3d: Capacity fields
print("\n⚡ CAPACITY FIELDS:")
print("-"*100)
cap_check = [f for f in ['commissioned_power_mw', 'uc_power_mw', 'planned_power_mw', 'full_capacity_mw'] if f in fields_to_check]
header = f"{'Source':<18} {'Count':<8}" + "".join([f"{f:<22}" for f in cap_check])
print(header)
print("-"*100)
for source in sorted(sources):
    row = f"{source:<18} {completeness[source]['_count']:<8}"
    for field in cap_check:
        pct = completeness[source].get(field, 0)
        status = "✅" if pct > 90 else ("⚠️" if pct > 0 else "❌")
        row += f"{pct:>5.0f}% {status}            "
    print(row)

# Section 3e: MW Forecast fields (Semianalysis specialty)
print("\n📈 MW FORECAST FIELDS (mw_2023 - mw_2032):")
print("-"*120)
mw_check = [f for f in ['mw_2023', 'mw_2024', 'mw_2025', 'mw_2026', 'mw_2027', 'mw_2028', 'mw_2029', 'mw_2030', 'mw_2031', 'mw_2032'] if f in fields_to_check]
header = f"{'Source':<18} {'Count':<8}" + "".join([f"{f:<10}" for f in mw_check])
print(header)
print("-"*120)
for source in sorted(sources):
    row = f"{source:<18} {completeness[source]['_count']:<8}"
    for field in mw_check:
        pct = completeness[source].get(field, 0)
        status = "✅" if pct > 90 else ("⚠️" if pct > 0 else "❌")
        row += f"{pct:>4.0f}%{status}   "
    print(row)

# ============================================================================
# SECTION 4: SEMIANALYSIS DEEP DIVE
# ============================================================================
print("\n" + "="*80)
print("SECTION 4: SEMIANALYSIS DEEP DIVE")
print("="*80)

semi_df = df[df['source'] == 'Semianalysis']
print(f"\n📊 Semianalysis records: {len(semi_df)}")

# Check each field
print("\n" + "-"*60)
print("FIELD-BY-FIELD ANALYSIS:")
print("-"*60)

for field in fields_to_check[1:]:
    non_null = semi_df[field].notna().sum()
    pct = (non_null / len(semi_df) * 100) if len(semi_df) > 0 else 0

    if pct == 0:
        status = "❌ EMPTY"
    elif pct < 50:
        status = "⚠️ SPARSE"
    elif pct < 100:
        status = "🔶 PARTIAL"
    else:
        status = "✅ COMPLETE"

    print(f"   {field:<30} {non_null:>5}/{len(semi_df):<5} ({pct:>5.1f}%) {status}")

# Sample Semianalysis records
print("\n" + "-"*60)
print("SAMPLE SEMIANALYSIS RECORDS (first 5):")
print("-"*60)

sample_fields = ['unique_id', 'campus_name', 'city', 'state', 'company_clean', 'latitude', 'longitude']
sample_fields = [f for f in sample_fields if f in fields_to_check]

if 'gold_lat' in existing_fields:
    sample_fields.append('gold_lat')
if 'gold_lon' in existing_fields or 'gold_long' in existing_fields:
    sample_fields.append('gold_lon' if 'gold_lon' in existing_fields else 'gold_long')

print(f"\nFields: {sample_fields}")
print()

with arcpy.da.SearchCursor(gold_buildings, sample_fields,
                           where_clause="source = 'Semianalysis'") as cursor:
    for i, row in enumerate(cursor):
        if i >= 5:
            break
        print(f"Record {i+1}:")
        for j, field in enumerate(sample_fields):
            val = row[j]
            val_str = str(val)[:50] if val else "NULL"
            print(f"   {field}: {val_str}")
        print()

# ============================================================================
# SECTION 5: COORDINATE FIELD INVESTIGATION
# ============================================================================
print("\n" + "="*80)
print("SECTION 5: COORDINATE FIELD INVESTIGATION")
print("="*80)

# Find all potential coordinate fields
potential_coord_fields = [f.name for f in fields if any(x in f.name.lower() for x in ['lat', 'lon', 'long', 'x', 'y'])]
potential_coord_fields.append('SHAPE@XY')

print(f"\n🔍 Potential coordinate fields found: {potential_coord_fields}")

# Check each source's coordinate coverage
print("\n" + "-"*80)
print("COORDINATE COVERAGE BY SOURCE:")
print("-"*80)

for source in sorted(sources):
    print(f"\n📍 {source}:")

    # Build query fields
    query_fields = ['SHAPE@XY'] + [f for f in potential_coord_fields if f != 'SHAPE@XY' and f in existing_fields]

    # Sample coordinates
    samples = []
    with arcpy.da.SearchCursor(gold_buildings, query_fields,
                               where_clause=f"source = '{source}'") as cursor:
        for i, row in enumerate(cursor):
            if i >= 3:
                break
            samples.append(row)

    if samples:
        print(f"   Sample coordinates (first 3 records):")
        for i, sample in enumerate(samples):
            shape_xy = sample[0]
            print(f"   Record {i+1}:")
            print(f"      SHAPE@XY: {shape_xy}")
            for j, field in enumerate(query_fields[1:], 1):
                val = sample[j]
                status = "✅" if val is not None else "❌ NULL"
                print(f"      {field}: {val} {status}")
    else:
        print(f"   ❌ No records found!")

# ============================================================================
# SECTION 6: RECOMMENDATIONS
# ============================================================================
print("\n" + "="*80)
print("SECTION 6: AUDIT FINDINGS & RECOMMENDATIONS")
print("="*80)

# Analyze findings
issues = []
recommendations = []

# Check Semianalysis completeness
semi_issues = []
for field in ['latitude', 'longitude', 'company_clean', 'city', 'state']:
    if field in completeness.get('Semianalysis', {}):
        pct = completeness['Semianalysis'][field]
        if pct < 50:
            semi_issues.append(f"{field} ({pct:.0f}% complete)")

if semi_issues:
    issues.append(f"Semianalysis missing critical fields: {', '.join(semi_issues)}")
    recommendations.append("Re-run Semianalysis ingestion script with complete field mapping")

# Check if gold_lat/gold_lon exist and are populated
gold_coord_fields = [f for f in existing_fields if 'gold_lat' in f.lower() or 'gold_lon' in f.lower()]
if gold_coord_fields:
    print(f"\n🔍 Found gold coordinate fields: {gold_coord_fields}")
    recommendations.append(f"Use {gold_coord_fields} for spatial analysis if latitude/longitude are NULL")

# Check SHAPE geometry
print("\n📋 ISSUES FOUND:")
if issues:
    for i, issue in enumerate(issues, 1):
        print(f"   {i}. ❌ {issue}")
else:
    print("   ✅ No critical issues found")

print("\n💡 RECOMMENDATIONS:")
if recommendations:
    for i, rec in enumerate(recommendations, 1):
        print(f"   {i}. {rec}")

# Coordinate field recommendation
print("\n🎯 RECOMMENDED COORDINATE FIELDS FOR SPATIAL ANALYSIS:")

# Priority order for coordinates
coord_priority = [
    ('gold_lat', 'gold_lon'),
    ('gold_lat', 'gold_long'),
    ('latitude', 'longitude'),
    ('lat', 'lon'),
    ('SHAPE@Y', 'SHAPE@X')
]

for lat_field, lon_field in coord_priority:
    if lat_field in existing_fields and lon_field in existing_fields:
        print(f"   ✅ Primary: {lat_field}, {lon_field}")
        break
    elif lat_field == 'SHAPE@Y':
        print(f"   ✅ Fallback: SHAPE@XY (geometry-based)")
        break

print("\n" + "="*80)
print("AUDIT COMPLETE")
print("="*80)

# Export audit results
audit_csv = gdb_path.replace('.gdb', f'_audit_results_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv')

# Create summary dataframe
audit_summary = []
for source in sorted(sources):
    row = {'source': source, 'count': completeness[source]['_count']}
    for field in fields_to_check[1:]:
        row[field] = completeness[source].get(field, 0)
    audit_summary.append(row)

audit_df = pd.DataFrame(audit_summary)
audit_df.to_csv(audit_csv, index=False)
print(f"\n📊 Audit results exported to: {audit_csv}")
