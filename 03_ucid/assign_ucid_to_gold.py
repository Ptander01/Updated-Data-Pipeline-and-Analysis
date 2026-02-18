"""
UCID Assignment Script
Assigns Universal Campus IDs to gold_campus_full and gold_buildings_full.

After running the comparison (validate_ucid_comparison.py), use this script
to apply the chosen tolerance (TIGHT or LOOSE) to the production tables.

Author: Meta Data Center GIS Team
Created: December 18, 2024
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
    script_dir = r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\scripts\06_ucid"

utils_dir = os.path.join(os.path.dirname(script_dir), "_utils")
if utils_dir not in sys.path:
    sys.path.insert(0, utils_dir)

from config import (GDB, GOLD_CAMPUS, GOLD_BUILDINGS,
                    CAMPUS_MASTER, CAMPUS_MASTER_TIGHT, CAMPUS_MASTER_LOOSE)

arcpy.env.workspace = GDB
arcpy.env.overwriteOutput = True

# ==============================================================================
# CONFIGURATION - SET YOUR CHOICE HERE
# ==============================================================================

# Choose which tolerance to use: 'TIGHT' or 'LOOSE'
# After running validate_ucid_comparison.py, set this to the recommended method
CHOSEN_METHOD = 'TIGHT'  # or 'LOOSE'

# ==============================================================================
# HELPER FUNCTIONS
# ==============================================================================

def add_ucid_field(fc_path, field_name='ucid'):
    """Add ucid field to feature class if it doesn't exist."""
    existing_fields = [f.name for f in arcpy.ListFields(fc_path)]

    if field_name not in existing_fields:
        arcpy.management.AddField(fc_path, field_name, 'TEXT', field_length=20)
        print(f"   - Added '{field_name}' field to {os.path.basename(fc_path)}")
        return True
    else:
        print(f"   - '{field_name}' field already exists in {os.path.basename(fc_path)}")
        return False

def create_final_campus_master(source_fc, target_fc):
    """Copy chosen campus_master variant to the final campus_master."""

    if arcpy.Exists(target_fc):
        arcpy.management.Delete(target_fc)
        print(f"   - Deleted existing {os.path.basename(target_fc)}")

    arcpy.management.Copy(source_fc, target_fc)
    print(f"   - Created {os.path.basename(target_fc)} from {os.path.basename(source_fc)}")

    return int(arcpy.management.GetCount(target_fc)[0])

def build_campus_id_to_ucid_map(campus_master_fc):
    """Build mapping from source campus_id to UCID."""

    mapping = {}

    with arcpy.da.SearchCursor(campus_master_fc, ['ucid', 'campus_ids']) as cursor:
        for row in cursor:
            ucid = row[0]
            campus_ids_str = row[1]

            if campus_ids_str:
                for campus_id in campus_ids_str.split('; '):
                    campus_id = campus_id.strip()
                    if campus_id:
                        mapping[campus_id] = ucid

    return mapping

def assign_ucid_to_gold_campus(mapping):
    """Assign UCIDs to gold_campus_full based on campus_id."""

    updated = 0
    not_found = 0

    with arcpy.da.UpdateCursor(GOLD_CAMPUS, ['campus_id', 'ucid']) as cursor:
        for row in cursor:
            campus_id = row[0]

            if campus_id and campus_id in mapping:
                row[1] = mapping[campus_id]
                cursor.updateRow(row)
                updated += 1
            else:
                not_found += 1

    return updated, not_found

def assign_ucid_to_gold_buildings(campus_mapping):
    """
    Assign UCIDs to gold_buildings_full.
    Buildings inherit UCID from their campus_id.
    """

    updated = 0
    not_found = 0

    with arcpy.da.UpdateCursor(GOLD_BUILDINGS, ['campus_id', 'ucid']) as cursor:
        for row in cursor:
            campus_id = row[0]

            if campus_id and campus_id in campus_mapping:
                row[1] = campus_mapping[campus_id]
                cursor.updateRow(row)
                updated += 1
            else:
                not_found += 1

    return updated, not_found

def generate_summary_stats():
    """Generate summary statistics of UCID assignment."""

    # Campus stats
    campus_total = int(arcpy.management.GetCount(GOLD_CAMPUS)[0])
    campus_with_ucid = 0
    campus_ucid_values = set()

    with arcpy.da.SearchCursor(GOLD_CAMPUS, ['ucid']) as cursor:
        for row in cursor:
            if row[0]:
                campus_with_ucid += 1
                campus_ucid_values.add(row[0])

    # Building stats
    building_total = int(arcpy.management.GetCount(GOLD_BUILDINGS)[0])
    building_with_ucid = 0
    building_ucid_values = set()

    with arcpy.da.SearchCursor(GOLD_BUILDINGS, ['ucid']) as cursor:
        for row in cursor:
            if row[0]:
                building_with_ucid += 1
                building_ucid_values.add(row[0])

    # Master stats
    master_count = int(arcpy.management.GetCount(CAMPUS_MASTER)[0])

    return {
        'master_ucids': master_count,
        'campus_total': campus_total,
        'campus_with_ucid': campus_with_ucid,
        'campus_unique_ucids': len(campus_ucid_values),
        'building_total': building_total,
        'building_with_ucid': building_with_ucid,
        'building_unique_ucids': len(building_ucid_values),
    }

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================

def main():
    print("="*80)
    print("UCID ASSIGNMENT TO GOLD TABLES")
    print(f"Started: {datetime.now()}")
    print(f"Method: {CHOSEN_METHOD}")
    print("="*80)

    # Determine source feature class
    if CHOSEN_METHOD == 'TIGHT':
        source_fc = CAMPUS_MASTER_TIGHT
    elif CHOSEN_METHOD == 'LOOSE':
        source_fc = CAMPUS_MASTER_LOOSE
    else:
        print(f"ERROR: Invalid CHOSEN_METHOD '{CHOSEN_METHOD}'. Use 'TIGHT' or 'LOOSE'.")
        return

    # Step 1: Verify source exists
    print("\n[Step 1] Verifying source campus_master...")

    if not arcpy.Exists(source_fc):
        print(f"   ERROR: {source_fc} not found.")
        print("   Run generate_ucid_clusters.py first.")
        return

    source_count = int(arcpy.management.GetCount(source_fc)[0])
    print(f"   - Found {source_count:,} UCIDs in {os.path.basename(source_fc)}")

    # Step 2: Create final campus_master
    print("\n[Step 2] Creating final campus_master...")
    master_count = create_final_campus_master(source_fc, CAMPUS_MASTER)
    print(f"   - campus_master has {master_count:,} records")

    # Step 3: Build mapping
    print("\n[Step 3] Building campus_id → UCID mapping...")
    campus_mapping = build_campus_id_to_ucid_map(CAMPUS_MASTER)
    print(f"   - Mapped {len(campus_mapping):,} source campus_ids to UCIDs")

    # Step 4: Add ucid field to gold tables
    print("\n[Step 4] Adding ucid field to gold tables...")
    add_ucid_field(GOLD_CAMPUS)
    add_ucid_field(GOLD_BUILDINGS)

    # Step 5: Assign UCIDs to gold_campus
    print("\n[Step 5] Assigning UCIDs to gold_campus_full...")
    campus_updated, campus_not_found = assign_ucid_to_gold_campus(campus_mapping)
    print(f"   - Updated {campus_updated:,} campus records")
    if campus_not_found > 0:
        print(f"   - Warning: {campus_not_found:,} records had no matching UCID")

    # Step 6: Assign UCIDs to gold_buildings
    print("\n[Step 6] Assigning UCIDs to gold_buildings_full...")
    building_updated, building_not_found = assign_ucid_to_gold_buildings(campus_mapping)
    print(f"   - Updated {building_updated:,} building records")
    if building_not_found > 0:
        print(f"   - Warning: {building_not_found:,} records had no matching UCID")

    # Step 7: Summary
    print("\n[Step 7] Generating summary statistics...")
    stats = generate_summary_stats()

    print("\n" + "="*80)
    print("UCID ASSIGNMENT COMPLETE")
    print("="*80)

    print(f"\n{'Feature Class':<30} {'Records':<15} {'With UCID':<15} {'Unique UCIDs':<15}")
    print("-"*75)
    print(f"{'campus_master':<30} {stats['master_ucids']:<15,} {'-':<15} {stats['master_ucids']:<15,}")
    print(f"{'gold_campus_full':<30} {stats['campus_total']:<15,} {stats['campus_with_ucid']:<15,} {stats['campus_unique_ucids']:<15,}")
    print(f"{'gold_buildings_full':<30} {stats['building_total']:<15,} {stats['building_with_ucid']:<15,} {stats['building_unique_ucids']:<15,}")

    # Validation
    print("\n" + "="*80)
    print("VALIDATION")
    print("="*80)

    if stats['campus_with_ucid'] == stats['campus_total']:
        print("\n✅ All campus records have UCIDs assigned")
    else:
        missing = stats['campus_total'] - stats['campus_with_ucid']
        print(f"\n⚠️  {missing:,} campus records missing UCIDs")

    if stats['building_with_ucid'] == stats['building_total']:
        print("✅ All building records have UCIDs assigned")
    else:
        missing = stats['building_total'] - stats['building_with_ucid']
        print(f"⚠️  {missing:,} building records missing UCIDs")

    # Cross-reference check
    if stats['campus_unique_ucids'] == stats['master_ucids']:
        print("✅ All UCIDs in campus_master are referenced by gold_campus")
    else:
        diff = stats['master_ucids'] - stats['campus_unique_ucids']
        print(f"⚠️  {diff:,} UCIDs in master not referenced by gold_campus")

    print(f"\nMethod used: {CHOSEN_METHOD} ({250 if CHOSEN_METHOD == 'TIGHT' else 1000}m tolerance)")
    print(f"Completed: {datetime.now()}")
    print("="*80)

    print("\n📋 Next Steps:")
    print("   1. Use 'ucid' field for cross-source comparisons")
    print("   2. Join incoming rumors/signals to campus_master by location")
    print("   3. Query by UCID to see all vendor data for a campus:")
    print(f"      SELECT * FROM gold_campus_full WHERE ucid = 'UCID-AMER-00001'")

# Execute
if __name__ == "__main__":
    main()
else:
    try:
        main()
    except Exception as e:
        print(f"\nERROR: {str(e)}")
        import traceback
        traceback.print_exc()
