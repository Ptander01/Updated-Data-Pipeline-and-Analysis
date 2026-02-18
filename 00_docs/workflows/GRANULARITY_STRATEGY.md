# 📊 Granularity Strategy — Data Center Consensus GIS Model

**Last Updated:** December 16, 2025
**Purpose:** Ensure accurate record_level assignments and prevent data misappropriation
**Status:** ✅ COMPLETE - 22,376 buildings ingested, 15,904 campuses derived

---

## 🎯 Core Principle

| Feature Class | Contains | record_level |
|---------------|----------|--------------|
| `gold_buildings_full` | Individual building/facility records | `Building` |
| `gold_campus_full` | Aggregated campus records (derived from buildings) | `Campus` |

**CRITICAL RULE:** `gold_campus` is DERIVED from `gold_buildings` via the campus rollup process. Do NOT directly insert campus-level source data into `gold_buildings`.

---

## 📋 Source Granularity Reference

| Source | Raw Table(s) | Native Granularity | Target FC | Records | Handling |
|--------|--------------|-------------------|-----------|---------|----------|
| **DCH Hyper** | `dch_hyper_raw` | Building | gold_buildings | 1,876 | ✅ Complete |
| **DCH Lease** | `dch_lease_raw` | Building | gold_buildings | 5,176 | ✅ Complete |
| **Semianalysis** | `semianalysis_raw` | Building | gold_buildings | 5,472 | ✅ Complete (Field1-43 mapping) |
| **DataCenterMap** | `dcm_raw` | Mixed | gold_buildings | 8,453 | ✅ Complete (table→points) |
| **NPM** | `npm_raw` | Project | gold_buildings | 1,399 | ✅ Complete (Lat_Lon_X/Y) |
| **Synergy** | `synergy_raw` | Facility | ❌ N/A | 956 | ⏭️ Skipped - no coordinates |
| **WoodMac DC** | `woodmac_dc_raw` | Dev Phase | ❌ EXCLUDED | 280 | Validation only (see below) |
| **WoodMac Campus** | `woodmac_campus_raw` | Future Build-out | ❌ EXCLUDED | 216 | Validation only (see below) |

---

## ⚠️ WoodMac Data: EXCLUDED from gold_buildings (Validation Only)

**Decision Date:** December 15, 2025
**Status:** ✅ RESOLVED - WoodMac excluded from main pipeline

### Why WoodMac is Different

Per WoodMac documentation, their data model tracks **development phases**, not physical buildings:

| WoodMac Term | Their Definition | Our Equivalent |
|--------------|------------------|----------------|
| **Data Center** | A development phase (e.g., "Phase 1: 20 MW") | ≠ Building |
| **Campus** | Full build-out projection (future state) | ≠ Current Campus |
| **Project ID** | Groups multiple phases of same project | N/A |

**Key Issues:**
1. Multiple DC rows can represent phases of the SAME physical project (same Project ID)
2. Campus MW **double-counts** associated DC MW
3. Campus represents FUTURE full build-out, not current state
4. Fundamentally incompatible with building-level inventory model

### Decision: Validation Layer Only

WoodMac data is **EXCLUDED** from `gold_buildings` and `gold_campus`. Instead:

```
WoodMac Raw Data
      ↓
geocode_woodmac.py → WoodMac_ToGeocode tables
      ↓
ArcGIS Pro Geocode Addresses (manual)
      ↓
WoodMac_Geocoded feature classes (491 records)
      ↓
extract_woodmac_coords.py → woodmac_coords (reference table)
      ↓
❌ NOT ingested into gold_buildings
      ↓
✅ Use for: Timeline validation, capacity comparison, pipeline tracking
```

### WoodMac Data Assets (For Reference/Validation)

| Asset | Records | Purpose |
|-------|---------|---------|
| `woodmac_campus_raw` | 216 | Raw campus data (cleaned) |
| `woodmac_dc_raw` | 280 | Raw DC phase data (cleaned) |
| `WoodMac_Campus_Geocoded` | 216 | Geocoded campus locations |
| `WoodMac_DC_Geocoded` | 275 | Geocoded DC phase locations |
| `woodmac_coords` | 491 | Combined coordinates lookup |

### Use Cases for WoodMac Data

1. **Timeline Validation:** Compare announced/COD dates to other sources
2. **Capacity Validation:** Cross-check MW estimates with DCH/Semianalysis
3. **Pipeline Analysis:** Track what's under construction vs announced
4. **Geographic Coverage:** Validate location accuracy of other sources

### Scripts Affected

- `ingest_woodmac.py` — **REMOVED from main pipeline** (do not run)
- `geocode_woodmac.py` — Still useful for geocoding WoodMac data
- `extract_woodmac_coords.py` — Creates reference coords table

---

## 🔍 Validation Workflow

### Pre-Ingestion (BEFORE running ingestion scripts)

```python
# In ArcGIS Pro Python window
exec(open(r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\scripts\04_validation\validate_granularity.py").read())

# Or manually:
from validate_granularity import run_full_validation
results = run_full_validation(mode='pre')
```

This will:
1. Audit all raw tables for granularity indicators
2. Flag WoodMac Campus gap
3. Identify any unexpected field patterns

### Post-Ingestion (AFTER running ingestion scripts)

```python
from validate_granularity import run_full_validation
results = run_full_validation(mode='post')
```

This will:
1. Check record_level distribution by source
2. Flag any Campus records incorrectly in gold_buildings
3. Validate campus derivation (gold_campus derived from gold_buildings)
4. Detect cross-source duplicates

---

## 📊 record_level Logic by Script

### ingest_dch.py
```python
def derive_record_level(facility_type, name):
    if facility_type and 'campus' in str(facility_type).lower():
        return 'Campus'
    if name and 'campus' in str(name).lower():
        return 'Campus'
    return 'Building'  # DCH default
```
**Assessment:** ✅ Good - defaults to Building, flags Campus exceptions

### ingest_semianalysis.py
```python
record_level = 'Building'  # Hardcoded
```
**Assessment:** ✅ Correct - Semianalysis cluster field has building numbers

### ingest_dcm.py
```python
def derive_record_level(name, parent_id):
    if " - Building" in name:
        return "Building"
    if parent_id and parent_id != 0:
        return "Building"
    return "Campus"
```
**Assessment:** ⚠️ Review - May flag some records as Campus that go into gold_buildings

### ingest_npm.py
```python
record_level = 'Building'  # Hardcoded
```
**Assessment:** ⚠️ Review - NPM projects may be campus-level announcements

### ingest_synergy.py
```python
record_level = 'Building'  # Hardcoded
```
**Assessment:** ⚠️ Unclear - Synergy reports facility counts, granularity uncertain

### ingest_woodmac.py
```python
record_level = 'Building'  # Hardcoded - from woodmac_dc_raw
```
**Assessment:** ✅ Correct - Only reads from DC table, not Campus table

---

## 🛡️ Data Protection Checklist

### Before Ingestion
- [ ] Run `validate_granularity.py` with `mode='pre'`
- [ ] Confirm WoodMac Campus handling decision
- [ ] Verify `gold_buildings_full` is empty (or backed up)
- [ ] Verify `gold_campus_full` is empty (or backed up)

### After Ingestion
- [ ] Run `validate_granularity.py` with `mode='post'`
- [ ] Check: 0 Campus records in gold_buildings
- [ ] Check: All record_level values are 'Building'
- [ ] Run campus_rollup.py to populate gold_campus

### Before Campus Rollup
- [ ] Confirm all building ingestion is complete
- [ ] Verify gold_campus will be truncated (not appended)

### After Campus Rollup
- [ ] Run `validate_granularity.py` with `mode='post'`
- [ ] Verify gold_campus count matches unique campus_ids in gold_buildings
- [ ] Check source field shows combined sources per campus

---

## 📊 Final Record Counts (December 16, 2025)

| Feature Class | Records | Notes |
|---------------|---------|-------|
| `gold_buildings_full` | **22,376** | All building records from 5 sources |
| `gold_campus_full` | **15,904** | Unique campuses after rollup |

### Breakdown by Source (Buildings)

| Source | Records | record_level | Status |
|--------|----------|--------------|--------|
| DataCenterMap | 8,453 | Mixed → Building | ✅ Complete |
| DataCenterHawk Lease | 5,176 | Building | ✅ Complete |
| Semianalysis | 5,472 | Building | ✅ Complete |
| DataCenterHawk Hyper | 1,876 | Building | ✅ Complete |
| NewProjectMedia | 1,399 | Building | ✅ Complete |
| **Synergy** | 956 | - | ⏭️ Skipped (no coords) |
| **WoodMac** | 496 | Dev Phase | ❌ **EXCLUDED** |

---

## 🔧 Remediation Procedures

### If Campus Records Found in gold_buildings

```python
# Option 1: Delete and re-ingest
arcpy.management.SelectLayerByAttribute(
    GOLD_BUILDINGS,
    "NEW_SELECTION",
    "record_level = 'Campus'"
)
arcpy.management.DeleteRows(GOLD_BUILDINGS)

# Option 2: Move to gold_campus (if valid)
# Requires custom script
```

### If Buildings Missing from Campus Rollup

```python
# Re-run campus rollup
exec(open(r"...\02_processing\campus_rollup_new.py").read())
```

---

*Document Version: 2.0 — December 16, 2025 (Full Data Pipeline Complete)*
