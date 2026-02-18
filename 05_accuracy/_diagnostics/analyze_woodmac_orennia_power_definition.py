"""
WoodMac & Orennia Power Definition Analysis
Determines whether these sources report IT capacity or Facility power.

Methodology:
1. Find overlapping Meta facilities across sources
2. Compare reported capacity values against Meta canonical IT load
3. Test with and without PUE adjustment to determine power definition

IMPORTANT: Meta Canonical Filters Applied (Apples-to-Apples):
- build_status = 'Complete Build' (operational only, excludes Active/Future Build)
- it_load_total > 0 (excludes placeholder records)
- has_coordinates = 1 (excludes unlocated records)

Author: Meta Data Center GIS Team
Date: 2026-02-18
"""

import arcpy
import os
from datetime import datetime
from collections import defaultdict

# ============================================================================
# CONFIGURATION
# ============================================================================

# Use Default.gdb (correct path from config.py)
GDB = r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\Default.gdb"
GOLD_BUILDINGS = os.path.join(GDB, "gold_buildings_full")
META_CANONICAL = os.path.join(GDB, "meta_canonical_buildings")

# PUE values to test
PUE_VALUES = [1.0, 1.2, 1.3, 1.4]

# Meta Canonical filters for apples-to-apples comparison
# Only compare against operational facilities with actual IT load values
META_CANONICAL_FILTERS = {
    'build_status': 'Complete Build',  # Only operational (exclude Active Build, Future Build)
    'min_it_load': 0.1,                # Exclude placeholder records (it_load > 0.1 MW)
    'require_coords': True,            # Exclude unlocated records
}

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def safe_float(val):
    if val is None:
        return 0.0
    try:
        return float(val)
    except:
        return 0.0

def calculate_mape(actual_values, predicted_values):
    """Calculate Mean Absolute Percentage Error."""
    if not actual_values or not predicted_values:
        return None

    errors = []
    for actual, predicted in zip(actual_values, predicted_values):
        if actual and actual > 0:
            error = abs(actual - predicted) / actual * 100
            errors.append(error)

    return sum(errors) / len(errors) if errors else None

def calculate_ratio(vendor_values, meta_values):
    """Calculate average vendor/meta ratio."""
    ratios = []
    for v, m in zip(vendor_values, meta_values):
        if m and m > 0 and v and v > 0:
            ratios.append(v / m)
    return sum(ratios) / len(ratios) if ratios else None

# ============================================================================
# MAIN ANALYSIS
# ============================================================================

def main():
    print("=" * 80)
    print("WOODMAC & ORENNIA POWER DEFINITION ANALYSIS")
    print(f"Started: {datetime.now()}")
    print("=" * 80)

    print("\n📋 META CANONICAL FILTERS (Apples-to-Apples):")
    print(f"   • build_status = '{META_CANONICAL_FILTERS['build_status']}' (operational only)")
    print(f"   • it_load_total > {META_CANONICAL_FILTERS['min_it_load']} MW (exclude placeholders)")
    print(f"   • has_coordinates = 1 (exclude unlocated records)")

    # Step 1: Get Meta canonical data by dc_code WITH FILTERS
    print("\n[1] Loading Meta Canonical IT Load data (filtered)...")
    meta_by_code = {}

    # Check available fields first
    meta_field_names = [f.name for f in arcpy.ListFields(META_CANONICAL)]
    print(f"   Available fields: {meta_field_names[:10]}...")  # Show first 10

    # Determine which fields to use based on what exists
    if 'new_build_status' in meta_field_names:
        status_field = 'new_build_status'
    elif 'build_status' in meta_field_names:
        status_field = 'build_status'
    else:
        status_field = None
        print("   ⚠️ No build status field found - will not filter by status")

    if 'has_coordinates' in meta_field_names:
        coords_field = 'has_coordinates'
    else:
        coords_field = None
        print("   ⚠️ No has_coordinates field - will check lat/lon instead")

    # Build the query with appropriate fields
    meta_fields = ['dc_code', 'it_load_total']
    if 'building_name' in meta_field_names:
        meta_fields.append('building_name')
    if 'building_key' in meta_field_names:
        meta_fields.append('building_key')
    if status_field:
        meta_fields.append(status_field)
    if coords_field:
        meta_fields.append(coords_field)
    if 'SHAPE@XY' not in meta_fields and coords_field is None:
        meta_fields.append('SHAPE@XY')

    # Build WHERE clause for filtering
    where_parts = []
    where_parts.append(f"it_load_total > {META_CANONICAL_FILTERS['min_it_load']}")

    if status_field:
        where_parts.append(f"{status_field} = '{META_CANONICAL_FILTERS['build_status']}'")

    if coords_field:
        where_parts.append(f"{coords_field} = 1")

    where_clause = " AND ".join(where_parts)
    print(f"   WHERE: {where_clause}")

    # Track stats
    total_records = 0
    filtered_records = 0

    with arcpy.da.SearchCursor(META_CANONICAL, meta_fields, where_clause) as cursor:
        for row in cursor:
            filtered_records += 1
            dc_code = row[0]
            it_load = row[1]

            if dc_code and it_load and it_load > 0:
                # Aggregate by dc_code (campus level) for comparison
                if dc_code not in meta_by_code:
                    meta_by_code[dc_code] = {
                        'name': row[2] if len(row) > 2 else dc_code,
                        'it_load': it_load,
                        'status': row[meta_fields.index(status_field)] if status_field else 'Unknown',
                        'building_count': 1
                    }
                else:
                    # Sum IT load for multi-building campuses
                    meta_by_code[dc_code]['it_load'] += it_load
                    meta_by_code[dc_code]['building_count'] += 1

    # Get total count for comparison
    total_records = int(arcpy.GetCount_management(META_CANONICAL)[0])

    print(f"   Total Meta Canonical records: {total_records:,}")
    print(f"   After filtering: {filtered_records:,} records")
    print(f"   Unique campuses (dc_codes): {len(meta_by_code)}")

    total_it_load = sum(m['it_load'] for m in meta_by_code.values())
    print(f"   Total IT Load (filtered): {total_it_load:,.1f} MW")

    # Step 2: Get WoodMac Meta facilities
    print("\n[2] Loading WoodMac Meta facilities...")
    woodmac_meta = []
    wm_fields = ['unique_id', 'campus_name', 'full_capacity_mw', 'commissioned_power_mw',
                 'facility_status', 'latitude', 'longitude']
    wm_clause = "source = 'WoodMac' AND company_clean_filter = 'Meta'"

    with arcpy.da.SearchCursor(GOLD_BUILDINGS, wm_fields, wm_clause) as cursor:
        for row in cursor:
            woodmac_meta.append({
                'id': row[0],
                'name': row[1],
                'full_mw': safe_float(row[2]),
                'comm_mw': safe_float(row[3]),
                'status': row[4],
                'lat': row[5],
                'lon': row[6]
            })

    print(f"   Found {len(woodmac_meta)} WoodMac Meta facilities")

    # Step 3: Get Orennia Meta facilities
    print("\n[3] Loading Orennia Meta facilities...")
    orennia_meta = []
    or_fields = ['unique_id', 'campus_name', 'full_capacity_mw', 'commissioned_power_mw',
                 'facility_status', 'latitude', 'longitude']
    or_clause = "source = 'Orennia' AND company_clean_filter = 'Meta'"

    with arcpy.da.SearchCursor(GOLD_BUILDINGS, or_fields, or_clause) as cursor:
        for row in cursor:
            orennia_meta.append({
                'id': row[0],
                'name': row[1],
                'full_mw': safe_float(row[2]),
                'comm_mw': safe_float(row[3]),
                'status': row[4],
                'lat': row[5],
                'lon': row[6]
            })

    print(f"   Found {len(orennia_meta)} Orennia Meta facilities")

    # Step 4: Attempt name-based matching
    print("\n[4] Attempting name-based matching to Meta canonical...")

    # Try to match by looking for dc_code patterns in names
    dc_codes = list(meta_by_code.keys())

    woodmac_matches = []
    for wm in woodmac_meta:
        name = (wm['name'] or '').upper()
        for dc_code in dc_codes:
            # Check if dc_code appears in name (e.g., "PRN" in "Prineville Data Center")
            code_prefix = dc_code.split('-')[0] if '-' in dc_code else dc_code[:3]
            if code_prefix.upper() in name or dc_code.upper() in name:
                woodmac_matches.append({
                    'wm_name': wm['name'],
                    'dc_code': dc_code,
                    'wm_mw': wm['full_mw'] or wm['comm_mw'],
                    'meta_it': meta_by_code[dc_code]['it_load'],
                    'status': wm['status']
                })
                break

    orennia_matches = []
    for orn in orennia_meta:
        name = (orn['name'] or '').upper()
        for dc_code in dc_codes:
            code_prefix = dc_code.split('-')[0] if '-' in dc_code else dc_code[:3]
            if code_prefix.upper() in name or dc_code.upper() in name:
                orennia_matches.append({
                    'orn_name': orn['name'],
                    'dc_code': dc_code,
                    'orn_mw': orn['full_mw'] or orn['comm_mw'],
                    'meta_it': meta_by_code[dc_code]['it_load'],
                    'status': orn['status']
                })
                break

    print(f"   WoodMac matches: {len(woodmac_matches)}")
    print(f"   Orennia matches: {len(orennia_matches)}")

    # Step 5: Analyze WoodMac power definition
    print("\n" + "=" * 80)
    print("WOODMAC POWER DEFINITION ANALYSIS")
    print("=" * 80)

    if woodmac_matches:
        print("\nMatched Facilities:")
        print("-" * 80)
        print(f"{'WoodMac Name':<35} {'DC Code':<10} {'WM MW':>10} {'Meta IT':>10} {'Ratio':>8}")
        print("-" * 80)

        wm_vendor = []
        wm_meta = []

        for m in woodmac_matches:
            if m['wm_mw'] and m['meta_it']:
                ratio = m['wm_mw'] / m['meta_it']
                print(f"{m['wm_name'][:35]:<35} {m['dc_code']:<10} {m['wm_mw']:>10.1f} {m['meta_it']:>10.1f} {ratio:>8.2f}")
                wm_vendor.append(m['wm_mw'])
                wm_meta.append(m['meta_it'])

        print("-" * 80)

        # Test PUE adjustments
        print("\nPUE Adjustment Test:")
        print("-" * 40)

        for pue in PUE_VALUES:
            adjusted = [v / pue for v in wm_vendor]
            mape = calculate_mape(wm_meta, adjusted)
            avg_ratio = calculate_ratio(adjusted, wm_meta)

            if pue == 1.0:
                label = "No adjustment"
            else:
                label = f"÷{pue}"

            print(f"  PUE {pue:.1f} ({label}): MAPE = {mape:.1f}%, Ratio = {avg_ratio:.2f}" if mape else f"  PUE {pue:.1f}: N/A")

        # Conclusion
        print("\n📊 WOODMAC CONCLUSION:")
        base_ratio = calculate_ratio(wm_vendor, wm_meta)

        if base_ratio:
            if 0.8 <= base_ratio <= 1.2:
                print(f"   ✅ WoodMac likely reports IT CAPACITY (ratio {base_ratio:.2f}, no PUE adjustment needed)")
            elif base_ratio > 1.2:
                print(f"   ⚠️ WoodMac may report FACILITY POWER (ratio {base_ratio:.2f}, consider PUE adjustment)")
            else:
                print(f"   ⚠️ WoodMac under-reports capacity (ratio {base_ratio:.2f})")
    else:
        print("   ⚠️ No WoodMac matches found for comparison")

    # Step 6: Analyze Orennia power definition
    print("\n" + "=" * 80)
    print("ORENNIA POWER DEFINITION ANALYSIS")
    print("=" * 80)

    if orennia_matches:
        print("\nMatched Facilities:")
        print("-" * 80)
        print(f"{'Orennia Name':<35} {'DC Code':<10} {'Orn MW':>10} {'Meta IT':>10} {'Ratio':>8}")
        print("-" * 80)

        orn_vendor = []
        orn_meta = []

        for m in orennia_matches:
            if m['orn_mw'] and m['meta_it']:
                ratio = m['orn_mw'] / m['meta_it']
                print(f"{m['orn_name'][:35]:<35} {m['dc_code']:<10} {m['orn_mw']:>10.1f} {m['meta_it']:>10.1f} {ratio:>8.2f}")
                orn_vendor.append(m['orn_mw'])
                orn_meta.append(m['meta_it'])

        print("-" * 80)

        # Test PUE adjustments
        print("\nPUE Adjustment Test:")
        print("-" * 40)

        for pue in PUE_VALUES:
            adjusted = [v / pue for v in orn_vendor]
            mape = calculate_mape(orn_meta, adjusted)
            avg_ratio = calculate_ratio(adjusted, orn_meta)

            if pue == 1.0:
                label = "No adjustment"
            else:
                label = f"÷{pue}"

            print(f"  PUE {pue:.1f} ({label}): MAPE = {mape:.1f}%, Ratio = {avg_ratio:.2f}" if mape else f"  PUE {pue:.1f}: N/A")

        # Conclusion
        print("\n📊 ORENNIA CONCLUSION:")
        base_ratio = calculate_ratio(orn_vendor, orn_meta)

        if base_ratio:
            if 0.8 <= base_ratio <= 1.2:
                print(f"   ✅ Orennia likely reports IT CAPACITY (ratio {base_ratio:.2f}, no PUE adjustment needed)")
            elif base_ratio > 1.2:
                print(f"   ⚠️ Orennia may report FACILITY POWER (ratio {base_ratio:.2f}, consider PUE adjustment)")
            else:
                print(f"   ⚠️ Orennia under-reports capacity (ratio {base_ratio:.2f})")
    else:
        print("   ⚠️ No Orennia matches found for comparison")

    # Step 7: Summary of all sources
    print("\n" + "=" * 80)
    print("SUMMARY: ALL SOURCES")
    print("=" * 80)

    # Get counts by source
    source_counts = defaultdict(int)
    source_capacity = defaultdict(float)

    with arcpy.da.SearchCursor(GOLD_BUILDINGS, ['source', 'full_capacity_mw']) as cursor:
        for row in cursor:
            source = row[0] or 'Unknown'
            source_counts[source] += 1
            source_capacity[source] += safe_float(row[1])

    print("\nSource Overview:")
    print("-" * 60)
    print(f"{'Source':<20} {'Records':>12} {'Total Capacity':>15}")
    print("-" * 60)

    for source in sorted(source_counts.keys()):
        count = source_counts[source]
        capacity = source_capacity[source]
        print(f"{source:<20} {count:>12,} {capacity:>15,.0f} MW")

    print("-" * 60)

    print("\n" + "=" * 80)
    print(f"ANALYSIS COMPLETE: {datetime.now()}")
    print("=" * 80)

# ============================================================================
# EXECUTE
# ============================================================================

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
