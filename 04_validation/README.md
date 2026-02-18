# Validation Scripts

This folder contains data quality validation scripts for the Data Center Consensus GIS Model pipeline. Run these after ingestion to ensure data integrity.

---

## 📋 Script Reference

### Meta Canonical Validation (New - Jan 30, 2026)

| Script | Purpose | When to Use |
|--------|---------|-------------|
| `validate_meta_canonical.py` | **Comprehensive data quality validation** | Before running full pipeline with new Meta data |
| `diagnose_meta_canonical_schema.py` | Schema diagnostic (fields, geometry, coordinates) | Debug coordinate/field issues |
| `create_filtered_meta_canonical.py` | Create filtered dataset excluding placeholders | After validation, before pipeline |

### Core Pipeline Validation (Run Every Time)

| Script | Purpose | When to Use |
|--------|---------|-------------|
| `validate_gold_buildings_data.py` | Validate gold_buildings data quality | **Run after every ingestion** |
| `validate_canonical_integrity.py` | Validate Meta canonical data integrity | After loading/updating Meta data |
| `validate_gold_build_schema.py` | Check gold_buildings schema compliance | After schema changes |

### Coordinate Validation

| Script | Purpose | When to Use |
|--------|---------|-------------|
| `validate_coordinate_independence.py` | Check if sources share coordinates | **Run with new data** to verify source independence |
| `compare_raw_source_coordinates.py` | Compare raw source FC coordinates | Debug coordinate issues at source level |

### Data Quality Audits

| Script | Purpose | When to Use |
|--------|---------|-------------|
| `gold_buildings_audit.py` | Comprehensive external data audit | Periodic data quality review |
| `attribute_accuracy_audit.py` | Audit attribute accuracy | After major data updates |

### Data Fixes

| Script | Purpose | When to Use |
|--------|---------|-------------|
| `fix_companies.py` | Standardize company names | After ingestion if company names need cleanup |
| `fix_regions.py` | Fix region field values | After ingestion if region values invalid |

---

## 🔄 Meta Canonical Validation Workflow (New Jan 2026)

When receiving a new Meta Canonical CSV export from DAI, run this validation workflow:

```python
# 1. Import new CSV (creates meta_canonical_v2)
exec(open(r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\scripts\01_ingestion\import_meta_canonical_v3.py", encoding='utf-8').read())

# 2. Run comprehensive data quality validation
exec(open(r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\scripts\04_validation\validate_meta_canonical.py", encoding='utf-8').read())

# 3. If issues found, run schema diagnostic
exec(open(r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\scripts\04_validation\diagnose_meta_canonical_schema.py", encoding='utf-8').read())

# 4. Create filtered dataset (excludes placeholder records)
exec(open(r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\scripts\04_validation\create_filtered_meta_canonical.py", encoding='utf-8').read())

# 5. Run deduplication on filtered data (suite → building)
exec(open(r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\scripts\02_processing\meta_deduplicate.py", encoding='utf-8').read())

# 6. Ingest to gold_buildings_full
exec(open(r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\scripts\01_ingestion\ingest_meta_canonical.py", encoding='utf-8').read())
```

### Quality Thresholds

| Check | Threshold | Flag |
|-------|-----------|------|
| Null Status Rate | >50% | ❌ RED |
| Null Capacity Rate | >50% | ❌ RED |
| Coordinate Coverage | <50% | ⚠️ YELLOW |
| Future/Unknown Capacity | >80% | ❌ RED |

### Recommendation Logic

- **🛑 RED - HOLD**: 2+ critical issues → Investigate DAI query
- **⚠️ YELLOW - INVESTIGATE**: 1 critical issue → Review data source
- **⚠️ YELLOW - CAUTION**: 2+ yellow flags → Proceed with documented gaps
- **✅ GREEN - PROCEED**: Data quality acceptable

---

## 🔄 Recommended Validation Workflow (General)

After loading new data, run these scripts in order:

```bash
# 1. Validate gold_buildings structure and required fields
python validate_gold_buildings_data.py

# 2. Validate Meta canonical data
python validate_canonical_integrity.py

# 3. Check coordinate independence between sources
python validate_coordinate_independence.py

# 4. Run comprehensive audit
python gold_buildings_audit.py
```

---

## 📊 Key Findings (Jan 30, 2026)

### Meta Canonical Data Quality

| Metric | Full Dataset | Filtered Dataset |
|--------|--------------|------------------|
| Total Records | 3,400 suites | 1,320 suites |
| Capacity | 17,230 MW | 17,230 MW (100%) |
| With Status | 33% | 84% |
| With Coordinates | 68% | 82% |
| Buildings (after dedup) | ~643 | ~400-450 |

### Why Records Have NULL Values

The source table `idc_schedule_udm_consumption_table` contains multiple records per site for:
- Development milestones
- Phase gates
- Activity statuses

The DAI query aggregates using `GROUP BY location_key` with `MAX()` for dates/status.
Records with NULL `new_build_status` or `it_load` represent:
- **Early-stage sites** — Planned but not in active development
- **Land acquisitions** — Secured but no building specs
- **Placeholder records** — Future expansion entries

### Coordinate Independence Check
- **81.7% of coordinates are identical** between DCH and Semianalysis
- This reflects **industry-wide multi-sourcing patterns** (per supervisor)
- Both vendors subscribe to overlapping 3P data sources
- NOT a bug in our pipeline

---

## 📁 Related Diagnostic Scripts

See `05_accuracy/_diagnostics/` for investigation scripts:
- `audit_capacity_by_source.py` — Capacity data availability
- `investigate_dch_granularity.py` — DCH building vs campus analysis
- `test_dch_pue_adjustment.py` — PUE factor testing

---

*Last Updated: January 30, 2026*
