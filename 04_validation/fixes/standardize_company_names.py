"""
Standardize Company Names
Applies company name standardization to gold_buildings_full and gold_campus_full.

This script:
1. Maps known variations to canonical company names
2. Updates company_clean field in both gold tables
3. Preserves original name in company_source field

Run audit_company_names.py FIRST to see what variations exist.

Author: Meta Data Center GIS Team
Last Updated: 2024-12-17
"""

import arcpy
import os
import sys
from collections import defaultdict
from datetime import datetime

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

# ============================================================================
# COMPANY STANDARDIZATION MAP
# ============================================================================
# Format: 'source_variation': 'canonical_name'
# Add new mappings here as you discover variations

# -------------------------------------------------------------------------
# HYPERSCALERS - These companies KEEP their distinct names for XB filtering
# -------------------------------------------------------------------------

HYPERSCALERS_KEEP = {
    # Cloud Hyperscalers
    'Meta', 'AWS', 'Google', 'Microsoft', 'Oracle', 'Apple',

    # AI Companies
    'xAI', 'Anthropic',

    # Asian Tech Giants
    'ByteDance', 'TikTok', 'Alibaba', 'Tencent', 'Baidu',

    # Enterprise Tech
    'IBM', 'Salesforce',
}

# Variations that map to hyperscaler canonical names
COMPANY_MAP = {
    # =========================================================================
    # HYPERSCALERS (Keep distinct - for XB filtering)
    # -------------------------------------------------------------------------

    # Amazon / AWS - ALL VARIATIONS
    'Amazon': 'AWS',
    'Amazon Web Services': 'AWS',
    'Amazon.com': 'AWS',
    'Amazon.com Services LLC': 'AWS',
    'Amazon Data Services': 'AWS',
    'Amazon AWS': 'AWS',  # From DCM
    'AWS': 'AWS',

    # Meta / Facebook
    'Facebook': 'Meta',
    'Facebook, Inc.': 'Meta',
    'Meta': 'Meta',
    'Meta Platforms': 'Meta',
    'Meta Platforms, Inc.': 'Meta',
    'Mortenson': 'Meta',  # Mortenson is a contractor that builds for Meta

    # Google / Alphabet
    'Google': 'Google',
    'Google LLC': 'Google',
    'Google Cloud': 'Google',
    'Alphabet': 'Google',
    'Alphabet Inc.': 'Google',

    # Microsoft / Azure - ALL VARIATIONS
    'Microsoft': 'Microsoft',
    'Microsoft Corporation': 'Microsoft',  # From NPM
    'Microsoft Azure': 'Microsoft',
    'Azure': 'Microsoft',

    # Oracle (includes Stargate partners)
    'Oracle': 'Oracle',
    'Oracle Corporation': 'Oracle',
    'Oracle America': 'Oracle',
    'Oracle America, Inc.': 'Oracle',
    'Lancium': 'Oracle',  # Lancium builds Stargate for Oracle
    'Lancium Technologies': 'Oracle',
    'Lancium Technologies Corporation': 'Oracle',

    # Apple
    'Apple': 'Apple',
    'Apple Inc.': 'Apple',
    'Apple Inc': 'Apple',

    # AI Companies
    'xAI': 'xAI',
    'Anthropic': 'Anthropic',

    # Asian Tech Giants
    'ByteDance': 'ByteDance',
    'TikTok': 'TikTok',
    'Alibaba': 'Alibaba',
    'Alibaba Cloud': 'Alibaba',
    'Tencent': 'Tencent',
    'Baidu': 'Baidu',

    # Enterprise Tech
    'IBM': 'IBM',
    'IBM Corporation': 'IBM',
    'Salesforce': 'Salesforce',
    'Salesforce.com': 'Salesforce',
}

# -------------------------------------------------------------------------
# COLO PROVIDERS - These ALL become "Colo - All Other"
# Add company names here that should be grouped as colo
# -------------------------------------------------------------------------

COLO_PROVIDERS = {
    # Major Colo
    'Equinix', 'Equinix, Inc.', 'Equinix Inc',
    'Digital Realty', 'Digital Realty Trust', 'Digital Realty Trust, Inc.', 'DLR',
    'CyrusOne', 'CyrusOne Inc.', 'Cyrus One',
    'QTS', 'QTS Realty Trust', 'QTS Data Centers',
    'Vantage', 'Vantage Data Centers',
    'CoreSite', 'CoreSite Realty',
    'Switch', 'Switch, Inc.',
    'Flexential', 'Peak 10',
    'DataBank', 'Data Bank',
    'Compass Datacenters', 'Compass',
    'EdgeConneX', 'EdgeConnex',
    'Stack Infrastructure', 'STACK',
    'DataGryd', 'Datagryd',
    'H5 Data Centers',
    'TierPoint', 'Tier Point',
    'Sabey', 'Sabey Data Centers',
    'Aligned', 'Aligned Data Centers', 'Aligned Energy',
    'Prime Data Centers',
    'Stream Data Centers', 'Stream',
    'T5 Data Centers', 'T5',
    'CloudHQ',

    # Telecom Colo
    'AT&T', 'AT&T Inc.', 'ATT',
    'Verizon', 'Verizon Communications',
    'Lumen', 'Lumen Technologies', 'CenturyLink',
    'NTT', 'NTT Global', 'NTT Communications', 'NTT Ltd',
    'Colt', 'Colt Technology Services',
    'Zayo', 'Zayo Group',

    # International Colo
    'Global Switch',
    'Interxion',
    'Cyxtera', 'Cyxtera Technologies',
    'Iron Mountain', 'Iron Mountain Data Centers',
    'GDS', 'GDS Holdings',
    'Chindata', 'Chindata Group',
    'KDDI',
    'Keppel DC',
    'ST Telemedia',
}

# Case-insensitive lookup (build at runtime)
COMPANY_MAP_LOWER = {k.lower(): v for k, v in COMPANY_MAP.items()}
COLO_PROVIDERS_LOWER = {c.lower() for c in COLO_PROVIDERS}


# ============================================================================
# STANDARDIZATION FUNCTION
# ============================================================================

def standardize_company(company_name):
    """
    Standardize a company name using the mapping.

    Logic:
    1. Parse pipe-separated company names (e.g., "Meta | DPR Construction")
    2. Check each company against COMPANY_MAP for hyperscaler match
    3. If any company is a hyperscaler, return that canonical name
    4. Otherwise return "Colo - All Other"

    This ensures only hyperscalers get distinct names for XB filtering.
    """
    if not company_name:
        return None

    company_name = str(company_name).strip()

    # Handle pipe-separated multi-company fields (e.g., "Oracle | OpenAI | Related Digital")
    if ' | ' in company_name:
        companies = [c.strip() for c in company_name.split(' | ')]
    elif '|' in company_name:
        companies = [c.strip() for c in company_name.split('|')]
    else:
        companies = [company_name]

    # Check each company for hyperscaler match (first match wins)
    for company in companies:
        # Direct match
        if company in COMPANY_MAP:
            return COMPANY_MAP[company]

        # Case-insensitive match
        lower = company.lower()
        if lower in COMPANY_MAP_LOWER:
            return COMPANY_MAP_LOWER[lower]

        # Handle variations like "Meta (FKA Facebook)"
        # Extract the first word/name before parentheses
        if '(' in company:
            base_name = company.split('(')[0].strip()
            if base_name in COMPANY_MAP:
                return COMPANY_MAP[base_name]
            if base_name.lower() in COMPANY_MAP_LOWER:
                return COMPANY_MAP_LOWER[base_name.lower()]

    # No hyperscaler found - it's a colo
    return "Colo - All Other"


def apply_standardization(fc_path, fc_name):
    """
    Apply company standardization to a feature class.
    Reads company_source, writes to company_clean.
    """
    print(f"\n  Processing {fc_name}...")

    # Check if required fields exist
    fields = [f.name for f in arcpy.ListFields(fc_path)]
    if 'company_clean' not in fields:
        print(f"    WARNING: company_clean field not found in {fc_name}")
        return 0
    if 'company_source' not in fields:
        print(f"    WARNING: company_source field not found in {fc_name}")
        return 0

    # Track changes
    changes = defaultdict(lambda: {'count': 0, 'new_name': None})
    total = 0
    updated = 0

    # Read company_source, write to company_clean
    with arcpy.da.UpdateCursor(fc_path, ['company_source', 'company_clean']) as cursor:
        for row in cursor:
            total += 1
            source_company = row[0]
            current_clean = row[1]

            if not source_company:
                continue

            standardized = standardize_company(source_company)

            if standardized != current_clean:
                row[1] = standardized
                cursor.updateRow(row)
                updated += 1
                changes[source_company]['count'] += 1
                changes[source_company]['new_name'] = standardized

    print(f"    Total records: {total}")
    print(f"    Updated: {updated}")

    if changes:
        print(f"\n    Changes applied:")
        for original, data in sorted(changes.items(), key=lambda x: -x[1]['count'])[:20]:
            print(f"      '{original}' → '{data['new_name']}' ({data['count']} records)")
        if len(changes) > 20:
            print(f"      ... and {len(changes) - 20} more mappings")

    return updated


# ============================================================================
# MAIN
# ============================================================================

def main():
    print("=" * 80)
    print("   STANDARDIZE COMPANY NAMES")
    print("=" * 80)
    print(f"   Started: {datetime.now()}")
    print(f"   GDB: {GDB}")
    print(f"\n   Company mappings loaded: {len(COMPANY_MAP)}")

    total_updated = 0

    # Process gold_buildings
    updated_buildings = apply_standardization(GOLD_BUILDINGS, "gold_buildings_full")
    total_updated += updated_buildings

    # Process gold_campus
    updated_campus = apply_standardization(GOLD_CAMPUS, "gold_campus_full")
    total_updated += updated_campus

    # Summary
    print("\n" + "=" * 80)
    print("   STANDARDIZATION COMPLETE")
    print("=" * 80)
    print(f"   Total records updated: {total_updated}")
    print(f"     gold_buildings: {updated_buildings}")
    print(f"     gold_campus: {updated_campus}")

    if total_updated > 0:
        print(f"\n   NEXT STEP: Re-run campus_rollup_new.py to re-aggregate with new names")
        print(f"   This ensures campus groupings use standardized company names.")

    print(f"\n   Completed: {datetime.now()}")
    print("=" * 80)

    return total_updated


# ============================================================================
# EXECUTE
# ============================================================================

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\nERROR: {str(e)}")
        import traceback
        traceback.print_exc()
else:
    # Run when exec()'d from ArcGIS Pro Python window
    try:
        main()
    except Exception as e:
        print(f"\nERROR: {str(e)}")
        import traceback
        traceback.print_exc()
