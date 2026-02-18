# Semianalysis vs Meta Canonical Comparison Analysis

**Author:** Meta Data Center GIS Team
**Created:** February 2, 2026
**Status:** Active Investigation
**Purpose:** Cross-source validation for Meta facility data quality

---

## Executive Summary

This document captures findings from comparing Semianalysis (SA) data against Meta Canonical (MC) data for Meta-owned facilities. The goal is to understand coverage gaps, capacity discrepancies, and establish a confident source of truth for Meta's data center portfolio.

### Key Findings

| Metric | Value |
|--------|-------|
| SA coverage of Meta Canonical | **52.6%** (51/97 campuses) |
| Meta Canonical coverage of SA | **38.6%** (51/132 campuses) |
| Matched campuses (both sources) | 51 |
| SA-only "Meta" campuses | 81 |
| MC-only campuses | 46 |

**Bottom Line:** Only ~53% of Meta Canonical campuses have corresponding Semianalysis records. SA reports 81 additional "Meta" campuses that are NOT in Meta Canonical - these require investigation.

---

## 1. Comparison Methodology

### 1.1 Why Direct Name Matching Fails

Initial attempt to match by `campus_name` yielded **0% match rate** because:
- SA uses naming convention: `Meta_Altoona_1`, `Meta_DeKalb_1`
- Meta Canonical uses DC codes: `Meta ATN`, `Meta DKL`, `Meta FRC`

**Lesson Learned:** String matching on campus names is unreliable across sources.

### 1.2 UCID-Based Spatial Matching (Recommended)

The **UCID (Universal Campus ID)** system provides reliable cross-source matching:

1. **Spatial clustering** groups facilities within tolerance distance (250m or 1000m)
2. **Same company + within tolerance = same UCID**
3. UCIDs enable joining records across any source

**Query Pattern:**
```python
# Group by UCID to compare sources
where = "company_clean = 'Meta' AND (source = 'Semianalysis' OR source = 'Meta Canonical')"

# Compare records sharing the same UCID
sa_by_ucid[ucid] vs mc_by_ucid[ucid]
```

### 1.3 Data Layers Used

| Layer | Purpose |
|-------|---------|
| `gold_buildings_full` | Building-level records with source-specific IDs |
| `gold_campus_full` | Campus-level aggregates with concatenated sources |
| `campus_master` | UCID reference table |

---

## 2. Detailed Findings

### 2.1 Matched Campuses (51 UCIDs)

These campuses exist in BOTH Semianalysis and Meta Canonical:

| UCID | SA Name | MC Code | SA MW | MC MW | Delta |
|------|---------|---------|-------|-------|-------|
| META-LOSLUNAS-1 | Meta_Los Lunas_1 | Meta VCN | 671.0 | 170.0 | **+501.0** |
| META-KUNA-2 | Meta_Kuna_1 | Meta KND | 166.0 | 81.6 | +84.4 |
| META-EAGLEMOUNTAIN-2 | Meta_Eagle Mountain_1 | Meta EAG | 90.0 | 171.6 | -81.6 |
| META-ALTOONA-1 | Meta_Altoona_1 | Meta ATN | 120.0 | 156.0 | -36.0 |
| META-DEKALB-2 | Meta_DeKalb_1 | Meta DKL | 90.0 | 90.0 | 0.0 |
| META-FORESTCITY | Meta_Forest City_1 | Meta FRC | 90.0 | 88.6 | +1.4 |

**Observations:**
- Capacity values frequently differ (sometimes by 500+ MW)
- Some campuses match exactly (DeKalb, Forest City)
- Large discrepancies suggest different definitions of "capacity"

### 2.2 SA-Only Campuses (81 UCIDs)

Semianalysis reports 81 "Meta" campuses that are NOT in Meta Canonical:

| SA Campus | Market | MW | Concern |
|-----------|--------|-----|---------|
| Meta Hyperion | Monroe, Louisiana | 2,672.0 | Very high capacity - verify |
| Meta Prometheus | Columbus, Ohio | 830.0 | Future/rumored? |
| Meta Titan - El Paso | El Paso, Texas | 1,112.0 | Verify ownership |
| Meta Titan - Indianapolis | Indianapolis | 996.0 | Verify ownership |
| Meta_Beaver Dam_1 | Madison, Wisconsin | 500.0 | Not in MC |
| Meta_Catoosa_1 | Tulsa, Oklahoma | 249.0 | Not in MC |
| Meta_Cheyenne_1 | Cheyenne, Wyoming | 588.0 | Not in MC |

**Possible Explanations:**
1. **Misattribution** - SA incorrectly attributes facility to Meta
2. **Future/Rumored** - Sites Meta hasn't confirmed publicly
3. **Leased facilities** - Meta leasing from colo providers (not owned)
4. **Acquisitions** - Recent purchases not yet in MC
5. **SA data quality** - Incorrect company assignment

### 2.3 MC-Only Campuses (46 UCIDs)

Meta Canonical reports 46 campuses that Semianalysis doesn't have:

**Possible Explanations:**
1. **SA coverage gap** - SA simply doesn't track this facility
2. **Naming mismatch** - SA has it under a different company name
3. **Small facilities** - Below SA's reporting threshold
4. **International** - SA may have weaker international coverage

---

## 3. Source of Truth Recommendations

### 3.1 Authority Hierarchy

| Data Type | Primary Source | Secondary Source | Rationale |
|-----------|----------------|------------------|-----------|
| **Meta facility existence** | Meta Canonical | - | Authoritative internal data |
| **Meta facility locations** | Meta Canonical | Semianalysis | MC has verified addresses |
| **Meta capacity (current)** | Meta Canonical | Semianalysis | MC reflects actual capacity |
| **Meta capacity (forecast)** | Semianalysis | - | SA provides year-over-year projections |
| **Industry-wide coverage** | Semianalysis | DataCenterHawk | SA has broader market coverage |

### 3.2 Confidence Levels

| Scenario | Confidence | Action |
|----------|------------|--------|
| **Campus in both SA and MC** | HIGH | Use MC for capacity, SA for forecasts |
| **Campus in MC only** | HIGH | Trust MC - SA coverage gap |
| **Campus in SA only (Meta company)** | LOW | Investigate - possible misattribution |
| **Capacity differs >50%** | MEDIUM | Manual review required |

### 3.3 Recommended Workflow

```
1. Start with Meta Canonical as ground truth for Meta facilities
2. Join SA data via UCID for forecast columns (mw_2025, mw_2026, etc.)
3. Flag SA-only "Meta" campuses for manual review
4. Do NOT use SA as authority for Meta facility existence
```

---

## 4. Next Steps

### 4.1 Immediate Actions

- [ ] **Investigate SA-only Meta campuses** - Are they misattributed?
- [ ] **Export full comparison to CSV** for manual review
- [ ] **Contact SA** about Meta facility attribution methodology
- [ ] **Add data quality flags** to gold_buildings for uncertain records

### 4.2 Pipeline Improvements

- [ ] **Add source confidence field** to gold_campus_full
- [ ] **Create validation script** that runs on each ingestion
- [ ] **Document capacity definition differences** between sources
- [ ] **Build reconciliation report** for Meta facilities

### 4.3 Queries for Investigation

**Find SA-only Meta campuses for manual review:**
```python
where = "company_clean = 'Meta' AND source LIKE '%Semianalysis%' AND source NOT LIKE '%Meta Canonical%'"
```

**Find large capacity discrepancies:**
```sql
SELECT ucid, sa_mw, mc_mw, ABS(sa_mw - mc_mw) as delta
FROM campus_comparison
WHERE delta > 100
ORDER BY delta DESC
```

**Export matched campuses with all fields:**
```python
fields = ["ucid", "source", "source_unique_id", "campus_name", "market",
          "state", "full_capacity_mw", "mw_2025", "mw_2026", "mw_2030"]
```

---

## 5. Appendix

### 5.1 Naming Convention Mapping

| SA Convention | MC Convention | Notes |
|---------------|---------------|-------|
| Meta_Altoona_1 | Meta ATN | Altoona, Iowa |
| Meta_DeKalb_1 | Meta DKL | DeKalb, Illinois |
| Meta_Forest City_1 | Meta FRC | Forest City, NC |
| Meta_Eagle Mountain_1 | Meta EAG / Meta UCO | Eagle Mountain, Utah |
| Meta_Los Lunas_1 | Meta VCN / Meta VLL | Los Lunas, NM |

### 5.2 Record Counts (Feb 2, 2026)

| Source | Meta Building Records | Meta Campus UCIDs |
|--------|----------------------|-------------------|
| Semianalysis | 232 | 132 |
| Meta Canonical | 340 | 97 |

### 5.3 Related Documentation

| Document | Purpose |
|----------|---------|
| `SEMIANALYSIS_PIPELINE_GUIDE.md` | SA data processing |
| `UCID_DESIGN.md` | Universal Campus ID system |
| `SA_VS_DCH_COMPARISON_WORKFLOW.md` | SA vs DataCenterHawk comparison |
| `MASTER_FIELD_MAPPING.md` | Field definitions across sources |

---

## 6. Changelog

### February 2, 2026
- Initial analysis comparing SA vs Meta Canonical
- Found 52.6% recall rate using UCID-based matching
- Identified 81 SA-only "Meta" campuses requiring investigation
- Documented source of truth recommendations

---

*Document maintained by: Meta Data Center GIS Team*
*Last Updated: February 2, 2026*
