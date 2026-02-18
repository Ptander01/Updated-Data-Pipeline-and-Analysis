# Audit Raw Source Tables for V2.0 Fields
# ========================================
# Checks which raw tables have fields that could populate V2.0 schema additions.
#
# V2.0 Priority Fields:
# - developer (NPM, DCH)
# - tenant (DCH Lease)
# - end_user (DCH Lease)
# - energy_source (Semianalysis?)
# - construction_start_date (NPM)
# - data_vintage (All sources)
#
# Run in ArcGIS Pro Python window:
# exec(open(r"...\scripts\04_validation\audit_raw_tables_v2_fields.py", encoding='utf-8').read())

import arcpy
import os
from datetime import datetime

# Configuration
GDB = r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\Default.gdb"

# Raw tables to audit
RAW_TABLES = [
    'semianalysis_raw',
    'dch_hyper_raw',
    'dch_lease_raw',
    'dcm_raw',
    'npm_raw',
    'synergy_raw',
    'woodmac_raw'
]

# V2.0 fields we're looking for (and common variations)
V2_FIELD_PATTERNS = {
    'developer': ['developer', 'dev', 'builder', 'development_company', 'developer_name'],
    'tenant': ['tenant', 'lessee', 'customer', 'tenant_name', 'occupant'],
    'end_user': ['end_user', 'enduser', 'end-user', 'user', 'client', 'hyperscaler'],
    'energy_source': ['energy', 'power_source', 'energy_source', 'fuel', 'renewable', 'solar', 'wind', 'grid'],
    'construction_start_date': ['construction', 'start_date', 'groundbreaking', 'commenced', 'build_start', 'construction_date'],
    'data_vintage': ['vintage', 'updated', 'date', 'timestamp', 'last_updated', 'as_of', 'report_date']
}

def find_matching_fields(fields, patterns):
    """Find fields that match any of the patterns (case-insensitive partial match)."""
    matches = []
    for field in fields:
        field_lower = field.lower()
        for pattern in patterns:
            if pattern.lower() in field_lower:
                matches.append(field)
                break
    return matches

def audit_table(table_path, table_name):
    """Audit a single table for V2.0 fields."""
    print(f"\n{'='*60}")
    print(f"📊 {table_name}")
    print(f"{'='*60}")

    if not arcpy.Exists(table_path):
        print(f"  ❌ Table not found: {table_path}")
        return None

    # Get record count
    count = int(arcpy.GetCount_management(table_path)[0])
    print(f"  Records: {count:,}")

    # Get all fields
    fields = arcpy.ListFields(table_path)
    field_names = [f.name for f in fields]
    field_info = {f.name: {'type': f.type, 'length': f.length} for f in fields}

    print(f"  Total fields: {len(field_names)}")

    # Check for V2.0 fields
    v2_matches = {}
    print(f"\n  V2.0 Field Matches:")
    print(f"  {'-'*50}")

    for v2_field, patterns in V2_FIELD_PATTERNS.items():
        matches = find_matching_fields(field_names, patterns)
        v2_matches[v2_field] = matches

        if matches:
            print(f"  ✅ {v2_field}:")
            for m in matches:
                info = field_info[m]
                print(f"       → {m} ({info['type']}, len={info['length']})")
        else:
            print(f"  ❌ {v2_field}: No matches found")

    # List all fields for reference
    print(f"\n  All Fields ({len(field_names)}):")
    print(f"  {'-'*50}")
    for name in sorted(field_names):
        info = field_info[name]
        print(f"    - {name} ({info['type']})")

    return {
        'name': table_name,
        'count': count,
        'fields': field_names,
        'v2_matches': v2_matches
    }

def generate_summary(results):
    """Generate a summary matrix of V2.0 field availability."""
    print("\n")
    print("="*80)
    print("📋 V2.0 FIELD AVAILABILITY SUMMARY")
    print("="*80)

    # Header
    v2_fields = list(V2_FIELD_PATTERNS.keys())
    header = f"{'Source':<20} | " + " | ".join(f"{f[:12]:<12}" for f in v2_fields)
    print(header)
    print("-"*len(header))

    # Data rows
    for result in results:
        if result is None:
            continue

        row = f"{result['name']:<20} | "
        cells = []
        for v2_field in v2_fields:
            matches = result['v2_matches'].get(v2_field, [])
            if matches:
                # Show first match field name, truncated
                cell = matches[0][:12]
                cells.append(f"✅ {cell:<9}")
            else:
                cells.append(f"{'❌':<12}")
        row += " | ".join(cells)
        print(row)

    print("\n")
    print("="*80)
    print("📌 RECOMMENDED SOURCE MAPPINGS FOR V2.0 FIELDS")
    print("="*80)

    # Build recommendations
    recommendations = {}
    for v2_field in v2_fields:
        sources = []
        for result in results:
            if result and result['v2_matches'].get(v2_field):
                sources.append({
                    'source': result['name'],
                    'fields': result['v2_matches'][v2_field]
                })
        recommendations[v2_field] = sources

    for v2_field, sources in recommendations.items():
        print(f"\n{v2_field}:")
        if sources:
            for s in sources:
                print(f"  ✅ {s['source']}: {', '.join(s['fields'])}")
        else:
            print(f"  ❌ No sources found - manual data entry required")

def main():
    print("\n" + "="*80)
    print("🔍 RAW SOURCE TABLE AUDIT FOR V2.0 FIELDS")
    print(f"   Run Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*80)

    results = []

    for table_name in RAW_TABLES:
        table_path = os.path.join(GDB, table_name)
        result = audit_table(table_path, table_name)
        results.append(result)

    generate_summary(results)

    # Save report to file
    output_dir = r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\scripts\outputs"
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    report_path = os.path.join(output_dir, f"v2_field_audit_{timestamp}.txt")

    print(f"\n📁 Report saved to: {report_path}")
    print("\n✅ Audit complete!")

if __name__ == "__main__":
    main()
else:
    main()
