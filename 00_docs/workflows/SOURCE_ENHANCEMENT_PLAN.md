# Source Enhancement Plan — Value-Based Source Integration

**Created:** January 12, 2026
**Updated:** February 11, 2026 (Session 30)
**Status:** 🟡 In Progress — Phase 2 (V2 Columns) COMPLETE, Phase 3-4 (Synergy/WoodMac) PLANNED
**Objective:** Integrate Synergy, WoodMac, and new Semianalysis columns based on unique value contribution

---

## Executive Summary

This document outlines the integration strategy for data enhancement initiatives:

| Initiative | Effort | Value | Risk | Status |
|------------|--------|-------|------|--------|
| **Semianalysis V2 Columns** | Medium (2-3 days) | High | Low | ✅ Complete (Session 22-23) |
| **TLBM + Hyperscaler Extraction** | Medium (2 days) | High | Low | ✅ Complete (Session 25) |
| **Meta Canonical V3** | Medium (1-2 days) | Critical | Low | ✅ Complete (Session 26, 29) |
| **DCH Hive Refresh** | Low (1 day) | High | Low | ✅ Complete (Session 26) |
| **ACRES Parcel Data** | Medium (2-3 days) | High | Low | 🟡 Scripts Ready (Session 27) |
| **SA vs DCH V2 Comparison** | Medium (2 days) | Medium | Low | ✅ Complete (Session 28) |
| **Synergy Integration** | Low (1-2 days) | Medium | Low | 📋 Planned |
| **WoodMac Integration** | Medium (3-5 days) | High | Medium | 📋 Planned |
| **New Vendor (TBD)** | TBD | TBD | TBD | 🔵 Intake |

**Key Insight from Supervisor:** Sources should be evaluated for their *unique value contributions*, not graded equally. Each source offers different strengths.

---

## ✅ COMPLETED: Semianalysis V2 Integration (Sessions 22-25)

### 2A. Schema Updates ✅ COMPLETE

**Script:** `02_processing/add_semianalysis_v2_fields.py` (EXECUTED)

8 new fields added across 3 feature classes:

| Table | New Fields | Status |
|-------|------------|--------|
| gold_buildings_full | end_user, tenant, gpu_cloud, workload_type | ✅ Added |
| gold_campus_full | end_user_list, tenant_list, has_ai_workload | ✅ Added |
| gold_combined_xb | end_user, tenant, gpu_cloud, workload_type | ✅ Added |

### 2B. Excel Extraction ✅ COMPLETE

**Pipeline:** `_utils/semianalysis_pipeline.py` — Unified extraction with exact cell coordinates

| Sheet | Records | Key Features |
|-------|---------|--------------|
| NA Data Center Supply | 3,500+ | Buildings with UUID, capacity, location |
| Overseas Data Center Supply | 1,800+ | International facilities |
| AI Labs | 278 | End_user enrichment, AI workload flags |
| TLBM Hyperscaler | 148 | Market-level aggregates |
| TLBM Colo | 135 | Colocation market aggregates |

### 2C. Year-over-Year MW Fields ✅ FIXED (Session 23)

**Problem:** 70% data loss due to duplicate columns ('2023' vs '2023.0')

**Solution:**
- Added `normalize_column_names()` to handle float column names
- Added `merge_duplicate_columns()` to SUM duplicate year values
- Created `validate_sa_ingestion.py` for CSV-to-GDB comparison

**Results:**
- Year MW fields: 7% → 95% population
- Total SA MW by 2032: 317,484 MW across 3,546 facilities

### 2D. TLBM + Hyperscaler Extraction ✅ COMPLETE (Session 25)

**New record_level values:**
- `Building` — Standard building-level records
- `TLBM_Hyperscaler` — 148 market-level aggregates (AWS, Google, Microsoft, Meta, Oracle)
- `TLBM_Colo` — 135 market-level aggregates (Equinix, Digital Realty, CyrusOne, etc.)

**Market Centroid Geocoding:**
- ~130 DC markets with coordinates
- 83% TLBM records geocoded
- Major markets: Ashburn, Dallas, Phoenix, Chicago, Silicon Valley
- International: ~40 EMEA/APAC/LATAM markets + country fallbacks

**Total Semianalysis records:** 6,221 (5,938 buildings + 283 TLBM)

---

## ✅ COMPLETED: Meta Canonical V3 (Sessions 26, 29)

### Major Data Update

| Metric | Old (V2) | New (V3) | Change |
|--------|----------|----------|--------|
| Suites | 1,218 | 3,400 | +179% |
| Buildings | 318 | 643 | +102% |
| Total Capacity | 2.5 GW | 17.2 GW | +589% |

### Data Quality Validation (Session 29)

**Initial Flags:**
- 67% null status
- 67% null capacity
- 0% coordinates (RESOLVED — geometry in SHAPE field, not attributes)

**Root Cause:** Source table stores multiple records per site for milestones/phases. NULL records are placeholders.

**Solution:** Created filtered dataset excluding placeholder records

| Metric | Full | Filtered |
|--------|------|----------|
| Records | 3,400 | 1,320 |
| Capacity | 17.2 GW | 17.2 GW |
| With Status | 33% | 84% |
| With Coords | 68% | 82% |

### "Unlocated" Record Level

- 43% of Meta buildings lack coordinates
- New `record_level = "Unlocated"` for buildings without coords
- Preserves all 17.2 GW while distinguishing spatial vs non-spatial

### Scripts Created

| Script | Purpose |
|--------|---------|
| `import_meta_canonical_v3.py` | New CSV format + change detection |
| `validate_meta_canonical.py` | Data quality validation with flags |
| `create_filtered_meta_canonical.py` | Exclude placeholder records |
| `diagnose_meta_canonical_schema.py` | Schema troubleshooting |

---

## ✅ COMPLETED: DCH Hive Refresh (Session 26)

### Hive Tables

| Table | Records | Coverage |
|-------|---------|----------|
| `idc_lsim_s_dch_hyperscale_details` | ~1,983 | 100% coords, 100% capacity |
| `idc_lsim_s_dch_facility_details` | ~5,341 | 100% coords, 93% capacity |

### Workflow

1. DaiQuery workspace: https://www.internalfb.com/intern/daiquery/workspace/1478092853227858/
2. Export CSV from DaiQuery
3. Run `import_dch_csvs.py` to ingest

---

## ✅ COMPLETED: SA vs DCH Comparison V2 (Session 28)

### Enhanced Comparison Metrics

| Metric | Value | Grade |
|--------|-------|-------|
| Match Rate | 85.8% | — |
| MAPE | 29.1% | C |
| Bias | +35.2% | SA higher |
| CV | 391.9% | High variance |
| Pearson r | 0.64 | Moderate |

### Net New Sites Analysis

| Source | Sites | Capacity |
|--------|-------|----------|
| SA-Only | 449 | 134K MW |
| DCH-Only | 1,317 | 121K MW |

### Outputs

- HTML report with tooltips and interpretation
- Excel workbook with styled tabs
- Conflict feature class for ArcGIS Pro

---

## 🟡 IN PROGRESS: ACRES Parcel Data (Session 27)

### Purpose

Track land acquisitions, ownership changes, and transaction history for data center sites.

### Data Source

- Provider: ACRES (via Janna Daniel, Bradley Wilson)
- Update frequency: Monthly (~15th of month)

### Hive Tables

| Table | Description |
|-------|-------------|
| `idc_lsim_datacenter_index_parcel_changes_centroid/polygon` | Ownership change history |
| `idc_lsim_datacenter_index_parcels_centroid/polygon` | Current ownership snapshot |
| `idc_lsim_datacenter_index_transactions_centroid/polygon` | Courthouse/assessor transactions |

### Entity Distribution (748 parcels)

| Company | Parcels | % |
|---------|---------|---|
| Amazon | 96 | 12.8% |
| Microsoft | 87 | 11.6% |
| DataBank | 66 | 8.8% |
| Meta | 28 | 3.7% |
| Vantage | 18 | 2.4% |
| Others | 453 | 60.6% |

### Scripts Created (08_acres/)

| Script | Purpose | Status |
|--------|---------|--------|
| `fetch_acres_hive.py` | Query ACRES from Hive | ✅ Ready |
| `ingest_acres.py` | Import from Portal/CSV | ✅ Ready |
| `acres_parcel_rollup.py` | Parcel → Campus centroid | ✅ Ready |
| `analyze_land_to_mw_lag.py` | Land acquisition → First MW timeline | ✅ Ready |
| `analyze_transaction_history.py` | Multi-transaction analysis | ✅ Ready |

### Pending Tasks

- [ ] Run `ingest_acres.py` to pull data from Portal/Hive
- [ ] Run `acres_parcel_rollup.py` to create campus centroids
- [ ] Run `analyze_land_to_mw_lag.py` to calculate timelines
- [ ] Link ACRES campuses to Consensus Model via spatial join

---

## 📋 PLANNED: Synergy Integration

### Current Exclusion Reason

| Source | Records | Why Excluded | Unique Value |
|--------|---------|--------------|--------------|
| **Synergy** | 956 | No coordinates | Owned/leased breakdown, facility counts |

### Approach: Validation/Enrichment Layer

Synergy cannot be ingested spatially, but can provide validation attributes via company+city matching.

### Unique Fields Synergy Provides

- `quantity` — Facility count per company/location
- `owned_or_leased_partner` — Ownership classification
- Focused on hyperscaler footprint

### Implementation Plan

1. **Create `synergy_enrichment` lookup table:**
   ```
   synergy_enrichment:
   ├── company_clean (standardized)
   ├── city
   ├── state_abbr
   ├── synergy_facility_count
   ├── synergy_owned_count
   ├── synergy_leased_count
   ├── synergy_reference_id
   └── match_confidence (exact/fuzzy)
   ```

2. **Match to gold_campus via company + city + state**
   - Exact match first
   - Fuzzy match on company name variations

3. **Add validation fields to gold_campus:**
   - `synergy_facility_count` — Cross-check field
   - `synergy_coverage` — Boolean flag

4. **Generate gap report:**
   - Locations Synergy sees but we don't have
   - Facility count mismatches

### Script to Create

`02_processing/integrate_synergy_validation.py`

---

## 📋 PLANNED: WoodMac Integration

### Current Exclusion Reason

| Source | Records | Why Excluded | Unique Value |
|--------|---------|--------------|--------------|
| **WoodMac** | 496 | Tracks dev phases, not buildings | Cost data, workloads, energy/cooling, site acres |

### Approach: Strategic Insights Layer

WoodMac provides unique project-level data not available elsewhere.

### Unique Fields WoodMac Provides

| Field | Value |
|-------|-------|
| `total_site_acres` | Land footprint |
| `data_center_acres` | DC building footprint |
| `land_cost_usd_million` | Land acquisition cost |
| `overall_cost_usd_million` | Total project cost |
| `workloads` | AI/HPC vs. general (TRAINING/INFERENCE indicator!) |
| `energy` | Energy source info |
| `cooling` | Cooling system type |
| `prior_use` | Greenfield vs. brownfield |
| `cod` | Commercial operation date |

### Implementation Plan

1. **Create `woodmac_pipeline_master` table:**
   - Consolidate DC + Campus tables
   - Deduplicate phases to unique projects
   - Join coordinates from existing `woodmac_coords` table

2. **Add enrichment fields to gold_campus:**
   ```
   woodmac_enrichment fields:
   ├── wm_total_site_acres
   ├── wm_project_cost_usd_m
   ├── wm_land_cost_usd_m
   ├── wm_workload_type (HPC, AI, Colo, General)
   ├── wm_energy_source
   ├── wm_cooling_type
   ├── wm_cod_date
   └── wm_match_confidence
   ```

3. **Create pipeline analysis views:**
   - Projects by stage (Announced → Permitting → Construction → Active)
   - 3-5 year capacity pipeline forecast
   - Cost per MW analysis by developer

4. **Match to gold_campus:**
   - Spatial match (within 1km of WoodMac coords)
   - Company + city fallback

### Scripts to Create

- `02_processing/create_woodmac_master.py`
- `02_processing/integrate_woodmac_enrichment.py`

---

## 🔵 INTAKE: New Vendor Source

**Status:** Not yet documented

**Information Needed:**
- Data format and schema
- Update frequency
- Unique fields provided
- Coordinate availability
- Licensing/access details

---

## 📋 Implementation Checklist

### ✅ Phase 1: Semianalysis V2 (COMPLETE)
- [x] Schema updates for new fields
- [x] Excel extraction automation
- [x] Year-over-year MW field fix
- [x] TLBM + Hyperscaler extraction
- [x] Ingestion validation

### ✅ Phase 2: Meta Canonical V3 (COMPLETE)
- [x] Import new CSV format
- [x] Data quality validation
- [x] Create filtered dataset
- [x] Handle "Unlocated" record level
- [x] Change detection reporting

### ✅ Phase 3: DCH Refresh (COMPLETE)
- [x] DaiQuery workflow established
- [x] CSV import script created
- [x] SA vs DCH comparison v2

### 🟡 Phase 4: ACRES Integration (IN PROGRESS)
- [x] Scripts created
- [ ] Data pull from Hive/Portal
- [ ] Parcel rollup execution
- [ ] Land-to-MW lag analysis
- [ ] Consensus Model linkage

### 📋 Phase 5: Synergy Integration (PLANNED)
- [ ] Create `integrate_synergy_validation.py`
- [ ] Create synergy_enrichment lookup table
- [ ] Generate gap analysis report
- [ ] Add synergy_coverage field to gold_campus

### 📋 Phase 6: WoodMac Integration (PLANNED)
- [ ] Create `create_woodmac_master.py`
- [ ] Create `integrate_woodmac_enrichment.py`
- [ ] Add enrichment fields to gold_campus
- [ ] Create pipeline analysis views
- [ ] Generate cost/workload reports

### 📋 Phase 7: New Vendor (PLANNED)
- [ ] Document data format and schema
- [ ] Assess coordinate availability
- [ ] Create ingestion script
- [ ] Integrate into pipeline

---

## 📊 Source Summary After Enhancements

| Source | Records | Coords | Capacity | Unique Value | Status |
|--------|---------|--------|----------|--------------|--------|
| **Semianalysis** | ~6,221 | 95% | 98% | 10-year forecasts, TLBM, AI workloads | ✅ Production |
| **Meta Canonical** | ~1,320 | 82% | 100% | Internal ground truth, 17.2 GW | ✅ Production |
| **DCH Hyper** | ~1,983 | 100% | 100% | Hyperscale buildings | ✅ Production |
| **DCH Lease** | ~5,341 | 100% | 93% | Leased facilities | ✅ Production |
| **DataCenterMap** | ~8,453 | 95% | 33% | Largest external coverage | ✅ Production |
| **NewProjectMedia** | ~1,399 | 100% | 53% | US announced projects | ✅ Production |
| **ACRES** | ~748 | 100% | N/A | Land parcels, transactions | 🟡 Scripts ready |
| **Synergy** | ~956 | 0% | — | Validation/enrichment only | 📋 Planned |
| **WoodMac** | ~496 | ~80% | — | Cost, workload, timeline data | 📋 Planned |

---

## 🔗 Related Documentation

| Document | Purpose |
|----------|---------|
| `SEMIANALYSIS_PIPELINE_GUIDE.md` | SA V2 extraction with TLBM |
| `META_CANONICAL_WORKFLOW.md` | Meta import workflow |
| `SA_VS_DCH_COMPARISON_WORKFLOW.md` | Comparison methodology |
| `08_acres/README.md` | ACRES module documentation |
| `WORKFLOW_WIP_TRACKER.md` | Cross-workstream status |

---

*Last Updated: February 11, 2026 (Session 30)*
