"""
Authority Configuration for Consensus Layer Generation

This module defines the source authority hierarchy and field-level priority matrices
used to determine "Best Available Value" when building consensus records.

Created: January 6, 2026
Version: 1.1 (Updated: Essential Site Integration)
Related Doc: 00_docs/workflows/CONSENSUS_LAYER_DESIGN.md
"""

# =============================================================================
# ESSENTIAL SITE UCIDs (High-Priority Targets)
# =============================================================================
# These sites were identified as "Essential" data centers for focused analysis.
# They receive highest priority in weighted consensus scoring.
# Generated from integrate_essential_list.py matching.

ESSENTIAL_SITE_UCIDS = [
    "AWS-BECKER",
    "AWS-BERWICK-1", "AWS-BERWICK-2", "AWS-BERWICK-3", "AWS-BERWICK-4",
    "AWS-BERWICK-5", "AWS-BERWICK-6", "AWS-BERWICK-7", "AWS-BERWICK-8", "AWS-BERWICK-9",
    "AWS-CANTON-1", "AWS-CANTON-2", "AWS-CANTON-3", "AWS-CANTON-4", "AWS-CANTON-5", "AWS-CANTON-6",
    "AWS-COVINGTON",
    "AWS-JACKSON-1", "AWS-JACKSON-2", "AWS-JACKSON-3", "AWS-JACKSON-4", "AWS-JACKSON-5",
    "AWS-JEFFERSONVILLE-1", "AWS-JEFFERSONVILLE-2", "AWS-JEFFERSONVILLE-3", "AWS-JEFFERSONVILLE-4",
    "AWS-LOUISA-1", "AWS-LOUISA-2", "AWS-LOUISA-3", "AWS-LOUISA-4",
    "AWS-NEWCARLISLE-1", "AWS-NEWCARLISLE-2", "AWS-NEWCARLISLE-3",
    "AWS-NEWCARLISLE-4", "AWS-NEWCARLISLE-5", "AWS-NEWCARLISLE-6",
    "AWS-RIDGELAND-1", "AWS-RIDGELAND-2", "AWS-RIDGELAND-3", "AWS-RIDGELAND-4",
    "AWS-SUWANEE",
    "CRUS-ABILENE-1", "CRUS-ABILENE-2", "CRUS-ABILENE-3", "CRUS-ABILENE-4", "CRUS-ABILENE-5",
    "CRUS-ABILENE-6", "CRUS-ABILENE-7", "CRUS-ABILENE-8", "CRUS-ABILENE-9", "CRUS-ABILENE-10",
    "CRUS-CARPENTER",
    "EDGE-ATLANTA-5", "EDGE-ATLANTA-6", "EDGE-UNIONCITY",
    "GOOG-FORTWAYNE-1", "GOOG-FORTWAYNE-2", "GOOG-FORTWAYNE-3", "GOOG-FORTWAYNE-4", "GOOG-FORTWAYNE-5",
    "GOOG-FORTWAYNE-6", "GOOG-FORTWAYNE-7", "GOOG-FORTWAYNE-8", "GOOG-FORTWAYNE-9", "GOOG-FORTWAYNE-10",
    "GOOG-KANSASCITY-1", "GOOG-KANSASCITY-2", "GOOG-KANSASCITY-3", "GOOG-KANSASCITY-4", "GOOG-KANSASCITY-5",
    "GOOG-KANSASCITY-6", "GOOG-KANSASCITY-7", "GOOG-KANSASCITY-8", "GOOG-KANSASCITY-9", "GOOG-KANSASCITY-10",
    "GOOG-WESTMEMPHIS-1", "GOOG-WESTMEMPHIS-2", "GOOG-WESTMEMPHIS-3", "GOOG-WESTMEMPHIS-4", "GOOG-WESTMEMPHIS-5",
    "MSFT-CASTROVILLE-1", "MSFT-CASTROVILLE-2", "MSFT-CASTROVILLE-3",
    "MSFT-CHEYENNE-1", "MSFT-CHEYENNE-2", "MSFT-CHEYENNE-3", "MSFT-CHEYENNE-4", "MSFT-CHEYENNE-5",
    "MSFT-CHEYENNE-6", "MSFT-CHEYENNE-7", "MSFT-CHEYENNE-8", "MSFT-CHEYENNE-9",
    "MSFT-JOHNSTOWN", "MSFT-MOUNTPLEASANT-1", "MSFT-MOUNTPLEASANT-2", "MSFT-MOUNTPLEASANT-3",
    "MSFT-MOUNTPLEASANT-4", "MSFT-MOUNTPLEASANT-5", "MSFT-MOUNTPLEASANT-6", "MSFT-MOUNTPLEASANT-7",
    "MSFT-MOUNTPLEASANT-8", "MSFT-MOUNTPLEASANT-9", "MSFT-MOUNTPLEASANT-10",
    "MSFT-NEWALBANY", "MSFT-PATASKALA", "MSFT-ROME",
    "MSFT-ROXBORO-1", "MSFT-ROXBORO-2", "MSFT-ROXBORO-3", "MSFT-ROXBORO-4",
    "MSFT-SANANTONIO-1", "MSFT-SANANTONIO-2", "MSFT-SANANTONIO-3", "MSFT-SANANTONIO-4", "MSFT-SANANTONIO-5",
    "MSFT-SANANTONIO-6", "MSFT-SANANTONIO-7", "MSFT-SANANTONIO-8", "MSFT-SANANTONIO-9",
    "MSFT-SILVERSPRINGS",
    "SOFT-ROSEBUD",
    "STACK-SANTATERESA",
    "SWCH-SPARKS-1", "SWCH-SPARKS-2", "SWCH-SPARKS-3", "SWCH-SPARKS-4", "SWCH-SPARKS-5",
    "TRAC-ASHLAND-EAST", "TRAC-ASHLAND-WEST",
    "VDC-ABILENE-EAST", "VDC-ABILENE-WEST",
    "VDC-PORTWASHINGTON-1", "VDC-PORTWASHINGTON-2", "VDC-PORTWASHINGTON-3", "VDC-PORTWASHINGTON-4",
    "XAI-MEMPHIS-1", "XAI-MEMPHIS-2", "XAI-MEMPHIS-3",
]

# Convert to set for O(1) lookup
ESSENTIAL_SITE_SET = set(ESSENTIAL_SITE_UCIDS)

# =============================================================================
# SOURCE AUTHORITY RANKING
# =============================================================================
# Overall authority ranking for geometry and default attributes.
# Lower number = higher authority

AUTHORITY_RANKING = {
    "Meta Canonical": 1,      # Internal ground truth, verified data
    "Semianalysis": 2,        # 43.2% accuracy vs Meta (best external)
    "DataCenterHawk": 3,      # 39.2% accuracy, building-level detail (Hyper)
    "DCH Lease": 4,           # Leased facility specifics
    "NPM": 5,                 # US announced projects
    "DataCenterMap": 6,       # Volume (37% of records), sparse capacity
}

# Reverse lookup for convenience
AUTHORITY_SOURCES = {v: k for k, v in AUTHORITY_RANKING.items()}

# =============================================================================
# FIELD-LEVEL AUTHORITY MATRIX
# =============================================================================
# Different fields have different authoritative sources.
# When building consensus records, use the first available value based on this priority.

FIELD_AUTHORITY_MATRIX = {
    # Geographic fields
    "latitude": ["Meta Canonical", "Semianalysis", "DataCenterHawk", "DataCenterMap", "DCH Lease", "NPM"],
    "longitude": ["Meta Canonical", "Semianalysis", "DataCenterHawk", "DataCenterMap", "DCH Lease", "NPM"],

    # Identity fields
    "company_clean": ["Meta Canonical", "DataCenterHawk", "Semianalysis", "DataCenterMap", "DCH Lease", "NPM"],
    "canonical_name": ["Meta Canonical", "DataCenterHawk", "Semianalysis", "DataCenterMap", "DCH Lease", "NPM"],

    # Status fields
    "facility_status": ["Meta Canonical", "DataCenterHawk", "DCH Lease", "NPM", "Semianalysis", "DataCenterMap"],

    # Capacity fields - note different priorities based on data quality
    "commissioned_power_mw": ["Meta Canonical", "DataCenterHawk", "Semianalysis", "DCH Lease", "DataCenterMap"],
    "full_capacity_mw": ["Semianalysis", "DataCenterHawk", "DCH Lease", "NPM", "DataCenterMap", "Meta Canonical"],
    "uc_power_mw": ["Semianalysis", "DataCenterHawk", "NPM", "Meta Canonical"],
    "planned_power_mw": ["Semianalysis", "NPM", "DataCenterHawk", "Meta Canonical"],

    # Building/facility details
    "building_count": ["DataCenterHawk", "Meta Canonical", "Semianalysis", "DataCenterMap"],
    "sqft": ["DCH Lease", "DataCenterHawk", "DataCenterMap", "Semianalysis"],

    # Forecast fields (Semianalysis exclusive)
    "mw_2024": ["Semianalysis"],
    "mw_2025": ["Semianalysis"],
    "mw_2026": ["Semianalysis"],
    "mw_2027": ["Semianalysis"],
    "mw_2028": ["Semianalysis"],
    "mw_2029": ["Semianalysis"],
    "mw_2030": ["Semianalysis"],
    "mw_2031": ["Semianalysis"],
    "mw_2032": ["Semianalysis"],

    # Freshness - always prefer most recent
    "data_vintage": ["MOST_RECENT"],  # Special handling: take most recent date across sources
}

# =============================================================================
# PUE ADJUSTMENT RULES
# =============================================================================
# Initially we thought DCH Hyper reported facility power, but testing confirmed
# DCH reports IT capacity (same definition as Meta). NO adjustment needed.
# See PIPELINE_DOCUMENTATION.md Session 10 findings: 17.6% MAPE without adjustment
# vs 23.5% MAPE with ÷1.3 adjustment. Keep all sources at None.

PUE_ADJUSTMENTS = {
    "Meta Canonical": None,       # Reports IT Load - use directly
    "Semianalysis": None,         # Reports IT Capacity - use directly
    "DataCenterHawk": None,       # Reports IT Capacity - NO adjustment needed (confirmed Session 10)
    "DCH Lease": None,            # Reports IT Capacity - use directly
    "NPM": None,                  # Design Capacity - context-dependent
    "DataCenterMap": None,        # Sparse data - use as-is
}

# Fields that require PUE adjustment
PUE_ADJUSTED_FIELDS = [
    "commissioned_power_mw",
    "full_capacity_mw",
    "uc_power_mw",
]

# =============================================================================
# SOURCE METADATA
# =============================================================================
# Additional metadata about each source for documentation and reporting

SOURCE_METADATA = {
    "Meta Canonical": {
        "description": "Internal Meta authoritative data",
        "accuracy_vs_meta": 1.0,  # Ground truth
        "coverage": 0.014,        # 1.4% of records
        "best_for": ["status", "it_load", "ownership"],
        "data_vintage_field": "data_vintage",
    },
    "Semianalysis": {
        "description": "Third-party analyst with IT capacity focus",
        "accuracy_vs_meta": 0.432,  # 43.2%
        "coverage": 0.241,          # 24.1% of records
        "best_for": ["full_capacity", "forecasts", "mw_2024-2032"],
        "data_vintage_field": "data_vintage",
    },
    "DataCenterHawk": {
        "description": "DCH Hyperscale - building-level facility data",
        "accuracy_vs_meta": 0.392,  # 39.2%
        "coverage": 0.311,          # 31.1% of records (Hyper + Lease)
        "best_for": ["commissioned", "building_count", "facility_power"],
        "data_vintage_field": "data_vintage",
        "power_type": "facility",   # Reports facility power
    },
    "DCH Lease": {
        "description": "DCH Lease - leased facility specifics",
        "accuracy_vs_meta": None,
        "coverage": 0.228,
        "best_for": ["sqft", "lease_details", "tenant"],
        "data_vintage_field": "data_vintage",
        "power_type": "it",
    },
    "NPM": {
        "description": "NewProjectMedia - US announced projects",
        "accuracy_vs_meta": None,
        "coverage": 0.062,  # 6.2%
        "best_for": ["announced_projects", "costs"],
        "data_vintage_field": "data_vintage",
    },
    "DataCenterMap": {
        "description": "Geographic coverage, sparse capacity",
        "accuracy_vs_meta": None,
        "coverage": 0.373,  # 37.3%
        "best_for": ["geographic_coverage"],
        "data_vintage_field": "data_vintage",
    },
}

# =============================================================================
# CONFIDENCE SCORING WEIGHTS
# =============================================================================
# Weights for calculating overall confidence score (0-1)

CONFIDENCE_WEIGHTS = {
    "source_count": 0.20,      # More sources = higher confidence
    "has_meta_canonical": 0.30, # Meta Canonical presence is high value
    "data_freshness": 0.25,    # Days since last update
    "field_coverage": 0.15,    # % of key fields populated
    "source_agreement": 0.10,  # Do sources agree on key values?
}

# Key fields used for field coverage calculation
KEY_FIELDS_FOR_COVERAGE = [
    "company_clean",
    "facility_status",
    "commissioned_power_mw",
    "full_capacity_mw",
    "latitude",
    "longitude",
    "building_count",
]

# =============================================================================
# XB FILTER CONFIGURATION
# =============================================================================
# Hyperscaler companies to keep as distinct values for XB filtering.
# All others become "Colo - All Other"

HYPERSCALER_COMPANIES = [
    "AWS",
    "Microsoft",
    "Google",
    "Meta",
    "Apple",
    "Oracle",
    "Alibaba",
    "xAI",
]

# Major Colocation / Enterprise providers (Tier 2 for consensus scoring)
MAJOR_COLO_COMPANIES = [
    "Equinix",
    "Digital Realty",
    "CyrusOne",
    "QTS",
    "CoreSite",
    "Vantage",
    "DataBank",
    "Switch",
    "Stack Infrastructure",
    "STACK",
    "Compass",
    "EdgeCore",
    "Prime",
    "CloudHQ",
    "Stream",
    "Aligned",
    "NTT",
    "Lumen",
    "Iron Mountain",
    "Flexential",
]

DEFAULT_COLO_LABEL = "Colo - All Other"

# =============================================================================
# COMPANY TIER CLASSIFICATION (for Weighted Consensus Scoring)
# =============================================================================
# Used to weight consensus metrics by business value

COMPANY_TIER_WEIGHTS = {
    "hyperscaler": 0.60,   # Frontier companies - highest business value
    "major_colo": 0.30,    # Large colo/enterprise - strategic context
    "other": 0.10,         # Unknown/small operators - geographic coverage
}


def get_company_tier(company: str) -> str:
    """
    Classify a company into a tier for weighted consensus scoring.

    Returns: "hyperscaler", "major_colo", or "other"
    """
    if not company:
        return "other"

    company_upper = company.upper().strip()

    # Check hyperscalers first
    for hyperscaler in HYPERSCALER_COMPANIES:
        if hyperscaler.upper() in company_upper or company_upper in hyperscaler.upper():
            return "hyperscaler"

    # Check major colo
    for colo in MAJOR_COLO_COMPANIES:
        if colo.upper() in company_upper or company_upper in colo.upper():
            return "major_colo"

    return "other"

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_authority_rank(source: str) -> int:
    """Get authority rank for a source. Higher rank = lower number."""
    return AUTHORITY_RANKING.get(source, 999)


def get_pue_adjustment(source: str) -> float | None:
    """Get PUE adjustment factor for a source. Returns None if no adjustment needed."""
    return PUE_ADJUSTMENTS.get(source)


def apply_pue_adjustment(source: str, field: str, value: float) -> float:
    """Apply PUE adjustment if needed."""
    if value is None:
        return None

    adjustment = get_pue_adjustment(source)
    if adjustment and field in PUE_ADJUSTED_FIELDS:
        return value / adjustment
    return value


def get_company_filter(company: str) -> str:
    """Get XB filter value for a company name."""
    if not company:
        return DEFAULT_COLO_LABEL

    # Normalize and check
    company_upper = company.upper().strip()
    for hyperscaler in HYPERSCALER_COMPANIES:
        if hyperscaler.upper() in company_upper or company_upper in hyperscaler.upper():
            return hyperscaler

    return DEFAULT_COLO_LABEL


def get_field_priority_list(field: str) -> list:
    """Get the source priority list for a field."""
    return FIELD_AUTHORITY_MATRIX.get(field, list(AUTHORITY_RANKING.keys()))


# =============================================================================
# VALIDATION
# =============================================================================

def validate_config():
    """Validate configuration consistency."""
    errors = []

    # Check all sources in AUTHORITY_RANKING are in SOURCE_METADATA
    for source in AUTHORITY_RANKING:
        if source not in SOURCE_METADATA:
            errors.append(f"Source '{source}' in AUTHORITY_RANKING but not in SOURCE_METADATA")

    # Check all sources in field matrix are valid
    for field, sources in FIELD_AUTHORITY_MATRIX.items():
        for source in sources:
            if source not in AUTHORITY_RANKING and source != "MOST_RECENT":
                errors.append(f"Unknown source '{source}' in FIELD_AUTHORITY_MATRIX[{field}]")

    if errors:
        print("⚠️ Configuration validation errors:")
        for error in errors:
            print(f"  - {error}")
        return False

    print("✅ Configuration validated successfully")
    return True


if __name__ == "__main__":
    validate_config()

    print("\n📊 Authority Ranking:")
    for rank in sorted(AUTHORITY_SOURCES.keys()):
        print(f"  {rank}. {AUTHORITY_SOURCES[rank]}")

    print("\n📋 Field-Level Priorities (first 5 fields):")
    for field, sources in list(FIELD_AUTHORITY_MATRIX.items())[:5]:
        print(f"  {field}: {' > '.join(sources[:3])}...")
