# 📁 Script Reorganization Plan — Data Center Consensus GIS Model

**Created:** January 5, 2026
**Status:** 🔄 PENDING APPROVAL
**Total Scripts Audited:** 89 files across 12 directories

---

## 📊 Executive Summary

After auditing your entire Scripts folder, I've identified:

| Category | Count | Action |
|----------|-------|--------|
| **Active Pipeline Scripts** | 27 | ✅ KEEP (organize better) |
| **Utility/Maintenance Scripts** | 24 | ✅ KEEP (consolidate) |
| **One-Time Migration Scripts** | 12 | 📦 MOVE to `_archive/migrations/` |
| **Obsolete/Deprecated Scripts** | 14 | 📦 ARCHIVE |
| **Duplicate/Broken Scripts** | 2 | 🗑️ DELETE |
| **Documentation Files** | 28+ | ✅ KEEP (organize by type) |

---

## 🚨 Critical Issues Identified

### 1. **Duplicate Folder Numbering**
```
06_consensus/   ← Both numbered "06"
06_ucid/        ← Confusing!
```

### 2. **Helper Functions Duplicated in 9+ Scripts**
- `slugify()`, `generate_campus_id()`, `parse_mw_string()` copied into each ingestion script
- Should be imported from `_utils/helper_scripts.py` instead

### 3. **Broken/Incomplete Scripts in Archive**
- `ETL Script.py` — Truncated mid-code
- `campus_level_deep_dive_export.py` — Entire file duplicated (lines 1-477 repeated)

### 4. **Orphaned Utility Scripts**
- `_utils/fix_dch_record_level.py` — One-time fix
- `_utils/import_meta_canonical.py` — Superseded by ingestion script
- `_utils/strip_bom.py` — One-time encoding fix

---

## 🏗️ Proposed New Folder Structure

### Current Structure
```
scripts/
├── 00_docs/                    # Documentation (28 files - cluttered)
├── 01_ingestion/               # Data ingestion (10 scripts)
├── 02_processing/              # Transform & aggregate (17 scripts - many one-time)
├── 03_spatial_join/            # Spatial accuracy (1 script)
├── 04_validation/              # Validation (30 scripts - very cluttered!)
├── 05_accuracy_analysis/       # Accuracy reports (14 scripts)
├── 06_consensus/               # Deduplication (3 scripts) ← DUPLICATE NUMBER
├── 06_ucid/                    # UCID generation (7 scripts) ← DUPLICATE NUMBER
├── 07_visualization/           # Charts/maps (3 scripts)
├── _archive/                   # Archived scripts (6 scripts)
├── _utils/                     # Utilities (8 files - mixed)
├── outputs/                    # Output files
└── run_full_pipeline.py        # Master pipeline script
```

### Proposed New Structure
```
scripts/
├── 00_docs/                    # Documentation
│   ├── context/                # AI context prompts, session logs
│   ├── schemas/                # Schema definitions, comparisons
│   ├── workflows/              # Pipeline documentation
│   └── reports/                # Generated HTML reports
│
├── 01_ingestion/               # Data ingestion (ACTIVE ONLY)
│   ├── ingest_dch.py
│   ├── ingest_dch_lease.py
│   ├── ingest_semianalysis.py
│   ├── ingest_dcm.py
│   ├── ingest_npm.py
│   └── ingest_meta_canonical.py
│
├── 02_processing/              # Transform & aggregate
│   ├── campus_rollup_new.py    # Main rollup
│   ├── cleanup_gold_campus.py  # Post-rollup cleanup
│   ├── migrate_company_fields_v2.py  # Company standardization
│   └── meta_deduplicate.py     # Meta suite→building
│
├── 03_ucid/                    # UCID generation (RENUMBERED from 06)
│   ├── generate_text_ucid.py
│   ├── analyze_ucid_confidence.py
│   └── README.md
│
├── 04_validation/              # Validation & QA (CONSOLIDATED)
│   ├── core/                   # Core validation scripts
│   │   ├── validate_granularity.py
│   │   ├── validate_canonical_integrity.py
│   │   └── torture_test_gold_datasets.py
│   ├── diagnostics/            # Ad-hoc diagnostic scripts
│   │   ├── check_semianalysis_headers.py
│   │   ├── diagnose_bad_city_values.py
│   │   └── ...
│   ├── reports/                # Report generators
│   │   └── generate_pipeline_report.py
│   └── fixes/                  # Data quality fix scripts
│       ├── fix_data_quality_issues.py
│       ├── fix_companies.py
│       └── fix_regions.py
│
├── 05_accuracy/                # Accuracy analysis (RENAMED)
│   ├── comprehensive_spatial_accuracy_report.py
│   ├── capacity_accuracy_analysis_v2.py
│   └── _diagnostics/           # Keep as-is
│
├── 06_visualization/           # Charts & layers (RENUMBERED from 07)
│   ├── create_xb_combined_layer.py
│   ├── generate_capacity_presentation_charts.py
│   └── plot_spatial_accuracy_LIGHT_THEME.py
│
├── _archive/                   # Archived scripts (REORGANIZED)
│   ├── migrations/             # One-time schema migrations
│   │   ├── migrate_campus_id_to_ucid.py
│   │   ├── migrate_schema_v2.py
│   │   ├── run_schema_v2_migration.py
│   │   └── remove_legacy_fields.py
│   ├── ingestion/              # Deprecated ingestion scripts
│   │   ├── import_raw_excel_to_gdb.py
│   │   ├── ingest_synergy.py
│   │   ├── ingest_woodmac.py
│   │   └── reimport_semianalysis.py
│   ├── processing/             # Deprecated processing scripts
│   │   ├── campus_rollup_meta_canonical.py
│   │   ├── geocode_woodmac.py
│   │   ├── extract_woodmac_coords.py
│   │   └── init_full_data_fcs.py
│   ├── validation/             # Deprecated validation scripts
│   │   ├── unified_accuracy_analysis.py  # Broken (duplicate code)
│   │   └── ... (various one-time audits)
│   ├── obsolete/               # Dead code (can be deleted)
│   │   ├── ETL Script.py
│   │   └── campus_level_deep_dive_export.py
│   └── README.md               # Archive documentation
│
├── _utils/                     # Utilities (CLEANED)
│   ├── config.py               # ✅ CRITICAL - Keep
│   ├── helper_scripts.py       # ✅ Consolidate duplicates here
│   └── load_helpers.py         # ✅ Interactive console helpers
│
├── outputs/                    # Output files
└── run_full_pipeline.py        # Master pipeline script
```

---

## 📋 Detailed Script Disposition

### 01_ingestion/ — Keep 6, Archive 4

| Script | Status | Action |
|--------|--------|--------|
| `ingest_dch.py` | ✅ Active | KEEP |
| `ingest_dch_lease.py` | ✅ Active | KEEP |
| `ingest_semianalysis.py` | ✅ Active | KEEP |
| `ingest_dcm.py` | ✅ Active | KEEP |
| `ingest_npm.py` | ✅ Active | KEEP |
| `ingest_meta_canonical.py` | ✅ Active | KEEP |
| `import_raw_excel_to_gdb.py` | ⚠️ One-time | → `_archive/ingestion/` |
| `ingest_synergy.py` | ❌ Excluded (no coords) | → `_archive/ingestion/` |
| `ingest_woodmac.py` | ❌ Excluded (manual geocode) | → `_archive/ingestion/` |
| `reimport_semianalysis.py` | ⚠️ Utility | → `_archive/ingestion/` |

---

### 02_processing/ — Keep 5, Archive 12

| Script | Status | Action |
|--------|--------|--------|
| `campus_rollup_new.py` | ✅ Active (Step 4) | KEEP |
| `cleanup_gold_campus.py` | ✅ Active (Step 5) | KEEP |
| `migrate_company_fields_v2.py` | ✅ Active (Step 2) | KEEP |
| `meta_deduplicate.py` | ✅ Active | KEEP |
| `enrich_geography_fields.py` | ✅ Utility | KEEP |
| `campus_rollup_meta_canonical.py` | ❌ Superseded | → `_archive/processing/` |
| `export_schema.py` | ⚠️ Utility | → `_archive/processing/` |
| `extract_woodmac_coords.py` | ❌ WoodMac excluded | → `_archive/processing/` |
| `geocode_woodmac.py` | ❌ WoodMac excluded | → `_archive/processing/` |
| `import_meta_canonical_v2.py` | ⚠️ One-time | → `_archive/processing/` |
| `init_full_data_fcs.py` | ⚠️ One-time | → `_archive/processing/` |
| `migrate_campus_id_to_ucid.py` | ⚠️ One-time migration | → `_archive/migrations/` |
| `migrate_schema_v2.py` | ⚠️ One-time migration | → `_archive/migrations/` |
| `populate_latlon_from_geometry.py` | ⚠️ Utility | KEEP (maintenance) |
| `recreate_gold_buildings.py` | ⚠️ Emergency utility | KEEP (recovery) |
| `remove_legacy_fields.py` | ⚠️ One-time migration | → `_archive/migrations/` |
| `run_schema_v2_migration.py` | ⚠️ One-time migration | → `_archive/migrations/` |

---

### 03_spatial_join/ — MERGE into 05_accuracy/

| Script | Status | Action |
|--------|--------|--------|
| `multi_source_spatial_accuracy.py` | ✅ Active | → `05_accuracy/` |

**Rationale:** Only 1 script. Merge with accuracy analysis folder.

---

### 04_validation/ — Major Cleanup Needed (30 → ~15)

#### KEEP in 04_validation/core/
| Script | Purpose |
|--------|---------|
| `validate_granularity.py` | Core validation |
| `validate_canonical_integrity.py` | Meta canonical checks |
| `torture_test_gold_datasets.py` | Comprehensive validation |
| `validate_gold_buildings_data.py` | Data integrity |
| `validate_gold_build_schema.py` | Schema validation |
| `validate_coordinate_independence.py` | Coordinate checks |

#### KEEP in 04_validation/reports/
| Script | Purpose |
|--------|---------|
| `generate_pipeline_report.py` | HTML diagnostic dashboard |
| `full_data_source_audit.py` | Source audit report |
| `analyze_capacity_coverage.py` | Capacity coverage report |

#### KEEP in 04_validation/fixes/
| Script | Purpose |
|--------|---------|
| `fix_data_quality_issues.py` | Multi-issue fixer |
| `fix_companies.py` | Company name fixes |
| `fix_regions.py` | Region standardization |
| `patch_semianalysis_planned_plus_uc.py` | Semianalysis patch |
| `standardize_company_names.py` | Company standardization |

#### MOVE to 04_validation/diagnostics/
| Script | Purpose |
|--------|---------|
| `audit_company_names.py` | One-time audit |
| `audit_raw_tables_v2_fields.py` | Schema audit |
| `check_semianalysis_headers.py` | Header check |
| `check_semianalysis_meta.py` | Meta comparison |
| `compare_raw_source_coordinates.py` | Coordinate comparison |
| `deep_dive_campus_validation.py` | Deep analysis |
| `diagnose_bad_city_values.py` | City value check |
| `gold_buildings_audit.py` | Building audit |
| `investigate_duplicate_buildings.py` | Duplicate check |
| `schema_check.py` | Schema check |
| `test_semianalysis_capacity_relationships.py` | Capacity test |
| `test_semianalysis_raw_vs_gold.py` | Raw vs gold test |
| `verify_no_duplicate_buildings.py` | Duplicate verification |
| `attribute_accuracy_audit.py` | Attribute audit |

#### ARCHIVE
| Script | Reason |
|--------|--------|
| `apple_dark_theme.css` | CSS file, not validation |
| `README.md` | Keep but update |

---

### 05_accuracy_analysis/ — Keep structure, minor cleanup

| Script | Status | Action |
|--------|--------|--------|
| `capacity_accuracy_analysis_v2.py` | ✅ Active | KEEP |
| `capacity_variance_experiments.py` | ⚠️ Experimental | KEEP |
| `capacity_variance_experiments_all_sources.py` | ✅ Active | KEEP |
| `comprehensive_spatial_accuracy_report.py` | ✅ Active | KEEP |
| `unified_accuracy_analysis.py` | ❌ Broken (duplicate code) | → `_archive/validation/` |
| `_diagnostics/*` | ⚠️ Mixed | KEEP subfolder as-is |

---

### 06_consensus/ — Renumber to 04b or merge

| Script | Status | Action |
|--------|--------|--------|
| `consensus_dedupe.py` | ⚠️ Unclear if used | Investigate |
| `spatial_clustering.py` | ⚠️ Unclear if used | Investigate |
| `validate_clusters.py` | ⚠️ Unclear if used | Investigate |

**Note:** These scripts don't appear in `run_full_pipeline.py`. May be experimental or superseded by UCID approach.

---

### 06_ucid/ — Renumber to 03_ucid/

| Script | Status | Action |
|--------|--------|--------|
| `generate_text_ucid.py` | ✅ Active (Step 3) | KEEP |
| `analyze_ucid_confidence.py` | ⚠️ Utility | KEEP |
| `assign_ucid_to_gold.py` | ⚠️ One-time? | Investigate |
| `generate_ucid_clusters.py` | ⚠️ Experimental | KEEP |
| `ucid_intake_matcher.py` | ⚠️ Utility | KEEP |
| `validate_ucid_comparison.py` | ⚠️ Utility | KEEP |
| `README.md` | ✅ Excellent | KEEP |

---

### 07_visualization/ — Renumber to 06_visualization/

All scripts are active. Just renumber folder.

---

### _archive/ — Clean up

| Script | Status | Action |
|--------|--------|--------|
| `ETL Script.py` | ❌ Incomplete/broken | DELETE or → `_archive/obsolete/` |
| `campus_level_deep_dive_export.py` | ❌ Broken (duplicate code) | DELETE or → `_archive/obsolete/` |
| `diagnose_new_canonical_v2.py` | ⚠️ Template | → `_archive/validation/` |
| `granularity_spatial_stats_enhanced.py` | ⚠️ Template | → `_archive/validation/` |
| `qa_region_country.py` | ⚠️ One-time fix | → `_archive/validation/` |
| `test_scripts.py` | ⚠️ Dev tool | → `_utils/` |

---

### _utils/ — Clean up

| File | Status | Action |
|------|--------|--------|
| `config.py` | ✅ CRITICAL | KEEP (heavily used) |
| `helper_scripts.py` | ⚠️ Not imported | REFACTOR (9+ duplicates exist) |
| `load_helpers.py` | ⚠️ Interactive | KEEP (document as interactive-only) |
| `fix_dch_record_level.py` | ❌ One-time | → `_archive/processing/` |
| `import_meta_canonical.py` | ❌ Superseded | → `_archive/ingestion/` |
| `strip_bom.py` | ❌ One-time | → `_archive/` or DELETE |
| `copy_to_fbsource.ps1` | ⚠️ Deployment | KEEP (but document) |

---

### 00_docs/ — Organize by type

#### Create subfolders:
```
00_docs/
├── context/
│   ├── AI_CONTEXT_PROMPT.md
│   └── SESSION_LOG.md
│
├── schemas/
│   ├── CAPACITY_CONCEPTS_DIAGRAM.md
│   ├── CAPACITY_FIELD_DEFINITIONS.md
│   ├── SCHEMA_CLARIFICATIONS_RESPONSE.md
│   ├── SCHEMA_COMPARISON_ANALYSIS.md
│   ├── SCHEMA_COMPARISON_ANALYSIS_DARK.html
│   ├── SCHEMA_COMPARISON_VISUAL.md
│   ├── SCHEMA_COMPARISON_VISUAL_DARK.html
│   └── UCID_VISUAL_SUMMARY.md
│
├── workflows/
│   ├── PIPELINE_DOCUMENTATION.md
│   ├── PIPELINE_EXECUTION_ORDER.md
│   ├── GRANULARITY_STRATEGY.md
│   ├── META_CANONICAL_WORKFLOW.md
│   ├── UCID_DESIGN.md
│   └── V2_INGESTION_AUDIT_TASKS.md
│
├── reports/
│   ├── PIPELINE_DIAGNOSTIC_*.html (8 files)
│   ├── PROGRESS_UPDATE_DEC30.html
│   ├── PROGRESS_UPDATE_JAN02.html
│   └── PROJECT_OVERVIEW.html
│
└── archive/
    └── SCRIPT_AUDIT_AND_REORG.md
```

---

## ✅ Recommended Execution Order

### Phase 1: Create Archive Structure (Low Risk)
1. Create `_archive/migrations/`
2. Create `_archive/ingestion/`
3. Create `_archive/processing/`
4. Create `_archive/validation/`
5. Create `_archive/obsolete/`

### Phase 2: Move Deprecated Scripts (Medium Risk)
1. Move one-time migration scripts
2. Move excluded ingestion scripts (Synergy, WoodMac)
3. Move superseded processing scripts

### Phase 3: Renumber Folders (Higher Risk)
1. Rename `06_ucid/` → `03_ucid/`
2. Rename `07_visualization/` → `06_visualization/`
3. Update `run_full_pipeline.py` paths
4. Update `PIPELINE_EXECUTION_ORDER.md`
5. Update `AI_CONTEXT_PROMPT.md`

### Phase 4: Reorganize Validation (Medium Risk)
1. Create subfolders in `04_validation/`
2. Move scripts to appropriate subfolders
3. Update any script references

### Phase 5: Organize Documentation
1. Create subfolders in `00_docs/`
2. Move files to appropriate subfolders

---

## ⚠️ Before Proceeding

**Please confirm:**
1. Do you want me to execute this reorganization?
2. Should I preserve the current structure as a backup first?
3. Any specific scripts you want to keep in their current location?
4. Should I delete the truly broken scripts (`ETL Script.py`, `campus_level_deep_dive_export.py`) or just archive them?

---

## 📎 Quick Reference: Active Pipeline Scripts

These are the **only scripts needed** for the production pipeline:

```python
# run_full_pipeline.py calls these in order:
01_ingestion/ingest_dch.py           # Step 1a
01_ingestion/ingest_dch_lease.py     # Step 1b
01_ingestion/ingest_semianalysis.py  # Step 1c
01_ingestion/ingest_dcm.py           # Step 1d
01_ingestion/ingest_npm.py           # Step 1e
01_ingestion/ingest_meta_canonical.py # Step 1f
02_processing/migrate_company_fields_v2.py  # Step 2
06_ucid/generate_text_ucid.py        # Step 3 (→ 03_ucid/)
02_processing/campus_rollup_new.py   # Step 4
02_processing/cleanup_gold_campus.py # Step 5
07_visualization/create_xb_combined_layer.py  # Step 6 (→ 06_visualization/)
04_validation/generate_pipeline_report.py     # Step 7 (optional)
```

**Everything else is either a utility, one-time migration, or archived.**

---

*Plan created by: AI Assistant*
*Awaiting approval before execution*
