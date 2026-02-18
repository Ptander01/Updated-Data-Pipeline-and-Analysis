"""
Deep Dive Campus Validation - Torture Test
Validates data integrity for high-profile data center campuses.

This script performs two key validations:
1. Building→Campus Aggregation: Ensures campus values correctly sum/aggregate from buildings
2. Meta Ground Truth Comparison: Compares Meta sites against meta_canonical_buildings
   - Now includes Semianalysis comparison (IT capacity, same definition as canonical)
   - Applies PUE adjustment to DCH Hyper (facility power → IT load estimate)

Target Sites:
- Meta campuses: Altoona, Prineville, Los Lunas, Eagle Mountain, New Albany
- Competitor AI projects: xAI Memphis (Colossus), Stargate, Project Rainier, Crusoe Abilene

Capacity Field Definitions:
- Meta canonical it_load_total: Actual IT server load (MW)
- Semianalysis mw_2024/commissioned_power_mw: IT capacity (MW) - SAME definition as Meta
- DCH Hyper commissioned_power_mw: Facility power capacity (MW) - divide by PUE for IT estimate
- DCM: Usually 0 MW for hyperscalers (location data only)

Author: Meta Data Center GIS Team
Last Updated: 2025-12-17 (v2 - Added Semianalysis, PUE adjustment)
"""

import arcpy
import os
import sys
from collections import defaultdict
from datetime import datetime
import csv

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

# Output directory
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(script_dir)), "outputs")
if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

# Feature class paths
META_CANONICAL = os.path.join(GDB, "meta_canonical_buildings")

# ============================================================================
# TARGET CAMPUSES FOR VALIDATION
# ============================================================================

# Meta campuses to validate against canonical data
# NOTE: dc_codes are Meta's internal 3-letter codes, not intuitive abbreviations
META_TARGETS = [
    # (search_pattern, dc_code for canonical match, display_name)
    ('Meta Altoona', 'ATN', 'Meta Altoona'),
    ('Meta Prineville', 'PRN', 'Meta Prineville'),
    ('Meta Los Lunas', 'LLA', 'Meta Los Lunas'),
    ('Meta Eagle Mountain', 'EAG', 'Meta Eagle Mountain'),
    ('Meta New Albany', 'NAB', 'Meta New Albany'),
    ('Meta Fort Worth', 'FTW', 'Meta Fort Worth'),
    ('Meta DeKalb', 'DKL', 'Meta DeKalb'),
    ('Meta Huntsville', 'HIL', 'Meta Huntsville'),
    ('Meta Mesa', 'MAZ', 'Meta Mesa'),
    ('Meta Gallatin', 'GTN', 'Meta Gallatin'),
]

# High-profile competitor campuses (no canonical comparison)
COMPETITOR_TARGETS = [
    # (search_pattern, display_name, notes)
    ('xAI_Memphis', 'xAI Memphis (Colossus)', 'xAI Colossus - largest AI training cluster'),
    ('Stargate', 'Stargate (OpenAI/SoftBank)', 'OpenAI Stargate - $500B AI infrastructure'),
    ('Project Rainier', 'Project Rainier (AWS)', 'AWS Project Rainier - major AI expansion'),
    ('Crusoe Abilene', 'Crusoe Abilene', 'Crusoe Energy - AI at stranded gas'),
    ('Vantages Abilene', 'Vantage Abilene', 'Vantage 1.4GW mega-campus'),
    ('Microsoft Boydton', 'Microsoft Boydton', 'Microsoft largest campus'),
    ('Google Council Bluffs', 'Google Council Bluffs', 'Google flagship'),
    ('AWS', 'AWS (various)', 'AWS hyperscale footprint'),
]

# Fields to aggregate and compare
CAPACITY_FIELDS = [
    'commissioned_power_mw',
    'uc_power_mw',
    'planned_power_mw',
    'full_capacity_mw',
]

MW_YEAR_FIELDS = [f'mw_{year}' for year in range(2023, 2033)]


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_buildings_for_campus(campus_pattern, company_filter=None):
    """Get all building records matching a campus pattern."""
    buildings = []

    where_clause = f"campus_name LIKE '%{campus_pattern}%'"
    if company_filter:
        where_clause += f" AND company_clean = '{company_filter}'"

    fields = ['unique_id', 'source', 'campus_name', 'building_designation',
              'company_clean', 'city', 'state', 'latitude', 'longitude',
              'facility_status', 'record_level'] + CAPACITY_FIELDS + MW_YEAR_FIELDS

    try:
        with arcpy.da.SearchCursor(GOLD_BUILDINGS, fields, where_clause) as cursor:
            for row in cursor:
                buildings.append(dict(zip(fields, row)))
    except Exception as e:
        print(f"    WARNING: Error querying buildings: {e}")

    return buildings


def get_campus_records(campus_pattern, company_filter=None):
    """Get campus records matching a pattern."""
    campuses = []

    where_clause = f"campus_name LIKE '%{campus_pattern}%'"
    if company_filter:
        where_clause += f" AND company_clean = '{company_filter}'"

    fields = ['campus_id', 'campus_name', 'company_clean', 'city', 'state',
              'building_count', 'source', 'facility_status_agg', 'latitude', 'longitude'] + CAPACITY_FIELDS + MW_YEAR_FIELDS

    try:
        with arcpy.da.SearchCursor(GOLD_CAMPUS, fields, where_clause) as cursor:
            for row in cursor:
                campuses.append(dict(zip(fields, row)))
    except Exception as e:
        print(f"    WARNING: Error querying campuses: {e}")

    return campuses


def get_meta_canonical(dc_code):
    """Get Meta canonical building data for a dc_code."""
    canonical = []

    if not arcpy.Exists(META_CANONICAL):
        print(f"    WARNING: meta_canonical_buildings not found")
        return canonical

    fields = ['building_key', 'dc_code', 'suite_count', 'it_load_total',
              'region_derived', 'new_build_status']

    where_clause = f"dc_code LIKE '{dc_code}%'"

    try:
        with arcpy.da.SearchCursor(META_CANONICAL, fields, where_clause) as cursor:
            for row in cursor:
                canonical.append(dict(zip(fields, row)))
    except Exception as e:
        print(f"    WARNING: Error querying canonical: {e}")

    return canonical


def aggregate_buildings(buildings, field):
    """Aggregate a field from building records."""
    total = 0
    for b in buildings:
        val = b.get(field)
        if val is not None:
            total += val
    return total


def compare_values(label, building_sum, campus_value, tolerance_pct=5):
    """Compare building sum to campus value, return status."""
    if building_sum == 0 and campus_value == 0:
        return "MATCH", 0, "Both zero"

    if building_sum == 0 and campus_value > 0:
        return "MISMATCH", 100, f"Buildings=0, Campus={campus_value:.1f}"

    if campus_value == 0 and building_sum > 0:
        return "MISMATCH", 100, f"Buildings={building_sum:.1f}, Campus=0"

    diff_pct = abs(building_sum - campus_value) / max(building_sum, campus_value) * 100

    if diff_pct <= tolerance_pct:
        return "MATCH", diff_pct, f"{building_sum:.1f} ~ {campus_value:.1f}"
    else:
        return "DIFF", diff_pct, f"{building_sum:.1f} vs {campus_value:.1f} ({diff_pct:.1f}%)"


# ============================================================================
# VALIDATION FUNCTIONS
# ============================================================================

def validate_building_to_campus_aggregation(campus_pattern, display_name, company_filter=None):
    """Validate that campus values correctly aggregate from buildings."""
    print(f"\n{'='*70}")
    print(f"  CAMPUS: {display_name}")
    print(f"{'='*70}")

    # Get data
    buildings = get_buildings_for_campus(campus_pattern, company_filter)
    campuses = get_campus_records(campus_pattern, company_filter)

    print(f"\n  📊 Data Found:")
    print(f"     Buildings: {len(buildings)} records")
    print(f"     Campuses:  {len(campuses)} records")

    if len(buildings) == 0:
        print(f"     ⚠️ No building records found for pattern '{campus_pattern}'")
        return None

    if len(campuses) == 0:
        print(f"     ⚠️ No campus records found for pattern '{campus_pattern}'")
        return None

    # Show building breakdown by source
    by_source = defaultdict(list)
    for b in buildings:
        by_source[b['source']].append(b)

    print(f"\n  📦 Buildings by Source:")
    for source, bldgs in sorted(by_source.items()):
        capacity = sum(b.get('commissioned_power_mw') or 0 for b in bldgs)
        print(f"     {source}: {len(bldgs)} buildings, {capacity:.1f} MW commissioned")

    # Show campus breakdown
    print(f"\n  🏛️ Campus Records:")
    for c in campuses:
        print(f"     {c['campus_name']}")
        print(f"        Sources: {c.get('source', 'N/A')}")
        print(f"        Building Count: {c.get('building_count', 'N/A')}")
        print(f"        Commissioned: {c.get('commissioned_power_mw') or 0:.1f} MW")

    # Aggregate and compare
    results = {}
    print(f"\n  🔍 Aggregation Validation:")

    for field in CAPACITY_FIELDS:
        building_sum = aggregate_buildings(buildings, field)

        # Sum across all matching campus records
        campus_total = sum(c.get(field) or 0 for c in campuses)

        status, diff_pct, detail = compare_values(field, building_sum, campus_total)
        results[field] = {
            'building_sum': building_sum,
            'campus_total': campus_total,
            'status': status,
            'diff_pct': diff_pct,
            'detail': detail
        }

        print(f"     {field:25s}: {status} {detail}")

    # Check MW year fields
    print(f"\n  📅 Year-by-Year Capacity (mw_20XX):")
    for field in MW_YEAR_FIELDS:
        building_sum = aggregate_buildings(buildings, field)
        campus_total = sum(c.get(field) or 0 for c in campuses)

        if building_sum > 0 or campus_total > 0:
            status, diff_pct, detail = compare_values(field, building_sum, campus_total)
            results[field] = {
                'building_sum': building_sum,
                'campus_total': campus_total,
                'status': status,
                'diff_pct': diff_pct
            }
            print(f"     {field}: {status} {detail}")

    return {
        'campus_name': display_name,
        'building_count': len(buildings),
        'campus_count': len(campuses),
        'sources': list(by_source.keys()),
        'validations': results
    }


# PUE adjustment for DCH Hyper (facility power → IT load estimate)
DCH_PUE_ADJUSTMENT = 1.3  # Typical PUE for hyperscale DCs


def get_semianalysis_for_city(city_name, company='Meta'):
    """Get Semianalysis buildings for a specific city and company."""
    buildings = []

    # Semianalysis campus names follow pattern: Company_City_1
    where_clause = f"source = 'Semianalysis' AND company_clean = '{company}' AND city LIKE '%{city_name}%'"

    fields = ['unique_id', 'source', 'campus_name', 'building_designation',
              'company_clean', 'city', 'state', 'latitude', 'longitude',
              'facility_status', 'record_level'] + CAPACITY_FIELDS + MW_YEAR_FIELDS

    try:
        with arcpy.da.SearchCursor(GOLD_BUILDINGS, fields, where_clause) as cursor:
            for row in cursor:
                buildings.append(dict(zip(fields, row)))
    except Exception as e:
        print(f"    WARNING: Error querying Semianalysis: {e}")

    return buildings


def validate_meta_against_canonical(campus_pattern, dc_code, display_name):
    """Validate Meta campus data against canonical ground truth.

    Now includes:
    - Semianalysis comparison (IT capacity, same definition as canonical)
    - PUE-adjusted DCH comparison (facility power ÷ 1.3 = estimated IT load)
    """
    print(f"\n{'='*70}")
    print(f"  META VALIDATION: {display_name}")
    print(f"  (Comparing against meta_canonical_buildings)")
    print(f"{'='*70}")

    # Get external data
    buildings = get_buildings_for_campus(campus_pattern, 'Meta')
    campuses = get_campus_records(campus_pattern, 'Meta')

    # Extract city name from campus pattern for Semianalysis lookup
    # Pattern is like "Meta Altoona" → city = "Altoona"
    city_name = display_name.replace('Meta ', '').replace('_', ' ')
    semianalysis_buildings = get_semianalysis_for_city(city_name, 'Meta')

    # Get canonical data
    canonical = get_meta_canonical(dc_code)

    print(f"\n  📊 Data Found:")
    print(f"     External Buildings: {len(buildings)} records")
    print(f"     Semianalysis Buildings: {len(semianalysis_buildings)} records")
    print(f"     External Campuses:  {len(campuses)} records")
    print(f"     Canonical Buildings: {len(canonical)} records")

    if len(canonical) == 0:
        print(f"     ⚠️ No canonical records found for dc_code '{dc_code}'")
        print(f"        (This may mean the campus isn't in meta_canonical_buildings)")

        # Still show what external sources have
        if len(buildings) > 0:
            print(f"\n  📦 External Building Data:")
            by_source = defaultdict(list)
            for b in buildings:
                by_source[b['source']].append(b)

            for source, bldgs in sorted(by_source.items()):
                capacity = sum(b.get('commissioned_power_mw') or 0 for b in bldgs)
                print(f"     {source}: {len(bldgs)} bldgs, {capacity:.1f} MW commissioned")

        return None

    # Calculate canonical totals
    canonical_it_load = sum(c.get('it_load_total') or 0 for c in canonical)
    canonical_building_count = len(canonical)
    canonical_suite_count = sum(c.get('suite_count') or 0 for c in canonical)

    print(f"\n  🎯 Meta Canonical Ground Truth:")
    print(f"     DC Code: {dc_code}")
    print(f"     Buildings: {canonical_building_count}")
    print(f"     Suites: {canonical_suite_count}")
    print(f"     Total IT Load: {canonical_it_load:.1f} MW")

    # Show canonical building details
    print(f"\n     Building Breakdown:")
    for c in canonical:
        print(f"       {c['building_key']}: {c.get('it_load_total') or 0:.1f} MW, {c.get('suite_count', 0)} suites, {c.get('new_build_status', 'N/A')}")

    # Compare external estimates to canonical
    print(f"\n  🔍 External Source Comparison:")

    by_source = defaultdict(list)
    for b in buildings:
        by_source[b['source']].append(b)

    # Add Semianalysis as its own source if found
    if semianalysis_buildings:
        by_source['Semianalysis'] = semianalysis_buildings

    comparison_results = []

    for source, bldgs in sorted(by_source.items()):
        # Sum external estimates
        ext_commissioned = sum(b.get('commissioned_power_mw') or 0 for b in bldgs)
        ext_it_load = sum(b.get('it_load_total') or 0 for b in bldgs)
        ext_count = len(bldgs)

        # For Semianalysis, get mw_2025 (current year) and mw_2026 (next year forecast)
        ext_mw_2025 = sum(b.get('mw_2025') or 0 for b in bldgs)
        ext_mw_2026 = sum(b.get('mw_2026') or 0 for b in bldgs)

        # Determine best comparison field and apply adjustments
        if canonical_it_load > 0:
            # For Semianalysis, prefer mw_2025 (current year IT capacity)
            if source == 'Semianalysis':
                # Use mw_2025 if available, otherwise commissioned
                best_value = ext_mw_2025 if ext_mw_2025 > 0 else ext_commissioned
                best_field = 'mw_2025' if ext_mw_2025 > 0 else 'commissioned_power_mw'
                accuracy = (1 - abs(best_value - canonical_it_load) / canonical_it_load) * 100
                adjusted_value = best_value  # No adjustment needed
            # For DCH, apply PUE adjustment
            elif source == 'DataCenterHawk':
                if ext_commissioned > 0:
                    # DCH reports facility power, adjust by PUE to estimate IT load
                    adjusted_value = ext_commissioned / DCH_PUE_ADJUSTMENT
                    accuracy = (1 - abs(adjusted_value - canonical_it_load) / canonical_it_load) * 100
                    best_field = f'commissioned_power_mw (÷{DCH_PUE_ADJUSTMENT} PUE)'
                    best_value = ext_commissioned
                else:
                    adjusted_value = 0
                    accuracy = 0
                    best_field = 'N/A'
                    best_value = 0
            # For other sources
            elif ext_it_load > 0:
                accuracy = (1 - abs(ext_it_load - canonical_it_load) / canonical_it_load) * 100
                best_field = 'it_load_total'
                best_value = ext_it_load
                adjusted_value = ext_it_load
            elif ext_commissioned > 0:
                accuracy = (1 - abs(ext_commissioned - canonical_it_load) / canonical_it_load) * 100
                best_field = 'commissioned_power_mw'
                best_value = ext_commissioned
                adjusted_value = ext_commissioned
            else:
                accuracy = 0
                best_field = 'N/A'
                best_value = 0
                adjusted_value = 0
        else:
            accuracy = 0
            best_field = 'N/A'
            best_value = 0
            adjusted_value = 0

        grade = "🏆" if accuracy >= 90 else "✅" if accuracy >= 75 else "⚠️" if accuracy >= 50 else "❌"

        print(f"     {source}:")
        print(f"        Buildings: {ext_count} (canonical: {canonical_building_count})")
        print(f"        commissioned_power_mw: {ext_commissioned:.1f} MW")
        if source == 'Semianalysis':
            print(f"        mw_2025 (current): {ext_mw_2025:.1f} MW")
            print(f"        mw_2026 (forecast): {ext_mw_2026:.1f} MW")
        if source == 'DataCenterHawk' and ext_commissioned > 0:
            print(f"        PUE-adjusted estimate: {adjusted_value:.1f} MW (÷{DCH_PUE_ADJUSTMENT})")
        print(f"        {grade} Accuracy vs Canonical: {accuracy:.1f}% (using {best_field})")

        # Calculate building count difference and net capacity difference
        building_diff = ext_count - canonical_building_count
        capacity_diff_mw = adjusted_value - canonical_it_load if adjusted_value > 0 else None

        comparison_results.append({
            'source': source,
            'building_count': ext_count,
            'building_diff': building_diff,
            'commissioned_mw': ext_commissioned,
            'mw_2025': ext_mw_2025 if source == 'Semianalysis' else None,
            'mw_2026': ext_mw_2026 if source == 'Semianalysis' else None,
            'adjusted_mw': adjusted_value,
            'capacity_diff_mw': capacity_diff_mw,
            'it_load_mw': ext_it_load,
            'accuracy_pct': accuracy,
            'best_field': best_field
        })

    return {
        'campus_name': display_name,
        'dc_code': dc_code,
        'canonical_it_load': canonical_it_load,
        'canonical_buildings': canonical_building_count,
        'source_comparisons': comparison_results
    }


def analyze_competitor_site(campus_pattern, display_name, notes):
    """Analyze a high-profile competitor site."""
    print(f"\n{'='*70}")
    print(f"  COMPETITOR: {display_name}")
    print(f"  {notes}")
    print(f"{'='*70}")

    # Get data
    buildings = get_buildings_for_campus(campus_pattern)
    campuses = get_campus_records(campus_pattern)

    print(f"\n  📊 Data Found:")
    print(f"     Buildings: {len(buildings)} records")
    print(f"     Campuses:  {len(campuses)} records")

    if len(buildings) == 0 and len(campuses) == 0:
        print(f"     ⚠️ No data found for pattern '{campus_pattern}'")
        return None

    # Analyze buildings by source
    by_source = defaultdict(list)
    for b in buildings:
        by_source[b['source']].append(b)

    print(f"\n  📦 Buildings by Source:")
    for source, bldgs in sorted(by_source.items()):
        commissioned = sum(b.get('commissioned_power_mw') or 0 for b in bldgs)
        full_cap = sum(b.get('full_capacity_mw') or 0 for b in bldgs)

        print(f"     {source}: {len(bldgs)} buildings")
        print(f"        Commissioned: {commissioned:.1f} MW")
        print(f"        Full Capacity: {full_cap:.1f} MW")

        # Show individual buildings
        for b in bldgs[:5]:  # Limit to first 5
            print(f"          - {b.get('building_designation', b.get('unique_id', 'N/A'))}: {b.get('commissioned_power_mw') or 0:.1f} MW, {b.get('city')}, {b.get('facility_status')}")
        if len(bldgs) > 5:
            print(f"          ... and {len(bldgs) - 5} more")

    # Show campus summary
    print(f"\n  🏛️ Campus Summary:")
    for c in campuses:
        print(f"     {c['campus_name']}")
        print(f"        Company: {c.get('company_clean')}")
        print(f"        Location: {c.get('city')}, {c.get('state')}")
        print(f"        Source: {c.get('source', 'N/A')}")
        print(f"        Building Count: {c.get('building_count', 'N/A')}")
        print(f"        Commissioned: {c.get('commissioned_power_mw') or 0:.1f} MW")
        print(f"        Full Capacity: {c.get('full_capacity_mw') or 0:.1f} MW")

    # Cross-source consistency check
    if len(by_source) > 1:
        print(f"\n  🔍 Cross-Source Consistency:")
        capacities_by_source = {}
        for source, bldgs in by_source.items():
            cap = sum(b.get('commissioned_power_mw') or 0 for b in bldgs)
            if cap > 0:
                capacities_by_source[source] = cap

        if len(capacities_by_source) > 1:
            values = list(capacities_by_source.values())
            avg = sum(values) / len(values)
            spread = max(values) - min(values)
            spread_pct = (spread / avg * 100) if avg > 0 else 0

            print(f"     Capacity Range: {min(values):.1f} - {max(values):.1f} MW")
            print(f"     Spread: {spread:.1f} MW ({spread_pct:.1f}%)")

            if spread_pct > 50:
                print(f"     ⚠️ HIGH VARIANCE across sources - investigate data quality")
            elif spread_pct > 20:
                print(f"     ⚡ Moderate variance - sources may have different definitions")
            else:
                print(f"     ✅ Good consistency across sources")

    return {
        'campus_name': display_name,
        'building_count': len(buildings),
        'campus_count': len(campuses),
        'sources': list(by_source.keys()),
        'notes': notes
    }


# ============================================================================
# MAIN
# ============================================================================

def main():
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    print("=" * 80)
    print("   DEEP DIVE CAMPUS VALIDATION - TORTURE TEST")
    print("=" * 80)
    print(f"   Started: {datetime.now()}")
    print(f"   GDB: {GDB}")
    print(f"   Output: {OUTPUT_DIR}")
    print()

    # Check feature classes exist
    for fc in [GOLD_BUILDINGS, GOLD_CAMPUS]:
        if arcpy.Exists(fc):
            count = int(arcpy.GetCount_management(fc)[0])
            print(f"   ✅ {os.path.basename(fc)}: {count:,} records")
        else:
            print(f"   ❌ {os.path.basename(fc)}: NOT FOUND")
            return

    if arcpy.Exists(META_CANONICAL):
        count = int(arcpy.GetCount_management(META_CANONICAL)[0])
        print(f"   ✅ meta_canonical_buildings: {count:,} records")
    else:
        print(f"   ⚠️ meta_canonical_buildings: NOT FOUND (Meta validation skipped)")

    all_results = {
        'meta_validations': [],
        'aggregation_checks': [],
        'competitor_analyses': []
    }

    # ========================================================================
    # PART 1: META CAMPUSES - Validate against canonical ground truth
    # ========================================================================
    print("\n")
    print("█" * 80)
    print("   PART 1: META CAMPUS VALIDATION (vs Canonical Ground Truth)")
    print("█" * 80)

    for pattern, dc_code, display_name in META_TARGETS:
        result = validate_meta_against_canonical(pattern, dc_code, display_name)
        if result:
            all_results['meta_validations'].append(result)

    # ========================================================================
    # PART 2: BUILDING→CAMPUS AGGREGATION CHECK
    # ========================================================================
    print("\n")
    print("█" * 80)
    print("   PART 2: BUILDING→CAMPUS AGGREGATION VALIDATION")
    print("█" * 80)

    # Check a mix of Meta and competitor sites
    aggregation_targets = [
        ('Meta Altoona', 'Meta Altoona', 'Meta'),
        ('Meta Prineville', 'Meta Prineville', 'Meta'),
        ('Microsoft Boydton', 'Microsoft Boydton', 'Microsoft'),
        ('Google Council Bluffs', 'Google Council Bluffs', 'Google'),
        ('xAI_Memphis', 'xAI Memphis', 'xAI'),
    ]

    for pattern, display_name, company in aggregation_targets:
        result = validate_building_to_campus_aggregation(pattern, display_name, company)
        if result:
            all_results['aggregation_checks'].append(result)

    # ========================================================================
    # PART 3: HIGH-PROFILE COMPETITOR ANALYSIS
    # ========================================================================
    print("\n")
    print("█" * 80)
    print("   PART 3: HIGH-PROFILE COMPETITOR SITE ANALYSIS")
    print("█" * 80)

    for pattern, display_name, notes in COMPETITOR_TARGETS:
        result = analyze_competitor_site(pattern, display_name, notes)
        if result:
            all_results['competitor_analyses'].append(result)

    # ========================================================================
    # SUMMARY
    # ========================================================================
    print("\n")
    print("█" * 80)
    print("   VALIDATION SUMMARY")
    print("█" * 80)

    print(f"\n  📊 Results Overview:")
    print(f"     Meta Validations: {len(all_results['meta_validations'])} sites analyzed")
    print(f"     Aggregation Checks: {len(all_results['aggregation_checks'])} sites checked")
    print(f"     Competitor Analyses: {len(all_results['competitor_analyses'])} sites analyzed")

    # Meta accuracy summary
    if all_results['meta_validations']:
        print(f"\n  🎯 Meta Accuracy Summary:")
        for mv in all_results['meta_validations']:
            print(f"     {mv['campus_name']}:")
            print(f"        Canonical IT Load: {mv['canonical_it_load']:.1f} MW")
            for sc in mv.get('source_comparisons', []):
                grade = "🏆" if sc['accuracy_pct'] >= 90 else "✅" if sc['accuracy_pct'] >= 75 else "⚠️"
                print(f"        {sc['source']}: {grade} {sc['accuracy_pct']:.1f}% accuracy")

    # Aggregation issues
    agg_issues = []
    for ac in all_results['aggregation_checks']:
        for field, val in ac.get('validations', {}).items():
            if '❌' in val.get('status', ''):
                agg_issues.append(f"{ac['campus_name']}.{field}: {val['detail']}")

    if agg_issues:
        print(f"\n  ⚠️ Aggregation Issues Found:")
        for issue in agg_issues[:10]:
            print(f"     - {issue}")
    else:
        print(f"\n  ✅ No aggregation issues found")

    # ========================================================================
    # EXPORT RESULTS TO CSV
    # ========================================================================
    print("\n")
    print("█" * 80)
    print("   EXPORTING RESULTS")
    print("█" * 80)

    # Export Meta validation comparison
    meta_csv_path = os.path.join(OUTPUT_DIR, f"meta_validation_comparison_{timestamp}.csv")
    try:
        with open(meta_csv_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([
                'campus_name', 'dc_code', 'canonical_it_load_mw', 'canonical_buildings',
                'source', 'source_buildings', 'building_diff', 'commissioned_mw', 'mw_2025', 'mw_2026',
                'pue_adjusted_mw', 'capacity_diff_mw', 'accuracy_pct', 'comparison_field'
            ])

            for mv in all_results['meta_validations']:
                for sc in mv.get('source_comparisons', []):
                    capacity_diff = sc.get('capacity_diff_mw')
                    capacity_diff_str = round(capacity_diff, 1) if capacity_diff is not None else ''

                    writer.writerow([
                        mv['campus_name'],
                        mv['dc_code'],
                        mv['canonical_it_load'],
                        mv['canonical_buildings'],
                        sc['source'],
                        sc['building_count'],
                        sc.get('building_diff', ''),
                        sc['commissioned_mw'],
                        sc.get('mw_2025', ''),
                        sc.get('mw_2026', ''),
                        sc.get('adjusted_mw', sc['commissioned_mw']),
                        capacity_diff_str,
                        round(sc['accuracy_pct'], 1),
                        sc['best_field']
                    ])

        print(f"   ✅ Meta validation: {meta_csv_path}")
    except Exception as e:
        print(f"   ❌ Failed to export Meta validation: {e}")

    # Export summary TXT
    summary_txt_path = os.path.join(OUTPUT_DIR, f"validation_summary_{timestamp}.txt")
    try:
        with open(summary_txt_path, 'w', encoding='utf-8') as f:
            f.write("=" * 80 + "\n")
            f.write("DEEP DIVE CAMPUS VALIDATION SUMMARY\n")
            f.write(f"Generated: {datetime.now()}\n")
            f.write("=" * 80 + "\n\n")

            f.write("META CAMPUS ACCURACY COMPARISON (Semianalysis vs DCH vs Canonical)\n")
            f.write("-" * 80 + "\n")
            f.write(f"{'Campus':<25} {'Canonical':<12} {'DCH Acc':<12} {'Semi Acc':<12} {'Best Source':<15}\n")
            f.write("-" * 80 + "\n")

            for mv in all_results['meta_validations']:
                canonical = mv['canonical_it_load']
                dch_acc = None
                semi_acc = None

                for sc in mv.get('source_comparisons', []):
                    if sc['source'] == 'DataCenterHawk':
                        dch_acc = sc['accuracy_pct']
                    elif sc['source'] == 'Semianalysis':
                        semi_acc = sc['accuracy_pct']

                # Determine best source
                if dch_acc is not None and semi_acc is not None:
                    best = 'Semianalysis' if semi_acc > dch_acc else 'DCH'
                elif semi_acc is not None:
                    best = 'Semianalysis'
                elif dch_acc is not None:
                    best = 'DCH'
                else:
                    best = 'N/A'

                dch_str = f"{dch_acc:.1f}%" if dch_acc is not None else "N/A"
                semi_str = f"{semi_acc:.1f}%" if semi_acc is not None else "N/A"

                f.write(f"{mv['campus_name']:<25} {canonical:<12.1f} {dch_str:<12} {semi_str:<12} {best:<15}\n")

            f.write("\n" + "-" * 80 + "\n")
            f.write("\nKEY FINDINGS:\n")
            f.write("- DCH reports FACILITY power (includes cooling/infrastructure)\n")
            f.write("- Semianalysis reports IT capacity (same definition as Meta canonical)\n")
            f.write("- PUE adjustment of 1.3 applied to DCH for comparison\n")
            f.write("- DataCenterMap provides location only (0 MW for hyperscalers)\n")

            # Calculate averages (excluding outliers < -100%)
            OUTLIER_THRESHOLD = -100  # Exclude massive over-reports
            dch_accuracies = []
            dch_outliers = []
            semi_accuracies = []
            semi_outliers = []

            for mv in all_results['meta_validations']:
                for sc in mv.get('source_comparisons', []):
                    if sc['source'] == 'DataCenterHawk' and sc['accuracy_pct'] != 0:
                        if sc['accuracy_pct'] >= OUTLIER_THRESHOLD:
                            dch_accuracies.append(sc['accuracy_pct'])
                        else:
                            dch_outliers.append((mv['campus_name'], sc['accuracy_pct']))
                    elif sc['source'] == 'Semianalysis' and sc['accuracy_pct'] != 0:
                        if sc['accuracy_pct'] >= OUTLIER_THRESHOLD:
                            semi_accuracies.append(sc['accuracy_pct'])
                        else:
                            semi_outliers.append((mv['campus_name'], sc['accuracy_pct']))

            f.write(f"\nACCURACY SUMMARY (excluding outliers < {OUTLIER_THRESHOLD}%):\n")
            if dch_accuracies:
                f.write(f"  DCH Average Accuracy: {sum(dch_accuracies)/len(dch_accuracies):.1f}% (n={len(dch_accuracies)})\n")
            if semi_accuracies:
                f.write(f"  Semianalysis Average Accuracy: {sum(semi_accuracies)/len(semi_accuracies):.1f}% (n={len(semi_accuracies)})\n")

            # Report outliers
            all_outliers = dch_outliers + semi_outliers
            if all_outliers:
                f.write(f"\n⚠️ OUTLIERS EXCLUDED ({len(all_outliers)} campuses):\n")
                for campus, acc in all_outliers:
                    f.write(f"  - {campus}: {acc:.1f}%\n")
                f.write("  → Investigate: likely planned capacity reported as commissioned\n")

        print(f"   ✅ Summary: {summary_txt_path}")
    except Exception as e:
        print(f"   ❌ Failed to export summary: {e}")

    print(f"\n   Completed: {datetime.now()}")
    print("=" * 80)

    return all_results


# ============================================================================
# EXECUTE
# ============================================================================

if __name__ == "__main__":
    try:
        results = main()
    except Exception as e:
        print(f"\n❌ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
else:
    # Run when exec()'d from ArcGIS Pro Python window
    try:
        results = main()
    except Exception as e:
        print(f"\n❌ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
