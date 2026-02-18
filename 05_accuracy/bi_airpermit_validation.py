"""
Business Insider Air-Permit Dataset Validation Study

This script evaluates whether BI's air-permit-derived dataset can identify parent companies
behind holding companies in our DC pipeline, using a ~20 site spot-check sample.

Phases:
1. Data Preparation & Sample Selection
2. Matching Methodology (Multi-tier spatial matching)
3. Evaluation Metrics
4. Documentation & Reporting

Author: Meta Data Center GIS Team
Created: 2026-02-13
"""

import arcpy
import os
import sys
import math
import json
import csv
import random
from datetime import datetime
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Optional, Tuple, Any

# Add _utils to path for config import
try:
    script_dir = os.path.dirname(os.path.abspath(__file__))
except NameError:
    script_dir = r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\scripts\05_accuracy"

utils_dir = os.path.join(os.path.dirname(script_dir), "_utils")
if utils_dir not in sys.path:
    sys.path.insert(0, utils_dir)

from config import GOLD_BUILDINGS, GOLD_CAMPUS, GDB, ACCURACY_REPORTS_DIR

# ============================================================================
# CONFIGURATION
# ============================================================================

# Sample size for spot-check
SAMPLE_SIZE = 20

# Random seed for reproducibility
RANDOM_SEED = 42

# Spatial matching thresholds (meters) - Multi-tier strategy per plan
MATCH_TIERS = {
    'tier_1': {'name': 'Definitive', 'distance': 0, 'confidence': 'Definitive', 'method': 'permit_id'},
    'tier_2': {'name': 'High', 'distance': 250, 'confidence': 'High', 'method': 'proximity_exact_name'},
    'tier_3': {'name': 'Medium', 'distance': 500, 'confidence': 'Medium', 'method': 'proximity_fuzzy_name'},
    'tier_4': {'name': 'Low', 'distance': 1000, 'confidence': 'Low', 'method': 'proximity_location_only'},
}

# Output directories
OUTPUT_DIR = ACCURACY_REPORTS_DIR
TIMESTAMP = datetime.now().strftime('%Y%m%d_%H%M%S')

# Status categories for stratified sampling
STATUS_PLANNED = ['Announced', 'Planned', 'Proposed', 'In Development']
STATUS_UC = ['Under Construction']
STATUS_OPERATIONAL = ['Active', 'Operational', 'Operating']

# High DC concentration states
HIGH_DC_STATES = ['VA', 'TX', 'AZ', 'GA', 'CA', 'OH', 'NV', 'OR']

# Holding company name normalization patterns
HOLDING_CO_SUFFIXES = [
    'llc', 'inc', 'corp', 'corporation', 'company', 'co',
    'properties', 'holdings', 'holding', 'development', 'dev',
    'land', 'real estate', 'realty', 'investments', 'partners',
    'ventures', 'enterprises', 'group', 'capital'
]

# State abbreviation mappings
STATE_ABBREV = {
    'virginia': 'va', 'texas': 'tx', 'arizona': 'az',
    'georgia': 'ga', 'california': 'ca', 'ohio': 'oh',
    'nevada': 'nv', 'oregon': 'or', 'washington': 'wa',
    'north carolina': 'nc', 'south carolina': 'sc',
    'new york': 'ny', 'new jersey': 'nj', 'illinois': 'il'
}

# Known hyperscaler aliases for parent company identification
HYPERSCALER_ALIASES = {
    'aws': ['amazon', 'aws', 'amazon web services', 'blue origin'],
    'microsoft': ['microsoft', 'azure', 'msft', 'stargate'],
    'google': ['google', 'gcp', 'alphabet', 'waymo'],
    'meta': ['meta', 'facebook', 'fb', 'instagram', 'whatsapp'],
    'apple': ['apple', 'acnv', 'maiden'],
    'oracle': ['oracle', 'oci'],
    'bytedance': ['bytedance', 'tiktok'],
    'alibaba': ['alibaba', 'aliyun'],
    'tencent': ['tencent', 'wechat'],
}

# Developer/Colo company aliases
DEVELOPER_ALIASES = {
    'equinix': ['equinix'],
    'digital_realty': ['digital realty', 'digitalrealty', 'dlr'],
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
    'switch': ['switch'],
    'prime': ['prime data centers'],
    'skybox': ['skybox'],
    'edgeconnex': ['edgeconnex', 'edge connex'],
}

# ============================================================================
# DATA CLASSES
# ============================================================================

class SiteRecord:
    """Represents a site from our pipeline (Sam's query results)."""
    def __init__(self, **kwargs):
        self.site_id = kwargs.get('site_id')
        self.unique_id = kwargs.get('unique_id')
        self.site_name = kwargs.get('site_name')
        self.campus_name = kwargs.get('campus_name')
        self.developer = kwargs.get('developer')  # Holding company
        self.tenant = kwargs.get('tenant')  # Confirmed hyperscaler (NULL for our targets)
        self.latitude = kwargs.get('latitude')
        self.longitude = kwargs.get('longitude')
        self.address = kwargs.get('address')
        self.city = kwargs.get('city')
        self.state = kwargs.get('state')
        self.state_abbr = kwargs.get('state_abbr')
        self.county = kwargs.get('county')
        self.capacity_mw = kwargs.get('capacity_mw')
        self.status = kwargs.get('status')
        self.permit_id = kwargs.get('permit_id')
        self.source = kwargs.get('source')

    def __repr__(self):
        return f"SiteRecord({self.site_name or self.unique_id}, {self.state_abbr})"

class BIRecord:
    """Represents a record from Business Insider air-permit dataset."""
    def __init__(self, **kwargs):
        self.bi_id = kwargs.get('bi_id')
        self.permit_holder = kwargs.get('permit_holder')  # Shell company
        self.parent_company = kwargs.get('parent_company')  # KEY VALUE-ADD
        self.latitude = kwargs.get('latitude')
        self.longitude = kwargs.get('longitude')
        self.address = kwargs.get('address')
        self.city = kwargs.get('city')
        self.state = kwargs.get('state')
        self.county = kwargs.get('county')
        self.permit_id = kwargs.get('permit_id')
        self.permit_date = kwargs.get('permit_date')
        self.capacity_mw = kwargs.get('capacity_mw')
        self.air_quality_district = kwargs.get('air_quality_district')

    def __repr__(self):
        return f"BIRecord({self.permit_holder or self.bi_id}, {self.state})"

class MatchResult:
    """Represents a matching result between our site and BI record."""
    def __init__(self, our_site: SiteRecord, bi_record: Optional[BIRecord] = None):
        self.our_site = our_site
        self.bi_record = bi_record
        self.match_found = bi_record is not None
        self.match_tier = None  # 1, 2, 3, or 4
        self.match_confidence = None  # Definitive, High, Medium, Low
        self.distance_meters = None
        self.name_match_score = None
        self.geographic_verified = False
        self.company_logic_valid = False
        self.parent_plausible = False
        self.intelligence_gained = 'None'  # None, Partial, Full
        self.notes = []

    def to_dict(self) -> Dict:
        return {
            'site_id': self.our_site.unique_id,
            'site_name': self.our_site.site_name or self.our_site.campus_name,
            'our_developer': self.our_site.developer,
            'our_state': self.our_site.state_abbr,
            'our_status': self.our_site.status,
            'our_lat': self.our_site.latitude,
            'our_lon': self.our_site.longitude,
            'match_found': self.match_found,
            'bi_id': self.bi_record.bi_id if self.bi_record else None,
            'bi_permit_holder': self.bi_record.permit_holder if self.bi_record else None,
            'bi_parent_company': self.bi_record.parent_company if self.bi_record else None,
            'match_tier': self.match_tier,
            'match_confidence': self.match_confidence,
            'distance_meters': self.distance_meters,
            'name_match_score': self.name_match_score,
            'geographic_verified': self.geographic_verified,
            'intelligence_gained': self.intelligence_gained,
            'notes': '; '.join(self.notes) if self.notes else ''
        }

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
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

def normalize_holding_company(name: str) -> str:
    """Normalize holding company name for matching."""
    if not name:
        return ''

    # Lowercase and strip
    normalized = str(name).lower().strip()

    # Remove punctuation
    for char in [',', '.', "'", '"', '/', '\\', '(', ')', '-', '_']:
        normalized = normalized.replace(char, ' ')

    # Remove common suffixes
    for suffix in HOLDING_CO_SUFFIXES:
        # Remove as whole word
        normalized = ' '.join([w for w in normalized.split() if w != suffix])

    # Replace state names with abbreviations
    for full, abbr in STATE_ABBREV.items():
        normalized = normalized.replace(full, abbr)

    # Clean up whitespace
    normalized = ' '.join(normalized.split())

    return normalized

def fuzzy_match_score(str1: str, str2: str) -> float:
    """Calculate fuzzy match score between two strings (0-100)."""
    if not str1 or not str2:
        return 0.0

    s1 = normalize_holding_company(str1)
    s2 = normalize_holding_company(str2)

    if s1 == s2:
        return 100.0

    if not s1 or not s2:
        return 0.0

    # Token-based similarity (Jaccard)
    tokens1 = set(s1.split())
    tokens2 = set(s2.split())

    if not tokens1 or not tokens2:
        return 0.0

    intersection = len(tokens1 & tokens2)
    union = len(tokens1 | tokens2)

    jaccard = (intersection / union) * 100 if union > 0 else 0.0

    # Check for substring containment
    if s1 in s2 or s2 in s1:
        return max(jaccard, 80.0)

    return jaccard

def identify_hyperscaler(company_name: str) -> Optional[str]:
    """Attempt to identify if a company name refers to a known hyperscaler."""
    if not company_name:
        return None

    name_lower = str(company_name).lower()

    for hyperscaler, aliases in HYPERSCALER_ALIASES.items():
        for alias in aliases:
            if alias in name_lower:
                return hyperscaler.upper()

    return None

def identify_developer(company_name: str) -> Optional[str]:
    """Attempt to identify if a company name refers to a known developer/colo."""
    if not company_name:
        return None

    name_lower = str(company_name).lower()

    for developer, aliases in DEVELOPER_ALIASES.items():
        for alias in aliases:
            if alias in name_lower:
                return developer.title().replace('_', ' ')

    return None

def normalize_status(status: str) -> str:
    """Normalize status to category."""
    if not status:
        return 'Unknown'

    status_str = str(status).strip().lower()

    if any(s.lower() in status_str for s in STATUS_OPERATIONAL):
        return 'Operational'
    elif any(s.lower() in status_str for s in STATUS_UC):
        return 'Under Construction'
    elif any(s.lower() in status_str for s in STATUS_PLANNED):
        return 'Planned'
    else:
        return 'Unknown'

def safe_float(val) -> Optional[float]:
    """Safely convert to float."""
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None

def safe_str(val) -> Optional[str]:
    """Safely convert to string."""
    if val is None:
        return None
    s = str(val).strip()
    return s if s and s.lower() not in ['none', 'nan', '', 'null'] else None

# ============================================================================
# PHASE 1: DATA PREPARATION & SAMPLE SELECTION
# ============================================================================

def load_pipeline_data() -> List[SiteRecord]:
    """
    Load data from gold_buildings feature class.
    Filters for records where developer exists but tenant is unknown.
    """
    print("\n" + "="*70)
    print("PHASE 1.1: Loading Pipeline Data")
    print("="*70)

    # Fields to extract from gold_buildings
    fields = [
        'OID@', 'SHAPE@XY', 'unique_id', 'source', 'company_source', 'company_clean',
        'company_clean_filter', 'state_abbr', 'state', 'county', 'country',
        'latitude', 'longitude', 'full_capacity_mw', 'facility_status',
        'campus_name', 'building_designation'
    ]

    records = []

    try:
        with arcpy.da.SearchCursor(GOLD_BUILDINGS, fields) as cursor:
            for row in cursor:
                # Extract values
                record = SiteRecord(
                    site_id=row[0],
                    unique_id=safe_str(row[2]),
                    source=safe_str(row[3]),
                    developer=safe_str(row[4]) or safe_str(row[5]),  # company_source or company_clean
                    tenant=None,  # We'll identify separately
                    state_abbr=safe_str(row[7]),
                    state=safe_str(row[8]),
                    county=safe_str(row[9]),
                    latitude=safe_float(row[11]),
                    longitude=safe_float(row[12]),
                    capacity_mw=safe_float(row[13]),
                    status=safe_str(row[14]),
                    campus_name=safe_str(row[15]),
                    site_name=safe_str(row[16]) or safe_str(row[15])
                )

                # Check if developer is actually a hyperscaler (known tenant)
                if record.developer:
                    hyperscaler = identify_hyperscaler(record.developer)
                    if hyperscaler:
                        record.tenant = hyperscaler

                records.append(record)

    except Exception as e:
        print(f"ERROR loading data: {e}")
        raise

    print(f"  Loaded {len(records):,} total records from gold_buildings")

    # Filter for developer exists, tenant unknown
    filtered = [r for r in records if r.developer and not r.tenant]
    print(f"  Filtered to {len(filtered):,} records where developer exists but tenant unknown")

    return filtered

def stratified_sample_selection(records: List[SiteRecord], n: int = SAMPLE_SIZE) -> List[SiteRecord]:
    """
    Select n sites using stratified random sampling per the plan:
    - By Status: 8 Planned/Announced, 8 Under Construction, 4 Operational
    - By Geography: 10 from VA/TX/AZ, 10 from other states
    """
    print("\n" + "="*70)
    print("PHASE 1.2: Stratified Sample Selection")
    print("="*70)

    random.seed(RANDOM_SEED)

    # Categorize records by status
    planned = [r for r in records if normalize_status(r.status) == 'Planned']
    uc = [r for r in records if normalize_status(r.status) == 'Under Construction']
    operational = [r for r in records if normalize_status(r.status) == 'Operational']

    print(f"\n  Status Distribution:")
    print(f"    Planned/Announced: {len(planned):,}")
    print(f"    Under Construction: {len(uc):,}")
    print(f"    Operational: {len(operational):,}")

    # Categorize by geography
    high_dc = [r for r in records if r.state_abbr and r.state_abbr.upper() in HIGH_DC_STATES]
    other = [r for r in records if not r.state_abbr or r.state_abbr.upper() not in HIGH_DC_STATES]

    print(f"\n  Geographic Distribution:")
    print(f"    High DC States (VA/TX/AZ/etc): {len(high_dc):,}")
    print(f"    Other States: {len(other):,}")

    # Selection quotas per plan
    quotas = {
        'planned_high_dc': 4,
        'planned_other': 4,
        'uc_high_dc': 4,
        'uc_other': 4,
        'operational_high_dc': 2,
        'operational_other': 2,
    }

    selected = []

    # Planned from high DC states
    pool = [r for r in planned if r.state_abbr and r.state_abbr.upper() in HIGH_DC_STATES]
    if pool:
        selected.extend(random.sample(pool, min(quotas['planned_high_dc'], len(pool))))

    # Planned from other states
    pool = [r for r in planned if not r.state_abbr or r.state_abbr.upper() not in HIGH_DC_STATES]
    if pool:
        selected.extend(random.sample(pool, min(quotas['planned_other'], len(pool))))

    # UC from high DC states
    pool = [r for r in uc if r.state_abbr and r.state_abbr.upper() in HIGH_DC_STATES]
    if pool:
        selected.extend(random.sample(pool, min(quotas['uc_high_dc'], len(pool))))

    # UC from other states
    pool = [r for r in uc if not r.state_abbr or r.state_abbr.upper() not in HIGH_DC_STATES]
    if pool:
        selected.extend(random.sample(pool, min(quotas['uc_other'], len(pool))))

    # Operational from high DC states
    pool = [r for r in operational if r.state_abbr and r.state_abbr.upper() in HIGH_DC_STATES]
    if pool:
        selected.extend(random.sample(pool, min(quotas['operational_high_dc'], len(pool))))

    # Operational from other states
    pool = [r for r in operational if not r.state_abbr or r.state_abbr.upper() not in HIGH_DC_STATES]
    if pool:
        selected.extend(random.sample(pool, min(quotas['operational_other'], len(pool))))

    # If we're short, fill from remaining records
    selected_ids = {r.unique_id for r in selected}
    remaining = [r for r in records if r.unique_id not in selected_ids]

    if len(selected) < n and remaining:
        additional = random.sample(remaining, min(n - len(selected), len(remaining)))
        selected.extend(additional)

    print(f"\n  Selected Sample (n={len(selected)}):")

    # Print sample summary
    status_counts = defaultdict(int)
    geo_counts = defaultdict(int)

    for r in selected:
        status_counts[normalize_status(r.status)] += 1
        if r.state_abbr and r.state_abbr.upper() in HIGH_DC_STATES:
            geo_counts['High DC States'] += 1
        else:
            geo_counts['Other States'] += 1

    print(f"    By Status: {dict(status_counts)}")
    print(f"    By Geography: {dict(geo_counts)}")

    return selected

def load_bi_dataset(filepath: str) -> List[BIRecord]:
    """
    Load Business Insider air-permit dataset from CSV.

    Expected columns (adjust based on actual BI data structure):
    - bi_id / id: Unique identifier
    - permit_holder / shell_company: The holding company on the permit
    - parent_company / linked_company: The identified parent (key value-add)
    - latitude, longitude: Coordinates
    - address, city, state, county: Location info
    - permit_id: Air permit identifier
    - capacity_mw / generator_capacity: Power capacity if available
    """
    print("\n" + "="*70)
    print("PHASE 1.3: Loading Business Insider Dataset")
    print("="*70)

    if not os.path.exists(filepath):
        print(f"  WARNING: BI dataset not found at: {filepath}")
        print("  Please download the BI dataset and place it at the specified path.")
        print("  Returning empty list - script will continue with simulation mode.")
        return []

    records = []

    # Common column name variations to check
    id_cols = ['bi_id', 'id', 'record_id', 'permit_record_id']
    holder_cols = ['permit_holder', 'shell_company', 'applicant', 'company', 'facility_name']
    parent_cols = ['parent_company', 'linked_company', 'ultimate_parent', 'parent', 'owner']
    lat_cols = ['latitude', 'lat', 'y']
    lon_cols = ['longitude', 'lon', 'long', 'x']
    permit_cols = ['permit_id', 'permit_number', 'air_permit_id']

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            headers = [h.lower().strip() for h in reader.fieldnames]

            print(f"  Found columns: {', '.join(reader.fieldnames[:10])}...")

            # Map columns
            def find_col(candidates):
                for c in candidates:
                    if c in headers:
                        return c
                return None

            id_col = find_col(id_cols)
            holder_col = find_col(holder_cols)
            parent_col = find_col(parent_cols)
            lat_col = find_col(lat_cols)
            lon_col = find_col(lon_cols)
            permit_col = find_col(permit_cols)

            for i, row in enumerate(reader):
                # Lowercase keys for consistent access
                row_lower = {k.lower().strip(): v for k, v in row.items()}

                record = BIRecord(
                    bi_id=safe_str(row_lower.get(id_col, str(i))),
                    permit_holder=safe_str(row_lower.get(holder_col)),
                    parent_company=safe_str(row_lower.get(parent_col)),
                    latitude=safe_float(row_lower.get(lat_col)),
                    longitude=safe_float(row_lower.get(lon_col)),
                    address=safe_str(row_lower.get('address')),
                    city=safe_str(row_lower.get('city')),
                    state=safe_str(row_lower.get('state')),
                    county=safe_str(row_lower.get('county')),
                    permit_id=safe_str(row_lower.get(permit_col)),
                    capacity_mw=safe_float(row_lower.get('capacity_mw') or row_lower.get('generator_capacity')),
                )
                records.append(record)

        print(f"  Loaded {len(records):,} records from BI dataset")

        # Quick stats
        with_parent = sum(1 for r in records if r.parent_company)
        with_coords = sum(1 for r in records if r.latitude and r.longitude)
        print(f"  Records with parent company identified: {with_parent:,} ({100*with_parent/len(records):.1f}%)")
        print(f"  Records with coordinates: {with_coords:,} ({100*with_coords/len(records):.1f}%)")

    except Exception as e:
        print(f"  ERROR loading BI dataset: {e}")
        return []

    return records

# ============================================================================
# PHASE 2: MATCHING METHODOLOGY
# ============================================================================

def match_single_site(site: SiteRecord, bi_records: List[BIRecord]) -> MatchResult:
    """
    Match a single site against all BI records using multi-tier strategy.

    Tier 1: Same permit ID (definitive)
    Tier 2: ≤250m proximity + same holding company name (high confidence)
    Tier 3: ≤500m proximity + fuzzy name match >85% (medium confidence)
    Tier 4: ≤1km proximity + same state/county (low confidence)
    """
    result = MatchResult(site)

    if not bi_records:
        result.notes.append("No BI dataset loaded")
        return result

    if not site.latitude or not site.longitude:
        result.notes.append("Site missing coordinates")
        return result

    best_match = None
    best_tier = 5  # Higher = worse
    best_distance = float('inf')
    best_score = 0

    for bi in bi_records:
        if not bi.latitude or not bi.longitude:
            continue

        distance = haversine_distance(site.latitude, site.longitude, bi.latitude, bi.longitude)

        # Tier 1: Permit ID match
        if site.permit_id and bi.permit_id and site.permit_id == bi.permit_id:
            if best_tier > 1:
                best_match = bi
                best_tier = 1
                best_distance = distance
                best_score = 100

        # Tier 2: ≤250m + exact name match
        if distance <= 250:
            name_score = fuzzy_match_score(site.developer, bi.permit_holder)
            if name_score >= 95 and (best_tier > 2 or (best_tier == 2 and distance < best_distance)):
                best_match = bi
                best_tier = 2
                best_distance = distance
                best_score = name_score

        # Tier 3: ≤500m + fuzzy name match
        if distance <= 500:
            name_score = fuzzy_match_score(site.developer, bi.permit_holder)
            if name_score >= 85 and (best_tier > 3 or (best_tier == 3 and name_score > best_score)):
                best_match = bi
                best_tier = 3
                best_distance = distance
                best_score = name_score

        # Tier 4: ≤1km + same state/county
        if distance <= 1000:
            same_state = (site.state_abbr and bi.state and
                         site.state_abbr.upper() in bi.state.upper())
            same_county = (site.county and bi.county and
                          normalize_holding_company(site.county) == normalize_holding_company(bi.county))
            if (same_state or same_county) and (best_tier > 4 or (best_tier == 4 and distance < best_distance)):
                best_match = bi
                best_tier = 4
                best_distance = distance
                best_score = 50 if same_county else 30

    # Apply best match
    if best_match and best_tier <= 4:
        result.bi_record = best_match
        result.match_found = True
        result.match_tier = best_tier
        result.match_confidence = MATCH_TIERS[f'tier_{best_tier}']['confidence']
        result.distance_meters = round(best_distance, 1)
        result.name_match_score = round(best_score, 1)

        # Geographic verification
        result.geographic_verified = best_distance <= 500

        # Company logic validation
        if best_match.parent_company:
            # Check if parent is a known hyperscaler
            parent_hs = identify_hyperscaler(best_match.parent_company)
            parent_dev = identify_developer(best_match.parent_company)
            result.company_logic_valid = bool(parent_hs or parent_dev)

            # Determine intelligence gained
            if parent_hs:
                result.intelligence_gained = 'Full'
                result.parent_plausible = True
                result.notes.append(f"BI identifies parent as: {best_match.parent_company} (Hyperscaler: {parent_hs})")
            elif parent_dev:
                result.intelligence_gained = 'Partial'
                result.parent_plausible = True
                result.notes.append(f"BI identifies parent as: {best_match.parent_company} (Developer: {parent_dev})")
            else:
                result.intelligence_gained = 'Partial'
                result.notes.append(f"BI identifies parent as: {best_match.parent_company} (Unknown entity)")
        else:
            result.intelligence_gained = 'None'
            result.notes.append("BI has record but no parent company identified")
    else:
        result.notes.append("No match found in BI dataset within distance thresholds")

    return result

def run_matching(sample: List[SiteRecord], bi_records: List[BIRecord]) -> List[MatchResult]:
    """Run matching for all sample sites."""
    print("\n" + "="*70)
    print("PHASE 2: Running Matching Methodology")
    print("="*70)

    results = []

    for i, site in enumerate(sample, 1):
        print(f"\n  [{i}/{len(sample)}] Matching: {site.site_name or site.unique_id} ({site.state_abbr})")
        result = match_single_site(site, bi_records)
        results.append(result)

        if result.match_found:
            print(f"    ✓ MATCH (Tier {result.match_tier} - {result.match_confidence}) @ {result.distance_meters}m")
            print(f"      BI Holder: {result.bi_record.permit_holder}")
            print(f"      BI Parent: {result.bi_record.parent_company or 'Not identified'}")
            print(f"      Intelligence: {result.intelligence_gained}")
        else:
            print(f"    ✗ No match found")
            if result.notes:
                print(f"      Reason: {result.notes[0]}")

    return results

# ============================================================================
# PHASE 3: EVALUATION METRICS
# ============================================================================

def calculate_metrics(results: List[MatchResult]) -> Dict:
    """Calculate evaluation metrics per the plan."""
    print("\n" + "="*70)
    print("PHASE 3: Calculating Evaluation Metrics")
    print("="*70)

    total = len(results)

    # Primary metrics
    full_id = sum(1 for r in results if r.intelligence_gained == 'Full')
    partial_id = sum(1 for r in results if r.intelligence_gained == 'Partial')
    no_match = sum(1 for r in results if not r.match_found)
    match_no_value = sum(1 for r in results if r.match_found and r.intelligence_gained == 'None')

    # Coverage rate
    coverage = sum(1 for r in results if r.match_found)

    # By tier
    tier_counts = defaultdict(int)
    for r in results:
        if r.match_found:
            tier_counts[f'Tier {r.match_tier}'] += 1

    metrics = {
        'total_sample': total,

        # Primary metrics
        'full_id_count': full_id,
        'full_id_pct': 100 * full_id / total if total > 0 else 0,
        'partial_id_count': partial_id,
        'partial_id_pct': 100 * partial_id / total if total > 0 else 0,
        'no_match_count': no_match,
        'no_match_pct': 100 * no_match / total if total > 0 else 0,
        'match_no_value_count': match_no_value,
        'match_no_value_pct': 100 * match_no_value / total if total > 0 else 0,

        # Secondary metrics
        'coverage_count': coverage,
        'coverage_pct': 100 * coverage / total if total > 0 else 0,
        'new_intel_count': full_id + partial_id,
        'new_intel_pct': 100 * (full_id + partial_id) / coverage if coverage > 0 else 0,

        # By tier
        'tier_distribution': dict(tier_counts),

        # Thresholds for recommendation
        'meets_full_id_target': full_id >= 5,  # ≥25%
        'meets_partial_id_target': partial_id >= 8,  # ≥40%
    }

    # Decision framework
    if full_id >= 5:
        metrics['recommendation'] = 'STRONGLY RECOMMEND'
        metrics['recommendation_detail'] = 'Pursue full dataset integration'
    elif full_id >= 3:
        metrics['recommendation'] = 'RECOMMEND'
        metrics['recommendation_detail'] = 'Targeted use for unidentified sites'
    elif full_id >= 1:
        metrics['recommendation'] = 'CONSIDER'
        metrics['recommendation_detail'] = 'Specific high-value investigations only'
    elif coverage > 10:
        metrics['recommendation'] = 'NOT USEFUL'
        metrics['recommendation_detail'] = 'High overlap but no parent ID value'
    else:
        metrics['recommendation'] = 'NOT USEFUL'
        metrics['recommendation_detail'] = 'Methodologies do not overlap'

    # Print metrics
    print(f"\n  PRIMARY METRICS:")
    print(f"    Full Parent ID:        {full_id}/{total} ({metrics['full_id_pct']:.1f}%) {'✓ TARGET MET' if metrics['meets_full_id_target'] else '✗ Below target'}")
    print(f"    Partial Parent ID:     {partial_id}/{total} ({metrics['partial_id_pct']:.1f}%) {'✓ TARGET MET' if metrics['meets_partial_id_target'] else '✗ Below target'}")
    print(f"    No Match:              {no_match}/{total} ({metrics['no_match_pct']:.1f}%)")
    print(f"    Match, No Value:       {match_no_value}/{total} ({metrics['match_no_value_pct']:.1f}%)")

    print(f"\n  SECONDARY METRICS:")
    print(f"    BI Coverage Rate:      {coverage}/{total} ({metrics['coverage_pct']:.1f}%)")
    print(f"    New Intelligence Rate: {metrics['new_intel_count']}/{coverage} ({metrics['new_intel_pct']:.1f}%) of matches")

    print(f"\n  MATCH TIER DISTRIBUTION:")
    for tier, count in sorted(tier_counts.items()):
        print(f"    {tier}: {count}")

    print(f"\n  RECOMMENDATION: {metrics['recommendation']}")
    print(f"    {metrics['recommendation_detail']}")

    return metrics

# ============================================================================
# PHASE 4: DOCUMENTATION & REPORTING
# ============================================================================

def export_sample_selection(sample: List[SiteRecord], output_dir: Path) -> str:
    """Export the sample selection to CSV."""
    filepath = output_dir / f"bi_validation_sample_selection_{TIMESTAMP}.csv"

    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=[
            'sample_idx', 'unique_id', 'site_name', 'developer', 'state_abbr',
            'county', 'status', 'latitude', 'longitude', 'capacity_mw', 'source'
        ])
        writer.writeheader()

        for i, site in enumerate(sample, 1):
            writer.writerow({
                'sample_idx': i,
                'unique_id': site.unique_id,
                'site_name': site.site_name or site.campus_name,
                'developer': site.developer,
                'state_abbr': site.state_abbr,
                'county': site.county,
                'status': site.status,
                'latitude': site.latitude,
                'longitude': site.longitude,
                'capacity_mw': site.capacity_mw,
                'source': site.source,
            })

    return str(filepath)

def export_match_results(results: List[MatchResult], output_dir: Path) -> str:
    """Export match results to CSV."""
    filepath = output_dir / f"bi_validation_match_results_{TIMESTAMP}.csv"

    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        fieldnames = list(results[0].to_dict().keys()) if results else []
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for result in results:
            writer.writerow(result.to_dict())

    return str(filepath)

def generate_site_analysis_report(results: List[MatchResult], output_dir: Path) -> str:
    """Generate detailed site-by-site analysis report per plan template."""
    filepath = output_dir / f"bi_validation_site_analysis_{TIMESTAMP}.md"

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write("# BI Air-Permit Dataset - Site-by-Site Analysis\n\n")
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write("---\n\n")

        for i, result in enumerate(results, 1):
            site = result.our_site
            bi = result.bi_record

            f.write(f"## Site {i}: {site.site_name or site.campus_name or site.unique_id}\n\n")

            f.write("**Our Record:**\n")
            f.write(f"- Developer/Holding Co: {site.developer}\n")
            f.write(f"- Location: ({site.latitude}, {site.longitude}) / {site.state_abbr}\n")
            f.write(f"- Status: {site.status}\n")
            f.write(f"- Tenant: Unknown\n\n")

            f.write(f"**BI Match Found:** {'Yes' if result.match_found else 'No'}\n\n")

            if result.match_found and bi:
                f.write("**Match Details:**\n")
                f.write(f"- BI Record ID: {bi.bi_id}\n")
                f.write(f"- BI Shell Company: {bi.permit_holder}\n")
                f.write(f"- BI Parent Company: {bi.parent_company or 'Not identified'} ← KEY FINDING\n")
                f.write(f"- Match Confidence: Tier {result.match_tier} ({result.match_confidence})\n")
                f.write(f"- Distance: {result.distance_meters} meters\n")
                f.write(f"- Name Match Score: {result.name_match_score}%\n\n")

                f.write("**Validation:**\n")
                f.write(f"- [{'x' if result.geographic_verified else ' '}] Geographic match confirmed (map check)\n")
                f.write(f"- [{'x' if result.company_logic_valid else ' '}] Company name logic makes sense\n")
                f.write(f"- [{'x' if result.parent_plausible else ' '}] Parent company plausible\n\n")

            f.write(f"**Intelligence Gained:** {result.intelligence_gained}\n\n")

            if result.notes:
                f.write("**Notes:**\n")
                for note in result.notes:
                    f.write(f"- {note}\n")
                f.write("\n")

            f.write("---\n\n")

    return str(filepath)

def generate_executive_summary(metrics: Dict, results: List[MatchResult], output_dir: Path) -> str:
    """Generate executive summary report per plan template."""
    filepath = output_dir / f"bi_validation_executive_summary_{TIMESTAMP}.md"

    # Find notable discoveries
    notable = []
    for r in results:
        if r.intelligence_gained == 'Full' and r.bi_record:
            hs = identify_hyperscaler(r.bi_record.parent_company)
            notable.append(f"Site '{r.our_site.site_name or r.our_site.unique_id}' ({r.our_site.state_abbr}) "
                          f"identified as {hs}-linked via '{r.bi_record.permit_holder}'")

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write("# BI Air-Permit Dataset Evaluation Summary\n\n")
        f.write(f"**Date:** {datetime.now().strftime('%Y-%m-%d')}\n")
        f.write(f"**Analyst:** [Your Name]\n")
        f.write(f"**Sample Size:** {metrics['total_sample']} sites\n\n")

        f.write("## Key Findings\n\n")
        f.write("| Metric | Result |\n")
        f.write("|--------|--------|\n")
        f.write(f"| BI Coverage of Our Sample | {metrics['coverage_count']}/{metrics['total_sample']} ({metrics['coverage_pct']:.1f}%) |\n")
        f.write(f"| New Parent Company IDs (Full) | {metrics['full_id_count']}/{metrics['total_sample']} ({metrics['full_id_pct']:.1f}%) |\n")
        f.write(f"| Partial Parent IDs | {metrics['partial_id_count']}/{metrics['total_sample']} ({metrics['partial_id_pct']:.1f}%) |\n")
        f.write(f"| Actionable Intelligence Rate | {metrics['new_intel_pct']:.1f}% of matches |\n\n")

        f.write("## Recommendation\n\n")
        f.write(f"**{metrics['recommendation']}** for full dataset acquisition\n\n")
        f.write(f"_{metrics['recommendation_detail']}_\n\n")

        if notable:
            f.write("## Notable Discoveries\n\n")
            for i, discovery in enumerate(notable, 1):
                f.write(f"{i}. {discovery}\n")
            f.write("\n")

        f.write("## Match Quality Distribution\n\n")
        f.write("| Tier | Confidence | Count |\n")
        f.write("|------|------------|-------|\n")
        for tier_name, count in sorted(metrics['tier_distribution'].items()):
            tier_num = tier_name.split()[-1]
            confidence = MATCH_TIERS.get(f'tier_{tier_num}', {}).get('confidence', 'Unknown')
            f.write(f"| {tier_name} | {confidence} | {count} |\n")
        f.write("\n")

        f.write("## Limitations\n\n")
        f.write(f"- Sample represents a spot-check of {metrics['total_sample']} sites from the full unknown-tenant population\n")
        f.write("- BI data vintage may not include recent 2025/2026 developments\n")
        f.write("- Spatial matching may miss sites with coordinate discrepancies >1km\n")
        f.write("- Company name matching relies on fuzzy logic and may miss unusual spellings\n\n")

        f.write("## Next Steps\n\n")
        if metrics['recommendation'] in ['STRONGLY RECOMMEND', 'RECOMMEND']:
            f.write("1. [ ] Pursue full dataset acquisition from Business Insider\n")
            f.write("2. [ ] Develop automated integration pipeline\n")
            f.write("3. [ ] Expand validation to full unknown-tenant population\n")
        else:
            f.write("1. [ ] Document findings for reference\n")
            f.write("2. [ ] Consider alternative data sources for parent company identification\n")
            f.write("3. [ ] Re-evaluate if BI methodology changes\n")

    return str(filepath)

def generate_html_report(metrics: Dict, results: List[MatchResult], output_dir: Path) -> str:
    """Generate interactive HTML report with charts."""
    filepath = output_dir / f"bi_validation_report_{TIMESTAMP}.html"

    # Prepare chart data
    intel_data = {
        'labels': ['Full ID', 'Partial ID', 'No Match', 'Match/No Value'],
        'values': [
            metrics['full_id_count'],
            metrics['partial_id_count'],
            metrics['no_match_count'],
            metrics['match_no_value_count']
        ],
        'colors': ['#28a745', '#ffc107', '#dc3545', '#6c757d']
    }

    tier_labels = list(metrics['tier_distribution'].keys())
    tier_values = list(metrics['tier_distribution'].values())

    html = f'''<!DOCTYPE html>
<html>
<head>
    <title>BI Air-Permit Dataset Validation Report</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 20px; background: #f5f5f5; }}
        .container {{ max-width: 1200px; margin: 0 auto; }}
        .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; border-radius: 10px; margin-bottom: 20px; }}
        .card {{ background: white; border-radius: 10px; padding: 20px; margin-bottom: 20px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
        .metric-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; }}
        .metric {{ text-align: center; padding: 15px; border-radius: 8px; background: #f8f9fa; }}
        .metric-value {{ font-size: 2em; font-weight: bold; }}
        .metric-label {{ color: #666; font-size: 0.9em; }}
        .recommendation {{ padding: 20px; border-radius: 8px; font-size: 1.2em; text-align: center; }}
        .recommendation.strong {{ background: #d4edda; color: #155724; }}
        .recommendation.recommend {{ background: #fff3cd; color: #856404; }}
        .recommendation.consider {{ background: #cce5ff; color: #004085; }}
        .recommendation.not-useful {{ background: #f8d7da; color: #721c24; }}
        .chart-container {{ height: 300px; }}
        table {{ width: 100%; border-collapse: collapse; }}
        th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }}
        th {{ background: #f8f9fa; }}
        .match-yes {{ color: #28a745; font-weight: bold; }}
        .match-no {{ color: #dc3545; }}
        .intel-full {{ background: #d4edda; }}
        .intel-partial {{ background: #fff3cd; }}
        .intel-none {{ background: #f8f9fa; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🔍 BI Air-Permit Dataset Validation Report</h1>
            <p>Evaluating parent company identification capability | Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}</p>
        </div>

        <div class="card">
            <h2>📊 Key Metrics</h2>
            <div class="metric-grid">
                <div class="metric">
                    <div class="metric-value" style="color: #28a745;">{metrics['full_id_count']}</div>
                    <div class="metric-label">Full Parent IDs</div>
                </div>
                <div class="metric">
                    <div class="metric-value" style="color: #ffc107;">{metrics['partial_id_count']}</div>
                    <div class="metric-label">Partial Parent IDs</div>
                </div>
                <div class="metric">
                    <div class="metric-value" style="color: #17a2b8;">{metrics['coverage_count']}/{metrics['total_sample']}</div>
                    <div class="metric-label">BI Coverage</div>
                </div>
                <div class="metric">
                    <div class="metric-value">{metrics['new_intel_pct']:.1f}%</div>
                    <div class="metric-label">Intel Rate (of matches)</div>
                </div>
            </div>
        </div>

        <div class="card recommendation {'strong' if 'STRONGLY' in metrics['recommendation'] else 'recommend' if 'RECOMMEND' in metrics['recommendation'] else 'consider' if 'CONSIDER' in metrics['recommendation'] else 'not-useful'}">
            <strong>RECOMMENDATION:</strong> {metrics['recommendation']}<br>
            <small>{metrics['recommendation_detail']}</small>
        </div>

        <div class="card">
            <h2>📈 Intelligence Distribution</h2>
            <div class="chart-container">
                <canvas id="intelChart"></canvas>
            </div>
        </div>

        <div class="card">
            <h2>🎯 Match Tier Distribution</h2>
            <div class="chart-container">
                <canvas id="tierChart"></canvas>
            </div>
        </div>

        <div class="card">
            <h2>📋 Site-by-Site Results</h2>
            <table>
                <thead>
                    <tr>
                        <th>#</th>
                        <th>Site Name</th>
                        <th>State</th>
                        <th>Our Developer</th>
                        <th>Match</th>
                        <th>BI Parent</th>
                        <th>Intelligence</th>
                        <th>Tier</th>
                    </tr>
                </thead>
                <tbody>
'''

    for i, r in enumerate(results, 1):
        match_class = 'match-yes' if r.match_found else 'match-no'
        intel_class = f'intel-{r.intelligence_gained.lower()}'
        bi_parent = r.bi_record.parent_company if r.bi_record and r.bi_record.parent_company else '-'
        tier = f"Tier {r.match_tier}" if r.match_tier else '-'

        html += f'''                    <tr class="{intel_class}">
                        <td>{i}</td>
                        <td>{r.our_site.site_name or r.our_site.unique_id}</td>
                        <td>{r.our_site.state_abbr or '-'}</td>
                        <td>{r.our_site.developer or '-'}</td>
                        <td class="{match_class}">{'✓' if r.match_found else '✗'}</td>
                        <td>{bi_parent}</td>
                        <td>{r.intelligence_gained}</td>
                        <td>{tier}</td>
                    </tr>
'''

    html += f'''                </tbody>
            </table>
        </div>
    </div>

    <script>
        // Intelligence Distribution Chart
        new Chart(document.getElementById('intelChart'), {{
            type: 'doughnut',
            data: {{
                labels: {json.dumps(intel_data['labels'])},
                datasets: [{{
                    data: {json.dumps(intel_data['values'])},
                    backgroundColor: {json.dumps(intel_data['colors'])}
                }}]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                plugins: {{
                    legend: {{ position: 'right' }}
                }}
            }}
        }});

        // Tier Distribution Chart
        new Chart(document.getElementById('tierChart'), {{
            type: 'bar',
            data: {{
                labels: {json.dumps(tier_labels)},
                datasets: [{{
                    label: 'Matches',
                    data: {json.dumps(tier_values)},
                    backgroundColor: '#667eea'
                }}]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                scales: {{
                    y: {{ beginAtZero: true, ticks: {{ stepSize: 1 }} }}
                }}
            }}
        }});
    </script>
</body>
</html>'''

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(html)

    return str(filepath)

# ============================================================================
# MAIN EXECUTION
# ============================================================================

def main(bi_dataset_path: str = None):
    """
    Main execution function for BI Air-Permit Dataset Validation Study.

    Args:
        bi_dataset_path: Path to the BI dataset CSV file. If None, will prompt or use default.
    """
    print("\n" + "="*70)
    print("BI AIR-PERMIT DATASET VALIDATION STUDY")
    print("="*70)
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Ensure output directory exists
    output_dir = Path(OUTPUT_DIR)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Default BI dataset path
    if bi_dataset_path is None:
        bi_dataset_path = r"C:\Users\ptanderson\Downloads\Pipeline_Ingestion\BI_AirPermit_Dataset.csv"

    # =========================================================================
    # PHASE 1: Data Preparation & Sample Selection
    # =========================================================================

    # Load pipeline data
    pipeline_data = load_pipeline_data()

    if not pipeline_data:
        print("\n  ERROR: No eligible records found in pipeline data.")
        print("  Ensure gold_buildings has records with developer but no known tenant.")
        return None

    # Stratified sample selection
    sample = stratified_sample_selection(pipeline_data, SAMPLE_SIZE)

    # Export sample selection
    sample_file = export_sample_selection(sample, output_dir)
    print(f"\n  Sample selection exported to: {sample_file}")

    # Load BI dataset
    bi_records = load_bi_dataset(bi_dataset_path)

    if not bi_records:
        print("\n  WARNING: BI dataset not loaded. Running in SIMULATION MODE.")
        print("  To run full analysis, place BI dataset at:")
        print(f"    {bi_dataset_path}")
        print("\n  Continuing with empty BI dataset to demonstrate workflow...")

    # =========================================================================
    # PHASE 2: Matching Methodology
    # =========================================================================

    results = run_matching(sample, bi_records)

    # =========================================================================
    # PHASE 3: Evaluation Metrics
    # =========================================================================

    metrics = calculate_metrics(results)

    # =========================================================================
    # PHASE 4: Documentation & Reporting
    # =========================================================================

    print("\n" + "="*70)
    print("PHASE 4: Generating Reports")
    print("="*70)

    # Export match results
    results_file = export_match_results(results, output_dir)
    print(f"  Match results exported to: {results_file}")

    # Generate site analysis report
    analysis_file = generate_site_analysis_report(results, output_dir)
    print(f"  Site analysis exported to: {analysis_file}")

    # Generate executive summary
    summary_file = generate_executive_summary(metrics, results, output_dir)
    print(f"  Executive summary exported to: {summary_file}")

    # Generate HTML report
    html_file = generate_html_report(metrics, results, output_dir)
    print(f"  HTML report exported to: {html_file}")

    # =========================================================================
    # SUMMARY
    # =========================================================================

    print("\n" + "="*70)
    print("VALIDATION STUDY COMPLETE")
    print("="*70)
    print(f"\n  Sample Size: {len(sample)} sites")
    print(f"  BI Coverage: {metrics['coverage_count']} ({metrics['coverage_pct']:.1f}%)")
    print(f"  Full Parent IDs: {metrics['full_id_count']} ({metrics['full_id_pct']:.1f}%)")
    print(f"  Recommendation: {metrics['recommendation']}")
    print(f"\n  All outputs saved to: {output_dir}")
    print(f"\n  Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    return {
        'sample': sample,
        'results': results,
        'metrics': metrics,
        'output_files': {
            'sample_selection': sample_file,
            'match_results': results_file,
            'site_analysis': analysis_file,
            'executive_summary': summary_file,
            'html_report': html_file,
        }
    }

# ============================================================================
# EXECUTE
# ============================================================================

if __name__ == "__main__":
    try:
        # Check for command line argument for BI dataset path
        bi_path = sys.argv[1] if len(sys.argv) > 1 else None
        results = main(bi_path)
    except Exception as e:
        print(f"\nERROR: {str(e)}")
        import traceback
        traceback.print_exc()
else:
    # Running in ArcGIS Pro Python window
    print("\n  To run the validation study, call:")
    print("    results = main(bi_dataset_path='path/to/bi_dataset.csv')")
    print("\n  Or run without arguments to use default path:")
    print("    results = main()")
