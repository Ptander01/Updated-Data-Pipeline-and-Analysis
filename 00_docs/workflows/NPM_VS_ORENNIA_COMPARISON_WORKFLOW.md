# NPM vs Orennia Comparison Workflow

**Created:** 2026-02-13
**Last NPM Ingestion:** 2026-02-13 (1,567 records)
**Last Orennia Ingestion:** 2026-02-12 (3,575 records)
**Last Comparison:** 2026-02-17
**Last Updated:** 2026-02-17
**Status:** ✅ Methodology Aligned with SA vs DCH | Source Overlap Investigated

---

## 📚 Related Methodology Documents

| Document | Purpose |
|----------|---------|
| **[SA_VS_DCH_COMPARISON_WORKFLOW.md](SA_VS_DCH_COMPARISON_WORKFLOW.md)** | Gold standard comparison methodology |
| **[SA_VS_META_CANONICAL_COMPARISON.md](SA_VS_META_CANONICAL_COMPARISON.md)** | UCID-based matching example |
| **[UCID_SA_DCH_IMPROVEMENT_PLAN.md](UCID_SA_DCH_IMPROVEMENT_PLAN.md)** | Company-aware matching & confidence scoring |
| [MASTER_FIELD_MAPPING.md](../schemas/MASTER_FIELD_MAPPING.md) | Complete field mapping reference |

---

## 📊 Executive Summary

| Metric | Value | Interpretation |
|--------|-------|----------------|
| **NPM Match Rate** | 60.6% | Majority of NPM overlaps with Orennia |
| **Orennia Match Rate** | 26.5% | Orennia has significant unique coverage |
| **Matched Pairs** | 949 | 1-to-1 optimal matching |
| **NPM-Only Records** | ~618 | 39.4% of NPM is unique |
| **Orennia-Only Records** | ~2,626 | 73.5% of Orennia is unique |

### Source Overlap Analysis (Sam's Hypothesis Investigation)

| Indicator | Finding | Interpretation |
|-----------|---------|----------------|
| **Evidence Score** | 3/9 | MODERATE EVIDENCE |
| **Exact Coord Match (0-1m)** | 3.6% | ❌ Against shared source |
| **Identical Capacity Values** | 34.3% | ⚠️ Suggests some shared data |
| **Smoking Gun Matches** | 0.1% | ❌ No systematic copying |

**Bottom Line:** Sources likely draw from common public/industry data (utility filings, planning permits) rather than one directly copying from the other.

---

## 🔬 Methodology (V3 - Aligned with SA vs DCH)

### Three Matching Modes Available

| Mode | Description | Use Case |
|------|-------------|----------|
| `spatial` | Distance only, 1-to-1 optimal | Understanding raw record overlap |
| `company_aware` | Distance + same company required | Preventing false matches at multi-tenant sites |
| `ucid` (recommended) | UCID-based campus matching | Accurate site counting (requires post-ingestion) |

### Current Analysis Uses: Building-Level Spatial (1-to-1 Optimal)

**Algorithm:**
1. Calculate all pairwise distances within threshold
2. Sort by distance (closest first)
3. Greedy 1-to-1 assignment (each record matches at most one counterpart)
4. Result: Symmetric pair counts (N matched pairs = N Orennia matched = N NPM matched)

**Limitations:**
- Building-level granularity (not campus-aggregated)
- Does not use UCID system
- Multi-tenant site risk (different companies at same location may match)

### For Campus-Level Comparison (Recommended)

Run the full post-ingestion pipeline first:

```python
exec(open(r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\scripts\run_post_ingestion.py", encoding='utf-8').read())
```

Then use `gold_campus_full` for UCID-based matching. See `SA_VS_DCH_COMPARISON_WORKFLOW.md` for the established approach.

---

## 🔍 Source Overlap Analysis (Deep Investigation)

**Purpose:** Investigate Sam's hypothesis that Orennia is sourcing data from NPM.

### Evidence Analysis Results (2026-02-17)

| Indicator | Finding | Weight |
|-----------|---------|--------|
| **Exact coordinate match (0-1m)** | 34 of 949 (3.6%) | Low - suggests independent geocoding |
| **Very close (0-10m)** | 109 of 949 (11.5%) | Low-moderate |
| **Identical capacity values** | 157 of 458 (34.3%) | High - suggests shared data sources |
| **Same company name** | 518 of 949 (54.6%) | Neutral - both track same market |
| **Smoking gun (all criteria)** | 1 of 949 (0.1%) | Very low - no systematic copying |

### Conclusion

**MODERATE EVIDENCE (Score 3/9)** - Mixed signals:
- LOW exact coordinate matches suggest independent data collection methods
- HIGH identical capacity rate suggests some shared underlying data sources
- VERY LOW smoking gun matches (only 1 record) indicates no direct copying

**Most Likely Explanation:** Both NPM and Orennia source from common public/industry data (FERC filings, utility interconnection queues, planning applications) rather than one directly copying from the other.

---

## 📌 Recommendations

### Data Source Strategy

1. **Use Orennia as primary** - 2.3x larger coverage, more complete
2. **Keep NPM for unique records** - ~618 records not in Orennia
3. **Run UCID generation** - Required for proper deduplication
4. **Cross-validate** - Use overlapping records to validate capacity values

### Match Quality Improvements

| Priority | Action | Benefit |
|----------|--------|---------|
| P1 | Use company-aware matching | Prevent false matches at multi-tenant sites |
| P2 | Use UCID-based matching | Accurate campus counts |
| P3 | Add confidence scoring | Identify low-quality matches |

---

## 🛠️ Scripts Reference

### Comparison Scripts

| Script | Purpose |
|--------|---------|
| `05_accuracy/compare_npm_vs_orennia.py` | **V3** Full comparison with HTML report (3 matching modes) |
| `05_accuracy/analyze_npm_orennia_source_overlap.py` | Deep source overlap analysis for Sam's hypothesis |
| `04_validation/compare_orennia_npm.py` | Quick overlap analysis (console output) |

### Ingestion Scripts

| Script | Purpose | Records |
|--------|---------|---------|
| `01_ingestion/import_npm_csv.py` | Import NPM CSV → npm_raw | 1,567 |
| `01_ingestion/ingest_npm.py` | npm_raw → gold_buildings | 1,567 |
| `01_ingestion/ingest_orennia.py` | Orennia CSV → gold_buildings | 3,575 |

---

## 🚀 Quick Commands

### Run Full Comparison (with HTML Report)

```python
exec(open(r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\scripts\05_accuracy\compare_npm_vs_orennia.py", encoding='utf-8').read())
```

### Run Source Overlap Analysis (Sam's Hypothesis)

```python
exec(open(r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\scripts\05_accuracy\analyze_npm_orennia_source_overlap.py", encoding='utf-8').read())
```

### Run Quick Overlap Check (Console Only)

```python
exec(open(r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\scripts\04_validation\compare_orennia_npm.py", encoding='utf-8').read())
```

---

## 📈 Statistical Metrics

### Grade Scale (from SA vs DCH)

| MAPE Range | Grade | Interpretation |
|------------|-------|----------------|
| 0-10% | A | Excellent agreement |
| 10-20% | B | Good agreement |
| 20-35% | C | Moderate disagreement |
| 35-50% | D | Significant disagreement |
| >50% | F | Poor agreement |

### Match Confidence Scoring (0-100)

| Factor | Points | Criteria |
|--------|--------|----------|
| Distance | 0-30 | <50m: 30, <100m: 25, <250m: 20, <500m: 10 |
| Company Match | 0-30 | Same company: 30, Fuzzy match: 15 |
| Capacity Agreement | 0-20 | <5%: 20, <10%: 15, <20%: 10 |
| State Match | 0-10 | Same state: 10 |
| Status Match | 0-10 | Same status: 10 |

**Confidence Tiers:** HIGH (80+), MEDIUM (50-79), LOW (<50)

---

## 📋 Session Log

### 2026-02-17

- [x] Created deep source overlap analysis script
- [x] Ran Sam's hypothesis investigation
- [x] Found MODERATE EVIDENCE (3/9) - not direct copying
- [x] Aligned comparison script with SA vs DCH methodology (V3)
- [x] Added company-aware matching function
- [x] Added UCID-based matching function
- [x] Added confidence scoring function
- [x] Updated methodology section in HTML report
- [x] Updated this workflow document

### 2026-02-13 (Initial)

- [x] Ran schema migration to add new fields
- [x] Ingested Orennia data (3,575 records)
- [x] Imported NPM CSV to npm_raw (1,567 records)
- [x] Ingested NPM to gold_buildings (1,567 records)
- [x] Created comparison script with HTML report (V1)
- [x] Created this workflow document

---

*Document created: 2026-02-13*
*Last updated: 2026-02-17*
