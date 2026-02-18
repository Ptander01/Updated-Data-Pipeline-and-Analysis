"""
Meta Canonical Data Quality Validation
======================================

Purpose:
Validates the new Meta Canonical dataset before running the full pipeline.
Analyzes data quality at suite, building, and campus levels to determine
if the 3x increase in records and 7x increase in capacity is legitimate.

Key Metrics to Validate:
- Total records: 3,400 suites → 643 buildings
- Total capacity: ~17.2 GW (up from ~2.5 GW)
- Quality flags for null status, null capacity, coordinate coverage

Run in ArcGIS Pro Python window:
exec(open(r"C:\\Users\\ptanderson\\Documents\\ArcGIS\\Projects\\Lean Consensus DC Model\\scripts\\04_validation\\validate_meta_canonical.py", encoding='utf-8').read())

Author: DC GIS Team
Created: January 30, 2026
"""

import arcpy
import os
import sys
from datetime import datetime
from collections import defaultdict

# Add _utils to path for config import
try:
    script_dir = os.path.dirname(os.path.abspath(__file__))
except NameError:
    script_dir = r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\scripts\04_validation"

utils_dir = os.path.join(os.path.dirname(script_dir), "_utils")
if utils_dir not in sys.path:
    sys.path.insert(0, utils_dir)

from config import GDB, META_CANONICAL_V2, META_CANONICAL_BUILDINGS, META_CANONICAL_CAMPUS

arcpy.env.workspace = GDB

# ============================================================================
# CONFIGURATION
# ============================================================================

# Previous dataset metrics for comparison
PREVIOUS_METRICS = {
    'suites': 1218,
    'buildings': 318,
    'capacity_mw': 2500
}

# Quality thresholds
THRESHOLDS = {
    'null_status_red': 0.50,      # >50% null status = RED FLAG
    'null_capacity_red': 0.50,    # >50% null IT load = RED FLAG
    'coord_coverage_yellow': 0.50, # <50% coordinates = YELLOW FLAG
    'future_capacity_red': 0.80,  # >80% future/null capacity = RED FLAG
}

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def format_mw(value):
    """Format MW value with commas."""
    if value is None:
        return "N/A"
    return f"{value:,.1f}"

def format_pct(value):
    """Format percentage value."""
    if value is None:
        return "N/A"
    return f"{value:.1f}%"

def get_flag(value, threshold, comparison='gt', invert=False):
    """
    Get quality flag emoji based on threshold.
    comparison: 'gt' (greater than) or 'lt' (less than)
    invert: if True, passing = below threshold for 'gt', above for 'lt'
    """
    if value is None:
        return "❓"

    if comparison == 'gt':
        is_bad = value > threshold
    else:  # 'lt'
        is_bad = value < threshold

    if invert:
        is_bad = not is_bad

    if is_bad:
        return "❌"
    elif comparison == 'gt' and value > threshold * 0.7:
        return "⚠️"
    elif comparison == 'lt' and value < threshold * 1.3:
        return "⚠️"
    else:
        return "✅"

def check_table_exists(table_path, table_name):
    """Check if table exists and return record count."""
    if not arcpy.Exists(table_path):
        print(f"   ❌ {table_name} NOT FOUND: {table_path}")
        return None
    return int(arcpy.management.GetCount(table_path)[0])

def get_field_names(table_path):
    """Get list of field names in table."""
    return [f.name for f in arcpy.ListFields(table_path)]

# ============================================================================
# SUITE-LEVEL ANALYSIS
# ============================================================================

def analyze_suites():
    """Analyze suite-level data quality in meta_canonical_v2."""
    print("\n" + "=" * 70)
    print("   1. SUITE-LEVEL ANALYSIS (meta_canonical_v2)")
    print("=" * 70)

    count = check_table_exists(META_CANONICAL_V2, "meta_canonical_v2")
    if count is None:
        return None

    fields = get_field_names(META_CANONICAL_V2)
    print(f"\n   Total Records: {count:,}")

    # Identify key fields
    it_load_field = 'it_load' if 'it_load' in fields else None
    status_field = 'new_build_status' if 'new_build_status' in fields else None
    dc_code_field = 'dc_code' if 'dc_code' in fields else None
    building_key_field = 'building_key' if 'building_key' in fields else None
    region_field = 'region_derived' if 'region_derived' in fields else ('region' if 'region' in fields else None)

    # Check if this is a feature class with geometry
    desc = arcpy.Describe(META_CANONICAL_V2)
    has_geometry = hasattr(desc, 'shapeType')
    if has_geometry:
        print(f"   Feature Class Type: {desc.shapeType}")

    # Build read fields list
    read_fields = []
    field_map = {}

    for name, field in [('it_load', it_load_field), ('status', status_field),
                         ('dc_code', dc_code_field), ('building_key', building_key_field),
                         ('region', region_field)]:
        if field:
            field_map[name] = len(read_fields)
            read_fields.append(field)

    # Add geometry field if available (SHAPE@XY returns tuple of x,y coordinates)
    if has_geometry:
        field_map['shape_xy'] = len(read_fields)
        read_fields.append('SHAPE@XY')

    # Initialize counters
    results = {
        'total_suites': count,
        'with_valid_status': 0,
        'with_it_load': 0,
        'with_coordinates': 0,
        'status_distribution': defaultdict(int),
        'capacity_by_status': defaultdict(float),
        'total_capacity_mw': 0,
        'unique_dc_codes': set(),
        'unique_building_keys': set(),
        'suites_by_building': defaultdict(int),
        'regions_no_coords': defaultdict(int),
        'capacity_with_coords': 0,
        'capacity_without_coords': 0,
    }

    # Read all suite records
    with arcpy.da.SearchCursor(META_CANONICAL_V2, read_fields) as cursor:
        for row in cursor:
            # Extract values using field map
            it_load = row[field_map['it_load']] if 'it_load' in field_map else None
            status = row[field_map['status']] if 'status' in field_map else None
            dc_code = row[field_map['dc_code']] if 'dc_code' in field_map else None
            building_key = row[field_map['building_key']] if 'building_key' in field_map else None
            region = row[field_map['region']] if 'region' in field_map else None

            # Extract coordinates from geometry (SHAPE@XY returns tuple of x, y)
            shape_xy = row[field_map['shape_xy']] if 'shape_xy' in field_map else None
            if shape_xy:
                lon, lat = shape_xy  # SHAPE@XY returns (x, y) = (longitude, latitude)
            else:
                lon, lat = None, None

            # Status analysis
            if status and str(status).strip():
                results['with_valid_status'] += 1
                status_clean = str(status).strip()
            else:
                status_clean = 'NULL/Empty'
            results['status_distribution'][status_clean] += 1

            # IT Load analysis
            if it_load is not None and it_load > 0:
                results['with_it_load'] += 1
                results['total_capacity_mw'] += it_load
                results['capacity_by_status'][status_clean] += it_load

            # Coordinate analysis (from geometry)
            has_coords = (lat is not None and lon is not None and
                         lat != 0 and lon != 0 and
                         abs(lat) > 0.01 and abs(lon) > 0.01)

            if has_coords:
                results['with_coordinates'] += 1
                if it_load:
                    results['capacity_with_coords'] += it_load
            else:
                if region:
                    results['regions_no_coords'][region] += 1
                if it_load:
                    results['capacity_without_coords'] += it_load

            # Campus/Building tracking
            if dc_code:
                results['unique_dc_codes'].add(dc_code)
            if building_key:
                results['unique_building_keys'].add(building_key)
                results['suites_by_building'][building_key] += 1

    # Print suite summary
    print(f"\n   {'─' * 66}")
    print(f"   FIELD COVERAGE")
    print(f"   {'─' * 66}")

    status_rate = results['with_valid_status'] / count * 100 if count else 0
    it_load_rate = results['with_it_load'] / count * 100 if count else 0
    coord_rate = results['with_coordinates'] / count * 100 if count else 0

    print(f"   {'Metric':<35} {'Count':>12} {'Percentage':>12}")
    print(f"   {'─' * 66}")
    print(f"   {'Records with valid status':<35} {results['with_valid_status']:>12,} {status_rate:>11.1f}%")
    print(f"   {'Records with IT load (>0)':<35} {results['with_it_load']:>12,} {it_load_rate:>11.1f}%")
    print(f"   {'Records with coordinates':<35} {results['with_coordinates']:>12,} {coord_rate:>11.1f}%")

    # Status distribution
    print(f"\n   {'─' * 66}")
    print(f"   STATUS DISTRIBUTION")
    print(f"   {'─' * 66}")
    print(f"   {'Status':<30} {'Count':>12} {'Percentage':>12}")
    print(f"   {'─' * 66}")

    for status in sorted(results['status_distribution'].keys()):
        count_val = results['status_distribution'][status]
        pct = count_val / count * 100 if count else 0
        print(f"   {status:<30} {count_val:>12,} {pct:>11.1f}%")

    return results

# ============================================================================
# CAPACITY ANALYSIS
# ============================================================================

def analyze_capacity(suite_results):
    """Analyze capacity breakdown by status."""
    print("\n" + "=" * 70)
    print("   2. CAPACITY ANALYSIS")
    print("=" * 70)

    if not suite_results:
        print("   ❌ No suite data available")
        return None

    total_mw = suite_results['total_capacity_mw']
    capacity_by_status = suite_results['capacity_by_status']

    print(f"\n   {'─' * 66}")
    print(f"   CAPACITY BY BUILD STATUS")
    print(f"   {'─' * 66}")
    print(f"   {'Status':<30} {'Capacity (MW)':>15} {'Percentage':>12}")
    print(f"   {'─' * 66}")

    # Define status order
    status_order = ['Complete Build', 'Active Build', 'Future Build', 'NULL/Empty']

    real_capacity = 0  # Complete + Active
    future_unknown = 0  # Future + NULL

    for status in status_order:
        cap = capacity_by_status.get(status, 0)
        pct = (cap / total_mw * 100) if total_mw > 0 else 0

        if status in ['Complete Build', 'Active Build']:
            real_capacity += cap
        else:
            future_unknown += cap

        print(f"   {status:<30} {cap:>15,.1f} {pct:>11.1f}%")

    # Other statuses not in order
    other_statuses = [s for s in capacity_by_status.keys() if s not in status_order]
    for status in sorted(other_statuses):
        cap = capacity_by_status[status]
        pct = (cap / total_mw * 100) if total_mw > 0 else 0
        future_unknown += cap
        print(f"   {status:<30} {cap:>15,.1f} {pct:>11.1f}%")

    print(f"   {'─' * 66}")
    print(f"   {'TOTAL':<30} {total_mw:>15,.1f} {'100.0%':>12}")

    # Capacity classification
    print(f"\n   {'─' * 66}")
    print(f"   CAPACITY CLASSIFICATION")
    print(f"   {'─' * 66}")

    real_pct = (real_capacity / total_mw * 100) if total_mw > 0 else 0
    future_pct = (future_unknown / total_mw * 100) if total_mw > 0 else 0

    print(f"   {'Operational (Complete + Active)':<35} {real_capacity:>12,.1f} MW ({real_pct:.1f}%)")
    print(f"   {'Future/Unknown (Future + NULL)':<35} {future_unknown:>12,.1f} MW ({future_pct:.1f}%)")

    # Coordinate coverage for capacity
    cap_with_coords = suite_results['capacity_with_coords']
    cap_without_coords = suite_results['capacity_without_coords']
    coord_cap_pct = (cap_with_coords / total_mw * 100) if total_mw > 0 else 0

    print(f"\n   {'─' * 66}")
    print(f"   CAPACITY BY COORDINATE COVERAGE")
    print(f"   {'─' * 66}")
    print(f"   {'Capacity with coordinates':<35} {cap_with_coords:>12,.1f} MW ({coord_cap_pct:.1f}%)")
    print(f"   {'Capacity without coordinates':<35} {cap_without_coords:>12,.1f} MW ({100-coord_cap_pct:.1f}%)")

    return {
        'total_mw': total_mw,
        'real_capacity_mw': real_capacity,
        'future_unknown_mw': future_unknown,
        'real_pct': real_pct,
        'future_pct': future_pct,
        'coord_coverage_pct': coord_cap_pct
    }

# ============================================================================
# CAMPUS/BUILDING ANALYSIS
# ============================================================================

def analyze_campus_building(suite_results):
    """Analyze campus and building level metrics."""
    print("\n" + "=" * 70)
    print("   3. CAMPUS/BUILDING ANALYSIS")
    print("=" * 70)

    if not suite_results:
        print("   ❌ No suite data available")
        return None

    unique_dc_codes = suite_results['unique_dc_codes']
    unique_buildings = suite_results['unique_building_keys']
    suites_by_building = suite_results['suites_by_building']
    total_suites = suite_results['total_suites']

    num_campuses = len(unique_dc_codes)
    num_buildings = len(unique_buildings)

    avg_suites_per_building = total_suites / num_buildings if num_buildings > 0 else 0
    avg_buildings_per_campus = num_buildings / num_campuses if num_campuses > 0 else 0

    print(f"\n   {'─' * 66}")
    print(f"   HIERARCHY COUNTS")
    print(f"   {'─' * 66}")
    print(f"   {'Unique campuses (dc_code)':<35} {num_campuses:>12,}")
    print(f"   {'Unique buildings (building_key)':<35} {num_buildings:>12,}")
    print(f"   {'Total suites':<35} {total_suites:>12,}")

    print(f"\n   {'─' * 66}")
    print(f"   AVERAGES")
    print(f"   {'─' * 66}")
    print(f"   {'Avg suites per building':<35} {avg_suites_per_building:>12.1f}")
    print(f"   {'Avg buildings per campus':<35} {avg_buildings_per_campus:>12.1f}")

    # Suite count distribution
    suite_counts = list(suites_by_building.values())
    if suite_counts:
        max_suites = max(suite_counts)
        min_suites = min(suite_counts)
        single_suite_buildings = sum(1 for c in suite_counts if c == 1)
        multi_suite_buildings = sum(1 for c in suite_counts if c > 1)

        print(f"\n   {'─' * 66}")
        print(f"   SUITE DISTRIBUTION PER BUILDING")
        print(f"   {'─' * 66}")
        print(f"   {'Min suites in a building':<35} {min_suites:>12}")
        print(f"   {'Max suites in a building':<35} {max_suites:>12}")
        print(f"   {'Buildings with 1 suite':<35} {single_suite_buildings:>12,}")
        print(f"   {'Buildings with >1 suite':<35} {multi_suite_buildings:>12,}")

    # Check buildings table if exists
    bldg_count = check_table_exists(META_CANONICAL_BUILDINGS, "meta_canonical_buildings")
    if bldg_count:
        print(f"\n   {'─' * 66}")
        print(f"   BUILDING TABLE COMPARISON")
        print(f"   {'─' * 66}")
        print(f"   {'Buildings from suite data':<35} {num_buildings:>12,}")
        print(f"   {'Buildings in building table':<35} {bldg_count:>12,}")
        diff = abs(bldg_count - num_buildings)
        match_flag = "✅" if diff == 0 else "⚠️"
        print(f"   {'Difference':<35} {diff:>12,} {match_flag}")

    return {
        'num_campuses': num_campuses,
        'num_buildings': num_buildings,
        'avg_suites_per_building': avg_suites_per_building,
        'avg_buildings_per_campus': avg_buildings_per_campus
    }

# ============================================================================
# COORDINATE COVERAGE ANALYSIS
# ============================================================================

def analyze_coordinates(suite_results):
    """Analyze coordinate coverage by region."""
    print("\n" + "=" * 70)
    print("   4. COORDINATE COVERAGE ANALYSIS")
    print("=" * 70)

    if not suite_results:
        print("   ❌ No suite data available")
        return None

    total = suite_results['total_suites']
    with_coords = suite_results['with_coordinates']
    without_coords = total - with_coords
    coord_pct = (with_coords / total * 100) if total > 0 else 0

    print(f"\n   {'─' * 66}")
    print(f"   OVERALL COORDINATE COVERAGE")
    print(f"   {'─' * 66}")
    print(f"   {'Records with valid coordinates':<35} {with_coords:>12,} ({coord_pct:.1f}%)")
    print(f"   {'Records without coordinates':<35} {without_coords:>12,} ({100-coord_pct:.1f}%)")

    # By region
    regions_no_coords = suite_results['regions_no_coords']
    if regions_no_coords:
        print(f"\n   {'─' * 66}")
        print(f"   RECORDS WITHOUT COORDINATES BY REGION")
        print(f"   {'─' * 66}")
        print(f"   {'Region':<40} {'Count':>12}")
        print(f"   {'─' * 66}")

        for region in sorted(regions_no_coords.keys(), key=lambda r: regions_no_coords[r], reverse=True):
            count = regions_no_coords[region]
            print(f"   {str(region)[:40]:<40} {count:>12,}")

    return {
        'with_coords': with_coords,
        'without_coords': without_coords,
        'coord_coverage_pct': coord_pct
    }

# ============================================================================
# COMPARISON TO PREVIOUS DATASET
# ============================================================================

def compare_to_previous(suite_results, capacity_results, campus_results):
    """Compare new dataset to previous metrics."""
    print("\n" + "=" * 70)
    print("   5. COMPARISON TO PREVIOUS DATASET")
    print("=" * 70)

    if not suite_results or not capacity_results or not campus_results:
        print("   ❌ Insufficient data for comparison")
        return None

    prev = PREVIOUS_METRICS

    print(f"\n   {'─' * 66}")
    print(f"   {'Metric':<25} {'Previous':>15} {'Current':>15} {'Change':>12}")
    print(f"   {'─' * 66}")

    # Suites
    prev_suites = prev['suites']
    curr_suites = suite_results['total_suites']
    suite_change = ((curr_suites - prev_suites) / prev_suites * 100) if prev_suites > 0 else 0
    print(f"   {'Suites':<25} {prev_suites:>15,} {curr_suites:>15,} {suite_change:>+11.0f}%")

    # Buildings
    prev_buildings = prev['buildings']
    curr_buildings = campus_results['num_buildings']
    bldg_change = ((curr_buildings - prev_buildings) / prev_buildings * 100) if prev_buildings > 0 else 0
    print(f"   {'Buildings':<25} {prev_buildings:>15,} {curr_buildings:>15,} {bldg_change:>+11.0f}%")

    # Capacity
    prev_cap = prev['capacity_mw']
    curr_cap = capacity_results['total_mw']
    cap_change = ((curr_cap - prev_cap) / prev_cap * 100) if prev_cap > 0 else 0
    print(f"   {'Total Capacity (MW)':<25} {prev_cap:>15,.0f} {curr_cap:>15,.0f} {cap_change:>+11.0f}%")

    # Net new
    print(f"\n   {'─' * 66}")
    print(f"   NET NEW RECORDS")
    print(f"   {'─' * 66}")
    print(f"   {'Net new suites':<35} {curr_suites - prev_suites:>+12,}")
    print(f"   {'Net new buildings':<35} {curr_buildings - prev_buildings:>+12,}")
    print(f"   {'Net new capacity (MW)':<35} {curr_cap - prev_cap:>+12,.0f}")

    # Calculate multipliers
    print(f"\n   {'─' * 66}")
    print(f"   GROWTH MULTIPLIERS")
    print(f"   {'─' * 66}")
    suite_mult = curr_suites / prev_suites if prev_suites > 0 else 0
    bldg_mult = curr_buildings / prev_buildings if prev_buildings > 0 else 0
    cap_mult = curr_cap / prev_cap if prev_cap > 0 else 0
    print(f"   {'Suite count multiplier':<35} {suite_mult:>12.1f}x")
    print(f"   {'Building count multiplier':<35} {bldg_mult:>12.1f}x")
    print(f"   {'Capacity multiplier':<35} {cap_mult:>12.1f}x")

    return {
        'suite_multiplier': suite_mult,
        'building_multiplier': bldg_mult,
        'capacity_multiplier': cap_mult
    }

# ============================================================================
# QUALITY FLAGS AND RECOMMENDATION
# ============================================================================

def generate_quality_report(suite_results, capacity_results, coord_results, comparison_results):
    """Generate quality flags and recommendation."""
    print("\n" + "=" * 70)
    print("   QUALITY FLAGS & RECOMMENDATION")
    print("=" * 70)

    if not suite_results or not capacity_results or not coord_results:
        print("   ❌ Insufficient data for quality assessment")
        return None

    total = suite_results['total_suites']

    # Calculate rates
    null_status_rate = (total - suite_results['with_valid_status']) / total * 100 if total > 0 else 0
    null_capacity_rate = (total - suite_results['with_it_load']) / total * 100 if total > 0 else 0
    coord_coverage_rate = coord_results['coord_coverage_pct']
    future_unknown_rate = capacity_results['future_pct']

    # Generate flags
    flags = []
    issues_red = 0
    issues_yellow = 0

    print(f"\n   {'─' * 66}")
    print(f"   QUALITY CHECK RESULTS")
    print(f"   {'─' * 66}")

    # 1. Null Status Rate
    flag = get_flag(null_status_rate / 100, THRESHOLDS['null_status_red'], 'gt')
    status_text = f"Null Status Rate: {null_status_rate:.1f}%"
    if flag == "❌":
        issues_red += 1
        status_text += f" (threshold: <{THRESHOLDS['null_status_red']*100:.0f}%)"
    print(f"   {flag} {status_text}")
    flags.append(('null_status', flag, null_status_rate))

    # 2. Null Capacity Rate
    flag = get_flag(null_capacity_rate / 100, THRESHOLDS['null_capacity_red'], 'gt')
    cap_text = f"Null Capacity Rate: {null_capacity_rate:.1f}%"
    if flag == "❌":
        issues_red += 1
        cap_text += f" (threshold: <{THRESHOLDS['null_capacity_red']*100:.0f}%)"
    print(f"   {flag} {cap_text}")
    flags.append(('null_capacity', flag, null_capacity_rate))

    # 3. Coordinate Coverage
    flag = get_flag(coord_coverage_rate / 100, THRESHOLDS['coord_coverage_yellow'], 'lt')
    coord_text = f"Coordinate Coverage: {coord_coverage_rate:.1f}%"
    if flag == "❌" or flag == "⚠️":
        issues_yellow += 1
        coord_text += f" (threshold: >{THRESHOLDS['coord_coverage_yellow']*100:.0f}%)"
    print(f"   {flag} {coord_text}")
    flags.append(('coordinates', flag, coord_coverage_rate))

    # 4. Future/Unknown Capacity
    flag = get_flag(future_unknown_rate / 100, THRESHOLDS['future_capacity_red'], 'gt')
    future_text = f"Future/Unknown Capacity: {future_unknown_rate:.1f}%"
    if flag == "❌":
        issues_red += 1
        future_text += f" (threshold: <{THRESHOLDS['future_capacity_red']*100:.0f}%)"
    print(f"   {flag} {future_text}")
    flags.append(('future_capacity', flag, future_unknown_rate))

    # Determine recommendation
    print(f"\n   {'─' * 66}")

    if issues_red >= 2:
        recommendation = "RED - HOLD"
        rec_detail = "Multiple critical quality issues detected. Investigate source DAI query before proceeding."
        rec_emoji = "🛑"
    elif issues_red == 1:
        recommendation = "YELLOW - INVESTIGATE"
        rec_detail = "One critical issue detected. Review data source before proceeding with pipeline."
        rec_emoji = "⚠️"
    elif issues_yellow >= 2:
        recommendation = "YELLOW - CAUTION"
        rec_detail = "Known limitations present. Proceed with caution and document data gaps."
        rec_emoji = "⚠️"
    else:
        recommendation = "GREEN - PROCEED"
        rec_detail = "Data quality acceptable. Safe to proceed with full pipeline."
        rec_emoji = "✅"

    print(f"   {rec_emoji} RECOMMENDATION: {recommendation}")
    print(f"   {'─' * 66}")
    print(f"   {rec_detail}")

    return {
        'flags': flags,
        'issues_red': issues_red,
        'issues_yellow': issues_yellow,
        'recommendation': recommendation
    }

# ============================================================================
# MAIN REPORT
# ============================================================================

def generate_summary_report(suite_results, capacity_results, campus_results, coord_results, comparison_results, quality_results):
    """Generate final summary report."""
    print("\n")
    print("╔" + "═" * 68 + "╗")
    print("║" + " " * 15 + "META CANONICAL DATA QUALITY REPORT" + " " * 18 + "║")
    print("╚" + "═" * 68 + "╝")
    print(f"\n   Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    if not suite_results:
        print("\n   ❌ REPORT GENERATION FAILED - No data available")
        return

    # Summary Table
    print("\n" + "═" * 70)
    print("   EXECUTIVE SUMMARY")
    print("═" * 70)

    print(f"\n   {'SUITE-LEVEL METRICS':<40}")
    print(f"   {'─' * 50}")
    print(f"   Total Suites:              {suite_results['total_suites']:>15,}")
    print(f"   With Valid Status:         {suite_results['with_valid_status']:>15,} ({suite_results['with_valid_status']/suite_results['total_suites']*100:.0f}%)")
    print(f"   With IT Load:              {suite_results['with_it_load']:>15,} ({suite_results['with_it_load']/suite_results['total_suites']*100:.0f}%)")
    print(f"   With Coordinates:          {suite_results['with_coordinates']:>15,} ({suite_results['with_coordinates']/suite_results['total_suites']*100:.0f}%)")

    if capacity_results:
        print(f"\n   {'CAPACITY BY STATUS':<40}")
        print(f"   {'─' * 50}")
        for status in ['Complete Build', 'Active Build', 'Future Build', 'NULL/Empty']:
            cap = suite_results['capacity_by_status'].get(status, 0)
            pct = (cap / capacity_results['total_mw'] * 100) if capacity_results['total_mw'] > 0 else 0
            print(f"   {status + ':':<25} {cap:>12,.0f} MW ({pct:.0f}%)")
        print(f"   {'─' * 50}")
        print(f"   {'TOTAL:':<25} {capacity_results['total_mw']:>12,.0f} MW")

    if campus_results:
        print(f"\n   {'HIERARCHY':<40}")
        print(f"   {'─' * 50}")
        print(f"   Campuses (dc_code):        {campus_results['num_campuses']:>15,}")
        print(f"   Buildings (building_key):  {campus_results['num_buildings']:>15,}")
        print(f"   Avg Suites/Building:       {campus_results['avg_suites_per_building']:>15.1f}")

    # Quality flags
    if quality_results:
        print(f"\n   {'QUALITY FLAGS':<40}")
        print(f"   {'─' * 50}")
        for name, flag, value in quality_results['flags']:
            print(f"   {flag} {name.replace('_', ' ').title()}: {value:.1f}%")

        print(f"\n   {'─' * 50}")
        print(f"   📋 RECOMMENDATION: {quality_results['recommendation']}")

    print("\n" + "═" * 70)

# ============================================================================
# MAIN EXECUTION
# ============================================================================

def main():
    """Main validation function."""
    print("\n")
    print("╔" + "═" * 68 + "╗")
    print("║" + " " * 10 + "META CANONICAL DATA QUALITY VALIDATION" + " " * 10 + "║")
    print("║" + " " * 10 + "Pre-Pipeline Data Quality Assessment" + " " * 12 + "║")
    print("╚" + "═" * 68 + "╝")
    print(f"\n   Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"   GDB: {GDB}")
    print(f"   Target: meta_canonical_v2")

    # Run all analyses
    suite_results = analyze_suites()
    capacity_results = analyze_capacity(suite_results)
    campus_results = analyze_campus_building(suite_results)
    coord_results = analyze_coordinates(suite_results)
    comparison_results = compare_to_previous(suite_results, capacity_results, campus_results)
    quality_results = generate_quality_report(suite_results, capacity_results, coord_results, comparison_results)

    # Generate summary
    generate_summary_report(suite_results, capacity_results, campus_results, coord_results, comparison_results, quality_results)

    print(f"\n   Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

    return quality_results

# ============================================================================
# EXECUTE
# ============================================================================

if __name__ == "__main__":
    result = main()
else:
    result = main()
