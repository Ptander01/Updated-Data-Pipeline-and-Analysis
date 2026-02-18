# UCID & SA vs DCH Improvement Plan

**Created:** 2026-02-11
**Status:** 📋 PLANNING
**Priority:** High

---

## Executive Summary

This plan consolidates all proposed improvements to the UCID clustering methodology and SA vs DCH comparison workflow, including a new validation approach using SemiAnalysis's native `cluster` field as a baseline.

---

## 🎯 Goals

1. **Improve UCID clustering accuracy** in dense markets (Ashburn, DFW, etc.)
2. **Add company-aware matching** to SA vs DCH comparison
3. **Validate clustering methods** against SA's native cluster field and Meta Canonical
4. **Add post-rollup validation** to catch orphaned buildings
5. **Implement confidence scoring** for all matches

---

## Phase 1: SA Cluster Validation Study (NEW)

### Concept

SemiAnalysis provides a `cluster` field in their raw data that represents their own grouping of buildings into sites. We can use this as a **baseline comparison** to validate our UCID clustering methodology.

### Validation Approach

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    SA CLUSTER vs UCID VALIDATION                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   Source Data:                                                              │
│   ┌─────────────────────────────────────────────────────────────────────┐  │
│   │ SA Raw Record                                                       │  │
│   │ ├── cluster: "Building 1" or "Phase 2" or "AWS Ashburn"            │  │
│   │ ├── company_clean: "AWS"                                           │  │
│   │ └── lat/lon: coordinates                                           │  │
│   └─────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
│   Two Clustering Methods to Compare:                                        │
│                                                                             │
│   Method A: SA Native Cluster                                               │
│   ├── Use SA's `cluster` field directly                                    │
│   ├── Group buildings by: company + city + cluster                         │
│   └── Result: SA_cluster_id                                                │
│                                                                             │
│   Method B: Our UCID Clustering                                             │
│   ├── Use company + proximity (250m)                                       │
│   ├── Transitive spatial clustering                                        │
│   └── Result: ucid                                                         │
│                                                                             │
│   Validation Against Meta Canonical:                                        │
│   ┌─────────────────────────────────────────────────────────────────────┐  │
│   │ For each Meta Canonical campus:                                     │  │
│   │ ├── Find SA records within 500m                                    │  │
│   │ ├── Check: Do all SA records have same SA_cluster_id?              │  │
│   │ ├── Check: Do all SA records have same ucid?                       │  │
│   │ └── Score: Which method better matches Meta ground truth?          │  │
│   └─────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Metrics to Compare

| Metric | SA Native Cluster | Our UCID | Winner |
|--------|-------------------|----------|--------|
| **Meta Canonical Match Rate** | ? | ? | TBD |
| **False Merge Rate** (distinct sites merged) | ? | ? | TBD |
| **False Split Rate** (same site split) | ? | ? | TBD |
| **Multi-source agreement** (SA+DCH same cluster) | N/A | ? | UCID only |

### Implementation Script

```python
# New script: validate_clustering_methods.py

def compare_clustering_methods():
    """
    Compare SA's native cluster field against our UCID clustering.
    Validate both against Meta Canonical ground truth.
    """

    # Step 1: Build SA native cluster IDs
    # Format: {company}|{city}|{cluster}
    sa_native_clusters = {}
    for sa_record in sa_records:
        native_id = f"{sa_record['company_clean']}|{sa_record['city']}|{sa_record['cluster']}"
        sa_native_clusters[sa_record['unique_id']] = native_id

    # Step 2: Get our UCID assignments
    ucid_clusters = {}
    for sa_record in sa_records:
        ucid_clusters[sa_record['unique_id']] = sa_record['ucid']

    # Step 3: For each Meta Canonical campus, compare methods
    results = []
    for meta_campus in meta_canonical_campuses:
        # Find SA records within 500m
        nearby_sa = find_records_within_distance(meta_campus, sa_records, 500)

        if not nearby_sa:
            continue

        # Check SA native cluster consistency
        sa_native_ids = set(sa_native_clusters[r['unique_id']] for r in nearby_sa)
        sa_native_consistent = len(sa_native_ids) == 1

        # Check UCID consistency
        ucids = set(ucid_clusters[r['unique_id']] for r in nearby_sa)
        ucid_consistent = len(ucids) == 1

        results.append({
            'meta_campus': meta_campus['campus_name'],
            'sa_records_found': len(nearby_sa),
            'sa_native_consistent': sa_native_consistent,
            'sa_native_cluster_count': len(sa_native_ids),
            'ucid_consistent': ucid_consistent,
            'ucid_count': len(ucids),
            'winner': 'SA' if sa_native_consistent and not ucid_consistent else
                      'UCID' if ucid_consistent and not sa_native_consistent else
                      'TIE' if sa_native_consistent and ucid_consistent else
                      'BOTH_FAIL'
        })

    return results
```

### Expected Outcomes

| Outcome | Implication |
|---------|-------------|
| **SA wins** | Consider incorporating SA's cluster field into UCID generation |
| **UCID wins** | Our spatial clustering is more accurate than SA's manual grouping |
| **TIE** | Both methods are valid; continue with UCID for cross-source capability |
| **Both fail** | Review Meta Canonical accuracy or adjust thresholds |

---

## Phase 2: Company-Aware Matching for SA vs DCH

### Current Problem

```python
# Current: Proximity-only matching (RISKY)
if distance <= 500m:
    match!  # Even if AWS matched to Google
```

### Solution

```python
# Proposed: Company-aware matching
if distance <= 500m AND company_match(sa_company, dch_company):
    match!  # Only if companies align
```

### Implementation

Update `compare_sa_vs_dch_v2.py`:

1. Add `require_company_match` parameter (default: `True`)
2. Filter potential matches by company BEFORE distance ranking
3. Add `match_method` field: `"UCID"`, `"SPATIAL_COMPANY"`, `"SPATIAL_ONLY"`
4. Report company mismatch rate for transparency

---

## Phase 3: Match Confidence Scoring

### Confidence Formula

```python
def calculate_match_confidence(sa_rec, dch_rec, distance_m):
    score = 0

    # Distance (0-30 pts)
    if distance_m < 100: score += 30
    elif distance_m < 250: score += 20
    elif distance_m < 500: score += 10

    # Company match (0-30 pts)
    if exact_company_match: score += 30
    elif fuzzy_match > 0.8: score += 15

    # Granularity match (0-15 pts)
    if same_granularity: score += 15

    # Capacity agreement (0-15 pts)
    if delta_pct < 10%: score += 15
    elif delta_pct < 25%: score += 10

    # Facility type match (0-10 pts)
    if same_type: score += 10

    # Tier: HIGH (80+), MEDIUM (50-79), LOW (<50)
    return score
```

### Report Enhancements

- Add "Confidence" column to CSV exports
- Add confidence distribution chart to HTML report
- Option to filter MAPE calculation by confidence tier

---

## Phase 4: Campus Rollup Validation

### Post-Rollup Checks

| Check | Query | Severity |
|-------|-------|----------|
| Orphaned buildings | `ucid IS NULL` in gold_buildings | 🔴 Critical |
| Campus count mismatch | `COUNT(DISTINCT ucid)` != campus count | 🔴 Critical |
| Zero-capacity campuses | `full_capacity_mw = 0 OR NULL` | 🟡 Warning |
| Single-building campuses | `building_count = 1` | ℹ️ Info |
| Multi-source rate | `source LIKE '%;%'` | ℹ️ Metric |

### Implementation

```python
# New script: validate_campus_rollup.py

def validate_rollup():
    issues = []

    # Check 1: Orphaned buildings
    orphaned = count_where(GOLD_BUILDINGS, "ucid IS NULL")
    if orphaned > 0:
        issues.append(f"🔴 {orphaned} buildings have no UCID")

    # Check 2: Campus count sanity
    campus_count = count(GOLD_CAMPUS)
    unique_ucids = count_distinct(GOLD_BUILDINGS, "ucid")
    if campus_count != unique_ucids:
        issues.append(f"🔴 Campus count ({campus_count}) != unique UCIDs ({unique_ucids})")

    # Check 3: Building count sum
    sum_buildings = sum(GOLD_CAMPUS, "building_count")
    buildings_with_ucid = count_where(GOLD_BUILDINGS, "ucid IS NOT NULL")
    if sum_buildings != buildings_with_ucid:
        issues.append(f"🟡 Sum of building counts doesn't match")

    # Metrics
    single_building = count_where(GOLD_CAMPUS, "building_count = 1")
    multi_source = count_where(GOLD_CAMPUS, "source LIKE '%;%'")

    return issues, {'single_building': single_building, 'multi_source': multi_source}
```

---

## Phase 5: High-Density Area Analysis

### Known Hotspots

| Market | Expected Issues | Special Handling |
|--------|-----------------|------------------|
| Ashburn, VA | Multi-tenant colo campus | Tighter threshold? |
| Dallas-Fort Worth | Large hyperscale sprawl | Geographic suffix |
| Phoenix, AZ | Rapid growth area | Watch for new sites |
| Northern Virginia | Dense corridor | Extra validation |

### Implementation

Generate a "High-Density Areas Report" showing:
- Areas with 10+ facilities within 1km
- Number of unique companies in each area
- Potential false merge risk score

---

## Implementation Roadmap

### Session 1 (Next): SA Cluster Validation Study

```python
# Run this command in ArcGIS Pro Python window:
exec(open(r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\scripts\04_validation\validate_clustering_methods.py").read())
```

**Deliverables:**
- [ ] Create `validate_clustering_methods.py`
- [ ] Run comparison: SA cluster vs UCID vs Meta Canonical
- [ ] Generate report showing which method wins
- [ ] Document findings in `SA_CLUSTER_VALIDATION_RESULTS.md`

### Session 2: Implement Winning Approach

Based on Session 1 results:
- If SA cluster wins: Incorporate into UCID generation
- If UCID wins: Proceed with confidence
- Either way: Add company-aware matching to SA vs DCH

**Deliverables:**
- [ ] Update `compare_sa_vs_dch_v2.py` with company-aware matching
- [ ] Add confidence scoring
- [ ] Generate new comparison report

### Session 3: Campus Rollup Validation

**Deliverables:**
- [ ] Create `validate_campus_rollup.py`
- [ ] Integrate into post-ingestion pipeline
- [ ] Add validation step to `run_post_ingestion.py`

### Session 4: Documentation & Cleanup

**Deliverables:**
- [ ] Update all related documentation
- [ ] Create consolidated methodology guide
- [ ] Archive deprecated approaches

---

## Quick Reference: SA `cluster` Field

From SemiAnalysis raw data, the `cluster` field contains:

| Pattern | Example | Interpretation |
|---------|---------|----------------|
| Building N | "Building 1", "Building 2" | Individual building in campus |
| Phase N | "Phase 1", "Phase 2" | Development phase (often campus-level) |
| Campus name | "AWS Ashburn" | Campus-level entry |
| Empty/null | - | Single-building site |

**Key Insight:** SA's cluster field is their internal grouping. Comparing it to our spatial UCID clustering will reveal which approach better matches ground truth.

---

## Files to Create/Modify

| File | Action | Purpose |
|------|--------|---------|
| `validate_clustering_methods.py` | CREATE | Compare SA cluster vs UCID |
| `validate_campus_rollup.py` | CREATE | Post-rollup validation |
| `compare_sa_vs_dch_v2.py` | MODIFY | Add company-aware matching |
| `generate_text_ucid.py` | POSSIBLY MODIFY | If SA cluster proves superior |
| `run_post_ingestion.py` | MODIFY | Add validation step |

---

## Success Criteria

| Metric | Current | Target |
|--------|---------|--------|
| Meta Canonical match rate | ~90% | >95% |
| Company mismatch rate in SA vs DCH | Unknown | <5% |
| Orphaned buildings after rollup | Unknown | 0 |
| High-confidence matches (80+ score) | Unknown | >70% |

---

## Related Documents

| Document | Purpose |
|----------|---------|
| `MATCH_CONFIDENCE_ANALYSIS.md` | Detailed confidence analysis |
| `SA_DCH_METHODOLOGY_RECOMMENDATIONS.md` | Capacity/granularity recommendations |
| `UCID_DESIGN.md` | UCID architecture |
| `GRANULARITY_STRATEGY.md` | Source granularity handling |

---

*Plan Created: 2026-02-11*
*Next Review: Session 2*
