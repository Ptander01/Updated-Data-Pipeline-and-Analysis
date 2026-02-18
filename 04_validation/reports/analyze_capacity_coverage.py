"""
Capacity Field Coverage Analysis
================================

Purpose:
Analyzes the population/coverage of each capacity field across all sources
to help determine which field should be the default for visualization.

Output:
- Coverage percentage by field
- Coverage by source
- Recommendation for default field

Run in ArcGIS Pro Python window:
exec(open(r"...scripts/04_validation/analyze_capacity_coverage.py", encoding='utf-8').read())

Author: DC GIS Team
Created: January 2, 2026
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

from config import GDB, GOLD_BUILDINGS, GOLD_CAMPUS

arcpy.env.workspace = GDB

# Capacity fields to analyze
CAPACITY_FIELDS = [
    'commissioned_power_mw',
    'uc_power_mw',
    'planned_power_mw',
    'full_capacity_mw',
    'planned_plus_uc_mw',
    'it_power_mw',
    'facility_power_mw',
    'available_power_kw',
    # Year fields
    'mw_2023',
    'mw_2024',
    'mw_2025',
    'mw_2026',
    'mw_2027',
    'mw_2028',
    'mw_2029',
    'mw_2030',
    'mw_2031',
    'mw_2032',
]


def analyze_layer(layer_path, layer_name):
    """Analyze capacity field coverage for a layer."""
    print(f"\n{'=' * 70}")
    print(f"   {layer_name.upper()} - CAPACITY FIELD COVERAGE")
    print(f"{'=' * 70}")

    if not arcpy.Exists(layer_path):
        print(f"   ❌ Layer not found: {layer_path}")
        return None

    # Get existing fields
    existing_fields = [f.name for f in arcpy.ListFields(layer_path)]

    # Filter to fields that exist
    fields_to_check = [f for f in CAPACITY_FIELDS if f in existing_fields]
    missing_fields = [f for f in CAPACITY_FIELDS if f not in existing_fields]

    if missing_fields:
        print(f"\n   ⚠️ Fields not in schema: {', '.join(missing_fields[:5])}{'...' if len(missing_fields) > 5 else ''}")

    # Get total count
    total_count = int(arcpy.management.GetCount(layer_path)[0])
    print(f"\n   Total records: {total_count:,}")

    # Initialize counters
    field_counts = {f: 0 for f in fields_to_check}
    field_sums = {f: 0.0 for f in fields_to_check}
    source_counts = defaultdict(int)
    source_field_counts = defaultdict(lambda: defaultdict(int))

    # Check if 'source' field exists
    has_source = 'source' in existing_fields

    # Read fields
    read_fields = fields_to_check.copy()
    if has_source:
        read_fields.append('source')

    # Analyze records
    with arcpy.da.SearchCursor(layer_path, read_fields) as cursor:
        for row in cursor:
            source = row[-1] if has_source else 'Unknown'
            source_counts[source] += 1

            for i, field in enumerate(fields_to_check):
                value = row[i]
                if value is not None and value > 0:
                    field_counts[field] += 1
                    field_sums[field] += value
                    if has_source:
                        source_field_counts[source][field] += 1

    # Print overall coverage
    print(f"\n   {'─' * 66}")
    print(f"   OVERALL FIELD COVERAGE")
    print(f"   {'─' * 66}")
    print(f"   {'Field':<30} {'Count':>10} {'Coverage':>12} {'Avg Value':>12}")
    print(f"   {'─' * 66}")

    # Sort by coverage
    sorted_fields = sorted(fields_to_check, key=lambda f: field_counts[f], reverse=True)

    for field in sorted_fields:
        count = field_counts[field]
        pct = (count / total_count * 100) if total_count > 0 else 0
        avg = (field_sums[field] / count) if count > 0 else 0

        # Highlight high coverage fields
        if pct >= 50:
            marker = "⭐"
        elif pct >= 25:
            marker = "✓"
        else:
            marker = " "

        print(f"   {marker} {field:<28} {count:>10,} {pct:>10.1f}% {avg:>10.1f} MW")

    # Print by source
    if has_source:
        print(f"\n   {'─' * 66}")
        print(f"   COVERAGE BY SOURCE")
        print(f"   {'─' * 66}")

        # Key fields for source breakdown
        key_fields = ['commissioned_power_mw', 'full_capacity_mw', 'it_power_mw', 'mw_2025']
        key_fields = [f for f in key_fields if f in fields_to_check]

        print(f"\n   {'Source':<20} {'Records':>10}", end='')
        for field in key_fields:
            short_name = field.replace('_power_mw', '').replace('commissioned', 'comm').replace('full_capacity', 'full_cap')
            print(f" {short_name:>12}", end='')
        print()
        print(f"   {'─' * 66}")

        for source in sorted(source_counts.keys(), key=lambda s: source_counts[s], reverse=True):
            src_total = source_counts[source]
            print(f"   {source:<20} {src_total:>10,}", end='')

            for field in key_fields:
                field_count = source_field_counts[source][field]
                pct = (field_count / src_total * 100) if src_total > 0 else 0
                print(f" {pct:>10.1f}%", end='')
            print()

    return {
        'total': total_count,
        'field_counts': field_counts,
        'field_sums': field_sums,
        'source_counts': dict(source_counts),
        'source_field_counts': {k: dict(v) for k, v in source_field_counts.items()}
    }


def generate_recommendation(buildings_data, campus_data):
    """Generate recommendation based on coverage analysis."""
    print(f"\n{'=' * 70}")
    print(f"   RECOMMENDATION")
    print(f"{'=' * 70}")

    if not buildings_data:
        print("   ❌ No data available for recommendation")
        return

    total = buildings_data['total']
    counts = buildings_data['field_counts']

    # Rank fields by coverage
    ranked = sorted(counts.items(), key=lambda x: x[1], reverse=True)

    print(f"\n   Based on coverage analysis of {total:,} building records:")
    print()

    # Top 3 fields
    print("   🏆 TOP FIELDS BY COVERAGE:")
    for i, (field, count) in enumerate(ranked[:5], 1):
        pct = (count / total * 100) if total > 0 else 0
        print(f"      {i}. {field}: {pct:.1f}% ({count:,} records)")

    # Primary recommendation
    best_field = ranked[0][0] if ranked else None
    best_coverage = (ranked[0][1] / total * 100) if ranked and total > 0 else 0

    print(f"\n   📊 PRIMARY RECOMMENDATION:")
    print(f"      Use '{best_field}' as default capacity field")
    print(f"      Coverage: {best_coverage:.1f}%")

    # Check for full_capacity_mw specifically
    full_cap_count = counts.get('full_capacity_mw', 0)
    full_cap_pct = (full_cap_count / total * 100) if total > 0 else 0

    if best_field != 'full_capacity_mw':
        print(f"\n   ℹ️ NOTE: full_capacity_mw has {full_cap_pct:.1f}% coverage")
        if full_cap_pct >= 40:
            print(f"      Consider using full_capacity_mw for conceptual consistency")
            print(f"      (represents total buildout potential)")

    # Check commissioned + full as composite
    comm_count = counts.get('commissioned_power_mw', 0)
    composite = max(comm_count, full_cap_count)
    composite_pct = (composite / total * 100) if total > 0 else 0

    print(f"\n   💡 COMPOSITE OPTION:")
    print(f"      Create 'primary_capacity_mw' = COALESCE(full_capacity_mw, commissioned_power_mw)")
    print(f"      Estimated coverage: ~{composite_pct:.0f}%+ (likely higher with overlap)")


def main():
    print("=" * 70)
    print("   CAPACITY FIELD COVERAGE ANALYSIS")
    print("=" * 70)
    print(f"   Started: {datetime.now()}")

    # Analyze buildings
    buildings_data = analyze_layer(GOLD_BUILDINGS, "gold_buildings_full")

    # Analyze campus
    campus_data = analyze_layer(GOLD_CAMPUS, "gold_campus_full")

    # Generate recommendation
    generate_recommendation(buildings_data, campus_data)

    print(f"\n   Completed: {datetime.now()}")
    print("=" * 70)


# Execute
if __name__ == "__main__":
    main()
else:
    main()
