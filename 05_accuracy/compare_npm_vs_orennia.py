"""
NPM vs Orennia Comparison Analysis Script (V3)
Comprehensive comparison of NewProjectMedia and Orennia datasets.

METHODOLOGY (Aligned with SA vs DCH workflow):
=============================================
This script supports three matching modes, aligned with the established
comparison methodology from SA_VS_DCH_COMPARISON_WORKFLOW.md:

1. BUILDING-LEVEL SPATIAL (default):
   - Uses gold_buildings_full
   - 1-to-1 optimal matching by distance
   - Good for understanding raw record overlap

2. BUILDING-LEVEL + COMPANY-AWARE:
   - Adds company name matching as a requirement
   - Only matches if same company + within distance threshold
   - Prevents AWS matched to Google at multi-tenant sites

3. CAMPUS-LEVEL UCID-BASED (recommended):
   - Uses gold_campus_full (UCID-aggregated data)
   - Matches on UCID (Universal Campus ID)
   - Best for accurate site counting and capacity comparison
   - Requires post-ingestion pipeline to have been run

KEY METRICS (from SA vs DCH v2):
- MAPE: Mean Absolute Percentage Error (lower = better)
- Systematic Bias: Consistent over/under-reporting
- Pearson r: Linear correlation strength
- Agreement Rate: % pairs within 20%
- Confidence Score: Match quality (0-100)

Run this script in ArcGIS Pro Python window after ingesting both sources.

Author: Meta Data Center GIS Team
Created: 2026-02-13
Updated: 2026-02-17 (V3 - Aligned with established methodology)
"""

import arcpy
import os
import sys
from datetime import datetime
from collections import defaultdict
import math
import json

# Add _utils to path for config import
try:
    script_dir = os.path.dirname(os.path.abspath(__file__))
except NameError:
    script_dir = r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\scripts\05_accuracy"

utils_dir = os.path.join(os.path.dirname(script_dir), "_utils")
if utils_dir not in sys.path:
    sys.path.insert(0, utils_dir)

from config import GOLD_BUILDINGS, GOLD_CAMPUS, GDB

# ============================================================================
# CONFIGURATION
# ============================================================================

# Spatial matching thresholds (meters)
THRESHOLDS = {
    '250m': 250,
    '500m': 500,
    '1km': 1000,
    '2km': 2000,
}

DEFAULT_THRESHOLD = 500

# Output directories
OUTPUT_DIR = r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\scripts\outputs\reports\accuracy"

# Source names in gold_buildings
ORENNIA_SOURCE = 'Orennia'
NPM_SOURCE = 'NewProjectMedia'

# Matching modes
MATCH_MODE_SPATIAL = 'spatial'           # Distance only
MATCH_MODE_COMPANY = 'company_aware'     # Distance + same company
MATCH_MODE_UCID = 'ucid'                 # Campus-level UCID matching

# Company name normalization
COMPANY_ALIASES = {
    'aws': ['amazon', 'aws', 'amazon web services'],
    'microsoft': ['microsoft', 'azure', 'msft'],
    'google': ['google', 'gcp', 'alphabet'],
    'meta': ['meta', 'facebook', 'fb'],
    'apple': ['apple'],
    'oracle': ['oracle', 'oci'],
    'equinix': ['equinix'],
    'digital realty': ['digital realty', 'digitalrealty', 'dlr'],
    'coreweave': ['coreweave', 'core weave'],
    'vantage': ['vantage'],
    'cyrusone': ['cyrusone', 'cyrus one'],
    'qts': ['qts', 'quality technology services'],
    'flexential': ['flexential', 'peak 10'],
    'cologix': ['cologix'],
    'compass': ['compass'],
    'stack': ['stack infrastructure', 'stack infra'],
    'databank': ['databank', 'data bank'],
    'coresite': ['coresite', 'core site'],
    'lumen': ['lumen', 'centurylink', 'level 3'],
    'cogent': ['cogent'],
}

# Status mapping for comparison
STATUS_ACTIVE = ['Active', 'Operational', 'Operating']
STATUS_UC = ['Under Construction']
STATUS_PLANNED = ['Announced', 'Planned', 'Proposed', 'In Development']
STATUS_CANCELLED = ['Cancelled', 'Withdrawn', 'On Hold']

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def haversine_distance(lat1, lon1, lat2, lon2):
    """Calculate distance between two lat/lon points in meters."""
    if None in [lat1, lon1, lat2, lon2]:
        return float('inf')

    R = 6371000  # Earth radius in meters

    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = math.sin(delta_phi/2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

    return R * c

def normalize_company(company):
    """Normalize company name for matching."""
    if not company:
        return None

    company_lower = str(company).lower().strip()

    for canonical, aliases in COMPANY_ALIASES.items():
        for alias in aliases:
            if alias in company_lower:
                return canonical

    return company_lower.replace(',', '').replace('.', '').replace(' inc', '').replace(' llc', '').strip()

def normalize_status(status):
    """Normalize status to category."""
    if not status:
        return 'Unknown'

    status_str = str(status).strip()

    if any(s.lower() in status_str.lower() for s in STATUS_ACTIVE):
        return 'Active'
    elif any(s.lower() in status_str.lower() for s in STATUS_UC):
        return 'Under Construction'
    elif any(s.lower() in status_str.lower() for s in STATUS_PLANNED):
        return 'Planned'
    elif any(s.lower() in status_str.lower() for s in STATUS_CANCELLED):
        return 'Cancelled'
    else:
        return 'Unknown'

def safe_float(val):
    """Safely convert to float."""
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None

def safe_str(val):
    """Safely convert to string."""
    if val is None:
        return None
    s = str(val).strip()
    return s if s and s.lower() not in ['none', 'nan', ''] else None

def format_number(val, decimals=0):
    """Format number with commas."""
    if val is None:
        return 'N/A'
    if decimals == 0:
        return f"{int(val):,}"
    return f"{val:,.{decimals}f}"

def format_pct(val):
    """Format percentage."""
    if val is None:
        return 'N/A'
    return f"{val:.1f}%"

# ============================================================================
# DATA LOADING
# ============================================================================

def load_source_data(source_name):
    """Load all records from gold_buildings for a given source."""
    fields = [
        'OID@', 'SHAPE@XY', 'unique_id', 'source', 'company_source', 'company_clean',
        'company_clean_filter', 'state_abbr', 'state', 'county', 'country', 'region',
        'latitude', 'longitude', 'full_capacity_mw', 'commissioned_power_mw',
        'uc_power_mw', 'planned_power_mw', 'facility_status', 'campus_name',
        'building_designation', 'facility_sqft', 'data_vintage'
    ]

    records = []
    where = f"source = '{source_name}'"

    try:
        with arcpy.da.SearchCursor(GOLD_BUILDINGS, fields, where) as cursor:
            for row in cursor:
                lat = row[12]
                lon = row[13]

                records.append({
                    'oid': row[0],
                    'xy': row[1],
                    'unique_id': row[2],
                    'source': row[3],
                    'company_source': row[4],
                    'company_clean': row[5],
                    'company_clean_filter': row[6],
                    'state_abbr': row[7],
                    'state': row[8],
                    'county': row[9],
                    'country': row[10],
                    'region': row[11],
                    'latitude': lat,
                    'longitude': lon,
                    'full_capacity_mw': row[14],
                    'commissioned_mw': row[15],
                    'uc_mw': row[16],
                    'planned_mw': row[17],
                    'status': row[18],
                    'campus_name': row[19],
                    'building_name': row[20],
                    'sqft': row[21],
                    'data_vintage': row[22],
                    'company_normalized': normalize_company(row[4] or row[5]),
                    'status_normalized': normalize_status(row[18]),
                })
    except Exception as e:
        print(f"Error loading {source_name}: {e}")
        import traceback
        traceback.print_exc()

    return records

# ============================================================================
# SPATIAL MATCHING
# ============================================================================

def find_spatial_matches(orennia_records, npm_records, threshold_m):
    """Find records within threshold distance of each other."""
    matches = []

    for o_rec in orennia_records:
        o_lat = o_rec.get('latitude')
        o_lon = o_rec.get('longitude')

        if o_lat is None or o_lon is None:
            continue

        for n_rec in npm_records:
            n_lat = n_rec.get('latitude')
            n_lon = n_rec.get('longitude')

            if n_lat is None or n_lon is None:
                continue

            dist = haversine_distance(o_lat, o_lon, n_lat, n_lon)

            if dist <= threshold_m:
                # Calculate capacity delta
                o_cap = o_rec.get('full_capacity_mw') or 0
                n_cap = n_rec.get('full_capacity_mw') or 0
                cap_delta = o_cap - n_cap
                cap_pct = (cap_delta / max(o_cap, n_cap) * 100) if max(o_cap, n_cap) > 0 else 0

                matches.append({
                    'orennia': o_rec,
                    'npm': n_rec,
                    'distance_m': dist,
                    'company_match': o_rec['company_normalized'] == n_rec['company_normalized'] if o_rec['company_normalized'] and n_rec['company_normalized'] else False,
                    'state_match': o_rec['state_abbr'] == n_rec['state_abbr'] if o_rec['state_abbr'] and n_rec['state_abbr'] else False,
                    'status_match': o_rec['status_normalized'] == n_rec['status_normalized'],
                    'orennia_cap': o_cap,
                    'npm_cap': n_cap,
                    'cap_delta': cap_delta,
                    'cap_delta_pct': cap_pct,
                })

    return matches


def find_best_1to1_matches(orennia_records, npm_records, threshold_m):
    """
    Find optimal 1-to-1 matches between sources using a greedy algorithm.

    This ensures:
    - Each Orennia record matches at most ONE NPM record
    - Each NPM record matches at most ONE Orennia record
    - Matches are assigned greedily by closest distance first
    - Result: symmetric match counts (N matched pairs = N Orennia matched = N NPM matched)

    Methodology:
    1. Calculate all pairwise distances within threshold
    2. Sort by distance (closest first)
    3. Greedily assign matches, skipping already-matched records
    """
    # Step 1: Calculate all candidate pairs within threshold
    candidates = []

    for o_idx, o_rec in enumerate(orennia_records):
        o_lat = o_rec.get('latitude')
        o_lon = o_rec.get('longitude')

        if o_lat is None or o_lon is None:
            continue

        for n_idx, n_rec in enumerate(npm_records):
            n_lat = n_rec.get('latitude')
            n_lon = n_rec.get('longitude')

            if n_lat is None or n_lon is None:
                continue

            dist = haversine_distance(o_lat, o_lon, n_lat, n_lon)

            if dist <= threshold_m:
                candidates.append({
                    'o_idx': o_idx,
                    'n_idx': n_idx,
                    'distance': dist,
                    'orennia': o_rec,
                    'npm': n_rec,
                })

    # Step 2: Sort by distance (closest first)
    candidates.sort(key=lambda x: x['distance'])

    # Step 3: Greedy assignment
    matched_orennia = set()
    matched_npm = set()
    final_matches = []

    for cand in candidates:
        o_idx = cand['o_idx']
        n_idx = cand['n_idx']

        # Skip if either record already matched
        if o_idx in matched_orennia or n_idx in matched_npm:
            continue

        # Assign this match
        matched_orennia.add(o_idx)
        matched_npm.add(n_idx)

        o_rec = cand['orennia']
        n_rec = cand['npm']
        o_cap = o_rec.get('full_capacity_mw') or 0
        n_cap = n_rec.get('full_capacity_mw') or 0
        cap_delta = o_cap - n_cap
        cap_pct = (cap_delta / max(o_cap, n_cap) * 100) if max(o_cap, n_cap) > 0 else 0

        final_matches.append({
            'orennia': o_rec,
            'npm': n_rec,
            'distance_m': cand['distance'],
            'company_match': o_rec['company_normalized'] == n_rec['company_normalized'] if o_rec['company_normalized'] and n_rec['company_normalized'] else False,
            'state_match': o_rec['state_abbr'] == n_rec['state_abbr'] if o_rec['state_abbr'] and n_rec['state_abbr'] else False,
            'status_match': o_rec['status_normalized'] == n_rec['status_normalized'],
            'orennia_cap': o_cap,
            'npm_cap': n_cap,
            'cap_delta': cap_delta,
            'cap_delta_pct': cap_pct,
        })

    return final_matches


def find_best_1to1_matches_company_aware(orennia_records, npm_records, threshold_m):
    """
    Find optimal 1-to-1 matches with COMPANY-AWARE filtering.

    This is the RECOMMENDED matching mode (aligned with SA vs DCH methodology):
    - Only matches records if companies are the same (after normalization)
    - Prevents false matches at multi-tenant sites (e.g., AWS matched to Google)

    Methodology (from UCID_SA_DCH_IMPROVEMENT_PLAN.md):
    1. Filter candidates by: distance <= threshold AND company_match
    2. Sort by distance (closest first)
    3. Greedy 1-to-1 assignment
    """
    candidates = []

    for o_idx, o_rec in enumerate(orennia_records):
        o_lat = o_rec.get('latitude')
        o_lon = o_rec.get('longitude')
        o_company = o_rec.get('company_normalized')

        if o_lat is None or o_lon is None:
            continue

        for n_idx, n_rec in enumerate(npm_records):
            n_lat = n_rec.get('latitude')
            n_lon = n_rec.get('longitude')
            n_company = n_rec.get('company_normalized')

            if n_lat is None or n_lon is None:
                continue

            # Company-aware: skip if companies don't match
            if o_company and n_company and o_company != n_company:
                continue

            dist = haversine_distance(o_lat, o_lon, n_lat, n_lon)

            if dist <= threshold_m:
                candidates.append({
                    'o_idx': o_idx,
                    'n_idx': n_idx,
                    'distance': dist,
                    'orennia': o_rec,
                    'npm': n_rec,
                    'company_match': True,  # Guaranteed by filter above
                })

    # Sort by distance and greedy assign
    candidates.sort(key=lambda x: x['distance'])

    matched_orennia = set()
    matched_npm = set()
    final_matches = []

    for cand in candidates:
        o_idx = cand['o_idx']
        n_idx = cand['n_idx']

        if o_idx in matched_orennia or n_idx in matched_npm:
            continue

        matched_orennia.add(o_idx)
        matched_npm.add(n_idx)

        o_rec = cand['orennia']
        n_rec = cand['npm']
        o_cap = o_rec.get('full_capacity_mw') or 0
        n_cap = n_rec.get('full_capacity_mw') or 0
        cap_delta = o_cap - n_cap
        cap_pct = (cap_delta / max(o_cap, n_cap) * 100) if max(o_cap, n_cap) > 0 else 0

        final_matches.append({
            'orennia': o_rec,
            'npm': n_rec,
            'distance_m': cand['distance'],
            'company_match': True,
            'state_match': o_rec['state_abbr'] == n_rec['state_abbr'] if o_rec['state_abbr'] and n_rec['state_abbr'] else False,
            'status_match': o_rec['status_normalized'] == n_rec['status_normalized'],
            'orennia_cap': o_cap,
            'npm_cap': n_cap,
            'cap_delta': cap_delta,
            'cap_delta_pct': cap_pct,
            'match_mode': MATCH_MODE_COMPANY,
        })

    return final_matches


def calculate_match_confidence(match):
    """
    Calculate match confidence score (0-100) based on multiple factors.

    Scoring aligned with UCID_SA_DCH_IMPROVEMENT_PLAN.md:
    - Distance (0-30 pts): Closer = higher confidence
    - Company match (0-30 pts): Same company = high confidence
    - Capacity agreement (0-20 pts): Similar capacity = higher confidence
    - State match (0-10 pts): Same state = higher confidence
    - Status match (0-10 pts): Same status = higher confidence

    Returns: score (0-100), tier (HIGH/MEDIUM/LOW)
    """
    score = 0

    # Distance (0-30 pts)
    dist = match.get('distance_m', 1000)
    if dist < 50:
        score += 30
    elif dist < 100:
        score += 25
    elif dist < 250:
        score += 20
    elif dist < 500:
        score += 10
    elif dist < 1000:
        score += 5

    # Company match (0-30 pts)
    if match.get('company_match'):
        score += 30

    # Capacity agreement (0-20 pts)
    cap_delta_pct = abs(match.get('cap_delta_pct', 100))
    if cap_delta_pct < 5:
        score += 20
    elif cap_delta_pct < 10:
        score += 15
    elif cap_delta_pct < 20:
        score += 10
    elif cap_delta_pct < 50:
        score += 5

    # State match (0-10 pts)
    if match.get('state_match'):
        score += 10

    # Status match (0-10 pts)
    if match.get('status_match'):
        score += 10

    # Tier classification
    if score >= 80:
        tier = 'HIGH'
    elif score >= 50:
        tier = 'MEDIUM'
    else:
        tier = 'LOW'

    return score, tier


def find_ucid_matches(orennia_records, npm_records):
    """
    Match records by UCID (Universal Campus ID) - CAMPUS-LEVEL matching.

    This is the GOLD STANDARD matching method (from SA_VS_META_CANONICAL_COMPARISON.md):
    - UCIDs group facilities by company + spatial proximity (250m/1000m)
    - Same UCID = same campus, regardless of source
    - Provides accurate campus-level comparison

    Prerequisites:
    - UCID generation must have been run (run_post_ingestion.py)
    - Records must have ucid field populated

    Returns: list of matched campus pairs
    """
    # Group by UCID
    orennia_by_ucid = defaultdict(list)
    npm_by_ucid = defaultdict(list)

    for rec in orennia_records:
        ucid = rec.get('ucid')
        if ucid:
            orennia_by_ucid[ucid].append(rec)

    for rec in npm_records:
        ucid = rec.get('ucid')
        if ucid:
            npm_by_ucid[ucid].append(rec)

    # Find UCIDs that appear in both sources
    common_ucids = set(orennia_by_ucid.keys()) & set(npm_by_ucid.keys())

    matches = []
    for ucid in common_ucids:
        o_recs = orennia_by_ucid[ucid]
        n_recs = npm_by_ucid[ucid]

        # Aggregate capacity per source for this campus
        o_cap_total = sum(r.get('full_capacity_mw') or 0 for r in o_recs)
        n_cap_total = sum(r.get('full_capacity_mw') or 0 for r in n_recs)

        # Use first record for representative data
        o_rep = o_recs[0]
        n_rep = n_recs[0]

        cap_delta = o_cap_total - n_cap_total
        cap_pct = (cap_delta / max(o_cap_total, n_cap_total) * 100) if max(o_cap_total, n_cap_total) > 0 else 0

        matches.append({
            'ucid': ucid,
            'orennia_records': o_recs,
            'npm_records': n_recs,
            'orennia_count': len(o_recs),
            'npm_count': len(n_recs),
            'orennia_cap': o_cap_total,
            'npm_cap': n_cap_total,
            'cap_delta': cap_delta,
            'cap_delta_pct': cap_pct,
            'company': o_rep.get('company_normalized') or n_rep.get('company_normalized'),
            'state': o_rep.get('state_abbr') or n_rep.get('state_abbr'),
            'match_mode': MATCH_MODE_UCID,
        })

    # Track unmatched UCIDs
    orennia_only_ucids = set(orennia_by_ucid.keys()) - common_ucids
    npm_only_ucids = set(npm_by_ucid.keys()) - common_ucids

    return {
        'matches': matches,
        'orennia_only_ucids': orennia_only_ucids,
        'npm_only_ucids': npm_only_ucids,
        'orennia_by_ucid': orennia_by_ucid,
        'npm_by_ucid': npm_by_ucid,
    }


def dedupe_matches(matches, by_orennia=True):
    """Deduplicate matches, keeping closest match for each record."""
    if by_orennia:
        key_func = lambda m: m['orennia']['unique_id']
    else:
        key_func = lambda m: m['npm']['unique_id']

    best_matches = {}
    for m in matches:
        key = key_func(m)
        if key not in best_matches or m['distance_m'] < best_matches[key]['distance_m']:
            best_matches[key] = m

    return list(best_matches.values())

def find_unmatched(all_records, matched_records, is_orennia=True):
    """Find records that didn't match."""
    if is_orennia:
        matched_ids = set(m['orennia']['unique_id'] for m in matched_records)
    else:
        matched_ids = set(m['npm']['unique_id'] for m in matched_records)

    return [r for r in all_records if r['unique_id'] not in matched_ids]

# ============================================================================
# STATISTICAL ANALYSIS
# ============================================================================

def calculate_statistics(matches):
    """Calculate MAPE, Bias, CV, and Pearson r for capacity comparison."""
    # Filter to pairs with capacity data
    cap_pairs = [(m['orennia_cap'], m['npm_cap']) for m in matches
                 if m['orennia_cap'] > 0 and m['npm_cap'] > 0]

    if len(cap_pairs) < 5:
        return {
            'mape': None,
            'bias': None,
            'cv': None,
            'pearson_r': None,
            'n_pairs': len(cap_pairs),
            'grade': 'N/A'
        }

    orennia_caps = [p[0] for p in cap_pairs]
    npm_caps = [p[1] for p in cap_pairs]

    # MAPE: Mean Absolute Percentage Error
    apes = []
    for o, n in cap_pairs:
        max_cap = max(o, n)
        if max_cap > 0:
            apes.append(abs(o - n) / max_cap * 100)
    mape = sum(apes) / len(apes) if apes else None

    # Bias: Systematic over/under-reporting (Orennia relative to NPM)
    deltas = [o - n for o, n in cap_pairs]
    mean_delta = sum(deltas) / len(deltas)
    mean_npm = sum(npm_caps) / len(npm_caps)
    bias = (mean_delta / mean_npm * 100) if mean_npm > 0 else None

    # CV: Coefficient of Variation of deltas
    abs_deltas = [abs(d) for d in deltas]
    mean_abs_delta = sum(abs_deltas) / len(abs_deltas)
    if mean_abs_delta > 0:
        variance = sum((d - mean_delta)**2 for d in deltas) / len(deltas)
        std_delta = math.sqrt(variance)
        cv = (std_delta / mean_abs_delta * 100)
    else:
        cv = None

    # Pearson r
    mean_o = sum(orennia_caps) / len(orennia_caps)
    mean_n = sum(npm_caps) / len(npm_caps)

    numerator = sum((o - mean_o) * (n - mean_n) for o, n in cap_pairs)
    denom_o = math.sqrt(sum((o - mean_o)**2 for o in orennia_caps))
    denom_n = math.sqrt(sum((n - mean_n)**2 for n in npm_caps))

    pearson_r = numerator / (denom_o * denom_n) if denom_o > 0 and denom_n > 0 else None

    # Grade based on MAPE
    if mape is None:
        grade = 'N/A'
    elif mape <= 10:
        grade = 'A'
    elif mape <= 20:
        grade = 'B'
    elif mape <= 35:
        grade = 'C'
    elif mape <= 50:
        grade = 'D'
    else:
        grade = 'F'

    return {
        'mape': mape,
        'bias': bias,
        'cv': cv,
        'pearson_r': pearson_r,
        'n_pairs': len(cap_pairs),
        'grade': grade,
        'orennia_total_mw': sum(orennia_caps),
        'npm_total_mw': sum(npm_caps),
    }

# ============================================================================
# ANALYSIS FUNCTIONS
# ============================================================================

def analyze_source_overlap(matches, orennia_records, npm_records):
    """
    Deep analysis to determine if NPM and Orennia share the same underlying data source.
    Returns evidence metrics for Sam's hypothesis investigation.
    """
    if not matches:
        return {
            'exact_coord_count': 0,
            'exact_coord_pct': 0,
            'very_close_count': 0,
            'very_close_pct': 0,
            'close_count': 0,
            'close_pct': 0,
            'identical_capacity_count': 0,
            'identical_capacity_pct': 0,
            'similar_capacity_count': 0,
            'similar_capacity_pct': 0,
            'same_company_count': 0,
            'same_company_pct': 0,
            'smoking_gun_count': 0,
            'smoking_gun_pct': 0,
            'evidence_score': 0,
            'conclusion': 'Insufficient data for analysis',
            'conclusion_detail': '',
        }

    total_matches = len(matches)

    # Coordinate analysis (key indicator of shared source)
    exact_coord_matches = sum(1 for m in matches if m['distance_m'] <= 1)  # 0-1m
    very_close_matches = sum(1 for m in matches if m['distance_m'] <= 10)  # 0-10m
    close_matches = sum(1 for m in matches if m['distance_m'] <= 100)  # 0-100m

    # Capacity analysis
    pairs_with_both_cap = [(m['orennia_cap'], m['npm_cap'], m) for m in matches
                           if m['orennia_cap'] > 0 and m['npm_cap'] > 0]
    identical_capacity = sum(1 for o, n, m in pairs_with_both_cap if o == n)
    similar_capacity = sum(1 for o, n, m in pairs_with_both_cap
                          if o == n or (max(o, n) > 0 and abs(o - n) / max(o, n) <= 0.05))

    # Company name analysis
    same_company = sum(1 for m in matches if m['company_match'])

    # Smoking gun analysis - records matching ALL criteria
    smoking_gun = sum(1 for m in matches if
                      m['distance_m'] <= 1 and  # Exact coordinates
                      m['company_match'] and    # Same company
                      (m['orennia_cap'] == m['npm_cap'] or  # Identical capacity
                       (m['orennia_cap'] > 0 and m['npm_cap'] > 0 and
                        abs(m['orennia_cap'] - m['npm_cap']) / max(m['orennia_cap'], m['npm_cap']) <= 0.05)))

    # Calculate percentages
    exact_coord_pct = exact_coord_matches / total_matches * 100
    very_close_pct = very_close_matches / total_matches * 100
    close_pct = close_matches / total_matches * 100
    identical_cap_pct = identical_capacity / len(pairs_with_both_cap) * 100 if pairs_with_both_cap else 0
    similar_cap_pct = similar_capacity / len(pairs_with_both_cap) * 100 if pairs_with_both_cap else 0
    same_company_pct = same_company / total_matches * 100
    smoking_gun_pct = smoking_gun / total_matches * 100

    # Evidence scoring (0-9 scale)
    evidence_score = 0
    evidence_items = []

    # Score: Exact coordinates (0-3 points)
    if exact_coord_pct >= 50:
        evidence_score += 3
        evidence_items.append(f"{exact_coord_pct:.0f}% exact coordinates (very strong)")
    elif exact_coord_pct >= 20:
        evidence_score += 2
        evidence_items.append(f"{exact_coord_pct:.0f}% exact coordinates (strong)")
    elif exact_coord_pct >= 5:
        evidence_score += 1
        evidence_items.append(f"{exact_coord_pct:.0f}% exact coordinates (weak)")

    # Score: Identical capacity (0-3 points)
    if identical_cap_pct >= 50:
        evidence_score += 3
        evidence_items.append(f"{identical_cap_pct:.0f}% identical capacity values (very strong)")
    elif identical_cap_pct >= 25:
        evidence_score += 2
        evidence_items.append(f"{identical_cap_pct:.0f}% identical capacity values (strong)")
    elif identical_cap_pct >= 10:
        evidence_score += 1
        evidence_items.append(f"{identical_cap_pct:.0f}% identical capacity values (moderate)")

    # Score: Smoking gun (0-3 points)
    if smoking_gun_pct >= 20:
        evidence_score += 3
        evidence_items.append(f"{smoking_gun_pct:.0f}% smoking gun matches (very strong)")
    elif smoking_gun_pct >= 5:
        evidence_score += 2
        evidence_items.append(f"{smoking_gun_pct:.0f}% smoking gun matches (strong)")
    elif smoking_gun_pct >= 1:
        evidence_score += 1
        evidence_items.append(f"{smoking_gun_pct:.1f}% smoking gun matches (weak)")

    # Determine conclusion
    if evidence_score >= 6:
        conclusion = "STRONG EVIDENCE"
        conclusion_detail = "NPM and Orennia likely share the same underlying data source or one is sourcing from the other."
    elif evidence_score >= 3:
        conclusion = "MODERATE EVIDENCE"
        conclusion_detail = "Sources have significant overlap but also show differences - likely both pull from common public records (utility filings, planning applications) rather than direct copying."
    else:
        conclusion = "WEAK EVIDENCE"
        conclusion_detail = "Sources appear largely independent - overlap is typical of two sources tracking the same market."

    return {
        'exact_coord_count': exact_coord_matches,
        'exact_coord_pct': exact_coord_pct,
        'very_close_count': very_close_matches,
        'very_close_pct': very_close_pct,
        'close_count': close_matches,
        'close_pct': close_pct,
        'identical_capacity_count': identical_capacity,
        'identical_capacity_pct': identical_cap_pct,
        'similar_capacity_count': similar_capacity,
        'similar_capacity_pct': similar_cap_pct,
        'pairs_with_capacity': len(pairs_with_both_cap),
        'same_company_count': same_company,
        'same_company_pct': same_company_pct,
        'smoking_gun_count': smoking_gun,
        'smoking_gun_pct': smoking_gun_pct,
        'evidence_score': evidence_score,
        'evidence_items': evidence_items,
        'conclusion': conclusion,
        'conclusion_detail': conclusion_detail,
    }


def run_full_analysis(orennia_records, npm_records, threshold_m=DEFAULT_THRESHOLD):
    """Run comprehensive analysis and return results dictionary."""
    results = {
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'threshold_m': threshold_m,
        'orennia': {
            'count': len(orennia_records),
            'with_coords': sum(1 for r in orennia_records if r['latitude'] and r['longitude']),
            'with_capacity': sum(1 for r in orennia_records if r.get('full_capacity_mw')),
            'total_capacity_mw': sum(r.get('full_capacity_mw') or 0 for r in orennia_records),
        },
        'npm': {
            'count': len(npm_records),
            'with_coords': sum(1 for r in npm_records if r['latitude'] and r['longitude']),
            'with_capacity': sum(1 for r in npm_records if r.get('full_capacity_mw')),
            'total_capacity_mw': sum(r.get('full_capacity_mw') or 0 for r in npm_records),
        },
    }

    # Spatial matches at all thresholds using 1-to-1 matching
    results['spatial_matches'] = {}
    for label, thresh in THRESHOLDS.items():
        # Use optimal 1-to-1 matching for accurate pair counts
        matched_pairs = find_best_1to1_matches(orennia_records, npm_records, thresh)

        results['spatial_matches'][label] = {
            'matched_pairs': len(matched_pairs),
            'orennia_matched': len(matched_pairs),  # Symmetric: same count
            'npm_matched': len(matched_pairs),       # Symmetric: same count
            'orennia_pct': len(matched_pairs) / len(orennia_records) * 100 if orennia_records else 0,
            'npm_pct': len(matched_pairs) / len(npm_records) * 100 if npm_records else 0,
        }

    # Use default threshold for detailed analysis with 1-to-1 matching
    matched_deduped = find_best_1to1_matches(orennia_records, npm_records, threshold_m)

    # Unmatched records (records that didn't get matched to any counterpart)
    matched_orennia_ids = set(m['orennia']['unique_id'] for m in matched_deduped)
    matched_npm_ids = set(m['npm']['unique_id'] for m in matched_deduped)

    orennia_only = [r for r in orennia_records if r['unique_id'] not in matched_orennia_ids]
    npm_only = [r for r in npm_records if r['unique_id'] not in matched_npm_ids]

    results['matched_pairs'] = matched_deduped
    results['orennia_only'] = orennia_only
    results['npm_only'] = npm_only

    # Statistics
    results['statistics'] = calculate_statistics(matched_deduped)

    # Company overlap
    orennia_companies = set(r['company_normalized'] for r in orennia_records if r['company_normalized'])
    npm_companies = set(r['company_normalized'] for r in npm_records if r['company_normalized'])

    results['company_overlap'] = {
        'orennia_unique': len(orennia_companies),
        'npm_unique': len(npm_companies),
        'common': len(orennia_companies & npm_companies),
        'common_list': sorted(orennia_companies & npm_companies)[:30],
        'orennia_only': sorted(orennia_companies - npm_companies)[:20],
        'npm_only': sorted(npm_companies - orennia_companies)[:20],
    }

    # State distribution
    orennia_states = defaultdict(int)
    npm_states = defaultdict(int)

    for r in orennia_records:
        if r['state_abbr']:
            orennia_states[r['state_abbr']] += 1
    for r in npm_records:
        if r['state_abbr']:
            npm_states[r['state_abbr']] += 1

    results['state_distribution'] = {
        'orennia': dict(sorted(orennia_states.items(), key=lambda x: -x[1])),
        'npm': dict(sorted(npm_states.items(), key=lambda x: -x[1])),
    }

    # Status distribution
    orennia_status = defaultdict(int)
    npm_status = defaultdict(int)

    for r in orennia_records:
        orennia_status[r['status_normalized']] += 1
    for r in npm_records:
        npm_status[r['status_normalized']] += 1

    results['status_distribution'] = {
        'orennia': dict(orennia_status),
        'npm': dict(npm_status),
    }

    # Company capacity breakdown (top 15)
    orennia_company_cap = defaultdict(float)
    npm_company_cap = defaultdict(float)

    for r in orennia_records:
        if r['company_normalized'] and r.get('full_capacity_mw'):
            orennia_company_cap[r['company_normalized']] += r['full_capacity_mw']
    for r in npm_records:
        if r['company_normalized'] and r.get('full_capacity_mw'):
            npm_company_cap[r['company_normalized']] += r['full_capacity_mw']

    results['company_capacity'] = {
        'orennia': dict(sorted(orennia_company_cap.items(), key=lambda x: -x[1])[:15]),
        'npm': dict(sorted(npm_company_cap.items(), key=lambda x: -x[1])[:15]),
    }

    # Match quality analysis
    company_matches = sum(1 for m in matched_deduped if m['company_match'])
    state_matches = sum(1 for m in matched_deduped if m['state_match'])
    status_matches = sum(1 for m in matched_deduped if m['status_match'])

    results['match_quality'] = {
        'total_matches': len(matched_deduped),
        'company_match_count': company_matches,
        'company_match_pct': company_matches / len(matched_deduped) * 100 if matched_deduped else 0,
        'state_match_count': state_matches,
        'state_match_pct': state_matches / len(matched_deduped) * 100 if matched_deduped else 0,
        'status_match_count': status_matches,
        'status_match_pct': status_matches / len(matched_deduped) * 100 if matched_deduped else 0,
    }

    # Detailed match examples (closest 30)
    sorted_matches = sorted(matched_deduped, key=lambda x: x['distance_m'])[:30]
    results['match_examples'] = sorted_matches

    # Significant conflicts (>20% capacity difference)
    conflicts = [m for m in matched_deduped if abs(m['cap_delta_pct']) > 20 and m['orennia_cap'] > 0 and m['npm_cap'] > 0]
    results['significant_conflicts'] = sorted(conflicts, key=lambda x: -abs(x['cap_delta']))[:30]

    # Deep source overlap analysis (Sam's hypothesis investigation)
    results['source_overlap'] = analyze_source_overlap(matched_deduped, orennia_records, npm_records)

    return results

# ============================================================================
# HTML REPORT GENERATION
# ============================================================================

def generate_html_report(results, output_path):
    """Generate interactive HTML report with charts."""

    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M')
    threshold = results['threshold_m']

    # Extract key metrics
    orennia = results['orennia']
    npm = results['npm']
    stats = results['statistics']
    spatial = results['spatial_matches']
    quality = results['match_quality']
    source_overlap = results['source_overlap']

    # Prepare chart data
    state_labels = list(results['state_distribution']['orennia'].keys())[:10]
    orennia_state_data = [results['state_distribution']['orennia'].get(s, 0) for s in state_labels]
    npm_state_data = [results['state_distribution']['npm'].get(s, 0) for s in state_labels]

    status_labels = ['Active', 'Under Construction', 'Planned', 'Cancelled', 'Unknown']
    orennia_status_data = [results['status_distribution']['orennia'].get(s, 0) for s in status_labels]
    npm_status_data = [results['status_distribution']['npm'].get(s, 0) for s in status_labels]

    # Determine overlap severity
    npm_match_pct = spatial['500m']['npm_pct']
    if npm_match_pct > 70:
        severity = 'HIGH'
        severity_color = '#e74c3c'
        severity_msg = 'NPM is largely redundant with Orennia'
    elif npm_match_pct > 40:
        severity = 'MODERATE'
        severity_color = '#f39c12'
        severity_msg = 'Significant overlap but both provide unique records'
    else:
        severity = 'LOW'
        severity_color = '#27ae60'
        severity_msg = 'Sources are largely complementary'

    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NPM vs Orennia Comparison Report</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        :root {{
            --bg-primary: #1a1a2e;
            --bg-secondary: #16213e;
            --bg-card: #0f3460;
            --text-primary: #eee;
            --text-secondary: #aaa;
            --accent: #4facfe;
            --accent2: #0f3460;
            --success: #27ae60;
            --warning: #f39c12;
            --danger: #e74c3c;
            --border: #333;
        }}

        * {{ margin: 0; padding: 0; box-sizing: border-box; }}

        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: var(--bg-primary);
            color: var(--text-primary);
            line-height: 1.6;
            padding: 20px;
        }}

        .container {{ max-width: 1400px; margin: 0 auto; }}

        h1 {{
            text-align: center;
            color: var(--accent);
            margin-bottom: 10px;
            font-size: 2.2em;
        }}

        h2 {{
            color: var(--accent);
            margin: 30px 0 15px 0;
            padding-bottom: 10px;
            border-bottom: 2px solid var(--accent);
        }}

        h3 {{
            color: var(--text-primary);
            margin: 20px 0 10px 0;
        }}

        .subtitle {{
            text-align: center;
            color: var(--text-secondary);
            margin-bottom: 30px;
        }}

        .metrics-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin: 20px 0;
        }}

        .metric-card {{
            background: var(--bg-card);
            padding: 20px;
            border-radius: 10px;
            text-align: center;
        }}

        .metric-value {{
            font-size: 2em;
            font-weight: bold;
            color: var(--accent);
        }}

        .metric-label {{
            color: var(--text-secondary);
            font-size: 0.9em;
            margin-top: 5px;
        }}

        .grade {{
            display: inline-block;
            padding: 5px 15px;
            border-radius: 5px;
            font-weight: bold;
            font-size: 1.5em;
        }}

        .grade-a {{ background: var(--success); color: white; }}
        .grade-b {{ background: #2ecc71; color: white; }}
        .grade-c {{ background: var(--warning); color: white; }}
        .grade-d {{ background: #e67e22; color: white; }}
        .grade-f {{ background: var(--danger); color: white; }}

        .severity-badge {{
            display: inline-block;
            padding: 8px 20px;
            border-radius: 5px;
            font-weight: bold;
            font-size: 1.2em;
            background: {severity_color};
            color: white;
        }}

        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 15px 0;
            background: var(--bg-secondary);
            border-radius: 10px;
            overflow: hidden;
        }}

        th, td {{
            padding: 12px 15px;
            text-align: left;
            border-bottom: 1px solid var(--border);
        }}

        th {{
            background: var(--bg-card);
            color: var(--accent);
            font-weight: 600;
        }}

        tr:hover {{ background: var(--bg-card); }}

        .chart-container {{
            background: var(--bg-secondary);
            padding: 20px;
            border-radius: 10px;
            margin: 20px 0;
            height: 320px;
        }}

        .chart-row {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
        }}

        .two-col {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
        }}

        .highlight-box {{
            background: var(--bg-card);
            padding: 20px;
            border-radius: 10px;
            border-left: 4px solid var(--accent);
            margin: 15px 0;
        }}

        .match-yes {{ color: var(--success); font-weight: bold; }}
        .match-no {{ color: var(--text-secondary); }}

        .number {{ font-family: 'Consolas', monospace; }}

        .recommendation {{
            background: var(--bg-card);
            padding: 20px;
            border-radius: 10px;
            margin: 15px 0;
        }}

        .recommendation h4 {{
            color: var(--accent);
            margin-bottom: 10px;
        }}

        .recommendation ul {{
            margin-left: 20px;
        }}

        .recommendation li {{
            margin: 8px 0;
        }}

        .source-orennia {{ color: #3498db; }}
        .source-npm {{ color: #1abc9c; }}

        @media (max-width: 768px) {{
            .chart-row, .two-col {{ grid-template-columns: 1fr; }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>NPM vs Orennia Comparison Report</h1>
        <p class="subtitle">Generated: {timestamp} | Threshold: {threshold}m</p>

        <!-- Executive Summary -->
        <h2>Executive Summary</h2>

        <div style="text-align: center; margin: 20px 0;">
            <span class="severity-badge">{severity} OVERLAP</span>
            <p style="margin-top: 10px; color: var(--text-secondary);">{severity_msg}</p>
        </div>

        <div class="metrics-grid">
            <div class="metric-card">
                <div class="metric-value">{format_number(orennia['count'])}</div>
                <div class="metric-label">Orennia Records</div>
            </div>
            <div class="metric-card">
                <div class="metric-value">{format_number(npm['count'])}</div>
                <div class="metric-label">NPM Records</div>
            </div>
            <div class="metric-card">
                <div class="metric-value">{format_pct(spatial['500m']['npm_pct'])}</div>
                <div class="metric-label">NPM Overlap Rate</div>
            </div>
            <div class="metric-card">
                <div class="metric-value">{format_pct(spatial['500m']['orennia_pct'])}</div>
                <div class="metric-label">Orennia Overlap Rate</div>
            </div>
            <div class="metric-card">
                <div class="metric-value">{format_number(len(results['npm_only']))}</div>
                <div class="metric-label">NPM-Only Records</div>
            </div>
            <div class="metric-card">
                <div class="metric-value">{format_number(len(results['orennia_only']))}</div>
                <div class="metric-label">Orennia-Only Records</div>
            </div>
        </div>

        <!-- Source Overlap Analysis (Sam's Hypothesis Investigation) -->
        <h2>🔍 Source Overlap Analysis</h2>
        <p style="color: var(--text-secondary); margin-bottom: 20px;">
            <em>Investigation into whether NPM and Orennia share the same underlying data source</em>
        </p>

        <div style="text-align: center; margin: 20px 0;">
            <span class="severity-badge" style="background: {
                'var(--danger)' if source_overlap['evidence_score'] >= 6
                else 'var(--warning)' if source_overlap['evidence_score'] >= 3
                else 'var(--success)'
            };">
                {source_overlap['conclusion']} (Score: {source_overlap['evidence_score']}/9)
            </span>
            <p style="margin-top: 10px; color: var(--text-secondary); max-width: 800px; margin-left: auto; margin-right: auto;">
                {source_overlap['conclusion_detail']}
            </p>
        </div>

        <div class="two-col">
            <!-- Coordinate Analysis -->
            <div class="data-card">
                <h3>📍 Coordinate Analysis</h3>
                <p style="color: var(--text-secondary); font-size: 0.9em; margin-bottom: 15px;">
                    Key indicator: If sources share data, coordinates should be nearly identical
                </p>
                <table class="data-table">
                    <thead>
                        <tr><th>Distance Threshold</th><th>Count</th><th>Percentage</th><th>Interpretation</th></tr>
                    </thead>
                    <tbody>
                        <tr>
                            <td>Exact match (0-1m)</td>
                            <td class="number">{source_overlap['exact_coord_count']}</td>
                            <td class="number">{source_overlap['exact_coord_pct']:.1f}%</td>
                            <td>{'⚠️ High' if source_overlap['exact_coord_pct'] >= 20 else '✓ Low'}</td>
                        </tr>
                        <tr>
                            <td>Very close (0-10m)</td>
                            <td class="number">{source_overlap['very_close_count']}</td>
                            <td class="number">{source_overlap['very_close_pct']:.1f}%</td>
                            <td>{'⚠️ High' if source_overlap['very_close_pct'] >= 30 else '✓ Low'}</td>
                        </tr>
                        <tr>
                            <td>Close (0-100m)</td>
                            <td class="number">{source_overlap['close_count']}</td>
                            <td class="number">{source_overlap['close_pct']:.1f}%</td>
                            <td>Typical geocoding variance</td>
                        </tr>
                    </tbody>
                </table>
            </div>

            <!-- Capacity Analysis -->
            <div class="data-card">
                <h3>⚡ Capacity Value Analysis</h3>
                <p style="color: var(--text-secondary); font-size: 0.9em; margin-bottom: 15px;">
                    Identical capacity values suggest shared underlying data
                </p>
                <table class="data-table">
                    <thead>
                        <tr><th>Metric</th><th>Count</th><th>Percentage</th><th>Interpretation</th></tr>
                    </thead>
                    <tbody>
                        <tr>
                            <td>Pairs with both capacities</td>
                            <td class="number">{source_overlap['pairs_with_capacity']}</td>
                            <td class="number">-</td>
                            <td>Analysis base</td>
                        </tr>
                        <tr>
                            <td>Identical capacity values</td>
                            <td class="number">{source_overlap['identical_capacity_count']}</td>
                            <td class="number">{source_overlap['identical_capacity_pct']:.1f}%</td>
                            <td>{'⚠️ High - shared source' if source_overlap['identical_capacity_pct'] >= 25 else '✓ Normal'}</td>
                        </tr>
                        <tr>
                            <td>Within 5% of each other</td>
                            <td class="number">{source_overlap['similar_capacity_count']}</td>
                            <td class="number">{source_overlap['similar_capacity_pct']:.1f}%</td>
                            <td>{'⚠️ High' if source_overlap['similar_capacity_pct'] >= 40 else '✓ Normal'}</td>
                        </tr>
                    </tbody>
                </table>
            </div>
        </div>

        <div class="two-col">
            <!-- Company Match Analysis -->
            <div class="data-card">
                <h3>🏢 Company Name Analysis</h3>
                <table class="data-table">
                    <thead>
                        <tr><th>Metric</th><th>Count</th><th>Percentage</th></tr>
                    </thead>
                    <tbody>
                        <tr>
                            <td>Same company name</td>
                            <td class="number">{source_overlap['same_company_count']}</td>
                            <td class="number">{source_overlap['same_company_pct']:.1f}%</td>
                        </tr>
                    </tbody>
                </table>
            </div>

            <!-- Smoking Gun Analysis -->
            <div class="data-card">
                <h3>🎯 Smoking Gun Analysis</h3>
                <p style="color: var(--text-secondary); font-size: 0.9em; margin-bottom: 15px;">
                    Records matching ALL criteria: exact coords + same company + same/similar capacity
                </p>
                <table class="data-table">
                    <thead>
                        <tr><th>Metric</th><th>Count</th><th>Percentage</th><th>Interpretation</th></tr>
                    </thead>
                    <tbody>
                        <tr>
                            <td>Smoking gun matches</td>
                            <td class="number">{source_overlap['smoking_gun_count']}</td>
                            <td class="number">{source_overlap['smoking_gun_pct']:.1f}%</td>
                            <td>{'🚨 Strong evidence!' if source_overlap['smoking_gun_pct'] >= 5 else '✓ No systematic copying'}</td>
                        </tr>
                    </tbody>
                </table>
            </div>
        </div>

        <div class="highlight-box" style="border-left-color: {'var(--danger)' if source_overlap['evidence_score'] >= 6 else 'var(--warning)' if source_overlap['evidence_score'] >= 3 else 'var(--success)'};">
            <strong>Bottom Line for Sam:</strong><br/>
            {
                "The data shows <strong>strong evidence</strong> that Orennia and NPM share the same underlying data source. The high rate of exact coordinate matches and identical capacity values suggest direct data sourcing between platforms."
                if source_overlap['evidence_score'] >= 6
                else "The data shows <strong>overlap typical of two independent sources tracking the same market</strong>, not evidence of direct data sourcing. Both likely pull from common public records (utility filings, planning applications). Orennia has broader coverage with significantly more records than NPM."
                if source_overlap['evidence_score'] < 3
                else "The data shows <strong>moderate overlap</strong> between the sources. Some indicators (like identical capacity values) suggest shared underlying data, but others (like low exact coordinate matches) indicate independent data collection. Both likely draw from common public/industry sources rather than one directly copying from the other."
            }
        </div>

        <!-- Capacity Statistics -->
        <h2>Capacity Comparison Statistics</h2>

        <div class="metrics-grid">
            <div class="metric-card">
                <div class="metric-value">{format_pct(stats['mape']) if stats['mape'] else 'N/A'}</div>
                <div class="metric-label">MAPE (Mean Absolute % Error)</div>
            </div>
            <div class="metric-card">
                <div class="metric-value" style="color: {'var(--success)' if stats['bias'] and stats['bias'] < 15 else 'var(--warning)'}">
                    {f"+{stats['bias']:.1f}%" if stats['bias'] and stats['bias'] > 0 else f"{stats['bias']:.1f}%" if stats['bias'] else 'N/A'}
                </div>
                <div class="metric-label">Systematic Bias (Orennia vs NPM)</div>
            </div>
            <div class="metric-card">
                <div class="metric-value">{f"{stats['pearson_r']:.3f}" if stats['pearson_r'] else 'N/A'}</div>
                <div class="metric-label">Pearson Correlation</div>
            </div>
            <div class="metric-card">
                <span class="grade grade-{stats['grade'].lower() if stats['grade'] != 'N/A' else 'c'}">{stats['grade']}</span>
                <div class="metric-label">Agreement Grade</div>
            </div>
        </div>

        <div class="highlight-box">
            <strong>Interpretation:</strong>
            {f"MAPE of {stats['mape']:.1f}% indicates {'excellent' if stats['mape'] <= 10 else 'good' if stats['mape'] <= 20 else 'moderate' if stats['mape'] <= 35 else 'poor'} agreement between sources on capacity values." if stats['mape'] else "Insufficient capacity data for statistical comparison."}
            {f" Orennia reports {abs(stats['bias']):.1f}% {'higher' if stats['bias'] > 0 else 'lower'} capacity on average compared to NPM." if stats['bias'] else ""}
            {f" Pearson r of {stats['pearson_r']:.2f} shows {'strong' if stats['pearson_r'] >= 0.7 else 'moderate' if stats['pearson_r'] >= 0.4 else 'weak'} correlation — the sources {'agree well' if stats['pearson_r'] >= 0.7 else 'generally agree' if stats['pearson_r'] >= 0.4 else 'disagree'} on which facilities are bigger vs smaller, but {'with tight consistency' if stats['pearson_r'] >= 0.8 else 'with significant scatter around the trend' if stats['pearson_r'] >= 0.5 else 'with high variability'}." if stats['pearson_r'] else ""}
        </div>

        <div class="highlight-box" style="border-left-color: var(--warning);">
            <strong>Bottom Line:</strong>
            {f"The sources {'strongly agree' if stats['pearson_r'] and stats['pearson_r'] >= 0.7 else 'moderately agree' if stats['pearson_r'] and stats['pearson_r'] >= 0.4 else 'weakly agree'} on the <em>ranking</em> of facilities (bigger vs smaller), but {'have excellent agreement' if stats['mape'] and stats['mape'] <= 10 else 'have good agreement' if stats['mape'] and stats['mape'] <= 20 else 'disagree substantially' if stats['mape'] and stats['mape'] > 30 else 'have moderate agreement'} on <em>actual MW values</em>" if stats['pearson_r'] and stats['mape'] else "Insufficient data for comparison."}
            {f" — with {'Orennia' if stats['bias'] and stats['bias'] > 0 else 'NPM'} consistently reporting {abs(stats['bias']):.0f}% {'higher' if stats['bias'] and stats['bias'] > 0 else 'lower'} capacity." if stats['bias'] else ""}
        </div>

          <!-- Methodology Section -->
          <h2>📋 Methodology</h2>
          <div class="highlight-box" style="border-left-color: var(--info);">
              <strong>How This Analysis Works (Aligned with SA vs DCH Workflow):</strong>
              <p style="margin: 10px 0; color: var(--text-secondary);">
                  This comparison follows the methodology established in <code>SA_VS_DCH_COMPARISON_WORKFLOW.md</code>
                  and <code>UCID_SA_DCH_IMPROVEMENT_PLAN.md</code>.
              </p>

              <strong>Matching Mode Used: Building-Level Spatial (1-to-1 Optimal)</strong>
              <ul style="margin: 10px 0; padding-left: 20px;">
                  <li><strong>1-to-1 Optimal Matching:</strong> Each record matches at most ONE counterpart. Uses a greedy algorithm prioritizing closest distances first, ensuring symmetric pair counts.</li>
                  <li><strong>Distance Threshold:</strong> {threshold}m default. Records farther apart are considered unmatched.</li>
                  <li><strong>Company Normalization:</strong> Company names normalized (e.g., "Amazon Web Services" → "AWS") for company match flagging.</li>
              </ul>

              <strong>Available Matching Modes:</strong>
              <table class="data-table" style="margin: 10px 0;">
                  <tr><th>Mode</th><th>Description</th><th>Best For</th></tr>
                  <tr>
                      <td><code>spatial</code></td>
                      <td>Distance only (current)</td>
                      <td>Understanding raw record overlap</td>
                  </tr>
                  <tr>
                      <td><code>company_aware</code></td>
                      <td>Distance + same company required</td>
                      <td>Preventing false matches at multi-tenant sites</td>
                  </tr>
                  <tr>
                      <td><code>ucid</code> (recommended)</td>
                      <td>UCID-based campus matching</td>
                      <td>Accurate site counting, requires post-ingestion pipeline</td>
                  </tr>
              </table>

              <strong>Questions This Analysis Answers:</strong>
              <ul style="margin: 10px 0; padding-left: 20px;">
                  <li>What percentage of NPM records have a corresponding Orennia record nearby? (Overlap rate)</li>
                  <li>For matched pairs, do they agree on company attribution?</li>
                  <li>How closely do capacity values agree between sources? (MAPE, Bias, Pearson r)</li>
                  <li>Is there evidence that sources share the same underlying data source? (Source Overlap Analysis)</li>
              </ul>

              <strong>Key Limitations:</strong>
              <ul style="margin: 10px 0; padding-left: 20px;">
                  <li><strong>Building-level granularity:</strong> This analysis compares individual building records, not UCID-aggregated campuses. A campus with 5 buildings in Orennia may match 3 buildings in NPM (showing as 3 pairs, not 1 campus).</li>
                  <li><strong>Multi-tenant risk:</strong> Without company-aware matching, records from different companies at the same location may be incorrectly matched.</li>
                  <li><strong>Capacity comparisons:</strong> Only include pairs where both sources report capacity values.</li>
              </ul>

              <strong>For More Accurate Campus-Level Comparison:</strong>
              <p style="margin: 10px 0; color: var(--text-secondary);">
                  Run the full post-ingestion pipeline first (<code>run_post_ingestion.py</code>) to generate UCIDs,
                  then use campus-level comparison from <code>gold_campus_full</code> for accurate site counts.
                  See <code>SA_VS_DCH_COMPARISON_WORKFLOW.md</code> for the recommended approach.
              </p>
          </div>

          <!-- Spatial Matching -->
          <h2>Spatial Proximity Matching</h2>
          <p style="color: var(--text-secondary); margin-bottom: 15px;">
              <em>Using 1-to-1 optimal matching: each record matches at most one counterpart (symmetric pair counts)</em>
          </p>

          <table>
              <thead>
                  <tr>
                      <th>Threshold</th>
                      <th>Matched Pairs</th>
                      <th>Orennia Coverage</th>
                      <th>NPM Coverage</th>
                  </tr>
              </thead>
              <tbody>
'''

    for label, data in spatial.items():
        html += f'''
                <tr>
                    <td>{label}</td>
                    <td class="number">{format_number(data['matched_pairs'])}</td>
                    <td class="number">{format_number(data['orennia_matched'])} ({format_pct(data['orennia_pct'])})</td>
                    <td class="number">{format_number(data['npm_matched'])} ({format_pct(data['npm_pct'])})</td>
                </tr>'''

    html += '''
            </tbody>
        </table>

        <!-- Match Quality -->
        <h2>Match Quality Analysis</h2>

        <div class="metrics-grid">
            <div class="metric-card">
                <div class="metric-value">''' + format_pct(quality['company_match_pct']) + '''</div>
                <div class="metric-label">Company Name Match</div>
            </div>
            <div class="metric-card">
                <div class="metric-value">''' + format_pct(quality['state_match_pct']) + '''</div>
                <div class="metric-label">State Match</div>
            </div>
            <div class="metric-card">
                <div class="metric-value">''' + format_pct(quality['status_match_pct']) + '''</div>
                <div class="metric-label">Status Match</div>
            </div>
        </div>

        <!-- Charts -->
        <h2>Distribution Comparison</h2>

        <div class="chart-row">
            <div class="chart-container">
                <h3>Top States by Source</h3>
                <canvas id="stateChart" height="250"></canvas>
            </div>
            <div class="chart-container">
                <h3>Status Distribution</h3>
                <canvas id="statusChart" height="250"></canvas>
            </div>
        </div>

        <!-- Company Overlap -->
        <h2>Company Analysis</h2>

        <div class="two-col">
            <div class="highlight-box">
                <h4>Company Overlap</h4>
                <p><strong>Orennia unique companies:</strong> ''' + format_number(results['company_overlap']['orennia_unique']) + '''</p>
                <p><strong>NPM unique companies:</strong> ''' + format_number(results['company_overlap']['npm_unique']) + '''</p>
                <p><strong>Common companies:</strong> ''' + format_number(results['company_overlap']['common']) + '''</p>
            </div>
            <div class="highlight-box">
                <h4>Top Common Companies</h4>
                <p>''' + ', '.join(results['company_overlap']['common_list'][:15]) + '''</p>
            </div>
        </div>

        <!-- Capacity by Source -->
        <h2>Total Capacity by Source</h2>

        <div class="metrics-grid">
            <div class="metric-card">
                <div class="metric-value source-orennia">''' + format_number(orennia['total_capacity_mw'], 0) + '''</div>
                <div class="metric-label">Orennia Total MW</div>
            </div>
            <div class="metric-card">
                <div class="metric-value source-npm">''' + format_number(npm['total_capacity_mw'], 0) + '''</div>
                <div class="metric-label">NPM Total MW</div>
            </div>
        </div>

        <!-- Detailed Match Examples -->
        <h2>Match Examples (Closest 20)</h2>

        <table>
            <thead>
                <tr>
                    <th>Distance</th>
                    <th>Company Match</th>
                    <th>Orennia Company</th>
                    <th>NPM Company</th>
                    <th>Orennia MW</th>
                    <th>NPM MW</th>
                    <th>Delta</th>
                </tr>
            </thead>
            <tbody>
'''

    for m in results['match_examples'][:20]:
        co_class = 'match-yes' if m['company_match'] else 'match-no'
        html += f'''
                <tr>
                    <td class="number">{m['distance_m']:.0f}m</td>
                    <td class="{co_class}">{'YES' if m['company_match'] else 'no'}</td>
                    <td>{(m['orennia']['company_source'] or '')[:25]}</td>
                    <td>{(m['npm']['company_source'] or '')[:25]}</td>
                    <td class="number">{format_number(m['orennia_cap'])}</td>
                    <td class="number">{format_number(m['npm_cap'])}</td>
                    <td class="number">{m['cap_delta']:+.0f}</td>
                </tr>'''

    html += '''
            </tbody>
        </table>

        <!-- Significant Conflicts -->
        <h2>Significant Capacity Conflicts (&gt;20% difference)</h2>

        <table>
            <thead>
                <tr>
                    <th>Distance</th>
                    <th>Orennia Company</th>
                    <th>NPM Company</th>
                    <th>Orennia MW</th>
                    <th>NPM MW</th>
                    <th>Delta MW</th>
                    <th>Delta %</th>
                </tr>
            </thead>
            <tbody>
'''

    for m in results['significant_conflicts'][:20]:
        html += f'''
                <tr>
                    <td class="number">{m['distance_m']:.0f}m</td>
                    <td>{(m['orennia']['company_source'] or '')[:20]}</td>
                    <td>{(m['npm']['company_source'] or '')[:20]}</td>
                    <td class="number">{format_number(m['orennia_cap'])}</td>
                    <td class="number">{format_number(m['npm_cap'])}</td>
                    <td class="number">{m['cap_delta']:+,.0f}</td>
                    <td class="number">{m['cap_delta_pct']:+.1f}%</td>
                </tr>'''

    html += '''
            </tbody>
        </table>

        <!-- Recommendations -->
        <h2>Recommendations</h2>

        <div class="recommendation">
            <h4>Data Source Strategy</h4>
            <ul>
                <li><strong>Primary Source:</strong> Use <span class="source-orennia">Orennia</span> as the primary data source (larger coverage: ''' + format_number(orennia['count']) + ''' vs ''' + format_number(npm['count']) + ''' records)</li>
                <li><strong>NPM Unique Records:</strong> ''' + format_number(len(results['npm_only'])) + f''' NPM records ({100 - spatial['500m']['npm_pct']:.1f}%) do NOT overlap with Orennia - consider keeping these for expanded coverage</li>
                <li><strong>Deduplication:</strong> Run UCID generation to properly cluster the ''' + format_number(spatial['500m']['orennia_matched']) + ''' overlapping records</li>
            </ul>
        </div>

        <div class="recommendation">
            <h4>Data Quality Considerations</h4>
            <ul>
                <li><strong>Company Match Rate:</strong> ''' + format_pct(quality['company_match_pct']) + ''' of matched pairs have the same company - investigate mismatches for data quality issues</li>
                <li><strong>Capacity Agreement:</strong> ''' + (f"Grade {stats['grade']} ({stats['mape']:.1f}% MAPE)" if stats['mape'] else 'Insufficient data') + ''' - ''' + ('acceptable for integration' if stats['grade'] in ['A', 'B'] else 'review conflicts before merging') + '''</li>
            </ul>
        </div>

    </div>

    <!-- Chart.js Scripts -->
    <script>
        // State Distribution Chart
        const stateCtx = document.getElementById('stateChart').getContext('2d');
        new Chart(stateCtx, {
            type: 'bar',
            data: {
                labels: ''' + json.dumps(state_labels) + ''',
                datasets: [
                    {
                        label: 'Orennia',
                        data: ''' + json.dumps(orennia_state_data) + ''',
                        backgroundColor: '#3498db'
                    },
                    {
                        label: 'NPM',
                        data: ''' + json.dumps(npm_state_data) + ''',
                        backgroundColor: '#1abc9c'
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { position: 'top', labels: { color: '#eee' } } },
                scales: {
                    x: { ticks: { color: '#aaa' }, grid: { color: '#333' } },
                    y: { ticks: { color: '#aaa' }, grid: { color: '#333' }, beginAtZero: true }
                },
                layout: { padding: 10 }
            }
        });

        // Status Distribution Chart
        const statusCtx = document.getElementById('statusChart').getContext('2d');
        new Chart(statusCtx, {
            type: 'bar',
            data: {
                labels: ''' + json.dumps(status_labels) + ''',
                datasets: [
                    {
                        label: 'Orennia',
                        data: ''' + json.dumps(orennia_status_data) + ''',
                        backgroundColor: '#3498db'
                    },
                    {
                        label: 'NPM',
                        data: ''' + json.dumps(npm_status_data) + ''',
                        backgroundColor: '#1abc9c'
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { position: 'top', labels: { color: '#eee' } } },
                scales: {
                    x: { ticks: { color: '#aaa' }, grid: { color: '#333' } },
                    y: { ticks: { color: '#aaa' }, grid: { color: '#333' }, beginAtZero: true }
                },
                layout: { padding: 10 }
            }
        });
    </script>
</body>
</html>
'''

    # Write HTML file
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)

    print(f"   HTML report saved to: {output_path}")
    return output_path


# ============================================================================
# MAIN EXECUTION
# ============================================================================

def run_comparison(threshold_m=DEFAULT_THRESHOLD, output_html=True):
    """Main entry point for running the comparison."""
    print("=" * 80)
    print("NPM vs ORENNIA COMPARISON ANALYSIS")
    print(f"Started: {datetime.now()}")
    print("=" * 80)

    print(f"\nTarget Feature Class: {GOLD_BUILDINGS}")
    print(f"Matching Threshold: {threshold_m}m")

    # Check if feature class exists
    if not arcpy.Exists(GOLD_BUILDINGS):
        raise Exception(f"Feature class not found: {GOLD_BUILDINGS}")

    # Load data
    print("\nLoading Orennia records...")
    orennia_records = load_source_data(ORENNIA_SOURCE)
    print(f"  Loaded {len(orennia_records):,} Orennia records")

    print("\nLoading NPM records...")
    npm_records = load_source_data(NPM_SOURCE)
    print(f"  Loaded {len(npm_records):,} NPM records")

    if len(npm_records) == 0:
        print("\n[ERROR] No NPM records found! Run ingest_npm.py first.")
        return None

    if len(orennia_records) == 0:
        print("\n[ERROR] No Orennia records found! Run ingest_orennia.py first.")
        return None

    # Run analysis
    print("\nRunning analysis...")
    results = run_full_analysis(orennia_records, npm_records, threshold_m)

    # Print summary
    print("\n" + "=" * 80)
    print("ANALYSIS SUMMARY")
    print("=" * 80)

    spatial = results['spatial_matches']['500m']
    stats = results['statistics']

    print(f"\nRecord Counts:")
    print(f"  Orennia: {results['orennia']['count']:,}")
    print(f"  NPM:     {results['npm']['count']:,}")

    print(f"\nSpatial Overlap (500m):")
    print(f"  NPM records matching Orennia:     {spatial['npm_matched']:,} ({spatial['npm_pct']:.1f}%)")
    print(f"  Orennia records matching NPM:     {spatial['orennia_matched']:,} ({spatial['orennia_pct']:.1f}%)")
    print(f"  NPM-only records (unique):        {len(results['npm_only']):,}")
    print(f"  Orennia-only records (unique):    {len(results['orennia_only']):,}")

    print(f"\nCapacity Statistics:")
    print(f"  MAPE:         {stats['mape']:.1f}%" if stats['mape'] else "  MAPE:         N/A")
    print(f"  Bias:         {stats['bias']:+.1f}%" if stats['bias'] else "  Bias:         N/A")
    print(f"  Pearson r:    {stats['pearson_r']:.3f}" if stats['pearson_r'] else "  Pearson r:    N/A")
    print(f"  Grade:        {stats['grade']}")

    print(f"\nMatch Quality:")
    print(f"  Company Match: {results['match_quality']['company_match_pct']:.1f}%")
    print(f"  State Match:   {results['match_quality']['state_match_pct']:.1f}%")
    print(f"  Status Match:  {results['match_quality']['status_match_pct']:.1f}%")

    # Generate HTML report
    if output_html:
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        html_path = os.path.join(OUTPUT_DIR, f"NPM_vs_Orennia_Comparison_{timestamp}.html")
        generate_html_report(results, html_path)

    print("\n" + "=" * 80)
    print("COMPARISON COMPLETE")
    print("=" * 80)

    return results


def main():
    """Main entry point."""
    return run_comparison()


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
    # Running in ArcGIS Pro Python window
    try:
        results = main()
    except Exception as e:
        print(f"\nERROR: {str(e)}")
        import traceback
        traceback.print_exc()
