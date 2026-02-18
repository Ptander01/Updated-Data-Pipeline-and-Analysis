"""
UCID Intake Matcher
Match incoming market rumors/signals to existing Universal Campus IDs.

This utility provides functions to match new data points (rumors, news, tips)
to existing campuses in the UCID registry.

Usage:
    from ucid_intake_matcher import match_rumor_to_ucid

    result = match_rumor_to_ucid(
        company="Microsoft",
        city="San Antonio",
        lat=29.4241,
        lon=-98.4936
    )

    # Returns: {
    #     'ucid': 'UCID-AMER-00088',
    #     'confidence': 0.92,
    #     'canonical_name': 'Microsoft San Antonio',
    #     'match_type': 'SPATIAL',
    #     'distance_m': 125.4
    # }

Author: Meta Data Center GIS Team
Created: December 18, 2024
"""

import arcpy
import os
import sys
import math
from collections import defaultdict

# Add _utils to path for config import
try:
    script_dir = os.path.dirname(os.path.abspath(__file__))
except NameError:
    script_dir = r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\scripts\06_ucid"

utils_dir = os.path.join(os.path.dirname(script_dir), "_utils")
if utils_dir not in sys.path:
    sys.path.insert(0, utils_dir)

from config import GDB, CAMPUS_MASTER

# ==============================================================================
# CONFIGURATION
# ==============================================================================

# Match thresholds
SPATIAL_MATCH_THRESHOLD_M = 1000  # Maximum distance for spatial match
HIGH_CONFIDENCE_THRESHOLD_M = 250  # Distance for high confidence match
NAME_MATCH_THRESHOLD = 0.7  # Minimum name similarity score

# Company name normalization (same as in generate_ucid_clusters.py)
COMPANY_NORMALIZATION = {
    'amazon': 'AWS',
    'amazon aws': 'AWS',
    'amazon web services': 'AWS',
    'aws': 'AWS',
    'microsoft': 'Microsoft',
    'microsoft corporation': 'Microsoft',
    'microsoft azure': 'Microsoft',
    'azure': 'Microsoft',
    'google': 'Google',
    'google cloud': 'Google',
    'alphabet': 'Google',
    'meta': 'Meta',
    'facebook': 'Meta',
    'apple': 'Apple',
    'oracle': 'Oracle',
    'oracle corporation': 'Oracle',
    'alibaba': 'Alibaba',
    'alibaba cloud': 'Alibaba',
    'xai': 'xAI',
    'x.ai': 'xAI',
}

# ==============================================================================
# HELPER FUNCTIONS
# ==============================================================================

def normalize_company(company_name):
    """Normalize company name for matching."""
    if not company_name:
        return None
    clean = str(company_name).lower().strip()
    return COMPANY_NORMALIZATION.get(clean, company_name)

def haversine_distance(lat1, lon1, lat2, lon2):
    """Calculate great-circle distance in meters."""
    R = 6371000
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)
    a = math.sin(delta_lat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return R * c

def simple_similarity(str1, str2):
    """Calculate simple string similarity (0-1)."""
    if not str1 or not str2:
        return 0

    s1 = str(str1).lower().strip()
    s2 = str(str2).lower().strip()

    if s1 == s2:
        return 1.0

    # Token-based similarity
    tokens1 = set(s1.split())
    tokens2 = set(s2.split())

    if not tokens1 or not tokens2:
        return 0

    intersection = len(tokens1 & tokens2)
    union = len(tokens1 | tokens2)

    return intersection / union if union > 0 else 0

def load_campus_master():
    """Load campus master data into memory for fast matching."""

    if not arcpy.Exists(CAMPUS_MASTER):
        raise ValueError(f"campus_master not found at {CAMPUS_MASTER}. Run assign_ucid_to_gold.py first.")

    campuses = []

    fields = ['ucid', 'canonical_name', 'company_canonical', 'city',
              'state_abbr', 'region', 'latitude', 'longitude',
              'source_count', 'total_capacity_mw']

    with arcpy.da.SearchCursor(CAMPUS_MASTER, fields) as cursor:
        for row in cursor:
            campuses.append({
                'ucid': row[0],
                'canonical_name': row[1],
                'company': row[2],
                'city': row[3],
                'state_abbr': row[4],
                'region': row[5],
                'lat': row[6],
                'lon': row[7],
                'source_count': row[8],
                'capacity_mw': row[9] or 0,
            })

    return campuses

# Cache campus master data
_campus_cache = None

def get_campus_cache():
    """Get or load cached campus master data."""
    global _campus_cache
    if _campus_cache is None:
        _campus_cache = load_campus_master()
    return _campus_cache

def clear_cache():
    """Clear the campus cache (call after updating campus_master)."""
    global _campus_cache
    _campus_cache = None

# ==============================================================================
# MATCHING FUNCTIONS
# ==============================================================================

def match_rumor_to_ucid(company=None, city=None, state=None, lat=None, lon=None,
                         campus_name=None, threshold_m=None):
    """
    Match an incoming rumor/signal to an existing UCID.

    Args:
        company: Company name (optional but recommended)
        city: City name (optional)
        state: State abbreviation (optional)
        lat: Latitude (required for spatial match)
        lon: Longitude (required for spatial match)
        campus_name: Campus/site name if known (optional)
        threshold_m: Custom distance threshold in meters (default: 1000)

    Returns:
        dict with match result, or None if no match found:
        {
            'ucid': 'UCID-AMER-00088',
            'confidence': 0.92,  # 0-1 score
            'canonical_name': 'Microsoft San Antonio',
            'match_type': 'SPATIAL' or 'NAME' or 'SPATIAL+NAME',
            'distance_m': 125.4,
            'company_match': True/False,
            'alternatives': []  # Other potential matches
        }
    """

    if threshold_m is None:
        threshold_m = SPATIAL_MATCH_THRESHOLD_M

    campuses = get_campus_cache()
    normalized_company = normalize_company(company) if company else None

    candidates = []

    # Spatial matching (if coordinates provided)
    if lat is not None and lon is not None:
        for campus in campuses:
            if campus['lat'] and campus['lon']:
                dist = haversine_distance(lat, lon, campus['lat'], campus['lon'])

                if dist <= threshold_m:
                    # Company match bonus
                    company_match = (normalized_company and
                                    campus['company'] == normalized_company)

                    # Name similarity
                    name_sim = 0
                    if campus_name:
                        name_sim = max(
                            simple_similarity(campus_name, campus['canonical_name']),
                            simple_similarity(campus_name, campus['city'])
                        )

                    # City similarity
                    city_sim = simple_similarity(city, campus['city']) if city else 0

                    # Calculate confidence
                    # Distance component (closer = higher)
                    dist_score = max(0, 1 - (dist / threshold_m))

                    # Company match is a big boost
                    company_score = 0.3 if company_match else 0

                    # Name/city similarity
                    name_score = max(name_sim, city_sim) * 0.2

                    confidence = min(1.0, dist_score * 0.5 + company_score + name_score)

                    # High distance penalty if company doesn't match
                    if dist > HIGH_CONFIDENCE_THRESHOLD_M and not company_match:
                        confidence *= 0.7

                    candidates.append({
                        'ucid': campus['ucid'],
                        'canonical_name': campus['canonical_name'],
                        'company': campus['company'],
                        'city': campus['city'],
                        'state_abbr': campus['state_abbr'],
                        'distance_m': round(dist, 1),
                        'company_match': company_match,
                        'confidence': round(confidence, 3),
                        'match_type': 'SPATIAL',
                        'capacity_mw': campus['capacity_mw'],
                    })

    # Name-only matching (fallback if no coordinates)
    elif city or campus_name:
        for campus in campuses:
            name_sim = 0
            city_sim = 0

            if campus_name:
                name_sim = simple_similarity(campus_name, campus['canonical_name'])

            if city:
                city_sim = simple_similarity(city, campus['city'])

            company_match = (normalized_company and
                            campus['company'] == normalized_company)

            # Only consider if company matches and some name/city match
            if company_match and (name_sim >= NAME_MATCH_THRESHOLD or
                                  city_sim >= NAME_MATCH_THRESHOLD):

                confidence = max(name_sim, city_sim) * 0.7 + 0.3

                candidates.append({
                    'ucid': campus['ucid'],
                    'canonical_name': campus['canonical_name'],
                    'company': campus['company'],
                    'city': campus['city'],
                    'state_abbr': campus['state_abbr'],
                    'distance_m': None,
                    'company_match': company_match,
                    'confidence': round(confidence, 3),
                    'match_type': 'NAME',
                    'capacity_mw': campus['capacity_mw'],
                })

    if not candidates:
        return None

    # Sort by confidence
    candidates.sort(key=lambda x: -x['confidence'])

    best = candidates[0]

    # Add alternatives (top 3 other matches)
    best['alternatives'] = candidates[1:4]

    return best

def find_nearby_campuses(lat, lon, radius_m=5000, company=None, limit=10):
    """
    Find all campuses within a radius of a point.

    Args:
        lat: Latitude
        lon: Longitude
        radius_m: Search radius in meters (default 5km)
        company: Filter by company (optional)
        limit: Maximum results to return

    Returns:
        List of campus dicts sorted by distance
    """

    campuses = get_campus_cache()
    normalized_company = normalize_company(company) if company else None

    results = []

    for campus in campuses:
        if campus['lat'] and campus['lon']:
            # Company filter
            if normalized_company and campus['company'] != normalized_company:
                continue

            dist = haversine_distance(lat, lon, campus['lat'], campus['lon'])

            if dist <= radius_m:
                results.append({
                    'ucid': campus['ucid'],
                    'canonical_name': campus['canonical_name'],
                    'company': campus['company'],
                    'city': campus['city'],
                    'state_abbr': campus['state_abbr'],
                    'distance_m': round(dist, 1),
                    'capacity_mw': campus['capacity_mw'],
                    'source_count': campus['source_count'],
                })

    # Sort by distance
    results.sort(key=lambda x: x['distance_m'])

    return results[:limit]

def search_by_name(query, company=None, limit=10):
    """
    Search campuses by name.

    Args:
        query: Search string (campus name, city, etc.)
        company: Filter by company (optional)
        limit: Maximum results to return

    Returns:
        List of campus dicts sorted by relevance
    """

    campuses = get_campus_cache()
    normalized_company = normalize_company(company) if company else None

    results = []
    query_lower = query.lower()

    for campus in campuses:
        # Company filter
        if normalized_company and campus['company'] != normalized_company:
            continue

        # Check if query matches canonical_name or city
        name_lower = (campus['canonical_name'] or '').lower()
        city_lower = (campus['city'] or '').lower()

        if query_lower in name_lower or query_lower in city_lower:
            # Calculate relevance
            name_sim = simple_similarity(query, campus['canonical_name'])
            city_sim = simple_similarity(query, campus['city'])
            relevance = max(name_sim, city_sim)

            results.append({
                'ucid': campus['ucid'],
                'canonical_name': campus['canonical_name'],
                'company': campus['company'],
                'city': campus['city'],
                'state_abbr': campus['state_abbr'],
                'relevance': round(relevance, 3),
                'capacity_mw': campus['capacity_mw'],
                'source_count': campus['source_count'],
            })

    # Sort by relevance
    results.sort(key=lambda x: -x['relevance'])

    return results[:limit]

# ==============================================================================
# DEMO / TEST
# ==============================================================================

def demo():
    """Demonstrate the intake matcher functionality."""

    print("="*80)
    print("UCID INTAKE MATCHER - DEMO")
    print("="*80)

    # Load campus data
    print("\nLoading campus master data...")
    campuses = get_campus_cache()
    print(f"Loaded {len(campuses):,} campuses")

    # Test 1: Spatial match with company
    print("\n" + "-"*40)
    print("Test 1: Match Microsoft campus near San Antonio")
    print("-"*40)

    result = match_rumor_to_ucid(
        company="Microsoft",
        city="San Antonio",
        lat=29.4241,
        lon=-98.4936
    )

    if result:
        print(f"   Match: {result['ucid']}")
        print(f"   Name: {result['canonical_name']}")
        print(f"   Confidence: {result['confidence']}")
        print(f"   Distance: {result['distance_m']}m")
        print(f"   Company Match: {result['company_match']}")
    else:
        print("   No match found")

    # Test 2: Name-only search
    print("\n" + "-"*40)
    print("Test 2: Search for 'Altoona'")
    print("-"*40)

    results = search_by_name("Altoona", limit=5)
    for r in results:
        print(f"   {r['ucid']}: {r['canonical_name']} ({r['company']}) - relevance {r['relevance']}")

    # Test 3: Find nearby campuses
    print("\n" + "-"*40)
    print("Test 3: Find AWS campuses near Ashburn, VA")
    print("-"*40)

    # Ashburn, VA coordinates
    nearby = find_nearby_campuses(39.0438, -77.4874, radius_m=20000, company="AWS", limit=5)
    for r in nearby:
        print(f"   {r['ucid']}: {r['canonical_name']} - {r['distance_m']}m away, {r['capacity_mw']} MW")

    print("\n" + "="*80)
    print("Demo complete!")
    print("="*80)

# Execute demo if run directly
if __name__ == "__main__":
    demo()
