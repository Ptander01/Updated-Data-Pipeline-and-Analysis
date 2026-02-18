"""
Enrich Geography Fields via Reverse Geocoding
Populates missing geography fields (region, country, state, state_abbr, county)
using ArcGIS reverse geocoding or spatial join to admin boundaries.

This script provides TWO methods:
1. Spatial Join to Admin Boundaries (preferred - no credits)
2. ArcGIS Online Reverse Geocoding (requires credits)

Author: Meta Data Center GIS Team
Last Updated: 2024-12-16
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

# ============================================================================
# CONFIGURATION
# ============================================================================

# Standard region mapping (country → region)
COUNTRY_TO_REGION = {
    # AMER
    'United States': 'AMER', 'USA': 'AMER', 'US': 'AMER',
    'Canada': 'AMER', 'Mexico': 'AMER', 'Brazil': 'AMER',
    'Chile': 'AMER', 'Colombia': 'AMER', 'Argentina': 'AMER',
    'Peru': 'AMER', 'Costa Rica': 'AMER',

    # EMEA
    'United Kingdom': 'EMEA', 'UK': 'EMEA', 'Ireland': 'EMEA',
    'Germany': 'EMEA', 'France': 'EMEA', 'Netherlands': 'EMEA',
    'Sweden': 'EMEA', 'Denmark': 'EMEA', 'Norway': 'EMEA',
    'Finland': 'EMEA', 'Spain': 'EMEA', 'Italy': 'EMEA',
    'Poland': 'EMEA', 'Serbia': 'EMEA', 'Austria': 'EMEA',
    'Belgium': 'EMEA', 'Switzerland': 'EMEA', 'Portugal': 'EMEA',
    'Czech Republic': 'EMEA', 'Czechia': 'EMEA',
    'UAE': 'EMEA', 'United Arab Emirates': 'EMEA',
    'Saudi Arabia': 'EMEA', 'Israel': 'EMEA', 'South Africa': 'EMEA',
    'Nigeria': 'EMEA', 'Kenya': 'EMEA', 'Egypt': 'EMEA',
    'Qatar': 'EMEA', 'Bahrain': 'EMEA', 'Oman': 'EMEA',
    'Iceland': 'EMEA', 'Luxembourg': 'EMEA', 'Greece': 'EMEA',

    # APAC
    'Singapore': 'APAC', 'Japan': 'APAC', 'Australia': 'APAC',
    'New Zealand': 'APAC', 'India': 'APAC', 'Indonesia': 'APAC',
    'Malaysia': 'APAC', 'Taiwan': 'APAC', 'South Korea': 'APAC',
    'Korea': 'APAC', 'Hong Kong': 'APAC', 'Philippines': 'APAC',
    'Thailand': 'APAC', 'Vietnam': 'APAC', 'China': 'APAC',
}

# US State name to abbreviation
US_STATE_ABBREV = {
    'Alabama': 'AL', 'Alaska': 'AK', 'Arizona': 'AZ', 'Arkansas': 'AR',
    'California': 'CA', 'Colorado': 'CO', 'Connecticut': 'CT', 'Delaware': 'DE',
    'Florida': 'FL', 'Georgia': 'GA', 'Hawaii': 'HI', 'Idaho': 'ID',
    'Illinois': 'IL', 'Indiana': 'IN', 'Iowa': 'IA', 'Kansas': 'KS',
    'Kentucky': 'KY', 'Louisiana': 'LA', 'Maine': 'ME', 'Maryland': 'MD',
    'Massachusetts': 'MA', 'Michigan': 'MI', 'Minnesota': 'MN', 'Mississippi': 'MS',
    'Missouri': 'MO', 'Montana': 'MT', 'Nebraska': 'NE', 'Nevada': 'NV',
    'New Hampshire': 'NH', 'New Jersey': 'NJ', 'New Mexico': 'NM', 'New York': 'NY',
    'North Carolina': 'NC', 'North Dakota': 'ND', 'Ohio': 'OH', 'Oklahoma': 'OK',
    'Oregon': 'OR', 'Pennsylvania': 'PA', 'Rhode Island': 'RI', 'South Carolina': 'SC',
    'South Dakota': 'SD', 'Tennessee': 'TN', 'Texas': 'TX', 'Utah': 'UT',
    'Vermont': 'VT', 'Virginia': 'VA', 'Washington': 'WA', 'West Virginia': 'WV',
    'Wisconsin': 'WI', 'Wyoming': 'WY', 'District of Columbia': 'DC'
}

# Abbreviation to full state name
ABBREV_TO_STATE = {v: k for k, v in US_STATE_ABBREV.items()}


# ============================================================================
# METHOD 1: Rule-Based Enrichment (Using existing data + lookups)
# ============================================================================

def enrich_from_existing_data(fc_path, fc_name):
    """
    Enrich geography fields using existing data and lookup tables.
    This method:
    1. Standardizes region from country using lookup
    2. Fills state_abbr from state or vice versa
    3. Does NOT require external data layers

    Returns:
        Dict with counts of updates per field
    """
    print(f"\n  Rule-Based Enrichment: {fc_name}")

    existing_fields = [f.name for f in arcpy.ListFields(fc_path)]

    # Fields we want to update
    geo_fields = ['region', 'country', 'state', 'state_abbr']
    check_fields = [f for f in geo_fields if f in existing_fields]

    if not check_fields:
        print(f"    ⚠️ No geography fields found")
        return {}

    print(f"    Fields to process: {check_fields}")

    updates = {f: 0 for f in check_fields}
    total_processed = 0

    with arcpy.da.UpdateCursor(fc_path, check_fields) as cursor:
        for row in cursor:
            total_processed += 1
            row_list = list(row)
            updated = False

            # Get current values
            field_vals = {f: row[check_fields.index(f)] if f in check_fields else None for f in geo_fields}

            country = field_vals.get('country')
            region = field_vals.get('region')
            state = field_vals.get('state')
            state_abbr = field_vals.get('state_abbr')

            # 1. Fill region from country
            if not region and country:
                new_region = COUNTRY_TO_REGION.get(country)
                if new_region and 'region' in check_fields:
                    idx = check_fields.index('region')
                    row_list[idx] = new_region
                    updates['region'] += 1
                    updated = True

            # 2. Fill state_abbr from state (if state looks like full name)
            if not state_abbr and state:
                # If state is full name, get abbreviation
                if state in US_STATE_ABBREV:
                    new_abbr = US_STATE_ABBREV[state]
                    if 'state_abbr' in check_fields:
                        idx = check_fields.index('state_abbr')
                        row_list[idx] = new_abbr
                        updates['state_abbr'] += 1
                        updated = True
                # If state is already abbreviation, fill state from abbrev
                elif state in ABBREV_TO_STATE:
                    # State field contains abbreviation - this shouldn't happen
                    # but if it does, we can fill the full name
                    pass  # Leave for now, handled in state field below

            # 3. Fill state from state_abbr (reverse lookup)
            if not state and state_abbr:
                if state_abbr in ABBREV_TO_STATE:
                    new_state = ABBREV_TO_STATE[state_abbr]
                    if 'state' in check_fields:
                        idx = check_fields.index('state')
                        row_list[idx] = new_state
                        updates['state'] += 1
                        updated = True

            # 4. Handle case where 'state' contains abbreviation (DCH issue)
            if state and len(state) <= 3 and state.upper() in ABBREV_TO_STATE:
                # State field has abbreviation - move to state_abbr, fill state with full name
                abbr = state.upper()
                full_name = ABBREV_TO_STATE[abbr]

                if 'state_abbr' in check_fields and not state_abbr:
                    idx = check_fields.index('state_abbr')
                    row_list[idx] = abbr
                    updates['state_abbr'] += 1
                    updated = True

                if 'state' in check_fields:
                    idx = check_fields.index('state')
                    row_list[idx] = full_name
                    updates['state'] += 1
                    updated = True

            if updated:
                cursor.updateRow(row_list)

    print(f"    Total records processed: {total_processed}")
    for field, count in updates.items():
        if count > 0:
            print(f"    ✅ {field}: {count} values enriched")

    return updates


# ============================================================================
# METHOD 2: Spatial Join to Admin Boundaries (Requires boundary layers)
# ============================================================================

def spatial_join_enrich(fc_path, fc_name, admin_boundaries_fc=None):
    """
    Enrich geography fields via spatial join to admin boundary polygons.

    This requires an admin boundaries feature class with fields like:
    - COUNTRY, STATE, COUNTY, etc.

    Args:
        fc_path: Path to feature class to enrich
        fc_name: Display name for logging
        admin_boundaries_fc: Path to admin boundaries (e.g., World Countries, US States)

    Returns:
        Number of records updated
    """
    if not admin_boundaries_fc:
        print(f"\n  ⚠️ Spatial Join Enrichment skipped - no admin boundaries provided")
        print("    To use this method, download admin boundary layers from:")
        print("    - World Countries: ArcGIS Living Atlas")
        print("    - US States/Counties: US Census TIGER data")
        return 0

    print(f"\n  Spatial Join Enrichment: {fc_name}")
    print(f"    Admin Boundaries: {admin_boundaries_fc}")

    # Check if boundary layer exists
    if not arcpy.Exists(admin_boundaries_fc):
        print(f"    ❌ Admin boundaries not found: {admin_boundaries_fc}")
        return 0

    # Create temp join output
    temp_join = os.path.join(GDB, f"temp_spatial_join_{fc_name}")
    if arcpy.Exists(temp_join):
        arcpy.management.Delete(temp_join)

    # Perform spatial join
    print(f"    Performing spatial join...")
    arcpy.analysis.SpatialJoin(
        target_features=fc_path,
        join_features=admin_boundaries_fc,
        out_feature_class=temp_join,
        join_operation="JOIN_ONE_TO_ONE",
        join_type="KEEP_ALL",
        match_option="INTERSECT"
    )

    # Get joined field names (will have different names)
    join_fields = [f.name for f in arcpy.ListFields(temp_join)]
    print(f"    Joined fields available: {[f for f in join_fields if any(kw in f.lower() for kw in ['country', 'state', 'county', 'region'])]}")

    # TODO: Map joined fields back to original feature class
    # This requires knowing the exact field names in the admin boundaries layer

    # Cleanup
    if arcpy.Exists(temp_join):
        arcpy.management.Delete(temp_join)

    return 0


# ============================================================================
# MAIN EXECUTION
# ============================================================================

def main():
    print("=" * 80)
    print("   ENRICH GEOGRAPHY FIELDS")
    print("=" * 80)
    print(f"   Started: {datetime.now()}")
    print(f"   GDB: {GDB}")

    print("\n" + "-" * 80)
    print("   METHOD 1: Rule-Based Enrichment (Using existing data + lookups)")
    print("-" * 80)

    # Process both feature classes
    results = {}

    for fc_name, fc_path in [('gold_buildings', GOLD_BUILDINGS),
                              ('gold_campus', GOLD_CAMPUS)]:
        results[fc_name] = enrich_from_existing_data(fc_path, fc_name)

    # Summary
    print("\n" + "=" * 80)
    print("   ENRICHMENT COMPLETE")
    print("=" * 80)

    for fc_name, updates in results.items():
        print(f"\n  {fc_name}:")
        if updates:
            for field, count in updates.items():
                print(f"    {field}: {count} enriched")
        else:
            print("    No updates")

    print("\n" + "-" * 80)
    print("   NEXT STEPS FOR FULL GEOGRAPHY ENRICHMENT")
    print("-" * 80)
    print("""
    The rule-based method enriches what it can from existing data.
    For complete coverage (especially county), you need spatial join:

    1. Download admin boundary layers:
       - World Countries (ArcGIS Living Atlas)
       - US States & Counties (Census TIGER)

    2. Add them to your GDB or reference directly

    3. Run spatial join manually in ArcGIS Pro:
       - Right-click gold_buildings → Joins & Relates → Spatial Join
       - Join to admin boundaries (Intersect)
       - Map Country → country, State → state, County → county

    4. Or uncomment and configure spatial_join_enrich() in this script
    """)

    print(f"\n   Completed: {datetime.now()}")
    print("=" * 80)

    return results


# Execute
if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n❌ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()

# Also run when exec()'d
try:
    main()
except Exception as e:
    print(f"\n❌ ERROR: {str(e)}")
    import traceback
    traceback.print_exc()
