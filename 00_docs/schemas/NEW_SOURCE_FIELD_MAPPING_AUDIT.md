# Field Mapping Audit: Orennia & WoodMac → Consensus Schema

**Created:** February 12, 2026
**Purpose:** Document field mappings and identify new fields for schema consideration

---

## 1. Orennia Field Mapping

### Source Fields (18 columns)

| # | Orennia Field | Gold Field | Transform | Status |
|---|---------------|------------|-----------|--------|
| 1 | Name | campus_name, building_designation | Direct | ✅ Mapped |
| 2 | Data Center ID | source_unique_id, unique_id | "OREN_" prefix | ✅ Mapped |
| 3 | Data Center Status | facility_status | STATUS_MAP | ✅ Mapped |
| 4 | State | state_abbr | Direct (2-char) | ✅ Mapped |
| 5 | County | county | Direct | ✅ Mapped |
| 6 | Owner | company_source, company_clean | Direct | ✅ Mapped |
| 7 | Construction Date | construction_start_date | parse_date() | ✅ Mapped |
| 8 | Country | country | Direct | ✅ Mapped |
| 9 | Detailed Status | ❌ | - | 🆕 **NEW FIELD CANDIDATE** |
| 10 | First Power Date | actual_live_date | parse_date() | ✅ Mapped |
| 11 | Owner Type | type_category, company_clean_filter | OWNER_TYPE_MAP | ✅ Mapped |
| 12 | Power Capacity (MW) | commissioned/uc/planned_power_mw | Status-based routing | ✅ Mapped |
| 13 | Reported First Power Date | actual_live_date (fallback) | parse_date() | ✅ Mapped |
| 14 | Square Footage (Sq Ft) | facility_sqft | Direct | ✅ Mapped |
| 15 | Transmission Owner | market (proxy) | Direct | ⚠️ **IMPERFECT FIT** |
| 16 | Power Source | ❌ | - | 🆕 **NEW FIELD CANDIDATE** |
| 17 | Latitude (Degrees) | latitude | Direct | ✅ Mapped |
| 18 | Longitude (Degrees) | longitude | Direct | ✅ Mapped |

### Orennia Status Mapping
```
'Operating'        → 'Active'
'Under Construction' → 'Under Construction'
'Planned'          → 'Announced'
'Proposed'         → 'Announced'
'Cancelled'        → 'Cancelled'
'On Hold'          → 'On Hold'
'Decommissioned'   → 'Decommissioned'
'In Development'   → 'Under Construction'
'Offline'          → 'Decommissioned'
```

### 🆕 New Fields from Orennia (Schema Candidates)

| Field | Sample Values | Use Case | Recommendation |
|-------|---------------|----------|----------------|
| **Detailed Status** | "Operating", "In Development - Phase 2" | More granular status tracking | ⭐ Add as `status_detail` |
| **Transmission Owner** | "ERCOT", "PJM", "Dominion Energy" | Grid operator / utility mapping | ⭐⭐ Add as `grid_operator` or `transmission_owner` |
| **Power Source** | "Actual", "Estimated" | Data confidence indicator | Consider adding to `data_quality_flag` |

---

## 2. WoodMac Field Mapping

### Source Fields (41 columns)

| # | WoodMac Field | Gold Field | Transform | Status |
|---|---------------|------------|-----------|--------|
| 1 | site_name | campus_name | Direct | ✅ Mapped |
| 2 | publication_date | data_vintage | parse_date() | ✅ Mapped |
| 3 | super_region | region | SUPER_REGION_MAP | ✅ Mapped |
| 4 | region | ❌ (conflict with super_region) | - | ⚠️ Ignored |
| 5 | country_name | country | Direct | ✅ Mapped |
| 6 | state_province_name | state | Direct | ✅ Mapped |
| 7 | county_district_name | county | Direct | ✅ Mapped |
| 8 | latitude | latitude | Direct | ✅ Mapped |
| 9 | longitude | longitude | Direct | ✅ Mapped |
| 10 | market_name | market | Direct | ✅ Mapped |
| 11 | zone_name | ❌ | - | 🆕 **NEW FIELD CANDIDATE** |
| 12 | id_site | source_unique_id, unique_id | "WDMAC_" prefix | ✅ Mapped |
| 13 | project_name | building_designation | Direct | ✅ Mapped |
| 14 | project_type | ❌ | - | 🆕 **NEW FIELD CANDIDATE** |
| 15 | is_site | record_level | "Y" → Building, else Project | ✅ Mapped |
| 16 | **workload** | type_category | Direct | ✅ Mapped |
| 17 | developer_name | company_source, company_clean | Direct | ✅ Mapped |
| 18 | **finance_partner** | ❌ | - | 🆕 **NEW FIELD CANDIDATE** |
| 19 | disclosed_date | ❌ | - | 🆕 **NEW FIELD CANDIDATE** |
| 20 | land_acquisition_date | ❌ | - | 🆕 **NEW FIELD CANDIDATE** |
| 21 | permitting_date | ❌ | - | 🆕 **NEW FIELD CANDIDATE** |
| 22 | construction_date | construction_start_date | parse_date() | ✅ Mapped |
| 23 | cancelled_date | ❌ | - | 🆕 **NEW FIELD CANDIDATE** |
| 24 | commercial_operation_date | actual_live_date | parse_date() | ✅ Mapped |
| 25 | forecast_commercial_operation_date | actual_live_date (fallback) | parse_date() | ✅ Mapped |
| 26 | status | facility_status | STATUS_MAP | ✅ Mapped |
| 27 | **taxes_and_incentives** | ❌ | - | 🆕 **NEW FIELD CANDIDATE** |
| 28 | **prior_use** | ❌ | - | 🆕 **NEW FIELD CANDIDATE** |
| 29 | **connectivity** | ❌ | - | 🆕 **NEW FIELD CANDIDATE** |
| 30 | **energy_supply** | energy_source | Direct | ✅ Mapped (existing) |
| 31 | **cooling** | ❌ | - | 🆕 **NEW FIELD CANDIDATE** |
| 32 | buildings | ❌ | - | Could use for building_count |
| 33 | existing_capacity__mw | commissioned_power_mw | Direct | ✅ Mapped |
| 34 | development_capacity__mw | uc_power_mw | Direct | ✅ Mapped |
| 35 | planned_capacity__mw | planned_power_mw | Direct | ✅ Mapped |
| 36 | existing_development__mw | ❌ | - | Unclear meaning |
| 37 | **total_site_acres** | total_site_acres | Direct | ✅ Mapped (existing) |
| 38 | **data_center_acres** | ❌ | - | 🆕 **NEW FIELD CANDIDATE** |
| 39 | **land_cost_usd_million** | ❌ | - | 🆕 **NEW FIELD CANDIDATE** |
| 40 | **development_overall_cost_usd_million** | ❌ | - | 🆕 **NEW FIELD CANDIDATE** |
| 41 | **planned_overall_cost_usd_million** | total_cost_usd_million | Direct | ✅ Mapped (existing) |

### WoodMac Status Mapping
```
'Operational'   → 'Active'
'Construction'  → 'Under Construction'
'Disclosed'     → 'Announced'
'Permitted'     → 'Announced'
'Permitting'    → 'Announced'
'Rezoning'      → 'Announced'
'Land Acquired' → 'Announced'
'Cancelled'     → 'Cancelled'
'Denied'        → 'Cancelled'
'Withdrawn'     → 'Cancelled'
'Unknown'       → 'Unknown'
```

### 🆕 New Fields from WoodMac (Schema Candidates)

| Field | Sample Values | Use Case | Recommendation |
|-------|---------------|----------|----------------|
| **workload** | "AI", "Cloud", "Colo", "AI, Cloud", "HPC" | Workload type classification | ⭐⭐⭐ Add as `workload_type` |
| **finance_partner** | Company names | Investment tracking | ⭐ Add as `finance_partner` |
| **project_type** | "data campus", "data center" | Project vs campus distinction | Consider for `record_level` |
| **zone_name** | Grid zone identifiers | More granular location | ⭐ Add as `grid_zone` |
| **disclosed_date** | Dates | Project timeline tracking | ⭐⭐ Add for pipeline analysis |
| **land_acquisition_date** | Dates | Project timeline tracking | ⭐⭐ Add for pipeline analysis |
| **permitting_date** | Dates | Project timeline tracking | ⭐⭐ Add for pipeline analysis |
| **cancelled_date** | Dates | Track cancellation timing | ⭐ Add as `cancelled_date` |
| **taxes_and_incentives** | Text descriptions | Incentive analysis | Consider for enrichment |
| **prior_use** | "agricultural", "industrial" | Land use analysis | Low priority |
| **connectivity** | Fiber/network details | Connectivity analysis | ⭐ Add as `connectivity_notes` |
| **cooling** | "air", "liquid", "hybrid" | Cooling technology | ⭐⭐ Add as `cooling_type` |
| **data_center_acres** | Numeric | More precise than total_site | ⭐ Add as `dc_acres` |
| **land_cost_usd_million** | Numeric | Cost analysis | ⭐⭐ Add for investment analysis |
| **development_overall_cost_usd_million** | Numeric | Cost analysis | ⭐⭐ Add for investment analysis |

---

## 3. Recommended Schema Additions

### Priority 1 (High Value - Unique Data)

| New Field | Type | Source | Rationale |
|-----------|------|--------|-----------|
| `workload_type` | TEXT(100) | WoodMac | **AI vs Cloud vs Colo differentiation** - critical for hyperscaler analysis |
| `transmission_owner` / `grid_operator` | TEXT(100) | Orennia | **Grid/utility mapping** - unique to Orennia, valuable for power analysis |
| `cooling_type` | TEXT(50) | WoodMac | Sustainability/efficiency analysis |

### Priority 2 (Project Pipeline Tracking)

| New Field | Type | Source | Rationale |
|-----------|------|--------|-----------|
| `disclosed_date` | DATE | WoodMac | When project was first announced |
| `land_acquisition_date` | DATE | WoodMac | Land secured milestone |
| `permitting_date` | DATE | WoodMac | Permits approved milestone |
| `cancelled_date` | DATE | WoodMac | When project was cancelled |

### Priority 3 (Financial Analysis)

| New Field | Type | Source | Rationale |
|-----------|------|--------|-----------|
| `land_cost_usd_million` | DOUBLE | WoodMac | Real estate investment tracking |
| `development_cost_usd_million` | DOUBLE | WoodMac | CapEx analysis |
| `finance_partner` | TEXT(100) | WoodMac | Investment/JV tracking |

### Priority 4 (Nice to Have)

| New Field | Type | Source | Rationale |
|-----------|------|--------|-----------|
| `status_detail` | TEXT(100) | Orennia | More granular status |
| `grid_zone` | TEXT(50) | WoodMac | Power grid zone |
| `dc_acres` | DOUBLE | WoodMac | DC footprint vs total site |
| `connectivity_notes` | TEXT(255) | WoodMac | Network/fiber details |
| `power_source_confidence` | TEXT(20) | Orennia | "Actual" vs "Estimated" |

---

## 4. Current Mapping Gaps / Issues

### Orennia Issues

| Issue | Current Handling | Recommendation |
|-------|------------------|----------------|
| **Transmission Owner → market** | Mapped to `market` field | Create dedicated `transmission_owner` field |
| **No city field** | Not populated | Could parse from Name if needed |
| **Status "In Development"** | Mapped to "Under Construction" | Verify this is correct interpretation |

### WoodMac Issues

| Issue | Current Handling | Recommendation |
|-------|------------------|----------------|
| **super_region vs region** | Using super_region only | super_region = AMER/EMEA/APAC, region = sub-region |
| **30.9% Unknown status** | Passed through as "Unknown" | May need manual review |
| **No square footage** | Left NULL | Accept - not provided by source |
| **workload field** | Mapped to type_category | Consider dedicated `workload_type` field |

---

## 5. Decision Required

Before running ingestion, please confirm:

### Schema Changes
- [ ] **Add `transmission_owner` field?** (Orennia has 238 unique values)
- [ ] **Add `workload_type` field?** (WoodMac has AI/Cloud/Colo/HPC differentiation)
- [ ] **Add `cooling_type` field?** (WoodMac provides this)
- [ ] **Add pipeline date fields?** (disclosed_date, land_acquisition_date, permitting_date)
- [ ] **Add cost fields?** (land_cost, development_cost)

### Mapping Decisions
- [ ] **Confirm Orennia status mapping** (In Development → Under Construction?)
- [ ] **Confirm WoodMac workload → type_category** or create new field?

---

## 6. Quick Reference: What's Currently Mapped

### Orennia → Gold Buildings
```
Name                    → campus_name, building_designation
Data Center ID          → source_unique_id (OREN_ prefix)
Data Center Status      → facility_status (via STATUS_MAP)
State                   → state_abbr
County                  → county
Owner                   → company_source, company_clean
Construction Date       → construction_start_date
Country                 → country
First Power Date        → actual_live_date
Owner Type              → type_category, company_clean_filter
Power Capacity (MW)     → commissioned/uc/planned_power_mw (status-based)
Square Footage          → facility_sqft
Transmission Owner      → market (⚠️ imperfect fit)
Latitude/Longitude      → latitude, longitude
```

### WoodMac → Gold Buildings
```
site_name               → campus_name
id_site                 → source_unique_id (WDMAC_ prefix)
developer_name          → company_source, company_clean
status                  → facility_status (via STATUS_MAP)
country_name            → country
state_province_name     → state
county_district_name    → county
market_name             → market
super_region            → region
existing_capacity__mw   → commissioned_power_mw
development_capacity__mw → uc_power_mw
planned_capacity__mw    → planned_power_mw
construction_date       → construction_start_date
commercial_operation_date → actual_live_date
publication_date        → data_vintage
workload                → type_category
latitude/longitude      → latitude, longitude
```

---

*Last Updated: February 12, 2026*
