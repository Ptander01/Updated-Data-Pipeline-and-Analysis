"""
Text-Based UCID Generation Script
=================================

Generates human-readable Universal Campus IDs using the format:

Campus Level:  {COMPANY_CODE}-{CAMPUS_NAME}
Building Level: {COMPANY_CODE}-{CAMPUS_NAME}-{BUILDING_NUM}

Examples:
- META-ALTOONA (campus)
- META-ALTOONA-01 (building 1)
- OAI-STARGATE-01 (OpenAI Stargate building 1)
- AWS-ASHBURN-EAST (AWS Ashburn East campus)

Logic:
1. Use project_name if available, otherwise fall back to city
2. Use geographic suffix (EAST, WEST, NORTH, SOUTH) for same-city disambiguation
3. Assign building numbers sequentially within each campus (source-agnostic)
4. All duplicate records across sources get the SAME UCID

Run in ArcGIS Pro Python window:
exec(open(r"...scripts/06_ucid/generate_text_ucid.py", encoding='utf-8').read())

Author: Meta Data Center GIS Team
Created: December 30, 2025
"""

import arcpy
import os
import sys
from datetime import datetime
from collections import defaultdict
import math
import re

# Add _utils to path for config import
try:
    script_dir = os.path.dirname(os.path.abspath(__file__))
except NameError:
    script_dir = r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\scripts\06_ucid"

utils_dir = os.path.join(os.path.dirname(script_dir), "_utils")
if utils_dir not in sys.path:
    sys.path.insert(0, utils_dir)

from config import (GDB, GOLD_CAMPUS, GOLD_BUILDINGS,
                    CAMPUS_MASTER_TIGHT, CAMPUS_MASTER_LOOSE,
                    UCID_TOLERANCE_TIGHT, UCID_TOLERANCE_LOOSE)

arcpy.env.workspace = GDB
arcpy.env.overwriteOutput = True

# =============================================================================
# COMPANY CODE MAPPING
# =============================================================================

# Canonical company name → Short code (3-5 chars)
COMPANY_CODES = {
    # Hyperscalers
    'Meta': 'META',
    'AWS': 'AWS',
    'Amazon': 'AWS',
    'Google': 'GOOG',
    'Microsoft': 'MSFT',
    'Oracle': 'ORCL',
    'Apple': 'AAPL',

    # AI Companies
    'OpenAI': 'OAI',
    'xAI': 'XAI',
    'Anthropic': 'ANTH',

    # Asian Tech Giants
    'ByteDance': 'BYTE',
    'TikTok': 'TIKTOK',
    'Alibaba': 'BABA',
    'Tencent': 'TENC',
    'Baidu': 'BIDU',

    # Enterprise Tech
    'IBM': 'IBM',
    'Salesforce': 'CRM',

    # Major Colo Providers
    'Equinix': 'EQIX',
    'Digital Realty': 'DLR',
    'CyrusOne': 'CONE',
    'QTS': 'QTS',
    'Vantage': 'VDC',
    'CoreSite': 'COR',
    'Switch': 'SWCH',
    'Flexential': 'FLEX',
    'DataBank': 'DBNK',
    'Compass': 'COMP',
    'EdgeConneX': 'EDGE',
    'Stack': 'STACK',
    'TierPoint': 'TIER',
    'Sabey': 'SABEY',
    'Aligned': 'ALIGN',
    'Stream': 'STRM',
    'T5': 'T5',
    'CloudHQ': 'CHQ',
    'Prime': 'PRIME',
    'H5': 'H5',
    'DataGryd': 'GRYD',

    # Telecom Colo
    'AT&T': 'ATT',
    'Verizon': 'VZ',
    'Lumen': 'LUMN',
    'NTT': 'NTT',
    'Colt': 'COLT',
    'Zayo': 'ZAYO',

    # International Colo
    'Global Switch': 'GLSW',
    'Interxion': 'INXN',
    'Cyxtera': 'CYXT',
    'Iron Mountain': 'IRM',
    'GDS': 'GDS',
    'Chindata': 'CD',
    'KDDI': 'KDDI',
    'Keppel': 'KEP',
    'ST Telemedia': 'STT',
}

# Build lowercase lookup
COMPANY_CODES_LOWER = {k.lower(): v for k, v in COMPANY_CODES.items()}

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_company_code(company_name):
    """Get short company code from company name."""
    if not company_name:
        return 'UNK'

    # Direct match
    if company_name in COMPANY_CODES:
        return COMPANY_CODES[company_name]

    # Case-insensitive match
    lower = company_name.lower()
    if lower in COMPANY_CODES_LOWER:
        return COMPANY_CODES_LOWER[lower]

    # Generate code from first 4 chars
    clean = re.sub(r'[^A-Za-z0-9]', '', company_name).upper()
    return clean[:4] if len(clean) >= 4 else clean or 'UNK'


def slugify(text):
    """Convert text to URL-safe slug (uppercase for UCID)."""
    if not text:
        return ''
    # Remove special characters, replace spaces with nothing
    clean = re.sub(r'[^A-Za-z0-9\s]', '', str(text))
    # Remove extra whitespace and convert to uppercase
    clean = re.sub(r'\s+', '', clean).upper()
    return clean


def haversine_distance(lat1, lon1, lat2, lon2):
    """Calculate great-circle distance between two points in meters."""
    R = 6371000  # Earth's radius in meters

    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)

    a = math.sin(delta_lat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

    return R * c


def get_geographic_suffix(campuses_in_city, new_campus_coords):
    """
    Determine geographic suffix (EAST, WEST, NORTH, SOUTH) for a new campus
    relative to existing campuses in the same city.
    """
    if not campuses_in_city:
        return None

    new_lat, new_lon = new_campus_coords

    # Calculate centroid of existing campuses
    avg_lat = sum(c['lat'] for c in campuses_in_city) / len(campuses_in_city)
    avg_lon = sum(c['lon'] for c in campuses_in_city) / len(campuses_in_city)

    # Determine direction from centroid
    lat_diff = new_lat - avg_lat
    lon_diff = new_lon - avg_lon

    # Use the more significant difference
    if abs(lon_diff) > abs(lat_diff):
        return 'EAST' if lon_diff > 0 else 'WEST'
    else:
        return 'NORTH' if lat_diff > 0 else 'SOUTH'


def generate_campus_ucid(company_code, campus_name, suffix=None):
    """Generate campus-level UCID."""
    ucid = f"{company_code}-{campus_name}"
    if suffix:
        ucid = f"{ucid}-{suffix}"
    return ucid


def generate_building_ucid(campus_ucid, building_num):
    """Generate building-level UCID."""
    return f"{campus_ucid}-{building_num:02d}"


# =============================================================================
# DATA LOADING
# =============================================================================

def load_building_records():
    """Load all building records from gold_buildings_full."""
    records = []

    fields = ['SHAPE@XY', 'OBJECTID', 'unique_id', 'source', 'source_unique_id',
              'company_clean', 'campus_name', 'building_designation',
              'city', 'state_abbr', 'country', 'region',
              'full_capacity_mw', 'commissioned_power_mw']

    # Check which fields exist
    existing_fields = [f.name for f in arcpy.ListFields(GOLD_BUILDINGS)]
    read_fields = [f for f in fields if f in existing_fields or f == 'SHAPE@XY']

    with arcpy.da.SearchCursor(GOLD_BUILDINGS, read_fields) as cursor:
        for row in cursor:
            xy = row[0]
            if xy and xy[0] and xy[1]:
                record = {
                    'lon': xy[0],
                    'lat': xy[1],
                }
                # Map remaining fields
                for i, field in enumerate(read_fields[1:], 1):
                    record[field] = row[i]

                # Get company_clean or fallback
                record['company'] = record.get('company_clean') or 'Unknown'

                records.append(record)

    return records


def load_campus_records():
    """Load all campus records from gold_campus_full."""
    records = []

    fields = ['SHAPE@XY', 'OBJECTID', 'source', 'campus_id',
              'company_clean', 'campus_name', 'city', 'state_abbr',
              'country', 'region', 'full_capacity_mw', 'building_count']

    # Check which fields exist
    existing_fields = [f.name for f in arcpy.ListFields(GOLD_CAMPUS)]
    read_fields = [f for f in fields if f in existing_fields or f == 'SHAPE@XY']

    with arcpy.da.SearchCursor(GOLD_CAMPUS, read_fields) as cursor:
        for row in cursor:
            xy = row[0]
            if xy and xy[0] and xy[1]:
                record = {
                    'lon': xy[0],
                    'lat': xy[1],
                }
                # Map remaining fields
                for i, field in enumerate(read_fields[1:], 1):
                    record[field] = row[i]

                # Get company_clean or fallback
                record['company'] = record.get('company_clean') or 'Unknown'

                records.append(record)

    return records


# =============================================================================
# CLUSTERING AND UCID GENERATION
# =============================================================================

def cluster_by_company_and_proximity(records, tolerance_m):
    """
    Cluster records by company + spatial proximity.
    Returns list of clusters, each containing records for the same physical campus.
    """
    # Group by company first
    by_company = defaultdict(list)
    for rec in records:
        by_company[rec['company']].append(rec)

    clusters = []

    for company, company_records in by_company.items():
        # Track which records have been assigned
        assigned = set()

        for i, rec in enumerate(company_records):
            if i in assigned:
                continue

            # Start new cluster
            cluster_records = [rec]
            assigned.add(i)

            # Find all records within tolerance (transitive)
            changed = True
            while changed:
                changed = False
                for j, other in enumerate(company_records):
                    if j in assigned:
                        continue

                    # Check distance to any record in cluster
                    for cluster_rec in cluster_records:
                        dist = haversine_distance(
                            cluster_rec['lat'], cluster_rec['lon'],
                            other['lat'], other['lon']
                        )
                        if dist <= tolerance_m:
                            cluster_records.append(other)
                            assigned.add(j)
                            changed = True
                            break

            # Calculate centroid
            avg_lat = sum(r['lat'] for r in cluster_records) / len(cluster_records)
            avg_lon = sum(r['lon'] for r in cluster_records) / len(cluster_records)

            clusters.append({
                'records': cluster_records,
                'company': company,
                'centroid': (avg_lat, avg_lon),
            })

    return clusters


def strip_company_from_name(name, company):
    """Remove company name prefix from campus_name if present."""
    if not name or not company:
        return name

    # Common variations to strip
    company_lower = company.lower()
    name_lower = name.lower()

    # Check if name starts with company
    if name_lower.startswith(company_lower):
        stripped = name[len(company):].strip()
        if stripped:
            return stripped

    # Check for common patterns like "AWS - Abu Dhabi" or "AWS Abu Dhabi"
    for sep in [' - ', '-', ' ']:
        if sep in name:
            parts = name.split(sep, 1)
            if parts[0].lower() == company_lower or parts[0].lower() in COMPANY_CODES_LOWER:
                return parts[1].strip() if len(parts) > 1 else name

    return name


def truncate_name(name, max_length=15):
    """Truncate a name to max_length characters."""
    if not name or len(name) <= max_length:
        return name
    return name[:max_length]


def determine_campus_name(cluster):
    """
    Determine the campus name for a cluster.

    Priority:
    1. City name (most reliable, clean)
    2. campus_name with company prefix stripped (if it's a project name)
    3. Coordinate-based fallback

    The campus_name field often contains "AWS Abu Dhabi" which would create
    redundant UCIDs like "AWS-AWSABUDHABI". We prefer city to avoid this.
    """
    records = cluster['records']
    company = cluster['company']

    # Collect all possible names
    cities = []
    campus_names = []

    for rec in records:
        if rec.get('city'):
            cities.append(rec['city'])
        if rec.get('campus_name'):
            # Strip company name if present
            clean_name = strip_company_from_name(rec['campus_name'], company)
            if clean_name:
                campus_names.append(clean_name)

    # Priority 1: Use city name (most reliable)
    if cities:
        city_counts = defaultdict(int)
        for city in cities:
            city_counts[city] += 1
        best_city = max(city_counts, key=city_counts.get)
        return truncate_name(slugify(best_city))

    # Priority 2: Use campus_name (with company stripped) if no city
    if campus_names:
        name_counts = defaultdict(int)
        for name in campus_names:
            name_counts[name] += 1
        best_name = max(name_counts, key=name_counts.get)
        return truncate_name(slugify(best_name))

    # Fallback: Use coordinates
    lat, lon = cluster['centroid']
    return f"LOC{abs(lat):.1f}{abs(lon):.1f}".replace('.', '')


def assign_ucids_to_clusters(clusters):
    """
    Assign text-based UCIDs to all clusters.
    Handles same-city disambiguation with geographic suffixes.
    """
    # Group clusters by company + base campus name
    by_company_name = defaultdict(list)

    for cluster in clusters:
        company_code = get_company_code(cluster['company'])
        campus_name = determine_campus_name(cluster)
        key = (company_code, campus_name)

        cluster['company_code'] = company_code
        cluster['campus_name'] = campus_name

        by_company_name[key].append(cluster)

    # Track how many duplicates we resolved
    duplicate_count = 0

    # Assign UCIDs, handling duplicates
    for (company_code, campus_name), same_name_clusters in by_company_name.items():
        if len(same_name_clusters) == 1:
            # Only one campus with this name - no suffix needed
            same_name_clusters[0]['ucid'] = generate_campus_ucid(company_code, campus_name)
        else:
            # Multiple campuses with same name - need geographic suffixes
            duplicate_count += 1

            # Sort by longitude (west to east) then latitude (south to north)
            sorted_clusters = sorted(same_name_clusters,
                                    key=lambda c: (c['centroid'][1], c['centroid'][0]))

            # Assign directional suffixes
            if len(sorted_clusters) == 2:
                # Two campuses: use EAST/WEST or NORTH/SOUTH based on primary axis
                c1, c2 = sorted_clusters
                lon_diff = abs(c1['centroid'][1] - c2['centroid'][1])
                lat_diff = abs(c1['centroid'][0] - c2['centroid'][0])

                if lon_diff > lat_diff:
                    c1['ucid'] = generate_campus_ucid(company_code, campus_name, 'WEST')
                    c2['ucid'] = generate_campus_ucid(company_code, campus_name, 'EAST')
                else:
                    c1['ucid'] = generate_campus_ucid(company_code, campus_name, 'SOUTH')
                    c2['ucid'] = generate_campus_ucid(company_code, campus_name, 'NORTH')
            else:
                # More than 2: use numbered suffixes
                for i, cluster in enumerate(sorted_clusters, 1):
                    cluster['ucid'] = generate_campus_ucid(company_code, campus_name, str(i))

    # Print summary instead of individual duplicates
    if duplicate_count > 0:
        print(f"   Resolved {duplicate_count} same-name campus groups with geographic suffixes")

    return clusters


def assign_building_numbers(clusters):
    """
    Assign building numbers within each campus cluster.
    Numbers are assigned source-agnostically (we don't trust source building numbers).
    """
    for cluster in clusters:
        records = cluster['records']
        campus_ucid = cluster['ucid']

        # Sort buildings by some deterministic order
        # Use: commissioned capacity (desc), then source, then unique_id
        sorted_records = sorted(records, key=lambda r: (
            -(r.get('commissioned_power_mw') or 0),
            r.get('source', ''),
            r.get('unique_id', '')
        ))

        # Assign building numbers
        for i, rec in enumerate(sorted_records, 1):
            rec['building_ucid'] = generate_building_ucid(campus_ucid, i)
            rec['campus_ucid'] = campus_ucid
            rec['building_num'] = i

    return clusters


# =============================================================================
# OUTPUT
# =============================================================================

def update_gold_buildings(clusters):
    """Update gold_buildings_full with UCIDs."""
    print("\n   Updating gold_buildings_full...")

    # Build lookup: unique_id → UCIDs
    ucid_lookup = {}
    for cluster in clusters:
        for rec in cluster['records']:
            unique_id = rec.get('unique_id')
            if unique_id:
                ucid_lookup[unique_id] = {
                    'campus_ucid': rec.get('campus_ucid'),
                    'building_ucid': rec.get('building_ucid'),
                }

    # Check if ucid field exists
    fields = [f.name for f in arcpy.ListFields(GOLD_BUILDINGS)]

    # Add fields if needed (increase field length to 75 to handle edge cases)
    if 'ucid' not in fields:
        arcpy.management.AddField(GOLD_BUILDINGS, 'ucid', 'TEXT', field_length=75,
                                  field_alias='Universal Campus ID')
        print("      Added 'ucid' field")

    if 'building_ucid' not in fields:
        arcpy.management.AddField(GOLD_BUILDINGS, 'building_ucid', 'TEXT', field_length=75,
                                  field_alias='Building UCID')
        print("      Added 'building_ucid' field")

    # Update records
    updated = 0
    with arcpy.da.UpdateCursor(GOLD_BUILDINGS, ['unique_id', 'ucid', 'building_ucid']) as cursor:
        for row in cursor:
            unique_id = row[0]
            if unique_id and unique_id in ucid_lookup:
                row[1] = ucid_lookup[unique_id]['campus_ucid']
                row[2] = ucid_lookup[unique_id]['building_ucid']
                cursor.updateRow(row)
                updated += 1

    print(f"      Updated {updated:,} building records with UCIDs")
    return updated


# NOTE: We no longer update gold_campus directly here.
# The campus_rollup_new.py script now uses UCID as the grouping key,
# so campus records will be created with UCID as the campus_id value.
# This eliminates the need for a separate campus update step.


def print_sample_ucids(clusters):
    """Print sample UCIDs for verification."""
    print("\n" + "=" * 70)
    print("   SAMPLE UCIDs GENERATED")
    print("=" * 70)

    # Group by company for display
    by_company = defaultdict(list)
    for cluster in clusters:
        by_company[cluster['company']].append(cluster)

    # Show samples for major companies
    shown = 0
    for company in sorted(by_company.keys()):
        if shown >= 20:
            break

        company_clusters = by_company[company][:3]  # Max 3 per company
        for cluster in company_clusters:
            if shown >= 20:
                break

            ucid = cluster['ucid']
            num_records = len(cluster['records'])
            sources = set(r.get('source', 'Unknown') for r in cluster['records'])

            print(f"   {ucid:<30} ({num_records} records from {', '.join(sources)})")
            shown += 1

    print(f"\n   ... and {len(clusters) - 20} more campuses")


# =============================================================================
# MAIN
# =============================================================================

def main():
    print("=" * 70)
    print("   TEXT-BASED UCID GENERATION")
    print("=" * 70)
    print(f"   Started: {datetime.now()}")
    print(f"\n   Format: {{COMPANY_CODE}}-{{CAMPUS_NAME}}[-{{SUFFIX}}]")
    print(f"   Examples: META-ALTOONA, AWS-ASHBURN-EAST, OAI-STARGATE")

    # Step 1: Load building records
    print("\n" + "-" * 70)
    print("[Step 1] Loading building records...")
    print("-" * 70)
    buildings = load_building_records()
    print(f"   Loaded {len(buildings):,} building records")

    # Step 2: Cluster by company + proximity
    print("\n" + "-" * 70)
    print(f"[Step 2] Clustering by company + proximity ({UCID_TOLERANCE_TIGHT}m tolerance)...")
    print("-" * 70)
    clusters = cluster_by_company_and_proximity(buildings, UCID_TOLERANCE_TIGHT)
    print(f"   Created {len(clusters):,} campus clusters")

    # Step 3: Assign text-based UCIDs
    print("\n" + "-" * 70)
    print("[Step 3] Assigning text-based UCIDs...")
    print("-" * 70)
    clusters = assign_ucids_to_clusters(clusters)
    print(f"   Assigned UCIDs to {len(clusters):,} campuses")

    # Step 4: Assign building numbers
    print("\n" + "-" * 70)
    print("[Step 4] Assigning building numbers...")
    print("-" * 70)
    clusters = assign_building_numbers(clusters)
    total_buildings = sum(len(c['records']) for c in clusters)
    print(f"   Assigned building numbers to {total_buildings:,} buildings")

    # Step 5: Update gold tables
    print("\n" + "-" * 70)
    print("[Step 5] Updating gold_buildings_full...")
    print("-" * 70)
    buildings_updated = update_gold_buildings(clusters)

    # Note: gold_campus is NOT updated here
    # It will be created by campus_rollup_new.py using UCID as the grouping key

    # Show samples
    print_sample_ucids(clusters)

    # Summary
    print("\n" + "=" * 70)
    print("   TEXT-BASED UCID GENERATION COMPLETE")
    print("=" * 70)
    print(f"\n   Results:")
    print(f"     Campus clusters created: {len(clusters):,}")
    print(f"     Buildings with UCIDs: {buildings_updated:,}")

    print(f"\n   NEXT STEP: Run campus_rollup_new.py to create gold_campus_full")
    print(f"              (It will group buildings by UCID)")

    print(f"\n   UCID Format Examples:")
    for cluster in clusters[:5]:
        print(f"     Campus: {cluster['ucid']}")
        if cluster['records']:
            print(f"     Building: {cluster['records'][0].get('building_ucid', 'N/A')}")

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
