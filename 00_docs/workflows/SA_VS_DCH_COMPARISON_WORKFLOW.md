# SemiAnalysis vs DataCenterHawk Comparison Workflow

**Created:** 2026-01-29
**Last SA Ingestion:** 2026-02-03 (5,852 records)
**Last Comparison:** 2026-02-04 (Grade B, MAPE 19.3%)
**Last Updated:** 2026-02-11
**Status:** ✅ Workflow Established | ✅ Campus-Level Comparison Implemented

---

## 📚 Related Methodology Documents

| Document | Purpose |
|----------|---------|
| **[SA_DCH_METHODOLOGY_RECOMMENDATIONS.md](SA_DCH_METHODOLOGY_RECOMMENDATIONS.md)** | 🆕 Detailed analysis of capacity, UCID, and granularity improvements |
| [UCID_DESIGN.md](UCID_DESIGN.md) | Universal Campus ID architecture |
| [GRANULARITY_STRATEGY.md](GRANULARITY_STRATEGY.md) | Source-specific granularity handling |
| [PIPELINE_DOCUMENTATION.md](PIPELINE_DOCUMENTATION.md) | Full pipeline context |

---

## 🆕 Session Updates (2026-02-11)

### Campus-Level Comparison (Major Enhancement)

Based on supervisor feedback regarding inflated site counts and company capacity totals (e.g., AWS showing 51 GW vs expected 20-25 GW), implemented campus-level comparison using existing pipeline infrastructure.

#### Issues Identified

| Issue | Root Cause | Solution |
|-------|------------|----------|
| Site counts inflated | Comparison used building records (5 buildings = 5 sites) | Now uses `gold_campus_full` (1 campus = 1 site) |
| Company GW totals 2-3x expected | Buildings inherit campus-level capacity values, causing double-counting | Campus rollup uses MAX aggregation to avoid duplication |
| Essential DC conflicts >1 GW | Granularity mismatch (campus vs building records matched) | Filter same-granularity pairs; show SA/DCH granularity in report |

#### Changes Made to `compare_sa_vs_dch_v2.py`

1. **Campus-level comparison by default** (`use_campus_level=True`)
   - Queries from `gold_campus_full` instead of `gold_buildings_full`
   - Uses existing campus rollup infrastructure (no duplicated code)

2. **Granularity filtering in all statistical functions**
   - `calculate_mape_and_bias()` — only same-granularity pairs
   - `calculate_cv()` — only same-granularity pairs
   - `calculate_agreement_rate()` — only same-granularity pairs
   - `calculate_tier_weighted_mape()` — only same-granularity pairs
   - `analyze_by_company()` — only same-granularity pairs for capacity totals

3. **Light/Dark mode toggle** in HTML report
   - Toggle button in top-right corner
   - Persists preference in localStorage
   - Chart.js colors update dynamically

4. **Essential DC conflicts table** now shows SA/DCH granularity columns

#### Usage

```python
# Campus-level comparison (DEFAULT - recommended)
exec(open(r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\scripts\05_accuracy\compare_sa_vs_dch_v2.py", encoding='utf-8').read())
run_comparison()

# Building-level comparison (if needed)
run_comparison(use_campus_level=False)
```

#### ⚠️ Pipeline Prerequisite

**Campus-level comparison requires the full post-ingestion pipeline to be run first:**

| Step | Script | Required? |
|------|--------|-----------|
| 1 | Ingestion scripts | ✅ Yes |
| 2 | `enrich_geography_fields.py` | ✅ Yes |
| 3 | `migrate_company_fields_v2.py` | ✅ Yes |
| 4 | `generate_text_ucid.py` | ✅ **Critical** |
| 5 | `campus_rollup_new.py` | ✅ **Critical** |
| 6 | `cleanup_gold_campus.py` | ✅ Yes |

Run all steps with:
```python
exec(open(r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\scripts\run_post_ingestion.py", encoding='utf-8').read())
```

---

## 🚀 Next Steps (For Next Session)

### Immediate Actions

1. **Re-run the full pipeline** to ensure `gold_campus_full` is current
   ```python
   exec(open(r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\scripts\run_post_ingestion.py", encoding='utf-8').read())
   ```

2. **Run campus-level comparison** and verify improved metrics
   ```python
   exec(open(r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\scripts\05_accuracy\compare_sa_vs_dch_v2.py", encoding='utf-8').read())
   run_comparison()  # Uses gold_campus_full by default
   ```

3. **Validate expected improvements**:
   - Site counts should be ~50% lower (campuses vs buildings)
   - Company GW totals should be closer to expected (AWS ~20-25 GW, not 51 GW)
   - Essential DC conflicts should have fewer 1 GW+ outliers

### Optional Verification

- **Building-level comparison** (for comparison/debugging):
  ```python
  run_comparison(use_campus_level=False)
  ```

### Potential Issues to Watch For

| Issue | Symptom | Solution |
|-------|---------|----------|
| Empty results | "No records loaded" error | Run `run_post_ingestion.py` first |
| Same inflated counts | Site counts unchanged | Verify `gold_campus_full` has fewer records than `gold_buildings_full` |
| Missing fields | Geography/company blank | Check enrichment scripts in pipeline |

---

## Overview

This document describes the workflow for refreshing and comparing SemiAnalysis (SA) and DataCenterHawk (DCH) datasets in the Consensus GIS Model.

---

## Data Sources

### DataCenterHawk (DCH) - Hive Tables

| Table | Hive Table Name | Records | Description |
|-------|-----------------|---------|-------------|
| **Hyperscale** | `idc_lsim_s_dch_hyperscale_details` | ~1,983 | Company-owned hyperscale DCs |
| **Colocation** | `idc_lsim_s_dch_facility_details` | ~5,341 | Leased/colo facilities |

- **Partition Column:** `ds` (date string, format: 'YYYY-MM-DD')
- **DaiQuery Workspace:** https://www.internalfb.com/intern/daiquery/workspace/1478092853227858/

### SemiAnalysis (SA) - Excel Pipeline

- **Source:** AI-Data-Center-Model-CLIENT Excel file
- **Pipeline:** `scripts/_utils/semianalysis_pipeline.py`
- **Guide:** `scripts/00_docs/workflows/SEMIANALYSIS_PIPELINE_GUIDE.md`

---

## Workflow: Refresh DCH from Hive

### Step 1: Query in DaiQuery

Go to: https://www.internalfb.com/intern/daiquery/workspace/1478092853227858/

**Hyperscale query:**
```sql
SELECT *
FROM idc_lsim_s_dch_hyperscale_details
WHERE ds = '2026-01-29'  -- Update to latest date
```

**Colocation query:**
```sql
SELECT *
FROM idc_lsim_s_dch_facility_details
WHERE ds = '2026-01-29'  -- Update to latest date
```

### Step 2: Download CSVs

- Export Hyperscale → `C:\Users\ptanderson\Downloads\DCH_Hyper_Raw.csv`
- Export Colocation → `C:\Users\ptanderson\Downloads\DCH_Colo_Raw.csv`

### Step 3: Import to Geodatabase

```python
exec(open(r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\scripts\01_ingestion\import_dch_csvs.py", encoding='utf-8').read())
```

### Step 4: Run Ingestion + Comparison

```python
exec(open(r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\scripts\05_accuracy\refresh_and_compare.py", encoding='utf-8').read())
main(refresh_sa=False, refresh_dch=True, run_compare=True)
```

---

## Workflow: Refresh SemiAnalysis

### Step 1: Update Pipeline Config

Edit `scripts/_utils/semianalysis_pipeline.py`:
```python
INPUT_FILE = r"C:\Users\ptanderson\Downloads\AI-Data-Center-Model-CLIENT-January-26-2026-SKU.xlsx"
```

### Step 2: Run SA Pipeline

```python
exec(open(r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\scripts\_utils\semianalysis_pipeline.py", encoding='utf-8').read())
```

### Step 3: Run SA Ingestion

Update `SOURCE_CSV` in `scripts/01_ingestion/ingest_semianalysis_v2.py` to the output from Step 2, then:

```python
exec(open(r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\scripts\01_ingestion\ingest_semianalysis_v2.py", encoding='utf-8').read())
```

---

## Scripts Created/Updated

| Script | Purpose |
|--------|---------|
| `scripts/05_accuracy/compare_sa_vs_dch.py` | Holistic comparison (7 dimensions) with HTML report |
| `scripts/05_accuracy/compare_sa_vs_dch_v2.py` | **NEW** Enhanced V2 comparison with MAPE, bias, CV, tier-weighting, and Chart.js visualizations |
| `scripts/05_accuracy/refresh_and_compare.py` | Orchestration script for refresh + compare |
| `scripts/01_ingestion/import_dch_csvs.py` | Import DCH CSVs from DaiQuery to geodatabase |
| `scripts/01_ingestion/fetch_dch_hive.py` | Direct Hive query (requires pyhive - use DaiQuery instead) |
| `scripts/05_accuracy/SA_vs_DCH_Comparison.ipynb` | Jupyter notebook (Bento) for Hive queries |
| `scripts/_utils/config.py` | Updated with HIVE_TABLES configuration |

---

## Post-Ingestion Pipeline (Required Before Comparison)

After ingesting new SA or DCH data, run the post-ingestion pipeline to enrich and prepare records for comparison:

```python
exec(open(r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\scripts\run_post_ingestion.py", encoding='utf-8').read())
```

### Pipeline Steps

| Step | Script | Purpose |
|------|--------|--------|
| 1. Geography Enrichment | `02_processing/enrich_geography_fields.py` | Populate region, state, state_abbr |
| 2. Company Standardization | `02_processing/migrate_company_fields_v2.py` | Normalize company_clean, company_clean_filter |
| 3. Essential DC Flag | `02_processing/integrate_essential_by_uid.py` | Flag 127 Essential DC buildings |
| 4. UCID Generation | `03_ucid/generate_text_ucid.py` | Assign Universal Campus IDs |
| 5. Campus Rollup | `02_processing/campus_rollup_new.py` | Aggregate buildings by UCID |
| 6. Cleanup Gold Campus | `02_processing/cleanup_gold_campus.py` | Populate lat/lon from geometry |
| 7. Create XB Combined | `06_visualization/create_xb_combined_layer.py` | Dashboard layer |
| 8. Export GeoJSON | `web_dashboard/08_web_export/export_to_geojson.py` | Web dashboard export |

### Why This Matters for Comparison

- **Geography Enrichment** → Enables regional accuracy breakdown
- **Essential DC Flags** → Allows filtering comparison to strategic facilities
- **UCID Generation** → Enables company-aware matching (vs pure spatial matching)

> ⚠️ **Important:** Without running post-ingestion, the comparison will use:
> - Spatial-only matching (may match wrong companies at multi-tenant sites)
> - Missing `is_essential` flags
> - Incomplete geography fields

---

## Comparison Results (2026-02-04)

### Summary

| Metric | SemiAnalysis | DataCenterHawk | Notes |
|--------|-------------|----------------|-------|
| **Total Records** | 5,852 | 7,052 | DCH has 1,200 more |
| **Matched Pairs** | 4,994 | 4,994 | 85.3% SA match rate |
| **SA-Only Records** | 858 | — | |
| **DCH-Only Records** | — | 2,058 | |
| **Significant Conflicts** | 2,236 | (44.8% of pairs) | |

### V2 Statistical Metrics

| Metric | Value | Interpretation |
|--------|-------|----------------|
| **MAPE** | 19.3% | Good agreement |
| **Systematic Bias** | +8.5% | SA reports slightly higher |
| **CV** | 415.1% | High variability in disagreement |
| **Pearson r** | 0.820 | Strong correlation |
| **Agreement Grade** | **B** | Good agreement |
| **Essential DCs Matched** | 114 / 127 | 89.8% coverage |

### Net New Sites Analysis

| Metric | SemiAnalysis | DataCenterHawk |
|--------|-------------|----------------|
| **Net New Sites** | 2,400 | 2,905 |
| **Net New Capacity** | 301,199 MW | 260,949 MW |
| **Coverage Rate** | 78.5% | 56.5% |
| **Net New MAPE** | 19.8% | — |
| **SA-Only Net New** | 517 (124 GW) | — |
| **DCH-Only Net New** | — | 1,263 (114 GW) |

### Key Findings

1. **Improved metrics after SA reingestion:**
   - MAPE improved from 29.1% → 19.3% (Grade C → B)
   - Pearson r improved from 0.642 → 0.820
   - Bias reduced from +35.2% → +8.5%

2. **Spatial Overlap:**
   - 85.3% of SA records have a DCH match within 500m
   - 70.8% of DCH records have a SA match

3. **Essential DC Coverage:**
   - 114 of 127 Essential DCs matched between sources
   - 41 Essential DCs have capacity conflicts

4. **SA Unique Strengths:**
   - Year-over-year forecasts (2023-2032) - 100% populated
   - Higher net new capacity (301 GW vs 261 GW)
   - Better net new coverage rate (78.5% vs 56.5%)
   - More emerging hyperscalers (xAI, ByteDance, Crusoe, Alibaba)

5. **DCH Unique Strengths:**
   - More total facilities (7,052 vs 5,852)
   - More net new sites detected (2,905 vs 2,400)
   - Better market field coverage (100% vs 67%)
   - Company tier classification (company_clean_filter)

6. **Data Gaps:**
   - SA has no `commissioned_power_mw` data
   - UK records: DCH has 262, SA has 0

### Latest Reports

**V2 HTML Report:**
```
G:\My Drive\Consensus GIS Model Cleaned Inputs\Admin Documentation\accuracy_reports\SA_vs_DCH_Comparison_V2_20260204_134127.html
```

**Excel Workbook:**
```
G:\My Drive\Consensus GIS Model Cleaned Inputs\Admin Documentation\accuracy_reports\SA_vs_DCH_Comparison_20260204_134127.xlsx
```

---

## Quick Commands Reference

### Check Data Vintages
```python
exec(open(r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\scripts\05_accuracy\refresh_and_compare.py", encoding='utf-8').read())
check_data_vintage()
```

### Run V1 Comparison (7 Dimensions)
```python
exec(open(r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\scripts\05_accuracy\compare_sa_vs_dch.py", encoding='utf-8').read())
```

### Run V2 Enhanced Comparison (MAPE, Bias, CV, Charts)
```python
exec(open(r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\scripts\05_accuracy\compare_sa_vs_dch_v2.py", encoding='utf-8').read())
run_comparison()
```

**V2 with options:**
```python
# Custom threshold (default 500m)
run_comparison(threshold_m=250)

# Skip certain outputs
run_comparison(output_html=False)  # Skip HTML
run_comparison(output_csv=False)   # Skip CSVs
run_comparison(output_fc=False)    # Skip feature class
```

### Full Refresh + Comparison
```python
exec(open(r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\scripts\05_accuracy\refresh_and_compare.py", encoding='utf-8').read())
main(refresh_sa=True, refresh_dch=True, run_compare=True)
```

---

## V2 Comparison Metrics Guide

### Statistical Metrics

| Metric | Formula | Interpretation | Target |
|--------|---------|----------------|--------|
| **MAPE** | mean(\|SA - DCH\| / max) × 100 | Overall accuracy (lower = better) | <25% (Grade B) |
| **Bias %** | mean(SA - DCH) / mean(DCH) × 100 | Systematic over/under-reporting | <15% |
| **CV** | std(delta) / mean(\|delta\|) × 100 | Consistency of disagreement | <30% |
| **Pearson r** | correlation(SA_cap, DCH_cap) | Linear relationship strength | >0.85 |
| **Agreement Rate** | % pairs within 20% | Simple agreement metric | >70% |

### Grade Scale

| MAPE Range | Grade | Interpretation |
|------------|-------|----------------|
| 0-10% | A | Excellent agreement |
| 10-20% | B | Good agreement |
| 20-35% | C | Moderate disagreement |
| 35-50% | D | Significant disagreement |
| >50% | F | Poor agreement |

### Tier Weighting

V2 calculates tier-weighted MAPE to prioritize accuracy for strategic facilities:
- **Hyperscaler**: 60% weight (AWS, Azure, Google, Meta, etc.)
- **Major Colo**: 30% weight (Equinix, Digital Realty, QTS, etc.)
- **Other**: 10% weight

### Output Artifacts (V2)

| Artifact | Location | Description |
|----------|----------|-------------|
| HTML Report | `scripts/00_docs/reports/SA_vs_DCH_Comparison_V2_*.html` | Interactive report with Chart.js visualizations |
| Matched Pairs CSV | `scripts/00_docs/reports/SA_DCH_Matched_Pairs_*.csv` | All matched facilities with deltas |
| SA-Only CSV | `scripts/00_docs/reports/SA_Only_Records_*.csv` | Facilities only in SemiAnalysis |
| DCH-Only CSV | `scripts/00_docs/reports/DCH_Only_Records_*.csv` | Facilities only in DataCenterHawk |
| Conflict FC | `Default.gdb/sa_dch_conflicts_*` | Feature class for ArcGIS Pro mapping |

---

## Bento Notes

**Bento Presto queries did not work** in the default Python 3 kernel. The workaround is to use **DaiQuery** directly for Hive queries, then download CSVs.

Attempted methods that failed:
- `bento.common.presto` - ModuleNotFoundError
- `analytics.bamboo` - requires namespace, validation errors
- `%%presto` magic - not found in kernel

---

## Next Steps

1. ~~**Refresh SA data**~~ ✅ Completed 2026-02-03 (5,852 records)
2. **Re-run V2 comparison** - Generate updated comparison with new SA data
3. **Automate DCH pull** - When Bento access is sorted, can automate the Hive query
4. **Schedule comparison** - Consider regular comparison reports
5. **Investigate gaps** - Why SA has 0 commissioned_power_mw, missing UK records

---

## Net New Sites Analysis (V2)

The V2 comparison now includes a dedicated **Net New Sites Analysis** section that focuses on facilities that are not yet operational:

### What It Analyzes

- **Under Construction** - Active construction projects
- **Announced** - Publicly announced future facilities
- **Planned** - In planning/approval stages
- **Proposed** - Proposed but not yet confirmed

### Key Metrics

| Metric | Description |
|--------|-------------|
| **SA Coverage Rate** | % of SA net new sites that also appear in DCH |
| **DCH Coverage Rate** | % of DCH net new sites that also appear in SA |
| **Net New MAPE** | Capacity agreement for matched net new sites |
| **Net New Bias** | Systematic capacity difference (SA vs DCH) |
| **Status Agreement** | % of pairs where both sources agree on construction stage |

### Insights Provided

- **Exclusive Detection**: Identifies sites that only one source reports, suggesting early detection advantages
- **Capacity Forecast Accuracy**: How well do SA and DCH agree on future capacity projections
- **Regional Patterns**: Geographic differences in net new site coverage
- **Company Breakdown**: Hyperscaler vs colo coverage for new construction

### HTML Report Section

The report includes:
- Summary metrics grid
- Coverage and agreement rates
- Breakdown by status type table
- Side-by-side top exclusive net new sites tables

---

## Related Documentation

| Document | Location |
|----------|----------|
| SA Pipeline Guide | `scripts/00_docs/workflows/SEMIANALYSIS_PIPELINE_GUIDE.md` |
| AI Context Prompt | `scripts/00_docs/context/AI_CONTEXT_PROMPT.md` |
| Data Source API Backlog | `scripts/00_docs/backlog/DATA_SOURCE_API_CONNECTIONS.md` |
| Config Module | `scripts/_utils/config.py` |

---

*Document created: 2026-01-29*
*Last updated: 2026-02-04*

---

## 📋 Pending To-Do List

### ✅ Completed

- [x] **Re-ingest SemiAnalysis dataset** — Completed 2026-02-03 11:29
  - Source: `semianalysis_FINAL_20260203_0916.csv`
  - Inserted: 5,852 records (54 skipped - missing lat/lon)
  - Deleted: 5,852 existing records (replaced)
  - ⚠️ Warning: `actual_live_date` dropped from 30.7% → 0.0%
  - 📈 Gains: `full_capacity_mw` +47.3%, `region` +48.3%, `commissioned_power_mw` +24.0%

### ⏳ In Progress (Required Sequence)

**Run post-ingestion pipeline before comparison:**

- [x] **Run `run_post_ingestion.py`** — Completed 2026-02-03 12:48-13:11
  - ✅ Geography Enrichment (229 region values enriched)
  - ✅ Company Standardization (410 company_clean updated, 5,852 company_clean_filter populated)
  - ✅ Essential DC Flags (127 buildings marked, 0 campuses)
  - ✅ UCID Generation (11,887 campuses, 23,264 buildings)
  - ✅ Campus Rollup (11,885 campus records)
  - ✅ Create XB Combined Layer (35,149 records)
  - ✅ Export GeoJSON (buildings: 30.4 MB, campuses: 13.1 MB, combined: 48.1 MB)

- [x] **Re-run V2 comparison** — Completed 2026-02-04
  - MAPE: 19.3% (Grade B)
  - Pearson r: 0.820
  - Essential DCs matched: 114/127

### High Priority (After Comparison)

- [x] **Add granularity filtering** — Completed 2026-02-04
    - Added `normalize_granularity()` function to standardize Building/Campus/Suite levels
    - MAPE/Bias/Correlation now calculated only on same-granularity matches
    - Report shows granularity match rate and breakdown
    - CSV exports include `sa_granularity`, `dch_granularity`, `granularity_match` columns

- [x] **Enhanced scatter plot** — Completed 2026-02-04
    - Added R² regression line alongside perfect agreement line
    - Added zoom controls (Reset, 0-500 MW, 0-200 MW, 0-100 MW)
    - Added pan/zoom capability (scroll to zoom, drag to pan)
    - Enhanced tooltips showing SA vs DCH delta MW and %

- [x] **Enhanced bar chart tooltips** — Completed 2026-02-04
    - Company and Region charts now show % of group and % of total
    - Footer shows group totals with overall percentage

- [x] **Added Land Acquisition to Net New** — Completed 2026-02-04
    - Net New statuses now include: Under Construction, Announced, Planned, Proposed, Land Acquisition

- [x] **Add source reliability summary to HTML report** — Completed 2026-02-04
    - Added "Conclusions & Recommendations" section after Ground Truth
    - Includes comparison summary table (sites, capacity, exclusive records, avg MW)
    - Key interpretation of coverage patterns
    - Recommendation framework for when to trust each source
    - Best practice guidance for capacity planning

- [ ] **Add forecasting reliability interpretation** — Based on ground truth (Meta Canonical) accuracy, SA's 11.9% MAPE vs DCH's 17.6% suggests SA is more reliable for capacity forecasting

- [ ] **Enhance comparison to use UCID-based matching** — After post-ingestion populates UCIDs, update V2 comparison to match on UCID instead of pure spatial proximity. Options:
    - Option A: Match on UCID (company-aware campus ID)
    - Option B: Spatial match + company name filter
    - Option C: Hybrid with company mismatch flagging

### Medium Priority

- [ ] **Add SA data vintage tracking** — Record which Excel file version was used for each comparison run

- [ ] **Automate DCH Hive pull** — When Bento/Presto access is sorted, create automated workflow

- [ ] **Investigate UK data gap** — DCH has 262 UK records, SA has 0

- [ ] **Investigate commissioned_power_mw gap** — SA has 0 MW, DCH has 78,739 MW

### Future Enhancements

- [ ] **Time series analysis** — Compare how each source's pipeline projections change over time

- [ ] **Lead time analysis** — If date fields become available, measure which source detects projects earlier

- [ ] **Regional accuracy breakdown** — Calculate MAPE by region to identify geographic strengths

- [ ] **Manifold hosting for HTML reports** — Host reports on Manifold + CDN for shareable links that don't require download
    - Create bucket at [Manifold Portal](https://www.internalfb.com/manifold/)
    - Enable Corpnet, set ACL: `proxygen-origin`: Read, `everyone`: Corp
    - URL pattern: `https://interncache-all.fbcdn.net/manifold/<bucket>/tree/<path>/report.html`
    - See [Hosting static HTML in Manifold](https://www.internalfb.com/wiki/Test_241/Hosting_static_HTML_in_Manifold_bucket/) for setup details

---

## 🔬 Known Limitations

### Spatial-Only Matching Disclaimer

The current comparison uses **spatial proximity matching only** (default 500m threshold). This means:

1. **Multi-tenant campuses** — A Google building and AWS building at the same location may be incorrectly matched
2. **Campus expansions** — Phase 1 and Phase 2 buildings from the same company may be matched to different records
3. **Company name variations** — "Amazon Web Services" vs "AWS" are checked AFTER matching, not used as a matching criterion

The UCID system in the main pipeline addresses this by grouping facilities by **location + company similarity**. A future enhancement could use UCID-based matching instead of pure spatial matching.

### Ground Truth Coverage

Meta Canonical validation is limited to ~643 buildings that overlap with SA/DCH. Accuracy grades reflect performance on this subset, which may not represent overall accuracy for smaller/regional facilities.

### Building-Level Granularity (Added 2026-02-10)

**All "sites" in this report are individual BUILDING records**, not aggregated campuses:

1. **Site Counts are Building Counts** — The Net New analysis counts individual building records, not physical campuses. A campus with 5 buildings = 5 "sites" in the report.

2. **Company Capacity Totals May Be Inflated** — The company summary (e.g., "AWS: 51 GW") sums `full_capacity_mw` from all building records. If building records inherit campus-level capacity values (common in SemiAnalysis data), the same capacity is counted multiple times.
   - **Example**: AWS campus with 200 MW total may have 5 building records each showing 200 MW → appears as 1,000 MW in company totals
   - **Recommendation**: For accurate portfolio totals, use campus-level UCID rollup or deduplicate by UCID before aggregation

3. **Large Conflicts (>500 MW) Often Indicate Granularity Mismatch** — When Essential DC conflicts show 1 GW+ differences, this typically means:
   - SA has a campus-level record matched to a DCH building-level record (or vice versa)
   - One source reports planned/full capacity while the other reports commissioned only
   - The V2 report now shows SA/DCH granularity columns in the Essential DC table to identify these cases

### Capacity Field Ambiguity

- **`full_capacity_mw`** — May include planned/future capacity, not just operational
- **`commissioned_power_mw`** — SA has 0% population, DCH has full coverage
- Company totals in the comparison use `full_capacity_mw` which overstates current operational capacity

### Recommended Interpretation Guidelines

| Metric | Current Behavior | Recommended Interpretation |
|--------|------------------|---------------------------|
| Site counts | Building-level | Divide by ~2-3 for approximate campus count |
| Company GW totals | Sum of building records | Use for relative comparison only, not absolute values |
| Essential conflicts >500 MW | May be granularity mismatch | Check SA/DCH granularity columns, investigate upstream |
| MAPE/Bias | Calculated on building pairs | Reliable for relative accuracy assessment |
