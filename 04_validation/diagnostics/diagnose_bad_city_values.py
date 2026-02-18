"""
Diagnostic: Find records with zip codes in city field
"""
import arcpy
import re

GDB = r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\Default.gdb"
GOLD_BUILDINGS = f"{GDB}\\gold_buildings_full"

# Pattern to match US zip codes or state abbreviations used as city
zip_pattern = re.compile(r'^[A-Z]{2}\d{5}$|^\d{5}$|^[A-Z]{2}$')

print("=" * 70)
print("DIAGNOSTIC: Records with zip codes or state abbr in city field")
print("=" * 70)

# Track by source
issues_by_source = {}
sample_records = {}

with arcpy.da.SearchCursor(GOLD_BUILDINGS, ['source', 'city', 'state', 'unique_id', 'company_clean']) as cursor:
    for row in cursor:
        source = row[0] or 'Unknown'
        city = row[1] or ''
        state = row[2] or ''
        unique_id = row[3] or ''
        company = row[4] or ''

        # Check for zip code patterns
        is_issue = False

        # US zip code pattern (5 digits or state+5 digits)
        if re.match(r'^\d{5}(-\d{4})?$', city):
            is_issue = True
        elif re.match(r'^[A-Z]{2}\d{5}$', city):  # e.g., "GA30025"
            is_issue = True
        elif re.match(r'^[A-Z]{2}$', city) and len(city) == 2:  # Just state abbr
            is_issue = True
        elif city and city.upper() == city and len(city) <= 3:  # Short uppercase codes
            is_issue = True

        if is_issue:
            if source not in issues_by_source:
                issues_by_source[source] = 0
                sample_records[source] = []

            issues_by_source[source] += 1

            if len(sample_records[source]) < 5:
                sample_records[source].append({
                    'city': city,
                    'state': state,
                    'company': company,
                    'unique_id': unique_id
                })

# Print results
print(f"\n{'Source':<25} {'Bad City Values':<15}")
print("-" * 40)

for source, count in sorted(issues_by_source.items(), key=lambda x: -x[1]):
    print(f"{source:<25} {count:<15}")

print(f"\n{'='*70}")
print("SAMPLE RECORDS BY SOURCE")
print("=" * 70)

for source, samples in sample_records.items():
    print(f"\n{source}:")
    for s in samples:
        print(f"   City: '{s['city']}', State: '{s['state']}', Company: {s['company']}")

print("\nDone!")
