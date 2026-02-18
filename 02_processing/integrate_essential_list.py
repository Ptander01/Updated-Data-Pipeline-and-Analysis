# -*- coding: utf-8 -*-
# integrate_essential_list.py
# Integrates the Essential DC list into the Consensus DC Model
#
# This script uses ATTRIBUTE MATCHING (not spatial) to link Essential sites
# to our consensus campuses by matching the cluster field directly.
#
# Steps:
# 1. Copies Essential list to our project geodatabase
# 2. Builds lookup from building_designation in gold_buildings_full
# 3. Matches Essential.cluster to Semianalysis cluster values
# 4. Adds 'is_essential' flag to gold_campus_full
# 5. Creates essential_consensus layer (filtered view)
# 6. Exports Essential UCIDs for weighted scoring
#
# Run in ArcGIS Pro Python console:
# exec(open(r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\scripts\02_processing\integrate_essential_list.py", encoding="utf-8").read())

import arcpy
import os
import sys
import re
from datetime import datetime

# Paths
SOURCE_GDB = r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Natural Gas and Data Centers\Default.gdb"
SOURCE_FC = "SAEssentialPee_FeatureToPoin"
SOURCE_PATH = os.path.join(SOURCE_GDB, SOURCE_FC)

TARGET_GDB = r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\Default.gdb"
ESSENTIAL_FC = "essential_dc_list"
ESSENTIAL_PATH = os.path.join(TARGET_GDB, ESSENTIAL_FC)

GOLD_CAMPUS = os.path.join(TARGET_GDB, "gold_campus_full")
GOLD_BUILDINGS = os.path.join(TARGET_GDB, "gold_buildings_full")

arcpy.env.overwriteOutput = True


def slug(text):
    """
    Generate URL-safe slug from text.
    Same function used in ingest_semianalysis.py for campus_id generation.
    """
    if not text:
        return ''
    return re.sub(r'[^a-z0-9]+', '', str(text).lower())


def parse_essential_cluster(cluster_value):
    """
    Parse Essential list cluster format: {Company}_{City}_{Number}
    Examples: 'AWS_Attalia_1', 'Microsoft_Cheyenne_1', 'Google_Fort Wayne_1'

    Returns: (company, city) tuple
    """
    if not cluster_value:
        return (None, None)

    # Split on underscore
    parts = cluster_value.split('_')

    if len(parts) < 3:
        return (None, None)

    # First part is company
    company = parts[0]

    # Last part is the number (e.g., "1"), skip it
    # Middle parts are the city (may have multiple parts like "Fort Wayne")
    city_parts = parts[1:-1]  # Everything between company and number
    city = ' '.join(city_parts) if city_parts else None

    return (company, city)


def normalize_company(company):
    """
    Normalize company names for matching.
    Handles variations like AWS/Amazon, etc.
    """
    if not company:
        return ''

    company_lower = company.lower().strip()

    # Company normalization mappings
    mappings = {
        'aws': 'aws',
        'amazon': 'aws',
        'microsoft': 'microsoft',
        'google': 'google',
        'meta': 'meta',
        'facebook': 'meta',
        'xai': 'xai',
        'switch': 'switch',
        'stack': 'stack',
        'stack infrastructure': 'stack',
        'vantage': 'vantage',
        'vantage data centers': 'vantage',
        'edgeconnex': 'edgeconnex',
        'crusoe': 'crusoe',
        'lancium': 'lancium',
        'tract': 'tract',
    }

    # Check for matches
    for key, normalized in mappings.items():
        if key in company_lower or company_lower.startswith(key):
            return normalized

    return company_lower


print("="*70)
print("ESSENTIAL DC LIST INTEGRATION (Attribute Matching)")
print("="*70)

# =============================================================================
# STEP 1: Copy Essential list to our project
# =============================================================================
print("\n[Step 1] Copying Essential list to project geodatabase...")

if not arcpy.Exists(SOURCE_PATH):
    print(f"  ❌ ERROR: Source not found: {SOURCE_PATH}")
    raise Exception("Source feature class not found")

# Delete existing if present
if arcpy.Exists(ESSENTIAL_PATH):
    arcpy.management.Delete(ESSENTIAL_PATH)
    print(f"  Deleted existing {ESSENTIAL_FC}")

arcpy.management.Copy(SOURCE_PATH, ESSENTIAL_PATH)
essential_count = int(arcpy.management.GetCount(ESSENTIAL_PATH)[0])
print(f"  ✓ Copied {essential_count} Essential sites to project")

# =============================================================================
# STEP 2: Build cluster lookup from gold_buildings_full (Semianalysis only)
# =============================================================================
print("\n[Step 2] Building cluster lookup from gold_buildings_full...")

# The original cluster value from Semianalysis is stored in building_designation
# We can match Essential.cluster directly to building_designation
# Then get the campus_id from the building record

cluster_to_campus = {}  # cluster (e.g., "AWS_Atlanta_1") -> campus_id
campus_fields = ['building_designation', 'campus_id', 'source', 'company_clean', 'city']

with arcpy.da.SearchCursor(GOLD_BUILDINGS, campus_fields) as cursor:
    for row in cursor:
        building_designation, campus_id, source, company, city = row
        if source == 'Semianalysis' and building_designation and campus_id:
            # Store the cluster -> campus_id mapping
            # Use the raw cluster value as key
            cluster_key = building_designation.strip()
            if cluster_key not in cluster_to_campus:
                cluster_to_campus[cluster_key] = {
                    'campus_id': campus_id,
                    'source': source,
                    'company': company,
                    'city': city
                }

print(f"  ✓ Built lookup with {len(cluster_to_campus)} unique Semianalysis cluster values")

# Show sample cluster values
sample_clusters = list(cluster_to_campus.keys())[:10]
print(f"  Sample cluster values: {sample_clusters}")

# =============================================================================
# STEP 3: Match Essential sites by direct cluster value
# =============================================================================
print("\n[Step 3] Matching Essential sites by direct cluster value...")

# Read Essential list - match cluster field directly
essential_fields = ['cluster', 'MAX_company', 'FIRST_city', 'FIRST_us_state']
matched_ucids = set()
unmatched_sites = []
match_details = []

with arcpy.da.SearchCursor(ESSENTIAL_PATH, essential_fields) as cursor:
    for row in cursor:
        cluster = row[0]
        max_company = row[1]
        first_city = row[2]
        state = row[3]

        if not cluster:
            continue

        cluster_key = cluster.strip()
        site_key = f"{max_company} - {first_city}, {state}"

        # Try exact match on cluster value
        if cluster_key in cluster_to_campus:
            match_info = cluster_to_campus[cluster_key]
            matched_ucids.add(match_info['campus_id'])
            match_details.append({
                'site': site_key,
                'cluster': cluster,
                'matched_id': match_info['campus_id'],
                'matched_source': match_info['source'],
                'match_type': 'EXACT (cluster)'
            })
        else:
            # Try case-insensitive match
            cluster_lower = cluster_key.lower()
            found = False
            for key, info in cluster_to_campus.items():
                if key.lower() == cluster_lower:
                    matched_ucids.add(info['campus_id'])
                    match_details.append({
                        'site': site_key,
                        'cluster': cluster,
                        'matched_id': info['campus_id'],
                        'matched_source': info['source'],
                        'match_type': 'CASE-INSENSITIVE (cluster)'
                    })
                    found = True
                    break

            if not found:
                # Try partial match (without trailing number)
                # e.g., "AWS_Atlanta_1" -> try matching "AWS_Atlanta"
                parts = cluster_key.rsplit('_', 1)
                if len(parts) == 2 and parts[1].isdigit():
                    prefix = parts[0]
                    partial_matches = [k for k in cluster_to_campus.keys()
                                      if k.startswith(prefix + '_')]
                    if partial_matches:
                        match_key = partial_matches[0]
                        info = cluster_to_campus[match_key]
                        matched_ucids.add(info['campus_id'])
                        match_details.append({
                            'site': site_key,
                            'cluster': cluster,
                            'matched_id': info['campus_id'],
                            'matched_source': info['source'],
                            'match_type': f'PARTIAL (prefix: {prefix})'
                        })
                        found = True

                if not found:
                    unmatched_sites.append({
                        'site': site_key,
                        'cluster': cluster,
                        'lookup_key': cluster_key
                    })

print(f"\n  Match Summary:")
print(f"    ✓ Matched: {len(matched_ucids)} unique campus_ids")
print(f"    ✗ Unmatched: {len(unmatched_sites)} sites")

# Show match details
exact_matches = [m for m in match_details if 'EXACT' in m['match_type']]
fuzzy_matches = [m for m in match_details if 'FUZZY' in m['match_type']]

print(f"\n  Exact Matches: {len(exact_matches)}")
print(f"  Fuzzy Matches: {len(fuzzy_matches)}")

if match_details:
    print(f"\n  Sample Matches (first 15):")
    for m in match_details[:15]:
        match_type_icon = "✓" if 'EXACT' in m['match_type'] else "~"
        print(f"    {match_type_icon} {m['site'][:35]:<35} → {m['matched_id'][:35]} ({m['matched_source']})")

if unmatched_sites:
    print(f"\n  Unmatched Sites ({len(unmatched_sites)}):")
    for site in unmatched_sites[:10]:
        print(f"    ✗ {site['site'][:40]:<40} (tried: {site['lookup_key'][:25]})")
    if len(unmatched_sites) > 10:
        print(f"    ... and {len(unmatched_sites) - 10} more")

# =============================================================================
# STEP 4: Add is_essential field to gold_campus_full
# =============================================================================
print("\n[Step 4] Adding 'is_essential' field to gold_campus_full...")

# Check if field exists
campus_field_list = [f.name for f in arcpy.ListFields(GOLD_CAMPUS)]
if 'is_essential' not in campus_field_list:
    arcpy.management.AddField(GOLD_CAMPUS, 'is_essential', 'SHORT', field_alias='Essential Site')
    print("  ✓ Added 'is_essential' field")
else:
    print("  Field 'is_essential' already exists")

# Build a lookup of Essential site attributes for matching to gold_campus_full
# Since campus_id format may differ, we match on (company, city) from Essential list
essential_company_city = set()
for match in match_details:
    # Parse company and city from site key format: "Company - City, State"
    site = match['site']
    parts = site.split(' - ')
    if len(parts) >= 2:
        company = parts[0].strip()
        city_state = parts[1].split(',')[0].strip()
        essential_company_city.add((normalize_company(company), city_state.lower()))

print(f"  Looking for {len(essential_company_city)} unique company+city combinations")

# Update field based on company+city matches
updated_count = 0
matched_campus_ucids = set()  # Track actual gold_campus_full UCIDs
with arcpy.da.UpdateCursor(GOLD_CAMPUS, ['campus_id', 'company_clean', 'city', 'is_essential']) as cursor:
    for row in cursor:
        campus_id = row[0]
        company = row[1]
        city = row[2]

        # Normalize for matching
        company_norm = normalize_company(company) if company else ''
        city_lower = city.lower() if city else ''

        if (company_norm, city_lower) in essential_company_city:
            row[3] = 1
            updated_count += 1
            matched_campus_ucids.add(campus_id)
        else:
            row[3] = 0
        cursor.updateRow(row)

print(f"  ✓ Marked {updated_count} campuses as Essential")

# Update matched_ucids to use actual gold_campus_full UCIDs for export
matched_ucids = matched_campus_ucids

# =============================================================================
# STEP 5: Create essential_consensus layer (filtered view)
# =============================================================================
print("\n[Step 5] Creating essential_consensus layer...")

essential_consensus_path = os.path.join(TARGET_GDB, "essential_consensus")
if arcpy.Exists(essential_consensus_path):
    arcpy.management.Delete(essential_consensus_path)

# Select and export Essential campuses
arcpy.analysis.Select(
    in_features=GOLD_CAMPUS,
    out_feature_class=essential_consensus_path,
    where_clause="is_essential = 1"
)

essential_count = int(arcpy.management.GetCount(essential_consensus_path)[0])
print(f"  ✓ Created essential_consensus with {essential_count} campuses")

# =============================================================================
# STEP 6: Export Essential UCIDs for authority_config.py
# =============================================================================
print("\n[Step 6] Exporting Essential UCIDs...")

# Write UCIDs to a text file for easy reference
ucid_export_path = os.path.join(
    r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\scripts\07_consensus",
    "essential_ucids.txt"
)

with open(ucid_export_path, 'w') as f:
    f.write("# Essential Site UCIDs\n")
    f.write(f"# Generated: {datetime.now()}\n")
    f.write(f"# Total: {len(matched_ucids)} UCIDs\n\n")

    f.write("ESSENTIAL_SITE_UCIDS = [\n")
    for ucid in sorted(matched_ucids):
        f.write(f'    "{ucid}",\n')
    f.write("]\n")

print(f"  ✓ Exported {len(matched_ucids)} UCIDs to essential_ucids.txt")

# =============================================================================
# STEP 7: Summary complete (no temp files with attribute matching)
# =============================================================================
print("\n[Step 7] Finalizing...")

# =============================================================================
# SUMMARY
# =============================================================================
print("\n" + "="*70)
print("INTEGRATION COMPLETE")
print("="*70)
print(f"""
  Essential Sites Imported: {essential_count}
  Consensus Campuses Matched: {updated_count}
  Unmatched Sites: {len(unmatched_sites)}

  New Feature Classes:
    • essential_dc_list (imported Essential sites)
    • essential_consensus (filtered consensus for Essential sites only)

  Updated Feature Classes:
    • gold_campus_full (added 'is_essential' field)

  Files Created:
    • 07_consensus/essential_ucids.txt (UCID list for weighted scoring)

  Next Steps:
    1. Review unmatched sites - may need manual matching or wider search radius
    2. Update authority_config.py to import ESSENTIAL_SITE_UCIDS
    3. Update weighted consensus scoring to prioritize Essential sites
""")
