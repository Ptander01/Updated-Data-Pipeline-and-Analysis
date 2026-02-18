"""
Diagnostic: Where is xAI and year forecast data?
Run in ArcGIS Pro Python window
"""

import arcpy
import os
from collections import defaultdict

GDB = r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\Default.gdb"
GOLD_COMBINED_XB = os.path.join(GDB, "gold_combined_xb")

print("="*70)
print("DIAGNOSTIC: PEER DATA LOCATION")
print("="*70)

# 1. Check xAI in all relevant fields
print("\n1. SEARCHING FOR xAI IN ALL COMPANY FIELDS...")
print("-"*50)

xai_fields = ['company_clean', 'company_source', 'company_clean_filter', 'end_user', 'tenant', 'developer']
fields_to_check = [f for f in xai_fields if f in [field.name for field in arcpy.ListFields(GOLD_COMBINED_XB)]]

for field in fields_to_check:
    # Count xAI occurrences
    where = f"{field} LIKE '%xAI%' OR {field} LIKE '%XAI%' OR {field} LIKE '%x.ai%'"
    try:
        count = 0
        with arcpy.da.SearchCursor(GOLD_COMBINED_XB, [field, 'record_level'], where) as cursor:
            building_count = 0
            campus_count = 0
            for row in cursor:
                count += 1
                if row[1] == 'Building':
                    building_count += 1
                else:
                    campus_count += 1
        print(f"  {field}: {count} records (Building: {building_count}, Campus: {campus_count})")
    except Exception as e:
        print(f"  {field}: Error - {e}")

# 2. Check where mw_2025+ data exists (Building vs Campus)
print("\n2. YEAR FORECAST DATA BY RECORD LEVEL...")
print("-"*50)

year_fields = ['mw_2025', 'mw_2026', 'mw_2027', 'mw_2028', 'mw_2029', 'mw_2030']
existing_year_fields = [f for f in year_fields if f in [field.name for field in arcpy.ListFields(GOLD_COMBINED_XB)]]

for year_field in existing_year_fields:
    where_has_data = f"{year_field} IS NOT NULL AND {year_field} > 0"
    building_count = 0
    campus_count = 0
    building_sum = 0
    campus_sum = 0

    with arcpy.da.SearchCursor(GOLD_COMBINED_XB, [year_field, 'record_level'], where_has_data) as cursor:
        for row in cursor:
            val = row[0] or 0
            if row[1] == 'Building':
                building_count += 1
                building_sum += val
            else:
                campus_count += 1
                campus_sum += val

    print(f"  {year_field}:")
    print(f"    Building: {building_count:,} records, {building_sum:,.0f} MW total")
    print(f"    Campus: {campus_count:,} records, {campus_sum:,.0f} MW total")

# 3. Check source distribution at Campus level
print("\n3. SOURCE DISTRIBUTION AT CAMPUS LEVEL...")
print("-"*50)

source_counts = defaultdict(int)
with arcpy.da.SearchCursor(GOLD_COMBINED_XB, ['source'], "record_level = 'Campus'") as cursor:
    for row in cursor:
        source_counts[row[0] or 'NULL'] += 1

for source, count in sorted(source_counts.items(), key=lambda x: -x[1]):
    print(f"  {source}: {count:,}")

# 4. Check what company_clean values exist for major hyperscalers
print("\n4. HYPERSCALER company_clean VALUES AT CAMPUS LEVEL...")
print("-"*50)

hyperscaler_patterns = ['AWS', 'Amazon', 'Google', 'Microsoft', 'Meta', 'Oracle', 'xAI', 'OpenAI', 'Apple']
company_counts = defaultdict(int)

with arcpy.da.SearchCursor(GOLD_COMBINED_XB, ['company_clean'], "record_level = 'Campus'") as cursor:
    for row in cursor:
        company = row[0] or 'NULL'
        company_counts[company] += 1

print("  Top 20 company_clean values:")
for company, count in sorted(company_counts.items(), key=lambda x: -x[1])[:20]:
    marker = " <-- HYPERSCALER" if company in hyperscaler_patterns else ""
    print(f"    {company}: {count:,}{marker}")

# 5. Check end_user values
print("\n5. TOP end_user VALUES AT CAMPUS LEVEL...")
print("-"*50)

end_user_counts = defaultdict(int)
with arcpy.da.SearchCursor(GOLD_COMBINED_XB, ['end_user'], "record_level = 'Campus'") as cursor:
    for row in cursor:
        eu = row[0] or 'NULL'
        end_user_counts[eu] += 1

print("  Top 20 end_user values:")
for eu, count in sorted(end_user_counts.items(), key=lambda x: -x[1])[:20]:
    marker = " <-- AI LAB" if eu in ['xAI', 'OpenAI', 'Anthropic', 'Meta', 'Google', 'Microsoft'] else ""
    print(f"    {eu}: {count:,}{marker}")

print("\n" + "="*70)
print("DIAGNOSTIC COMPLETE")
print("="*70)
