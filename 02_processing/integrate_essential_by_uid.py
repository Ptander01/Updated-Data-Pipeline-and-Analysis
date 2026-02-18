# -*- coding: utf-8 -*-
# integrate_essential_by_uid.py
# Integrates Essential DC list by matching exact Semianalysis Unique_IDs
#
# Run: exec(open(r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\scripts\02_processing\integrate_essential_by_uid.py", encoding="utf-8").read())

import arcpy
import os
from datetime import datetime
from collections import Counter

TARGET_GDB = r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\Default.gdb"
GOLD_BUILDINGS = os.path.join(TARGET_GDB, "gold_buildings_full")
GOLD_CAMPUS = os.path.join(TARGET_GDB, "gold_campus_full")
arcpy.env.overwriteOutput = True

# 129 Essential Building Unique_IDs (from GSheet: SemiAnalysis - SiteID 2025-09-25)
ESSENTIAL_UNIQUE_IDS = [
    "c4fe3714-5ab4-5906-a436-765ec360db47", "d384623a-5b15-5537-994b-2aac364cfd2f",
    "d5ae3714-5ab4-5906-a436-765ec360db47", "d154623a-5b15-5537-994b-2aac364cfc1a",
    "d2ae3714-5ab4-5906-a436-765ec360da21", "91a4623a-5b15-5537-994b-2aac364cfc4c",
    "d5bf3714-5ab4-5906-a436-765ec360db14", "c274623a-5b15-5537-994b-2aac364cfd2f",
    "8e5a9a10-f7e6-422b-ac62-b0c50a416eb2", "225a9a10-f7e6-422b-ac62-b0c50a416aa1",
    "bc919877-7644-5205-b2cd-dea83220223a", "11112983-0691-5e77-bab2-a5843caaa4b1",
    "8a401491-dbbd-451c-9851-8d710fe333df", "a232e8ba-1ce0-5392-9ce6-c8664591422a",
    "b111e8ba-1ce0-5392-9ce6-c8664597111a", "c4fe3714-5ab4-5906-a436-765ec360db22",
    "aae47de5-3863-55dc-afbc-fea5f1ca98df", "ddd61468-0ea6-5c77-9ed6-94d52111f1d1",
    "4d030c61-3a2f-570a-8937-7323aaa786d2", "807acac7-96b4-506f-85da-4b25d4c00c20",
    "a8549b03-4425-421a-a7b3-4f1a2ebf3a7f", "574dab2b-94d8-59a1-8550-ac8b64400713",
    "574dab2b-94d8-59a1-8550-ac8b64400712", "67de4513-7b99-5305-8f5d-91777539f666",
    "67de4513-7b99-5305-8f5d-91887539f556", "67de4513-7b99-5305-8f5d-91777539f116",
    "67de4544-7b99-5305-8f5d-91777539f556", "67de4513-7b99-5305-8f5d-91777539f556",
    "836dd8aa-8fe4-54be-9aa2-2994dec6dc82", "7baf5237-3f4f-52f1-b091-ba9e1ccde852",
    "270ea40a-e513-5929-9b82-d7c709001766", "bb6aba43-3e26-5361-81c6-d10a98aa858e",
    "e81811ac-d7d7-55c2-acff-9c2bbfda79f1", "e81811ac-d7d7-55c2-acff-9c2bbfda89f1",
    "e81811ac-d7d7-55c2-acff-9c2bbfda79f5", "d11811ac-d7d7-55c2-acff-9c2bbfda79f1",
    "a0518892-0956-5854-8b74-06329fcc45dc", "a0518892-0956-5854-8b74-06329fcdfc54",
    "a0518892-0956-5854-8b74-06329fcaed45", "a0518892-0956-5854-8b74-06329fcdc54f",
    "a0518892-0956-5854-8b74-06329fc995fd", "a0518892-0956-5854-8b74-06329fc44aed",
    "a0518892-0956-5854-8b74-06329fcaed54", "a0518892-0956-5854-8b74-06329fcdccb2",
    "a0518892-0956-5854-8b74-06329fcbb225", "a0518892-0956-5854-8b74-06329fc598bb",
    "a0518892-0956-5854-8b74-06329fcdbd54", "6f182557-7db7-5ab3-95bb-78364f6e0bd8",
    "b174e39c-96bb-5093-ba7e-1dc769c94a82", "b174e39c-96bb-5093-ba7e-1dc769c55469",
    "b174e39c-96bb-5093-ba7e-1dc769c9935f", "b174e39c-96bb-5093-ba7e-1dc769cf2541",
    "b174e39c-96bb-5093-ba7e-1dc769cd62ba", "b174e39c-96bb-5093-ba7e-1dc769ca9574",
    "b174e39c-96bb-5093-ba7e-1dc769caab35", "b174e39c-96bb-5093-ba7e-1dc769c4598b",
    "b174e39c-96bb-5093-ba7e-1dc769c12bdf", "b174e39c-96bb-5093-ba7e-1dc769c94a81",
    "3305841e-b369-5cee-9fda-9cb0b095829c", "29dbe077-648c-5592-9be0-83fcf69cacb0",
    "a06cc549-d13c-5be1-98c0-1ac5e3e46d01", "8bbed48d-106e-5003-9b9b-c5c53315a81c",
    "1741d2d7-ea9f-5fbe-8315-4cc82db3ed78", "6baf4d18-43bd-5a16-8f59-92c8cf0cc503",
    "762ab670-df31-533b-8a49-c7e7649cf9b9", "762ab670-df31-533b-8a49-c7e7649cf9c9",
    "c5664204-ea7d-5204-9e2b-23f47c0d3637", "038a84ba-534e-5a0d-b02d-0308b8f514d5",
    "20844e97-362a-5856-b0bd-d35a7dc8d070", "ac4e3164-c361-5d4e-85a2-498058e258b7",
    "217019e0-3067-57bb-b365-da91563a4de0", "b1a39188-bac8-5f03-bc0b-ae4967e57dfd",
    "00bfa1a3-8caf-51fe-8f02-4f290661d4b1", "18ad80d3-8809-5e32-95e8-0121f734c20c",
    "f771a0b6-1417-5421-9375-1ff4da7d5a22", "b8ce7dde-4360-5cb2-8c51-97943b5300e7",
    "6eefc952-cb6b-56eb-ae44-4b74f3edf8ad", "6ac9de20-a713-5561-b4c7-4dfdfece0ded",
    "7f31e3c4-3255-53e5-8f16-546e71f42be2", "2c7760ec-c296-52cc-8e10-e7f05495abad",
    "acbdd058-d082-5a1a-879b-5c32a69d0d89", "cabdd058-d082-5a1a-879b-5c32a69d0d89",
    "ccbdd058-d082-5a1a-879b-5c32a69d0d89", "a7b0a754-3b28-54aa-bfc1-d29267bec8fa",
    "668b2bf3-9ade-5614-bafe-fe04d8f13d01", "eb9ab3c4-cea8-510b-a808-2a015e7c19dd",
    "0f803b9b-6057-5668-b41e-1981486164b9", "b89986e4-dc6e-5de6-a0f1-0f3354704e0d",
    "f7cca9d7-1c2f-5f1d-b790-1c49bb8cff91", "090defa9-bece-5cb3-9438-e1d21f49560a",
    "749864fd-05cb-51fd-9ab5-e5e7749becb9", "51f6ac63-69d3-5cbf-9d8a-2e9f8a04bf8c",
    "442399f1-48d3-588e-8c54-950d1cb62b04", "11659285-16f9-5f40-9d29-8fca0a541ebd",
    "1de4b1c5-3e27-5b83-b44f-ba6d9e00f227", "e15da5ef-1535-529c-84d1-851b5c0fd3f9",
    "8a4bf5d8-9d40-52b6-84f8-94fc815e6049", "baa78955-0bfb-5872-a56b-9c784bb3cd1c",
    "2c1b8130-6433-5809-8595-2f2650ad2487", "bcb16e30-876f-5c67-9f89-32f70a4c5d07",
    "6160595d-407f-51c4-b228-a57b5b125cd0", "9bfc93e3-c5af-5437-b9b7-ef29d42658a8",
    "8ff753d0-01c6-5239-81a0-c59094c0ebbd", "f7036d6b-d4d2-5546-83f4-4604b3f42812",
    "b36fea82-b10a-5b53-bf2d-acc8a3976dd8", "1e63ba6c-d833-5bca-b925-ce4d2efe7aab",
    "9fa05b43-3956-5bf0-a51f-b1a4bf8eaafb", "1f71c711-d06d-5de2-815b-d3092a290d9d",
    "cffdd3ab-6ef1-5036-9606-c6c936e22305", "91adbc22-741c-5a0c-8852-9ee808a08781",
    "9e8ae955-5a7b-5765-96ef-71f6b1d4e81c", "904e766e-5dc7-5e2f-b1db-d3dfc7df0322",
    "530c929e-b491-56c4-baa0-3aad72c171fa", "51978f19-129d-5176-ad37-3201ad8dddb8",
    "40ede3f8-845d-5942-b028-00ceecf3366a", "530c929e-b491-56c4-bba0-3aad72c171fa",
    "7d129335-aa32-5aed-aae4-0c4cf4d0cdf6", "c6b3915c-b405-5077-912c-7352c63f4f8b",
    "7d009335-aa32-5aed-aae4-0c4cf4d0cdf6", "0715ddf7-4bc0-598b-9b54-dd47e3837ca5",
    "0715ddf7-4bc0-598b-9b54-dd47e3837ca8", "24935bde-4578-4032-ae36-43261a63cdbf",
    "c42eb244-02d7-5d37-ba08-05fa7b48cc9b", "20d1d406-67f6-5221-8550-4a1c95051ee2",
    "2e5e134b-cf5a-557d-a746-b6e2b0e73e47", "277f905c-2228-588f-98d0-b0836b43fd76",
    "a72d9ca2-0a21-5dd0-a603-06e3bd81f511", "b72d9ca2-0a21-5dd0-a603-06e3bd81f511",
    "c72d9ca2-0a21-5dd0-a603-06e3bd81f511",
]
ESSENTIAL_UID_SET = set(ESSENTIAL_UNIQUE_IDS)

print("="*70)
print("ESSENTIAL DC INTEGRATION (By Exact SA Unique_ID)")
print("="*70)
print(f"\n  Total Essential Unique_IDs: {len(ESSENTIAL_UNIQUE_IDS)}")
print(f"  Unique IDs (after dedup): {len(ESSENTIAL_UID_SET)}")

# =============================================================================
# STEP 1: Match buildings by source_unique_id
# =============================================================================
print("\n[Step 1] Matching buildings by source_unique_id...")

matched_buildings = []
matched_ucids = set()  # Changed from campus_id to ucid

with arcpy.da.SearchCursor(
    GOLD_BUILDINGS,
    ['unique_id', 'source_unique_id', 'building_designation', 'ucid',
     'source', 'company_clean', 'city', 'state_abbr']
) as cursor:
    for row in cursor:
        unique_id, source_uid, bldg_desig, ucid, source, company, city, state = row
        if source == 'Semianalysis' and source_uid and source_uid in ESSENTIAL_UID_SET:
            matched_buildings.append({
                'unique_id': unique_id,
                'source_unique_id': source_uid,
                'building_designation': bldg_desig,
                'ucid': ucid,  # Changed from campus_id
                'company': company,
                'city': city,
                'state': state
            })
            if ucid:
                matched_ucids.add(ucid)  # Changed from campus_id

print(f"\n  Matched {len(matched_buildings)} of {len(ESSENTIAL_UID_SET)} Essential buildings")
print(f"  Covering {len(matched_ucids)} unique UCIDs")  # Updated message

# Check for unmatched IDs
matched_uids = set(b['source_unique_id'] for b in matched_buildings)
unmatched_uids = ESSENTIAL_UID_SET - matched_uids
if unmatched_uids:
    print(f"\n  WARNING: {len(unmatched_uids)} Essential IDs not found:")
    for uid in list(unmatched_uids)[:5]:
        print(f"    - {uid}")
    if len(unmatched_uids) > 5:
        print(f"    ... and {len(unmatched_uids) - 5} more")

# Show sample matches
print(f"\n  Sample matched buildings (first 10):")
for b in matched_buildings[:10]:
    print(f"    - {b['company']} - {b['city']}, {b['state']} ({b['building_designation']})")

# =============================================================================
# STEP 2: Add is_essential field to gold_buildings_full
# =============================================================================
print("\n[Step 2] Marking Essential buildings in gold_buildings_full...")

bldg_fields = [f.name for f in arcpy.ListFields(GOLD_BUILDINGS)]
if 'is_essential' not in bldg_fields:
    arcpy.management.AddField(GOLD_BUILDINGS, 'is_essential', 'SHORT', field_alias='Essential Site')
    print("  Added 'is_essential' field to gold_buildings_full")

matched_bldg_uids = set(b['unique_id'] for b in matched_buildings)
bldg_update_count = 0
with arcpy.da.UpdateCursor(GOLD_BUILDINGS, ['unique_id', 'is_essential']) as cursor:
    for row in cursor:
        if row[0] in matched_bldg_uids:
            row[1] = 1
            bldg_update_count += 1
        else:
            row[1] = 0
        cursor.updateRow(row)

print(f"  Marked {bldg_update_count} buildings as Essential")

# =============================================================================
# STEP 3: Campus is_essential will be handled by campus_rollup aggregation
# =============================================================================
print("\n[Step 3] Campus Essential flagging...")

# NOTE: Campus is_essential is now handled AUTOMATICALLY by campus_rollup_new.py
# The rollup dissolves buildings by UCID and aggregates is_essential using MAX
# This means if ANY building in a campus is essential, the campus will be marked essential
#
# We still try to match here as a verification, but the real work is done by the rollup

campus_fields = [f.name for f in arcpy.ListFields(GOLD_CAMPUS)]
if 'is_essential' not in campus_fields:
    arcpy.management.AddField(GOLD_CAMPUS, 'is_essential', 'SHORT', field_alias='Essential Site')
    print("  Added 'is_essential' field to gold_campus_full")

# Try to match using campus_id (contains UCID after rollup) or ucid field
# Priority: campus_id (populated by rollup), then ucid (populated by cleanup)
campus_id_field = None
if 'campus_id' in campus_fields:
    campus_id_field = 'campus_id'
elif 'ucid' in campus_fields:
    campus_id_field = 'ucid'

campus_update_count = 0
matched_campus_ucids_final = set()

if campus_id_field:
    with arcpy.da.UpdateCursor(GOLD_CAMPUS, [campus_id_field, 'is_essential']) as cursor:
        for row in cursor:
            if row[0] in matched_ucids:
                row[1] = 1
                campus_update_count += 1
                matched_campus_ucids_final.add(row[0])
            else:
                row[1] = 0
            cursor.updateRow(row)
    print(f"  Marked {campus_update_count} campuses as Essential (matched via {campus_id_field})")
else:
    print("  WARNING: No campus ID field found - campus marking skipped")
    print("  Campus is_essential will be set by campus_rollup aggregation (MAX of building values)")

if campus_update_count == 0 and len(matched_ucids) > 0:
    print(f"  NOTE: 0 campuses matched - this is expected if pipeline runs in order:")
    print(f"        1. This script marks BUILDINGS with is_essential=1")
    print(f"        2. campus_rollup_new.py will aggregate is_essential via MAX")
    print(f"        3. Final campus table will have {len(matched_ucids)} Essential campuses")

# =============================================================================
# STEP 4: Create essential_consensus layer
# =============================================================================
print("\n[Step 4] Creating essential_consensus layer...")

essential_consensus_path = os.path.join(TARGET_GDB, "essential_consensus")
if arcpy.Exists(essential_consensus_path):
    arcpy.management.Delete(essential_consensus_path)

arcpy.analysis.Select(GOLD_CAMPUS, essential_consensus_path, "is_essential = 1")
essential_count = int(arcpy.management.GetCount(essential_consensus_path)[0])
print(f"  Created essential_consensus with {essential_count} campuses")

# =============================================================================
# STEP 5: Export Essential UCIDs
# =============================================================================
print("\n[Step 5] Exporting Essential UCIDs...")

ucid_path = r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\scripts\07_consensus\essential_ucids.txt"
with open(ucid_path, 'w') as f:
    f.write("# Essential Site UCIDs (Verified by SA Unique_ID)\n")
    f.write(f"# Generated: {datetime.now()}\n")
    f.write(f"# Buildings matched: {len(matched_buildings)}\n")
    f.write(f"# Campuses: {campus_update_count}\n\n")
    f.write("ESSENTIAL_SITE_UCIDS = [\n")
    for ucid in sorted(matched_campus_ucids_final):
        f.write(f'    "{ucid}",\n')
    f.write("]\n")
print(f"  Exported {len(matched_campus_ucids_final)} UCIDs")

# =============================================================================
# SUMMARY
# =============================================================================
print("\n" + "="*70)
print("INTEGRATION COMPLETE")
print("="*70)
print(f"""
  Essential Unique_IDs provided: {len(ESSENTIAL_UID_SET)}
  Buildings matched: {len(matched_buildings)}
  Buildings not found: {len(unmatched_uids)}
  Campuses marked: {campus_update_count}

  Updated:
    - gold_buildings_full.is_essential
    - gold_campus_full.is_essential
    - essential_consensus layer
    - 07_consensus/essential_ucids.txt
""")
