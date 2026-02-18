# New Source Ingestion Summary — Feb 2026

**Date:** February 12, 2026
**Status:** Scripts Ready for Execution in ArcGIS Pro

---

## Overview

Three new data sources have been analyzed and prepared for ingestion into the consensus model:

| Source | Records | Geocoded | Coverage | Key Strength |
|--------|---------|----------|----------|--------------|
| **Orennia** | 3,575 | 100.0% | US-centric (2 countries) | Grid/utility mapping (238 transmission owners) |
| **SemiAnalysis Global** | 5,731 | 95.6% | Global (64 countries) | Year-over-year MW forecasts (2017-2032) |
| **WoodMac** | 2,265 | 96.7% | Global (17 countries) | Project pipeline tracking, AI/Cloud workload differentiation |

**Combined Total:** 11,571 records (with high geocoding rates across all sources)

---

## Strengths & Weaknesses Analysis

### Orennia
**Best For:** US market deep-dive with grid context

| Metric | Value | Assessment |
|--------|-------|------------|
| Geocoding | 100.0% | ✅ Excellent |
| Capacity Data | 83.9% populated | ✅ Strong |
| Square Footage | 68.1% populated | ✅ Good |
| Grid/Utility Data | 238 transmission owners | ✅ Unique |
| Geographic Scope | US only | ⚠️ Limited |

**Strengths:**
- ✅ Excellent geocoding rate (100%)
- ✅ Strong capacity data (83.9% populated)
- ✅ Good square footage data (68.1%)
- ✅ Grid/utility mapping (238 transmission owners)
- ✅ Owner type classification (Hyperscaler/Colo/Enterprise)

**Weaknesses:**
- ⚠️ US-only coverage (2 countries including minor Canada presence)
- ⚠️ Date data sparse (37.2% populated)

---

### SemiAnalysis Global Import
**Best For:** Capacity forecasting and market-level analysis

| Metric | Value | Assessment |
|--------|-------|------------|
| Geocoding | 95.6% | ✅ Excellent |
| Capacity Data | Derived from year columns | ✅ Unique |
| Square Footage | 70.6% populated | ✅ Good |
| MW Forecasts | 2017-2032 | ✅ Unique |
| Geographic Scope | 64 countries | ✅ Global |

**Strengths:**
- ✅ Excellent geocoding rate (95.6%)
- ✅ Global coverage (64 countries)
- ✅ Good square footage data (70.6%)
- ✅ Unique year-over-year capacity forecasts (2023-2032)
- ✅ Detailed market coverage (422 markets)
- ✅ Building-level granularity with cluster groupings

**Weaknesses:**
- ⚠️ "Full Capacity" column contains dates, not MW values (schema documentation issue)
- ⚠️ Status must be derived from capacity fields

**Year-over-Year MW Totals:**
| Year | Records | Total MW |
|------|---------|----------|
| 2023 | 2,934 | 49,916 |
| 2024 | 3,381 | 61,251 |
| 2025 | 4,001 | 80,939 |
| 2026 | 4,389 | 112,971 |
| 2027 | 4,841 | 169,801 |
| 2028 | 5,034 | 220,867 |
| 2029 | 5,138 | 259,363 |
| 2030 | 5,167 | 285,541 |
| 2031 | 5,184 | 305,702 |
| 2032 | 5,195 | 320,837 |

---

### WoodMac (Wood Mackenzie)
**Best For:** International market analysis and project tracking

| Metric | Value | Assessment |
|--------|-------|------------|
| Geocoding | 96.7% | ✅ Excellent |
| Capacity Data | 56.2% populated | ⚠️ Moderate |
| Project Tracking | 2,049 unique projects | ✅ Strong |
| Workload Types | AI, Cloud, Colo, HPC | ✅ Unique |
| Geographic Scope | 17 countries | ✅ Good |

**Strengths:**
- ✅ Excellent geocoding rate (96.7%)
- ✅ Global coverage (17 countries)
- ✅ Project-level tracking with development phases
- ✅ AI vs Cloud workload differentiation
- ✅ Detailed status tracking (12 status values)

**Weaknesses:**
- ⚠️ No square footage data
- ⚠️ Date data sparse (24.0% populated)
- ⚠️ 30.9% unknown status

**Workload Distribution (Top 10):**
| Workload | Count |
|----------|-------|
| Colo | 582 |
| AI, Cloud | 285 |
| AI | 236 |
| Cloud | 230 |
| AI, Colo | 70 |
| AI, HPC | 56 |
| Cloud, Colo | 48 |
| AI, Cloud, Edge | 47 |
| AI, Cloud, Colo | 47 |
| Crypto | 24 |

---

## Ingestion Scripts

| Source | Script | Path |
|--------|--------|------|
| Orennia | `ingest_orennia.py` | `scripts/01_ingestion/ingest_orennia.py` |
| SemiAnalysis Global | `ingest_semianalysis_global.py` | `scripts/01_ingestion/ingest_semianalysis_global.py` |
| WoodMac | `ingest_woodmac.py` | `scripts/01_ingestion/ingest_woodmac.py` |

### Execution Order

Run in ArcGIS Pro Python window (after opening the project):

```python
# 1. Orennia (US coverage with grid data)
exec(open(r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\scripts\01_ingestion\ingest_orennia.py").read())

# 2. SemiAnalysis Global (capacity forecasts)
exec(open(r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\scripts\01_ingestion\ingest_semianalysis_global.py").read())

# 3. WoodMac (global project tracking)
exec(open(r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\scripts\01_ingestion\ingest_woodmac.py").read())
```

---

## Integration Strategy

### Layered Approach

```
┌────────────────────────────────────────────────────────────────────┐
│ Layer 3: Coverage Expansion                                        │
│    Orennia (US grid context) + WoodMac (global projects)          │
├────────────────────────────────────────────────────────────────────┤
│ Layer 2: Enrichment                                                │
│    SemiAnalysis (capacity forecasts, building detail)              │
├────────────────────────────────────────────────────────────────────┤
│ Layer 1: Foundation                                                │
│    DCH + Meta Canonical (existing trusted sources)                 │
└────────────────────────────────────────────────────────────────────┘
```

### Deduplication Strategy

1. **UCID-based campus matching**
   - 250m TIGHT threshold for urban areas
   - 500m standard threshold for rural areas

2. **Company name standardization**
   - All sources use `company_clean_filter` for tier grouping
   - Hyperscaler detection keywords applied consistently

3. **Priority weighting for conflicts:**
   ```
   Meta Canonical > DCH > SemiAnalysis > Orennia > WoodMac
   ```

### Field Inheritance Rules

| Field Type | Primary Source | Secondary | Notes |
|------------|---------------|-----------|-------|
| Coordinates | SemiAnalysis | Orennia | Prefer highest geocode rate |
| Capacity | SemiAnalysis | DCH | SA has methodology |
| Status | WoodMac | Orennia | Explicit status tracking |
| Grid/Utility | Orennia | N/A | Unique to Orennia |
| MW Forecasts | SemiAnalysis | N/A | Unique to SA |
| Workload Type | WoodMac | N/A | Unique to WoodMac |

---

## Post-Ingestion Workflow

After running ingestion scripts:

1. **Re-run UCID generation**
   ```python
   exec(open(r"...\scripts\03_ucid\generate_text_ucid.py").read())
   ```

2. **Re-run campus rollup**
   ```python
   exec(open(r"...\scripts\04_validation\campus_rollup.py").read())
   ```

3. **Run source comparison**
   ```python
   exec(open(r"...\scripts\04_validation\compare_data_sources.py").read())
   ```

4. **Update dashboard GeoJSON exports**
   ```python
   exec(open(r"...\scripts\export_to_geojson.py").read())
   ```

---

## Files Created/Updated

| File | Purpose |
|------|---------|
| `scripts/04_validation/analyze_new_sources.py` | Data quality analysis script |
| `scripts/01_ingestion/ingest_semianalysis_global.py` | New SA Global Import ingestion |
| `outputs/source_analysis_YYYYMMDD_HHMM.json` | Analysis results JSON |

---

## Next Steps

- [ ] Run ingestion scripts in ArcGIS Pro
- [ ] Re-run UCID generation after new sources
- [ ] Re-run campus rollup
- [ ] Update dashboard GeoJSON exports
- [ ] Validate overlap/deduplication with compare_data_sources.py
- [ ] Document any data quality issues found during ingestion

---

*Analysis Date: February 12, 2026*
*Author: Data Center GIS Team*
