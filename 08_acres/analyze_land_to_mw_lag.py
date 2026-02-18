"""
Land Sale to First MW Time-Lag Analysis
========================================

Analyzes the time lag between land acquisition (from ACRES) and first MW commissioned
(from Consensus Model) by site.

This script:
1. Joins ACRES campus centroids with gold_buildings_full/gold_campus_full by spatial proximity
2. Extracts earliest land acquisition date from ACRES
3. Extracts first commissioned MW date from Consensus Model
4. Calculates the time lag in months/years
5. Produces summary statistics by company, state, and time period

USAGE (in ArcGIS Pro Python window):
    exec(open(r"C:/Users/ptanderson/Documents/ArcGIS/Projects/Lean Consensus DC Model/scripts/08_acres/analyze_land_to_mw_lag.py", encoding='utf-8').read())

Author: Meta Data Center GIS Team
Created: 2026-01-29
"""

import arcpy
import os
import sys
from datetime import datetime
from collections import defaultdict
import math

# Add _utils to path
try:
    script_dir = os.path.dirname(os.path.abspath(__file__))
except NameError:
    script_dir = r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\scripts\08_acres"

utils_dir = os.path.join(os.path.dirname(script_dir), "_utils")
if utils_dir not in sys.path:
    sys.path.insert(0, utils_dir)

from config import GDB, GOLD_BUILDINGS, GOLD_CAMPUS

arcpy.env.workspace = GDB
arcpy.env.overwriteOutput = True

# ==============================================================================
# CONFIGURATION
# ==============================================================================

# Input feature classes
ACRES_CAMPUS_CENTROIDS = os.path.join(GDB, "acres_campus_centroids")
ACRES_PARCEL_CROSSWALK = os.path.join(GDB, "acres_parcel_campus_xwalk")

# Output analysis table
OUTPUT_LAND_TO_MW_ANALYSIS = os.path.join(GDB, "land_to_mw_analysis")

# Spatial matching tolerance (meters)
SPATIAL_MATCH_TOLERANCE = 2000  # 2km radius for matching ACRES to Consensus sites

# Company name normalization between ACRES and Consensus Model
COMPANY_ALIASES = {
    # ACRES company_clean → Consensus company_clean
    'Meta': ['Meta'],
    'Microsoft': ['Microsoft'],
    'AWS': ['AWS', 'Amazon'],
    'Google': ['Google'],
    'Apple': ['Apple'],
    'Oracle': ['Oracle'],
    'Digital Realty': ['Digital Realty', 'DLR'],
    'Equinix': ['Equinix'],
    'CyrusOne': ['CyrusOne'],
    'Vantage': ['Vantage'],
    'QTS': ['QTS'],
    'T5': ['T5'],
    'CoreSite': ['CoreSite'],
    'Switch': ['Switch'],
    'Compass': ['Compass'],
    'Aligned': ['Aligned'],
}


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


def load_acres_campuses():
    """Load ACRES campus centroids with acquisition dates."""
    print("\n   Loading ACRES campus centroids...")
    
    campuses = []
    
    if not arcpy.Exists(ACRES_CAMPUS_CENTROIDS):
        print("   ERROR: ACRES campus centroids not found. Run acres_parcel_rollup.py first.")
        return []
    
    # Get available fields
    fields = [f.name for f in arcpy.ListFields(ACRES_CAMPUS_CENTROIDS)]
    print(f"   Fields: {fields[:10]}...")
    
    # Build field list for cursor
    cursor_fields = ['SHAPE@XY', 'campus_id']
    
    # Map field names (handle variations)
    field_map = {
        'company_clean': ['company_clean', 'company'],
        'state': ['state'],
        'county': ['county'],
        'total_acres': ['total_acres'],
        'parcel_count': ['parcel_count'],
        'earliest_acquisition_date': ['earliest_acquisition_date', 'earliest_date'],
        'latest_acquisition_date': ['latest_acquisition_date', 'latest_date'],
    }
    
    for target, candidates in field_map.items():
        for candidate in candidates:
            if candidate in fields:
                cursor_fields.append(candidate)
                break
    
    with arcpy.da.SearchCursor(ACRES_CAMPUS_CENTROIDS, cursor_fields) as cursor:
        for row in cursor:
            xy = row[0]
            if not xy or not xy[0] or not xy[1]:
                continue
            
            record = {
                'lon': xy[0],
                'lat': xy[1],
                'acres_campus_id': row[1],
            }
            
            # Map other fields
            for i, field in enumerate(cursor_fields[2:], 2):
                for target, candidates in field_map.items():
                    if field in candidates:
                        record[target] = row[i]
                        break
            
            campuses.append(record)
    
    print(f"   Loaded {len(campuses):,} ACRES campus records")
    return campuses


def load_consensus_campuses():
    """Load Consensus Model campuses with commission dates and MW."""
    print("\n   Loading Consensus Model campuses...")
    
    campuses = []
    
    # Determine which layer to use - prefer campus, fall back to buildings
    if arcpy.Exists(GOLD_CAMPUS):
        input_fc = GOLD_CAMPUS
        print(f"   Using: {os.path.basename(GOLD_CAMPUS)}")
    elif arcpy.Exists(GOLD_BUILDINGS):
        input_fc = GOLD_BUILDINGS
        print(f"   Using: {os.path.basename(GOLD_BUILDINGS)}")
    else:
        print("   ERROR: No Consensus Model data found.")
        return []
    
    # Get available fields
    fields = [f.name for f in arcpy.ListFields(input_fc)]
    
    # Build field list
    cursor_fields = ['SHAPE@XY', 'OBJECTID']
    
    # Core fields we need
    target_fields = [
        'ucid', 'unique_id', 'company_clean', 'company_clean_filter',
        'state_abbr', 'city', 'facility_status',
        'full_capacity_mw', 'commissioned_power_mw',
        'capacity_under_construction_mw', 'planned_capacity_mw',
        'mw_2023', 'mw_2024', 'mw_2025', 'mw_2026', 'mw_2027',
        'mw_2028', 'mw_2029', 'mw_2030', 'mw_2031', 'mw_2032'
    ]
    
    for field in target_fields:
        if field in fields:
            cursor_fields.append(field)
    
    with arcpy.da.SearchCursor(input_fc, cursor_fields) as cursor:
        for row in cursor:
            xy = row[0]
            if not xy or not xy[0] or not xy[1]:
                continue
            
            record = {
                'lon': xy[0],
                'lat': xy[1],
                'consensus_oid': row[1],
            }
            
            # Map fields
            for i, field in enumerate(cursor_fields[2:], 2):
                record[field] = row[i]
            
            campuses.append(record)
    
    print(f"   Loaded {len(campuses):,} Consensus Model records")
    return campuses


def match_acres_to_consensus(acres_campuses, consensus_campuses):
    """
    Match ACRES campuses to Consensus Model campuses by:
    1. Company name match (fuzzy)
    2. Spatial proximity
    
    Returns list of matched pairs with analysis data.
    """
    print(f"\n   Matching ACRES to Consensus (tolerance: {SPATIAL_MATCH_TOLERANCE}m)...")
    
    matches = []
    unmatched_acres = []
    
    # Build spatial index of consensus campuses by company
    consensus_by_company = defaultdict(list)
    for camp in consensus_campuses:
        company = camp.get('company_clean', 'Unknown')
        consensus_by_company[company].append(camp)
    
    # For each ACRES campus, find best matching Consensus campus
    for acres_camp in acres_campuses:
        acres_company = acres_camp.get('company_clean', 'Unknown')
        
        # Get candidate companies (including aliases)
        candidate_companies = [acres_company]
        for key, aliases in COMPANY_ALIASES.items():
            if acres_company in aliases or key == acres_company:
                candidate_companies.extend([key] + aliases)
        candidate_companies = list(set(candidate_companies))
        
        # Find all consensus candidates for this company
        candidates = []
        for company in candidate_companies:
            candidates.extend(consensus_by_company.get(company, []))
        
        if not candidates:
            unmatched_acres.append(acres_camp)
            continue
        
        # Find closest spatial match
        best_match = None
        best_distance = float('inf')
        
        for consensus_camp in candidates:
            dist = haversine_distance(
                acres_camp['lat'], acres_camp['lon'],
                consensus_camp['lat'], consensus_camp['lon']
            )
            
            if dist < best_distance:
                best_distance = dist
                best_match = consensus_camp
        
        if best_distance <= SPATIAL_MATCH_TOLERANCE:
            matches.append({
                'acres': acres_camp,
                'consensus': best_match,
                'distance_m': best_distance
            })
        else:
            unmatched_acres.append(acres_camp)
    
    print(f"   Matched: {len(matches):,} ACRES campuses")
    print(f"   Unmatched: {len(unmatched_acres):,} ACRES campuses (no Consensus site within {SPATIAL_MATCH_TOLERANCE}m)")
    
    return matches, unmatched_acres


def estimate_first_mw_date(consensus_record):
    """
    Estimate the date of first MW commissioned based on:
    1. Year-over-year MW values (mw_2023, mw_2024, etc.)
    2. Facility status
    3. Commissioned power value
    
    Returns datetime or None if cannot be determined.
    """
    # Check year-over-year MW values to find first year with MW > 0
    years = ['2023', '2024', '2025', '2026', '2027', '2028', '2029', '2030', '2031', '2032']
    
    for year in years:
        mw_value = consensus_record.get(f'mw_{year}')
        if mw_value and mw_value > 0:
            # Return January 1 of that year as estimate
            return datetime(int(year), 1, 1)
    
    # Check if currently active with commissioned power
    status = consensus_record.get('facility_status', '').lower()
    commissioned_mw = consensus_record.get('commissioned_power_mw', 0)
    
    if 'active' in status and commissioned_mw and commissioned_mw > 0:
        # Assume commissioned before current year
        return datetime(2023, 1, 1)
    
    # Cannot determine first MW date
    return None


def calculate_time_lag(acquisition_date, first_mw_date):
    """
    Calculate the time lag between acquisition and first MW.
    
    Returns dict with lag in days, months, and years.
    """
    if not acquisition_date or not first_mw_date:
        return None
    
    # Handle date objects
    if isinstance(acquisition_date, str):
        try:
            acquisition_date = datetime.strptime(acquisition_date[:10], '%Y-%m-%d')
        except:
            return None
    
    # Calculate difference
    delta = first_mw_date - acquisition_date
    
    lag_days = delta.days
    lag_months = lag_days / 30.44  # Average days per month
    lag_years = lag_days / 365.25
    
    return {
        'lag_days': lag_days,
        'lag_months': round(lag_months, 1),
        'lag_years': round(lag_years, 2),
    }


def analyze_matches(matches):
    """
    Perform time lag analysis on matched ACRES-Consensus pairs.
    """
    print("\n   Analyzing time lag for matched sites...")
    
    analysis_results = []
    
    for match in matches:
        acres = match['acres']
        consensus = match['consensus']
        
        # Get acquisition date
        acquisition_date = acres.get('earliest_acquisition_date')
        
        # Estimate first MW date
        first_mw_date = estimate_first_mw_date(consensus)
        
        # Calculate time lag
        lag = calculate_time_lag(acquisition_date, first_mw_date)
        
        result = {
            # ACRES data
            'acres_campus_id': acres.get('acres_campus_id'),
            'acres_company': acres.get('company_clean'),
            'acres_state': acres.get('state'),
            'acres_county': acres.get('county'),
            'total_acres': acres.get('total_acres'),
            'parcel_count': acres.get('parcel_count'),
            'acquisition_date': acquisition_date,
            
            # Consensus data
            'consensus_ucid': consensus.get('ucid'),
            'consensus_company': consensus.get('company_clean'),
            'consensus_state': consensus.get('state_abbr'),
            'consensus_city': consensus.get('city'),
            'facility_status': consensus.get('facility_status'),
            'commissioned_mw': consensus.get('commissioned_power_mw'),
            'full_capacity_mw': consensus.get('full_capacity_mw'),
            'first_mw_date': first_mw_date,
            
            # Match quality
            'match_distance_m': match['distance_m'],
            
            # Calculated lag
            'lag_days': lag.get('lag_days') if lag else None,
            'lag_months': lag.get('lag_months') if lag else None,
            'lag_years': lag.get('lag_years') if lag else None,
            
            # Coordinates
            'acres_lat': acres.get('lat'),
            'acres_lon': acres.get('lon'),
            'consensus_lat': consensus.get('lat'),
            'consensus_lon': consensus.get('lon'),
        }
        
        analysis_results.append(result)
    
    # Count results with valid lag
    valid_lag_count = sum(1 for r in analysis_results if r.get('lag_months') is not None)
    print(f"   Sites with calculable lag: {valid_lag_count:,} of {len(analysis_results):,}")
    
    return analysis_results


def create_analysis_output(analysis_results):
    """Create output feature class with analysis results."""
    print(f"\n   Creating analysis output feature class...")
    
    # Delete existing
    if arcpy.Exists(OUTPUT_LAND_TO_MW_ANALYSIS):
        arcpy.management.Delete(OUTPUT_LAND_TO_MW_ANALYSIS)
    
    # Create feature class (point)
    spatial_ref = arcpy.SpatialReference(4326)
    arcpy.management.CreateFeatureclass(
        GDB,
        os.path.basename(OUTPUT_LAND_TO_MW_ANALYSIS),
        "POINT",
        spatial_reference=spatial_ref
    )
    
    # Add fields
    fields_to_add = [
        ('acres_campus_id', 'TEXT', 50),
        ('acres_company', 'TEXT', 100),
        ('acres_state', 'TEXT', 10),
        ('acres_county', 'TEXT', 100),
        ('total_acres', 'DOUBLE', None),
        ('parcel_count', 'LONG', None),
        ('acquisition_date', 'DATE', None),
        ('consensus_ucid', 'TEXT', 75),
        ('consensus_company', 'TEXT', 100),
        ('consensus_state', 'TEXT', 10),
        ('consensus_city', 'TEXT', 100),
        ('facility_status', 'TEXT', 50),
        ('commissioned_mw', 'DOUBLE', None),
        ('full_capacity_mw', 'DOUBLE', None),
        ('first_mw_date', 'DATE', None),
        ('match_distance_m', 'DOUBLE', None),
        ('lag_days', 'LONG', None),
        ('lag_months', 'DOUBLE', None),
        ('lag_years', 'DOUBLE', None),
    ]
    
    for field_name, field_type, field_length in fields_to_add:
        if field_length:
            arcpy.management.AddField(OUTPUT_LAND_TO_MW_ANALYSIS, field_name, field_type, field_length=field_length)
        else:
            arcpy.management.AddField(OUTPUT_LAND_TO_MW_ANALYSIS, field_name, field_type)
    
    # Insert records
    insert_fields = ['SHAPE@XY'] + [f[0] for f in fields_to_add]
    
    with arcpy.da.InsertCursor(OUTPUT_LAND_TO_MW_ANALYSIS, insert_fields) as cursor:
        for result in analysis_results:
            row = [
                (result['acres_lon'], result['acres_lat']),
                result.get('acres_campus_id'),
                result.get('acres_company'),
                result.get('acres_state'),
                result.get('acres_county'),
                result.get('total_acres'),
                result.get('parcel_count'),
                result.get('acquisition_date'),
                result.get('consensus_ucid'),
                result.get('consensus_company'),
                result.get('consensus_state'),
                result.get('consensus_city'),
                result.get('facility_status'),
                result.get('commissioned_mw'),
                result.get('full_capacity_mw'),
                result.get('first_mw_date'),
                result.get('match_distance_m'),
                result.get('lag_days'),
                result.get('lag_months'),
                result.get('lag_years'),
            ]
            cursor.insertRow(row)
    
    count = int(arcpy.management.GetCount(OUTPUT_LAND_TO_MW_ANALYSIS)[0])
    print(f"   Created {count:,} analysis records")
    
    return count


def print_summary_statistics(analysis_results):
    """Print summary statistics of the time lag analysis."""
    print("\n" + "=" * 70)
    print("   LAND SALE TO FIRST MW TIME LAG ANALYSIS")
    print("=" * 70)
    
    # Filter to results with valid lag
    valid_results = [r for r in analysis_results if r.get('lag_months') is not None]
    
    if not valid_results:
        print("\n   No results with calculable time lag.")
        return
    
    # Overall statistics
    lag_months = [r['lag_months'] for r in valid_results]
    avg_lag = sum(lag_months) / len(lag_months)
    min_lag = min(lag_months)
    max_lag = max(lag_months)
    
    print(f"\n   Overall Statistics (n={len(valid_results):,}):")
    print(f"   {'Metric':<30} {'Value':>15}")
    print(f"   {'-'*30} {'-'*15}")
    print(f"   {'Average Lag (months)':<30} {avg_lag:>15.1f}")
    print(f"   {'Min Lag (months)':<30} {min_lag:>15.1f}")
    print(f"   {'Max Lag (months)':<30} {max_lag:>15.1f}")
    print(f"   {'Average Lag (years)':<30} {avg_lag/12:>15.2f}")
    
    # By Company
    print(f"\n   Time Lag by Company:")
    print(f"   {'Company':<25} {'Sites':>8} {'Avg Lag (mo)':>15} {'Avg MW':>12}")
    print(f"   {'-'*25} {'-'*8} {'-'*15} {'-'*12}")
    
    by_company = defaultdict(list)
    for r in valid_results:
        company = r.get('acres_company', 'Unknown')
        by_company[company].append(r)
    
    for company in sorted(by_company.keys()):
        company_results = by_company[company]
        avg_lag_company = sum(r['lag_months'] for r in company_results) / len(company_results)
        avg_mw = sum(r.get('commissioned_mw') or 0 for r in company_results) / len(company_results)
        print(f"   {company:<25} {len(company_results):>8} {avg_lag_company:>15.1f} {avg_mw:>12.1f}")
    
    # By State
    print(f"\n   Top 10 States by Site Count:")
    by_state = defaultdict(list)
    for r in valid_results:
        state = r.get('acres_state', 'Unknown')
        by_state[state].append(r)
    
    sorted_states = sorted(by_state.items(), key=lambda x: -len(x[1]))[:10]
    print(f"   {'State':<10} {'Sites':>8} {'Avg Lag (mo)':>15}")
    print(f"   {'-'*10} {'-'*8} {'-'*15}")
    
    for state, state_results in sorted_states:
        avg_lag_state = sum(r['lag_months'] for r in state_results) / len(state_results)
        print(f"   {state:<10} {len(state_results):>8} {avg_lag_state:>15.1f}")
    
    # Time lag distribution
    print(f"\n   Time Lag Distribution:")
    buckets = [
        ('< 12 months', 0, 12),
        ('12-24 months', 12, 24),
        ('24-36 months', 24, 36),
        ('36-48 months', 36, 48),
        ('48-60 months', 48, 60),
        ('> 60 months', 60, float('inf')),
    ]
    
    print(f"   {'Range':<20} {'Count':>10} {'Percent':>10}")
    print(f"   {'-'*20} {'-'*10} {'-'*10}")
    
    for label, low, high in buckets:
        count = sum(1 for r in valid_results if low <= r['lag_months'] < high)
        pct = count / len(valid_results) * 100
        print(f"   {label:<20} {count:>10} {pct:>9.1f}%")


def main():
    """Main function for land-to-MW time lag analysis."""
    print("=" * 70)
    print("   LAND SALE TO FIRST MW TIME LAG ANALYSIS")
    print("=" * 70)
    print(f"   Started: {datetime.now()}")
    
    # Step 1: Load ACRES campuses
    print("\n" + "-" * 70)
    print("[Step 1] Loading ACRES campus data...")
    print("-" * 70)
    acres_campuses = load_acres_campuses()
    
    if not acres_campuses:
        print("\n   ERROR: No ACRES data. Run acres_parcel_rollup.py first.")
        return
    
    # Step 2: Load Consensus Model campuses
    print("\n" + "-" * 70)
    print("[Step 2] Loading Consensus Model data...")
    print("-" * 70)
    consensus_campuses = load_consensus_campuses()
    
    if not consensus_campuses:
        print("\n   ERROR: No Consensus Model data. Run pipeline first.")
        return
    
    # Step 3: Match ACRES to Consensus
    print("\n" + "-" * 70)
    print("[Step 3] Matching ACRES to Consensus Model...")
    print("-" * 70)
    matches, unmatched = match_acres_to_consensus(acres_campuses, consensus_campuses)
    
    if not matches:
        print("\n   ERROR: No matches found.")
        return
    
    # Step 4: Analyze time lag
    print("\n" + "-" * 70)
    print("[Step 4] Analyzing time lag...")
    print("-" * 70)
    analysis_results = analyze_matches(matches)
    
    # Step 5: Create output
    print("\n" + "-" * 70)
    print("[Step 5] Creating output feature class...")
    print("-" * 70)
    count = create_analysis_output(analysis_results)
    
    # Print summary
    print_summary_statistics(analysis_results)
    
    print("\n" + "=" * 70)
    print("   ANALYSIS COMPLETE")
    print("=" * 70)
    print(f"\n   Output: {os.path.basename(OUTPUT_LAND_TO_MW_ANALYSIS)} ({count:,} records)")
    print(f"\n   Completed: {datetime.now()}")
    print("=" * 70)
    
    return analysis_results


# ==============================================================================
# EXECUTE
# ==============================================================================

if __name__ == "__main__":
    main()
else:
    main()
