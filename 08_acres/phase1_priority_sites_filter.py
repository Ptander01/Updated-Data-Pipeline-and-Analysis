"""
Phase 1: Priority Sites Filter - Peer Self-Build Planning Timeline Analysis
============================================================================

Filters the Consensus Model to the curated list of 28 priority DC sites
provided by the analyst team.

INPUT CSV:
- data/priority_sites_28.csv (28 sites with clusterid, gpu_owner, cluster name)

MATCHING LOGIC:
1. Match by clusterid → Semianalysis unique_id (SA_uuid format)
2. Fallback: Match by cluster name → facility_name
3. Fallback: Match by gpu_owner + location keywords

OUTPUT:
- priority_sites_filtered feature class with matched sites from Consensus Model
- Match statistics showing which sites were found/not found

USAGE (in ArcGIS Pro Python window):
    exec(open(r"C:/Users/ptanderson/Documents/ArcGIS/Projects/Lean Consensus DC Model/scripts/08_acres/phase1_priority_sites_filter.py", encoding='utf-8').read())

Author: Meta Data Center GIS Team
Created: 2026-02-02
Project: Peer Planning Timeline Analysis (1-Week Sprint)
"""

import arcpy
import os
import sys
import csv
from datetime import datetime
from collections import defaultdict

# Add _utils to path
try:
    script_dir = os.path.dirname(os.path.abspath(__file__))
except NameError:
    script_dir = r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\scripts\08_acres"

utils_dir = os.path.join(os.path.dirname(script_dir), "_utils")
if utils_dir not in sys.path:
    sys.path.insert(0, utils_dir)

from config import GDB, GOLD_BUILDINGS

arcpy.env.workspace = GDB
arcpy.env.overwriteOutput = True

# ==============================================================================
# CONFIGURATION
# ==============================================================================

# Priority sites CSV
PRIORITY_SITES_CSV = os.path.join(script_dir, "data", "priority_sites_28.csv")

# Output feature class
OUTPUT_FC = os.path.join(GDB, "priority_sites_filtered")

# Company name normalization (gpu_owner → company_clean)
GPU_OWNER_TO_COMPANY = {
    'AWS': ['AWS', 'Amazon'],
    'Google': ['Google'],
    'Microsoft': ['Microsoft'],
    'Oracle': ['Oracle'],
    'Meta': ['Meta'],
    'CoreWeave': ['CoreWeave'],
    'Fluidstack': ['Fluidstack', 'FluidStack'],
    'SoftBank': ['SoftBank', 'Softbank'],
    'xAI': ['xAI', 'XAI'],
}

# Location keywords to extract from cluster names for fuzzy matching
LOCATION_KEYWORDS = [
    'Indiana', 'North Carolina', 'Denton', 'Afton', 'BarberLake', 'Barker',
    'Abernathy', 'Goodnight', 'Cedar Rapids', 'Hamina', 'Haskell', 'Shakelford',
    'Shackelford', 'Hyperion', 'Prometheus', 'Titan', 'El Paso', 'Fairwater',
    'ATL', 'Atlanta', 'Wisconsin', 'Abilene', 'Borden', 'Dona Ana', 'Michigan',
    'Milam', 'Colossus'
]


def load_priority_sites():
    """Load priority sites from CSV."""
    print("\n" + "=" * 70)
    print("[Step 1] Loading priority sites from CSV...")
    print("=" * 70)
    
    if not os.path.exists(PRIORITY_SITES_CSV):
        print(f"   ERROR: CSV not found: {PRIORITY_SITES_CSV}")
        return []
    
    sites = []
    with open(PRIORITY_SITES_CSV, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            site = {
                'clusterid': row.get('clusterid', '').strip(),
                'gpu_owner': row.get('gpu_owner', '').strip(),
                'cluster': row.get('cluster', '').strip(),
                'num_instances': row.get('num_instances', '1'),
            }
            
            # Generate potential unique_id matches
            site['potential_ids'] = [
                f"SA_{site['clusterid']}",  # Semianalysis format
                f"SEMI_{site['clusterid']}",  # Alternative format
                site['clusterid'],  # Raw UUID
            ]
            
            # Extract location keywords from cluster name
            site['location_keywords'] = []
            cluster_lower = site['cluster'].lower()
            for kw in LOCATION_KEYWORDS:
                if kw.lower() in cluster_lower:
                    site['location_keywords'].append(kw)
            
            sites.append(site)
    
    print(f"   Loaded {len(sites)} priority sites")
    
    # Summary by gpu_owner
    by_owner = defaultdict(int)
    for site in sites:
        by_owner[site['gpu_owner']] += 1
    
    print(f"\n   BY GPU OWNER:")
    for owner, count in sorted(by_owner.items()):
        print(f"   - {owner}: {count}")
    
    return sites


def load_consensus_model():
    """Load all records from gold_buildings_full."""
    print("\n" + "=" * 70)
    print("[Step 2] Loading Consensus Model data...")
    print("=" * 70)
    
    if not arcpy.Exists(GOLD_BUILDINGS):
        print(f"   ERROR: {GOLD_BUILDINGS} not found.")
        return []
    
    # Get available fields
    fields = [f.name for f in arcpy.ListFields(GOLD_BUILDINGS)]
    print(f"   Available fields: {len(fields)}")
    
    # Required fields
    required_fields = ['SHAPE@XY', 'OBJECTID', 'unique_id']
    
    # Optional fields to include
    optional_fields = [
        'ucid', 'company_clean', 'company_clean_filter', 'record_level',
        'facility_name', 'facility_status', 'city', 'state_abbr', 'country', 'region',
        'full_capacity_mw', 'commissioned_power_mw',
        'mw_2023', 'mw_2024', 'mw_2025', 'mw_2026', 'mw_2027',
        'mw_2028', 'mw_2029', 'mw_2030', 'mw_2031', 'mw_2032',
        'source', 'market', 'latitude', 'longitude'
    ]
    
    cursor_fields = required_fields.copy()
    for field in optional_fields:
        if field in fields and field not in cursor_fields:
            cursor_fields.append(field)
    
    records = []
    with arcpy.da.SearchCursor(GOLD_BUILDINGS, cursor_fields) as cursor:
        for row in cursor:
            record = {}
            for i, field in enumerate(cursor_fields):
                if field == 'SHAPE@XY':
                    xy = row[i]
                    record['lon'] = xy[0] if xy else None
                    record['lat'] = xy[1] if xy else None
                else:
                    record[field] = row[i]
            records.append(record)
    
    print(f"   Loaded {len(records):,} records from Consensus Model")
    
    return records


def match_priority_sites(priority_sites, consensus_records):
    """
    Match priority sites to Consensus Model records.
    
    Matching strategies (in order):
    1. Exact match on clusterid → unique_id (with SA_ prefix)
    2. Fuzzy match on cluster name → facility_name
    3. Company + location keyword match
    """
    print("\n" + "=" * 70)
    print("[Step 3] Matching priority sites to Consensus Model...")
    print("=" * 70)
    
    # Build lookup indexes
    by_unique_id = {}
    by_facility_name = defaultdict(list)
    by_company = defaultdict(list)
    
    for record in consensus_records:
        uid = record.get('unique_id', '')
        if uid:
            by_unique_id[uid.lower()] = record
            # Also index by UUID portion only
            if '_' in uid:
                uuid_part = uid.split('_', 1)[1]
                by_unique_id[uuid_part.lower()] = record
        
        fname = record.get('facility_name', '')
        if fname:
            by_facility_name[fname.lower()].append(record)
        
        company = record.get('company_clean', '')
        if company:
            by_company[company.lower()].append(record)
    
    matched_sites = []
    unmatched_sites = []
    
    match_stats = {
        'total': len(priority_sites),
        'by_clusterid': 0,
        'by_facility_name': 0,
        'by_company_location': 0,
        'unmatched': 0,
    }
    
    for psite in priority_sites:
        match_found = False
        matched_record = None
        match_type = None
        
        # Strategy 1: Match by clusterid
        for potential_id in psite['potential_ids']:
            if potential_id.lower() in by_unique_id:
                matched_record = by_unique_id[potential_id.lower()]
                match_type = 'clusterid_match'
                match_stats['by_clusterid'] += 1
                match_found = True
                break
        
        # Strategy 2: Match by facility name
        if not match_found:
            cluster_name = psite['cluster'].lower()
            
            # Try exact match first
            if cluster_name in by_facility_name:
                matched_record = by_facility_name[cluster_name][0]
                match_type = 'facility_name_exact'
                match_stats['by_facility_name'] += 1
                match_found = True
            else:
                # Try partial match
                for fname, records in by_facility_name.items():
                    # Check if cluster name is contained in facility name or vice versa
                    if cluster_name in fname or fname in cluster_name:
                        matched_record = records[0]
                        match_type = 'facility_name_partial'
                        match_stats['by_facility_name'] += 1
                        match_found = True
                        break
                    
                    # Check location keywords
                    for kw in psite['location_keywords']:
                        if kw.lower() in fname:
                            matched_record = records[0]
                            match_type = 'facility_name_keyword'
                            match_stats['by_facility_name'] += 1
                            match_found = True
                            break
                    
                    if match_found:
                        break
        
        # Strategy 3: Match by company + location keywords
        if not match_found:
            gpu_owner = psite['gpu_owner']
            company_variants = GPU_OWNER_TO_COMPANY.get(gpu_owner, [gpu_owner])
            
            for company in company_variants:
                company_records = by_company.get(company.lower(), [])
                
                for record in company_records:
                    record_text = ' '.join([
                        str(record.get('facility_name', '')),
                        str(record.get('city', '')),
                        str(record.get('state_abbr', '')),
                        str(record.get('market', '')),
                    ]).lower()
                    
                    for kw in psite['location_keywords']:
                        if kw.lower() in record_text:
                            matched_record = record
                            match_type = 'company_location_match'
                            match_stats['by_company_location'] += 1
                            match_found = True
                            break
                    
                    if match_found:
                        break
                
                if match_found:
                    break
        
        # Record result
        if match_found and matched_record:
            result = matched_record.copy()
            result['priority_clusterid'] = psite['clusterid']
            result['priority_gpu_owner'] = psite['gpu_owner']
            result['priority_cluster_name'] = psite['cluster']
            result['match_type'] = match_type
            matched_sites.append(result)
        else:
            unmatched_sites.append(psite)
            match_stats['unmatched'] += 1
    
    # Print match stats
    print(f"\n   MATCHING SUMMARY:")
    print(f"   {'Match Type':<35} {'Count':>10} {'%':>10}")
    print(f"   {'-'*35} {'-'*10} {'-'*10}")
    print(f"   {'By clusterid (unique_id)':<35} {match_stats['by_clusterid']:>10,} {match_stats['by_clusterid']/match_stats['total']*100:>9.1f}%")
    print(f"   {'By facility name':<35} {match_stats['by_facility_name']:>10,} {match_stats['by_facility_name']/match_stats['total']*100:>9.1f}%")
    print(f"   {'By company + location':<35} {match_stats['by_company_location']:>10,} {match_stats['by_company_location']/match_stats['total']*100:>9.1f}%")
    print(f"   {'Unmatched':<35} {match_stats['unmatched']:>10,} {match_stats['unmatched']/match_stats['total']*100:>9.1f}%")
    print(f"   {'-'*35} {'-'*10} {'-'*10}")
    print(f"   {'TOTAL MATCHED':<35} {len(matched_sites):>10,} {len(matched_sites)/match_stats['total']*100:>9.1f}%")
    
    # List unmatched sites
    if unmatched_sites:
        print(f"\n   UNMATCHED SITES ({len(unmatched_sites)}):")
        for site in unmatched_sites:
            print(f"   - {site['gpu_owner']}: {site['cluster']} (ID: {site['clusterid'][:8]}...)")
    
    return matched_sites, unmatched_sites, match_stats


def create_output_feature_class(matched_sites):
    """Create output feature class with matched priority sites."""
    print("\n" + "=" * 70)
    print("[Step 4] Creating output feature class...")
    print("=" * 70)
    
    # Delete existing
    if arcpy.Exists(OUTPUT_FC):
        arcpy.management.Delete(OUTPUT_FC)
    
    # Create feature class
    spatial_ref = arcpy.SpatialReference(4326)
    arcpy.management.CreateFeatureclass(
        GDB,
        os.path.basename(OUTPUT_FC),
        "POINT",
        spatial_reference=spatial_ref
    )
    
    # Add fields
    fields_to_add = [
        # Priority site info
        ('priority_clusterid', 'TEXT', 50),
        ('priority_gpu_owner', 'TEXT', 50),
        ('priority_cluster_name', 'TEXT', 200),
        ('match_type', 'TEXT', 50),
        
        # Consensus Model fields
        ('unique_id', 'TEXT', 100),
        ('ucid', 'TEXT', 75),
        ('company_clean', 'TEXT', 100),
        ('facility_name', 'TEXT', 200),
        ('facility_status', 'TEXT', 50),
        ('city', 'TEXT', 100),
        ('state_abbr', 'TEXT', 10),
        ('country', 'TEXT', 100),
        ('region', 'TEXT', 20),
        ('record_level', 'TEXT', 50),
        ('full_capacity_mw', 'DOUBLE', None),
        ('commissioned_power_mw', 'DOUBLE', None),
        ('mw_2025', 'DOUBLE', None),
        ('mw_2026', 'DOUBLE', None),
        ('mw_2027', 'DOUBLE', None),
        ('source', 'TEXT', 200),
        ('market', 'TEXT', 100),
        ('latitude', 'DOUBLE', None),
        ('longitude', 'DOUBLE', None),
    ]
    
    for field_name, field_type, field_length in fields_to_add:
        if field_length:
            arcpy.management.AddField(OUTPUT_FC, field_name, field_type, field_length=field_length)
        else:
            arcpy.management.AddField(OUTPUT_FC, field_name, field_type)
    
    # Insert records
    insert_fields = ['SHAPE@XY'] + [f[0] for f in fields_to_add]
    
    inserted = 0
    with arcpy.da.InsertCursor(OUTPUT_FC, insert_fields) as cursor:
        for site in matched_sites:
            if not site.get('lon') or not site.get('lat'):
                continue
            
            row = [
                (site['lon'], site['lat']),
                site.get('priority_clusterid'),
                site.get('priority_gpu_owner'),
                site.get('priority_cluster_name'),
                site.get('match_type'),
                site.get('unique_id'),
                site.get('ucid'),
                site.get('company_clean'),
                site.get('facility_name'),
                site.get('facility_status'),
                site.get('city'),
                site.get('state_abbr'),
                site.get('country'),
                site.get('region'),
                site.get('record_level'),
                site.get('full_capacity_mw'),
                site.get('commissioned_power_mw'),
                site.get('mw_2025'),
                site.get('mw_2026'),
                site.get('mw_2027'),
                site.get('source'),
                site.get('market'),
                site.get('lat'),
                site.get('lon'),
            ]
            
            cursor.insertRow(row)
            inserted += 1
    
    print(f"   Created: {os.path.basename(OUTPUT_FC)}")
    print(f"   Records: {inserted:,}")
    
    return inserted


def print_summary(matched_sites):
    """Print summary of matched priority sites."""
    print("\n" + "=" * 70)
    print("PRIORITY SITES SUMMARY")
    print("=" * 70)
    
    if not matched_sites:
        print("   No matched sites.")
        return
    
    # By GPU owner
    print(f"\n   BY GPU OWNER:")
    print(f"   {'Owner':<15} {'Sites':>8} {'Total MW (2027)':>18}")
    print(f"   {'-'*15} {'-'*8} {'-'*18}")
    
    by_owner = defaultdict(list)
    for site in matched_sites:
        owner = site.get('priority_gpu_owner', 'Unknown')
        by_owner[owner].append(site)
    
    for owner in sorted(by_owner.keys()):
        owner_sites = by_owner[owner]
        total_mw = sum(s.get('mw_2027') or 0 for s in owner_sites)
        print(f"   {owner:<15} {len(owner_sites):>8,} {total_mw:>18,.0f}")
    
    total_mw = sum(s.get('mw_2027') or 0 for s in matched_sites)
    print(f"   {'-'*15} {'-'*8} {'-'*18}")
    print(f"   {'TOTAL':<15} {len(matched_sites):>8,} {total_mw:>18,.0f}")
    
    # By match type
    print(f"\n   BY MATCH TYPE:")
    by_match_type = defaultdict(int)
    for site in matched_sites:
        match_type = site.get('match_type', 'unknown')
        by_match_type[match_type] += 1
    
    for match_type, count in sorted(by_match_type.items()):
        print(f"   - {match_type}: {count}")
    
    # Site list
    print(f"\n   MATCHED SITES ({len(matched_sites)}):")
    print(f"   {'Owner':<12} {'Cluster Name':<40} {'Location':<20} {'MW 2027':>10}")
    print(f"   {'-'*12} {'-'*40} {'-'*20} {'-'*10}")
    
    for site in sorted(matched_sites, key=lambda x: (x.get('priority_gpu_owner', ''), x.get('priority_cluster_name', ''))):
        owner = site.get('priority_gpu_owner', 'Unknown')[:12]
        cluster = site.get('priority_cluster_name', 'Unknown')[:40]
        location = f"{site.get('city', '')}, {site.get('state_abbr', '')}"[:20]
        mw = site.get('mw_2027') or 0
        print(f"   {owner:<12} {cluster:<40} {location:<20} {mw:>10,.0f}")


def main():
    """Main function for priority sites filtering."""
    print("=" * 70)
    print("PHASE 1: PRIORITY SITES FILTER (28 Curated Sites)")
    print("Peer Self-Build Planning Timeline Analysis")
    print("=" * 70)
    print(f"Started: {datetime.now()}")
    
    # Step 1: Load priority sites from CSV
    priority_sites = load_priority_sites()
    
    if not priority_sites:
        print("\n   ERROR: No priority sites loaded from CSV.")
        return
    
    # Step 2: Load Consensus Model
    consensus_records = load_consensus_model()
    
    if not consensus_records:
        print("\n   ERROR: No Consensus Model data loaded.")
        return
    
    # Step 3: Match priority sites
    matched_sites, unmatched_sites, match_stats = match_priority_sites(priority_sites, consensus_records)
    
    # Step 4: Create output
    if matched_sites:
        count = create_output_feature_class(matched_sites)
    else:
        count = 0
        print("\n   WARNING: No sites matched. Output feature class not created.")
    
    # Step 5: Print summary
    print_summary(matched_sites)
    
    # Final output
    print("\n" + "=" * 70)
    print("PRIORITY SITES FILTER COMPLETE")
    print("=" * 70)
    print(f"\n   Input: {len(priority_sites)} priority sites from CSV")
    print(f"   Output: {os.path.basename(OUTPUT_FC)} ({count:,} matched records)")
    print(f"\n   Match Rate: {len(matched_sites)}/{len(priority_sites)} ({len(matched_sites)/len(priority_sites)*100:.1f}%)")
    print(f"   Unmatched: {len(unmatched_sites)} sites")
    print(f"\n   Next Steps:")
    print(f"   1. Run phase1_acres_match.py with priority_sites_filtered as input")
    print(f"   2. Or run phase1_timeline_calc.py directly if ACRES already matched")
    print(f"\n   Completed: {datetime.now()}")
    print("=" * 70)
    
    return matched_sites, unmatched_sites


# ==============================================================================
# EXECUTE
# ==============================================================================

if __name__ == "__main__":
    main()
else:
    main()
