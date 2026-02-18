# SA vs DCH Methodology Recommendations

**Created:** 2026-02-11
**Purpose:** Comprehensive analysis of capacity analysis, UCID methodology, and granularity definitions for improved SA vs DCH comparison
**Status:** 📋 RECOMMENDATIONS FOR DISCUSSION

---

## Executive Summary

Based on review of the current implementation, this document identifies **three key areas for improvement** in the SA vs DCH comparison workflow:

| Area | Current Issue | Recommended Solution | Priority |
|------|---------------|---------------------|----------|
| **Capacity Analysis** | Building records inherit campus-level values → double-counting | Use `MAX` aggregation at campus level, not `SUM` | 🔴 High |
| **UCID Methodology** | Comparison uses spatial-only matching | Implement UCID-based matching for cross-source linkage | 🟡 Medium |
| **Granularity Definitions** | Inconsistent `building_designation` vs `record_level` | Standardize on single field with source-aware logic | 🟡 Medium |

---

## 1. Capacity Analysis Methodology

### 1.1 Current Issues Identified

#### Issue A: Double-Counting in Company Totals

**Problem:** When building records inherit campus-level capacity values, summing across buildings inflates portfolio totals.

```
Example: AWS campus with 200 MW total capacity
├── Building 1: 200 MW (inherited from campus)
├── Building 2: 200 MW (inherited from campus)
├── Building 3: 200 MW (inherited from campus)
└── Total shown in report: 600 MW (3× actual)
```

**Evidence from 2026-02-04 Report:**
- AWS showed 51 GW vs expected 20-25 GW (2-3× inflated)
- Company totals were systematically too high

#### Issue B: Capacity Field Ambiguity

| Field | SA Population | DCH Population | Issue |
|-------|---------------|----------------|-------|
| `full_capacity_mw` | ~95% | ~95% | Includes planned/future, not just operational |
| `commissioned_power_mw` | **0%** | ~100% | SA missing this field entirely |
| `uc_power_mw` | ~30% | ~60% | Inconsistent coverage |

**Impact:** Comparing `full_capacity_mw` across sources conflates different capacity stages.

#### Issue C: Granularity Mismatch in Pairs

When a SA campus record is matched to a DCH building record (or vice versa), the capacity delta is meaningless:

```
SA Campus: 500 MW (total campus)
DCH Building: 100 MW (single building in campus)
Delta: 400 MW (appears as massive conflict, but it's apples-to-oranges)
```

### 1.2 Recommended Improvements

#### Recommendation 1A: Campus-Level Aggregation Strategy

For company portfolio totals, use `MAX` aggregation instead of `SUM`:

```python
# Current (problematic)
company_total = sum(r['full_capacity_mw'] for r in company_records)

# Recommended
# Group by UCID first, take MAX within each UCID
by_ucid = defaultdict(list)
for r in company_records:
    by_ucid[r['ucid']].append(r['full_capacity_mw'])

company_total = sum(max(caps) for caps in by_ucid.values())
```

**Rationale:** When buildings inherit campus capacity, all buildings in a campus have the same value. Taking `MAX` gives the correct campus total.

#### Recommendation 1B: Capacity Field Prioritization

Implement a capacity field selection hierarchy based on what's available:

```python
def get_best_capacity(record: Dict) -> Tuple[float, str]:
    """
    Returns (capacity_value, field_used) with priority:
    1. commissioned_power_mw (most accurate for operational)
    2. full_capacity_mw (includes planned, widely available)
    3. uc_power_mw (under construction)
    """
    if record.get('commissioned_power_mw') and record['commissioned_power_mw'] > 0:
        return (record['commissioned_power_mw'], 'commissioned')
    elif record.get('full_capacity_mw') and record['full_capacity_mw'] > 0:
        return (record['full_capacity_mw'], 'full')
    elif record.get('uc_power_mw') and record['uc_power_mw'] > 0:
        return (record['uc_power_mw'], 'uc')
    return (0, 'none')
```

**Report Enhancement:** Add a "Capacity Field Used" column showing which field was compared.

#### Recommendation 1C: Same-Field Comparison Flag

Only calculate MAPE/bias when comparing the same capacity field:

```python
def is_comparable(sa_field: str, dch_field: str) -> bool:
    """Only compare if both sources used the same capacity concept."""
    return sa_field == dch_field

# In analyze_capacity_conflicts:
comparable_pairs = [
    p for p in matched_pairs
    if is_comparable(p['sa_capacity_field'], p['dch_capacity_field'])
]
```

---

## 2. UCID Methodology

### 2.1 Current State

The UCID system is **implemented but not used for SA/DCH matching**:

| Component | Status | Notes |
|-----------|--------|-------|
| `generate_text_ucid.py` | ✅ Implemented | Assigns UCIDs to buildings/campuses |
| `campus_rollup_new.py` | ✅ Implemented | Uses UCID for campus aggregation |
| `compare_sa_vs_dch_v2.py` | ⚠️ Spatial-only | Does NOT use UCID for matching |

**Current matching algorithm:**
```python
# Spatial-only (current)
for sa_rec in sa_records:
    for dch_rec in dch_records:
        distance = haversine_distance(sa_rec, dch_rec)
        if distance <= 500m:
            # Match! (ignores company name)
```

**Problem:** Multi-tenant sites get incorrectly matched:
- Google building at 100 Main St matched to AWS building at 110 Main St
- Both are <500m apart but are different companies

### 2.2 UCID Matching Options

#### Option A: Pure UCID Matching (Recommended for Campus-Level)

```python
def match_by_ucid(sa_records, dch_records):
    """Match records with the same UCID."""
    sa_by_ucid = {r['ucid']: r for r in sa_records if r.get('ucid')}
    dch_by_ucid = {r['ucid']: r for r in dch_records if r.get('ucid')}

    common_ucids = set(sa_by_ucid.keys()) & set(dch_by_ucid.keys())

    matched = [
        {'sa': sa_by_ucid[ucid], 'dch': dch_by_ucid[ucid], 'ucid': ucid}
        for ucid in common_ucids
    ]

    sa_only = [r for r in sa_records if r.get('ucid') not in dch_by_ucid]
    dch_only = [r for r in dch_records if r.get('ucid') not in sa_by_ucid]

    return matched, sa_only, dch_only
```

**Pros:**
- Company-aware (won't match AWS to Google)
- Deterministic (no distance tiebreakers)
- Leverages existing UCID infrastructure

**Cons:**
- Requires both sources to have UCID populated
- May miss matches if UCID generation differs between runs

#### Option B: Spatial + Company Filter (Hybrid)

```python
def match_with_company_validation(sa_records, dch_records, threshold_m=500):
    """Spatial match with company name validation."""
    matched = []

    for sa_rec in sa_records:
        best_match = None
        best_distance = float('inf')

        for dch_rec in dch_records:
            distance = haversine_distance(sa_rec, dch_rec)
            if distance <= threshold_m and distance < best_distance:
                # Check company match
                if check_company_match(sa_rec['company_clean'], dch_rec['company_clean']):
                    best_match = dch_rec
                    best_distance = distance

        if best_match:
            matched.append({'sa': sa_rec, 'dch': best_match, 'distance': best_distance})

    return matched
```

**Pros:**
- Works even if UCID is missing
- Catches company mismatches that spatial-only would miss

**Cons:**
- Still requires fuzzy company name matching
- May miss matches where company names differ ("Amazon Web Services" vs "AWS")

#### Option C: UCID Primary, Spatial Fallback (Recommended)

```python
def match_hybrid(sa_records, dch_records, threshold_m=500):
    """
    Try UCID match first, then spatial match for records without UCID.
    """
    # Phase 1: UCID matching
    ucid_matched, sa_no_ucid, dch_no_ucid = match_by_ucid(sa_records, dch_records)

    # Phase 2: Spatial matching for records without UCID match
    spatial_matched = match_with_company_validation(sa_no_ucid, dch_no_ucid, threshold_m)

    # Flag match method
    for m in ucid_matched:
        m['match_method'] = 'UCID'
    for m in spatial_matched:
        m['match_method'] = 'SPATIAL'

    return ucid_matched + spatial_matched
```

**Recommended Approach:** This gives the best of both worlds.

### 2.3 UCID Format Clarification

Current UCID format is **text-based**:

```
Campus:   {COMPANY_CODE}-{CAMPUS_NAME}
Building: {COMPANY_CODE}-{CAMPUS_NAME}-{BUILDING_NUM}

Examples:
- META-ALTOONA (campus)
- META-ALTOONA-01 (building 1)
- AWS-ASHBURN-EAST (campus with geographic suffix)
```

**Advantages:**
- Human-readable
- Self-documenting (company + location visible)
- Stable across pipeline runs (unlike auto-increment IDs)

**Considerations for Comparison:**
- For campus-level comparison, strip the building suffix:
  ```python
  def get_campus_ucid(ucid: str) -> str:
      """Extract campus portion from building UCID."""
      parts = ucid.rsplit('-', 1)
      if parts[-1].isdigit() and len(parts) > 1:
          return parts[0]  # Strip building number
      return ucid  # Already a campus UCID
  ```

---

## 3. Granularity Definitions

### 3.1 Current State

Two fields currently track granularity, with inconsistent usage:

| Field | Source | Values | Issue |
|-------|--------|--------|-------|
| `building_designation` | SA, DCH | "Building", "Campus", "Suite" | Not always populated |
| `record_level` | All ingestion | "Building", "Campus" | Derived during ingestion |

**Current normalization logic:**

```python
def normalize_granularity(record: Dict) -> str:
    """Check building_designation first, then record_level."""
    designation = record.get('building_designation', '').lower()
    record_level = record.get('record_level', '').lower()

    for val in [designation, record_level]:
        if 'campus' in val:
            return 'Campus'
        if 'building' in val:
            return 'Building'
        if 'suite' in val or 'unit' in val:
            return 'Suite'

    return 'Unknown'
```

**Problem:** Logic depends on field population, which varies by source.

### 3.2 Granularity Determination by Source

| Source | Native Granularity | `building_designation` | `record_level` | Recommended Logic |
|--------|-------------------|------------------------|----------------|-------------------|
| **SemiAnalysis** | Mixed (see below) | Usually populated | "Building" | Check `building_designation` first |
| **DCH Hyper** | Building | Usually populated | "Building" | Trust `record_level` |
| **DCH Lease** | Building | Usually populated | "Building" | Trust `record_level` |
| **DCM** | Mixed | May have "- Building" suffix | Derived | Check facility name pattern |
| **NPM** | Project (often campus) | Not populated | "Building" ⚠️ | **Review needed** |

### 3.3 SemiAnalysis Granularity Deep-Dive

SemiAnalysis data has specific patterns in the source data:

| `cluster` Field Pattern | Interpretation | Granularity |
|------------------------|----------------|-------------|
| "Building 1", "Building 2" | Individual building in campus | Building |
| "Phase 1", "Phase 2" | Development phase (often campus-level) | Campus |
| Empty/null | Single-building site | Building |
| Campus name only | Campus-level entry | Campus |

**Recommended SA-specific logic:**

```python
def determine_sa_granularity(record: Dict) -> str:
    """SemiAnalysis-specific granularity determination."""
    cluster = record.get('cluster', '') or ''
    building_designation = record.get('building_designation', '') or ''

    # Explicit building designation takes precedence
    if 'building' in building_designation.lower():
        return 'Building'
    if 'campus' in building_designation.lower():
        return 'Campus'

    # Infer from cluster field
    if re.match(r'Building\s*\d+', cluster, re.IGNORECASE):
        return 'Building'
    if re.match(r'Phase\s*\d+', cluster, re.IGNORECASE):
        return 'Campus'  # Phases are typically campus-level

    # Default to building for individual rows
    return 'Building'
```

### 3.4 Recommended Granularity Standard

**Canonical Values:**

| Granularity | Definition | Comparison Guidance |
|-------------|------------|---------------------|
| **Building** | Single physical building/structure | Compare building↔building only |
| **Campus** | Aggregated site with multiple buildings | Compare campus↔campus only |
| **Suite** | Portion of a building (cage, unit) | Rarely comparable, flag for review |
| **Phase** | Development phase (temporal, not physical) | Treat as Campus for comparison |
| **Unknown** | Could not determine | Exclude from statistical metrics |

**Decision Tree for Same-Granularity Comparison:**

```
Is SA_granularity == DCH_granularity?
├── Yes → Include in MAPE/Bias/Correlation calculations
├── No, but both are Building or both are Campus → Include (compatible)
└── No, and different levels → Flag as granularity_mismatch, exclude from stats
```

### 3.5 Enhanced Granularity Filtering

Update `compare_sa_vs_dch_v2.py` with stricter logic:

```python
def is_comparable_granularity(sa_gran: str, dch_gran: str) -> Tuple[bool, str]:
    """
    Determine if two granularity values are comparable.

    Returns: (is_comparable, reason)
    """
    # Normalize
    sa = sa_gran.lower()
    dch = dch_gran.lower()

    # Same level = always comparable
    if sa == dch:
        return (True, 'exact_match')

    # Building-like values
    building_like = {'building', 'structure', 'facility'}
    if sa in building_like and dch in building_like:
        return (True, 'building_equivalent')

    # Campus-like values
    campus_like = {'campus', 'site', 'phase'}
    if sa in campus_like and dch in campus_like:
        return (True, 'campus_equivalent')

    # Unknown should be excluded
    if sa == 'unknown' or dch == 'unknown':
        return (False, 'unknown_granularity')

    # Different levels = not comparable
    return (False, 'level_mismatch')
```

---

## 4. Implementation Roadmap

### Phase 1: Quick Wins (This Session)

| Task | Impact | Effort |
|------|--------|--------|
| ✅ Campus-level comparison by default | High | Done |
| ✅ Granularity filtering in MAPE/Bias | High | Done |
| 🔲 Add capacity field tracking to report | Medium | Low |
| 🔲 Show match method (UCID vs Spatial) in output | Medium | Low |

### Phase 2: UCID-Based Matching (Next Session)

| Task | Impact | Effort |
|------|--------|--------|
| 🔲 Verify UCID population in both sources | High | Low |
| 🔲 Implement Option C (UCID + Spatial fallback) | High | Medium |
| 🔲 Add "Match Method" column to report | Medium | Low |
| 🔲 Calculate UCID match rate vs spatial match rate | Medium | Low |

### Phase 3: Capacity Reconciliation (Future)

| Task | Impact | Effort |
|------|--------|--------|
| 🔲 Implement SA `commissioned_power_mw` sourcing | High | High |
| 🔲 Add capacity field comparison matrix to report | Medium | Medium |
| 🔲 Per-UCID capacity timeline analysis | Medium | High |

---

## 5. Validation Queries

### Query 1: Check UCID Population

```python
# Run after pipeline to verify UCID coverage
def check_ucid_coverage():
    sa_records = arcpy.da.SearchCursor(GOLD_BUILDINGS,
        ['source', 'ucid'], "source = 'Semianalysis'")
    dch_records = arcpy.da.SearchCursor(GOLD_BUILDINGS,
        ['source', 'ucid'], "source = 'DataCenterHawk'")

    sa_with_ucid = sum(1 for r in sa_records if r[1])
    dch_with_ucid = sum(1 for r in dch_records if r[1])

    print(f"SA UCID coverage: {sa_with_ucid}/{sa_total}")
    print(f"DCH UCID coverage: {dch_with_ucid}/{dch_total}")
```

### Query 2: Granularity Distribution

```python
# Check granularity breakdown by source
def check_granularity_distribution():
    with arcpy.da.SearchCursor(GOLD_BUILDINGS,
        ['source', 'building_designation', 'record_level']) as cursor:

        by_source = defaultdict(lambda: defaultdict(int))
        for source, designation, level in cursor:
            gran = normalize_granularity({'building_designation': designation,
                                          'record_level': level})
            by_source[source][gran] += 1

    for source, counts in by_source.items():
        print(f"\n{source}:")
        for gran, count in counts.items():
            print(f"  {gran}: {count}")
```

### Query 3: Capacity Field Coverage

```python
# Check which capacity fields are populated by source
def check_capacity_coverage():
    fields = ['source', 'full_capacity_mw', 'commissioned_power_mw', 'uc_power_mw']

    by_source = defaultdict(lambda: {'full': 0, 'comm': 0, 'uc': 0, 'total': 0})

    with arcpy.da.SearchCursor(GOLD_BUILDINGS, fields) as cursor:
        for row in cursor:
            source = row[0]
            by_source[source]['total'] += 1
            if row[1] and row[1] > 0:
                by_source[source]['full'] += 1
            if row[2] and row[2] > 0:
                by_source[source]['comm'] += 1
            if row[3] and row[3] > 0:
                by_source[source]['uc'] += 1

    for source, counts in by_source.items():
        total = counts['total']
        print(f"\n{source} (n={total}):")
        print(f"  full_capacity_mw: {counts['full']/total*100:.1f}%")
        print(f"  commissioned_power_mw: {counts['comm']/total*100:.1f}%")
        print(f"  uc_power_mw: {counts['uc']/total*100:.1f}%")
```

---

## 6. Summary of Recommendations

### Immediate Actions (Before Next Run)

1. **Use campus-level comparison** (`use_campus_level=True`) ✅ Done
2. **Filter same-granularity pairs** for MAPE/Bias calculations ✅ Done
3. **Add granularity columns** to Essential DC table ✅ Done

### Short-Term Actions (Next Session)

4. **Implement UCID-based matching** with spatial fallback
5. **Add "Match Method" column** to track UCID vs spatial matches
6. **Add capacity field tracking** to show which field was compared

### Medium-Term Actions (Future Sessions)

7. **Source SA `commissioned_power_mw`** from Excel if available
8. **Per-UCID capacity timeline** to track changes over time
9. **Regional MAPE breakdown** to identify geographic accuracy patterns

---

## Related Documents

| Document | Purpose |
|----------|---------|
| `SA_VS_DCH_COMPARISON_WORKFLOW.md` | Main workflow reference |
| `UCID_DESIGN.md` | UCID architecture and matching logic |
| `GRANULARITY_STRATEGY.md` | Source granularity handling |
| `PIPELINE_DOCUMENTATION.md` | Full pipeline context |

---

*Document Created: 2026-02-11*
*Author: AI-Assisted Analysis*
