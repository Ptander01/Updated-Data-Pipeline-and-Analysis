# Capacity Field Definitions Matrix

## Purpose
This document defines what each capacity field measures across all data sources to ensure apples-to-apples comparisons in capacity accuracy analysis.

**Last Updated:** December 17, 2025
**Version:** 3.0 (Deep Dive Validation Complete)

---

## 🎯 DECEMBER 2024 CAPACITY ACCURACY FINDINGS

Comprehensive validation against Meta canonical ground truth revealed:

### Key Discovery: No PUE Adjustment Needed for DCH

**Both DCH Hyper and DCH Lease report IT capacity (same definition as Meta).** No PUE adjustment is needed.

| Source | MAPE (Complete Builds) | Granularity | Grade |
|--------|------------------------|-------------|-------|
| **Semianalysis** | **11.9%** 🏆 | Building | A |
| **DataCenterHawk** | **17.6%** | Building | A- |

**Evidence from December 2024 analysis:**
- PUE=1.0 (no adjustment) gives the best MAPE (17.6%)
- Average DCH/Meta ratio = 0.84 (DCH slightly under-reports by ~16%)
- Applying PUE=1.3 actually **worsens** accuracy (23.5% MAPE)

**Conclusion:** DCH reports IT capacity directly. Compare without PUE adjustment.

### Semianalysis vs DCH Accuracy Summary

| Source | Avg Accuracy | Best Campuses | Notes |
|--------|-------------|---------------|-------|
| **Semianalysis** | 43.2% (n=7) | Fort Worth (96.8%), DeKalb (100%), Gallatin (88.2%) | Uses `mw_2025` |
| **DataCenterHawk** | 39.2% (n=9) | DeKalb (76.9%), Fort Worth (74.4%) | Uses `commissioned_power_mw ÷ 1.3` |

### Outliers Identified

4 campus comparisons excluded as outliers (< -100% accuracy):
- **Huntsville**: -586% (DCH), -960% (Semi) — likely planned capacity reported as commissioned
- **Los Lunas**: -124.6% (Semi)
- **New Albany**: -122.9% (Semi)

### Deep Dive Validation Script

```python
# Configuration in deep_dive_campus_validation.py
DCH_PUE_ADJUSTMENT = 1.3  # Facility power → IT load estimate
OUTLIER_THRESHOLD = -100  # Exclude from average calculations
```

---

This document has been audited against the actual ingestion scripts used in the Full Data Pipeline.

| Source | Script | Documented? | Implementation Verified? |
|--------|--------|-------------|-------------------------|
| DCH Hyper | `ingest_dch.py` | ✅ Yes | ✅ Verified |
| DCH Lease | `ingest_dch_lease.py` | ⚠️ Partial | ✅ Now Documented |
| Semianalysis | `ingest_semianalysis.py` | ✅ Yes | ✅ Verified |
| DataCenterMap | `ingest_dcm.py` | ✅ Yes | ✅ Verified |
| NewProjectMedia | `ingest_npm.py` | ⚠️ Partial | ✅ Now Documented |
| WoodMac | Excluded | ✅ Yes | N/A (Excluded) |
| Synergy | Skipped | ✅ Yes | N/A (No coords) |

---

## Meta Ground Truth

| Field | Table | Unit | What It Measures | Time Horizon |
|-------|-------|------|------------------|--------------|
| `it_load` | meta_canonical_v2 | MW | **Actual IT server load** (current draw) | Current |
| `it_load_total` | meta_canonical_buildings | MW | Sum of suite-level IT loads per building | Current |

**Key Point:** Meta's `it_load` is **actual server load**, NOT facility power or design capacity. This is critical for comparisons.

---

## Gold Schema Capacity Fields

The gold_buildings and gold_campus feature classes use these standardized capacity fields:

| Field | Unit | Definition | Time Horizon |
|-------|------|------------|--------------|
| `commissioned_power_mw` | MW | Currently operational capacity | Current |
| `uc_power_mw` | MW | Capacity under construction | Near-term |
| `planned_power_mw` | MW | Announced/planned capacity | Future |
| `full_capacity_mw` | MW | Total buildout (commissioned + UC + planned) | Future |
| `planned_plus_uc_mw` | MW | Planned + under construction | Near-term |
| `available_power_kw` | kW | Available (unallocated) capacity | Current |
| `mw_2023` - `mw_2032` | MW | Year-by-year capacity forecasts | Annual |

---

## Vendor Field Definitions & Ingestion Mappings

### DataCenterHawk Hyperscale (DCH Hyper)

**Script:** `ingest_dch.py`
**Source Table:** `dch_hyper_raw`
**Records:** 1,876

| Gold Field | Source Field | Unit Conversion | What It Measures | Verified? |
|------------|--------------|-----------------|------------------|-----------|
| `commissioned_power_mw` | `capacity_commissioned_power` | **kW → MW (×0.001)** | Facility power capacity (design) | ✅ |
| `planned_power_mw` | `capacity_planned_power` | kW → MW (×0.001) | Planned facility additions | ✅ |
| `uc_power_mw` | `capacity_under_construction_power` | kW → MW (×0.001) | Under construction capacity | ✅ |
| `full_capacity_mw` | Derived | Sum of above | Total buildout potential | ✅ |
| `planned_plus_uc_mw` | Derived | planned + uc | Non-commissioned capacity | ✅ |
| `facility_sqft` | `capacity_building_sf` | Already sqft | Building square footage | ✅ |

**Implementation Notes:**
```python
# From ingest_dch.py lines 228-233
KW_TO_MW = 0.001
commissioned_mw = (cap_comm * KW_TO_MW) if cap_comm else 0
planned_mw = (cap_plan * KW_TO_MW) if cap_plan else 0
uc_mw = (cap_uc * KW_TO_MW) if cap_uc else 0
full_capacity_mw = commissioned_mw + planned_mw + uc_mw
planned_plus_uc_mw = planned_mw + uc_mw
```

**✅ Comparison Note (Updated December 2024):**
- DCH Hyper reports **IT capacity** (same definition as Meta) - NO PUE adjustment needed
- December 2024 testing confirmed: PUE=1.0 gives best MAPE (17.6%), applying PUE worsens accuracy
- DCH under-reports by ~16% on average (ratio 0.84)
- Granularity: **Building level** (despite documentation saying Campus)

---

### DataCenterHawk Lease (DCH Lease)

**Script:** `ingest_dch_lease.py`
**Source Table:** `dch_lease_raw`
**Records:** 5,176

| Gold Field | Source Field | Unit Conversion | What It Measures | Verified? |
|------------|--------------|-----------------|------------------|-----------|
| `commissioned_power_mw` | `capacity_commissioned_power` | kW → MW (×0.001) | IT capacity (colocation) | ✅ |
| `planned_power_mw` | `capacity_planned_power` | kW → MW (×0.001) | Planned IT capacity | ✅ |
| `uc_power_mw` | `capacity_under_construction_power` | kW → MW (×0.001) | Under construction | ✅ |
| `available_power_kw` | `capacity_available_power` | **Kept as kW** | Available (unallocated) | ✅ |
| `full_capacity_mw` | Derived | Sum of above | Total buildout | ✅ |
| `planned_plus_uc_mw` | Derived | planned + uc | Non-commissioned | ✅ |
| `facility_sqft` | `building_size` OR `capacity_commissioned_space` | Already sqft | Building size | ✅ |
| `whitespace_sqft` | `capacity_available_space` | Already sqft | Available floor space | ✅ |

**Implementation Notes:**
```python
# From ingest_dch_lease.py lines 266-278
# DCH Lease reports IT capacity, no PUE adjustment needed
commissioned_mw = safe_float(cap_comm) * KW_TO_MW if safe_float(cap_comm) else 0
planned_mw = safe_float(cap_plan) * KW_TO_MW if safe_float(cap_plan) else 0
uc_mw = safe_float(cap_uc) * KW_TO_MW if safe_float(cap_uc) else 0
available_kw = safe_float(cap_avail)  # Keep in kW for available_power_kw field

full_capacity_mw = commissioned_mw + planned_mw + uc_mw
planned_plus_uc_mw = planned_mw + uc_mw
```

**✅ Comparison Note:**
- DCH Lease reports **IT capacity** (same definition as Meta) - NO PUE adjustment needed
- Additional field: `available_power_kw` captures unallocated capacity
- Granularity: **Building/Facility level**

---

### Semianalysis

**Script:** `ingest_semianalysis.py`
**Source Table:** `semianalysis_raw`
**Records:** 5,472

| Gold Field | Source Field | Unit Conversion | What It Measures | Verified? |
|------------|--------------|-----------------|------------------|-----------|
| `commissioned_power_mw` | `Field41` (Installed Capacity MW) | Already MW | IT capacity (Q2 2025) | ✅ |
| `planned_power_mw` | `Field37` (Total Planned MW) | Already MW | Planned IT capacity | ✅ |
| `uc_power_mw` | `Field31` (Total under Construction MW) | Already MW | Under construction | ✅ |
| `full_capacity_mw` | `Field34` (Full Capacity) OR derived | Already MW | Total buildout | ✅ |
| `mw_2023` | `Field20` | Already MW | Year 2023 capacity | ✅ |
| `mw_2024` | `Field21` | Already MW | Year 2024 capacity | ✅ |
| `mw_2025` | `Field22` | Already MW | Year 2025 capacity | ✅ |
| `mw_2026` | `Field23` | Already MW | Year 2026 capacity | ✅ |
| `mw_2027` | `Field24` | Already MW | Year 2027 capacity | ✅ |
| `mw_2028` | `Field25` | Already MW | Year 2028 capacity | ✅ |
| `mw_2029` | `Field26` | Already MW | Year 2029 capacity | ✅ |
| `mw_2030` | `Field27` | Already MW | Year 2030 capacity | ✅ |
| `mw_2031` | `Field28` | Already MW | Year 2031 capacity | ✅ |
| `mw_2032` | `Field29` | Already MW | Year 2032 capacity | ✅ |
| `facility_sqft` | `Field42` | Already sqft | Facility square footage | ✅ |

**Implementation Notes:**
```python
# From ingest_semianalysis.py lines 351-358
# Status determination based on capacity
facility_status = determine_status(installed_mw, uc_mw, planned_mw)

# Commissioned = installed capacity
commissioned_mw = installed_mw or 0

# Full capacity (use provided or sum)
full_capacity_mw = full_cap or (commissioned_mw + (uc_mw or 0) + (planned_mw or 0))
```

**✅ Comparison Note:**
- Semianalysis reports **IT capacity** (same definition as Meta)
- `mw_YYYY` fields are **directly comparable** to Meta `it_load_total`
- Data is at **BUILDING level** - matches Meta building granularity
- **BEST source for capacity comparison** - has 10-year forecasts

---

### DataCenterMap (DCM)

**Script:** `ingest_dcm.py`
**Source Table:** `dcm_raw`
**Records:** 8,453

| Gold Field | Source Field | Unit Conversion | What It Measures | Verified? |
|------------|--------------|-----------------|------------------|-----------|
| `commissioned_power_mw` | `power_mw` (if stage='operational') | Already MW | Design power capacity | ✅ |
| `planned_power_mw` | `power_mw` (if stage='planned'/'land banked') | Already MW | Planned capacity | ✅ |
| `uc_power_mw` | `power_mw` (if stage='under construction') | Already MW | Under construction | ✅ |
| `full_capacity_mw` | Derived | Sum of routed values | Total capacity | ✅ |
| `planned_plus_uc_mw` | Derived | planned + uc | Non-commissioned | ✅ |
| `facility_sqft` | `building_sqft` | Already sqft | Building size | ✅ |
| `whitespace_sqft` | `whitespace_sqft` | Already sqft | Whitespace | ✅ |

**Implementation Notes:**
```python
# From ingest_dcm.py lines 207-220
def route_capacity(stage, power_mw):
    """Route power capacity to appropriate field based on status."""
    if not power_mw:
        return None, None, None

    stage_lower = str(stage).lower() if stage else ''

    if 'operational' in stage_lower:
        return power_mw, None, None  # commissioned
    elif 'under construction' in stage_lower:
        return None, power_mw, None  # uc
    elif 'planned' in stage_lower or 'land banked' in stage_lower:
        return None, None, power_mw  # planned

    return None, None, None
```

**⚠️ Comparison Note:**
- Single `power_mw` field is routed to different columns based on `stage` field
- Mix of campus and building level records (check `record_level` field)
- **Unclear if this is facility power or IT capacity** - documentation needed from DCM
- Capacity coverage is sparse (~33% of records)

**🔍 DCM Capacity Limitation - Hyperscalers (December 17, 2025):**

DCM does NOT provide capacity data for hyperscaler facilities:

| Company | DCM Records | With Capacity > 0 |
|---------|-------------|-------------------|
| Meta | 72 | **0 (0%)** |
| Microsoft | 253 | **~0%** |
| Google | 100 | **~0%** |
| AWS | ~363 | **~0%** |
| **All DCM** | 8,453 | 2,749 (32.5%) |

**Root Cause:** Hyperscalers keep their capacity data proprietary. DCM's capacity data is primarily for colocation/enterprise data centers where providers publicly disclose capacity.

**Implication for Analysis:**
- DCM provides **location data only** for hyperscalers
- For hyperscaler capacity, use **DataCenterHawk** or **Semianalysis**
- DCM is still valuable for colocation facility capacity and ecosystem metadata

---

### NewProjectMedia (NPM)

**Script:** `ingest_npm.py`
**Source Table:** `npm_raw`
**Records:** 1,399

| Gold Field | Source Field | Unit Conversion | What It Measures | Verified? |
|------------|--------------|-----------------|------------------|-----------|
| `full_capacity_mw` | `Total_MWs` | Already MW | Total project capacity (design) | ✅ |
| `facility_sqft` | `Building_Size__sq_ft_` | Parsed (handles "M" suffix) | Building size | ✅ |
| `total_site_acres` | `Land_Size__acre_` | Already acres | Land footprint | ✅ |
| `total_cost_usd_million` | `Cost` | Parsed (extracts numeric) | Project cost | ✅ |

**Implementation Notes:**
```python
# From ingest_npm.py lines 447-456
# Capacity
full_capacity_mw = float(total_mws) if total_mws else None

# Building size (handles "4.00M" → 4000000.0)
facility_sqft = parse_building_size(building_size)

# Land size (already in acres)
total_site_acres = float(land_size) if land_size else None

# Cost (handles "USD 800M" → 800.0)
total_cost_usd_million = parse_cost_string(cost)
```

**⚠️ Comparison Note:**
- NPM only provides **total project capacity** - no split by status
- `commissioned_power_mw`, `uc_power_mw`, `planned_power_mw` are **NOT populated**
- All NPM records go to `full_capacity_mw` regardless of status
- US-only coverage
- Likely represents **design/nameplate capacity**, not IT load
- **Not suitable for current-state capacity comparison**

---

### WoodMac (EXCLUDED)

**Script:** `ingest_woodmac.py` (NOT in active pipeline)
**Status:** EXCLUDED from gold_buildings

| Gold Field | Source Field | Unit Conversion | What It Measures |
|------------|--------------|-----------------|------------------|
| `commissioned_power_mw` | `existing_mw` | Already MW | Existing built capacity |
| `planned_power_mw` | `new_mw` | Already MW | New expansion capacity |
| `full_capacity_mw` | Derived | existing + new | Post-expansion total |

**❌ Exclusion Reason:**
- WoodMac tracks **development phases**, not physical buildings
- See `GRANULARITY_STRATEGY.md` for full explanation
- Use for validation reference only

---

### Synergy (SKIPPED)

**Script:** `ingest_synergy.py` (NOT executed)
**Status:** SKIPPED - No coordinates

| Field | Status |
|-------|--------|
| All capacity fields | **NOT INGESTED** |

**❌ Exclusion Reason:**
- Synergy source has **no coordinate data**
- Cannot be spatially joined or mapped
- Focus is on facility attributes, not capacity

---

## Capacity Field Flow Summary

```
SOURCE DATA                 INGESTION TRANSFORM              GOLD SCHEMA
─────────────────          ──────────────────────           ───────────────
DCH Hyper/Lease
├─ capacity_commissioned_power (kW) ──→ ×0.001 ──→ commissioned_power_mw
├─ capacity_planned_power (kW) ──────→ ×0.001 ──→ planned_power_mw
├─ capacity_under_construction (kW) ─→ ×0.001 ──→ uc_power_mw
├─ capacity_available_power (kW) ────→ no conv ─→ available_power_kw (Lease only)
└─ capacity_building_sf ─────────────→ no conv ─→ facility_sqft

Semianalysis
├─ Installed Capacity MW ────────────→ no conv ─→ commissioned_power_mw
├─ Total Planned MW ─────────────────→ no conv ─→ planned_power_mw
├─ Total under Construction MW ──────→ no conv ─→ uc_power_mw
├─ Full Capacity ────────────────────→ no conv ─→ full_capacity_mw
├─ mw_2023-2032 ─────────────────────→ no conv ─→ mw_2023-mw_2032
└─ Facility Square Footage ──────────→ no conv ─→ facility_sqft

DCM
├─ power_mw (if operational) ────────→ no conv ─→ commissioned_power_mw
├─ power_mw (if UC) ─────────────────→ no conv ─→ uc_power_mw
├─ power_mw (if planned) ────────────→ no conv ─→ planned_power_mw
├─ building_sqft ────────────────────→ no conv ─→ facility_sqft
└─ whitespace_sqft ──────────────────→ no conv ─→ whitespace_sqft

NPM
├─ Total_MWs ────────────────────────→ no conv ─→ full_capacity_mw ONLY
├─ Building_Size__sq_ft_ ────────────→ parsed ──→ facility_sqft
├─ Land_Size__acre_ ─────────────────→ no conv ─→ total_site_acres
└─ Cost ─────────────────────────────→ parsed ──→ total_cost_usd_million
```

---

## Apples-to-Apples Comparison Matrix

### Best Comparisons (Same Definition)

| Comparison | Vendor Field | Meta Field | Notes |
|------------|--------------|------------|-------|
| ✅ **BEST** | Semianalysis `mw_2024`/`mw_2025` | `it_load_total` | Both = IT capacity, building level |
| ✅ **GOOD** | Semianalysis `commissioned_power_mw` | `it_load_total` | Both = IT capacity, building level |
| ✅ **GOOD** | DCH Lease `commissioned_power_mw` | `it_load_total` | Both = IT capacity (per script comment) |

### Also Good (No Adjustment Needed)

| Comparison | Vendor Field | Meta Field | Notes |
|------------|--------------|------------|-------|
| ✅ **GOOD** | DCH Hyper `commissioned_power_mw` | `it_load_total` | IT capacity - no PUE adjustment (Dec 2024 validated) |
| ⚠️ | DCM `commissioned_power_mw` | `it_load_total` | Filter to building level, verify IT vs facility |

### Not Comparable

| Comparison | Vendor Field | Meta Field | Reason |
|------------|--------------|------------|--------|
| ❌ | NPM `full_capacity_mw` | `it_load_total` | NPM = design capacity, no status split |
| ❌ | Any `mw_2030`/`mw_2032` | `it_load_total` | Future forecast vs current state |
| ❌ | Synergy | Any | No data (skipped) |
| ❌ | WoodMac | Any | Dev phases, not buildings (excluded) |

---

## Recommended Comparison Approaches

### 1. Building-Level IT Capacity (Semianalysis - BEST)
```
Vendor: Semianalysis mw_2024 or commissioned_power_mw
Meta: meta_canonical_buildings.it_load_total
Method: 1:1 spatial match (closest within 5km)
Expected MAPE: <15% (same definition)
```

### 2. Building-Level Colocation (DCH Lease)
```
Vendor: DCH Lease commissioned_power_mw (source='DataCenterHawk', record_level='Building')
Meta: meta_canonical_buildings.it_load_total
Adjustment: None needed (IT capacity per script comment)
Method: Spatial match + company filter
Expected MAPE: 15-25%
```

### 3. Campus-Level (DCH Hyper)
```
Vendor: gold_campus (DCH Hyper records only)
Meta: Aggregate it_load_total by dc_code (campus)
Adjustment: None needed (DCH reports IT capacity)
Method: Match by campus_id or spatial proximity
Expected MAPE: ~18% (same definition as Meta)
```

### 4. Time-Horizon Validation
```
For CURRENT state: Use commissioned_power_mw or mw_2024
For FORECAST accuracy: Compare mw_2025+ against future builds only
DO NOT compare future forecasts to current IT load
```

---

## Key Terminology

| Term | Definition |
|------|------------|
| **IT Load** | Actual power consumed by IT equipment (servers, storage, network) |
| **Facility Power** | Total building power including IT load + cooling + lighting + infrastructure |
| **PUE** | Power Usage Effectiveness = Facility Power / IT Load (typically 1.2-1.5) |
| **Design Capacity** | Maximum rated capacity of facility (often higher than actual load) |
| **Commissioned** | Built and operational |
| **Utilization** | Actual load / Design capacity (typically 60-80%) |

---

## Summary & Audit Findings

### What's Working Well ✅
1. **Semianalysis** is properly mapped with all 10 year-fields (mw_2023-2032)
2. **DCH Hyper/Lease** correctly converts kW→MW with ×0.001 factor
3. **DCM** properly routes single `power_mw` field based on status
4. Derived fields (`full_capacity_mw`, `planned_plus_uc_mw`) calculated consistently

### Issues Identified ⚠️
1. **NPM only populates `full_capacity_mw`** - no split by status (commissioned/uc/planned)
   - This is intentional (NPM doesn't provide status breakdown) but limits comparison utility

2. **DCH Lease `available_power_kw` field** - not documented previously
   - Now added to documentation

3. **DCM capacity definition unclear** - is it IT or facility power?
   - Needs verification from DCM data dictionary

### Recommendations
1. ✅ Use **Semianalysis** for primary capacity comparison (IT capacity, building level, 11.9% MAPE)
2. ✅ Use **DCH Hyper** for hyperscaler capacity comparison (IT capacity, 17.6% MAPE)
3. ✅ Use **DCH Lease** for colocation capacity comparison (IT capacity)
4. ❌ **Do not apply PUE adjustment** to DCH - December 2024 testing showed it worsens accuracy
5. ⚠️ **Orennia may require PUE adjustment** - February 2026 testing suggests ratio ~1.25 (facility power)
6. ❓ **WoodMac** - Insufficient data for power definition analysis (no Meta facilities matched)
7. ❌ **Do not use NPM** for current-state capacity analysis (design only)
8. ❌ **Do not use future forecasts** (mw_2030+) to compare with current IT load

---

## 🆕 FEBRUARY 2026: ORENNIA & WOODMAC POWER DEFINITION ANALYSIS

### Orennia Analysis Results

**Methodology:** Compared Orennia `Power Capacity (MW)` against Meta canonical `it_load_total` for matched facilities.

| PUE Adjustment | MAPE | Vendor/Meta Ratio | Interpretation |
|----------------|------|-------------------|----------------|
| **1.0 (none)** | 68.6% | 1.25 | Orennia over-reports by ~25% |
| **1.2** | 57.7% | **1.05** | ✅ Best ratio alignment |
| **1.3** | 55.8% | 0.96 | Good |
| **1.4** | 54.2% | 0.90 | Under-reports |

**Conclusion:** Orennia likely reports **FACILITY POWER** (not IT capacity).
- Without adjustment: 25% over-reporting vs Meta IT load
- With PUE ÷1.2: Ratio improves to 1.05
- **Recommendation:** Apply PUE ÷1.2 when comparing Orennia to Meta IT load

**Caveats:**
- Small sample size (6 matched facilities)
- Orennia reports by phase (multiple records per campus)
- Some outliers may include planned capacity (e.g., Eagle Mountain 3.04x ratio)

### WoodMac Analysis Results

**Status:** ⚠️ Insufficient data for analysis
- 0 WoodMac Meta facilities found in gold_buildings_full
- Possible causes:
  - WoodMac not yet ingested to gold_buildings, OR
  - WoodMac uses "Facebook" instead of "Meta" for company name
- **Action Required:** Verify WoodMac ingestion and company naming before analysis

### Source Power Definition Summary (Updated Feb 2026)

| Source | Reports | PUE Adjustment | Evidence | Confidence |
|--------|---------|----------------|----------|------------|
| **Semianalysis** | IT Capacity | None | Dec 2024: 11.9% MAPE | ✅ High |
| **DCH Hyper** | IT Capacity | None | Dec 2024: 17.6% MAPE, ratio 0.84 | ✅ High |
| **DCH Lease** | IT Capacity | None | Same as DCH Hyper | ✅ High |
| **Orennia** | Facility Power | ÷1.2 | Feb 2026: ratio 1.25 → 1.05 | ⚠️ Medium (small sample) |
| **WoodMac** | Unknown | TBD | No data for comparison | ❓ Unknown |
| **NPM** | Design Capacity | N/A | Not comparable to IT load | ❌ N/A |
| **DCM** | Unknown | TBD | Not tested | ❓ Unknown |

---

**Document Audit Complete - December 17, 2025**
