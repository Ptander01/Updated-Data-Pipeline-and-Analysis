# Feature Backlog: Data Vintage Tracking & Delta Analysis

**Status:** 📋 Backlog  
**Priority:** Medium  
**Created:** 2026-01-20  
**Requested By:** P. Anderson  

---

## Problem Statement

Currently, the data pipeline overwrites all records on each run. There is no automated way to:
- Track how data changes between ingestion runs
- Identify new/removed/modified records over time
- Analyze trends in capacity, status changes, or source coverage
- Audit data quality improvements across vintages

---

## Proposed Solution: Pipeline Delta Tracking

### Phase 1: Metrics Snapshot (Quick Win)

**Effort:** Low (1-2 hours)  
**Approach:** Extend existing pipeline diagnostic to save metrics JSON after each run

```
scripts/
├── 00_docs/
│   └── reports/
│       └── pipeline_metrics/          # NEW
│           ├── metrics_20260120.json
│           ├── metrics_20260115.json
│           └── ...
```

**Metrics to capture per run:**
```json
{
  "run_date": "2026-01-20T22:45:00Z",
  "record_counts": {
    "gold_buildings": 32500,
    "gold_campus": 4200,
    "gold_combined_xb": 36700
  },
  "by_source": {
    "DCHyper": 8500,
    "DCHLease": 3200,
    "SemiAnalysis": 12000,
    "DCM": 4500,
    "NewProjectMedia": 2800,
    "Synergy": 1500
  },
  "by_status": {
    "Active": 18000,
    "Under Construction": 5500,
    "Announced": 7000,
    "Planned": 2000
  },
  "capacity_totals": {
    "commissioned_mw": 45000,
    "uc_power_mw": 12000,
    "planned_power_mw": 28000,
    "full_capacity_mw": 85000
  },
  "data_vintage_range": {
    "oldest": "2024-06-15",
    "newest": "2026-01-15"
  }
}
```

**Delta Report Output:**
```
=== PIPELINE DELTA REPORT (2026-01-20 vs 2026-01-15) ===

RECORD CHANGES:
  gold_buildings: +127 records (32,373 → 32,500)
  gold_campus: +15 records (4,185 → 4,200)

BY SOURCE:
  NewProjectMedia: +89 records (new NPM_DC_1_15_2026 ingestion)
  DCHyper: +38 records
  SemiAnalysis: unchanged

CAPACITY CHANGES:
  commissioned_mw: +450 MW (+1.0%)
  uc_power_mw: +1,200 MW (+10.0%)
  planned_power_mw: +2,500 MW (+8.9%)

STATUS TRANSITIONS:
  Under Construction → Active: 12 campuses
  Announced → Under Construction: 8 campuses
```

---

### Phase 2: Record-Level Change Detection (Medium Effort)

**Effort:** Medium (4-6 hours)  
**Approach:** Compare current vs previous GeoJSON exports

**Script:** `scripts/04_analysis/compare_vintages.py`

```python
# Pseudocode
def compare_vintages(current_geojson, previous_geojson):
    current = load_features(current_geojson)
    previous = load_features(previous_geojson)
    
    # Match by unique_id
    new_records = current.keys() - previous.keys()
    removed_records = previous.keys() - current.keys()
    
    # For matching records, compare key fields
    changed_records = []
    for uid in current.keys() & previous.keys():
        if fields_changed(current[uid], previous[uid]):
            changed_records.append({
                'unique_id': uid,
                'changes': diff_fields(current[uid], previous[uid])
            })
    
    return {
        'new': new_records,
        'removed': removed_records,
        'changed': changed_records
    }
```

**Key fields to track for changes:**
- `facility_status` (status transitions)
- `full_capacity_mw`, `uc_power_mw`, `planned_power_mw` (capacity updates)
- `company_clean` (ownership changes)
- `data_vintage` (source freshness)

---

### Phase 3: Historical Snapshot Table (Higher Effort)

**Effort:** High (8-12 hours)  
**Approach:** Append-only history table with batch tracking

**New tables:**
- `gold_buildings_history` - Full record snapshots with `ingest_batch_id`
- `pipeline_runs` - Metadata for each pipeline execution

**Schema additions:**
```python
# gold_buildings_history
('ingest_batch_id', 'TEXT', 36),    # UUID for each pipeline run
('record_action', 'TEXT', 10),      # 'INSERT', 'UPDATE', 'DELETE'
('previous_batch_id', 'TEXT', 36),  # Link to prior version
```

**Benefits:**
- Full audit trail of all changes
- Time-travel queries ("show me this campus as of 2025-12-01")
- Trend analysis across any time range

**Tradeoffs:**
- Significant storage increase (~10x over time)
- More complex queries for current state
- Requires cleanup/archival strategy

---

## Implementation Plan

| Phase | Deliverable | Effort | Dependencies |
|-------|-------------|--------|--------------|
| 1 | Metrics snapshot JSON + delta report | 1-2 hrs | None |
| 2 | Record-level comparison script | 4-6 hrs | Phase 1 |
| 3 | History table + batch tracking | 8-12 hrs | Phase 2 |

---

## Files to Create/Modify

### Phase 1
- [ ] `scripts/04_analysis/save_pipeline_metrics.py` - NEW
- [ ] `scripts/04_analysis/generate_delta_report.py` - NEW
- [ ] Integrate into existing pipeline run workflow

### Phase 2
- [ ] `scripts/04_analysis/compare_vintages.py` - NEW
- [ ] `web_dashboard/08_web_export/` - Archive previous exports before overwriting

### Phase 3
- [ ] `scripts/_utils/config.py` - Add history table paths
- [ ] `scripts/02_processing/` - Modify ingestion to append to history
- [ ] `scripts/04_analysis/query_history.py` - NEW

---

## Notes

- Phase 1 provides 80% of the value with 20% of the effort
- Consider adding metrics to web dashboard for visual trend analysis
- GeoJSON archive could use dated filenames: `combined_20260120.geojson`

---

## Related

- Pipeline diagnostic reports: `scripts/00_docs/reports/pipeline_diagnostics/`
- Data vintage field added in v2.0 schema
- `ingest_date` field tracks when records were processed
