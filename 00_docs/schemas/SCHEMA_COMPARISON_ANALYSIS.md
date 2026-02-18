# 📊 Schema Comparison Analysis — Data Center Consensus Model

**Created:** December 29, 2025
**Purpose:** Compare 4 schema versions to determine optimal consensus schema
**For:** Supervisor review and final schema decision

---

## 📋 Schema Sources Compared

| # | Schema | Origin | Fields | Status |
|---|--------|--------|--------|--------|
| 1 | **Gold Buildings** | Production pipeline | 32 | ✅ Active |
| 2 | **Gold Campus** | Production pipeline | 25 | ✅ Active |
| 3 | **Google Form Intake** | Manual data collection | 27 | 📝 Reference |
| 4 | **Ad-hoc Brainstorm** | Recent whiteboard session | 19 | 📝 Draft |

---

## 🔍 Field-by-Field Comparison Matrix

### IDENTIFIERS & KEYS

| Concept | Gold Buildings | Gold Campus | Intake Form | Ad-hoc | Recommendation |
|---------|---------------|-------------|-------------|--------|----------------|
| Record UUID | `unique_id` | — | — | `UID` | ✅ **Keep `unique_id`** |
| Building ID | — | — | — | `UID_Building` | 🆕 **Add** - useful for multi-building campuses |
| Campus ID | `campus_id` | `campus_id` | — | `UID_Campus` | ✅ **Keep `campus_id`** |
| Phase ID | — | — | — | `UID_Phase` | 🆕 **Consider** - tracks expansion phases |
| Source record ID | `source_unique_id` | — | — | — | ✅ Keep for traceability |

### NAMING & IDENTITY

| Concept | Gold Buildings | Gold Campus | Intake Form | Ad-hoc | Recommendation |
|---------|---------------|-------------|-------------|--------|----------------|
| Building name | — | — | — | `Build_Name` | 🆕 **Add `building_name`** |
| Campus name | `campus_name` | `campus_name` | — | `Campus_Name_1` | ✅ Keep |
| Alternate name | — | — | — | `Campus_Name_2` | 🆕 **Add `campus_name_alt`** - aliases are common |
| Project name | — | — | `Project Name` | `Project_Name` | 🆕 **Add `project_name`** - announced projects |
| Company (clean) | `company_clean` | `company_clean` | `Company (Tenant/User)` | `Company_Name` | ✅ Keep `company_clean` |

### LOCATION FIELDS

| Concept | Gold Buildings | Gold Campus | Intake Form | Ad-hoc | Recommendation |
|---------|---------------|-------------|-------------|--------|----------------|
| Full address | `address` | `address` | `Facility Location` | — | ✅ Keep |
| City | `city` | `city` | (parsed) | `Loc_City` | ✅ Keep |
| State | `state` | `state` | (parsed) | `Loc_State` | ✅ Keep |
| State abbr | `state_abbr` | `state_abbr` | — | — | ✅ Keep |
| County | `county` | `county` | — | `Loc_County` | ✅ Keep |
| Country | `country` | `country` | (parsed) | `Loc_Country` | ✅ Keep |
| Region | `region` | `region` | — | — | ✅ Keep |
| Market | `market` | `market` | — | — | ✅ Keep |
| Postal code | `postal_code` | `postal_code` | — | — | ✅ Keep |
| Latitude | `latitude` | `latitude` | — | — | ✅ Keep |
| Longitude | `longitude` | `longitude` | — | — | ✅ Keep |

### CAPACITY FIELDS — POWER

| Concept | Gold Buildings | Gold Campus | Intake Form | Ad-hoc | Recommendation |
|---------|---------------|-------------|-------------|--------|----------------|
| **IT Power (MW)** | — | — | `IT (MW) - Server Power` | — | 🔥 **ADD `it_power_mw`** - critical for AI tracking |
| **Facility Power (MW)** | — | — | `Total Site Power (MW)` | — | 🔥 **ADD `facility_power_mw`** - enables PUE calc |
| Commissioned MW | `commissioned_power_mw` | `commissioned_power_mw` | — | `MW_Operational` | ✅ Keep (rename consideration) |
| Under Construction MW | `uc_power_mw` | `uc_power_mw` | — | `MW_Construction` | ✅ Keep |
| Planned MW | `planned_power_mw` | `planned_power_mw` | — | — | ✅ Keep |
| Full Capacity MW | `full_capacity_mw` | `full_capacity_mw` | — | `MW_Full_Capacity` | ✅ Keep |
| Planned + UC MW | `planned_plus_uc_mw` | `planned_plus_uc_mw` | — | — | ⚠️ Derived - keep for convenience |
| Available power (kW) | `available_power_kw` | — | — | — | ✅ Keep (DCH Lease) |
| Year forecasts | `mw_2023`-`mw_2032` | `mw_2023`-`mw_2032` | — | — | ✅ Keep (Semianalysis) |

### CAPACITY FIELDS — SPACE

| Concept | Gold Buildings | Gold Campus | Intake Form | Ad-hoc | Recommendation |
|---------|---------------|-------------|-------------|--------|----------------|
| Building sqft | `facility_sqft` | `facility_sqft_sum` | `Site: Building Size (SQFT)` | — | ✅ Keep |
| Whitespace sqft | `whitespace_sqft` | `whitespace_sqft_sum` | — | — | ✅ Keep |
| Land acres | — | — | `Site: Land Size (Acres)` | — | 🆕 **Add `total_site_acres`** (NPM has this) |

### STATUS & LIFECYCLE

| Concept | Gold Buildings | Gold Campus | Intake Form | Ad-hoc | Recommendation |
|---------|---------------|-------------|-------------|--------|----------------|
| Facility status | `facility_status` | `facility_status_agg` | `Development Stage` | — | ✅ Keep (domain values) |
| Cancelled flag | `cancelled` | `cancelled` | — | — | ✅ Keep |
| Actual live date | `actual_live_date` | `first_live_date` | `Date of Operation` | — | ✅ Keep |
| Building type | — | — | — | `Build_type` | 🆕 **Add `building_type`** |

### OWNERSHIP & RELATIONSHIPS

| Concept | Gold Buildings | Gold Campus | Intake Form | Ad-hoc | Recommendation |
|---------|---------------|-------------|-------------|--------|----------------|
| Owned/Leased | `owned_leased` | — | `Development Model` | — | ✅ Keep |
| **Developer** | — | — | `Developer of record` | `Site_Developer` | 🔥 **ADD `developer`** |
| **Tenant** | — | — | `Company (Tenant/User)` | `Site_Tennant` | 🔥 **ADD `tenant`** |
| **End User** | — | — | — | `Site_User` | 🔥 **ADD `end_user`** |
| Related entity | — | — | `Related Entity` | — | 🆕 Consider for corporate structures |
| GC/Contractor | — | — | `Developer, GC (Name)` | — | 🆕 Consider |

### ENERGY & INFRASTRUCTURE

| Concept | Gold Buildings | Gold Campus | Intake Form | Ad-hoc | Recommendation |
|---------|---------------|-------------|-------------|--------|----------------|
| **Power Strategy** | — | — | `Energy: Power Strategy` | — | 🔥 **ADD** - grid vs on-site |
| **Utility Company** | — | — | `Energy: Utility Company` | — | 🔥 **ADD** - critical for planning |
| **Fuel Type** | — | — | `Energy: Fuel Type` | — | 🔥 **ADD** - sustainability tracking |
| Cooling Type | — | — | `Cooling System Type` | — | 🆕 Consider - technical specs |

### AI/GPU TRACKING (NEW REQUIREMENT)

| Concept | Gold Buildings | Gold Campus | Intake Form | Ad-hoc | Recommendation |
|---------|---------------|-------------|-------------|--------|----------------|
| **GPU Type** | — | — | `Hardware: GPU Type` | — | 🔥 **ADD `gpu_type`** - critical for AI DC |
| **GPU Count** | — | — | `Hardware: GPU Count` | — | 🔥 **ADD `gpu_count`** - capacity metric |

### DATA QUALITY & PROVENANCE

| Concept | Gold Buildings | Gold Campus | Intake Form | Ad-hoc | Recommendation |
|---------|---------------|-------------|-------------|--------|----------------|
| Source | `source` | `source` | — | — | ✅ Keep |
| Date reported | `date_reported` | — | `Timestamp` | — | ✅ Keep |
| Ingest date | `ingest_date` | — | — | — | ✅ Keep |
| **Confidence score** | — | — | `Confidence Score` | — | 🔥 **ADD** - data quality tracking |
| Notes | — | — | `Notes` | — | 🆕 **Add `notes`** |
| News link | — | — | `News Article Link` | — | 🆕 Consider for provenance |
| Construction permits | — | — | `Construction Permits` | — | 🆕 Consider |

### AGGREGATION FIELDS (Campus-level only)

| Concept | Gold Campus | Recommendation |
|---------|-------------|----------------|
| Building count | `building_count` | ✅ Keep |
| Record level | `record_level` | ✅ Keep |

---

## 🎯 RECOMMENDATIONS SUMMARY

### 🔥 HIGH PRIORITY ADDITIONS (Add to Gold Schema)

These fields appear in intake forms and represent critical business needs:

| Field | Type | Rationale |
|-------|------|-----------|
| `it_power_mw` | DOUBLE | Separates IT load from facility power - critical for accurate comparison |
| `facility_power_mw` | DOUBLE | Enables PUE calculation (facility/IT) |
| `developer` | TEXT(128) | Tracks who is building - distinct from tenant/user |
| `tenant` | TEXT(128) | Lease tenant - distinct from end user |
| `end_user` | TEXT(128) | Actual occupant (e.g., Meta leasing from Vantage) |
| `gpu_type` | TEXT(64) | AI datacenter tracking (H100, B200, etc.) |
| `gpu_count` | LONG | Scale of AI deployments |
| `utility_company` | TEXT(128) | Power provider - critical for planning |
| `fuel_type` | TEXT(64) | Sustainability tracking (grid, solar, gas, etc.) |
| `confidence_score` | SHORT | 1-5 scale for data reliability |

### 🆕 MEDIUM PRIORITY ADDITIONS

| Field | Type | Rationale |
|-------|------|-----------|
| `building_name` | TEXT(128) | Individual building identity within campus |
| `project_name` | TEXT(128) | Announced project codename |
| `campus_name_alt` | TEXT(128) | Alternate/legacy name |
| `building_type` | TEXT(32) | Type classification |
| `power_strategy` | TEXT(64) | Grid, on-site gen, hybrid |
| `notes` | TEXT(500) | General notes field |
| `building_id` | TEXT(64) | Unique building identifier within campus |
| `phase_id` | TEXT(64) | Expansion phase tracking |

### ⚠️ FIELDS TO DEPRECATE OR MERGE

| Current Field | Issue | Resolution |
|---------------|-------|------------|
| `planned_plus_uc_mw` | Derived, redundant | Keep for convenience but document as derived |
| `market` | Often duplicate of metro/city | Keep but clarify definition |

### 📝 NAMING CONVENTIONS TO STANDARDIZE

The ad-hoc schema uses different naming conventions. Recommend standardizing to:

| Ad-hoc Name | Standardized Name | Reason |
|-------------|-------------------|--------|
| `UID` | `unique_id` | Consistency with existing |
| `UID_Building` | `building_id` | Clearer |
| `UID_Campus` | `campus_id` | Already exists |
| `UID_Phase` | `phase_id` | Clearer |
| `Build_Name` | `building_name` | Clearer |
| `Campus_Name_1` | `campus_name` | Already exists |
| `Campus_Name_2` | `campus_name_alt` | Clearer purpose |
| `Company_Name` | `company_clean` | Already exists |
| `Loc_*` | `city`, `state`, etc. | Already exists |
| `MW_Operational` | `commissioned_power_mw` | Already exists |
| `MW_Construction` | `uc_power_mw` | Already exists |
| `Site_Developer` | `developer` | Cleaner |
| `Site_Tennant` | `tenant` | Fix typo, cleaner |
| `Site_User` | `end_user` | Cleaner |

---

## 🏗️ PROPOSED CONSENSUS SCHEMA v2.0

### Building-Level Fields (gold_buildings)

```
IDENTIFIERS
├── unique_id           TEXT(64)    — Record UUID
├── source              TEXT(64)    — Data source name
├── source_unique_id    TEXT(64)    — Source's original ID
├── building_id         TEXT(64)    — Building ID within campus [NEW]
├── campus_id           TEXT(128)   — Campus linkage key
├── phase_id            TEXT(64)    — Expansion phase [NEW]

NAMING
├── building_name       TEXT(128)   — Building name [NEW]
├── campus_name         TEXT(128)   — Campus name
├── campus_name_alt     TEXT(128)   — Alternate name [NEW]
├── project_name        TEXT(128)   — Announced project name [NEW]
├── company_clean       TEXT(128)   — Company (standardized)

OWNERSHIP & RELATIONSHIPS [NEW SECTION]
├── developer           TEXT(128)   — Developer/builder [NEW]
├── tenant              TEXT(128)   — Lease tenant [NEW]
├── end_user            TEXT(128)   — Actual occupant [NEW]
├── owned_leased        TEXT(16)    — Ownership model

LOCATION
├── address             TEXT(255)
├── city                TEXT(128)
├── state               TEXT(64)
├── state_abbr          TEXT(8)
├── county              TEXT(128)
├── country             TEXT(64)
├── postal_code         TEXT(16)
├── region              TEXT(16)
├── market              TEXT(128)
├── latitude            DOUBLE
├── longitude           DOUBLE

CAPACITY — POWER
├── it_power_mw              DOUBLE   — IT/server power [NEW]
├── facility_power_mw        DOUBLE   — Total facility power [NEW]
├── commissioned_power_mw    DOUBLE   — Operational capacity
├── uc_power_mw              DOUBLE   — Under construction
├── planned_power_mw         DOUBLE   — Planned/announced
├── full_capacity_mw         DOUBLE   — Total buildout
├── planned_plus_uc_mw       DOUBLE   — Derived convenience field
├── available_power_kw       DOUBLE   — Available (DCH Lease)
├── mw_2023 - mw_2032        DOUBLE   — Year forecasts (Semianalysis)

CAPACITY — SPACE
├── facility_sqft       DOUBLE
├── whitespace_sqft     DOUBLE
├── total_site_acres    DOUBLE      — Land size [NEW]

INFRASTRUCTURE [NEW SECTION]
├── utility_company     TEXT(128)   — Power utility [NEW]
├── fuel_type           TEXT(64)    — Power source [NEW]
├── power_strategy      TEXT(64)    — Grid/on-site/hybrid [NEW]
├── cooling_type        TEXT(64)    — Cooling system [NEW]

AI/GPU [NEW SECTION]
├── gpu_type            TEXT(64)    — GPU model [NEW]
├── gpu_count           LONG        — GPU count [NEW]

STATUS & LIFECYCLE
├── facility_status     TEXT(32)    — Lifecycle stage (domain)
├── building_type       TEXT(32)    — Building classification [NEW]
├── actual_live_date    DATE
├── cancelled           SHORT

PROVENANCE
├── date_reported       DATE
├── ingest_date         DATE
├── confidence_score    SHORT       — 1-5 reliability [NEW]
├── notes               TEXT(500)   — General notes [NEW]
├── record_level        TEXT(16)    — Building/Campus
```

### Campus-Level Fields (gold_campus)

Same as buildings with these differences:
- Aggregated capacity fields (SUM)
- `building_count` — Count of buildings
- `first_live_date` instead of `actual_live_date`
- `facility_status_agg` — Aggregated status

---

## 📊 FIELD COUNT COMPARISON

| Schema Version | Field Count | Coverage |
|----------------|-------------|----------|
| Current Gold Buildings | 32 | Core pipeline |
| Current Gold Campus | 25 | Core pipeline |
| Google Form Intake | 27 | Manual collection |
| Ad-hoc Brainstorm | 19 | Conceptual |
| **Proposed v2.0 Buildings** | **48** | Comprehensive |
| **Proposed v2.0 Campus** | **45** | Comprehensive |

---

## ✅ NEXT STEPS

1. **Review this document** with supervisor
2. **Prioritize additions** — Decide which HIGH/MEDIUM priority fields to add
3. **Create migration script** — Add new fields to existing gold_buildings/gold_campus
4. **Update ingestion scripts** — Map new fields from source data
5. **Update intake form** — Align Google Form with new schema
6. **Document field definitions** — Add to CAPACITY_FIELD_DEFINITIONS.md

---

## 📝 QUESTIONS FOR SUPERVISOR

1. **GPU tracking**: Is this a priority for the current phase?
2. **Developer/Tenant/User split**: Critical for the business use case?
3. **Energy fields**: Needed now or future phase?
4. **Confidence scoring**: Who assigns scores, what's the scale?
5. **Phase tracking**: How granular should expansion phase tracking be?

---

*Document created by schema comparison analysis — December 29, 2025*
