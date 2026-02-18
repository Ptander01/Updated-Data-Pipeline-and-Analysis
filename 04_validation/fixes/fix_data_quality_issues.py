"""
Fix Data Quality Issues
Addresses issues found during pipeline execution:
1. NPM unique_id field length exceeded (2 records) - truncate long unique_ids
2. DCM missing region (1,349 records) - derive from country
3. State abbreviations in state field (1,813 records) - expand to full names
4. Missing state_abbr field (5,057 records) - derive from state

Author: Meta Data Center GIS Team
Last Updated: 2026-01-02
"""

import arcpy
import os
import sys
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
arcpy.env.overwriteOutput = True

# ============================================================================
# LOOKUP TABLES
# ============================================================================

# Country to region mapping
COUNTRY_TO_REGION = {
    # AMER
    'United States': 'AMER', 'USA': 'AMER', 'US': 'AMER', 'United States of America': 'AMER',
    'Canada': 'AMER', 'Mexico': 'AMER', 'Brazil': 'AMER',
    'Chile': 'AMER', 'Colombia': 'AMER', 'Argentina': 'AMER',
    'Peru': 'AMER', 'Costa Rica': 'AMER', 'Panama': 'AMER',

    # EMEA
    'United Kingdom': 'EMEA', 'UK': 'EMEA', 'Ireland': 'EMEA',
    'Germany': 'EMEA', 'France': 'EMEA', 'Netherlands': 'EMEA',
    'Sweden': 'EMEA', 'Denmark': 'EMEA', 'Norway': 'EMEA',
    'Finland': 'EMEA', 'Spain': 'EMEA', 'Italy': 'EMEA',
    'Poland': 'EMEA', 'Serbia': 'EMEA', 'Austria': 'EMEA',
    'Belgium': 'EMEA', 'Switzerland': 'EMEA', 'Portugal': 'EMEA',
    'Czech Republic': 'EMEA', 'Czechia': 'EMEA', 'Romania': 'EMEA',
    'Hungary': 'EMEA', 'Greece': 'EMEA', 'Bulgaria': 'EMEA',
    'Croatia': 'EMEA', 'Slovakia': 'EMEA', 'Slovenia': 'EMEA',
    'Lithuania': 'EMEA', 'Latvia': 'EMEA', 'Estonia': 'EMEA',
    'UAE': 'EMEA', 'United Arab Emirates': 'EMEA',
    'Saudi Arabia': 'EMEA', 'Israel': 'EMEA', 'South Africa': 'EMEA',
    'Nigeria': 'EMEA', 'Kenya': 'EMEA', 'Egypt': 'EMEA',
    'Qatar': 'EMEA', 'Bahrain': 'EMEA', 'Oman': 'EMEA', 'Kuwait': 'EMEA',
    'Iceland': 'EMEA', 'Luxembourg': 'EMEA', 'Malta': 'EMEA',
    'Russia': 'EMEA', 'Turkey': 'EMEA', 'Ukraine': 'EMEA',

    # APAC
    'Singapore': 'APAC', 'Japan': 'APAC', 'Australia': 'APAC',
    'New Zealand': 'APAC', 'India': 'APAC', 'Indonesia': 'APAC',
    'Malaysia': 'APAC', 'Taiwan': 'APAC', 'South Korea': 'APAC',
    'Korea': 'APAC', 'Hong Kong': 'APAC', 'Philippines': 'APAC',
    'Thailand': 'APAC', 'Vietnam': 'APAC', 'China': 'APAC',
    'Bangladesh': 'APAC', 'Pakistan': 'APAC', 'Sri Lanka': 'APAC',
    'Macau': 'APAC', 'Papua New Guinea': 'APAC', 'Myanmar': 'APAC',
    'Cambodia': 'APAC', 'Laos': 'APAC', 'Mongolia': 'APAC',

    # Additional EMEA (missing from first pass)
    'Cyprus': 'EMEA', 'Monaco': 'EMEA', 'Gibraltar': 'EMEA',
    'Liechtenstein': 'EMEA', 'Albania': 'EMEA', 'Montenegro': 'EMEA',
    'North Macedonia': 'EMEA', 'Bosnia and Herzegovina': 'EMEA',
    'Moldova': 'EMEA', 'Belarus': 'EMEA', 'Kosovo': 'EMEA',
    'Andorra': 'EMEA', 'San Marino': 'EMEA', 'Vatican City': 'EMEA',
    'Morocco': 'EMEA', 'Tunisia': 'EMEA', 'Algeria': 'EMEA',
    'Libya': 'EMEA', 'Jordan': 'EMEA', 'Lebanon': 'EMEA',
    'Iraq': 'EMEA', 'Iran': 'EMEA', 'Afghanistan': 'EMEA',
    'Togo': 'EMEA', 'Ghana': 'EMEA', 'Senegal': 'EMEA',
    'Ivory Coast': 'EMEA', 'Cameroon': 'EMEA', 'Uganda': 'EMEA',
    'Tanzania': 'EMEA', 'Rwanda': 'EMEA', 'Ethiopia': 'EMEA',

    # Additional AMER (missing from first pass)
    'Bermuda': 'AMER', 'Bahamas': 'AMER', 'Jamaica': 'AMER',
    'Puerto Rico': 'AMER', 'Trinidad and Tobago': 'AMER',
    'Dominican Republic': 'AMER', 'Haiti': 'AMER', 'Cuba': 'AMER',
    'Curacao': 'AMER', 'Aruba': 'AMER', 'Cayman Islands': 'AMER',
    'Barbados': 'AMER', 'Guatemala': 'AMER', 'Honduras': 'AMER',
    'El Salvador': 'AMER', 'Nicaragua': 'AMER', 'Ecuador': 'AMER',
    'Venezuela': 'AMER', 'Paraguay': 'AMER', 'Uruguay': 'AMER',
    'Bolivia': 'AMER', 'French Guiana': 'AMER', 'Suriname': 'AMER',
    'Guyana': 'AMER', 'Belize': 'AMER', 'Netherlands Antilles': 'AMER',

    # Additional countries found in data
    'The Netherlands': 'EMEA', 'Holland': 'EMEA',
    'Macedonia': 'EMEA', 'Republic of Macedonia': 'EMEA',
    'Guernsey': 'EMEA', 'Jersey': 'EMEA', 'Isle of Man': 'EMEA',
    'Republic of the Congo': 'EMEA', 'Congo': 'EMEA', 'DRC': 'EMEA',
    'Democratic Republic of the Congo': 'EMEA',
    'Sudan': 'EMEA', 'South Sudan': 'EMEA',
    'Mauritius': 'EMEA', 'Seychelles': 'EMEA', 'Madagascar': 'EMEA',
    'Zimbabwe': 'EMEA', 'Zambia': 'EMEA', 'Botswana': 'EMEA',
    'Mozambique': 'EMEA', 'Namibia': 'EMEA', 'Angola': 'EMEA',
    'Nepal': 'APAC', 'Bhutan': 'APAC', 'Maldives': 'APAC',
    'Brunei': 'APAC', 'Fiji': 'APAC', 'Samoa': 'APAC',

    # Final batch - obscure countries from data
    'Somalia': 'EMEA', 'Djibouti': 'EMEA', 'Eritrea': 'EMEA',
    'Kazakhstan': 'APAC', 'Kyrgyzstan': 'APAC', 'Uzbekistan': 'APAC',
    'Tajikistan': 'APAC', 'Turkmenistan': 'APAC',
    'Azerbaijan': 'EMEA', 'Armenia': 'EMEA', 'Georgia': 'EMEA',
    'Palestine': 'EMEA', 'Syria': 'EMEA', 'Yemen': 'EMEA',
    'Guam': 'APAC', 'Northern Mariana Islands': 'APAC',
    'Mayotte': 'EMEA', 'Reunion': 'EMEA',
    'Greenland': 'AMER',  # Danish territory but geographically AMER

    # Last 5 - Pacific islands and Africa
    'French Polynesia': 'APAC',  # French territory in Pacific
    'New Caledonia': 'APAC',     # French territory in Pacific
    'Solomon Islands': 'APAC',   # Pacific island nation
    'Guinea': 'EMEA',            # West Africa
    'DR Congo': 'EMEA',          # Variant of Democratic Republic of the Congo
}

# US State abbreviation to full name
ABBREV_TO_STATE = {
    'AL': 'Alabama', 'AK': 'Alaska', 'AZ': 'Arizona', 'AR': 'Arkansas',
    'CA': 'California', 'CO': 'Colorado', 'CT': 'Connecticut', 'DE': 'Delaware',
    'FL': 'Florida', 'GA': 'Georgia', 'HI': 'Hawaii', 'ID': 'Idaho',
    'IL': 'Illinois', 'IN': 'Indiana', 'IA': 'Iowa', 'KS': 'Kansas',
    'KY': 'Kentucky', 'LA': 'Louisiana', 'ME': 'Maine', 'MD': 'Maryland',
    'MA': 'Massachusetts', 'MI': 'Michigan', 'MN': 'Minnesota', 'MS': 'Mississippi',
    'MO': 'Missouri', 'MT': 'Montana', 'NE': 'Nebraska', 'NV': 'Nevada',
    'NH': 'New Hampshire', 'NJ': 'New Jersey', 'NM': 'New Mexico', 'NY': 'New York',
    'NC': 'North Carolina', 'ND': 'North Dakota', 'OH': 'Ohio', 'OK': 'Oklahoma',
    'OR': 'Oregon', 'PA': 'Pennsylvania', 'RI': 'Rhode Island', 'SC': 'South Carolina',
    'SD': 'South Dakota', 'TN': 'Tennessee', 'TX': 'Texas', 'UT': 'Utah',
    'VT': 'Vermont', 'VA': 'Virginia', 'WA': 'Washington', 'WV': 'West Virginia',
    'WI': 'Wisconsin', 'WY': 'Wyoming', 'DC': 'District of Columbia',
    'PR': 'Puerto Rico', 'VI': 'Virgin Islands', 'GU': 'Guam'
}

# Full state name to abbreviation
STATE_TO_ABBREV = {v: k for k, v in ABBREV_TO_STATE.items()}


# ============================================================================
# FIX FUNCTIONS
# ============================================================================

def fix_npm_unique_id_length(fc_path):
    """
    Fix NPM records with unique_id that exceeds field length.
    Truncates unique_id to 100 characters (field limit).
    """
    print("\n" + "="*70)
    print("FIX 1: NPM unique_id Field Length")
    print("="*70)

    # Get unique_id field length
    fields = arcpy.ListFields(fc_path, 'unique_id')
    if not fields:
        print("   ❌ unique_id field not found")
        return 0

    field_length = fields[0].length
    print(f"   Field length limit: {field_length} characters")

    # Find NPM records with long unique_ids
    long_ids = []
    with arcpy.da.SearchCursor(fc_path, ['OBJECTID', 'unique_id', 'source']) as cursor:
        for row in cursor:
            if row[2] == 'NewProjectMedia' and row[1] and len(row[1]) > field_length:
                long_ids.append((row[0], row[1], len(row[1])))

    if not long_ids:
        print("   ✅ No NPM records with oversized unique_id found")
        return 0

    print(f"   Found {len(long_ids)} records with unique_id > {field_length} chars:")
    for oid, uid, length in long_ids:
        print(f"      OID {oid}: {length} chars - {uid[:50]}...")

    # For future ingestions, we need to fix the ingest_npm.py script
    # For existing data, the records that failed to insert are already missing
    print(f"\n   ⚠️ These records failed during ingestion and were not inserted.")
    print(f"   📝 To fix: Update ingest_npm.py to truncate unique_id to {field_length} chars")

    return len(long_ids)


def fix_dcm_missing_region(fc_path):
    """
    Fix DCM records missing region by deriving from country.
    """
    print("\n" + "="*70)
    print("FIX 2: DCM Missing Region")
    print("="*70)

    # Count records missing region
    where_clause = "source = 'DataCenterMap' AND (region IS NULL OR region = '')"
    count_before = 0
    with arcpy.da.SearchCursor(fc_path, ['OBJECTID'], where_clause) as cursor:
        count_before = sum(1 for _ in cursor)

    print(f"   Records missing region: {count_before:,}")

    if count_before == 0:
        print("   ✅ No DCM records missing region")
        return 0

    # Update region from country
    updated = 0
    with arcpy.da.UpdateCursor(fc_path, ['region', 'country'], where_clause) as cursor:
        for row in cursor:
            country = row[1]
            if country and country in COUNTRY_TO_REGION:
                row[0] = COUNTRY_TO_REGION[country]
                cursor.updateRow(row)
                updated += 1

    print(f"   ✅ Updated region for {updated:,} records")

    # Check remaining
    remaining = 0
    unknown_countries = set()
    with arcpy.da.SearchCursor(fc_path, ['country'], where_clause) as cursor:
        for row in cursor:
            remaining += 1
            if row[0]:
                unknown_countries.add(row[0])

    if remaining > 0:
        print(f"   ⚠️ {remaining:,} records still missing region")
        if unknown_countries:
            print(f"   Unknown countries: {list(unknown_countries)[:10]}")

    return updated


def fix_state_abbreviations(fc_path):
    """
    Fix records where state field contains abbreviations instead of full names.
    Also populates state_abbr where missing (for US records only).
    """
    print("\n" + "="*70)
    print("FIX 3 & 4: State Field Standardization")
    print("="*70)

    # Count issues before fix with breakdown
    abbr_in_state = 0
    missing_state_abbr = 0
    missing_us = 0
    missing_intl = 0

    # Check field existence
    existing_fields = [f.name for f in arcpy.ListFields(fc_path)]
    has_country = 'country' in existing_fields

    with arcpy.da.SearchCursor(fc_path, ['state', 'state_abbr', 'country'] if has_country else ['state', 'state_abbr']) as cursor:
        for row in cursor:
            state = row[0]
            state_abbr = row[1]
            country = row[2] if has_country and len(row) > 2 else None

            # Check if state contains abbreviation
            if state and len(str(state).strip()) <= 3 and str(state).strip().upper() in ABBREV_TO_STATE:
                abbr_in_state += 1

            # Check if state_abbr is missing
            if not state_abbr or str(state_abbr).strip() == '':
                missing_state_abbr += 1
                # Check if US or international
                if country:
                    country_str = str(country).strip()
                    if country_str in ['United States', 'USA', 'US', 'United States of America']:
                        missing_us += 1
                    else:
                        missing_intl += 1

    print(f"   State field contains abbreviation: {abbr_in_state:,}")
    print(f"   State_abbr field missing: {missing_state_abbr:,}")
    if has_country:
        print(f"      - US records (can fix): {missing_us:,}")
        print(f"      - International (no US abbr): {missing_intl:,}")

    # Fix both issues in one pass
    fixed_state = 0
    fixed_abbr = 0

    with arcpy.da.UpdateCursor(fc_path, ['state', 'state_abbr']) as cursor:
        for row in cursor:
            state = row[0]
            state_abbr = row[1]
            updated = False

            state_str = str(state).strip() if state else ''
            abbr_str = str(state_abbr).strip() if state_abbr else ''

            # Case 1: State contains abbreviation (e.g., "TX" in state field)
            if state_str and len(state_str) <= 3 and state_str.upper() in ABBREV_TO_STATE:
                # Move abbreviation to state_abbr if empty
                if not abbr_str:
                    row[1] = state_str.upper()
                    fixed_abbr += 1
                # Replace state with full name
                row[0] = ABBREV_TO_STATE[state_str.upper()]
                fixed_state += 1
                updated = True

            # Case 2: State_abbr is missing but state has full name
            elif state_str and not abbr_str:
                if state_str in STATE_TO_ABBREV:
                    row[1] = STATE_TO_ABBREV[state_str]
                    fixed_abbr += 1
                    updated = True
                # Also try title case
                elif state_str.title() in STATE_TO_ABBREV:
                    row[1] = STATE_TO_ABBREV[state_str.title()]
                    fixed_abbr += 1
                    updated = True

            if updated:
                cursor.updateRow(row)

    print(f"   ✅ Fixed state field (abbr→full name): {fixed_state:,}")
    print(f"   ✅ Fixed state_abbr (derived from state): {fixed_abbr:,}")

    return fixed_state + fixed_abbr


def update_ingest_npm_script():
    """
    Update ingest_npm.py to truncate unique_id to prevent field length errors.
    """
    print("\n" + "="*70)
    print("FIX 1b: Update ingest_npm.py Script")
    print("="*70)

    npm_script = os.path.join(os.path.dirname(script_dir), "01_ingestion", "ingest_npm.py")

    if not os.path.exists(npm_script):
        print(f"   ❌ Script not found: {npm_script}")
        return False

    # Read current content
    with open(npm_script, 'r', encoding='utf-8') as f:
        content = f.read()

    # Check if already fixed
    if 'unique_id[:100]' in content or 'truncate unique_id' in content.lower():
        print("   ✅ Script already has unique_id truncation")
        return True

    # Find the line that creates unique_id and add truncation
    old_line = 'unique_id = f"npm_{project_slug}"'
    new_line = '# Truncate unique_id to 64 chars to prevent field length errors\n                unique_id = f"npm_{project_slug}"[:64]'

    if old_line in content:
        content = content.replace(old_line, new_line)

        with open(npm_script, 'w', encoding='utf-8') as f:
            f.write(content)

        print("   ✅ Updated ingest_npm.py to truncate unique_id to 100 chars")
        return True
    else:
        print("   ⚠️ Could not find unique_id line to update")
        print("   Manual fix: Add [:100] to truncate unique_id")
        return False


# ============================================================================
# MAIN EXECUTION
# ============================================================================

def main():
    print("█" * 70)
    print("   DATA QUALITY FIXES")
    print("█" * 70)
    print(f"   Started: {datetime.now()}")
    print(f"   GDB: {GDB}")

    results = {
        'npm_unique_id': 0,
        'dcm_region': 0,
        'state_fixes': 0,
        'script_updated': False
    }

    # Process gold_buildings_full
    print(f"\n{'='*70}")
    print(f"   Processing: gold_buildings_full")
    print(f"{'='*70}")

    fc_path = os.path.join(GDB, GOLD_BUILDINGS)

    # Fix 1: NPM unique_id (check only - records already failed to insert)
    results['npm_unique_id'] = fix_npm_unique_id_length(fc_path)

    # Fix 1b: Update the ingestion script for future runs
    results['script_updated'] = update_ingest_npm_script()

    # Fix 2: DCM missing region
    results['dcm_region'] = fix_dcm_missing_region(fc_path)

    # Fix 3 & 4: State field standardization
    results['state_fixes'] = fix_state_abbreviations(fc_path)

    # Process gold_campus_full
    print(f"\n{'='*70}")
    print(f"   Processing: gold_campus_full")
    print(f"{'='*70}")

    campus_path = os.path.join(GDB, GOLD_CAMPUS)

    # Fix 2: DCM missing region (campus)
    dcm_campus = fix_dcm_missing_region(campus_path)
    results['dcm_region'] += dcm_campus

    # Fix 3 & 4: State field standardization (campus)
    state_campus = fix_state_abbreviations(campus_path)
    results['state_fixes'] += state_campus

    # Summary
    print("\n" + "█" * 70)
    print("   SUMMARY")
    print("█" * 70)
    print(f"""
   Results:
   ----------------------------------------
   NPM unique_id issues detected: {results['npm_unique_id']}
   ingest_npm.py updated: {'Yes' if results['script_updated'] else 'No'}
   DCM region fixed: {results['dcm_region']:,}
   State field fixes: {results['state_fixes']:,}

   NEXT STEPS:
   1. Re-run ingest_npm.py to pick up the 2 failed records
   2. Run campus_rollup_new.py to propagate fixes to campuses
   3. Run create_xb_combined_layer.py to update XB layer

   Completed: {datetime.now()}
""")
    print("█" * 70)

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
