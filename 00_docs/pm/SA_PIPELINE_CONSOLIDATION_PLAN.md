# SemiAnalysis Pipeline Consolidation Plan

**Created:** January 27, 2026
**Purpose:** Consolidate and reorganize SA-related scripts and documentation for better maintainability

---

## Current State Analysis

### 1. Scripts by Location

#### `_utils/` (38 SA-related files)

| File | Purpose | Status | Recommendation |
|------|---------|--------|----------------|
| **semianalysis_pipeline.py** | Main unified pipeline | ✅ ACTIVE | Keep as primary |
| **validate_sa_ingestion.py** | Post-ingestion validation | ✅ ACTIVE | Keep |
| **config.py** | Shared configuration | ✅ ACTIVE | Keep |
| **gdrive_export.py** | Google Drive export | ✅ ACTIVE | Keep |
| **date_helpers.py** | Date utilities | ✅ ACTIVE | Keep |
| **PIPELINE_CHANGELOG.md** | Change log | ✅ ACTIVE | Keep |
| analyze_output.py | Output analysis helper | ⚠️ TEMPORARY | Archive after consolidation |
| analyze_col_columns.py | Debug Col_* columns | ⚠️ TEMPORARY | Archive |
| analyze_sa_duplicates.py | Duplicate analysis | ⚠️ INVESTIGATION | Archive |
| analyze_semianalysis_deep.py | Deep analysis | ⚠️ INVESTIGATION | Archive |
| analyze_semianalysis_excel.py | Excel structure analysis | ⚠️ INVESTIGATION | Archive |
| analyze_sheet_overlap.py | Sheet overlap analysis | ⚠️ INVESTIGATION | Archive |
| check_building_fields.py | Field checking | ⚠️ DEBUG | Archive |
| check_dup_coords.py | Coordinate duplicate check | ⚠️ DEBUG | Archive |
| check_hyperscaler_duplicates.py | Hyperscaler duplicate check | ⚠️ INVESTIGATION | Archive |
| check_record_levels.py | Record level check | ⚠️ DEBUG | Archive |
| check_sa_year_fields.py | Year field check | ⚠️ DEBUG | Archive |
| check_source_overlap.py | Source overlap v1 | ⚠️ INVESTIGATION | Archive |
| check_source_overlap_v2.py | Source overlap v2 | ⚠️ INVESTIGATION | Archive |
| clean_semianalysis_excel.py | Excel cleaning | ❌ SUPERSEDED | Archive (merged into pipeline) |
| combine_sa_extracts.py | Combine extracts | ❌ SUPERSEDED | Archive (merged into pipeline) |
| debug_sa_dates.py | Date debugging | ⚠️ DEBUG | Archive |
| diagnose_essential_matching.py | Essential list matching | ⚠️ DEBUG | Archive |
| diagnose_sa_structure.py | Structure diagnosis | ⚠️ DEBUG | Archive |
| diagnose_sa_ucids.py | UCID diagnosis | ⚠️ DEBUG | Archive |
| diagnose_year_fields.py | Year field diagnosis | ⚠️ DEBUG | Archive |
| explore_essential_list.py | Essential list exploration | ⚠️ DEBUG | Archive |
| extract_sa_ai_labs.py | AI Labs extraction | ❌ SUPERSEDED | Archive (merged into pipeline) |
| extract_sa_na.py | NA extraction | ❌ SUPERSEDED | Archive (merged into pipeline) |
| extract_sa_overseas.py | Overseas extraction | ❌ SUPERSEDED | Archive (merged into pipeline) |
| find_ai_labs_uuids.py | AI Labs UUID finder | ⚠️ INVESTIGATION | Archive |
| investigate_half_pattern.py | Half-value pattern investigation | ⚠️ INVESTIGATION | Archive |
| investigate_hyperscaler_overlap.py | Hyperscaler overlap investigation | ⚠️ INVESTIGATION | Archive |
| merge_sa_duplicates.py | Duplicate merging | ❌ SUPERSEDED | Archive (merged into pipeline) |
| show_output_summary.py | Output summary | ⚠️ TEMPORARY | Archive |
| verify_fix.py | Fix verification | ⚠️ TEMPORARY | Archive |
| verify_output_columns.py | Column verification | ⚠️ TEMPORARY | Archive |

**Summary:** 6 ACTIVE files to keep, 32 files to archive

#### `01_ingestion/` (2 SA-related files)

| File | Purpose | Status | Recommendation |
|------|---------|--------|----------------|
| ingest_semianalysis.py | GDB ingestion (v1) | ⚠️ LEGACY | Archive or update |
| ingest_semianalysis_v2.py | GDB ingestion (v2) | ✅ ACTIVE | Keep - uses pipeline output |

#### `02_processing/` (1 SA-related file)

| File | Purpose | Status | Recommendation |
|------|---------|--------|----------------|
| add_semianalysis_v2_fields.py | Add V2 fields | ⚠️ LEGACY | Archive (merged into pipeline) |

#### `04_validation/diagnostics/` (4 SA-related files)

| File | Purpose | Status | Recommendation |
|------|---------|--------|----------------|
| check_semianalysis_headers.py | Header validation | ⚠️ DEBUG | Archive |
| check_semianalysis_meta.py | Metadata validation | ⚠️ DEBUG | Archive |
| test_semianalysis_capacity_relationships.py | Capacity relationship tests | ⚠️ INVESTIGATION | Archive |
| test_semianalysis_raw_vs_gold.py | Raw vs Gold comparison | ⚠️ DEBUG | Archive |

#### `04_validation/fixes/` (1 SA-related file)

| File | Purpose | Status | Recommendation |
|------|---------|--------|----------------|
| patch_semianalysis_planned_plus_uc.py | Planned+UC patch | ⚠️ ONE-TIME FIX | Archive |

#### `_archive/ingestion/` (1 SA-related file)

| File | Purpose | Status | Recommendation |
|------|---------|--------|----------------|
| reimport_semianalysis.py | Re-import script | ❌ ARCHIVED | Already archived |

---

### 2. Documentation by Location

#### `00_docs/workflows/` (Primary SA Documentation)

| File | Purpose | Status | Recommendation |
|------|---------|--------|----------------|
| **SEMIANALYSIS_PIPELINE_GUIDE.md** | Complete pipeline reference | ✅ ACTIVE | Keep as primary |
| PIPELINE_DOCUMENTATION.md | General pipeline docs | ✅ ACTIVE | Keep |
| PIPELINE_EXECUTION_ORDER.md | Execution order | ✅ ACTIVE | Keep |

#### `00_docs/analysis/` (Investigation Documentation)

| File | Purpose | Status | Recommendation |
|------|---------|--------|----------------|
| SEMIANALYSIS_DATA_RELATIONSHIP_INVESTIGATION.md | Data relationship investigation | ✅ REFERENCE | Keep for historical context |

#### `00_docs/schemas/` (Schema Documentation)

| File | Purpose | Status | Recommendation |
|------|---------|--------|----------------|
| CAPACITY_FIELD_DEFINITIONS.md | Capacity field definitions | ✅ ACTIVE | Keep |
| MASTER_FIELD_MAPPING.md | Field mapping reference | ✅ ACTIVE | Keep |

---

## Proposed New Structure

### Option A: Archive Investigation Scripts (Recommended)

```
scripts/
├── _utils/
│   ├── semianalysis_pipeline.py      # Main pipeline (KEEP)
│   ├── validate_sa_ingestion.py      # Validation (KEEP)
│   ├── config.py                     # Config (KEEP)
│   ├── gdrive_export.py              # Export (KEEP)
│   ├── date_helpers.py               # Helpers (KEEP)
│   ├── PIPELINE_CHANGELOG.md         # Changelog (KEEP)
│   └── _sa_archive/                  # NEW: Archive folder
│       ├── investigation/            # Investigation scripts
│       │   ├── analyze_sa_duplicates.py
│       │   ├── check_hyperscaler_duplicates.py
│       │   ├── investigate_half_pattern.py
│       │   └── ... (other investigation scripts)
│       ├── superseded/               # Superseded by pipeline
│       │   ├── extract_sa_na.py
│       │   ├── extract_sa_overseas.py
│       │   ├── extract_sa_ai_labs.py
│       │   ├── clean_semianalysis_excel.py
│       │   └── ... (other superseded scripts)
│       └── debug/                    # One-time debug scripts
│           ├── check_building_fields.py
│           ├── diagnose_sa_structure.py
│           └── ... (other debug scripts)
│
├── 01_ingestion/
│   ├── ingest_semianalysis_v2.py     # KEEP - GDB ingestion
│   └── _archive/
│       └── ingest_semianalysis.py    # ARCHIVE - v1 ingestion
│
├── 00_docs/
│   └── workflows/
│       └── SEMIANALYSIS_PIPELINE_GUIDE.md  # Primary reference
```

### Option B: Consolidate All SA Files

```
scripts/
├── semianalysis/                     # NEW: Dedicated SA folder
│   ├── pipeline/
│   │   ├── semianalysis_pipeline.py  # Main pipeline
│   │   ├── validate_sa_ingestion.py  # Validation
│   │   └── ingest_semianalysis_v2.py # GDB ingestion
│   ├── config/
│   │   └── config.py                 # SA-specific config
│   ├── docs/
│   │   ├── SEMIANALYSIS_PIPELINE_GUIDE.md
│   │   └── DATA_RELATIONSHIP_INVESTIGATION.md
│   └── _archive/
│       ├── investigation/
│       ├── superseded/
│       └── debug/
```

---

## Recommended Actions

### Phase 1: Immediate Cleanup (Low Risk)

1. **Create `_utils/_sa_archive/` folder structure**
   ```
   _sa_archive/
   ├── investigation/    # Scripts used for one-time investigations
   ├── superseded/       # Scripts replaced by unified pipeline
   └── debug/            # One-time debugging scripts
   ```

2. **Move 32 temporary/superseded scripts to archive**
   - Investigation scripts → `_sa_archive/investigation/`
   - Superseded extract/clean scripts → `_sa_archive/superseded/`
   - Debug scripts → `_sa_archive/debug/`

3. **Keep 6 active scripts in `_utils/`**
   - `semianalysis_pipeline.py`
   - `validate_sa_ingestion.py`
   - `config.py`
   - `gdrive_export.py`
   - `date_helpers.py`
   - `PIPELINE_CHANGELOG.md`

### Phase 2: Documentation Consolidation

1. **Update SEMIANALYSIS_PIPELINE_GUIDE.md** (already done today)
   - ✅ Fixed bugs documented
   - ✅ Tenant attribution model documented
   - ✅ Output formats documented

2. **Create quick-reference card**
   - Single-page summary of pipeline usage
   - Input/output file locations
   - Common troubleshooting

### Phase 3: Optional Future Improvements

1. **Consider dedicated `semianalysis/` folder** (Option B)
   - Only if SA becomes a larger subsystem
   - Would require updating import paths

2. **Add unit tests for pipeline functions**
   - Test extraction functions
   - Test merge logic
   - Test output validation

---

## Files to Archive (32 total)

### Investigation Scripts (12 files) → `_sa_archive/investigation/`
```
analyze_sa_duplicates.py
analyze_semianalysis_deep.py
analyze_semianalysis_excel.py
analyze_sheet_overlap.py
check_hyperscaler_duplicates.py
check_source_overlap.py
check_source_overlap_v2.py
find_ai_labs_uuids.py
investigate_half_pattern.py
investigate_hyperscaler_overlap.py
test_semianalysis_capacity_relationships.py
test_semianalysis_raw_vs_gold.py
```

### Superseded Scripts (7 files) → `_sa_archive/superseded/`
```
clean_semianalysis_excel.py
combine_sa_extracts.py
extract_sa_ai_labs.py
extract_sa_na.py
extract_sa_overseas.py
merge_sa_duplicates.py
add_semianalysis_v2_fields.py
```

### Debug Scripts (13 files) → `_sa_archive/debug/`
```
analyze_col_columns.py
analyze_output.py
check_building_fields.py
check_dup_coords.py
check_record_levels.py
check_sa_year_fields.py
check_semianalysis_headers.py
check_semianalysis_meta.py
debug_sa_dates.py
diagnose_essential_matching.py
diagnose_sa_structure.py
diagnose_sa_ucids.py
diagnose_year_fields.py
explore_essential_list.py
patch_semianalysis_planned_plus_uc.py
show_output_summary.py
verify_fix.py
verify_output_columns.py
```

---

## Final Active SA Pipeline Files

After consolidation, these files will remain active:

### Core Pipeline (`_utils/`)
| File | Lines | Purpose |
|------|-------|---------|
| semianalysis_pipeline.py | ~2,265 | Complete extraction, cleaning, export |
| validate_sa_ingestion.py | ~200 | Post-ingestion validation |
| config.py | ~50 | Shared configuration |
| gdrive_export.py | ~100 | Google Drive export |
| date_helpers.py | ~50 | Date utilities |
| PIPELINE_CHANGELOG.md | ~100 | Change history |

### Ingestion (`01_ingestion/`)
| File | Lines | Purpose |
|------|-------|---------|
| ingest_semianalysis_v2.py | ~300 | GDB ingestion from pipeline CSV |

### Documentation (`00_docs/workflows/`)
| File | Purpose |
|------|---------|
| SEMIANALYSIS_PIPELINE_GUIDE.md | Complete reference guide |
| PIPELINE_EXECUTION_ORDER.md | Execution sequence |

---

## Implementation Script

To execute the consolidation, run:

```powershell
# Create archive folders
$archiveBase = "c:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\scripts\_utils\_sa_archive"
New-Item -ItemType Directory -Force -Path "$archiveBase\investigation"
New-Item -ItemType Directory -Force -Path "$archiveBase\superseded"
New-Item -ItemType Directory -Force -Path "$archiveBase\debug"

# Move investigation scripts
$investigation = @(
    "analyze_sa_duplicates.py",
    "analyze_semianalysis_deep.py",
    "analyze_semianalysis_excel.py",
    "analyze_sheet_overlap.py",
    "check_hyperscaler_duplicates.py",
    "check_source_overlap.py",
    "check_source_overlap_v2.py",
    "find_ai_labs_uuids.py",
    "investigate_half_pattern.py",
    "investigate_hyperscaler_overlap.py"
)
foreach ($f in $investigation) {
    Move-Item "scripts\_utils\$f" "$archiveBase\investigation\" -Force
}

# Move superseded scripts
$superseded = @(
    "clean_semianalysis_excel.py",
    "combine_sa_extracts.py",
    "extract_sa_ai_labs.py",
    "extract_sa_na.py",
    "extract_sa_overseas.py",
    "merge_sa_duplicates.py"
)
foreach ($f in $superseded) {
    Move-Item "scripts\_utils\$f" "$archiveBase\superseded\" -Force
}

# Move debug scripts
$debug = @(
    "analyze_col_columns.py",
    "analyze_output.py",
    "check_building_fields.py",
    "check_dup_coords.py",
    "check_record_levels.py",
    "check_sa_year_fields.py",
    "debug_sa_dates.py",
    "diagnose_essential_matching.py",
    "diagnose_sa_structure.py",
    "diagnose_sa_ucids.py",
    "diagnose_year_fields.py",
    "explore_essential_list.py",
    "show_output_summary.py",
    "verify_fix.py",
    "verify_output_columns.py"
)
foreach ($f in $debug) {
    Move-Item "scripts\_utils\$f" "$archiveBase\debug\" -Force
}
```

---

*Document created: January 27, 2026*
*Author: GIS Data Team*
