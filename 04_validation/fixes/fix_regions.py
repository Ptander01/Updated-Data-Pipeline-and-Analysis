import arcpy

gdb_path = r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\Default.gdb"
campus_fc = f"{gdb_path}\\gold_campus"
buildings_fc = f"{gdb_path}\\gold_buildings"

region_map = {
    'NorthAmerica': 'AMER',
    'North America': 'AMER',
    'Americas': 'AMER',
    'Europe': 'EMEA',
    'Middle East': 'EMEA',
    'Asia': 'APAC',
    'Asia Pacific': 'APAC',
    'Pacific': 'APAC'
}

print("Starting region standardization...")

for fc in [buildings_fc, campus_fc]:
    fc_name = fc.split("\\")[-1]
    print(f"\nProcessing {fc_name}...")
    update_count = 0
    with arcpy.da.UpdateCursor(fc, ['region']) as cursor:
        for row in cursor:
            if row[0] and row[0] in region_map:
                old_region = row[0]
                row[0] = region_map[row[0]]
                cursor.updateRow(row)
                update_count += 1
    print(f"  Updated {update_count} records in {fc_name}")

print("\n" + "="*60)
print("Region standardization complete!")
print("="*60)
print("\nNext step: Re-run Campus_Rollup_new.py to update aggregations")