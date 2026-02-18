# 📋 AI Context Prompt — Data Center Consensus GIS Model (v56.0)

**Last Updated:** February 13, 2026 (Session 33)
**Status:** ✅ FOLDER REORGANIZATION COMPLETE | Orennia & WoodMac Ready for Ingestion

---

## ⚡ QUICK START (Resume Here)

### 🆕 Session 32 Completed (Feb 12, 2026)
**New source ingestion preparation complete:**
- ✅ Analyzed Orennia (3,575 records, 100% geocoded, US grid/utility data)
- ✅ Analyzed WoodMac (2,265 records, 96.7% geocoded, global project tracking)
- ✅ Created schema migration script with 15 new fields
- ✅ Updated ingestion scripts with new field mappings
- ✅ Updated MASTER_FIELD_MAPPING.md with Orennia/WoodMac sections
- ⏳ SemiAnalysis Global Import on hold (data quality issues to debug)

### 🔴 NEXT STEPS — Run in ArcGIS Pro:

**Note:** Schema migration script archived to `_archive/migrations/` (fields already added).

```python
# Step 1: Ingest Orennia (3,575 records)
exec(open(r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\scripts\01_ingestion\ingest_orennia.py").read())

# Step 2: Ingest WoodMac (2,265 records)
exec(open(r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\scripts\01_ingestion\ingest_woodmac.py").read())

# Step 3: Re-run UCID generation
exec(open(r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\scripts\03_ucid\generate_text_ucid.py").read())

# Step 4: Re-run campus rollup
exec(open(r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\scripts\02_processing\campus_rollup_new.py").read())
```

### Current Pipeline Stats
| Layer | Records | Description |
|-------|---------|-------------|
| `gold_buildings_full` | ~23,487 | Individual building/facility records |
| `gold_campus_full` | ~10,275 | Aggregated campus records (UCID grouped) |
| `gold_combined_xb` | ~34,257 | Combined XB layer for dashboard |

### Key Commands

```python
# Run full pipeline (ingestion → processing → validation)
exec(open(r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\scripts\run_full_pipeline.py", encoding='utf-8').read())

# Generate diagnostic report
exec(open(r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\scripts\04_validation\reports\generate_pipeline_report.py", encoding='utf-8').read())

# Export GeoJSON for web dashboard
exec(open(r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\web_dashboard\08_web_export\export_to_geojson.py", encoding='utf-8').read())
```

```powershell
# Start web dashboard
cd "C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\web_dashboard"
.\start_dashboard.ps1

# Sync docs to Google Drive
pwsh -File "C:\...\scripts\_utils\sync_to_gdrive.ps1"
```

---

## 🎯 Project Overview

Building a **production-ready data pipeline** for Meta's Infrastructure Planning team that:
1. Ingests 6 external vendor data sources + Meta's internal canonical data
2. Harmonizes them into standardized "gold" feature classes
3. Provides Meta canonical as ground truth for accuracy benchmarking
4. Produces repeatable, documented workflows for ongoing vendor evaluation

**This is a data pipeline project, not a one-off analysis.** Scripts must be dependable and repeatable.

---

## 📊 Data Sources

| Source | Records | Coords | Capacity | Key Features |
|--------|---------|--------|----------|--------------|
| **DataCenterMap** | ~8,453 | 95% ✅ | 33% | Largest external source |
| **DCH Hyper** | ~1,983 | 100% ✅ | 100% ✅ | Hyperscale buildings (from Hive) |
| **DCH Lease** | ~5,341 | 100% ✅ | 93% ✅ | Leased facilities (from Hive) |
| **Semianalysis** | ~5,772 | 95% ✅ | 98% ✅ | 10-year forecasts (mw_2023-2032), TLBM, Hyperscalers |
| **NewProjectMedia** | ~1,399 | 100% ✅ | 53% | US announced projects |
| **Meta Canonical** | ~643 | 57% ⚠️ | 100% ✅ | Internal ground truth (17.2 GW) |
| **Orennia** | ~3,575 | 100% ✅ | ✅ | Power capacity, grid operator, owner type |
| **WoodMac** | ~1,002 | ❌ 0% | ✅ | Project phases, cost/acreage (record_level=WoodMac_Project) |
| Synergy | ~1,003 | ❌ 0% | - | Enrichment only (no coordinates) - hyperscaler counts |

---

## 🏗️ Architecture

### Gold Tables Schema

**`gold_buildings_full`** — Individual buildings from all sources
- `unique_id` — Source-prefixed unique identifier (DCH_123, SA_456, SEMI_TLBM_*, etc.)
- `ucid` — Campus-level clustering ID (text, e.g., "US-VA-Ashburn-001")
- `source` — Origin dataset (DataCenterHawk, Semianalysis, etc.)
- `record_level` — Record type: Building, TLBM_Hyperscaler, TLBM_Colo
- `company_clean` — Standardized company name
- `company_clean_filter` — Tier grouping (AWS, Microsoft, Google, Meta, Apple, Oracle, Colo - All Other)
- `facility_status` — Active, Under Construction, Announced, Planned, etc.
- `full_capacity_mw`, `commissioned_power_mw`, `capacity_under_construction_mw`, `planned_capacity_mw`
- `mw_2023` through `mw_2032` — Year-by-year capacity (from Semianalysis)
- `market` — DC market/metro area (for TLBM geocoding)
- `is_essential` — Boolean flag for curated strategic sites

**`gold_campus_full`** — Campus-level aggregates (grouped by UCID)
- Aggregates capacity values from child buildings
- Tracks source overlap (e.g., "DataCenterHawk; Semianalysis")
- Contains `building_count`

**`gold_combined_xb`** — Union of buildings + campuses for web dashboard
- `record_level` = "Building" or "Campus"
- Optimized schema (41 fields, sparse building fields removed)

### UCID System

Campus-level spatial clustering identifier:
- Format: `{country}-{state}-{city}-{nnn}` (e.g., "US-VA-Ashburn-001")
- Generated by spatial proximity clustering (500m threshold)
- Source-agnostic — same UCID across all vendors

---

## 🔧 Pipeline Execution Order

All ingestion scripts **auto-delete existing records** before inserting (safe to re-run).

```
Step 1: Ingestion (6 scripts)
├── ingest_dch.py           # DCH Hyper
├── ingest_dch_lease.py     # DCH Lease
├── ingest_semianalysis_v2.py  # Semianalysis (V2 with dedup)
├── ingest_dcm.py           # DataCenterMap
├── ingest_npm.py           # NewProjectMedia
└── ingest_meta_canonical.py # Meta internal

Step 2: Processing
├── migrate_company_fields_v2.py  # Company standardization
└── integrate_essential_by_uid.py # Essential DC flag

Step 3: UCID Generation
└── generate_text_ucid.py

Step 4: Campus Rollup
└── campus_rollup_new.py

Step 5: Cleanup
└── cleanup_gold_campus.py  # Populate lat/lon from geometry

Step 6: XB Layer
└── create_xb_combined_layer.py
```

---

## 🌐 Web Dashboard

**Custom MapLibre dashboard** replacing ESRI Experience Builder.

### Architecture
```
web_dashboard/
├── backend/             # FastAPI server (port 8000)
│   └── main.py          # REST API with filtering, caching, exports
├── frontend/            # React + TypeScript + Vite (port 5173)
│   └── src/components/  # Map, Table, Charts, Filters
├── data/                # GeoJSON files (generated)
│   ├── buildings.geojson, campuses.geojson, combined.geojson
│   ├── lookups.json, statistics.json
└── 08_web_export/
    └── export_to_geojson.py
```

### Key Features
- **MapLibre GL JS** — Free, no API key, handles 34K+ points
- **Zoom-based visibility** — Campuses all zooms, Buildings at 14+
- **Company colors** — Solid dots (AWS orange, Microsoft green, etc.)
- **Arc/Pie status indicators** — Progress ring (100%=Active → 10%=Land Acq.)
- **Feature Popup** — Slide-in panel with executive summary, drill-down sections, 10-year trend chart
- **Filters** — Company, source, status, region, state, tier, capacity range, essential, hyperscalers
- **Export** — CSV and GeoJSON downloads

### Network Deployment
Dashboard migrated to shared server for internal team access:
```
\\snc-isiarchive03-smb\gsstnab_esrilab_smb_001\ICI_ConsensusDashboard
```

**Start on server:**
```powershell
cd "\\snc-isiarchive03-smb\gsstnab_esrilab_smb_001\ICI_ConsensusDashboard"
.\start_server.ps1
```

**Update after changes:**
```powershell
cd "C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\web_dashboard"
.\migrate_to_server.ps1
```

### Refresh Data
```python
# 1. Export GeoJSON after pipeline changes
exec(open(r"...\web_dashboard\08_web_export\export_to_geojson.py", encoding='utf-8').read())

# 2. Either reload cache OR restart backend
# Option A: Visit http://localhost:8000/api/reload
# Option B: Restart backend server
```

---

## 📁 Folder Structure (Updated Feb 13, 2026)

```
scripts/
├── 00_docs/                    # 📚 Documentation & PM
│   ├── context/                # AI_CONTEXT_PROMPT.md, SESSION_LOG.md
│   ├── pm/                     # WIP tracker, progress updates, PM dashboards
│   │   ├── progress/           # Consolidated progress updates
│   │   └── archive/            # Old PM dashboard versions
│   ├── schemas/                # Field definitions, mappings
│   ├── workflows/              # Pipeline docs, SOPs, design docs
│   ├── analysis/               # One-time analysis reports
│   ├── backlog/                # Future work items
│   └── reports/
│       └── dashboards/         # Interactive HTML dashboards, chart scripts
│
├── 01_ingestion/               # 🔽 Data ingestion (9 active scripts)
├── 02_processing/              # ⚙️ Transform, rollup, XB layer (includes create_xb_combined_layer.py)
├── 03_ucid/                    # 🔗 UCID generation
├── 04_validation/              # ✅ Validation & QA
│   ├── core/                   # Main validation scripts
│   ├── diagnostics/            # Ad-hoc investigation scripts
│   ├── reports/                # Report generators
│   └── fixes/                  # Data quality fixes
├── 05_accuracy/                # 📊 Accuracy analysis
├── 07_consensus/               # 🤝 Consensus layer for XB (BAV attributes)
├── 08_acres/                   # 🏞️ ACRES parcel project (paused)
├── 09_export/                  # 📤 Export scripts (renamed from 05_export)
│
├── _archive/                   # 📦 Superseded scripts (organized by category)
│   ├── consensus/, ingestion/, migrations/, notebooks/
│   ├── processing/, reports/, semianalysis/, validation/
│   └── README.md               # Archive inventory
│
├── _utils/                     # 🔧 Config, helpers, sync
│   ├── config.py               # Centralized paths (CRITICAL)
│   └── semianalysis_pipeline.py # SA V2 extraction
│
├── outputs/                    # 📁 All generated outputs
│   ├── reports/                # Generated HTML/CSV reports
│   │   ├── accuracy/           # SA vs DCH comparisons (latest 2)
│   │   └── diagnostics/        # Pipeline diagnostics (latest 2)
│   ├── analysis/               # JSON analysis files
│   └── logs/                   # Sync logs
│
├── run_full_pipeline.py        # 🚀 Master pipeline script
└── run_post_ingestion.py       # 🚀 Post-ingestion steps
```

**Key changes (Feb 13, 2026):**
- `06_visualization/` dissolved → `create_xb_combined_layer.py` moved to `02_processing/`
- `05_export/` renamed to `09_export/`
- Generated reports moved from `00_docs/reports/` to `outputs/reports/`
- Progress updates consolidated to `00_docs/pm/progress/`
- SA archive consolidated from `_utils/_sa_archive/` to `_archive/semianalysis/`
- Timestamped reports cleaned (keeping most recent 2 of each type)

---

## 📈 Scoring & Quality

### Weighted Source Scoring
```
Final Score = (Volume × 15%) + (Core × 30%) + (Capacity × 25%) + (Location × 20%) + (Richness × 10%)
```

### Capacity Accuracy (vs Meta Canonical)
| Source | MAPE | Grade |
|--------|------|-------|
| Semianalysis | 11.9% | A |
| DataCenterHawk | 17.6% | B |
| DataCenterMap | N/A | F (1.5% coverage) |
| NewProjectMedia | N/A | D (sparse) |

### Composite Consensus Score
```
Composite = (Tier-Weighted × 80%) + (Essential DC Coverage × 20%)
```

---

## 🔄 Recent Changes

### Session 31 (Feb 12, 2026) — New Source Ingestion + QA/QC

#### New Ingestion Scripts Created

| Script | Records | Coords | Status |
|--------|---------|--------|--------|
| `ingest_orennia.py` | 3,575 | 100% | ✅ Ready |
| `ingest_woodmac.py` (V2) | 2,265 | 96.7% | ✅ Ready (now has coords!) |
| `analyze_synergy.py` | 1,003 | 0% | ✅ Enrichment only |
| `compare_data_sources.py` | - | - | ✅ QA/QC tool |

#### WoodMac Major Upgrade
- **Old:** 999 records, 0% geocoded, US only
- **New:** 2,265 records, **96.7% geocoded**, 17 countries (global)
- New fields: workload, cost, acreage, finance_partner

#### SemiAnalysis Hive Pipeline QA Issues
- **Data Vintage:** December 2025 (not latest January)
- **Coordinates:** 0% populated (critical issue)
- **Format:** Pivoted (one row per year-quarter, not per building)
- **Column labeling:** First column is UUID but labeled "clusterid"
- **Action:** Follow up with Data Engineering

#### Synergy Business Intelligence Recommendations
- Keep as enrichment table (no coordinates)
- Best uses: Ownership intelligence (O/L/P), competitive positioning, validation

#### Commands to Run New Sources
```python
# Orennia (3,575 records)
exec(open(r"C:\...\scripts\01_ingestion\ingest_orennia.py", encoding='utf-8').read())

# WoodMac V2 (2,265 records, 96.7% geocoded!)
exec(open(r"C:\...\scripts\01_ingestion\ingest_woodmac.py", encoding='utf-8').read())

# Synergy analysis (no ingestion)
exec(open(r"C:\...\scripts\01_ingestion\analyze_synergy.py", encoding='utf-8').read())
```

### Session 30 (Feb 11, 2026) — Multi-Workflow Management

#### Problem Statement
New Meta Canonical dataset showed:
- **3,400 suites** (up from 1,218 — 179% increase)
- **643 buildings** (up from 318 — 102% increase)
- **17.2 GW capacity** (up from 2.5 GW — 589% increase)

Initial validation showed RED flags (67% null status, 67% null capacity, 0% coordinates).

#### Root Cause Analysis

1. **Coordinate Issue (RESOLVED)**
   - Initial check showed 0% coordinate coverage
   - **Root cause:** Script was looking for `latitude`/`longitude` attribute fields
   - **Reality:** Coordinates stored in SHAPE geometry field (correct for feature classes)
   - **Fix:** Updated validation to read from `SHAPE@XY` geometry token
   - **Result:** 68% record coverage, 75% capacity coverage with coordinates

2. **NULL Status/Capacity (EXPLAINED)**
   - 67% of records have no `new_build_status` or `it_load`
   - **Root cause:** Source table `idc_schedule_udm_consumption_table` stores multiple records per site for development milestones, phase gates, and activities
   - **DAI Query:** Uses `GROUP BY location_key` with `MAX()` aggregation
   - **Interpretation:** NULL records are early-stage/placeholder entries (land acquisitions, future expansion)
   - **Solution:** Create filtered dataset excluding placeholder records

#### Scripts Created

| Script | Purpose |
|--------|---------|
| `validate_meta_canonical.py` | Comprehensive data quality validation with quality flags |
| `diagnose_meta_canonical_schema.py` | Schema diagnostic for troubleshooting field/coordinate issues |
| `create_filtered_meta_canonical.py` | Create filtered dataset excluding placeholder records |

#### Filtered Dataset Results

| Metric | Full Dataset | Filtered Dataset |
|--------|--------------|------------------|
| Records | 3,400 | 1,320 (-61%) |
| Capacity | 17,230 MW | 17,230 MW (100%) |
| With Status | 33% | 84% |
| With Coordinates | 68% | 82% |

#### Configuration Updates

- Added `META_CANONICAL_V2_FILTERED` to `config.py`
- Updated `meta_deduplicate.py` with `USE_FILTERED = True` (default)
- Documented DAI query in `META_CANONICAL_WORKFLOW.md`

#### Validation Thresholds

| Check | Threshold | Flag |
|-------|-----------|------|
| Null Status Rate | >50% | ❌ RED |
| Null Capacity Rate | >50% | ❌ RED |
| Coordinate Coverage | <50% | ⚠️ YELLOW |
| Future/Unknown Capacity | >80% | ❌ RED |

#### Pipeline Commands (Updated)

```python
# Meta Canonical Validation + Filtered Pipeline
exec(open(r"C:\...\scripts\04_validation\validate_meta_canonical.py", encoding='utf-8').read())
exec(open(r"C:\...\scripts\04_validation\create_filtered_meta_canonical.py", encoding='utf-8').read())
exec(open(r"C:\...\scripts\02_processing\meta_deduplicate.py", encoding='utf-8').read())
exec(open(r"C:\...\scripts\01_ingestion\ingest_meta_canonical.py", encoding='utf-8').read())
```

### Session 28 (Jan 30, 2026) — SA vs DCH V2 + Net New Sites Analysis

#### Enhanced Comparison Script V2
- **New `compare_sa_vs_dch_v2.py`** with comprehensive statistical analysis
- **MAPE/Bias/CV/Pearson r** metrics with grade assignment (A-F)
- **Tier-weighted scoring** prioritizing hyperscaler accuracy (60% weight)
- **Bootstrap 95% confidence intervals** for MAPE
- **Chart.js visualizations:** scatter plot, histogram, company bar chart, regional distribution
- **Excel workbook export** with styled tabs (Matched Pairs, SA-Only, DCH-Only, Summary)
- **Conflict feature class** for ArcGIS Pro mapping

#### Net New Sites Analysis
- **`analyze_net_new_sites()` function** to compare Under Construction/Announced facilities
- **Key metrics added:**
  - SA/DCH coverage rates (81.6% vs 54.7%)
  - Net New MAPE: 22.2% (better than overall 29.1%)
  - Status breakdown table (Announced, Under Construction)
  - Exclusive site counts and capacity (SA-only: 449 sites, 134K MW)
- **Finding:** Neither source uses "Planned" status - all future projects are "Announced" or "Under Construction"

#### HTML Report Enhancements
- **Hover tooltips** on all metric boxes explaining what each metric means
- **Interpretation box** with natural language explanations based on actual values
- **Grade legend** with color-coded MAPE ranges (A-F)
- **Note** clarifying why "Planned" status shows zeros

#### Results Summary (Jan 30, 2026)
| Metric | Value | Interpretation |
|--------|-------|----------------|
| **Match Rate** | 85.8% (4,951 of 5,772) | High spatial overlap |
| **MAPE** | 29.1% | Grade C - moderate agreement |
| **Bias** | +35.2% | SA reports higher capacity |
| **CV** | 391.9% | High variance in disagreements |
| **Pearson r** | 0.64 | Moderate correlation |
| **Net New MAPE** | 22.2% | Better agreement on future sites |
| **SA-Only Net New** | 449 sites (134K MW) | Exclusive SA pipeline |
| **DCH-Only Net New** | 1,317 sites (121K MW) | DCH broader coverage |

#### Documentation Updated
- `SA_VS_DCH_COMPARISON_WORKFLOW.md` - Added Net New Sites Analysis section
- `PROJECT_OVERVIEW.html` - Added timeline entries for Jan 29-30 work
- `AI_CONTEXT_PROMPT.md` - Updated to v51.0 with session 28

### Session 27 (Jan 30, 2026) — ACRES Parcel Data Integration

#### New Data Source: ACRES (Land Parcel Tracking)
- **Purpose:** Track land acquisitions, ownership changes, and transaction history for data center sites
- **Data Provider:** ACRES (via Janna Daniel, Bradley Wilson)
- **Update Frequency:** Monthly (~15th of month)

#### HIVE Tables Available
| Table | Description |
|-------|-------------|
| `idc_lsim_datacenter_index_parcel_changes_centroid/polygon` | Ownership change history |
| `idc_lsim_datacenter_index_parcels_centroid/polygon` | Current ownership snapshot |
| `idc_lsim_datacenter_index_transactions_centroid/polygon` | Courthouse/assessor transactions |

#### Key Fields from Official Schema
| Field | Layer | Description |
|-------|-------|-------------|
| `entity` | All | Parent company (AMAZON_DATA_CENTERS, META_DATA_CENTERS, etc.) |
| `apn` | All | Assessor Parcel Number (primary key for joins) |
| `transaction_amount` | Transactions | **Sale price** - enables resale premium analysis |
| `buyer_name` / `seller_name` | Transactions | Ownership chain tracking |
| `owner_change_type` | Parcel Changes | "new owner", "previous owner", "internal transfer" |
| `new_record` | All | "new" = added in last 2 months |

#### Entity Distribution (748 parcels total)
- Amazon: 96 (12.8%), Microsoft: 87 (11.6%), DataBank: 66 (8.8%)
- Meta: 28 (3.7%), Vantage: 18 (2.4%)
- Others: Cologix, CoreSite, T5, Apple, Oracle, xAI, etc.

#### Scripts Created (08_acres/)
| Script | Purpose |
|--------|---------|
| `fetch_acres_hive.py` | Query ACRES from Hive tables |
| `ingest_acres.py` | Import from Portal/CSV |
| `acres_parcel_rollup.py` | Parcel → Campus centroid rollup (like buildings → campus) |
| `analyze_land_to_mw_lag.py` | Land acquisition → First MW timeline |
| `analyze_transaction_history.py` | Multi-transaction analysis (Vantage WI case study) |
| `ACRES_SCHEMA_REFERENCE.md` | Complete data dictionary |
| `README.md` | Module documentation |

#### Analysis Capabilities
1. **Parcel-to-Campus Rollup** - Collapse adjacent parcels into single-point centroids
2. **Time Lag Analysis** - Land sale date → First MW commissioned
3. **Multi-Transaction Tracking** - Ownership chains (e.g., Cloverleaf → Vantage)
4. **Resale Premium Analysis** - Using `transaction_amount` from Transactions layer

#### Vantage WI Case Study Query
```sql
SELECT apn, transaction_date, buyer_name, seller_name, transaction_amount
FROM idc_lsim_datacenter_index_transactions_polygon
WHERE ds = '2025-11-21' AND state = 'WI'
  AND (buyer_name LIKE '%VANTAGE%' OR seller_name LIKE '%CLOVERLEAF%')
```

#### Pending (Next Session)
- [ ] Run `ingest_acres.py` to pull data from Portal/Hive
- [ ] Run `acres_parcel_rollup.py` to create campus centroids
- [ ] Run `analyze_land_to_mw_lag.py` to calculate timelines
- [ ] Investigate Vantage WI Cloverleaf transaction chain
- [ ] Link ACRES campuses to Consensus Model via spatial join

### Session 26 (Jan 30, 2026) — Meta Canonical V3 + DCH Hive Refresh

#### Meta Canonical Major Update
- **3x more data:** 1,218 → 3,400 suites, 318 → 643 buildings
- **Total capacity:** ~17,230 MW (up from ~2,500 MW)
- **New import script:** `import_meta_canonical_v3.py` with change detection
- **Change report generated:** `Meta_Canonical_Change_Report_20260130_0847.md`
- **65 status changes detected** (e.g., Active Build → Complete Build)
- **112 IT load changes detected**

#### "Unlocated" Record Level
- **Problem:** 43% of Meta buildings (275) lack coordinates
- **Solution:** New `record_level = "Unlocated"` for buildings without coords
- **Similar to:** Semianalysis TLBM (Total Lease By Market) approach
- **Preserves:** All 17.2 GW of capacity while distinguishing spatial vs non-spatial
- **Queryable:** Filter by `record_level = 'Building'` for spatial analysis

#### DCH Hive Integration
- **Confirmed Hive tables:**
  - `idc_lsim_s_dch_hyperscale_details` (~1,983 records)
  - `idc_lsim_s_dch_facility_details` (~5,341 records)
- **DaiQuery workspace:** https://www.internalfb.com/intern/daiquery/workspace/1478092853227858/
- **CSV import workflow:** DaiQuery → CSV download → `import_dch_csvs.py`
- **Bento/Presto:** Did not work (module errors), using DaiQuery workaround

#### SA vs DCH Comparison
- **SA:** 5,772 records, 339,030 MW
- **DCH:** 7,052 records, 333,911 MW
- **Spatial overlap:** 94.6% of SA records match DCH within 500m
- **HTML report:** `SA_vs_DCH_Comparison_20260129_1650.html`

#### Scripts Created/Updated
| Script | Status | Purpose |
|--------|--------|---------|
| `import_meta_canonical_v3.py` | ✅ Created | New CSV format + change detection |
| `meta_deduplicate.py` | ✅ Updated | Added Jan 2026 notes |
| `ingest_meta_canonical.py` | ✅ Updated | Added "Unlocated" record_level |
| `campus_rollup_meta_canonical.py` | ✅ Created | Standalone campus rollup |
| `import_dch_csvs.py` | ✅ Created | Import DCH from DaiQuery CSVs |
| `compare_sa_vs_dch.py` | ✅ Created | 7-dimension comparison |
| `META_CANONICAL_WORKFLOW.md` | ✅ Updated | Complete rewrite |
| `SA_VS_DCH_COMPARISON_WORKFLOW.md` | ✅ Created | DCH refresh workflow |

#### Pending (for next session)
- **Run full pipeline steps 2-5** for Meta Canonical (geography enrichment, company standardization, UCID generation, essential flag)
- **Re-run step 6** (campus rollup) to include Meta with UCIDs
- **Update pipeline diagnostic report** with new stats
- **Update PROJECT_OVERVIEW.html** dashboard

### Session 25 (Jan 23, 2026) — TLBM + Hyperscaler Extraction
- **Added TLBM (Total Lease by Market) extraction** — 283 records with market-level aggregated leasing data
  - `TLBM_Hyperscaler`: 148 records (AWS, Google, Microsoft, Meta, Oracle)
  - `TLBM_Colo`: 135 records (Equinix, Digital Realty, CyrusOne, etc.)
  - 83% geocoded using market centroid lookup (~130 markets)
- **Added Hyperscalers & Neoclouds building extraction** — 386 building records from dedicated sheet
- **Market Centroid Geocoding** — ~130 DC markets with coordinates for TLBM geocoding
  - Major markets: Ashburn, Dallas, Phoenix, Chicago, Silicon Valley
  - Small/rural: Cedar Rapids, Harwood ND, Temple TX, Boydton VA
  - West Texas corridor: Midland, Odessa, Sweetwater, Big Spring
  - International: ~40 EMEA/APAC/LATAM markets + country fallbacks
- **Overseas TLBM structure handling** — Countries in Company column treated as Markets
- **Hyperscaler Summary → Validation only** — Summary tables used to validate building totals, not ingested
- **record_level field extended** — Now supports: Building, TLBM_Hyperscaler, TLBM_Colo
- **Ingestion updated** — TLBM records now ingested with centroid coordinates
- **Total Semianalysis records**: 6,221 (5,938 buildings + 283 TLBM)
- **Created repair_geodatabase.py** — GDB diagnostic and repair utility
- **Fixed Unicode encoding** — Replaced ✓⚠️❌ with ASCII for Windows cp1252 compatibility

### Session 24 (Jan 14, 2026) — Dashboard UX Enhancements
- **FeaturePopup slide-in panel** — Executive summary with drill-down sections, 10-year capacity trend chart
- **Hyperscalers Only toggle** — Filter to show only AWS, Microsoft, Google, Meta, Apple, Oracle, Alibaba, xAI
- **Essential Sites toggle moved** to Company filter section for better UX
- **Capacity Distribution Histogram** — Grouped bar chart by capacity bucket, color-coded by company
- **Company color consistency** — Chart colors now match map legend (Microsoft=green, Google=red)
- **Arc/Pie status indicators** — Replaced grayscale blur rings with progress arc visualization:
  - Active: 100% (full circle)
  - Under Construction: 75%
  - Announced: 50%
  - Planned: 25%
  - Land Acquisition: 10%
- **Coordinate-based feature matching** — Fixed MapLibre click handler with 0.2° tolerance
- **Legend updated** — Shows arc progress indicators with SVG stroke-dasharray

### Session 23 (Jan 13, 2026) — Year-over-Year MW Fix & Validation
- **Discovered duplicate year columns** ('2023' vs '2023.0') causing 70% data loss
- **Fixed upstream pipeline** with `normalize_column_names()` and `merge_duplicate_columns()`
- **Created validation module** (`validate_sa_ingestion.py`) for CSV-to-GDB comparison
- **Year MW fields improved:** 7% → 95% population
- **Total SA MW by 2032:** 317,484 MW across 3,546 facilities

### Session 22 (Jan 13, 2026) — Semianalysis V2 Pipeline
- **Unified SA extraction** with exact cell coordinates for all 3 sheets
- **Merged 322 duplicate UUIDs** (same-site phases) by SUMming capacity
- **AI Labs enrichment** — 278 records with end_user field
- **Records reduced** from 5,472 → 3,717 (clean, unique)

### Session 21 (Jan 13, 2026) — Dashboard Symbology
- Removed clustering — individual points always shown
- Zoom-based visibility (Campus all zooms, Buildings 14+)
- Fixed-size points, grayscale status ring
- Added `/api/reload` endpoint
- Fixed Essential Sites filter bug

### Session 20 (Jan 12, 2026) — Dashboard Launch
- Custom MapLibre dashboard replacing ESRI Experience Builder
- Company colors per brand table
- Source filter with "contains" logic
- Unified XB layer as default

---

## 📋 Google Drive Sync

Reports auto-sync nightly to Google Drive:
```
G:\My Drive\Consensus GIS Model Cleaned Inputs\Admin Documentation\
├── context/                 # AI_CONTEXT_PROMPT.md
├── dashboards/              # PROJECT_OVERVIEW.html
├── pipeline/                # Scripts for dev team
├── pipeline_diagnostics/    # PIPELINE_DIAGNOSTIC_*.html
├── progress_updates/        # Status dashboards
├── schemas/                 # Documentation
├── visualizations/          # Charts, diagrams
└── workflows/               # SOPs
```

**Manual sync:**
```powershell
pwsh -File "C:\...\scripts\_utils\sync_to_gdrive.ps1"
```

---

## ⚙️ Configuration

All scripts use centralized config (`_utils/config.py`):

```python
from config import GDB, GOLD_BUILDINGS, GOLD_CAMPUS, RAW_TABLES

# Key paths
GDB = r"...\Lean Consensus DC Model\Default.gdb"
GOLD_BUILDINGS = "gold_buildings_full"
GOLD_CAMPUS = "gold_campus_full"
META_CANONICAL_BUILDINGS = "meta_canonical_buildings"
META_CANONICAL_CAMPUS = "meta_canonical_campus"

# Output paths
OUTPUT_ROOT = Path("G:/My Drive/Consensus GIS Model Cleaned Inputs/Admin Documentation")
```

---

## 🐛 Known Issues & Notes

1. **Scripts require ArcGIS Pro Python environment** (uses `arcpy`)
2. **Essential campus matching** — Some SA campus_ids may not match (127/129 buildings match)
3. **DCH reports facility power** — Apply PUE ÷1.3 adjustment for IT load comparison
4. **Semianalysis reports IT capacity** — No adjustment needed
5. **DCH kW→MW conversion** — All ingestion scripts convert DCH kW values to MW (×0.001)
6. **Semianalysis raw table quirk** — Field names are `Field1`, `Field2`, etc. Row 1 contains actual headers.
7. **TLBM records** — Market-level aggregates with centroid coordinates, not building-level
8. **Windows cp1252 encoding** — Avoid Unicode symbols (✓⚠️❌) in Python scripts run via ArcGIS Pro

---

## 📚 Key Mapping References

### Company Tier Mapping (company_clean_filter)
Hyperscalers get their own name; everyone else → "Colo - All Other":
- **Keep distinct:** AWS, Microsoft, Google, Meta, Apple, Oracle, xAI, OpenAI, Anthropic, ByteDance, Crusoe, CoreWeave
- **Collapse:** All colocation providers → "Colo - All Other"

### Facility Status Standardization
| Raw Values | Gold Status |
|------------|-------------|
| "Operational", "Active", "Live" | Active |
| "Under Construction", "Building", "UC" | Under Construction |
| "Announced", "Planned", "Proposed" | Announced |
| "Cancelled", "Abandoned" | Cancelled |

### Region Mapping
| Countries | Region |
|-----------|--------|
| US, Canada, Mexico, Brazil, Chile, Colombia | AMER |
| UK, Germany, France, Netherlands, Ireland, Spain, etc. | EMEA |
| Japan, Australia, Singapore, India, South Korea, etc. | APAC |

### Source Unique ID Prefixes
| Source | Prefix | Example |
|--------|--------|---------|
| DCH Hyper | `DCH_` | DCH_12345 |
| DCH Lease | `DCH_L_` | DCH_L_6789 |
| Semianalysis | `SA_` | SA_uuid-here |
| DataCenterMap | `dcm_` | dcm_1001 |
| NewProjectMedia | `npm_` | npm_project-slug |
| Meta Canonical | `MetaCanonical_` | MetaCanonical_bldg_key |

---

## 📑 Excluded/Skipped Sources

| Source | Reason | Notes |
|--------|--------|-------|
| **Synergy** | 0% geocoded | No coordinates - unusable for spatial analysis |
| **WoodMac** | Wrong granularity | Reports "development phases" not physical buildings |

---

## 🔄 Multi-Workflow Management

This project is developed across multiple parallel chat sessions. To maintain consistency:

### Key Documents

| Document | Location | Purpose |
|----------|----------|---------|
| `WORKFLOW_WIP_TRACKER.md` | `00_docs/context/` | Central status across all workstreams |
| `SESSION_HANDOFF_TEMPLATE.md` | `00_docs/context/` | Consistent session transitions |

### Active Workstreams

| Workstream | Focus | Status |
|------------|-------|--------|
| **New Ingestion Sources** | Adding ACRES, Synergy, WoodMac, other vendors | 🟢 Active |
| **UCID Design** | Improving campus-level spatial clustering | 🟢 Active |
| **Dashboard Updates** | MapLibre dashboard enhancements | 🟡 Paused |

### Sync Protocol

1. **Start Session:**
   - Read `WORKFLOW_WIP_TRACKER.md` for current state
   - Check "Documentation Sync Queue" for pending updates
   - Update "Last Activity" for your workstream

2. **During Session:**
   - Update specific docs + tracker
   - Note cross-workstream impacts

3. **End Session:**
   - Update workstream status in tracker
   - Add pending items to sync queue
   - Create session handoff if needed

### Cross-Chat Context Sharing

When changes in one chat affect another:
1. Update `WORKFLOW_WIP_TRACKER.md` dependencies section
2. Add to "Documentation Sync Queue"
3. Note in your session handoff

---

## 🗂️ Related Documentation

| Document | Location | Purpose |
|----------|----------|---------|
| `SESSION_LOG.md` | `00_docs/context/` | Detailed session history |
| `PIPELINE_EXECUTION_ORDER.md` | `00_docs/workflows/` | Step-by-step pipeline commands |
| `MASTER_FIELD_MAPPING.md` | `00_docs/schemas/` | Source → Gold field lineage |
| `CAPACITY_FIELD_DEFINITIONS.md` | `00_docs/schemas/` | Capacity field meanings |
| `UCID_DESIGN.md` | `00_docs/workflows/` | UCID generation logic |
| `WEB_DASHBOARD_ARCHITECTURE.html` | `00_docs/workflows/` | Dashboard architecture diagram |
| `SEMIANALYSIS_PIPELINE_GUIDE.md` | `00_docs/workflows/` | SA V2 pipeline with TLBM extraction |
| `repair_geodatabase.py` | `_utils/` | GDB diagnostic and repair utility |

---

## 💡 Context for AI Assistant

**When resuming:**
1. Pipeline is complete and validated (~34K records)
2. Web dashboard is fully operational
3. All ingestion scripts auto-delete before inserting (safe to re-run)
4. Use `run_full_pipeline.py` to refresh all data
5. Use `export_to_geojson.py` after pipeline changes to update dashboard

**Key architectural decisions:**
- UCID for campus-level identity (source-agnostic)
- company_clean_filter for XB tier grouping
- Standalone Meta canonical layers for ground truth comparison
- Combined XB layer for single-layer dashboard consumption

---

*Copy this prompt into a new chat to continue!* 🚀
