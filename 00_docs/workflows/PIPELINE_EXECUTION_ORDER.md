# Pipeline Execution Order

This document defines the correct order of operations for the Data Center Consensus GIS pipeline.

**Last Updated:** January 14, 2026

---

## Complete Pipeline (Fresh Start)

Run these steps in order when starting from scratch:

```
┌─────────────────────────────────────────────────────────────────────┐
│                    COMPLETE PIPELINE ORDER                          │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  1. INGEST RAW DATA                                                │
│     └─→ Raw CSVs → gold_buildings_full                             │
│         • ingest_dch.py                                            │
│         • ingest_dch_lease.py                                      │
│         • ingest_semianalysis.py                                   │
│         • ingest_dcm.py                                            │
│         • ingest_npm.py                                            │
│         • ingest_meta_canonical.py                                 │
│                                                                     │
│  2. GEOGRAPHY ENRICHMENT                                            │
│     └─→ Enrich region, state, state_abbr from lookups             │
│         • enrich_geography_fields.py                               │
│         (Fills region from country, state_abbr from state)         │
│                                                                     │
│  3. COMPANY STANDARDIZATION                                         │
│     └─→ Populate company_clean and company_clean_filter            │
│         • migrate_company_fields_v2.py                             │
│         (REQUIRED before UCID - clustering uses company_clean)     │
│                                                                     │
│  4. UCID GENERATION (ON BUILDINGS)                                  │
│     └─→ Spatial clustering + UCID assignment to buildings          │
│         • generate_text_ucid.py                                    │
│         (Assigns ucid and building_ucid to gold_buildings_full)    │
│                                                                     │
│  5. ESSENTIAL DC FLAG                                               │
│     └─→ Flag 127 strategic buildings from curated Essential list  │
│         • integrate_essential_by_uid.py                            │
│         (Sets is_essential=1 for curated Semianalysis sites)       │
│                                                                     │
│  6. CAMPUS ROLLUP (GROUPS BY UCID)                                  │
│     └─→ Aggregate buildings → gold_campus_full                     │
│         • campus_rollup_new.py                                     │
│         (Groups by UCID, rolls up is_essential via MAX)            │
│                                                                     │
│  7. CLEANUP GOLD CAMPUS                                             │
│     └─→ Populate lat/lon from geometry, verify ucid                │
│         • cleanup_gold_campus.py                                   │
│         (REQUIRED after rollup - rollup truncates table)           │
│                                                                     │
│  8. CREATE COMBINED XB LAYER                                        │
│     └─→ Combine buildings + campuses for Experience Builder        │
│         • create_xb_combined_layer.py                              │
│         (Creates gold_combined_xb with 41 unified fields)          │
│                                                                     │
│  9. VALIDATION                                                      │
│     └─→ Verify data quality                                        │
│         • validate_granularity.py                                  │
│         • torture_test_gold_datasets.py                            │
│                                                                     │
│ 10. DIAGNOSTIC REPORT                                               │
│     └─→ Generate pipeline health report                            │
│         • generate_pipeline_report.py                              │
│         (Outputs HTML report to 00_docs/reports/pipeline_diagnostics)│
│                                                                     │
│ 11. WEB DASHBOARD EXPORT (Optional)                                 │
│     └─→ Export GeoJSON for web dashboard                           │
│         • export_to_geojson.py                                     │
│         (Exports to web_dashboard/data/*.geojson)                  │
│         ⚠️ After export: Visit http://localhost:8000/api/reload    │
│            OR restart backend server to refresh cache              │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Quick Reference Commands

### Full Pipeline (ArcGIS Pro Python Window)

```python
# Step 1: Ingest all sources
exec(open(r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\scripts\01_ingestion\ingest_dch.py", encoding='utf-8').read())
exec(open(r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\scripts\01_ingestion\ingest_dch_lease.py", encoding='utf-8').read())
exec(open(r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\scripts\01_ingestion\ingest_semianalysis.py", encoding='utf-8').read())
exec(open(r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\scripts\01_ingestion\ingest_dcm.py", encoding='utf-8').read())
exec(open(r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\scripts\01_ingestion\ingest_npm.py", encoding='utf-8').read())
exec(open(r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\scripts\01_ingestion\ingest_meta_canonical.py", encoding='utf-8').read())

# Step 2: Geography enrichment
exec(open(r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\scripts\02_processing\enrich_geography_fields.py", encoding='utf-8').read())

# Step 3: Company standardization
exec(open(r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\scripts\02_processing\migrate_company_fields_v2.py", encoding='utf-8').read())

# Step 4: UCID generation (BEFORE campus rollup!)
exec(open(r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\scripts\03_ucid\generate_text_ucid.py", encoding='utf-8').read())

# Step 5: Essential DC Flag (127 strategic buildings)
exec(open(r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\scripts\02_processing\integrate_essential_by_uid.py", encoding='utf-8').read())

# Step 6: Campus rollup (groups by UCID, rolls up is_essential)
exec(open(r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\scripts\02_processing\campus_rollup_new.py", encoding='utf-8').read())

# Step 7: Cleanup gold_campus (lat/lon from geometry)
exec(open(r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\scripts\02_processing\cleanup_gold_campus.py", encoding='utf-8').read())

# Step 8: Create XB combined layer
exec(open(r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\scripts\06_visualization\create_xb_combined_layer.py", encoding='utf-8').read())

# Step 9: Validation
exec(open(r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\scripts\04_validation\core\validate_granularity.py", encoding='utf-8').read())

# Step 10: Diagnostic report
exec(open(r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\scripts\04_validation\reports\generate_pipeline_report.py", encoding='utf-8').read())
```

---

## Semianalysis V2 Pipeline (New Excel Model)

When you receive a new Semianalysis Excel file (AI Data Center Model), use the unified pipeline:

```
┌─────────────────────────────────────────────────────────────────────┐
│                SEMIANALYSIS V2 PIPELINE                             │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  1. UPDATE INPUT FILE PATH                                          │
│     └─→ Edit semianalysis_pipeline.py                              │
│         • Set INPUT_FILE to the new Excel file location            │
│         • Verify sheet coordinates haven't changed (check manually)│
│                                                                     │
│  2. RUN UNIFIED PIPELINE                                            │
│     └─→ Extracts, combines, merges, and exports                    │
│         • semianalysis_pipeline.py                                 │
│         (Handles duplicate columns, merges same-site phases)       │
│                                                                     │
│  3. UPDATE INGESTION SCRIPT                                         │
│     └─→ Point to new cleaned CSV                                   │
│         • Edit ingest_semianalysis_v2.py SOURCE_CSV path           │
│         • Update to semianalysis_FINAL_YYYYMMDD_HHMM.csv           │
│                                                                     │
│  4. RUN INGESTION                                                   │
│     └─→ Loads cleaned data into geodatabase                        │
│         • ingest_semianalysis_v2.py                                │
│         (Auto-deletes old SA records, auto-runs validation)        │
│                                                                     │
│  5. VERIFY WITH VALIDATION (Auto-runs after ingestion)              │
│     └─→ Confirms field population matches CSV                      │
│         • validate_sa_ingestion.py                                 │
│         (All year fields should show ✓ OK status)                  │
│                                                                     │
│  6. CONTINUE STANDARD PIPELINE (Steps 2-10)                         │
│     └─→ Company standardization, UCID, Campus rollup, etc.         │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### Semianalysis Excel Structure (December 2026 Version)

| Sheet | UUID Rows | Header Rows | Records | Notes |
|-------|-----------|-------------|---------|-------|
| NA Data Center Supply | 19-5001 | 3-4 | ~3,085 | Primary US/Canada data |
| Overseas Data Center Supply | 21-1440 | 3-4 | ~714 | EMEA/APAC data |
| AI Labs - OpenAI, Anthropic etc | 80-382 | 3-4 | ~270 | Enrichment layer (99% overlap) |

**Key Columns:** A (UUID), H-AA (basic info), BV-CG (location), CL-CZ (AI enrichment)

**Duplicate Handling:**
- Same UUID at same lat/long = phases at same site → **SUM capacity values**
- AI Labs records mostly overlap NA/Overseas → **Merge to enrich with AI fields**

**Year-over-Year MW Fields (mw_2023-mw_2032):**
- Pipeline normalizes pandas column naming ('2023.0' → '2023')
- Merges duplicate year columns (takes positive values)
- Expected population: 47% (2023) → 95% (2032)

### Quick Reference Commands

```python
# Step 1: Run unified pipeline (extraction + merge)
exec(open(r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\scripts\_utils\semianalysis_pipeline.py", encoding='utf-8').read())

# Step 2: Run ingestion (includes validation)
exec(open(r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\scripts\01_ingestion\ingest_semianalysis_v2.py", encoding='utf-8').read())

# Optional: Run validation separately
exec(open(r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\scripts\_utils\validate_sa_ingestion.py", encoding='utf-8').read())
```

---

## Incremental Refresh (New Source Data)

When you receive updated data from a vendor (e.g., new Semianalysis export):

```
┌─────────────────────────────────────────────────────────────────────┐
│                    INCREMENTAL REFRESH                              │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  1. RE-INGEST SOURCE (Auto-deletes old records first!)             │
│     └─→ Run the specific ingestion script                          │
│         • For Semianalysis: Use V2 pipeline above                  │
│         • For others: Run the specific ingest_*.py script          │
│         (Script automatically cleans up existing records)          │
│                                                                     │
│  2. COMPANY STANDARDIZATION                                         │
│     └─→ Re-run to catch new company names                          │
│         • migrate_company_fields_v2.py                             │
│                                                                     │
│  3. UCID GENERATION                                                 │
│     └─→ Re-cluster and assign UCIDs to buildings                   │
│         • generate_text_ucid.py                                    │
│         (Overwrites existing ucid values)                          │
│                                                                     │
│  4. CAMPUS ROLLUP                                                   │
│     └─→ Recreate campus aggregations (grouped by UCID)             │
│         • campus_rollup_new.py                                     │
│                                                                     │
│  5. CLEANUP GOLD CAMPUS                                             │
│     └─→ Populate lat/lon from geometry                             │
│         • cleanup_gold_campus.py                                   │
│                                                                     │
│  6. RECREATE XB COMBINED LAYER                                      │
│     └─→ Rebuild combined layer with updated data                   │
│         • create_xb_combined_layer.py                              │
│                                                                     │
│  7. VALIDATION & REPORT                                             │
│     └─→ Verify results and generate diagnostic report              │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Key Points

### Clean Re-ingestion
- Each ingestion script **automatically deletes** existing records from its source before inserting
- You'll see `[CLEANUP] Checking for existing {source} records...` when running
- Safe to re-run any script multiple times
- The `data_vintage` field is populated for all sources

### DCH Scripts Use unique_id Prefix
Both DCH Hyper and DCH Lease use `source = 'DataCenterHawk'`, differentiated by unique_id prefix:

| Script | Deletes Records Where |
|--------|----------------------|
| `ingest_dch.py` | `unique_id LIKE 'DCH_%' AND NOT LIKE 'DCH_L_%'` |
| `ingest_dch_lease.py` | `unique_id LIKE 'DCH_L_%'` |

### UCID Generation is Idempotent
- The script **overwrites** existing `ucid` and `building_ucid` values
- No need to delete fields or records before running
- Safe to run multiple times

### Company Standardization Must Run Before UCID
- UCID clusters by `company_clean` (distinct names)
- If company_clean contains "Colo - All Other", you'll get false merges
- Always run `migrate_company_fields_v2.py` before UCID generation

### Campus Rollup Uses UCID
- Groups by `ucid` (source-agnostic, spatial clustering)
- Creates ONE campus record per physical location
- All sources for the same location are merged together

### Cleanup Must Run After Rollup
- Campus rollup **truncates** gold_campus_full and rebuilds it
- This wipes lat/lon values populated earlier
- Always run `cleanup_gold_campus.py` after `campus_rollup_new.py`

### XB Combined Layer is the Final Output
- Combines buildings + campuses into single layer (gold_combined_xb)
- 50 unified fields for Experience Builder filtering
- Use `record_level` field to filter ("Building" or "Campus")

---

## Current Record Counts

| Layer | Records |
|-------|---------|
| gold_buildings_full | **20,941** |
| gold_campus_full | **11,347** |
| gold_combined_xb | **32,288** |
| Essential Buildings | **127** |
| Essential Campuses | **79** |

---

## Related Documentation

| Document | Purpose |
|----------|---------|
| `PIPELINE_DOCUMENTATION.md` | Comprehensive technical documentation and changelog |
| `AI_CONTEXT_PROMPT.md` | Context for AI coding sessions |
| `REPORT_OUTPUT_SOP.md` | How to share and distribute reports |

---

*For detailed technical documentation, scripts reference, and changelog, see `PIPELINE_DOCUMENTATION.md`*
