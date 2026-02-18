# Match Confidence Analysis: UCID & SA vs DCH

**Created:** 2026-02-11
**Purpose:** Analyze match confidence in clustered areas and identify validation opportunities
**Status:** 📋 ANALYSIS & RECOMMENDATIONS

---

## Executive Summary

### Current State Assessment

| System | Matching Criteria | Confidence Level | Key Gap |
|--------|-------------------|------------------|---------|
| **UCID Generation** | Company + Proximity | 🟡 Medium | No facility type filter |
| **SA vs DCH Comparison** | Proximity only (post-hoc company check) | 🔴 Low | Company NOT used for matching |

### Answer to Your Question

> "Is there any way to incorporate data validation?"

**Yes.** I've identified **5 validation strategies** that can be implemented:

1. **Ground Truth Validation** — Compare UCID/matches against Meta Canonical
2. **Cross-Source Agreement Score** — Flag matches where multiple sources disagree
3. **Attribute Consistency Scoring** — Check if matched records have similar non-spatial attributes
4. **Cluster Density Analysis** — Flag high-density areas requiring manual review
5. **Match Confidence Tiers** — Classify matches as High/Medium/Low confidence

---

## 1. Current Matching Logic Analysis

### 1.1 UCID Generation (`generate_text_ucid.py`)

**What it uses:**
| Criterion | Used? | Code Reference |
|-----------|-------|----------------|
| Proximity | ✅ Yes | `haversine_distance() <= tolerance_m` (250m or 1000m) |
| Company name | ✅ Yes | Groups by `company` before clustering |
| Granularity | ❌ No | Not checked |
| Facility type (hyper/colo) | ❌ No | Not checked |
| Facility status | ❌ No | Not checked |

**Algorithm:**
```python
# Simplified from generate_text_ucid.py lines 291-345
def cluster_by_company_and_proximity(records, tolerance_m):
    # Step 1: Group by company
    by_company = defaultdict(list)
    for rec in records:
        by_company[rec['company']].append(rec)

    # Step 2: For each company, cluster by proximity (transitive)
    for company, company_records in by_company.items():
        for rec in company_records:
            # Find all records within tolerance (transitive expansion)
            for other in company_records:
                if haversine_distance(rec, other) <= tolerance_m:
                    # Same cluster
```

**Key Insight:** UCID clustering is **company-aware** but does **not** distinguish between:
- Hyperscale vs Colo facilities
- Building vs Campus records
- Operational vs Under Construction

### 1.2 SA vs DCH Comparison (`compare_sa_vs_dch_v2.py`)

**What it uses:**
| Criterion | Used for Matching? | Used Post-Match? |
|-----------|-------------------|------------------|
| Proximity | ✅ Yes (500m default) | Distance reported |
| Company name | ❌ **NO** | ✅ `company_match` flag calculated |
| Granularity | ❌ No | ✅ `granularity_match` flag calculated |
| Facility type | ❌ No | ❌ Not checked |
| Facility status | ❌ No | ✅ `status_match` flag calculated |

**Algorithm:**
```python
# Simplified from compare_sa_vs_dch_v2.py lines 347-465
def build_match_sets(sa_records, dch_records, threshold_m=500):
    # Find ALL pairs within threshold (no company filter!)
    for sa_rec in sa_records:
        for dch_rec in dch_records:
            distance = haversine_distance(sa_rec, dch_rec)
            if distance <= threshold_m:
                potential_matches.append(...)

    # Sort by distance, greedily assign closest pairs
    potential_matches.sort(key=distance)
    for match in potential_matches:
        if neither_already_matched:
            matched_pairs.append(match)
            # THEN calculate company_match, granularity_match, etc.
```

**Critical Finding:** The SA vs DCH comparison **does not use company as a matching criterion**. It matches purely by proximity, then checks company match after the fact.

---

## 2. Problem Scenarios in Clustered Areas

### Scenario A: Multi-Tenant Campus (Current Risk: HIGH)

```
Location: Ashburn, VA Data Center Alley
Within 500m radius:
├── Equinix DC15 (colo)
├── AWS IAD-77 (hyperscale)
├── Microsoft MIC-01 (hyperscale)
└── CoreSite VA2 (colo)
```

**Current behavior (SA vs DCH):**
- SA Equinix record → matches to closest DCH record (might be AWS!)
- Capacity comparison is meaningless
- `company_match = False` flag is set, but match already committed

**Current behavior (UCID):**
- ✅ Would NOT merge these (different companies)
- But if SA has "Equinix" and DCH has "Equnix" (typo), no fuzzy match

### Scenario B: Same-Company Multi-Campus (Current Risk: MEDIUM)

```
Location: Columbus, OH (10 miles apart)
├── AWS Columbus North (CMH-14, CMH-15)
├── AWS Columbus South (CMH-08, CMH-09)
└── AWS Columbus West (CMH-21)
```

**With TIGHT tolerance (250m):**
- ✅ Each campus correctly separated
- Buildings within each campus correctly grouped

**With LOOSE tolerance (1000m):**
- ⚠️ Risk of merging nearby campuses if any buildings overlap radius

### Scenario C: Mixed Hyperscale/Colo (Current Risk: LOW for UCID, HIGH for SA vs DCH)

```
Location: Digital Realty building with hyperscale tenant
├── Digital Realty DAL-1 (colo owner)
└── Meta DFW-01 (hyperscale tenant, subleasing from DLR)
```

**Current behavior:**
- UCID: Correctly separates (different companies)
- SA vs DCH: **May incorrectly match** if coordinates are close

---

## 3. Validation Strategies

### Strategy 1: Ground Truth Validation

**Concept:** Use Meta Canonical as ground truth to measure match accuracy.

```python
def validate_against_meta_canonical():
    """
    For each Meta Canonical building:
    1. Find its UCID
    2. Find all other sources assigned to same UCID
    3. Check: Do all sources report the same company?
    4. Calculate: Match accuracy rate
    """
    meta_records = load_meta_canonical()

    validation_results = []
    for meta_rec in meta_records:
        ucid = meta_rec['ucid']

        # Find all records with this UCID
        same_ucid = get_records_by_ucid(ucid)

        # Check company consistency
        companies = set(r['company_clean'] for r in same_ucid)
        if len(companies) > 1:
            validation_results.append({
                'ucid': ucid,
                'issue': 'company_mismatch',
                'companies': list(companies),
                'meta_company': meta_rec['company_clean']
            })

    return validation_results
```

**Output:** Report of UCIDs where sources disagree on company.

### Strategy 2: Cross-Source Agreement Score

**Concept:** Flag matches where sources have significant disagreements.

```python
def calculate_match_confidence(sa_rec, dch_rec, distance_m):
    """
    Score a match based on multiple agreement factors.
    Returns confidence tier: HIGH, MEDIUM, LOW
    """
    score = 0
    max_score = 100

    # Distance factor (0-30 points)
    if distance_m < 100:
        score += 30
    elif distance_m < 250:
        score += 20
    elif distance_m < 500:
        score += 10

    # Company match (0-30 points)
    if check_company_match(sa_rec['company_clean'], dch_rec['company_clean']):
        score += 30
    elif fuzzy_company_match(sa_rec['company_clean'], dch_rec['company_clean']) > 0.8:
        score += 15

    # Granularity match (0-15 points)
    if normalize_granularity(sa_rec) == normalize_granularity(dch_rec):
        score += 15

    # Capacity agreement (0-15 points)
    delta_pct = calculate_capacity_delta(sa_rec, dch_rec)['delta_pct']
    if delta_pct < 10:
        score += 15
    elif delta_pct < 25:
        score += 10
    elif delta_pct < 50:
        score += 5

    # Facility type match (0-10 points) - NEW
    if get_facility_type(sa_rec) == get_facility_type(dch_rec):
        score += 10

    # Tier assignment
    if score >= 80:
        return 'HIGH', score
    elif score >= 50:
        return 'MEDIUM', score
    else:
        return 'LOW', score
```

### Strategy 3: Cluster Density Analysis

**Concept:** Identify high-density areas that need special handling or manual review.

```python
def identify_high_density_clusters():
    """
    Find areas with many facilities within a small radius.
    These are most likely to have matching errors.
    """
    # Grid the world into cells
    CELL_SIZE_DEG = 0.01  # ~1km cells

    cell_counts = defaultdict(list)
    for rec in all_records:
        cell = (round(rec['lat'] / CELL_SIZE_DEG),
                round(rec['lon'] / CELL_SIZE_DEG))
        cell_counts[cell].append(rec)

    # Flag cells with > threshold facilities
    HIGH_DENSITY_THRESHOLD = 10

    high_density_areas = []
    for cell, records in cell_counts.items():
        if len(records) >= HIGH_DENSITY_THRESHOLD:
            # Count unique companies
            companies = set(r['company_clean'] for r in records)

            high_density_areas.append({
                'cell': cell,
                'center_lat': cell[0] * CELL_SIZE_DEG,
                'center_lon': cell[1] * CELL_SIZE_DEG,
                'facility_count': len(records),
                'company_count': len(companies),
                'companies': list(companies),
                'review_priority': 'HIGH' if len(companies) > 3 else 'MEDIUM'
            })

    return sorted(high_density_areas, key=lambda x: -x['facility_count'])
```

**Known High-Density Markets to Watch:**
| Market | Expected Density | Risk Level |
|--------|-----------------|------------|
| Ashburn, VA | Very High (100+ facilities) | 🔴 Critical |
| Dallas-Fort Worth | High (50+ facilities) | 🟡 High |
| Phoenix, AZ | High (40+ facilities) | 🟡 High |
| Chicago, IL | Medium-High (30+) | 🟡 Medium |
| Singapore | High (30+) | 🟡 High |
| Amsterdam | Medium-High (25+) | 🟡 Medium |

### Strategy 4: Attribute Consistency Checks

**Concept:** Even if proximity matches, validate that other attributes are consistent.

```python
def validate_match_attributes(matched_pairs):
    """
    For each matched pair, check attribute consistency.
    Flag pairs with suspicious inconsistencies.
    """
    issues = []

    for pair in matched_pairs:
        sa = pair['sa_record']
        dch = pair['dch_record']

        # Check 1: Company mismatch (critical)
        if not check_company_match(sa['company_clean'], dch['company_clean']):
            issues.append({
                'pair': pair,
                'issue': 'COMPANY_MISMATCH',
                'severity': 'CRITICAL',
                'sa_company': sa['company_clean'],
                'dch_company': dch['company_clean']
            })

        # Check 2: Facility type mismatch (if available)
        sa_type = sa.get('company_clean_filter', '').lower()  # 'hyper' or 'colo'
        dch_type = dch.get('company_clean_filter', '').lower()
        if sa_type and dch_type and sa_type != dch_type:
            issues.append({
                'pair': pair,
                'issue': 'FACILITY_TYPE_MISMATCH',
                'severity': 'HIGH',
                'sa_type': sa_type,
                'dch_type': dch_type
            })

        # Check 3: Capacity order-of-magnitude mismatch
        sa_cap = safe_float(sa.get('full_capacity_mw')) or 0
        dch_cap = safe_float(dch.get('full_capacity_mw')) or 0
        if sa_cap > 0 and dch_cap > 0:
            ratio = max(sa_cap, dch_cap) / min(sa_cap, dch_cap)
            if ratio > 5:  # 5x difference
                issues.append({
                    'pair': pair,
                    'issue': 'CAPACITY_ORDER_OF_MAGNITUDE',
                    'severity': 'HIGH',
                    'sa_capacity': sa_cap,
                    'dch_capacity': dch_cap,
                    'ratio': ratio
                })

        # Check 4: Geographic field mismatch
        if sa.get('city') and dch.get('city'):
            if sa['city'].lower() != dch['city'].lower():
                issues.append({
                    'pair': pair,
                    'issue': 'CITY_MISMATCH',
                    'severity': 'MEDIUM',
                    'sa_city': sa['city'],
                    'dch_city': dch['city']
                })

    return issues
```

### Strategy 5: Facility Type Filtering (NEW)

**Concept:** Add `company_clean_filter` (hyper vs colo) as a matching constraint.

```python
def get_facility_type(record):
    """
    Determine if facility is hyperscale or colocation.
    Uses company_clean_filter if available, else infers from company.
    """
    # Direct field
    ccf = record.get('company_clean_filter', '').lower()
    if ccf in ['hyper', 'hyperscale', 'hyperscaler']:
        return 'HYPER'
    if ccf in ['colo', 'colocation', 'enterprise']:
        return 'COLO'

    # Infer from company
    company = record.get('company_clean', '').lower()

    HYPERSCALERS = ['aws', 'amazon', 'microsoft', 'azure', 'google', 'meta',
                   'facebook', 'apple', 'oracle', 'bytedance', 'alibaba',
                   'xai', 'openai', 'anthropic']

    if any(h in company for h in HYPERSCALERS):
        return 'HYPER'

    MAJOR_COLOS = ['equinix', 'digital realty', 'cyrusone', 'qts', 'vantage',
                  'coresite', 'switch', 'flexential', 'databank', 'compass']

    if any(c in company for c in MAJOR_COLOS):
        return 'COLO'

    return 'UNKNOWN'


def build_match_sets_v3(sa_records, dch_records, threshold_m=500,
                         require_company_match=True,
                         require_type_match=False):
    """
    Enhanced matching with optional company and type filters.
    """
    potential_matches = []

    for sa_rec in sa_records:
        for dch_rec in dch_records:
            distance = haversine_distance(sa_rec, dch_rec)

            if distance > threshold_m:
                continue

            # Optional: Require company match BEFORE matching
            if require_company_match:
                if not check_company_match(sa_rec['company_clean'],
                                          dch_rec['company_clean']):
                    continue

            # Optional: Require facility type match
            if require_type_match:
                if get_facility_type(sa_rec) != get_facility_type(dch_rec):
                    continue

            potential_matches.append({...})

    # Rest of greedy matching...
```

---

## 4. Recommended Implementation

### Phase 1: Add Confidence Scoring (Low Effort, High Value)

Modify `compare_sa_vs_dch_v2.py` to add confidence tiers:

```python
# In matched_pairs loop, add:
confidence_tier, confidence_score = calculate_match_confidence(
    sa_rec, dch_rec, distance_m
)

matched_pairs.append({
    # ... existing fields ...
    'confidence_tier': confidence_tier,
    'confidence_score': confidence_score,
})
```

**Report Enhancement:**
- Add "Match Confidence" column to CSV
- Add "Confidence Distribution" chart to HTML
- Filter low-confidence matches from MAPE calculation

### Phase 2: Add Company-Aware Matching (Medium Effort, High Value)

Modify `build_match_sets()` to require company match:

```python
def build_match_sets(sa_records, dch_records, threshold_m=500,
                     require_company_match=True):  # NEW PARAMETER
```

**Expected Impact:**
- Fewer false matches in clustered areas
- Slight reduction in overall match count (true negatives)
- More meaningful capacity comparisons

### Phase 3: Add High-Density Area Report (Low Effort, Medium Value)

Create new function to identify and report high-density areas:

```python
def generate_density_report():
    """Generate report of high-density areas needing review."""
    high_density = identify_high_density_clusters()

    # Export to CSV for manual review
    export_to_csv(high_density, 'high_density_areas.csv')

    # Add section to HTML report
    add_high_density_section_to_report(high_density)
```

### Phase 4: Ground Truth Validation Dashboard (Higher Effort, High Value)

Create validation script:

```python
# New script: validate_ucid_quality.py
def run_ucid_validation():
    """
    Validate UCID assignments against ground truth.

    Reports:
    1. UCIDs with company disagreement across sources
    2. UCIDs that should be merged (same Meta Canonical building)
    3. UCIDs that should be split (different Meta Canonical buildings)
    """
```

---

## 5. Quick Validation Queries

### Query: Check Company Match Rate in Current Comparison

```python
# After running comparison, check company match rate
def check_company_match_rate(matched_pairs):
    company_matches = sum(1 for p in matched_pairs if p['company_match'])
    total = len(matched_pairs)

    print(f"Company Match Rate: {company_matches}/{total} ({company_matches/total*100:.1f}%)")

    # Show mismatches
    mismatches = [p for p in matched_pairs if not p['company_match']]
    print(f"\nTop 10 Company Mismatches:")
    for p in mismatches[:10]:
        print(f"  SA: {p['sa_record']['company_clean']} ↔ DCH: {p['dch_record']['company_clean']}")
        print(f"      Distance: {p['distance_m']:.0f}m")
```

### Query: Find Multi-Company UCIDs

```python
# Check if any UCIDs have multiple companies (indicates potential merge error)
def find_multi_company_ucids():
    ucid_companies = defaultdict(set)

    with arcpy.da.SearchCursor(GOLD_BUILDINGS, ['ucid', 'company_clean']) as cursor:
        for ucid, company in cursor:
            if ucid and company:
                ucid_companies[ucid].add(company)

    multi_company = {ucid: comps for ucid, comps in ucid_companies.items()
                     if len(comps) > 1}

    print(f"UCIDs with multiple companies: {len(multi_company)}")
    for ucid, comps in list(multi_company.items())[:10]:
        print(f"  {ucid}: {', '.join(comps)}")
```

### Query: Identify Ashburn Area Matches (Known High-Density)

```python
# Check matching quality in Ashburn area specifically
def analyze_ashburn_matches(matched_pairs):
    # Ashburn, VA approximate bounding box
    ASHBURN_LAT_MIN, ASHBURN_LAT_MAX = 38.9, 39.1
    ASHBURN_LON_MIN, ASHBURN_LON_MAX = -77.6, -77.3

    def in_ashburn(rec):
        lat = rec.get('_lat') or 0
        lon = rec.get('_lon') or 0
        return (ASHBURN_LAT_MIN <= lat <= ASHBURN_LAT_MAX and
                ASHBURN_LON_MIN <= lon <= ASHBURN_LON_MAX)

    ashburn_pairs = [p for p in matched_pairs
                    if in_ashburn(p['sa_record']) or in_ashburn(p['dch_record'])]

    print(f"Ashburn area pairs: {len(ashburn_pairs)}")

    # Check company match rate in Ashburn
    company_matches = sum(1 for p in ashburn_pairs if p['company_match'])
    print(f"Company match rate: {company_matches}/{len(ashburn_pairs)} ({company_matches/len(ashburn_pairs)*100:.1f}%)")

    # Show mismatches
    mismatches = [p for p in ashburn_pairs if not p['company_match']]
    print(f"\nAshburn company mismatches ({len(mismatches)}):")
    for p in mismatches[:10]:
        print(f"  SA: {p['sa_record']['company_clean']} ↔ DCH: {p['dch_record']['company_clean']}")
```

---

## 6. Summary of Findings

### Current UCID Generation

| Criterion | Used? | Confidence Impact |
|-----------|-------|-------------------|
| Proximity (250m/1000m) | ✅ | Good for same-company clustering |
| Company name | ✅ | Prevents cross-company merges |
| Granularity | ❌ | May merge building with campus |
| Facility type | ❌ | May merge hyper with colo if same owner |

**UCID Confidence: 🟡 MEDIUM** — Good company filtering, but lacks granularity/type awareness.

### Current SA vs DCH Comparison

| Criterion | Used for Matching? | Used for Filtering Stats? |
|-----------|-------------------|---------------------------|
| Proximity (500m) | ✅ | ✅ Distance reported |
| Company name | ❌ **NO** | ✅ company_match flag |
| Granularity | ❌ No | ✅ granularity_match filter |
| Facility type | ❌ No | ❌ Not implemented |

**SA vs DCH Confidence: 🔴 LOW** — No company filtering means high risk of false matches in clustered areas.

### Recommended Priority

1. **HIGH:** Add company-aware matching to SA vs DCH comparison
2. **HIGH:** Add confidence scoring to all matched pairs
3. **MEDIUM:** Add facility type (hyper/colo) as matching criterion
4. **MEDIUM:** Generate high-density area report for manual review
5. **LOW:** Add granularity to UCID clustering (complex, may cause over-splitting)

---

## Related Documents

| Document | Purpose |
|----------|---------|
| `UCID_DESIGN.md` | UCID architecture and format |
| `SA_DCH_METHODOLOGY_RECOMMENDATIONS.md` | Capacity and granularity improvements |
| `GRANULARITY_STRATEGY.md` | Source granularity handling |

---

*Document Created: 2026-02-11*
*Author: AI-Assisted Analysis*
