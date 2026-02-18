import arcpy

gdb_path = r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\Default.gdb"
buildings_fc = f"{gdb_path}\\gold_buildings"

print("Starting company name corrections...")

update_count = 0
with arcpy.da.UpdateCursor(buildings_fc, ['company_clean', 'unique_id']) as cursor:
    for row in cursor:
        if row[0] == 'Mortenson':
            print(f"  Correcting {row[1]}: Mortenson → Meta")
            row[0] = 'Meta'
            cursor.updateRow(row)
            update_count += 1

print(f"\nUpdated {update_count} records")
print("\n" + "="*60)
print("Company name corrections complete!")
print("="*60)
print("\nNext step: Re-run Campus_Rollup_new.py to update aggregations")