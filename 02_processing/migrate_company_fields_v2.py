"""
Migration Script: Company Fields v2.0
=====================================

This script migrates the company field structure to support proper UCID clustering:

BEFORE (Current - Broken for UCID):
- company_source: Raw vendor value
- company_clean: Hyperscalers OR "Colo - All Other" (wrong - merges all colos!)

AFTER (Fixed):
- company_source: Raw vendor value (unchanged)
- company_clean: Standardized DISTINCT names (Equinix, Digital Realty, QTS, etc.)
- company_clean_filter: Hyperscalers OR "Colo - All Other" (for XB filtering only)

This ensures UCID clustering uses company_clean with DISTINCT company names,
preventing false merges of different colo providers in the same city.

Run in ArcGIS Pro Python window:
exec(open(r"...scripts/02_processing/migrate_company_fields_v2.py", encoding='utf-8').read())

Author: Meta Data Center GIS Team
Created: December 30, 2025
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
    script_dir = r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\scripts\02_processing"

utils_dir = os.path.join(os.path.dirname(script_dir), "_utils")
if utils_dir not in sys.path:
    sys.path.insert(0, utils_dir)

from config import GDB, GOLD_BUILDINGS, GOLD_CAMPUS

arcpy.env.workspace = GDB
arcpy.env.overwriteOutput = True

# =============================================================================
# COMPANY STANDARDIZATION MAPS
# =============================================================================

# Hyperscalers - These companies appear BOTH in company_clean AND company_clean_filter
HYPERSCALERS = {
    'Meta', 'AWS', 'Google', 'Microsoft', 'Oracle', 'Apple',
    'xAI', 'Anthropic', 'OpenAI',
    'ByteDance', 'TikTok', 'Alibaba', 'Tencent', 'Baidu',
    'IBM', 'Salesforce',
}

# Company name variations → Canonical name
# This applies to BOTH hyperscalers and colo providers
COMPANY_CANONICAL_MAP = {
    # =========================================================================
    # HYPERSCALERS
    # =========================================================================

    # Amazon / AWS
    'Amazon': 'AWS',
    'Amazon Web Services': 'AWS',
    'Amazon.com': 'AWS',
    'Amazon.com Services LLC': 'AWS',
    'Amazon Data Services': 'AWS',
    'Amazon AWS': 'AWS',
    'AWS': 'AWS',

    # Meta / Facebook
    'Facebook': 'Meta',
    'Facebook, Inc.': 'Meta',
    'Meta': 'Meta',
    'Meta Platforms': 'Meta',
    'Meta Platforms, Inc.': 'Meta',

    # Google / Alphabet
    'Google': 'Google',
    'Google LLC': 'Google',
    'Google Cloud': 'Google',
    'Alphabet': 'Google',
    'Alphabet Inc.': 'Google',

    # Microsoft / Azure
    'Microsoft': 'Microsoft',
    'Microsoft Corporation': 'Microsoft',
    'Microsoft Azure': 'Microsoft',
    'Azure': 'Microsoft',

    # Oracle
    'Oracle': 'Oracle',
    'Oracle Corporation': 'Oracle',
    'Oracle America': 'Oracle',
    'Oracle America, Inc.': 'Oracle',

    # Apple
    'Apple': 'Apple',
    'Apple Inc.': 'Apple',
    'Apple Inc': 'Apple',

    # AI Companies
    'xAI': 'xAI',
    'x.ai': 'xAI',
    'Anthropic': 'Anthropic',
    'OpenAI': 'OpenAI',
    'Open AI': 'OpenAI',

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

    # =========================================================================
    # COLO PROVIDERS - Standardized but DISTINCT (not grouped!)
    # =========================================================================

    # Equinix
    'Equinix': 'Equinix',
    'Equinix, Inc.': 'Equinix',
    'Equinix Inc': 'Equinix',
    'Equinix Inc.': 'Equinix',

    # Digital Realty
    'Digital Realty': 'Digital Realty',
    'Digital Realty Trust': 'Digital Realty',
    'Digital Realty Trust, Inc.': 'Digital Realty',
    'DLR': 'Digital Realty',
    'DRT': 'Digital Realty',

    # CyrusOne
    'CyrusOne': 'CyrusOne',
    'CyrusOne Inc.': 'CyrusOne',
    'Cyrus One': 'CyrusOne',

    # QTS
    'QTS': 'QTS',
    'QTS Realty Trust': 'QTS',
    'QTS Data Centers': 'QTS',

    # Vantage
    'Vantage': 'Vantage',
    'Vantage Data Centers': 'Vantage',

    # CoreSite
    'CoreSite': 'CoreSite',
    'CoreSite Realty': 'CoreSite',

    # Switch
    'Switch': 'Switch',
    'Switch, Inc.': 'Switch',

    # Flexential
    'Flexential': 'Flexential',
    'Peak 10': 'Flexential',

    # DataBank
    'DataBank': 'DataBank',
    'Data Bank': 'DataBank',

    # Compass
    'Compass': 'Compass',
    'Compass Datacenters': 'Compass',

    # EdgeConneX
    'EdgeConneX': 'EdgeConneX',
    'EdgeConnex': 'EdgeConneX',

    # Stack
    'Stack Infrastructure': 'Stack',
    'STACK': 'Stack',
    'Stack': 'Stack',

    # TierPoint
    'TierPoint': 'TierPoint',
    'Tier Point': 'TierPoint',

    # Sabey
    'Sabey': 'Sabey',
    'Sabey Data Centers': 'Sabey',

    # Aligned
    'Aligned': 'Aligned',
    'Aligned Data Centers': 'Aligned',
    'Aligned Energy': 'Aligned',

    # Stream
    'Stream': 'Stream',
    'Stream Data Centers': 'Stream',

    # T5
    'T5': 'T5',
    'T5 Data Centers': 'T5',

    # CloudHQ
    'CloudHQ': 'CloudHQ',

    # Prime
    'Prime': 'Prime',
    'Prime Data Centers': 'Prime',

    # H5
    'H5': 'H5',
    'H5 Data Centers': 'H5',

    # DataGryd
    'DataGryd': 'DataGryd',
    'Datagryd': 'DataGryd',

    # =========================================================================
    # TELECOM COLO
    # =========================================================================

    'AT&T': 'AT&T',
    'AT&T Inc.': 'AT&T',
    'ATT': 'AT&T',

    'Verizon': 'Verizon',
    'Verizon Communications': 'Verizon',

    'Lumen': 'Lumen',
    'Lumen Technologies': 'Lumen',
    'CenturyLink': 'Lumen',

    'NTT': 'NTT',
    'NTT Global': 'NTT',
    'NTT Communications': 'NTT',
    'NTT Ltd': 'NTT',

    'Colt': 'Colt',
    'Colt Technology Services': 'Colt',

    'Zayo': 'Zayo',
    'Zayo Group': 'Zayo',

    # =========================================================================
    # INTERNATIONAL COLO
    # =========================================================================

    'Global Switch': 'Global Switch',
    'Interxion': 'Interxion',

    'Cyxtera': 'Cyxtera',
    'Cyxtera Technologies': 'Cyxtera',

    'Iron Mountain': 'Iron Mountain',
    'Iron Mountain Data Centers': 'Iron Mountain',

    'GDS': 'GDS',
    'GDS Holdings': 'GDS',

    'Chindata': 'Chindata',
    'Chindata Group': 'Chindata',

    'KDDI': 'KDDI',
    'Keppel DC': 'Keppel',
    'ST Telemedia': 'ST Telemedia',

    # =========================================================================
    # CONTRACTORS / BUILDERS (Map to end client if known)
    # =========================================================================

    'Mortenson': 'Meta',  # Mortenson builds for Meta
    'Lancium': 'Oracle',  # Lancium builds Stargate for Oracle
    'Lancium Technologies': 'Oracle',
    'Lancium Technologies Corporation': 'Oracle',
}

# Build case-insensitive lookup
COMPANY_CANONICAL_MAP_LOWER = {k.lower(): v for k, v in COMPANY_CANONICAL_MAP.items()}


# =============================================================================
# STANDARDIZATION FUNCTIONS
# =============================================================================

def get_canonical_company(company_name):
    """
    Get the canonical (standardized) company name.
    Returns DISTINCT names for all companies (both hyperscalers and colos).

    Examples:
    - "Amazon Web Services" → "AWS"
    - "Equinix, Inc." → "Equinix"
    - "Digital Realty Trust" → "Digital Realty"
    - "Unknown Company XYZ" → "Unknown Company XYZ" (unchanged)
    """
    if not company_name:
        return None

    company_name = str(company_name).strip()

    # Handle pipe-separated multi-company fields
    if ' | ' in company_name:
        companies = [c.strip() for c in company_name.split(' | ')]
    elif '|' in company_name:
        companies = [c.strip() for c in company_name.split('|')]
    else:
        companies = [company_name]

    # Return first matching canonical name
    for company in companies:
        # Direct match
        if company in COMPANY_CANONICAL_MAP:
            return COMPANY_CANONICAL_MAP[company]

        # Case-insensitive match
        lower = company.lower()
        if lower in COMPANY_CANONICAL_MAP_LOWER:
            return COMPANY_CANONICAL_MAP_LOWER[lower]

        # Handle "Company (FKA OldName)" format
        if '(' in company:
            base_name = company.split('(')[0].strip()
            if base_name in COMPANY_CANONICAL_MAP:
                return COMPANY_CANONICAL_MAP[base_name]
            if base_name.lower() in COMPANY_CANONICAL_MAP_LOWER:
                return COMPANY_CANONICAL_MAP_LOWER[base_name.lower()]

    # No mapping found - return first company unchanged
    return companies[0]


def get_company_filter(canonical_name):
    """
    Get the filter category for XB filtering.
    Hyperscalers keep their name, everyone else becomes "Colo - All Other".

    Examples:
    - "AWS" → "AWS"
    - "Meta" → "Meta"
    - "Equinix" → "Colo - All Other"
    - "Digital Realty" → "Colo - All Other"
    """
    if not canonical_name:
        return "Colo - All Other"

    if canonical_name in HYPERSCALERS:
        return canonical_name

    return "Colo - All Other"


# =============================================================================
# MIGRATION FUNCTIONS
# =============================================================================

def add_company_clean_filter_field(fc_path, fc_name):
    """Add company_clean_filter field if it doesn't exist."""
    fields = [f.name for f in arcpy.ListFields(fc_path)]

    if 'company_clean_filter' in fields:
        print(f"   {fc_name}: company_clean_filter already exists")
        return False

    arcpy.management.AddField(
        fc_path,
        'company_clean_filter',
        'TEXT',
        field_length=128,
        field_alias='Company Filter (XB)'
    )
    print(f"   {fc_name}: Added company_clean_filter field")
    return True


def migrate_company_fields(fc_path, fc_name):
    """
    Migrate company fields:
    1. Copy current company_clean → company_clean_filter
    2. Repopulate company_clean with DISTINCT canonical names
    """
    print(f"\n   Migrating {fc_name}...")

    # Check which source field to use
    existing_fields = [f.name for f in arcpy.ListFields(fc_path)]

    # Determine source field: prefer company_source, fall back to company_clean
    if 'company_source' in existing_fields:
        source_field = 'company_source'
    elif 'company_clean' in existing_fields:
        # For gold_campus_full which may not have company_source
        # We need to derive from building records or use existing company_clean
        source_field = 'company_clean'
        print(f"   NOTE: Using company_clean as source (company_source not found)")
    else:
        print(f"   ERROR: Neither company_source nor company_clean found in {fc_name}")
        return 0, 0

    if 'company_clean_filter' not in existing_fields:
        print(f"   ERROR: company_clean_filter not found in {fc_name}")
        return 0, 0

    fields = [source_field, 'company_clean', 'company_clean_filter']

    stats = {
        'total': 0,
        'clean_updated': 0,
        'filter_populated': 0,
        'distinct_companies': set(),
    }

    with arcpy.da.UpdateCursor(fc_path, fields) as cursor:
        for row in cursor:
            stats['total'] += 1
            company_source = row[0]
            current_clean = row[1]
            current_filter = row[2]

            # Step 1: Get canonical (distinct) company name
            canonical = get_canonical_company(company_source)

            # Step 2: Get filter value (hyperscaler or "Colo - All Other")
            filter_val = get_company_filter(canonical)

            # Track distinct companies
            if canonical:
                stats['distinct_companies'].add(canonical)

            # Update company_clean with DISTINCT canonical name
            if canonical != current_clean:
                row[1] = canonical
                stats['clean_updated'] += 1

            # Populate company_clean_filter
            if filter_val != current_filter:
                row[2] = filter_val
                stats['filter_populated'] += 1

            cursor.updateRow(row)

    print(f"   {fc_name} Results:")
    print(f"     Total records: {stats['total']:,}")
    print(f"     company_clean updated: {stats['clean_updated']:,}")
    print(f"     company_clean_filter populated: {stats['filter_populated']:,}")
    print(f"     Distinct companies found: {len(stats['distinct_companies'])}")

    return stats['clean_updated'], stats['filter_populated']


def verify_migration(fc_path, fc_name):
    """Verify the migration worked correctly."""
    print(f"\n   Verifying {fc_name}...")

    # Count "Colo - All Other" in each field
    clean_colo_count = 0
    filter_colo_count = 0
    filter_null_count = 0
    total = 0

    sample_distinct = set()

    with arcpy.da.SearchCursor(fc_path, ['company_clean', 'company_clean_filter']) as cursor:
        for row in cursor:
            total += 1
            clean = row[0]
            filter_val = row[1]

            if clean and 'colo - all other' in str(clean).lower():
                clean_colo_count += 1
            elif clean:
                sample_distinct.add(clean)

            if filter_val and 'colo - all other' in str(filter_val).lower():
                filter_colo_count += 1
            elif not filter_val:
                filter_null_count += 1

    print(f"   {fc_name} Verification:")
    print(f"     company_clean 'Colo - All Other': {clean_colo_count:,} ({clean_colo_count/total*100:.1f}%)")
    print(f"     company_clean_filter 'Colo - All Other': {filter_colo_count:,} ({filter_colo_count/total*100:.1f}%)")
    print(f"     company_clean_filter NULL: {filter_null_count:,}")

    # Show sample of distinct company names in company_clean
    print(f"\n     Sample distinct companies in company_clean:")
    for company in sorted(list(sample_distinct))[:15]:
        print(f"       - {company}")
    if len(sample_distinct) > 15:
        print(f"       ... and {len(sample_distinct) - 15} more")

    # Check for the problem: company_clean should NOT have "Colo - All Other"
    if clean_colo_count > 0:
        print(f"\n   ⚠️  WARNING: {clean_colo_count} records still have 'Colo - All Other' in company_clean")
        print(f"       These may be records where company_source was already 'Colo - All Other'")
    else:
        print(f"\n   ✅ SUCCESS: No 'Colo - All Other' in company_clean field")


# =============================================================================
# MAIN
# =============================================================================

def main():
    print("=" * 70)
    print("   COMPANY FIELDS MIGRATION v2.0")
    print("=" * 70)
    print(f"   Started: {datetime.now()}")
    print(f"\n   This migration:")
    print(f"   1. Adds company_clean_filter field")
    print(f"   2. Populates company_clean with DISTINCT canonical names")
    print(f"   3. Populates company_clean_filter with hyperscaler OR 'Colo - All Other'")

    # Step 1: Add company_clean_filter field
    print("\n" + "-" * 70)
    print("[Step 1] Adding company_clean_filter field")
    print("-" * 70)
    add_company_clean_filter_field(GOLD_BUILDINGS, "gold_buildings_full")
    add_company_clean_filter_field(GOLD_CAMPUS, "gold_campus_full")

    # Step 2: Migrate company fields
    print("\n" + "-" * 70)
    print("[Step 2] Migrating company fields")
    print("-" * 70)

    buildings_clean, buildings_filter = migrate_company_fields(GOLD_BUILDINGS, "gold_buildings_full")
    campus_clean, campus_filter = migrate_company_fields(GOLD_CAMPUS, "gold_campus_full")

    # Step 3: Verify migration
    print("\n" + "-" * 70)
    print("[Step 3] Verifying migration")
    print("-" * 70)
    verify_migration(GOLD_BUILDINGS, "gold_buildings_full")
    verify_migration(GOLD_CAMPUS, "gold_campus_full")

    # Summary
    print("\n" + "=" * 70)
    print("   MIGRATION COMPLETE")
    print("=" * 70)
    print(f"\n   Results:")
    print(f"     gold_buildings_full:")
    print(f"       - company_clean updated: {buildings_clean:,}")
    print(f"       - company_clean_filter populated: {buildings_filter:,}")
    print(f"     gold_campus_full:")
    print(f"       - company_clean updated: {campus_clean:,}")
    print(f"       - company_clean_filter populated: {campus_filter:,}")

    print(f"\n   NEXT STEPS:")
    print(f"   1. Update UCID generation to use company_clean (distinct names)")
    print(f"   2. Re-run UCID clustering: generate_ucid_clusters.py")
    print(f"   3. Verify no false colo merges in results")

    print(f"\n   Completed: {datetime.now()}")
    print("=" * 70)


# =============================================================================
# EXECUTE
# =============================================================================

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\nERROR: {str(e)}")
        import traceback
        traceback.print_exc()
else:
    try:
        main()
    except Exception as e:
        print(f"\nERROR: {str(e)}")
        import traceback
        traceback.print_exc()
