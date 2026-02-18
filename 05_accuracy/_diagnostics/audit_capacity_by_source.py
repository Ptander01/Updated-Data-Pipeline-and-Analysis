"""
Audit Capacity Fields by Source
Examines what capacity data exists in gold_buildings for each vendor source.

Author: Meta Data Center GIS Team
Date: December 11, 2024
"""

import arcpy
import pandas as pd
from collections import defaultdict
import os

# ============================================================================
# CONFIGURATION
# ============================================================================

GDB = r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\Default.gdb"
GOLD_BUILDINGS = os.path.join(GDB, "gold_buildings")
SPATIAL_MATCHES = os.path.join(GDB, "accuracy_analysis_multi_source_REBUILT")

# Capacity fields to check
CAPACITY_FIELDS = [
    'commissioned_power_mw',
    'planned_power_mw',
    'uc_power_mw',
    'full_capacity_mw',
    'planned_plus_uc_mw',
    'mw_2023',
    'mw_2024',
    'mw_2025',
    'mw_2026',
    'mw_2027',
    'mw_2028'
]


def audit_gold_buildings():
    """Audit capacity fields in gold_buildings by source."""

    print("=" * 80)
    print("CAPACITY FIELD AUDIT - gold_buildings")
    print("=" * 80)

    # Get all fields that exist
    available_fields = [f.name for f in arcpy.ListFields(GOLD_BUILDINGS)]

    # Filter to capacity fields that exist
    check_fields = ['source', 'record_level'] + [f for f in CAPACITY_FIELDS if f in available_fields]

    print(f"\nChecking fields: {check_fields}")

    # Read data
    data = []
    with arcpy.da.SearchCursor(GOLD_BUILDINGS, check_fields) as cursor:
        for row in cursor:
            data.append(dict(zip(check_fields, row)))

    df = pd.DataFrame(data)

    print(f"\nTotal records in gold_buildings: {len(df)}")

    # Summary by source
    print("\n" + "=" * 80)
    print("CAPACITY DATA BY SOURCE")
    print("=" * 80)

    for source in df['source'].unique():
        source_df = df[df['source'] == source]

        print(f"\n{'='*40}")
        print(f"SOURCE: {source}")
        print(f"{'='*40}")
        print(f"Total records: {len(source_df)}")

        # Record level breakdown
        if 'record_level' in source_df.columns:
            levels = source_df['record_level'].value_counts()
            print(f"\nRecord Levels:")
            for level, count in levels.items():
                print(f"  {level}: {count}")

        # Check each capacity field
        print(f"\nCapacity Fields:")
        cap_fields_found = False

        for field in CAPACITY_FIELDS:
            if field in source_df.columns:
                non_null = source_df[field].notna() & (source_df[field] > 0)
                non_null_count = non_null.sum()

                if non_null_count > 0:
                    cap_fields_found = True
                    values = source_df.loc[non_null, field]
                    print(f"\n  {field}:")
                    print(f"    Records with data: {non_null_count} ({non_null_count/len(source_df)*100:.1f}%)")
                    print(f"    Min: {values.min():.1f} MW")
                    print(f"    Max: {values.max():.1f} MW")
                    print(f"    Mean: {values.mean():.1f} MW")
                    print(f"    Sum: {values.sum():.1f} MW")

        if not cap_fields_found:
            print("  ❌ NO CAPACITY DATA FOUND")

    return df


def audit_spatial_matches():
    """Audit capacity fields available in spatial matches."""

    print("\n\n" + "=" * 80)
    print("CAPACITY FIELD AUDIT - Spatial Matches (accuracy_analysis_multi_source_REBUILT)")
    print("=" * 80)

    if not arcpy.Exists(SPATIAL_MATCHES):
        print("❌ Spatial matches feature class not found!")
        return None

    # Get all fields
    available_fields = [f.name for f in arcpy.ListFields(SPATIAL_MATCHES)]

    # Look for capacity fields (may have _1 suffix from spatial join)
    cap_fields_in_matches = []
    for field in CAPACITY_FIELDS:
        if field in available_fields:
            cap_fields_in_matches.append(field)
        elif field + '_1' in available_fields:
            cap_fields_in_matches.append(field + '_1')

    print(f"\nCapacity fields available in spatial matches:")
    for f in cap_fields_in_matches:
        print(f"  - {f}")

    # Check by source
    check_fields = ['source', 'building_key', 'distance_m'] + cap_fields_in_matches
    check_fields = [f for f in check_fields if f in available_fields or f.replace('_1', '') in available_fields]

    # Actually read what's available
    actual_check = []
    for f in check_fields:
        if f in available_fields:
            actual_check.append(f)
        elif f + '_1' in available_fields:
            actual_check.append(f + '_1')

    # Ensure we have source
    if 'source' not in actual_check and 'source_1' in available_fields:
        actual_check.append('source_1')

    data = []
    with arcpy.da.SearchCursor(SPATIAL_MATCHES, actual_check) as cursor:
        for row in cursor:
            record = {}
            for i, field in enumerate(actual_check):
                # Clean field name (remove _1 suffix)
                clean_name = field.replace('_1', '') if field.endswith('_1') else field
                record[clean_name] = row[i]
            data.append(record)

    df = pd.DataFrame(data)

    print(f"\nTotal spatial match records: {len(df)}")

    # Summary by source
    print("\n" + "-" * 40)
    print("CAPACITY DATA IN SPATIAL MATCHES BY SOURCE")
    print("-" * 40)

    for source in df['source'].unique():
        source_df = df[df['source'] == source]

        print(f"\n{source}: {len(source_df)} matches")

        for field in CAPACITY_FIELDS:
            if field in source_df.columns:
                non_null = source_df[field].notna() & (source_df[field] > 0)
                non_null_count = non_null.sum()

                if non_null_count > 0:
                    print(f"  {field}: {non_null_count} records with data")

    return df


def summarize_findings():
    """Print summary of what sources can be used for capacity analysis."""

    print("\n\n" + "=" * 80)
    print("📋 SUMMARY: SOURCES AVAILABLE FOR CAPACITY ANALYSIS")
    print("=" * 80)

    print("""
Based on the audit above, here's what we can compare:

CURRENTLY IN ANALYSIS:
  ✅ Semianalysis - mw_2023, mw_2024, commissioned_power_mw
  ✅ DataCenterHawk - commissioned_power_mw (Building-level, no PUE adjustment)
  ⚠️  DataCenterMap - commissioned_power_mw (Building-level filter, may have few matches)

TO ADD:
  📥 NewProjectMedia - full_capacity_mw (from total_mws field)
     └─ Note: This is "total IT ramp-up capacity" - may represent different time horizon

  📥 WoodMac - commissioned_power_mw, planned_power_mw, full_capacity_mw
     └─ Note: existing_mw → commissioned, new_mw → planned

CANNOT ADD:
  ❌ Synergy - No capacity fields ingested (only tracks facility count/locations)

NEXT STEPS:
  1. Add NPM and WoodMac to COMPARISONS config
  2. Run variance experiments to determine best field for each
  3. Document capacity definition differences
""")


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    df_gold = audit_gold_buildings()
    df_matches = audit_spatial_matches()
    summarize_findings()
