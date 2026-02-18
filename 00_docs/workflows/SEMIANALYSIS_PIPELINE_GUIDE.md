# Semianalysis Data Pipeline Guide

## Complete Reference for Semianalysis V2 Data Processing

**Created:** January 14, 2026
**Last Updated:** January 27, 2026
**Version:** 1.5

---

## Table of Contents

1. [Overview](#1-overview)
2. [Pipeline Architecture](#2-pipeline-architecture)
3. [Configuration](#3-configuration)
4. [Excel Structure Reference](#4-excel-structure-reference)
5. [Step-by-Step Execution](#5-step-by-step-execution)
6. [Field Mappings](#6-field-mappings)
7. [Google Drive Export](#7-google-drive-export)
8. [Utility Scripts Reference](#8-utility-scripts-reference)
9. [Troubleshooting](#9-troubleshooting)
10. [Changelog](#10-changelog)

---

## 1. Overview

### What It Does

The Semianalysis pipeline automates the ingestion of Semianalysis' AI Data Center Model Excel workbook into the Consensus GIS Model. This is a complex multi-sheet Excel file with:

- **19 sheets** containing ~5,400+ data center records
- **Time-series MW capacity forecasts** (2023-2032)
- **AI enrichment data** (end_user, tenant, gpu_cloud)
- **Building-level coordinates** and company information
- **Total Lease by Market (TLBM)** aggregated capacity data by company and metro

### Data Types Extracted

| Record Type | Description | Approx Count |
|-------------|-------------|--------------|
| **Building** | Individual data center facilities with coordinates | ~5,700 |
| **TLBM_Hyperscaler** | Hyperscaler leasing by market (aggregated) | ~80 |
| **TLBM_Colo** | Colocation leasing by market (aggregated) | ~155 |

### Sheets Processed

| Sheet Name | Record Types | Description |
|------------|--------------|-------------|
| NA Data Center Supply | Building, TLBM | US/Canada data centers + market leasing |
| Overseas Data Center Supply | Building, TLBM | EMEA/APAC data centers + market leasing |
| AI Labs - OpenAI, Anthropic etc | Building | AI workload enrichment (overlaps with NA/Overseas) |
| Hyperscalers & Neoclouds | Building | Building records (Summary used for validation only) |

### Why It's Needed

The raw Semianalysis Excel is challenging to work with:

1. **Multiple sheets** with overlapping data (NA, Overseas, AI Labs)
2. **Inconsistent headers** across sheets (different row positions)
3. **Duplicate UUIDs** representing phases at the same site
4. **Column naming issues** (pandas reads "2023" as "2023.0")
5. **AI Labs enrichment** needs to be merged with base records
6. **TLBM sections** hidden at bottom of sheets need separate extraction

### Key Benefits

| Before (Manual) | After (Automated) |
|-----------------|-------------------|
| 2-3 hours manual Excel cleanup | ~5 minutes script execution |
| Error-prone copy/paste | Reproducible, auditable |
| 6 separate scripts | 1 unified pipeline |
| 7% year field population | 95% year field population |

---

## 2. Pipeline Architecture

### Data Flow

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                          SEMIANALYSIS V2 PIPELINE (v1.5)                            │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                     │
│  INPUT: AI-Data-Center-Model-CLIENT-SKU-*.xlsx                                     │
│                                                                                     │
│  ┌───────────────────────────────────────────────────────────────────────────────┐ │
│  │                           SOURCE SHEETS                                        │ │
│  ├───────────────────┬───────────────────┬─────────────────┬─────────────────────┤ │
│  │ NA Data Center    │ Overseas DC       │ AI Labs         │ Hyperscalers &      │ │
│  │ Supply            │ Supply            │                 │ Neoclouds           │ │
│  │ ┌───────────────┐ │ ┌───────────────┐ │ ┌─────────────┐ │ ┌─────────────────┐ │ │
│  │ │ Buildings     │ │ │ Buildings     │ │ │ Buildings   │ │ │ Summary Tables  │ │ │
│  │ │ (rows 19-5001)│ │ │ (rows 21-6000)│ │ │ (rows 80-   │ │ │ (rows 5-78)     │ │ │
│  │ │ ~3,090 recs   │ │ │ ~2,531 recs   │ │ │  500)       │ │ │ ~50-80 recs     │ │ │
│  │ └───────┬───────┘ │ └───────┬───────┘ │ │ ~270 recs   │ │ ├─────────────────┤ │ │
│  │ ┌───────┴───────┐ │ ┌───────┴───────┐ │ │ (99% over-  │ │ │ Buildings       │ │ │
│  │ │ TLBM Section  │ │ │ TLBM Section  │ │ │  lap)       │ │ │ (rows 82-740)   │ │ │
│  │ │ (rows 5108-   │ │ │ (rows 5937-   │ │ └─────────────┘ │ │ ~500-600 recs   │ │ │
│  │ │  5217)        │ │ │  6050)        │ │                 │ └─────────────────┘ │ │
│  │ │ ~110 recs     │ │ │ ~100 recs     │ │                 │                     │ │
│  │ └───────────────┘ │ └───────────────┘ │                 │                     │ │
│  └───────────────────┴───────────────────┴─────────────────┴─────────────────────┘ │
│                                          │                                         │
│  ════════════════════════════════════════╪═════════════════════════════════════    │
│                                          │                                         │
│                        ┌─────────────────┴─────────────────┐                       │
│                        │         STEP 1: EXTRACT           │                       │
│                        │  • Read each sheet with config    │                       │
│                        │  • Filter valid UUIDs             │                       │
│                        │  • Detect Excel formula errors    │                       │
│                        │  • Normalize column names         │                       │
│                        └─────────────────┬─────────────────┘                       │
│                                          │                                         │
│    ┌─────────────────────────────────────┼─────────────────────────────────────┐   │
│    │                                     │                                     │   │
│    ▼                                     ▼                                     ▼   │
│  ┌─────────────────────┐  ┌─────────────────────────────┐  ┌─────────────────────┐ │
│  │ STEP 2: TLBM        │  │ STEP 2B: HYPERSCALERS       │  │ STEP 3: BUILDINGS   │ │
│  │ EXTRACTION          │  │ EXTRACTION                  │  │ COMBINE             │ │
│  │ • Hyperscaler rows  │  │ • Summary tables (5-78)     │  │ • Concat NA+OV+AI   │ │
│  │ • Colo rows         │  │ • Building rows (82-740)    │  │ • Merge dup columns │ │
│  │ • Generate TLBM IDs │  │ • Generate HS IDs           │  │ • Clean orphan cols │ │
│  │ • Market geocoding  │  │ • Parse company hierarchy   │  │                     │ │
│  └──────────┬──────────┘  └──────────────┬──────────────┘  └──────────┬──────────┘ │
│             │                            │                            │            │
│             │                            │                            ▼            │
│             │                            │               ┌─────────────────────┐   │
│             │                            │               │ STEP 4: MERGE       │   │
│             │                            │               │ DUPLICATES          │   │
│             │                            │               │ • Group by UUID     │   │
│             │                            │               │ • SUM capacity cols │   │
│             │                            │               │ • FIRST for text    │   │
│             │                            │               └──────────┬──────────┘   │
│             │                            │                          │              │
│             └────────────────────────────┴──────────────────────────┘              │
│                                          │                                         │
│                                          ▼                                         │
│                        ┌─────────────────────────────────┐                         │
│                        │ STEP 5: COMBINE ALL DATA        │                         │
│                        │                                 │                         │
│                        │ record_level values:            │                         │
│                        │ • Building (~4,200 recs)        │                         │
│                        │ • TLBM_Hyperscaler (~100 recs)  │                         │
│                        │ • TLBM_Colo (~100 recs)         │                         │
│                        │ • Hyperscaler_Summary (~60 recs)│                         │
│                        └─────────────────┬───────────────┘                         │
│                                          │                                         │
│                                          ▼                                         │
│                        ┌─────────────────────────────────┐                         │
│                        │ STEP 6: EXPORT LOCAL            │                         │
│                        │ semianalysis_FINAL_             │                         │
│                        │ YYYYMMDD_HHMM.csv/xlsx          │                         │
│                        │                                 │                         │
│                        │ + data_vintage column           │                         │
│                        │ + field validation report       │                         │
│                        └─────────────────┬───────────────┘                         │
│                                          │                                         │
│         ┌────────────────────────────────┼────────────────────────────────┐        │
│         │                                │                                │        │
│         ▼                                ▼                                ▼        │
│  ┌─────────────────┐       ┌─────────────────────────┐      ┌─────────────────────┐│
│  │ LOCAL FILES     │       │ INGEST TO GDB           │      │ GOOGLE DRIVE        ││
│  │                 │       │                         │      │ EXPORT              ││
│  │ scripts/outputs/│       │ gold_buildings_full     │      │                     ││
│  │ • CSV           │       │                         │      │ Pipeline Ingestion/ ││
│  │ • Excel         │       │ record_level values:    │      │ • CSV               ││
│  │                 │       │ • Building ✓            │      │ • Excel             ││
│  │                 │       │ • TLBM_* ✓ (w/centroid) │      │ • Export log        ││
│  │                 │       │ • Hyperscaler_Summary ✗ │      │                     ││
│  │                 │       │   (no coordinates)      │      │                     ││
│  └─────────────────┘       └───────────┬─────────────┘      └─────────────────────┘│
│                                        │                                           │
│                                        ▼                                           │
│                        ┌─────────────────────────────────┐                         │
│                        │ STEP 7: VALIDATE                │                         │
│                        │ validate_sa_ingestion.py        │                         │
│                        │                                 │                         │
│                        │ • Compare CSV vs GDB counts     │                         │
│                        │ • Check field population        │                         │
│                        │ • Year field validation         │                         │
│                        └─────────────────────────────────┘                         │
│                                                                                    │
│  ══════════════════════════════════════════════════════════════════════════════   │
│                                                                                    │
│  OUTPUTS:                                                                          │
│  ├─ CSV/Excel: All records (Buildings + TLBM + Hyperscaler Summary)               │
│  ├─ Geodatabase: Building + TLBM records (with coordinates)                       │
│  └─ Google Drive: Team-shared flat files                                          │
│                                                                                    │
│  RECORD COUNTS (January 26, 2026 vintage):                                         │
│  ├─ Building (NA + Overseas):               ~5,700 (after deduplication)          │
│  ├─ Building (Hyperscalers tab):            ~387 (merged with NA/OS by UUID)      │
│  ├─ TLBM_Hyperscaler:                       ~80                                   │
│  ├─ TLBM_Colo:                              ~155                                  │
│  └─ TOTAL:                                  ~5,900+                               │
│                                                                                    │
└────────────────────────────────────────────────────────────────────────────────────┘
```

### Output Files Summary

| Output | Location | Format | Purpose |
|--------|----------|--------|---------|
| **Local CSV** | `scripts\outputs\` | `semianalysis_FINAL_YYYYMMDD_HHMM.csv` | Pipeline input for GDB ingestion |
| **Local Excel** | `scripts\outputs\` | `semianalysis_FINAL_YYYYMMDD_HHMM.xlsx` | Local backup |
| **GDrive CSV** | `Pipeline Ingestion\` | `semianalysis_FINAL_YYYYMMDD_HHMM.csv` | Team-shared flat file |
| **GDrive Excel** | `Pipeline Ingestion\` | `semianalysis_FINAL_YYYYMMDD_HHMM.xlsx` | Team-shared flat file |
| **Geodatabase** | `Default.gdb` | `gold_buildings_full` | Production layer |

### Scripts Involved

| Script | Location | Purpose |
|--------|----------|---------|
| `semianalysis_pipeline.py` | `_utils/` | **Main pipeline** - Extract, combine, merge, export |
| `gdrive_export.py` | `_utils/` | Google Drive export utility |
| `ingest_semianalysis_v2.py` | `01_ingestion/` | Ingest cleaned CSV to geodatabase |
| `validate_sa_ingestion.py` | `_utils/` | Validate field population after ingestion |

---

## 3. Configuration

### Main Configuration (semianalysis_pipeline.py)

```python
# ============================================================================
# CONFIGURATION - UPDATE THESE FOR NEW DATA VINTAGES
# ============================================================================

# Input Excel file - UPDATE THIS PATH for new SA releases
INPUT_FILE = r"C:\Users\ptanderson\Downloads\AI-Data-Center-Model-CLIENT-January-26-2026-SKU.xlsx"

# Output directory
OUTPUT_DIR = r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\scripts\outputs"
```

### Sheet Configuration

The sheet configuration must be updated when the Excel structure changes. **Updated January 16, 2026** for expanded Overseas sheet in the January 12 data vintage.

```python
# UPDATED 2026-01-16: Overseas sheet expanded significantly in January 12 data
SHEET_CONFIG = {
    'NA Data Center Supply': {
        'uuid_start_row': 19,      # First row with UUID (1-indexed)
        'uuid_end_row': 5001,      # Last row with UUID
        'header_row_1': 4,         # Row with headers for columns H-AA
        'header_row_2': 3,         # Row with headers for columns BV-CG, CL-CZ
        'source_label': 'NA'
    },
    'Overseas Data Center Supply': {
        'uuid_start_row': 21,
        'uuid_end_row': 6000,      # UPDATED: Was 1440, now extends to ~5931
        'header_row_1': 4,
        'header_row_2': 3,
        'source_label': 'Overseas'
    },
    'AI Labs - OpenAI, Anthropic etc': {
        'uuid_start_row': 80,
        'uuid_end_row': 500,       # UPDATED: Increased buffer for growth
        'header_row_1': 4,
        'header_row_2': 3,
        'source_label': 'AI Labs'
    }
}
```

> ⚠️ **Important:** Always verify sheet row ranges when processing a new data vintage. The Overseas sheet expanded from ~1,400 rows to ~6,000 rows between the December 2025 and January 2026 vintages.

### TLBM Configuration (Added January 2026)

The **Total Lease by Market (TLBM)** sections are located at the bottom of the NA and Overseas sheets. These contain aggregated leasing data by company and metro market.

```python
# TLBM sections - market-level aggregated capacity data
# Located at bottom of NA and Overseas sheets
TLBM_CONFIG = {
    'NA Data Center Supply': {
        'hyperscaler': {
            'start_row': 5108,     # First row of Hyperscaler TLBM data
            'end_row': 5160,       # Last row (approximate, adjust if needed)
            'header_row': 4,       # Same header row as main data (columns H-Z)
        },
        'colo': {
            'start_row': 5165,     # First row of Colo TLBM data
            'end_row': 5217,       # Last row
            'header_row': 4,
        },
        'source_label': 'NA'
    },
    'Overseas Data Center Supply': {
        'hyperscaler': {
            'start_row': 5937,     # First row of Hyperscaler TLBM data
            'end_row': 6000,       # Last row (approximate)
            'header_row': 4,
        },
        'colo': {
            'start_row': 6005,     # First row of Colo TLBM data (approximate)
            'end_row': 6050,       # Last row (approximate)
            'header_row': 4,
        },
        'source_label': 'Overseas'
    }
}

# TLBM uses columns H-Z (indices 7-25) for Company, Market, and capacity data
TLBM_COLUMNS = list(range(7, 26))  # H through Z
```

**Key Notes:**
- TLBM records use a synthetic `Unique_ID` format: `TLBM_{H|C}_{company}_{market}_{region}`
- TLBM records don't have coordinates (they're market-level aggregates)
- The `record_level` field distinguishes record types:
  - `Building` = individual facility with coordinates
  - `TLBM_Hyperscaler` = hyperscaler leasing by market
  - `TLBM_Colo` = colo leasing by market

### Hyperscalers & Neoclouds Configuration (Added January 2026)

The **Hyperscalers & Neoclouds** sheet contains two distinct sections:

1. **Summary Tables (rows 5-78)**: Company-level capacity aggregations by build type and region
2. **Building Records (rows 82-740)**: Individual facility records with coordinates

```python
# Hyperscalers & Neoclouds tab configuration
# Contains both summary aggregations and building records
HYPERSCALER_CONFIG = {
    'sheet_name': 'Hyperscalers & Neoclouds',
    'header_row': 4,           # Row with column headers (1-indexed)

    # Summary tables section (company aggregations)
    'summary': {
        'start_row': 5,        # First data row after header
        'end_row': 78,         # Last row of summary tables
        'columns': list(range(1, 27)),  # B:AA (indices 1-26)
        'record_level': 'Hyperscaler_Summary'
    },

    # Building records section (individual facilities)
    'buildings': {
        'start_row': 82,       # First row of building data
        'end_row': 740,        # Last row of building data
        'columns': list(range(0, 115)),  # A:DK (indices 0-114)
        'record_level': 'Building'
    }
}
```

**Summary Table Structure:**
- **Global Hyperscaler Critical IT Capacity**: Microsoft, Meta, Google, AWS, Oracle
- **Global Neocloud Critical IT Capacity**: Coreweave, Nebius, Lambda, etc.
- Each company has sub-rows by:
  - Build Type: Self-build, Leasing, Contracted Neocloud capacity
  - Region: North America, Overseas

**Key Notes:**
- Summary records use synthetic IDs: `HS_{company}_{build_type}_{region}`
- Summary records don't have coordinates (they're company aggregations)
- Building records use standard UUID format from column A
- The `record_level` field distinguishes:
  - `Hyperscaler_Summary` = company aggregation by build type/region
  - `Building` = individual facility with coordinates

### Ingestion Configuration (ingest_semianalysis_v2.py)

```python
# Source CSV - UPDATE after running semianalysis_pipeline.py
SOURCE_CSV = r"C:\...\scripts\outputs\semianalysis_FINAL_20260113_1430.csv"

# TLBM record handling options:
# 'skip' = don't ingest to GDB (TLBM stays in CSV only)
# 'centroid' = use market centroid coordinates (future)
# 'null_geom' = insert with null geometry (future)
TLBM_HANDLING = 'skip'  # Default: keep in CSV, don't ingest to GDB
```

---

## 4. Excel Structure Reference

### Sheet Layout

| Sheet Name | UUID Rows | Header Rows | ~Records | Purpose |
|------------|-----------|-------------|----------|---------|
| NA Data Center Supply | 19-5001 | 3-4 | ~3,145 | Primary US/Canada data |
| Overseas Data Center Supply | 21-6000 | 3-4 | ~2,598 | EMEA/APAC data |
| AI Labs - OpenAI, Anthropic etc | 80-400 | 3-4 | ~292 | AI enrichment (99% overlap) |
| Hyperscalers & Neoclouds | 82-740 | 3-4 | ~387 | Hyperscaler attribution (95% overlap) |

### Column Ranges

| Excel Columns | Index Range | Content |
|---------------|-------------|---------|
| A | 0 | UUID (unique identifier) |
| H-AA | 7-26 | Basic info (company, city, state, country, region) |
| BV-CG | 73-84 | Location coordinates (lat, long) |
| CL-CZ | 89-103 | Year-over-year MW forecasts (2023-2032) |

### Header Row Positions

| Content Type | Header Row |
|--------------|------------|
| Basic info columns (H-AA) | Row 4 |
| Location & year columns (BV-CG, CL-CZ) | Row 3 |

---

## 5. Step-by-Step Execution

### Quick Start

```python
# In ArcGIS Pro Python window:

# Step 1: Run extraction/merge pipeline
exec(open(r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\scripts\_utils\semianalysis_pipeline.py", encoding='utf-8').read())

# Step 2: Update SOURCE_CSV path in ingest script, then run ingestion
exec(open(r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\scripts\01_ingestion\ingest_semianalysis_v2.py", encoding='utf-8').read())

# Step 3: Validate (optional - runs automatically after ingestion)
exec(open(r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\scripts\_utils\validate_sa_ingestion.py", encoding='utf-8').read())
```

### Detailed Steps

#### Step 1: Update Configuration

When you receive a new Semianalysis Excel file:

1. **Save the file** to your Downloads folder
2. **Open `semianalysis_pipeline.py`** in a text editor
3. **Update `INPUT_FILE`** path:
   ```python
   INPUT_FILE = r"C:\Users\ptanderson\Downloads\AI-Data-Center-Model-CLIENT-SKU-January-2026.xlsx"
   ```
4. **Verify sheet coordinates** haven't changed (check manually in Excel):
   - First UUID row
   - Last UUID row
   - Header rows

#### Step 2: Run Extraction Pipeline

```python
exec(open(r"C:\...\scripts\_utils\semianalysis_pipeline.py", encoding='utf-8').read())
```

**Expected Output:**
```
======================================================================
SEMIANALYSIS COMPLETE PIPELINE
======================================================================
Started: 2026-01-13 14:30:00
Input: AI-Data-Center-Model-CLIENT-SKU-December-29-2026.xlsx

--- Extracting: NA Data Center Supply ---
  Read 4,983 rows, kept 3,085 with valid UUIDs

--- Extracting: Overseas Data Center Supply ---
  Read 1,420 rows, kept 714 with valid UUIDs

--- Extracting: AI Labs - OpenAI, Anthropic etc ---
  Read 303 rows, kept 270 with valid UUIDs

--- Combining Sheets ---
  Combined: 4,069 total records
  Columns after merge: 48

--- Merging Duplicates ---
  Duplicate UUIDs to merge: 339
  After merge: 3,730 records (reduced by 339)

PIPELINE COMPLETE
Total unique records: 3,730
Output ready for ingestion: semianalysis_FINAL_20260113_1430.csv
```

#### Step 3: Update Ingestion Script

1. **Note the output CSV filename** from Step 2
2. **Open `01_ingestion/ingest_semianalysis_v2.py`**
3. **Update `SOURCE_CSV`**:
   ```python
   SOURCE_CSV = r"C:\...\scripts\outputs\semianalysis_FINAL_20260113_1430.csv"
   ```

#### Step 4: Run Ingestion

```python
exec(open(r"C:\...\scripts\01_ingestion\ingest_semianalysis_v2.py", encoding='utf-8').read())
```

**Expected Output:**
```
[CLEANUP] Deleting existing Semianalysis records...
[CLEANUP] Deleted 3,717 records

[INGESTION] Reading CSV: semianalysis_FINAL_20260113_1430.csv
[INGESTION] Processing 3,730 records...
[INGESTION] Inserted 3,717 records (13 skipped - no coordinates)

[VALIDATION] Running field population comparison...
✅ All validations passed!
```

#### Step 5: Continue Standard Pipeline

After Semianalysis ingestion, continue with the rest of the pipeline:

```python
# Company standardization
exec(open(r"C:\...\scripts\02_processing\migrate_company_fields_v2.py", encoding='utf-8').read())

# UCID generation
exec(open(r"C:\...\scripts\03_ucid\generate_text_ucid.py", encoding='utf-8').read())

# Campus rollup
exec(open(r"C:\...\scripts\02_processing\campus_rollup_new.py", encoding='utf-8').read())

# ... etc
```

---

## 6. Field Mappings

### Source CSV → Gold Buildings Mapping

| CSV Column | Gold Field | Transform |
|------------|------------|-----------|
| Unique_ID | source_unique_id | Direct |
| Unique_ID | unique_id | Prefix "SEMI_" |
| Lat | latitude | safe_float() |
| Long | longitude | safe_float() |
| Company | company_source, company_clean | Direct + standardization |
| City | city | Direct |
| State | state | Direct |
| Country | country | COUNTRY_MAP |
| Region | region | REGION_MAP |
| 2023 | mw_2023 | safe_float() |
| 2024 | mw_2024 | safe_float() |
| ... | ... | ... |
| 2032 | mw_2032 | safe_float() |
| Total under Construction MW | uc_power_mw | safe_float() |
| Total Planned MW | planned_power_mw | safe_float() |
| Installed Capacity MW (Q2 2025) | commissioned_power_mw | safe_float() |
| Full Capacity | full_capacity_mw | safe_float() |
| Facility Square Footage | facility_sqft | safe_float() |
| end_user | end_user | Direct |
| tenant | tenant | Direct |
| gpu_cloud | gpu_cloud | Direct |
| data_vintage | data_vintage | parse_date_flexible() |
| start_ops | construction_start_date | parse_date_flexible() |
| live_assumption | actual_live_date | parse_date_flexible() |

### Year-over-Year MW Fields

| Year | CSV Column | Gold Field | Expected Population |
|------|------------|------------|---------------------|
| 2023 | 2023 | mw_2023 | ~47% |
| 2024 | 2024 | mw_2024 | ~57% |
| 2025 | 2025 | mw_2025 | ~64% |
| 2026 | 2026 | mw_2026 | ~73% |
| 2027 | 2027 | mw_2027 | ~86% |
| 2028 | 2028 | mw_2028 | ~89% |
| 2029 | 2029 | mw_2029 | ~92% |
| 2030 | 2030 | mw_2030 | ~95% |
| 2031 | 2031 | mw_2031 | ~95% |
| 2032 | 2032 | mw_2032 | ~95% |

### Duplicate Handling

When merging duplicate UUIDs (same location, different phases):

| Column Type | Aggregation | Example |
|-------------|-------------|---------|
| Base Capacity (2017-2040) | FIRST from NA/Overseas | 100 MW from NA (authoritative) |
| AI_ Capacity (AI_2017-AI_2040) | FIRST non-null | 50 MW from AI Labs (attribution) |
| HS_ Capacity (HS_2017-HS_2040) | FIRST non-null | 75 MW from Hyperscalers (attribution) |
| Text (company, city) | FIRST non-null | "AWS" |
| Source_Sheet | CONCATENATE | "AI Labs, Hyperscalers, NA" |

### Tenant Attribution Columns (Added January 2026)

These columns capture WHO uses HOW MUCH of a building's capacity. They are **descriptive** (not additive to base capacity).

#### AI Labs Attribution (AI_* prefix)

| CSV Column | Purpose | Source Tab |
|------------|---------|------------|
| AI_2017 - AI_2040 | AI workload capacity by year | AI Labs - OpenAI, Anthropic etc |

**Usage Notes:**
- Represents portion of building capacity used for AI training/inference
- ~99.6% of AI Labs records match UUIDs in NA/Overseas
- Use for analysis of AI adoption by facility/company

#### Hyperscaler Attribution (HS_* prefix)

| CSV Column | Purpose | Source Tab |
|------------|---------|------------|
| HS_2017 - HS_2040 | Hyperscaler leased capacity by year | Hyperscalers & Neoclouds |
| HS_Company | Hyperscaler tenant name | Hyperscalers & Neoclouds |
| HS_Description | Facility description | Hyperscalers & Neoclouds |
| HS_Notes | Additional notes | Hyperscalers & Neoclouds |
| HS_Region | Geographic region | Hyperscalers & Neoclouds |
| HS_Status | Project status | Hyperscalers & Neoclouds |
| HS_Total Planned MW | Total planned capacity | Hyperscalers & Neoclouds |
| HS_Total under Construction MW | Capacity under construction | Hyperscalers & Neoclouds |
| HS_Planned + UC | Planned + Under Construction | Hyperscalers & Neoclouds |

**Usage Notes:**
- Represents portion of building capacity leased by hyperscalers
- ~95.4% of Hyperscaler records match UUIDs in NA/Overseas
- Often shows ~50% of base capacity (one phase of multi-phase facility)
- Use for tenant attribution analysis

---

## 7. Google Drive Export

### Overview

The pipeline automatically exports the cleaned and merged Semianalysis global flat file to a shared Google Drive folder for team collaboration.

**Shared Folder URL:** [https://drive.google.com/drive/u/0/folders/1gXwCKN5Osh6g8p4QI8e-KgiQEEi7RBnV](https://drive.google.com/drive/u/0/folders/1gXwCKN5Osh6g8p4QI8e-KgiQEEi7RBnV)

### Export Location

The utility attempts to find an accessible Google Drive path in this order:

| Priority | Path | Description |
|----------|------|-------------|
| 1 | `G:\Shared drives\DC GIS Model\Pipeline Ingestion` | Shared drive (preferred) |
| 2 | `G:\My Drive\Consensus GIS Model Cleaned Inputs\Pipeline Ingestion` | My Drive fallback |

### Exported Files

The pipeline generates outputs in multiple formats for different use cases:

#### Wide Format (for GIS and spatial analysis)

| File Type | Naming Pattern | Example |
|-----------|---------------|---------|
| CSV | `semianalysis_FINAL_YYYYMMDD_HHMM.csv` | `semianalysis_FINAL_20260127_1040.csv` |
| Excel | `semianalysis_FINAL_YYYYMMDD_HHMM.xlsx` | `semianalysis_FINAL_20260127_1040.xlsx` |

**Structure:** ~138 columns, ~5,848 rows
- One row per building/TLBM record
- Year columns as separate fields (2017, 2018, ... 2040)
- AI_ and HS_ capacity columns alongside base capacity
- Ideal for: GIS mapping, spatial analysis, ArcGIS Pro import

#### Long Format (for time series analysis)

| File Type | Naming Pattern | Example |
|-----------|---------------|---------|
| CSV | `semianalysis_LONG_YYYYMMDD_HHMM.csv` | `semianalysis_LONG_20260127_1040.csv` |

**Structure:** 23 columns, ~100,000+ rows
- Multiple rows per building (one per year)
- Uses `pd.melt()` to pivot year columns into rows
- Columns: Unique_ID, Year, MW_Capacity, AI_MW_Capacity, HS_MW_Capacity
- Ideal for: Time series analysis, Power BI, trend visualization

| Column | Description |
|--------|-------------|
| Year | Integer year (2017-2040) |
| MW_Capacity | Base capacity in MW (from NA/Overseas) |
| AI_MW_Capacity | AI workload capacity (from AI Labs tab) |
| HS_MW_Capacity | Hyperscaler leased capacity (from Hyperscalers tab) |

### Pipeline Output

When the pipeline runs, you'll see:

```
======================================================================
STEP 7: EXPORT TO SHARED GOOGLE DRIVE
======================================================================

--- Exporting to Google Drive ---
  Target folder: G:\Shared drives\DC GIS Model\Semianalysis Global Flat Files
  ✅ CSV: semianalysis_FINAL_20260114_1430.csv
  ✅ Excel: semianalysis_FINAL_20260114_1430.xlsx

  Successfully exported 2 files to Google Drive
  📁 View at: https://drive.google.com/drive/u/0/folders/1gXwCKN5Osh6g8p4QI8e-KgiQEEi7RBnV
```

### Prerequisites

1. **Google Drive Desktop** must be installed and running
2. Access to the shared folder must be granted
3. The G: drive must be mounted

### Manual Upload (Fallback)

If Google Drive is not accessible:

1. Locate the local output files:
   ```
   C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\scripts\outputs\
   ```

2. Manually upload to the shared folder:
   - Open: https://drive.google.com/drive/u/0/folders/1gXwCKN5Osh6g8p4QI8e-KgiQEEi7RBnV
   - Drag and drop both CSV and Excel files

### Configuration

The export utility is located at `_utils/gdrive_export.py`. To modify paths:

```python
# In gdrive_export.py

# Primary shared drive path
GDRIVE_SEMIANALYSIS_SHARED = r"G:\Shared drives\DC GIS Model\Semianalysis Global Flat Files"

# Fallback My Drive path
GDRIVE_SEMIANALYSIS_ALT = r"G:\My Drive\Consensus GIS Model Cleaned Inputs\Semianalysis Global Flat Files"

# Google Drive folder ID (for web URL)
GDRIVE_FOLDER_ID = "1gXwCKN5Osh6g8p4QI8e-KgiQEEi7RBnV"
```

### Standalone Usage

You can also use the export utility independently:

```python
from gdrive_export import export_to_gdrive, get_gdrive_status

# Check Google Drive status
status = get_gdrive_status()
print(f"Google Drive accessible: {status['accessible']}")
print(f"Path: {status['path']}")

# Export files
success, message = export_to_gdrive(
    csv_path=r"C:\...\outputs\semianalysis_FINAL_20260114_1430.csv",
    xlsx_path=r"C:\...\outputs\semianalysis_FINAL_20260114_1430.xlsx"
)
```

---

## 8. Utility Scripts Reference

### Primary Scripts

| Script | Purpose | When to Use |
|--------|---------|-------------|
| **`semianalysis_pipeline.py`** | Extract, combine, merge SA sheets | New SA data vintage |
| **`ingest_semianalysis_v2.py`** | Load CSV to geodatabase | After pipeline export |
| **`validate_sa_ingestion.py`** | Validate field population | After ingestion |

### Diagnostic Scripts (Archived)

As of January 27, 2026, diagnostic scripts have been moved to `_utils/_sa_archive/` for cleaner organization.
See `_utils/_sa_archive/README.md` for the complete archive inventory.

| Archive Folder | Contents | Purpose |
|----------------|----------|---------|
| `_sa_archive/investigation/` | 10 scripts | One-time investigation scripts |
| `_sa_archive/superseded/` | 8 scripts | Scripts merged into main pipeline |
| `_sa_archive/debug/` | 20 scripts | Debugging and diagnostic scripts |

### Active Utility Scripts

Only these utility scripts remain active in `_utils/`:

| Script | Purpose |
|--------|---------|
| `semianalysis_pipeline.py` | Main unified pipeline (extraction, cleaning, export) |
| `validate_sa_ingestion.py` | Post-ingestion validation for GDB |
| `config.py` | Shared configuration settings |
| `gdrive_export.py` | Google Drive export utility |
| `date_helpers.py` | Date parsing utilities |

### Legacy Scripts (Archived)

These individual scripts have been replaced by `semianalysis_pipeline.py` and moved to `_sa_archive/superseded/`:

| Archived Script | Original Purpose |
|-----------------|------------------|
| `extract_sa_na.py` | NA extraction (now in pipeline) |
| `extract_sa_overseas.py` | Overseas extraction (now in pipeline) |
| `extract_sa_ai_labs.py` | AI Labs extraction (now in pipeline) |
| `combine_sa_extracts.py` | Combine sheets (now in pipeline) |
| `merge_sa_duplicates.py` | UUID deduplication (now in pipeline) |
| `clean_semianalysis_excel.py` | Excel cleaning (now in pipeline) |
| `ingest_semianalysis.py` | V1 ingestion (replaced by V2) |

---

## 9. Known Issues & Data Relationships

### FIXED: Hyperscaler Building Deduplication (January 2026)

**Status:** ✅ FIXED (January 27, 2026)

**Original Issue:** The Hyperscalers & Neoclouds building records were added to the output AFTER the duplicate merge step, resulting in duplicate UUIDs in the final output.

**Solution Implemented:**
1. Hyperscaler building extraction now happens BEFORE Step 4 (merge_duplicates)
2. AI Labs and Hyperscaler capacity columns are now **prefixed** (AI_2025, HS_2025, etc.) to preserve them as separate tenant attribution data
3. Base capacity columns (2025, 2026, etc.) come from NA/Overseas (authoritative sources)

**Key Insight - Tenant Attribution Model:**
- **NA/Overseas tabs** = TOTAL building capacity (authoritative)
- **AI Labs/Hyperscaler tabs** = DESCRIPTIVE (who uses how much)
- The AI Labs/Hyperscaler capacity values should NOT be added to NA/OS - they attribute portions of building capacity to specific tenants/users

### Data Model: Base Capacity vs. Tenant Attribution

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     CAPACITY DATA MODEL                                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  BASE CAPACITY (2017, 2018, ... 2040)                                       │
│  ├── Source: NA Data Center Supply, Overseas Data Center Supply             │
│  ├── Meaning: TOTAL building capacity in MW                                 │
│  └── Usage: Sum for company/region totals                                   │
│                                                                              │
│  AI LABS ATTRIBUTION (AI_2017, AI_2018, ... AI_2040)                        │
│  ├── Source: AI Labs - OpenAI, Anthropic etc tab                            │
│  ├── Meaning: Portion of building capacity used for AI training/inference   │
│  └── Usage: Attribution analysis (WHO uses HOW MUCH for AI)                 │
│                                                                              │
│  HYPERSCALER ATTRIBUTION (HS_2017, HS_2018, ... HS_2040)                    │
│  ├── Source: Hyperscalers & Neoclouds tab                                   │
│  ├── Meaning: Portion of building capacity leased by hyperscalers           │
│  └── Usage: Attribution analysis (WHO leases HOW MUCH)                      │
│                                                                              │
│  IMPORTANT: AI_ and HS_ columns are NOT additive to base capacity!          │
│  They represent SUBSETS of the total capacity for attribution purposes.     │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Data Source Relationships Summary

| Data Source | Relationship | Capacity Columns | Add to Aggregation? |
|-------------|--------------|------------------|---------------------|
| NA Data Center Supply | Primary buildings | 2017-2040 (base) | ✅ YES |
| Overseas Data Center Supply | Primary buildings | 2017-2040 (base) | ✅ YES |
| AI Labs | **SUBSET** (99.6% overlap) | AI_2017-AI_2040 | ❌ NO (descriptive) |
| Hyperscalers Buildings | **SUBSET** (95.4% overlap) | HS_2017-HS_2040 | ❌ NO (descriptive) |
| TLBM | Additional colo leasing | 2017-2040 (base) | ✅ YES |

### Correct Aggregation Formula

```
Company Total Capacity = NA Buildings + Overseas Buildings + TLBM
                        (Base capacity columns only: 2017, 2018, ... 2040)

AI Workload Attribution = Sum of AI_* columns (for AI usage analysis)
Hyperscaler Leasing     = Sum of HS_* columns (for tenant analysis)
```

---

## 10. Troubleshooting

### Common Issues

#### Issue: Year fields (mw_2023-mw_2032) have low population

**Symptoms:** Validation shows 7-25% instead of expected 40-95%

**Root Cause:** Pandas reads numeric column headers (like "2023") as floats, creating "2023.0" column names. The ingestion script may not find the right column.

**Solution:** The pipeline now includes `normalize_column_names()` and `merge_duplicate_columns()` to handle this. If still seeing issues:

1. Check the CSV column names:
   ```python
   import pandas as pd
   df = pd.read_csv("semianalysis_FINAL_*.csv")
   print([c for c in df.columns if '202' in str(c)])
   ```

2. Verify columns are "2023" not "2023.0":
   ```python
   # Should see: ['2023', '2024', '2025', ...]
   # NOT: ['2023.0', '2024.0', '2025.0', ...]
   ```

#### Issue: "File not found" error

**Solution:** Update `INPUT_FILE` path in `semianalysis_pipeline.py`

#### Issue: Wrong record count after extraction

**Symptoms:** Fewer/more records than expected

**Possible Causes:**
1. Sheet structure changed (header rows moved)
2. UUID range changed (more/fewer rows with data)

**Solution:**
1. Open Excel file manually
2. Find first/last row with valid UUID in column A
3. Find header rows (check rows 3 and 4)
4. Update `SHEET_CONFIG` in the pipeline script

#### Issue: AI Labs fields (end_user, tenant) not populating

**Symptoms:** V2 enrichment fields all NULL

**Check:**
1. Verify AI Labs sheet is being extracted
2. Check merge is happening (should see "NA, AI Labs" in Source_Sheet)
3. Verify AI Labs sheet coordinates are correct

#### Issue: Ingestion skips too many records

**Symptoms:** "X skipped - no coordinates" is high

**Normal:** 10-20 records skipped is normal (no lat/long in source)

**If higher:**
1. Check Lat/Long columns are being extracted
2. Verify coordinate columns are in `COLUMNS_TO_KEEP` range
3. Check CSV has lat/long values:
   ```python
   df = pd.read_csv("semianalysis_FINAL_*.csv")
   print(df[['Lat', 'Long']].notna().sum())
   ```

### Validation Checks

After ingestion, verify with:

```python
# Quick field population check
import arcpy
fc = r"C:\...\Default.gdb\gold_buildings_full"

# Count Semianalysis records
with arcpy.da.SearchCursor(fc, ["source"], "source = 'Semianalysis'") as cur:
    print(f"SA records: {sum(1 for _ in cur)}")

# Check year fields
for year in range(2023, 2033):
    field = f"mw_{year}"
    with arcpy.da.SearchCursor(fc, [field], f"source = 'Semianalysis' AND {field} > 0") as cur:
        count = sum(1 for _ in cur)
        print(f"{field}: {count}")
```

---

## 10. Changelog

### February 2, 2026 (v1.6) - TLBM Geocoding & Data Vintage Fixes

**Bug Fixes:**
- **CRITICAL: Missing Lat/Long columns in extraction**: `COLUMNS_TO_KEEP` only extracted columns 0-74, but Lat/Long are in columns 91-92. Extended range to include columns 78-100 (location data). This was causing 92% of records to be skipped during ingestion.
- **Missing 'Great Britain' in MARKET_CENTROIDS**: Added `'Great Britain': (51.5074, -0.1278)` alias for UK in `semianalysis_pipeline.py` (line 319) to fix Coreweave TLBM geocoding failures for EMEA records
- **data_vintage not populating in gold_buildings**: Fixed `ingest_semianalysis_v2.py` which was hardcoding `None` instead of reading the `data_vintage` column from the pipeline CSV output
  - Added `data_vintage_str = row.get('data_vintage')` to read from CSV (line 329)
  - Changed insert from `None` to `parse_date_flexible(data_vintage_str)` (line 451)

**Root Cause Analysis:**
- Pipeline (`semianalysis_pipeline.py`) was correctly generating `data_vintage` column
- Ingestion script had outdated code with comment "(not in cleaned CSV yet)" that predated the pipeline update

**Files Modified:**
- `scripts/_utils/semianalysis_pipeline.py` - Added Great Britain centroid
- `scripts/01_ingestion/ingest_semianalysis_v2.py` - Fixed data_vintage ingestion

### January 27, 2026 (v1.5) - Tenant Attribution Model & Script Consolidation

**Data Model Clarification:**
- **FIXED: Hyperscaler Deduplication Bug**: Hyperscaler buildings now included in merge step BEFORE Step 4, eliminating duplicate UUID issues
- **Tenant Attribution Model**: Clarified that AI Labs and Hyperscaler capacity values are DESCRIPTIVE (who uses how much), NOT additive to base capacity
  - Base capacity columns (2017-2040): From NA/Overseas tabs (authoritative total)
  - AI_ capacity columns (AI_2017-AI_2040): From AI Labs tab (tenant attribution)
  - HS_ capacity columns (HS_2017-HS_2040): From Hyperscalers tab (tenant attribution)

**New Features:**
- **Dual Output Formats**:
  - Wide format (CSV/XLSX): ~138 columns for GIS and spatial analysis
  - Long format (CSV): 23 columns using `pd.melt()` for time series analysis
- **Dynamic Data Vintage**: Automatically extracted from input filename
- **Improved Column Organization**: ID → Location → Company/Type → Capacity → Metadata

**Script Consolidation:**
- Archived 38 temporary/investigation/debug scripts to `_utils/_sa_archive/`
- Active pipeline reduced to 6 core files in `_utils/`
- Created `_sa_archive/README.md` documenting archived scripts

**Documentation Updates:**
- Updated record counts to reflect January 26, 2026 release (~5,900+ total records)
- Added tenant attribution data model documentation (Section 9)
- Added output format documentation (Section 7)
- Updated utility scripts reference to reflect archive structure

### January 23, 2026 (v1.4) - TLBM Refinements + Validation
- **Overseas TLBM Extraction Fixed**: Corrected column structure detection for Overseas sheet where countries appear in Company column instead of Market column
  - Added region detection logic (EMEA, APAC, LATAM) to skip region headers
  - Countries are now properly treated as Markets for geocoding
- **Expanded Market Centroids**: Added ~80 additional market centroids for improved geocoding:
  - Rural/small markets: Cedar Rapids, Harwood ND, Temple TX, Boydton VA, Cheyenne WY, etc.
  - West Texas data center corridor: Midland, Odessa, Sweetwater, Big Spring, Pecos, etc.
  - Country-level fallbacks: Netherlands, France, Brazil, Chile, Germany, UK, etc.
- **Summary Row Filter**: Added filter to exclude summary rows that were slipping through:
  - "Total North America Hyperscale Colo Supply", "Total Overseas", etc.
- **Hyperscaler Summary → Validation Only**: Changed Hyperscaler Summary tables from ingested data to validation-only step:
  - Summary tables (rows 5-78) are now extracted for comparison, not ingestion
  - Added `validate_hyperscaler_totals()` function to compare summary vs. building aggregations
  - Reports discrepancies by company and year with tolerance thresholds
- **Encoding Fix**: Replaced Unicode symbols (✓, ⚠️, ❌) with ASCII equivalents for Windows cp1252 compatibility
- **Improved TLBM Geocoding**: Now achieving ~80%+ geocoding rate for TLBM records
  - NA Hyperscaler: 92% geocoded
  - NA Colo: 63% geocoded (many smaller/rural markets)
  - Overseas Hyperscaler: 87% geocoded
  - Overseas Colo: 79% geocoded

### January 22, 2026 (v1.3) - TLBM + Hyperscalers Extraction
- **New Data Type: Total Lease by Market (TLBM)**: Added extraction of aggregated market-level leasing data from bottom of NA and Overseas sheets
  - `TLBM_Hyperscaler`: Hyperscaler leasing aggregated by company and metro market
  - `TLBM_Colo`: Colocation leasing aggregated by company and metro market
- **New Data Type: Hyperscalers & Neoclouds**: Added extraction from dedicated sheet
  - `Hyperscaler_Summary`: Company-level capacity by build type (Self-build/Leasing) and region (NA/Overseas)
  - Building records: Individual hyperscaler/neocloud facilities with coordinates
  - Companies covered: Microsoft, Meta, Google, AWS, Oracle, Coreweave, Nebius, Lambda, etc.
- **Market Centroid Geocoding**: Added ~130 data center markets for TLBM geocoding
  - TLBM records automatically assigned coordinates from market centroid lookup
  - Supports partial/fuzzy matching (e.g., "Northern Virginia Area" → Northern Virginia)
- **Excel Formula Error Detection**: Pipeline now detects and reports broken formulas (#REF!, #N/A, etc.)
  - Converts error cells to NaN with warning messages
  - Reports affected columns and error counts
- **`record_level` field**: Extended to support new record types:
  - `Building` = individual facility with coordinates
  - `TLBM_Hyperscaler` = hyperscaler leasing by market
  - `TLBM_Colo` = colo leasing by market
- **Synthetic IDs**: TLBM uses format `TLBM_{H|C}_{company}_{market}_{region}`
- **Ingestion handling**: TLBM records included in GDB with centroid coordinates
- **Updated data flow diagram**: Shows TLBM + Hyperscaler extraction paths

### January 16, 2026 (v1.2)
- **Overseas sheet expansion**: Updated `uuid_end_row` from 1440 → 6000 to capture all ~2,531 overseas records (was only capturing ~718)
- **AI Labs buffer**: Increased `uuid_end_row` from 382 → 500 for future growth
- **Data vintage field**: Added `data_vintage` column extracted from filename (e.g., "January 12, 2026")
- **Orphan column cleanup**: Added `cleanup_orphan_columns()` function to merge stray Col_* columns:
  - Col_8 (MW units) → merged into `Unit` column
  - Col_102 (city names) → merged into `City` column
  - Col_89/Col_90 (stray coordinates) → merged into `Lat`/`Long` if missing
- **Field truncation**: Added max length limits to prevent field overflow errors (e.g., `building_designation` truncated to 50 chars)
- Updated documentation with new record counts and configuration notes

### January 14, 2026 (v1.1)
- Added Google Drive export as Step 7 in pipeline
- Created `gdrive_export.py` utility for automatic upload to shared folder
- Updated data flow diagram to show GDrive export branch
- Added "Output Files Summary" table with all output locations

### January 14, 2026 (v1.0)
- Created initial SEMIANALYSIS_PIPELINE_GUIDE.md

### January 13, 2026 (Pipeline Updates)
- Fixed year column naming issue (2023.0 → 2023)
- Added `normalize_column_names()` function
- Added `merge_duplicate_columns()` function
- Created `validate_sa_ingestion.py` validation module
- Year field population improved from 7% → 95%

### January 12, 2026 (Initial Pipeline)
- Created unified `semianalysis_pipeline.py`
- Replaced 6 individual scripts with single pipeline
- Added configuration-driven sheet extraction
- Added duplicate UUID merging with SUM aggregation

---

## Related Documentation

| Document | Purpose |
|----------|---------|
| `PIPELINE_EXECUTION_ORDER.md` | Complete pipeline execution order |
| `PIPELINE_DOCUMENTATION.md` | Comprehensive technical documentation |
| `MASTER_FIELD_MAPPING.md` | Complete field lineage |
| `CAPACITY_FIELD_DEFINITIONS.md` | Capacity field definitions |
| `PROGRESS_UPDATE_JAN13.md` | Session notes with pipeline development |

---

*Document updated: February 2, 2026*
*Original creation: January 14, 2026*
*Author: Meta Data Center GIS Team*
