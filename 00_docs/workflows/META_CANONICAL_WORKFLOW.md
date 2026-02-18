# 📋 Meta Canonical Data Workflow

**Last Updated:** February 10, 2026
**Status:** ✅ Complete - Building & Campus level processing with Unlocated Capacity support

---

## 📤 Quick Export for Coworkers

Need a **flat file** of the Meta canonical dataset? See:
- **Export README:** `C:\Users\ptanderson\Downloads\meta_canonical_buildings_README.md`
- **Export CSV:** `C:\Users\ptanderson\Downloads\meta_canonical_buildings.csv`

### Full vs. Filtered Dataset

| Dataset | Buildings | With Coords | Without Coords | Use Case |
|---------|-----------|-------------|----------------|----------|
| **Full** (`meta_canonical_v2`) | 643 | 368 | 275 | Complete inventory including placeholders |
| **Filtered** (`meta_canonical_v2_filtered`) | 340 | 267 | 73 | Active sites with capacity or build status |

The flat file export uses the **FILTERED** dataset (340 buildings, 17,230 MW).

---

## 🎯 Overview

Meta Canonical represents **Meta's internal authoritative data** on our global data center footprint. This data flows from internal DAI queries and serves two purposes:

1. **Ground Truth for Validation** — Compare external vendor estimates against what we actually know
2. **Unified Analysis** — Include Meta's internal view alongside vendor data in Experience Builder

### January 2026 Update

**Major changes in this update:**
- New CSV format from DAI query (3,400 suites → 643 buildings)
- **"Unlocated Campus Capacity"** record type for buildings without coordinates
- Mirrors how SemiAnalysis handles TLBM (Total Lease By Market) records
- Preserves all 17+ GW of Meta capacity while distinguishing spatial vs non-spatial

---

## 📊 Data Source Query

### Source Table
**Hive Table:** `idc_schedule_udm_consumption_table`

### Important: Source Data Structure

The source Hive table contains **multiple records per site** based on development milestones, phase gates, and activity statuses. A single data center location may have 10-50+ rows tracking its lifecycle from planning through completion.

### DAI Query - Aggregation Strategy

The data pull aggregates to **one record per `location_key`** using:

```sql
SELECT
    location_key,
    datacenter,
    region,
    address,
    latitude,
    longitude,
    building_type,
    new_build_status,
    it_load,
    MAX(milestone_date) AS latest_milestone_date,
    MAX(dc_phase_gate) AS latest_phase_gate,
    MAX(activity_status) AS latest_activity_status
FROM idc_schedule_udm_consumption_table
WHERE
    ds = '<LATEST_DS:idc_schedule_udm_consumption_table:infrastructure>'
    AND is_current_record = TRUE
GROUP BY
    location_key,
    datacenter,
    region,
    address,
    latitude,
    longitude,
    building_type,
    new_build_status,
    it_load
ORDER BY
    datacenter ASC
```

### Key Query Elements:

| Element | Purpose |
|---------|---------|
| `GROUP BY location_key` | Ensures one record per suite/location |
| `MAX(milestone_date)` | Gets the most recent milestone date |
| `MAX(dc_phase_gate)` | Gets the latest phase gate achieved |
| `MAX(activity_status)` | Gets the current activity status |
| `is_current_record = TRUE` | Filters to only active records (not historical) |
| `ds = '<LATEST_DS:...>'` | Uses most recent data partition |

### Why Some Records Have NULL Values

Records with NULL `new_build_status` or `it_load` may represent:
- **Early-stage sites** — Planned but not yet in active development
- **Land acquisitions** — Secured but no building specs yet
- **Administrative records** — Placeholder entries for future expansion

### Data Quality Metrics (January 2026)

| Metric | Count | Percentage |
|--------|-------|------------|
| Total Suites | 3,400 | 100% |
| With Build Status | 1,106 | 33% |
| With IT Load | 1,145 | 34% |
| With Coordinates | 2,327 | 68% |

### Filtered Dataset for Pipeline

For pipeline processing, use `meta_canonical_v2_filtered` which includes only records where:
- `it_load > 0` **OR**
- `new_build_status IS NOT NULL`

This yields **~1,320 suites** → **340 buildings** with **17.2 GW** of capacity (100% of populated capacity).

```python
# Create filtered dataset
exec(open(r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\scripts\04_validation\create_filtered_meta_canonical.py", encoding='utf-8').read())
```

---

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         META CANONICAL DATA FLOW                             │
│                            (January 2026)                                    │
└─────────────────────────────────────────────────────────────────────────────┘

    DAI Query Export (CSV)
    Meta_Authoritative_Raw.csv
    (3,400 suite-level records)
             │
             │  import_meta_canonical_v3.py
             │  • Change analysis vs existing data
             │  • Generates change report
             ▼
      ┌──────────────────┐
      │ meta_canonical_v2│  ← Suite-level records (3,400 suites)
      │   (Suite Level)  │    ~2,327 with coords, ~1,073 without
      └────────┬─────────┘
               │
               │  meta_deduplicate.py
               │  • Creates building_key (dc_code + datacenter)
               │  • Aggregates suites → buildings
               │  • Maps building_type → owned_leased
               ▼
      ┌──────────────────────┐
      │meta_canonical_buildings│  ← Building-level (643 buildings)
      │   (Building Level)     │    ~368 with coords, ~275 without
      └────────┬───────────────┘
               │
               ├────────────────────────────────────┐
               │                                    │
               │  campus_rollup_meta_canonical.py   │  ingest_meta_canonical.py
               ▼                                    ▼
      ┌────────────────────┐              ┌────────────────────┐
      │meta_canonical_campus│              │ gold_buildings_full │
      │  (Campus Level)     │              │  source="Meta       │
      │  STANDALONE         │              │  Canonical"         │
      └─────────────────────┘              │                     │
                                           │  record_level:      │
                                           │  • "Building" (368) │
                                           │  • "Unlocated Campus│
                                           │    Capacity" (275)  │
                                           └──────────┬──────────┘
                                                      │
                                                      │  campus_rollup_new.py
                                                      ▼
                                           ┌────────────────────┐
                                           │  gold_campus_full   │
                                           │  source="Meta       │
                                           │  Canonical"         │
                                           └─────────────────────┘

─────────────────────────────────────────────────────────────────────────────
 STANDALONE LAYERS              │        INTEGRATED LAYERS
 (Ground Truth)                 │        (Unified Analysis)
```

---

## 📁 Feature Classes

### Standalone (Authoritative Reference)

| Feature Class | Level | Records | Purpose |
|---------------|-------|---------|---------|
| `meta_canonical_v2` | Suite | 3,400 | Raw import from DAI query |
| `meta_canonical_buildings` | Building | 643 | Deduplicated, building-level |
| `meta_canonical_campus` | Campus | ~120 | Aggregated by dc_code |

### Integrated (Unified Gold Tables)

| Feature Class | Level | Meta Records | Purpose |
|---------------|-------|--------------|---------|
| `gold_buildings_full` | Building | 643 | Unified with vendor data, `source = "Meta Canonical"` |
| `gold_campus_full` | Campus | ~120 | Auto-aggregated by campus_rollup_new.py |

### Record Level Types (in gold_buildings_full)

| record_level | Count | Capacity | Description |
|--------------|-------|----------|-------------|
| `Building` | ~368 | ~12,848 MW | Located buildings with valid coordinates |
| `Unlocated` | ~275 | ~4,382 MW | Aggregate capacity for campuses without coordinates |

> **Note:** The value "Unlocated" is used instead of "Unlocated Campus Capacity" due to field length constraints in `gold_buildings_full`. This is similar to how SemiAnalysis uses short codes like "TLBM" for "Total Lease By Market".

---

## 📈 Capacity Summary (January 2026)

| Category | Buildings | Capacity (MW) | % of Total |
|----------|-----------|---------------|------------|
| **With Coordinates** | 368 | 12,848 | 75% |
| **Without Coordinates** | 275 | 4,382 | 25% |
| **TOTAL** | 643 | 17,230 | 100% |

### Regional Distribution

| Region | Campuses | Buildings | IT Load (MW) |
|--------|----------|-----------|--------------|
| AMER | ~85 | ~450 | ~14,000 |
| EMEA | ~15 | ~80 | ~2,000 |
| APAC | ~5 | ~30 | ~800 |
| UNKNOWN (no coords) | ~114 | ~275 | ~4,382 |

### Owned vs Leased

| Type | Suites | Buildings (est.) |
|------|--------|------------------|
| Owned | 1,912 | ~400 |
| Leased | 1,302 | ~230 |
| NULL | 186 | ~13 |

---

## 🔧 Scripts

### 1. Import Raw CSV (New V3)

**Script:** `01_ingestion/import_meta_canonical_v3.py`

```python
exec(open(r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\scripts\01_ingestion\import_meta_canonical_v3.py", encoding='utf-8').read())
```

**What it does:**
1. Loads new CSV format (Jan 2026 structure)
2. **Performs change analysis** vs existing meta_canonical_v2 data:
   - Added/removed locations
   - Status changes
   - IT load changes
   - Building type changes
3. Derives region (AMER/EMEA/APAC) from coordinates
4. Maps `region` column → `dc_code` (it's actually datacenter code, not region)
5. **Generates change report** in `scripts/00_docs/reports/`

**Input:** `C:\Users\ptanderson\Downloads\Meta_Authoritative_Raw.csv`
**Output:** `meta_canonical_v2` (3,400 suite records)

**CSV Columns (Jan 2026 format):**
- `location_key` - Unique suite identifier (e.g., UCO0D)
- `datacenter` - Building number (e.g., 0, 1, 2)
- `region` - Actually dc_code (e.g., UCO, RPL, LCO)
- `address` - Street address (often empty for no-coord records)
- `latitude`, `longitude` - Coordinates
- `building_type` - own/lease
- `new_build_status` - Active Build, Complete Build, Future Build
- `it_load` - IT capacity in MW
- `latest_milestone_date` - Date of latest milestone
- `latest_phase_gate` - Phase gate status
- `latest_activity_status` - Activity status

---

### 2. Suite → Building Deduplication

**Script:** `02_processing/meta_deduplicate.py`

```python
exec(open(r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\scripts\02_processing\meta_deduplicate.py", encoding='utf-8').read())
```

**What it does:**
1. Creates `building_key` = `{dc_code}-{datacenter}` (e.g., "ATN-1")
2. Dissolves suites by building_key (MULTI_PART for buildings with multiple coords)
3. Aggregates: `SUM(it_load)`, `FIRST(region)`, `FIRST(build_status)`
4. Maps `building_type` → normalized `owned_leased` field
5. Tracks `has_coordinates` (MAX - if any suite has coords, building gets 1)

**Output:** `meta_canonical_buildings` (643 buildings)

---

### 3. Building → Campus Rollup (Standalone)

**Script:** `02_processing/campus_rollup_meta_canonical.py`

```python
exec(open(r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\scripts\02_processing\campus_rollup_meta_canonical.py", encoding='utf-8').read())
```

**What it does:**
1. Aggregates buildings by `dc_code`
2. Calculates: building_count, suite_count, it_load by status
3. Counts owned vs leased buildings
4. Creates centroid from building coordinates

**Output:** `meta_canonical_campus` (~120 campuses)

---

### 4. Ingest to Gold Tables

**Script:** `01_ingestion/ingest_meta_canonical.py`

```python
exec(open(r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\scripts\01_ingestion\ingest_meta_canonical.py", encoding='utf-8').read())
```

**What it does:**
1. Reads `meta_canonical_buildings`
2. Maps to gold_buildings schema
3. Inserts with `source = "Meta Canonical"`
4. **NEW:** Sets `record_level` based on coordinate availability:
   - `"Building"` for records with valid coordinates
   - `"Unlocated Campus Capacity"` for records without coordinates
5. Maps build_status → capacity fields (commissioned/UC/planned)

**Output:** 643 records added to `gold_buildings_full`
- ~368 as "Building" (located)
- ~275 as "Unlocated Campus Capacity" (unlocated)

---

### 5. Campus Rollup (Integrated)

**Script:** `02_processing/campus_rollup_new.py`

After running `ingest_meta_canonical.py`, re-run the main campus rollup:

```python
exec(open(r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\scripts\02_processing\campus_rollup_new.py", encoding='utf-8').read())
```

This automatically includes Meta Canonical in `gold_campus_full` with source tracking.

---

## 📋 Complete Workflow

### Full Refresh (with new CSV)

```python
# 1. Import new CSV + analyze changes
exec(open(r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\scripts\01_ingestion\import_meta_canonical_v3.py", encoding='utf-8').read())

# 2. Suite → Building deduplication
exec(open(r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\scripts\02_processing\meta_deduplicate.py", encoding='utf-8').read())

# 3. Create standalone campus rollup (authoritative reference)
exec(open(r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\scripts\02_processing\campus_rollup_meta_canonical.py", encoding='utf-8').read())

# 4. Ingest to gold_buildings_full (with record_level assignment)
exec(open(r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\scripts\01_ingestion\ingest_meta_canonical.py", encoding='utf-8').read())

# 5. Re-run main campus rollup (includes Meta Canonical in gold_campus_full)
exec(open(r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\scripts\02_processing\campus_rollup_new.py", encoding='utf-8').read())
```

### Quick Copy-Paste Version

```python
# Full Meta Canonical refresh workflow
exec(open(r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\scripts\01_ingestion\import_meta_canonical_v3.py", encoding='utf-8').read())
exec(open(r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\scripts\02_processing\meta_deduplicate.py", encoding='utf-8').read())
exec(open(r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\scripts\02_processing\campus_rollup_meta_canonical.py", encoding='utf-8').read())
exec(open(r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\scripts\01_ingestion\ingest_meta_canonical.py", encoding='utf-8').read())
exec(open(r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\scripts\02_processing\campus_rollup_new.py", encoding='utf-8').read())
```

---

## 📊 Field Mapping

### meta_canonical_v2 → meta_canonical_buildings

| Source Field | Target Field | Aggregation |
|--------------|--------------|-------------|
| `dc_code` + `datacenter` | `building_key` | Concatenate |
| `dc_code` | `dc_code` | FIRST |
| `datacenter` | `datacenter` | FIRST |
| `location_key` | `suite_count` | COUNT |
| `region` (original) | `dc_code` | Renamed |
| Derived from coords | `region_derived` | AMER/EMEA/APAC |
| `new_build_status` | `new_build_status` | FIRST |
| `it_load` | `it_load_total` | SUM |
| `building_type` | `owned_leased` | Mapped ("Own"→"Owned", "Lease"→"Leased") |
| `has_coordinates` | `has_coordinates` | MAX |

### meta_canonical_buildings → gold_buildings_full

| Source Field | Target Field | Notes |
|--------------|--------------|-------|
| `building_key` | `unique_id` | Prefixed: `MetaCanonical_{building_key}` |
| — | `source` | "Meta Canonical" |
| `building_key` | `source_unique_id` | Original key |
| `dc_code` | `campus_id` | Format: `meta\|{region}\|{dc_code}` |
| `dc_code` | `campus_name` | "Meta {dc_code}" |
| — | `company_clean` | "Meta" |
| — | `company_source` | "Meta" |
| `datacenter` | `building_designation` | Building number |
| `region_derived` | `region` | AMER/EMEA/APAC |
| `it_load_total` | `*_power_mw` | Mapped by status (see below) |
| `owned_leased` | `owned_leased` | Direct copy |
| — | `type_category` | "Hyperscale" |
| Derived from coords | `record_level` | "Building" or "Unlocated Campus Capacity" |

### Capacity Mapping by Build Status

| Build Status | commissioned_power_mw | uc_power_mw | planned_power_mw |
|--------------|----------------------|-------------|------------------|
| Complete Build | it_load_total | 0 | 0 |
| Active Build | 0 | it_load_total | 0 |
| Future Build | 0 | 0 | it_load_total |
| NULL/Unknown | it_load_total | 0 | 0 |

### Record Level Assignment

| Condition | record_level | Notes |
|-----------|--------------|-------|
| Valid lat/lon (not 0,0) | `"Building"` | Spatial record, shown on map |
| No coordinates or null island | `"Unlocated Campus Capacity"` | Non-spatial aggregate, like SA's TLBM |

---

## 🔍 Unlocated Campus Capacity

### What is "Unlocated Campus Capacity"?

Similar to how SemiAnalysis uses **"Total Lease By Market" (TLBM)** records for market-level aggregates without specific building locations, Meta Canonical now uses **"Unlocated Campus Capacity"** for:

- Campuses/buildings that exist in internal planning systems
- Future sites where coordinates aren't yet finalized
- Sites where location data is confidential or pending

### Why This Matters

| Scenario | Without This | With This |
|----------|--------------|-----------|
| Company-level capacity totals | Missing 4.4 GW (25%) | Full 17.2 GW captured |
| Spatial analysis | Full 17.2 GW (inflated) | Only 12.8 GW (accurate) |
| Market comparisons | Incomplete | Can filter by record_level |

### Querying by Record Level

```sql
-- Total Meta capacity (all records)
SELECT SUM(full_capacity_mw)
FROM gold_buildings_full
WHERE source = 'Meta Canonical';

-- Spatial capacity only (for mapping)
SELECT SUM(full_capacity_mw)
FROM gold_buildings_full
WHERE source = 'Meta Canonical' AND record_level = 'Building';

-- Unlocated capacity (aggregate only)
SELECT SUM(full_capacity_mw)
FROM gold_buildings_full
WHERE source = 'Meta Canonical' AND record_level = 'Unlocated Campus Capacity';
```

### Unknown Campuses (No Coordinates Anywhere)

114 dc_codes have no coordinates in any of their suites. These are likely:

- **NA30-NA60 series** — North American future sites
- **NO31-NO82 series** — New planned campuses
- **TXB, TXG, TXH, TXJ, TXK** — Texas expansion sites
- **NB1, NB2** — "New Build" sites

Top capacity in unknown campuses:

| Campus | Suites | Capacity (MW) |
|--------|--------|---------------|
| NB1 | 32 | 720 |
| SMS | 6 | 319 |
| SBN | 6 | 319 |
| CMS | 32 | 312 |
| CMV | 9 | 291 |

---

## 🔍 Validation Scripts

### Verify No Duplicate Buildings

```python
exec(open(r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\scripts\04_validation\verify_no_duplicate_buildings.py", encoding='utf-8').read())
```

### Deep Dive Campus Validation (Compare to Vendor Data)

```python
exec(open(r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\scripts\04_validation\deep_dive_campus_validation.py", encoding='utf-8').read())
```

This script compares Meta canonical IT load against external vendor estimates for accuracy benchmarking.

---

## ❓ Why Keep Both Standalone and Integrated?

### Standalone Layers (`meta_canonical_*`)

✅ **Clean ground truth** — Not mixed with vendor noise
✅ **Direct comparison** — Easy to query "what do we actually know?"
✅ **Internal reporting** — Meta-only footprint analysis
✅ **Validation reference** — Benchmark vendor accuracy

### Integrated Layers (`gold_*_full`)

✅ **Unified view** — All sources in one table
✅ **Experience Builder** — Single layer for filtering by source
✅ **Cross-source comparison** — See Meta vs vendors side-by-side
✅ **Automatic aggregation** — Campus rollup works for all sources

---

## 📝 Key Decisions

1. **Source label:** `"Meta Canonical"` (clear distinction from vendor sources)
2. **Campus ID format:** `meta|{region}|{dc_code}` (e.g., `meta|amer|atn`)
3. **Include buildings without coordinates:** Yes (275 buildings as "Unlocated Campus Capacity")
4. **Owned/Leased normalization:** "Own" → "Owned", "Lease/Colo" → "Leased"
5. **Duplicate handling:** MULTI_PART dissolve (buildings with multiple suite locations)
6. **Unlocated capacity:** Use `record_level = "Unlocated Campus Capacity"` (similar to SA TLBM)

---

## 📊 Version History

### January 2026 (V3)

| Metric | Dec 2025 | Jan 2026 | Change |
|--------|----------|----------|--------|
| Suites | 1,218 | 3,400 | +179% |
| Buildings | 318 | 643 | +102% |
| Campuses | ~70 | ~120 | +71% |
| Total IT Load | ~2,500 MW | ~17,230 MW | +589% |
| With Coordinates | 276 | 368 | +33% |
| Without Coordinates | 42 | 275 | +555% |

**New Features:**
- Change analysis on import
- "Unlocated Campus Capacity" record type
- Change report generation

### December 2025 (V2)

- Initial building-level processing
- Added owned_leased field mapping
- Included buildings without coordinates (42)

---

## 🚨 Troubleshooting

### Import Fails with Unicode Error

If you see `'unicodeescape' codec can't decode bytes`:
- Check CSV path uses forward slashes or escaped backslashes
- Ensure the CSV file is UTF-8 encoded

### Missing Columns in New CSV

The Jan 2026 CSV format has different columns than the Nov 2025 format:
- Old: `suite`, `dc_design_type`, `project_p6_id`, `source_team`, `source_schedule_name`
- New: `latest_phase_gate`, `latest_activity_status`

Use `import_meta_canonical_v3.py` for the new format.

### Null Island Records

Records with coordinates (0, 0) are treated as "no coordinates" and get:
- `has_coordinates = 0`
- `record_level = "Unlocated Campus Capacity"`
- Placed at (0, 0) in the feature class but filtered in analysis

---

*Documentation maintained as part of Data Center Consensus GIS Model project*
*Last updated: February 10, 2026*
