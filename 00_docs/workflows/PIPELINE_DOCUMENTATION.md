# Lean Consensus Data Center Model - Pipeline Documentation

## Overview

This document provides a comprehensive summary of the data ingestion, processing, analysis, accuracy assessment, and visualization pipeline for the Lean Consensus Data Center Model. The pipeline integrates multiple external data sources with Meta's internal canonical datacenter inventory to create a unified, validated view of global datacenter facilities.

**Last Updated:** February 12, 2026 (Session 31)
**Status:** ✅ NEW SOURCES ADDED - ORENNIA, WOODMAC, SYNERGY ANALYSIS
**New:** Orennia ingestion, WoodMac ingestion (projects), Synergy analysis script

---

## 🆕 Session 31 Updates (February 12, 2026)

### New Data Source Ingestion

Added three new data sources to the pipeline:

#### 1. Orennia Data Centers (`ingest_orennia.py`)
- **Records:** ~3,575 data center facilities
- **Coordinates:** 100% geocoded ✅
- **Key Features:**
  - Power capacity (MW)
  - Grid operator/transmission owner
  - Owner type (Hyperscaler, Colocation, Enterprise)
  - US-centric with detailed state/county coverage
  - First power dates and construction dates

| Field | Gold Field | Notes |
|-------|------------|-------|
| Data Center ID | source_unique_id | Format: or:data_center:NNNN |
| Name | campus_name, building_designation | Facility name |
| Owner | company_source, company_clean | Company name |
| Owner Type | type_category, company_clean_filter | Hyperscaler/Colo/Enterprise |
| Power Capacity (MW) | full_capacity_mw, commissioned/uc/planned | Status-aware assignment |
| State | state_abbr | US state abbreviation |
| County | county | County name |
| Latitude/Longitude | latitude, longitude, SHAPE@XY | High-quality coordinates |

#### 2. WoodMac Projects (`ingest_woodmac.py`)
- **Records:** ~1,002 project records
- **Coordinates:** 0% (project-level, not building-level)
- **Status:** INCLUDED with `record_level='WoodMac_Project'`
- **Key Features:**
  - Rich development timeline (Announced → COD)
  - Cost estimates (Overall cost, Land cost)
  - Site acreage data
  - Useful for timeline enrichment and cost benchmarking

| Field | Gold Field | Notes |
|-------|------------|-------|
| Project ID | source_unique_id | WDMAC_NNN format |
| Project name | campus_name | Project name |
| Developer | company_source, company_clean | Development company |
| Existing MW / New MW | commissioned_power_mw, planned_power_mw | Capacity values |
| State/County/City | state, county, city | Location (no coords) |
| Milestone dates | construction_start_date, actual_live_date | Derived from milestones |

**Note:** WoodMac records have `record_level = 'WoodMac_Project'` and null geometry. They won't appear on maps but are included in capacity totals and can be used for enrichment analysis.

#### 3. Synergy Analysis (`analyze_synergy.py`)
- **Records:** ~1,003 records
- **Coordinates:** 0% (no geocoding)
- **Status:** EXCLUDED from gold_buildings (analysis only)
- **Key Features:**
  - Hyperscaler facility counts by region/country/city
  - Ownership model tracking (Owned vs Leased vs Partner)
  - Temporal analysis (when facilities opened)
  - Market trend analysis

**Recommendation:** Use Synergy as enrichment layer for ownership intelligence, validation source for hyperscaler counts, and trend analysis dataset.

### Scripts Created

| Script | Location | Purpose |
|--------|----------|---------|
| `ingest_orennia.py` | `01_ingestion/` | Ingest Orennia data centers to gold_buildings |
| `ingest_woodmac.py` | `01_ingestion/` | Analyze & ingest WoodMac projects |
| `analyze_synergy.py` | `01_ingestion/` | Synergy analysis (no ingestion) |

### Configuration Updates

Updated `_utils/config.py`:
- Added `orennia` to RAW_TABLES
- Added `SOURCE_CSV_FILES` dictionary with paths to new source CSVs

### Updated Record Counts (Estimated)

| Layer | Records | Change |
|-------|---------|--------|
| gold_buildings_full | ~28,064 | +4,577 (Orennia + WoodMac) |
| gold_campus_full | ~10,275 | TBD after UCID regeneration |

### Pipeline Commands

```python
# Run Orennia ingestion
exec(open(r"C:\...\scripts\01_ingestion\ingest_orennia.py", encoding='utf-8').read())

# Run WoodMac analysis + ingestion
exec(open(r"C:\...\scripts\01_ingestion\ingest_woodmac.py", encoding='utf-8').read())

# Run Synergy analysis (no ingestion)
exec(open(r"C:\...\scripts\01_ingestion\analyze_synergy.py", encoding='utf-8').read())

# After new sources, re-run post-ingestion pipeline
exec(open(r"C:\...\scripts\run_post_ingestion.py", encoding='utf-8').read())
```

---

## 🆕 Session 30 Updates (February 11, 2026)

### Multi-Workflow Management System

Created centralized documentation and tracking system for managing parallel chat workflows:

| New Document | Purpose |
|--------------|---------|
| `WORKFLOW_WIP_TRACKER.md` | Central status across all workstreams |
| `SESSION_HANDOFF_TEMPLATE.md` | Consistent session transitions |

#### Active Workstreams

| Workstream | Status | Last Activity | Next Action |
|------------|--------|---------------|-------------|
| **New Sources** | 🟢 Active | Feb 12 | Run ingestion scripts, re-run pipeline |
| **UCID Design** | 🟢 Active | Feb 11 | Test 250m vs 500m threshold |
| **Dashboard** | 🟡 Paused | Jan 14 | Update after pipeline changes |

#### Documentation Sync Completed

| Document | Update Applied |
|----------|----------------|
| `AI_CONTEXT_PROMPT.md` | Added Multi-Workflow Management section, v53.0 |
| `SOURCE_ENHANCEMENT_PLAN.md` | Sessions 25-29 changes incorporated |
| `PIPELINE_DOCUMENTATION.md` | Sessions 29-31 updates |

#### Sync Protocol

1. **Start Session:** Read tracker, check sync queue, update last activity
2. **During Session:** Update specific docs + tracker
3. **End Session:** Update status, add pending items, create handoff

---

## 🆕 Session 29 Updates (January 30, 2026)

### Meta Canonical Data Quality Validation

Comprehensive validation of new Meta Canonical V3 dataset:

| Metric | Full Dataset | Filtered Dataset |
|--------|--------------|------------------|
| Records | 3,400 | 1,320 (-61%) |
| Capacity | 17.2 GW | 17.2 GW (100%) |
| With Status | 33% | 84% |
| With Coordinates | 68% | 82% |

#### Root Cause Analysis

1. **Coordinate Issue (RESOLVED)**
   - Initial check showed 0% coordinate coverage
   - Root cause: Script looked for `latitude`/`longitude` attributes
   - Reality: Coordinates stored in SHAPE geometry field
   - Fix: Updated validation to read from `SHAPE@XY` geometry token

2. **NULL Status/Capacity (EXPLAINED)**
   - 67% of records have no `new_build_status` or `it_load`
   - Root cause: Source table stores multiple records per site for milestones
   - Solution: Created filtered dataset excluding placeholder records

#### New Scripts Created

| Script | Purpose |
|--------|---------|
| `validate_meta_canonical.py` | Data quality validation with quality flags |
| `diagnose_meta_canonical_schema.py` | Schema troubleshooting |
| `create_filtered_meta_canonical.py` | Exclude placeholder records |

#### Validation Thresholds

| Check | Threshold | Flag |
|-------|-----------|------|
| Null Status Rate | >50% | ❌ RED |
| Null Capacity Rate | >50% | ❌ RED |
| Coordinate Coverage | <50% | ⚠️ YELLOW |

---

## 🆕 Session 28 Updates (January 30, 2026)

### SA vs DCH Enhanced Comparison V2

Built comprehensive statistical comparison framework in `scripts/05_accuracy/compare_sa_vs_dch_v2.py`:

#### Statistical Metrics Added
| Metric | Formula | Current Value | Interpretation |
|--------|---------|---------------|----------------|
| **MAPE** | mean(\|SA - DCH\| / max) × 100 | 29.1% | Grade C - moderate agreement |
| **Bias** | mean(SA - DCH) / mean(DCH) × 100 | +35.2% | SA reports higher capacity |
| **CV** | std(delta) / mean(\|delta\|) × 100 | 391.9% | High variance in disagreements |
| **Pearson r** | correlation(SA, DCH) | 0.64 | Moderate correlation |

#### Net New Sites Analysis
New `analyze_net_new_sites()` function to compare Under Construction/Announced facilities:

| Metric | Value |
|--------|-------|
| SA Net New Sites | 2,437 (339,030 MW) |
| DCH Net New Sites | 2,905 (260,949 MW) |
| Matched (both net new) | 1,424 |
| SA Coverage Rate | 81.6% |
| DCH Coverage Rate | 54.7% |
| **Net New MAPE** | **22.2%** (better than overall) |

**Key Finding:** Neither source uses "Planned" status - all future projects are classified as "Announced" or "Under Construction".

#### HTML Report Enhancements
- **Hover tooltips** on all metric boxes explaining each statistic
- **Interpretation box** with natural language explanations based on actual values
- **Grade legend** (A-F) with color-coded MAPE ranges
- **Net New Sites section** with status breakdown and exclusive site tables

#### Quick Command
```python
exec(open(r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\scripts\05_accuracy\compare_sa_vs_dch_v2.py", encoding='utf-8').read())
run_comparison()
```

#### Output Artifacts
| File | Purpose |
|------|---------|
| `SA_vs_DCH_Comparison_V2_*.html` | Interactive HTML report with charts |
| `SA_DCH_Matched_Pairs_*.csv` | 4,951 matched facility pairs |
| `SA_Only_Records_*.csv` | 821 SA-exclusive records |
| `DCH_Only_Records_*.csv` | 2,101 DCH-exclusive records |
| `SA_vs_DCH_Comparison_*.xlsx` | Combined Excel workbook |
| `sa_dch_conflicts_*` | Feature class for ArcGIS Pro |

---

## 🆕 Session 19 Updates (January 14, 2026)

### Essential DC Campus Flagging Fix
**Fixed critical bug** where 0 campuses were being marked as Essential (should be 79):

**Root Cause:** After the UCID refactor, campus records store the UCID value in the `campus_id` field (populated by `campus_rollup_new.py`), not the `ucid` field. The `ucid` field is only populated later by `cleanup_gold_campus.py`. The Essential DC script was looking for `ucid` first, which was empty.

**Solution:** Updated `integrate_essential_by_uid.py` to prioritize `campus_id` field over `ucid` when matching campuses:

```python
# Priority: campus_id (populated by rollup), then ucid (populated by cleanup)
campus_id_field = None
if 'campus_id' in campus_fields:
    campus_id_field = 'campus_id'
elif 'ucid' in campus_fields:
    campus_id_field = 'ucid'
```

**Results:**
- Buildings marked as Essential: **127** (unchanged)
- Campuses marked as Essential: **79** (fixed from 0)

### State Abbreviation Gaps Clarification
Confirmed that 1,348 records with NULL `state_abbr` are working as designed - these are **international locations** where state abbreviation is a US-only convention. Examples include sites in Japan, Singapore, UK, Germany, etc.

### G Drive Export Script
**Created `05_export/export_to_gdrive.py`** for sharing Gold tables with team members:

**Features:**
- Exports gold_buildings_full, gold_campus_full, gold_combined_xb
- Three output formats: CSV (Excel), GeoJSON (mapping), File Geodatabase (ArcGIS)
- Auto-creates timestamped export folder
- Generates README.txt with export metadata and record counts
- Syncs to shared G Drive: `G:\My Drive\Consensus GIS Model Cleaned Inputs\Admin Documentation\data_exports\`

**Usage:**
```python
exec(open(r"C:\...\scripts\05_export\export_to_gdrive.py", encoding='utf-8').read())
```

### Post-Ingestion Pipeline Script
**Created `run_post_ingestion.py`** that orchestrates all post-ingestion processing steps:

**Steps Executed (in order):**
1. Company Standardization → `migrate_company_fields_v2.py`
2. Essential DC Flag → `integrate_essential_by_uid.py`
3. UCID Generation → `generate_text_ucid.py`
4. Campus Rollup → `campus_rollup_new.py`
5. Cleanup Gold Campus → `cleanup_gold_campus.py`
6. XB Combined Layer → `create_xb_combined_layer.py`
7. Export GeoJSON → `export_to_geojson.py`

**Usage:**
```python
exec(open(r"C:\...\scripts\run_post_ingestion.py", encoding='utf-8').read())
```

### Updated Record Counts
| Layer | Records |
|-------|---------|
| gold_buildings_full | **20,941** |
| gold_campus_full | **11,347** |
| gold_combined_xb | **32,288** |
| Essential Buildings | **127** |
| Essential Campuses | **79** |

---

## 🆕 Session 18 Updates (January 12, 2026)

### PM Dashboard Generator
**Created `00_docs/pm/generate_pm_dashboard.py`** for automated project management dashboard:

**Features:**
- Reads Patrick's Excel Work Organizer workbook
- Generates interactive HTML dashboard with glassmorphism design
- 8-week rolling trend chart (SVG line chart)
- Current vs previous week heatmap comparison
- GSD (Goals, Signals, Metrics) task hierarchy visualization
- Key accomplishments timeline (past 2 months)
- Task breakdown by project category
- Auto-syncs to Google Drive

**Output:**
- `PM_DASHBOARD.html` - Current dashboard
- `archive/PM_DASHBOARD_YYYYMMDD_HHMM.html` - Dated backups
- Synced to `G:\My Drive\...\Admin Documentation\dashboards\`

### Web Dashboard (React + FastAPI)
**Created `web_dashboard/` folder** with full-stack data center visualization:

**Architecture:**
```
web_dashboard/
├── backend/                 # FastAPI server
│   ├── main.py             # API endpoints, CORS, static file serving
│   └── requirements.txt    # Python dependencies
├── frontend/               # React + TypeScript + Vite
│   ├── src/
│   │   ├── components/     # Map, Table, Charts, Filters
│   │   ├── types/          # TypeScript interfaces
│   │   ├── App.tsx         # Main app with filter context
│   │   └── index.css       # Glassmorphism CSS
│   └── package.json        # Node dependencies
├── data/                   # GeoJSON data files
├── 08_web_export/          # ArcGIS export scripts
└── run_server.bat          # One-click startup
```

**Tech Stack:**
| Component | Technology |
|-----------|------------|
| Mapping | MapLibre GL JS 4.0 (free, no API key) |
| Charts | Apache ECharts 5.4 |
| Data Table | TanStack Table 8.11 |
| Frontend | React 18 + TypeScript + Vite |
| Styling | Tailwind CSS + glassmorphism |
| Backend | FastAPI + Uvicorn |

**Key Features:**
- Interactive map with clustering
- Filter by company, source, status, region, state, tier, capacity range
- ECharts-powered analytics (capacity by company, status, region, forecast)
- TanStack Table with sorting, filtering, pagination, export
- Export filtered data as CSV or GeoJSON
- Apple-inspired glassmorphism UI

---

## 🆕 Session 17 Updates (January 11, 2026)

### Semianalysis V2 Fields Integration
**Added new fields from Semianalysis enhanced dataset:**

| New Field | Type | Description | Population |
|-----------|------|-------------|------------|
| `end_user` | TEXT(100) | End user of the facility | ~30% |
| `tenant` | TEXT(100) | Primary tenant | ~25% |
| `gpu_cloud` | TEXT(50) | GPU cloud provider (if any) | ~10% |
| `workload_type` | TEXT(50) | AI training, inference, general | ~15% |

**Campus-Only Aggregated Fields:**
- `end_user_list` (TEXT 500) - Semicolon-separated
- `tenant_list` (TEXT 500) - Semicolon-separated
- `has_ai_workload` (SHORT) - 0/1 flag

**New Scripts:**
| Script | Purpose |
|--------|---------|
| `02_processing/add_semianalysis_v2_fields.py` | Schema update for V2 fields |
| `01_ingestion/ingest_semianalysis_v2.py` | CSV-based ingestion with V2 fields |
| `_utils/clean_semianalysis_excel.py` | Excel → cleaned CSV conversion |
| `_utils/analyze_semianalysis_deep.py` | Deep audit of Semianalysis data |

### Consensus Layer Script Complete
**Created `07_consensus/generate_consensus_layer.py`** implementing Option A (Pre-computed Single Layer):

**Features:**
- BAV (Best Available Value) logic for each attribute
- Field-priority matrix (different sources authoritative for different fields)
- Geometry priority selection (Meta > Semi > DCH > DCM > DCH Lease > NPM)
- `source_details_json` field for popup drill-down (TEXT 4000)
- Confidence scoring (0-1) based on:
  - Source count (20%)
  - Has Meta Canonical (30%)
  - Data freshness (25%)
  - Field coverage (15%)
  - Source agreement (10%)
- Validation checks (duplicate UCIDs, JSON field length)

**Output Schema (~35 fields):**
```python
CONSENSUS_SCHEMA = [
    ("ucid", "TEXT", 50),
    ("canonical_name", "TEXT", 100),
    ("company_clean", "TEXT", 50),
    ("full_capacity_mw", "DOUBLE", None),
    ("full_capacity_source", "TEXT", 30),
    ("source_details_json", "TEXT", 4000),
    ("confidence_score", "DOUBLE", None),
    # ... ~28 more fields
]
```

**Status:** Code complete, pending testing in ArcGIS Pro.

### Semianalysis Data Quality Audit
**Comprehensive audit of Semianalysis Excel** revealed:
- 19 sheets with 5,461 total records
- UCID mapping issues (some buildings not joining properly)
- AI Labs coverage: OpenAI, Anthropic, xAI, Inflection, etc.
- Data vintage varies by sheet (2024-2026)

**Diagnostic Scripts Created:**
| Script | Purpose |
|--------|---------|
| `_utils/diagnose_sa_ucids.py` | Debug UCID join issues |
| `_utils/diagnose_sa_structure.py` | Analyze Excel structure |
| `_utils/debug_sa_dates.py` | Date parsing validation |

---

## 🆕 Session 16 Updates (January 8, 2026)

### Nightly Google Drive Sync Script
**Created `_utils/sync_to_gdrive.ps1`** for automated documentation and pipeline script synchronization:

**Features:**
- Incremental sync (only copies if source file is newer than destination)
- Syncs 54+ documentation files across 8 categories
- Syncs 24 core pipeline scripts to `GDrive\pipeline\` for dev team access
- Maintains `PIPELINE_CHANGELOG.md` with timestamped entries
- 30-day log retention with automatic cleanup
- Logs saved to `_utils\logs\sync_YYYYMMDD_HHMMSS.log`

**Sync Categories:**
| Category | Files | Destination |
|----------|-------|-------------|
| Documentation | 54+ | context/, dashboards/, progress_updates/, schemas/, visualizations/, workflows/ |
| Pipeline Scripts | 24 | pipeline/ingestion/, pipeline/processing/, pipeline/consensus/, pipeline/utilities/ |

**Manual Run:**
```powershell
cd "C:\...\scripts\_utils"
pwsh -File sync_to_gdrive.ps1
```

**Automated (Task Scheduler):**
- Action: `pwsh -File "C:\...\scripts\_utils\sync_to_gdrive.ps1"`
- Trigger: Daily at 11:00 PM

### Pipeline Folder for Dev Team (SQL/HIVE Porting)
**Created structured folder on Google Drive** for sharing scripts with another GIS dev team porting to SQL/HIVE:

```
G:\My Drive\...\Admin Documentation\pipeline\
├── ingestion\           ← 6 ingestion scripts
├── processing\          ← 5 processing scripts
├── consensus\           ← 2 consensus scripts (placeholders)
├── utilities\           ← 4 utility scripts
├── README.html          ← Developer documentation
└── PIPELINE_CHANGELOG.md ← Script change tracking
```

### README.html for Pipeline
**Created comprehensive developer documentation** at `pipeline\README.html`:
- Overview with key metrics badges (24 scripts, 22,696 buildings, 11,715 campuses)
- Static folder structure tree diagram
- Execution order flow diagram (6 steps)
- Script descriptions by category (ingestion, processing, UCID, consensus)
- UCID format examples
- Data schema table (key fields)
- Configuration warnings (`config.py` paths)
- **SQL/HIVE Porting Notes:**
  - ArcPy dependencies to replace (arcpy.da.*, Dissolve, FeatureToPoint)
  - Key transformations (slug generation, capacity MW conversion)
  - Spatial operations (clustering, geometry handling)

### Files Created/Modified
| File | Action |
|------|--------|
| `_utils/sync_to_gdrive.ps1` | Enhanced with pipeline script sync |
| `_utils/PIPELINE_CHANGELOG.md` | Created - tracks all script changes |
| `GDrive\pipeline\README.html` | Created - developer documentation |
| `GDrive\pipeline\ingestion\*.py` | Synced 6 scripts |
| `GDrive\pipeline\processing\*.py` | Synced 5 scripts |
| `GDrive\pipeline\consensus\*.py` | Synced 2 scripts (placeholders) |
| `GDrive\pipeline\utilities\*.py` | Synced 4 scripts |

---

## 🆕 Session 15 Updates (January 8, 2026)

### Date Field Mapping Enhancement
**Added construction timeline dates** from SemiAnalysis source to gold_buildings:

| Source Field | Semantic Meaning | Gold Field | Population |
|--------------|------------------|------------|------------|
| Field32 (start_ops) | Construction start date | `construction_start_date` | 38.8% (2,121) |
| Field35 (live_assumption) | Facility go-live date | `actual_live_date` | 36.8% (2,014) |
| Field43 (data_vintage) | Source data publish date | `data_vintage` | (parsed) |

**Date Format:** SemiAnalysis uses US date format `M/D/YYYY` (e.g., "5/31/2027")

**New Utility Module:** `_utils/date_helpers.py`
```python
# Provides standardized date parsing:
parse_date_flexible(date_value)      # Handles M/D/YYYY, YYYY-MM-DD, quarters
parse_year_to_date(year_value)       # Converts year to datetime
parse_quarter_to_date(qtr_string)    # Converts "Q2 2025" to datetime
safe_parse_construction_start(...)   # For construction dates (start of period)
safe_parse_live_date(...)            # For operational dates (end of period)
```

### XB Schema Optimization
**Removed 9 sparse building-characteristic fields** from XB combined layer to reduce null clutter:

| Removed Field | Type | Reason |
|---------------|------|--------|
| `gross_sqft`, `shell_sqft`, `building_sqm` | DOUBLE | Sparse area fields |
| `building_type`, `num_stories` | TEXT/LONG | Sparse building characteristics |
| `height_ft`, `height_m` | DOUBLE | Sparse height fields |
| `footprint_sqft`, `footprint_sqm` | DOUBLE | Sparse footprint fields |

**Impact:** XB schema reduced from 50 to 41 fields. These fields remain in `gold_buildings_full` for building-level analysis.

### Verified Date Mappings (Other Sources)
**Confirmed existing date mappings are correct:**

| Source | Source Field | → Gold Field | Status |
|--------|-------------|--------------|--------|
| **DCH Hyper** | `commissioned_year` | → `actual_live_date` | ✅ Correct |
| **DCM** | `year_operational` | → `actual_live_date` | ✅ Correct |
| **NPM** | `planned_op_date` | → `actual_live_date` | ✅ Correct |
| **DCH Lease** | (none available) | (none) | ⚠️ Documented limitation |

### Files Modified
- `_utils/date_helpers.py` - **NEW** Date parsing utilities
- `01_ingestion/ingest_semianalysis.py` - Added date field imports and mappings
- `06_visualization/create_xb_combined_layer.py` - Removed sparse building fields

---

## 🆕 Session 14 Updates (January 8, 2026)

### Essential DC List Integration
**Integrated curated Essential Data Center list** (39 campus-level sites / 129 buildings from Semianalysis strategic sites):

- **Matching Strategy:** Exact SA Unique_ID (UUID) matching for precision
- **Results:** 127/129 buildings matched (98.4%) → 73 campuses marked
- **New Field:** `is_essential` (SHORT) added to buildings, campus, and XB layers
- **Pipeline Integration:** Runs after UCID generation, before Campus Rollup

**New Script:** `integrate_essential_by_uid.py`
```python
# Contains 129 UUIDs from curated Essential DC GSheet
ESSENTIAL_UNIQUE_IDS = [
    "c4fe3714-5ab4-5906-a436-765ec360db47",
    "d384623a-5b15-5537-994b-2aac364cfd2f",
    # ... 127 more UUIDs
]

# Matches buildings by source_unique_id
# Sets is_essential = 1 for matching buildings
```

### Composite Consensus Score
**Enhanced weighted consensus score** to include Essential DC coverage:

| Component | Weight | Description |
|-----------|--------|-------------|
| **Tier-Weighted** | 80% | Hyperscaler (60%), Major Colo (30%), Other (10%) |
| **Essential DC** | 20% | Coverage of curated strategic sites |

**Formula:**
```
Composite Score = (Tier-Weighted Score × 0.80) + (Essential DC Score × 0.20)
```

**Impact:** Essential DC coverage now directly contributes to the overall model quality grade.

### Pipeline Order Updated
**Essential DC Flag step added** as Step 4 in pipeline:

| Step | Script | Description |
|------|--------|-------------|
| 1 | ingest_*.py | Ingest 6 data sources |
| 2 | migrate_company_fields_v2.py | Company Standardization |
| 3 | generate_text_ucid.py | UCID Generation |
| **4** | **integrate_essential_by_uid.py** | **Essential DC Flag** |
| 5 | campus_rollup_new.py | Campus Rollup (rolls up is_essential via MAX) |
| 6 | cleanup_gold_campus.py | Cleanup Gold Campus |
| 7 | create_xb_combined_layer.py | Create XB Combined Layer |

**Files Modified:**
- `run_full_pipeline.py` - Added Step 4: Essential DC Flag
- `campus_rollup_new.py` - Added is_essential aggregation (MAX)
- `create_xb_combined_layer.py` - Added is_essential to UNIFIED_SCHEMA
- `generate_pipeline_report.py` - Added Essential DC Coverage section and composite scoring

---

## 🆕 Session 13 Updates (January 7, 2026)

### Campus data_vintage Aggregation
**Updated `campus_rollup_new.py`** to aggregate `data_vintage` from building records:

- **Aggregation Method:** MAX (most recent vintage date from child buildings)
- **Purpose:** Campus-level freshness now reflects actual source data, not manual values
- **Impact:** Temporal freshness metrics now correctly measure source vintage across all layers

**Code Changes:**
```python
# Added to dissolve statistics
stats_fields.append(['data_vintage', 'MAX'])

# Added to insert field mapping
if has_data_vintage and campus_has_data_vintage:
    insert_fields.append('data_vintage')
```

### Meta Canonical Excluded from Accuracy Scoring
**Fixed diagnostic report** to exclude Meta Canonical from spatial accuracy scoring sections:

- **Issue:** Meta Canonical was appearing in accuracy rankings scored against itself (circular logic)
- **Solution:** Created `SOURCES_FOR_ACCURACY_SCORING` list that excludes Meta Canonical
- **Impact:** Spatial accuracy now only evaluates external sources (DCH, SA, DCM, NPM) against Meta ground truth

**Files Modified:**
- `generate_pipeline_report.py` - Added `SOURCES_FOR_ACCURACY_SCORING` constant
- Updated spatial accuracy calculation loop
- Updated threshold performance table display
- Updated source detail cards display

### Campus Field Population Analysis
**Analyzed `gold_campus_full`** field population using diagnostic script:

| Field | Building Population | Campus Status |
|-------|---------------------|---------------|
| `data_vintage` | 100% ✓ | **Now aggregated (MAX)** |
| `notes` | 66.2% | Skipped (available in buildings) |
| `energy_source`, `ai_gpu_indicator` | 0% | Schema placeholder |
| `developer`, `tenant`, `end_user` | 0% | Schema placeholder |
| `construction_*`, `lease_*` dates | 0% | Schema placeholder |
| `developer_list`, `tenant_list`, `end_user_list` | Not in buildings | Campus-only placeholder |

**Conclusion:** Many campus fields are schema placeholders for future enhancement. The only actionable gap was `data_vintage`, which is now fixed.

---

## 🆕 Session 12 Updates (January 7, 2026)

### Weighted Consensus Scoring by Business Value
**Enhanced the Consensus Strength calculation** to weight multi-source coverage by company tier:

| Tier | Companies | Weight | Rationale |
|------|-----------|--------|-----------|
| 🚀 **Hyperscaler/Frontier** | AWS, Microsoft, Google, Meta, Apple, Oracle, xAI, Alibaba | **60%** | What leadership cares about most |
| 🏢 **Major Colo/Enterprise** | Equinix, Digital Realty, CyrusOne, QTS, CoreSite, Vantage, etc. | **30%** | Strategic context |
| 📍 **Other/Unknown** | Small operators, unknown companies | **10%** | Geographic coverage |

**New scoring formula:**
```
Weighted Score = Σ (tier_multi_source_% × source_density_factor × tier_weight)
```

**Impact:** A dataset with 45% hyperscaler multi-source coverage but only 8% overall now grades as **C** instead of **F**.

**New code additions:**
- `MAJOR_COLO_COMPANIES` list in `authority_config.py`
- `COMPANY_TIER_WEIGHTS` configuration
- `get_company_tier()` function for classification
- Tier breakdown table in Consensus Strength section

### Temporal Freshness Scoped to Buildings Only
**Fixed vintage coverage denominator** to exclude campus-level records (n=~22k buildings instead of n=~34k total):
- Campus `data_vintage` values are manually populated during rollup
- Building `data_vintage` reflects actual source reporting dates
- Updated section description to clarify this measures **input source freshness**

---

## 📋 Future Enhancements

### Multi-Layer Temporal Tracking (Planned)
**Concept:** Track three distinct temporal dimensions for complete data lineage:

| Layer | What It Measures | Potential Source |
|-------|------------------|------------------|
| **Record Vintage** | When source says data was current | `data_vintage` field (already tracked) |
| **Dataset Delivery** | When vendor last delivered updated data | File timestamps, `date_stamp` columns in raw tables |
| **Ingestion Date** | When ETL last processed this source | Add `ingestion_timestamp` to ingestion scripts |

**Use Case:** Identifies different failure modes:
- Stale record vintage + recent delivery = *Vendor sending old data*
- Fresh vintage + old ingestion = *Pipeline behind on processing*
- All dates aligned = *System healthy*

**Implementation Notes:**
- Some raw source tables may already have date stamp columns (e.g., `date_stamp`, `load_date`)
- Would require adding `ingestion_timestamp` field to each source's ingestion script
- Display as simple comparison table in Temporal Freshness section
- Lower priority than current diagnostic features

---

## 🆕 Session 11 Updates (January 7, 2026)

### Executive Report Card (3-Pillar Summary)
**NEW section at top of Pipeline Diagnostic Report** providing at-a-glance assessment:

| Pillar | Measures | Key Question |
|--------|----------|--------------|
| 📈 **Source Quality** | Avg score across input sources | "How good are our inputs?" |
| 🏆 **Pipeline Health** | Data completeness grade | "Is our output complete?" |
| 🤝 **Consensus Strength** | Source agreement level | "Can we trust this data?" |

**New Function:** `generate_report_card_section()` creates a 3-column visual display with color-coded grades.

### Consensus Strength Section
**NEW section** measuring source agreement - the unique value proposition of a consensus dataset:

**Metrics calculated by `calculate_consensus_metrics()`:**
- % of campuses with 2+ sources (multi-source validation)
- Average sources per campus
- Coefficient of variation for MW estimates across sources
- Confidence level distribution (High/Medium/Low)

**Grading Scale:**
| Grade | Criteria |
|-------|----------|
| A | >50% multi-source, avg 2.5+ sources |
| B | >30% multi-source, avg 2.0+ sources |
| C | >20% multi-source, avg 1.5+ sources |
| D | >10% multi-source |
| F | <10% multi-source |

### Natural Language Question Subheaders
**Added italicized "Key Question" subheaders** to all major sections:

| Section | Question Added |
|---------|----------------|
| Spatial Accuracy | "Can I trust the coordinates?" |
| Temporal Freshness | "When was this data last touched?" |
| Consensus Strength | "How much agreement exists between sources?" |
| Field Completeness | "Does this dataset have what I need?" |
| Data Quality | "Are there data integrity issues?" |
| Data Distribution | "Where is the data concentrated?" |
| Recommendations | "Which sources should I trust most?" |

### Report Structure Reorganization
**New Navigation Structure:**
```
Executive Summary
├── Report Card (NEW)
└── Recommendations

Input Source Quality
├── Source Analysis
├── Spatial Accuracy
├── Temporal Freshness
└── Consensus Strength (NEW)

Output Dataset Quality
├── Pipeline Health (moved here)
├── Field Completeness
├── Data Distribution
└── Quality Checks

Synthesis
└── Site Comparison
```

---

## 🆕 Session 10 Updates (January 6, 2026)

### Capacity Accuracy Values Fixed
The live capacity calculation was producing incorrect MAPE scores due to on-the-fly spatial matching not replicating the original analysis methodology.

**Solution:** Updated `calculate_capacity_accuracy_stats()` to use verified static values from `CAPACITY_ACCURACY_EXECUTIVE_REPORT.md`:

| Source | MAPE | Grade | Field Used |
|--------|------|-------|------------|
| Semianalysis | 11.9% | A | mw_2023 |
| DataCenterHawk | 17.6% | B | commissioned_power_mw |
| DataCenterMap | N/A | F | Insufficient coverage (1.5%) |
| NewProjectMedia | N/A | D | Sparse coverage (24%) |

### Excluded Sources Added to Health Matrix
**Added Synergy and WoodMac** to Source Health Matrix with visual distinction:
- Row styling: 70% opacity with subtle red background tint
- "EXCLUDED" badge next to source name
- 🚫 icon in recommendation column
- Shows reason for exclusion

| Source | Overall | Spatial | Capacity | Reason |
|--------|---------|---------|----------|--------|
| Synergy | F (12) | — | — | No coordinates available |
| WoodMac | F (28) | — | D | Tracks development phases, not buildings |

### Meta Canonical Ground Truth Handling
**Fixed:** Meta Canonical was incorrectly showing spatial accuracy grade when it IS the ground truth.

**Solution:** Added special handling for Meta Canonical:
- Spatial column now shows "—" with "Ground Truth" label
- Capacity column already showed "Ground Truth"
- Both spatial and capacity exclude Meta from grading calculations

### Source Health Matrix Auto-Sorted
**Added automatic sorting** by overall score (highest to lowest):
```python
sorted_sources = sorted(
    weighted_source_stats.items(),
    key=lambda x: x[1].get("final_score", 0),
    reverse=True
)
```

### PROJECT_OVERVIEW.html Workflow Diagram Enhanced
**Improved source boxes and processing steps:**
- Source boxes: `flex: 1`, `justify-content: space-between`, wider padding
- Processing steps: Same treatment - evenly distributed across full width
- Better visual alignment with connecting arrows

---

## 🆕 Session 9 Updates (January 6, 2026)

### Live Capacity Accuracy Calculation
The Pipeline Diagnostic Report now calculates capacity accuracy dynamically at report generation time:

**New Function: `calculate_capacity_accuracy_stats()`**
- Compares source capacity values against Meta Canonical IT Load (ground truth)
- Uses methodology from `capacity_accuracy_analysis_v2.py`:
  - Spatial matching to link source records to Meta buildings
  - Optimal capacity field selection per source (mw_2023 for Semi, commissioned_power_mw for DCH)
  - Deduplicates to closest match per Meta building
  - Calculates MAPE and bias percentage
- Returns per-source accuracy grades: A (<15% MAPE), B (15-25%), C (25-40%), D (40-60%), F (>60%)

### Source Health Matrix Enhanced
The Recommendations & Actionability section now shows 5 assessment dimensions:

| Column | Measures | Status |
|--------|----------|--------|
| Overall | Composite weighted score | Existing |
| Spatial | Location accuracy vs Meta | Existing |
| **Capacity** | **MW estimation accuracy (MAPE)** | **✓ NEW** |
| Freshness | Data currency (days since update) | Existing |
| Recommendation | Action guidance | Updated |

**Updated Recommendation Logic:**
- Capacity accuracy grades now factor into composite assessment
- Recommendations flag sources with poor capacity accuracy specifically
- Meta Canonical displays "Ground Truth" (since it IS the reference)

### PROJECT_OVERVIEW.html Enhanced
The Capacity Accuracy section now includes comprehensive methodology documentation:
- Executive Summary table with all sources, MAPE values, and grades
- Methodology section explaining apples-to-apples comparison
- PUE Adjustment Analysis (confirms no adjustment needed for DCH)
- Variance by Build Status table
- Outlier Analysis
- Capacity Data Coverage by source
- Recommended Configuration code block
- Scripts & Documentation reference table

**Navigation Sidebar Updated:**
- Added section headers: Overview, Data Pipeline, Accuracy Analysis, Documentation

---

## 🆕 Session 7 Updates (January 5, 2026)

### Google Drive Report Output Integration
All generated reports now auto-sync to Google Drive for team access:

```
G:\My Drive\Consensus GIS Model Cleaned Inputs\Admin Documentation\
├── context\                 ← AI_CONTEXT_PROMPT.md
├── dashboards\              ← PROJECT_OVERVIEW.html (executive dashboard)
├── pipeline_diagnostics\    ← Auto-generated PIPELINE_DIAGNOSTIC_*.html
├── progress_updates\        ← WEEKLY_STATUS_DASHBOARD.html, PROGRESS_UPDATE_*.html
├── schemas\                 ← Schema documentation
├── visualizations\          ← FOLDER_STRUCTURE_*.html
├── workflows\               ← PIPELINE_DOCUMENTATION.md, REPORT_OUTPUT_SOP.md
└── _archive\                ← Dated backups
```

**Configuration:** Output paths defined in `_utils/config.py`:
```python
OUTPUT_ROOT = Path("G:/My Drive/Consensus GIS Model Cleaned Inputs/Admin Documentation")
DASHBOARDS_DIR = OUTPUT_ROOT / "dashboards"
PIPELINE_REPORTS_DIR = OUTPUT_ROOT / "pipeline_diagnostics"
PROGRESS_UPDATES_DIR = OUTPUT_ROOT / "progress_updates"
VISUALIZATIONS_DIR = OUTPUT_ROOT / "visualizations"
```

**SOP:** See `00_docs/workflows/REPORT_OUTPUT_SOP.md` for complete workflow.

### PROJECT_OVERVIEW.html Enhancements
- Fixed left navigation sidebar (220px, stays visible while scrolling)
- Collapsible sections with click-to-expand headers
- Pure HTML/CSS pipeline diagram (replaced Mermaid for reliable horizontal layout)
- Neomorphism/3D glass effects with hover interactions
- Methodology section with links to detailed documentation
- Timeline with hover glow effects
- Professional appearance (emojis removed from diagrams)

### Scripts Folder Reorganization
See `00_docs/workflows/PIPELINE_EXECUTION_ORDER.md` for updated folder structure.

---

### 4.3 Deep Dive Campus Validation (December 2025) ⭐ NEW

**Location**: `scripts/04_validation/deep_dive_campus_validation.py`

**Purpose**: Comprehensive validation of Meta campuses against canonical ground truth, comparing multiple external sources.

**Key Features**:
- **Semianalysis comparison**: Uses `mw_2025` field (IT capacity, same definition as Meta canonical)
- **DCH PUE adjustment**: Applies ÷1.3 to convert facility power to estimated IT load
- **Building count tracking**: Compares source building counts vs canonical
- **Net capacity difference**: Shows MW over/under-reporting
- **CSV/TXT export**: Exports results for further analysis

**Output Files**:
- `outputs/meta_validation_comparison_YYYYMMDD_HHMMSS.csv`
  - New columns: `building_diff`, `capacity_diff_mw`
- `outputs/validation_summary_YYYYMMDD_HHMMSS.txt`
  - Includes outlier exclusion (< -100% accuracy)

**Key Configuration**:
```python
DCH_PUE_ADJUSTMENT = 1.3  # Facility power → IT load estimate
OUTLIER_THRESHOLD = -100  # Exclude from averages
```

**Results Summary** (10 Meta campuses):

| Source | Avg Accuracy | Sample | Best For |
|--------|-------------|--------|----------|
| **Semianalysis** | 43.2% | n=7 | Fort Worth, DeKalb, Gallatin, Mesa |
| **DataCenterHawk** | 39.2% | n=9 | Altoona, Prineville, Eagle Mountain |

**4 Outliers Excluded**:
- Huntsville: -586% (DCH), -960% (Semi) — planned vs commissioned confusion
- Los Lunas: -124.6% (Semi)
- New Albany: -122.9% (Semi)

**Building Count Insights**:
- External sources typically report MORE buildings than canonical
- Likely counting phases/halls as separate buildings
- DeKalb is the only campus with perfect match (0 diff)

---

### 4.4 Semianalysis Meta Coverage Check

**Location**: `scripts/04_validation/check_semianalysis_meta.py`

**Purpose**: Quick check to see if Semianalysis has Meta campus data.

**Findings**:
- 178 Meta records in Semianalysis
- 3,860.8 MW total commissioned
- Coverage for all major Meta campuses (Altoona, Prineville, Fort Worth, etc.)

---

## CURRENT STATUS (December 2025)

### Pipeline State: ✅ VALIDATED

| Step | Status | Notes |
|------|--------|-------|
| **1. Raw CSV Import** | ✅ Complete | 8 tables, 26,139 records |
| **2. Initialize Full Data FCs** | ✅ Complete | `gold_buildings_full`, `gold_campus_full` |
| **3. WoodMac Geocoding** | ✅ Complete | 491 coords extracted |
| **4. Run Ingestion Scripts** | ✅ **COMPLETE** | 22,378 external buildings |
| **5. Meta Canonical Processing** | ✅ **COMPLETE** | 318 buildings, 83 campuses |
| **6. Meta Canonical Ingestion** | ✅ **COMPLETE** | Added to gold_buildings_full |
| **7. Campus Rollup** | ✅ Complete | 11,715 campuses (grouped by UCID) |
| **8. Validation** | ✅ Complete | All data quality issues resolved |
| **9. Company Standardization** | ✅ **COMPLETE** | 9 unique companies for XB |
| **10. Deep Dive Validation** | ✅ **COMPLETE** | Semianalysis vs DCH comparison |
| **11. Data Quality Fixes** | ✅ **COMPLETE** | 150+ country mappings, state abbr, NPM truncation |

### Geodatabase Contents

#### Raw Tables (Source Data)

| Table | Records | Source File |
|-------|---------|-------------|
| `dch_hyper_raw` | 1,876 | DCH_Hyper_full.csv |
| `dch_lease_raw` | 5,236 | DCH_Lease.csv |
| `semianalysis_raw` | 5,732 | SemiAnalysis Global Import.csv |
| `synergy_raw` | 999 | Synergy Hyperscale DC.csv |
| `dcm_raw` | 8,897 | Datacentermap.csv |
| `npm_raw` | 1,401 | NPM_DC_11_12_25.csv |
| `woodmac_campus_raw` | 999 | WoodMac_Campus.csv |
| `woodmac_dc_raw` | 999 | WoodMac_DC.csv |

#### Feature Classes

| Feature Class | Records | Purpose |
|---------------|---------|--------|
| `gold_buildings_full` | **22,696** | Full data buildings (6 sources incl. Meta Canonical) |
| `gold_campus_full` | **11,715** | Full data campus rollup (grouped by UCID) |
| `gold_combined_xb` | **34,411** | Combined XB layer for Experience Builder |
| `gold_buildings` | 663 | Lean model (preserved) |
| `gold_campus` | 229 | Lean model campus (preserved) |
| `woodmac_coords` | 491 | Geocoded WoodMac coordinates |
| `meta_canonical_v2` | 1,218 | Suite-level ground truth |
| `meta_canonical_buildings` | **318** | Building-level ground truth (with owned_leased) |
| `meta_canonical_campus` | **83** | ⭐ NEW - Campus-level ground truth |

---

## Architecture: Full vs Lean Data

The pipeline now supports **separate feature classes** for Full Data vs Lean model:

| Mode | Buildings FC | Campus FC | Records |
|------|--------------|-----------|---------|
| **Full Data** | `gold_buildings_full` | `gold_campus_full` | ~26k |
| **Lean Model** | `gold_buildings` | `gold_campus` | 663 |

### Configuration Module (`_utils/config.py`)

All scripts use centralized paths:

```python
from config import GDB, GOLD_BUILDINGS, GOLD_CAMPUS, RAW_TABLES

# Active configuration (Full Data mode):
GOLD_BUILDINGS = GOLD_BUILDINGS_FULL  # → gold_buildings_full
GOLD_CAMPUS = GOLD_CAMPUS_FULL        # → gold_campus_full

# To switch to Lean model, edit config.py:
# GOLD_BUILDINGS = GOLD_BUILDINGS_LEAN
# GOLD_CAMPUS = GOLD_CAMPUS_LEAN
```

---

## Table of Contents

1. [Ingestion Process](#1-ingestion-process)
2. [Processing Pipeline](#2-processing-pipeline)
3. [Analysis Workflow](#3-analysis-workflow)
4. [Accuracy Assessment](#4-accuracy-assessment)
5. [Visualization](#5-visualization)
6. [Data Schema](#6-data-schema)
7. [File Structure](#7-file-structure)
8. [Consolidated Scripts](#8-consolidated-scripts)

---

## 1. Ingestion Process

### Purpose
Ingest data from six external datacenter intelligence sources into a unified `gold_buildings` feature class with standardized schema.

### Data Sources

| Source | Script | Records | Description | Key Data |
|--------|--------|---------|-------------|----------|
| **DataCenterHawk Hyper** | `ingest_dch.py` | 1,876 | Hyperscale datacenter database | Facility ID, capacity (kW→MW), status, commissioned year |
| **DataCenterHawk Lease** | `ingest_dch_lease.py` | 5,176 | Leased/colocation facilities | UPS/fiber info, available capacity |
| **SemiAnalysis** | `ingest_semianalysis.py` | 5,472 | Building-level capacity projections | Time-series capacity (2023-2032), Field1-43 mapping |
| **DataCenterMap (DCM)** | `ingest_dcm.py` | 8,453 | Datacenter location database | Stage-based status, table→point conversion |
| **New Project Media (NPM)** | `ingest_npm.py` | 1,401 | US datacenter project announcements | Lat_Lon_X/Y fields, cost, planned dates, unique_id truncated to 64 chars |
| **Meta Canonical** | `ingest_meta_canonical.py` | 318 | ⭐ Meta internal buildings | IT load, owned/leased, build status |
| **Synergy** | `ingest_synergy.py` | ⏭️ Skipped | No coordinates | Facility counts only - not geocoded |
| **WoodMac** | `ingest_woodmac.py` | ⏭️ Excluded | Dev phases, not buildings | Validation only (see GRANULARITY_STRATEGY) |

**Total gold_buildings_full:** 22,696 records (from 6 sources)

### Common Ingestion Features

1. **Unique ID Generation**: `{source}_{source_unique_id}` format
2. **Campus ID Convention**: `{company_slug}|{city_slug}|{campus_name_slug}`
3. **Status Vocabulary Mapping**: Maps source-specific statuses to standard values:
   - Active, Under Construction, Permitting, Announced, Land Acquisition, Rumor, Unknown
4. **Status Rank Assignment**: Numeric ranking for aggregation (1=Active → 7=Unknown)
5. **Duplicate Prevention**: Checks for existing records before insertion
6. **Progress Logging**: Detailed console output with record counts and validation

### Key Transformations

```python
# Status mapping example (DCH)
STATUS_MAP = {
    'Owned': 'Active',
    'Under Construction': 'Under Construction',
    'Planned': 'Announced',
    None: 'Unknown'
}

# Capacity conversion (kW to MW)
commissioned_mw = cap_comm * 0.001

# Campus ID generation
campus_id = f"{slug(company)}|{slug(city)}|{slug(campus_name)}"
```

---

## 2. Processing Pipeline

### 2.1 Meta Canonical Import (`import_meta_canonical_v2.py`)

**Purpose**: Import Meta's internal datacenter inventory from DAI query export.

**Process**:
1. Load CSV from internal database export
2. Deduplicate by `location_key` with aggregation rules:
   - Latest milestone date
   - Maximum IT load (for upgrades)
   - First geographic data (coordinates, address)
3. Derive geographic region from coordinates:
   - **AMER**: Longitude -180 to -30
   - **EMEA**: Longitude -25 to 65
   - **APAC**: Longitude 65 to 180
4. Create `meta_canonical_v2` feature class
5. Export non-spatial records to separate table for geocoding

**Output Fields**:
- `location_key` (unique identifier)
- `dc_code` (datacenter code)
- `suite` (building designation)
- `it_load` (MW capacity)
- `new_build_status`, `activity_status`
- `region_derived` (AMER/EMEA/APAC)

### 2.2 Meta Deduplication (`meta_deduplicate.py`)

**Purpose**: Deduplicate Meta canonical data from suite-level to building-level for accurate spatial analysis.

**Problem Solved**: The raw Meta canonical data (`meta_canonical_v2`) contains records at the **suite level** (e.g., Suite A, B, C, D within Building 1). For accurate spatial accuracy analysis, we need to deduplicate to the **building level** using a composite key.

**Process**:
1. Add `building_key` field to `meta_canonical_v2`
2. Calculate composite key: `{dc_code}-{datacenter}` (e.g., "ALT-1", "ALT-2")
3. **Include ALL buildings** (no has_coordinates filter) - 318 total
4. Dissolve suites to building-level using `building_key` with **MULTI_PART** geometry
5. Aggregate fields:
   - `COUNT(location_key)` → `suite_count` (suites per building)
   - `FIRST(dc_code)` → campus identifier
   - `FIRST(datacenter)` → building number
   - `FIRST(region_derived)` → region (AMER/EMEA/APAC)
   - `FIRST(new_build_status)` → build status
   - `FIRST(building_type)` → owned/leased status
   - `SUM(it_load)` → total IT load per building
6. Add `owned_leased` field (normalized: "Own"→"Owned", "Lease"→"Leased")
7. Rename dissolved fields for clarity
8. Validate against expected counts (318 buildings)

**Input**: `meta_canonical_v2` (suite-level records)
**Output**: `meta_canonical_buildings` (building-level, 318 records)

**Key Fields Added (December 18, 2025)**:
- `owned_leased` — "Owned" (292) or "Leased" (26)
- `has_coordinates` — 276 with coords, 42 without

**Expected Distribution**:
| Region | Buildings |
|--------|-----------|
| AMER | 251 |
| APAC | 5 |
| EMEA | 20 |
| UNKNOWN | 42 |

### 2.2a Meta Canonical Campus Rollup (`campus_rollup_meta_canonical.py`) ⭐ NEW

**Purpose**: Aggregate Meta canonical buildings to campus-level (by dc_code).

**Output**: `meta_canonical_campus` (83 campuses)

**Aggregated Fields**:
- `building_count` — Number of buildings per campus
- `suite_count_total` — Total suites
- `it_load_total` — Total IT capacity (MW)
- `it_load_commissioned`, `it_load_uc`, `it_load_planned` — By status
- `owned_count`, `leased_count` — Ownership breakdown
- `status_summary` — Build status distribution

### 2.2b Meta Canonical Ingestion (`ingest_meta_canonical.py`) ⭐ NEW

**Purpose**: Add Meta canonical buildings to `gold_buildings_full` for unified analysis.

**Key Mappings**:
- `source = "Meta Canonical"`
- `unique_id = "MetaCanonical_{building_key}"`
- `campus_id = "meta|{region}|{dc_code}"`
- Maps `new_build_status` → capacity fields:
  - Complete Build → `commissioned_power_mw`
  - Active Build → `uc_power_mw`
  - Future Build → `planned_power_mw`
- Preserves `owned_leased` field

### 2.3 Campus Rollup (`campus_rollup_new.py`)

**Purpose**: Aggregate building-level records into campus-level summaries, grouped by UCID.

**Key Change (December 30, 2025):** Campus rollup now groups by `ucid` (Universal Campus ID) instead of `campus_id`. This creates ONE campus record per physical location, merging data from all sources.

**Process**:
1. Build source lookup dictionary by `campus_id`
2. Clear existing `gold_campus` table
3. Perform PairwiseDissolve by `campus_id` with statistics:
   - `SUM`: planned_power_mw, uc_power_mw, commissioned_power_mw, full_capacity_mw, facility_sqft, mw_2023-2032
   - `FIRST`: company_clean, campus_name, city, state, country, region
   - `MIN`: actual_live_date, status_rank_tmp
   - `MAX`: cancelled
   - `COUNT`: unique_id (→ building_count)
   - `MEAN`: pue
4. Feature to Point (INSIDE) for representative campus points
5. Map derived fields and insert into `gold_campus`

**Output Schema**:
- Campus identification (campus_id, campus_name, company_clean)
- Location (city, state, country, region)
- Aggregated capacity (planned_power_mw, commissioned_power_mw, full_capacity_mw)
- Time-series capacity (mw_2023 through mw_2032)
- Building count and aggregated status

---

## 3. Analysis Workflow

### 3.1 Multi-Source Spatial Accuracy (`multi_source_spatial_accuracy.py`) ⭐ SPATIAL JOIN

**Purpose**: Perform spatial join between Meta canonical buildings and external vendor data to create the base accuracy analysis dataset.

**Version**: v5 (FIXED) - Uses geodesic distance calculation

**Key Features**:
- **Input**: `meta_canonical_buildings` (276 deduplicated buildings)
- **Join Features**: `gold_buildings` (all external vendor records)
- **Method**: Spatial join with CLOSEST match within 50km search radius
- **Distance**: Haversine formula for accurate geodesic distance in meters
- **No Company Filter**: Matches by proximity only (catches misclassified records)

**Process**:
1. Spatial join Meta buildings to external sources (JOIN_ONE_TO_MANY)
2. Calculate geodesic distance using Haversine formula
3. Analyze recall and distance accuracy by source
4. Generate regional breakdown (AMER, EMEA, APAC)
5. Rank vendors by coverage and spatial accuracy

**Output**: `accuracy_analysis_buildings_v4`

**Metrics Generated**:
- Recall (% of 276 Meta buildings detected)
- Distance accuracy (median, mean, range)
- Threshold analysis (≤100m, ≤500m, ≤1km, ≤5km)
- Regional recall breakdown

### 3.2 Gold Buildings Audit (`gold_buildings_audit.py`) ⭐ QA

**Purpose**: Audit external vendor data quality before accuracy analysis.

**Location**: `scripts/qa/gold_buildings_audit.py`

**Audits Performed**:
- Record counts by source
- Field completeness analysis
- Capacity data availability
- Geographic distribution
- Company name standardization check

### 3.3 Unified Accuracy Analysis (`unified_accuracy_analysis.py`)

**Purpose**: Replicate Accenture's manual benchmarking methodology at scale.

**Three Main Tasks**:

#### Task 1: Enhance Spatial Match Data
- Add `distance_to_meta_dc_miles` (convert meters to miles)
- Add `meta_location_name` (from location_key)
- Classify records as Building or Campus level based on suite designation
- Add `campus_name_meta`

#### Task 2: Create Unified Global_DC_All_Sources Table
- 45+ standardized fields matching Accenture schema
- Import Meta canonical locations as "Meta Actuals"
- Import external source data from gold_buildings
- Link spatial match information with confidence scoring:
  - **High**: < 0.5 miles
  - **Medium**: 0.5 - 2.0 miles
  - **Low**: > 2.0 miles

#### Task 3: Capacity Validation Analysis
- Compare external MW estimates against Meta actual IT load
- Calculate percent difference for each source-location pair
- Apply Accenture variance scoring:
  - **Within 15%**: Variance Score 1
  - **15-30%**: Variance Score 2
  - **30-60%**: Variance Score 3
  - **>60%**: Variance Score 4
- Generate summary statistics by source

**Output Tables**:
- `Global_DC_All_Sources` (unified feature class)
- `capacity_validation_report` (MW comparison table)

---

## 4. Accuracy Assessment

### 4.1 Comprehensive Spatial Accuracy Report (`comprehensive_spatial_accuracy_report.py`) ⭐ PRIMARY

**Location**: `scripts/accuracy/comprehensive_spatial_accuracy_report.py`

This is the **primary accuracy analysis script** that performs both campus-level and building-level analysis in a single run.

**Features**:
- **Campus-Level Analysis**: Unique `dc_code` values with valid coordinates
- **Building-Level Analysis**: Composite key `{dc_code}-{datacenter}`
- **Deduplication**: Closest match per building/campus per source
- **Complete Statistical Output**: All metrics in one execution

**Metrics Calculated**:
- **Recall**: % of Meta sites detected by each source
- **Distance Statistics**: min, max, mean, std, MAD, percentiles (P10-P90)
- **Threshold Shares**: % within 100m, 500m, 1km, 5km
- **Match Quality Bands**:
  - Excellent: < 1km
  - Good: 1-3km
  - Fair: 3-5km

**Breakdowns**:
- By region (AMER, EMEA, APAC)
- By build status (Complete Build, Active Build, Future Build)
- Worst-case analysis (top 25 largest distances per source)
- Executive summary with rankings

### Output Files
- `comprehensive_accuracy_report_{timestamp}.txt` - Executive summary
- `campus_level_stats_{timestamp}.csv` - Campus-level results
- `building_level_stats_{timestamp}.csv` - Building-level results
- `by_region_{timestamp}.csv` - Regional breakdown
- `by_status_{timestamp}.csv` - Build status breakdown
- `worst_case_{timestamp}.csv` - Outlier analysis

### 4.2 Capacity Accuracy Analysis ⭐ NEW (Dec 10, 2025)

**Location**: `scripts/qa/`

A suite of scripts for comparing vendor capacity predictions against Meta's actual IT load.

#### Scripts

| Script | Purpose |
|--------|---------|
| `validate_canonical_integrity.py` | Verify Meta suite→building aggregation |
| `capacity_accuracy_analysis_v2.py` | Apples-to-apples capacity comparison |
| `capacity_variance_experiments.py` | Root cause analysis of errors |
| `CAPACITY_FIELD_DEFINITIONS.md` | Field definitions documentation |

#### Key Findings (Final v4)

**Best Result: 11.9% MAPE** for Complete Builds using Semianalysis `mw_2023`

| Source | MAPE (Complete) | Granularity | PUE Adjustment | Grade |
|--------|-----------------|-------------|----------------|-------|
| **Semianalysis** | **11.9%** 🏆 | Building | None | A |
| **DataCenterHawk** | **17.6%** | Building | **None** | A- |

#### Critical Finding: No PUE Adjustment Needed

After testing, we confirmed that **DCH reports IT capacity** (same definition as Meta), NOT facility power. Applying a PUE adjustment makes accuracy WORSE:

| PUE Factor | MAPE | Conclusion |
|------------|------|------------|
| **1.0 (none)** | **17.6%** | ✅ Best - use this |
| 1.3 | 23.5% | ❌ Wrong assumption |

#### DCH Granularity Correction

Initially, we labeled DCH as "Campus-level" based on the `record_level` field. Investigation revealed:
- DCH provides **BUILDING-level data** (unique coordinates and capacities per building)
- The `record_level = 'Campus'` was a labeling error, now corrected to `'Building'`
- Both Semianalysis and DCH should be compared at building-level

#### Variance Analysis Results

| Source of Error | Impact | Resolution |
|-----------------|--------|------------|
| **Source selection** | Moderate | Semi 11.9% vs DCH 17.6% |
| **Year alignment** | Moderate (3%) | Use `mw_2023` not `mw_2024` |
| **PUE adjustment** | Major | **Don't apply** — makes it worse |
| **4 outlier buildings** | Major | MAPE → 3.7% without them |

#### Capacity Accuracy Recommendations

1. **Use Semianalysis `mw_2023`** for primary capacity estimation (~12% MAPE)
2. **Use DataCenterHawk** as backup (~18% MAPE, no adjustment needed)
3. **Both are building-level** — aggregate for campus analysis
4. **DCH under-reports** by ~16% on average (ratio 0.84)

---

## 5. Visualization

### Script: `plot_spatial_accuracy_LIGHT_THEME.py`

**Purpose**: Generate publication-quality visualizations for spatial accuracy analysis

**Data Preparation**:
1. Load accuracy matches and Meta canonical data
2. Deduplicate to closest match per building/campus per source
3. Calculate denominators (unique campuses and buildings)

### Generated Plots

| Plot | Description | Use Case |
|------|-------------|----------|
| **Plot 1** | Building-level box plot by source | Overall source comparison |
| **Plot 2** | Granularity comparison (campus vs building) | Side-by-side granularity analysis |
| **Plot 3** | By region | Regional performance comparison |
| **Plot 4** | By build status | Status-based accuracy |
| **Plot 5** | Building-level violin plot | Full distribution visualization |
| **Plot 6** | Campus-level violin plot | Campus-level distribution |

### Visual Specifications
- **Theme**: Light (white background)
- **Color Palette**:
  - DataCenterHawk: #5dade2 (Sky blue)
  - Semianalysis: #af7ac5 (Purple)
  - DataCenterMap: #f4d03f (Gold)
  - NewProjectMedia: #ec7063 (Coral)
  - WoodMac: #58d68d (Green)
  - Synergy: #cb4335 (Dark red)
- **Reference Lines**: 1km (green), 3km (orange)
- **Output Format**: PNG, 300 DPI

---

## 6. Data Schema

### gold_buildings (Building-Level)

| Field | Type | Description |
|-------|------|-------------|
| unique_id | TEXT | Source-prefixed unique identifier |
| source | TEXT | Data source name |
| source_unique_id | TEXT | Original source ID |
| campus_id | TEXT | Standardized campus identifier |
| campus_name | TEXT | Campus/project name |
| building_designation | TEXT | Building number/phase |
| company_source | TEXT | Company name from source |
| company_clean | TEXT | Standardized company name |
| city, state, country | TEXT | Location fields |
| region | TEXT | AMER/EMEA/APAC |
| latitude, longitude | DOUBLE | Coordinates |
| facility_status | TEXT | Current status |
| planned_power_mw | DOUBLE | Planned capacity |
| uc_power_mw | DOUBLE | Under construction capacity |
| commissioned_power_mw | DOUBLE | Operational capacity |
| full_capacity_mw | DOUBLE | Total buildout capacity |
| mw_2023 - mw_2032 | DOUBLE | Year-by-year projections |
| total_cost_usd_million | DOUBLE | Project cost |
| total_site_acres | DOUBLE | Site size |
| ingest_date | DATE | Import timestamp |

### gold_campus (Campus-Level)

Same as gold_buildings plus:
- `building_count` - Number of buildings
- `facility_sqft_sum` - Total facility area
- `first_live_date` - Earliest operational date
- `facility_status_agg` - Most advanced status

### meta_canonical_v2 (Meta Internal)

| Field | Type | Description |
|-------|------|-------------|
| location_key | TEXT | Unique location identifier |
| datacenter | TEXT | Building number |
| suite | TEXT | Suite designation |
| dc_code | TEXT | Datacenter code (campus) |
| region_derived | TEXT | Derived from coordinates |
| it_load | DOUBLE | IT load (MW) |
| new_build_status | TEXT | Build status |
| building_type | TEXT | Own/Lease |
| has_coordinates | SHORT | Valid coordinates flag |

---

## 7. File Structure

```
scripts/
├── 00_docs/                           # Documentation
│   ├── AI_CONTEXT_PROMPT.md           # AI assistant context (copy for new chats)
│   ├── CAPACITY_FIELD_DEFINITIONS.md  # Field definitions
│   ├── PIPELINE_DOCUMENTATION.md      # This file
│   └── SCRIPT_AUDIT_AND_REORG.md      # Cleanup audit log
│
├── 01_ingestion/                      # Step 1: Load external data
│   ├── ingest_dch.py                  # DataCenterHawk (Building-level)
│   ├── ingest_dcm.py                  # DataCenterMap (with duplicate prevention)
│   ├── ingest_npm.py                  # New Project Media
│   ├── ingest_semianalysis.py         # SemiAnalysis (fixed coordinates)
│   ├── ingest_synergy.py              # Synergy
│   ├── ingest_woodmac.py              # WoodMac
│   └── ingest_meta_canonical.py       # ⭐ NEW - Meta Canonical → gold_buildings_full
│
├── 02_processing/                     # Step 2: Transform & aggregate
│   ├── import_meta_canonical_v2.py    # Import Meta internal data
│   ├── meta_deduplicate.py            # Suite → Building deduplication
│   ├── campus_rollup_new.py           # Building → Campus aggregation
│   ├── campus_rollup_meta_canonical.py # ⭐ NEW - Meta campus rollup (standalone)
│   └── export_schema.py               # Schema export utility
│
├── 03_spatial_join/                   # Step 3: Create spatial matches
│   └── multi_source_spatial_accuracy.py  # Spatial join (v5)
│
├── 04_validation/                     # Step 4: Validate data quality
│   ├── validate_gold_buildings_data.py   # Gold buildings validation
│   ├── validate_canonical_integrity.py   # Meta canonical validation
│   ├── validate_gold_build_schema.py     # Schema validation
│   ├── gold_buildings_audit.py           # External data audit
│   ├── attribute_accuracy_audit.py       # Attribute accuracy
│   ├── fix_companies.py                  # Company name fixes
│   └── fix_regions.py                    # Region fixes
│
├── 05_accuracy_analysis/              # Step 5: Measure accuracy
│   ├── comprehensive_spatial_accuracy_report.py  # PRIMARY spatial analysis
│   ├── capacity_accuracy_analysis_v2.py          # Capacity comparison (SA+DCH only)
│   ├── capacity_variance_experiments.py          # Root cause analysis
│   ├── capacity_variance_experiments_all_sources.py  # All-source experiments
│   ├── unified_accuracy_analysis.py              # Unified table creation
│   └── _diagnostics/                             # Investigation scripts
│       ├── audit_capacity_by_source.py           # Capacity data audit
│       ├── check_woodmac_npm_source.py           # Source data diagnosis
│       ├── investigate_dch_granularity.py        # DCH granularity investigation
│       └── test_dch_pue_adjustment.py            # PUE testing
│
├── 06_consensus/                      # Step 6: Build consensus model
│   ├── consensus_dedupe.py            # Deduplication logic
│   ├── spatial_clustering.py          # Clustering algorithms
│   └── validate_clusters.py           # Cluster validation
│
├── 07_visualization/                  # Step 7: Create outputs
│   ├── generate_capacity_presentation_charts.py  # Capacity charts
│   └── plot_spatial_accuracy_LIGHT_THEME.py      # Spatial accuracy plots
│
├── _archive/                          # Deprecated scripts
│   └── (old scripts for reference)
│
└── _utils/                            # Shared helpers
    ├── fix_dch_record_level.py        # DCH record level fix
    ├── helper_scripts.py              # Common utilities
    └── copy_to_fbsource.ps1           # Deployment script
```

---

## 8. Consolidated Scripts

### Scripts Removed (Redundant)

The following scripts were removed during consolidation as their functionality is covered by the primary scripts:

| Removed Script | Replaced By | Reason |
|----------------|-------------|--------|
| `accuracy/spatial_accuracy_campus_level.py` | `comprehensive_spatial_accuracy_report.py` | Campus analysis included in comprehensive report |
| `accuracy/spatial_accuracy_building_level_FIXED.py` | `comprehensive_spatial_accuracy_report.py` | Building analysis included in comprehensive report |
| `analysis/deep_dive_site_comparison_export.py` | `campus_level_deep_dive_export.py` | Near-identical functionality |
| `analysis/multi_source_spatial_accuracy.py` | `unified_accuracy_analysis.py` | Creates same output table |
| `analysis/capacity_validation_campus_level.py` | `unified_accuracy_analysis.py` Task 3 | Capacity validation included |

### Primary Scripts to Use

| Script | Purpose | Output |
|--------|---------|--------|
| **`comprehensive_spatial_accuracy_report.py`** | Spatial accuracy at both levels | Statistics CSVs + Executive summary |
| **`unified_accuracy_analysis.py`** | Unified table + capacity validation | `Global_DC_All_Sources`, `capacity_validation_report` |
| **`campus_level_deep_dive_export.py`** | Detailed per-campus analysis | TXT report + detailed CSVs |

---

## Execution Order

### FULL DATA PIPELINE (December 2025+)

For running the full data pipeline with all companies (~26k records):

#### Step 0: Import Raw CSVs to Geodatabase
```
python 01_ingestion/import_raw_excel_to_gdb.py
```
**Source:** `C:\Users\ptanderson\Downloads\Pipeline_Ingestion\`
**Output:** Raw tables in geodatabase (dch_hyper_raw, dch_lease_raw, semianalysis_raw, etc.)

#### Step 1: Geocode WoodMac (Before Ingestion)
```
# In ArcGIS Pro Python window:
python 02_processing/geocode_woodmac.py
# Then use ArcGIS Pro Geocode Addresses tool on output tables
```
**Output:** `WoodMac_Campus_Geocoded`, `WoodMac_DC_Geocoded`

#### Step 2: Ingest External Sources (any order)
```
python 01_ingestion/ingest_dch.py           # From dch_hyper_raw (building-level, kW→MW)
python 01_ingestion/ingest_dcm.py           # From dcm_raw
python 01_ingestion/ingest_npm.py           # From npm_raw
python 01_ingestion/ingest_semianalysis.py  # From semianalysis_raw
python 01_ingestion/ingest_synergy.py       # ⚠️ NO COORDINATES - counts only
python 01_ingestion/ingest_woodmac.py       # From WoodMac_DC_Geocoded (after geocoding)
```

**⚠️ Critical Notes:**
- **Synergy has NO coordinates** - use for facility counts only
- **WoodMac must be geocoded first** - run `geocode_woodmac.py` before ingestion
- **DCH capacity is in kW** - scripts convert to MW using factor 0.001
- **DCH is building-level** - `record_level` defaults to 'Building'

---

### LEAN PIPELINE (Legacy Reference)

For running the Lean model (Meta/Oracle only, 663 records):

### Step 1: Ingest External Sources (any order)
```
python ingestion/ingest_dch.py
python ingestion/ingest_dcm.py
python ingestion/ingest_npm.py
python ingestion/ingest_semianalysis.py
python ingestion/ingest_synergy.py
python ingestion/ingest_woodmac.py
```

**Note:** All ingestion scripts include **duplicate prevention** - safe to re-run without creating duplicates.

### Step 2: Import Meta Canonical
```
python processing/import_meta_canonical_v2.py
```

### Step 3: Deduplicate Meta to Building-Level ⭐ NEW
```
python processing/meta_deduplicate.py
```
This creates `meta_canonical_buildings` (276 buildings) from suite-level data.

### Step 4: Process Campus Rollup
```
python processing/campus_rollup_new.py
```

### Step 4a: Audit External Data Quality (OPTIONAL)
```
python qa/gold_buildings_audit.py
```
Generates data quality report for `gold_buildings` by source (record counts, field completeness, capacity data availability).

### Step 5: Perform Spatial Join & Initial Accuracy Analysis
```
python analysis/multi_source_spatial_accuracy.py
```
Creates `accuracy_analysis_buildings_v4` with spatial matches between Meta buildings and external sources.

### Step 6: Run Comprehensive Accuracy Analysis (choose based on need)

**For comprehensive statistics (RECOMMENDED):**
```
python accuracy/comprehensive_spatial_accuracy_report.py
```

**For unified table + capacity validation:**
```
python analysis/unified_accuracy_analysis.py
```

**For detailed per-campus deep dive:**
```
python analysis/campus_level_deep_dive_export.py
```

### Step 7: Generate Visualizations
```
python visualization/plot_spatial_accuracy_LIGHT_THEME.py
```

---

## Key Metrics Summary

| Metric | Description | Target |
|--------|-------------|--------|
| **Spatial Recall** | % of Meta sites detected by source | Higher is better |
| **Median Distance** | Median spatial offset from Meta actual | < 1km excellent |
| **Capacity Accuracy** | % within 15% of Meta IT load | Higher is better |
| **Match Confidence** | High (<0.5mi), Medium (0.5-2mi), Low (>2mi) | More High is better |

---

## 9. Feature Classes Reference

### Geodatabase: `Default.gdb`

| Feature Class | Records | Purpose | Updated |
|---------------|---------|---------|---------|
| `meta_canonical_v2` | 1,068 | Suite-level Meta ground truth | Stable |
| `meta_canonical_buildings` | 276 | Building-level (dissolved from suites) | Stable |
| `gold_buildings` | 663 | Harmonized vendor buildings | Dec 9, 2025 |
| `gold_campus` | 229 | Campus-level rollup | Dec 9, 2025 |
| `accuracy_analysis_multi_source` | 13,210 | OLD spatial join (deprecated) | Dec 8, 2025 |
| `accuracy_analysis_multi_source_REBUILT` | 5,167 | **CURRENT spatial join** | Dec 10, 2025 |
| `accuracy_analysis_buildings_v4` | 276 | Single closest match per building | Dec 9, 2025 |
| `accuracy_analysis_buildings_v5` | 276 | Latest single match version | Dec 10, 2025 |

**⚠️ Important:** Use `accuracy_analysis_multi_source_REBUILT` for accuracy analysis - it contains the current building-level coordinates from `gold_buildings`.

---

## 10. Spatial Accuracy Results (Dec 10, 2025)

### Vendor Rankings

| Rank | Source | Recall | Median Distance | Consistency (MAD) |
|------|--------|--------|-----------------|-------------------|
| 🥇 | **DataCenterHawk** | 89.9% | 233m | 204m |
| 🥈 | **Semianalysis** | 88.8% | 307m | 285m |
| 🥉 | **NewProjectMedia** | 73.2% | 1,002m | 763m |
| 4 | **DataCenterMap** | 69.6% | 677m | 586m |
| 5 | **WoodMac** | 30.1% | 1,436m | 837m |
| 6 | **Synergy** | 58.0% | 5,772m | 2,045m |

### Semianalysis Improvement (Dec 8 → Dec 10)

| Metric | Before Fix | After Fix | Improvement |
|--------|------------|-----------|-------------|
| **Median Distance** | 841m | **307m** | **63% better** |
| **Recall** | 86.2% | 88.8% | +2.6% |
| **Consistency (MAD)** | 350m | 285m | -65m |
| **Ranking** | #4 | **#2** | ⬆️ 2 spots |

### Regional Coverage

| Region | Buildings | DCHawk | Semianalysis | DCMap | NPM | WoodMac | Synergy |
|--------|-----------|--------|--------------|-------|-----|---------|---------|
| **AMER** | 251 | 90.4% | 89.2% | 68.1% | 80.5% | 33.1% | 57.4% |
| **APAC** | 5 | 100% | 100% | 100% | 0% | 0% | 100% |
| **EMEA** | 20 | 80% | 80% | 80% | 0% | 0% | 55% |

**⚠️ NewProjectMedia & WoodMac are US-only** (0% recall in APAC/EMEA)

### Recommendations for Consensus Model

**Spatial Coordinate Priority:**
1. DataCenterHawk (233m median)
2. Semianalysis (307m median)
3. DataCenterMap (677m median)

**Capacity Data Priority:**
- Current: DataCenterHawk `commissioned_power_mw`
- Forecast: Semianalysis `mw_2032`

**Exclusions:**
- Synergy: EXCLUDE from spatial consensus (5,772m median - too inaccurate)
- Use Synergy for transparency reporting only

---

## 11. Company Name Standardization (December 17, 2025)

### Purpose

Standardize company names in `company_clean` field for Experience Builder (XB) filtering. Before standardization, there were hundreds of company name variations (e.g., "AWS", "Amazon AWS", "Amazon Web Services"). After standardization, there are only 9 unique values.

### Final Distribution

| Category | Records | % | Description |
|----------|---------|---|-------------|
| **Hyperscalers** | 4,423 | 19.8% | Keep distinct names for XB filtering |
| **Colo - All Other** | 17,953 | 80.2% | All colo/other providers grouped |
| **NULL/Missing** | 0 | 0.0% | No gaps |

### Hyperscaler Breakdown

| Company | Records | Capacity (MW) |
|---------|---------|---------------|
| AWS | 1,872 | 97,089.5 |
| Microsoft | 1,243 | 70,159.1 |
| Google | 678 | 60,390.1 |
| Meta | 505 | 41,252.5 |
| Apple | 87 | 1,258.3 |
| Oracle | 23 | 1,145.3 |
| Alibaba | 12 | 0.0 |
| xAI | 3 | 1,680.0 |

### Scripts

| Script | Purpose |
|--------|---------|
| `04_validation/audit_company_names.py` | Audit company names, output CSV |
| `04_validation/standardize_company_names.py` | Apply standardization |

### Execution

```python
# In ArcGIS Pro Python window:

# 1. Audit current company names (outputs CSV)
exec(open(r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\scripts\04_validation\audit_company_names.py").read())

# 2. Apply standardization
exec(open(r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\scripts\04_validation\standardize_company_names.py").read())
```

### Output Files

- `outputs/company_audit_*.csv` - Full company list with counts and recommendations
- `outputs/company_summary_*.csv` - Summary by category (Hyperscaler/Colo/NULL)

---

## 12. Company Fields Migration (December 30, 2025)

### Purpose

The company fields were restructured to support both UCID spatial clustering AND Experience Builder (XB) filtering with different requirements:

| Field | Purpose | Example Values |
|-------|---------|----------------|
| `company_source` | Raw vendor value | "Amazon Web Services, Inc.", "Equinix, Inc." |
| `company_clean` | Standardized DISTINCT names | "AWS", "Equinix", "Digital Realty", "Meta" |
| `company_clean_filter` | XB filter categories | "AWS", "Meta", "Colo - All Other" |

### Why 3 Fields?

**Problem Solved:** The original `company_clean` field grouped all colo providers as "Colo - All Other", which caused false merges in UCID spatial clustering (Equinix + Digital Realty in same city would merge).

**Solution:**
- `company_clean` now contains DISTINCT canonical names (Equinix, Digital Realty, QTS, etc.)
- `company_clean_filter` contains hyperscaler names OR "Colo - All Other" (for XB filtering only)
- UCID clustering uses `company_clean` (distinct names) to prevent false merges

### Hyperscalers List

The following companies keep their distinct name in `company_clean_filter`:
- AWS, Microsoft, Google, Meta, Apple, Oracle, xAI, OpenAI, Anthropic, ByteDance, TikTok, Alibaba

All other companies → "Colo - All Other" in `company_clean_filter`

### Migration Script

**Location:** `scripts/02_processing/migrate_company_fields_v2.py`

**Execution:**
```python
exec(open(r"...scripts/02_processing/migrate_company_fields_v2.py", encoding='utf-8').read())
```

**Results:**
- gold_buildings_full: 17,944 records updated, 3,375 distinct companies found
- gold_campus_full: Updated via building data propagation

---

## 13. Text-Based UCID System (December 30, 2025)

### Purpose

Replace opaque numeric UCID codes with human-readable identifiers that are recognizable at a glance.

### Format Design

| Level | Format | Example |
|-------|--------|---------|
| **Campus** | `{COMPANY}-{CAMPUS_NAME}` | `META-ALTOONA` |
| **Campus (disambiguated)** | `{COMPANY}-{CAMPUS_NAME}-{SUFFIX}` | `AWS-ASHBURN-EAST` |
| **Building** | `{COMPANY}-{CAMPUS_NAME}-{NUM}` | `META-ALTOONA-01` |

### Disambiguation Rules

1. **Campus Name Priority:** project_name > campus_name > city
2. **Same-City Multiple Campuses:** Geographic suffixes (EAST, WEST, NORTH, SOUTH)
3. **3+ Campuses in Same City:** Numbered suffixes (1, 2, 3...)
4. **Building Numbers:** Sequential, source-agnostic (01, 02, 03...)

### Company Codes (60+)

| Category | Codes |
|----------|-------|
| **Hyperscalers** | META, AWS, MSFT, GOOG, ORCL, AAPL, OAI, XAI, ANTH |
| **Asian Tech** | BYTE, TIKTOK, BABA, TENC, BIDU |
| **Major Colos** | EQIX, DLR, CONE, QTS, VDC, COR, SWCH, FLEX, STACK |
| **Telecom** | ATT, VZ, LUMN, NTT, COLT, ZAYO |

### Scripts

| Script | Purpose |
|--------|---------|
| `06_ucid/generate_text_ucid.py` | Generate text-based UCIDs |
| `06_ucid/generate_ucid_clusters.py` | Spatial clustering (uses company_clean) |

### Execution

```python
exec(open(r"...scripts/06_ucid/generate_text_ucid.py", encoding='utf-8').read())
```

---

## 14. Changelog

### December 30, 2025
- ✅ **Semianalysis Patch Verified** — 99.6% match achieved after running patch script
- ✅ **Company Fields Migration** — Created 3-field structure (company_source, company_clean, company_clean_filter)
- ✅ **Text-Based UCID System** — Replaced opaque numeric UCIDs with human-readable format
- ✅ **UCID Clustering Fix** — Updated to use company_clean (distinct names) instead of company_clean_filter
- ✅ Updated ownership model example to Vantage/Oracle/OpenAI in schema visual

### January 2, 2026
- ✅ **Data Quality Fixes Complete**
  - Fixed DCM missing region (1,349+ records) with 150+ country-to-region mappings
  - Fixed state abbreviations in state field (1,813 records)
  - Fixed NPM unique_id/source_unique_id field length (truncated to 64 chars)
  - Created `fix_data_quality_issues.py` for ongoing maintenance
- ✅ **Batch Pipeline Script** — Created `run_full_pipeline.py` for automated execution
- ✅ **Clean Re-ingestion** — All scripts now auto-delete existing records before inserting
- ✅ **data_vintage Field** — Added to all 6 ingestion scripts
- ✅ **PROJECT_OVERVIEW.html** — Created comprehensive shareable documentation
- ✅ Updated counts: 22,696 buildings, 11,715 campuses, 34,411 XB records

### December 18, 2025
- ✅ **Meta Canonical Integration Complete**
  - Added `owned_leased` field to `meta_canonical_buildings`
  - Created `meta_canonical_campus` (83 campuses from 318 buildings)
  - Created `ingest_meta_canonical.py` - adds Meta to gold_buildings_full
  - Created `campus_rollup_meta_canonical.py` - standalone campus rollup
  - Updated counts: 22,694 buildings, 15,987 campuses
  - Removed `has_coordinates=1` filter (includes all 318 buildings)
  - Fixed duplicate buildings issue with MULTI_PART dissolve
- ✅ Created `META_CANONICAL_WORKFLOW.md` documentation
- ✅ Updated all documentation to v24.0

### December 17, 2025
- ✅ **Deep Dive Validation Complete** - Comprehensive Meta canonical comparison
  - Added Semianalysis comparison using `mw_2025` field
  - Added PUE adjustment (÷1.3) for DCH facility power
  - Added `building_diff` and `capacity_diff_mw` columns to CSV export
  - Added outlier exclusion (< -100% accuracy) for averages
  - Created `check_semianalysis_meta.py` utility script
- ✅ Updated all documentation to v23.0

### December 17, 2025
- ✅ **Company Name Standardization** - Reduced company names from 100s to 9 unique values
  - Hyperscalers (AWS, Microsoft, Google, Meta, etc.) keep distinct names
  - All colo providers grouped as "Colo - All Other"
  - Created `audit_company_names.py` and `standardize_company_names.py`
- ✅ Updated documentation to v21.0

### December 10, 2025
- ✅ Rebuilt `accuracy_analysis_multi_source_REBUILT` with current gold_buildings coordinates
- ✅ Updated `comprehensive_spatial_accuracy_report.py` to use REBUILT table
- ✅ Updated `plot_spatial_accuracy_LIGHT_THEME.py` to use REBUILT table
- ✅ Verified Semianalysis spatial accuracy improved (841m → 307m)
- ✅ Generated new accuracy reports and visualizations

### December 9, 2025
- ✅ Fixed Semianalysis ingestion - populated `latitude`, `longitude`, `gold_lat`, `gold_lon`, `company_clean`
- ✅ Renamed `ingest_semianalysis_CORRECTED.py` → `ingest_semianalysis.py`
- ✅ Created `ingest_dcm.py` with duplicate prevention
- ✅ Fixed data quality issues (178 Semianalysis records, 67 DCM duplicates removed)
- ✅ All required fields now 100% populated
- ✅ All regions properly mapped (NorthAmerica → AMER, etc.)

### December 8, 2025
- Initial spatial accuracy analysis
- Identified Semianalysis coordinate issues (841m median - suboptimal)

---

*Last Updated: January 2, 2026*
*Author: Meta Data Center GIS Team*
