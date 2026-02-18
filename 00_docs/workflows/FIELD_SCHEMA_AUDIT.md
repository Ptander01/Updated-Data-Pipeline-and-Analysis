# Gold Layer Field Schema Audit
## Comprehensive Field Definition & Consistency Review
**Generated:** January 8, 2026

---

## Executive Summary

This document provides a complete audit of all fields across the three gold layers:
- **gold_buildings_full** - Individual building/facility records
- **gold_campus_full** - Aggregated campus records (grouped by UCID)
- **gold_combined_xb** - Combined layer for Experience Builder visualization

### Key Findings
1. **74 fields** defined in gold_buildings schema (per validate_gold_build_schema.py)
2. **42 fields** in XB combined layer (optimized for visualization)
3. Several fields could be deprecated or consolidated
4. Field ordering is inconsistent - should be reorganized by category

---

## Field Categories

| Category | Description | Example Fields |
|----------|-------------|----------------|
| **1. Identifiers** | Unique IDs, record level | ucid, building_ucid, unique_id |
| **2. Company/Ownership** | Owner, developer, tenant info | company_clean, developer, end_user |
| **3. Location** | Geographic information | city, state, country, lat/lon |
| **4. Capacity - Power** | Power metrics in MW | commissioned_power_mw, full_capacity_mw |
| **5. Capacity - Area** | Square footage metrics | facility_sqft, whitespace_sqft |
| **6. Capacity - Forecast** | Year-by-year projections | mw_2023 through mw_2032 |
| **7. Status** | Facility operational status | facility_status, cancelled |
| **8. Dates/Timeline** | Key milestone dates | construction_start_date, actual_live_date |
| **9. Infrastructure** | Power, PUE, tier design | pue, tier_design, power_provider |
| **10. Classification** | Facility type, purpose | type_category, owned_leased |
| **11. Costs/Land** | Financial and land metrics | total_cost_usd_million, total_site_acres |
| **12. Source Tracking** | Data provenance | source, ingest_date, data_vintage |
| **13. Flags** | Boolean indicators | is_essential, cancelled |
| **14. Notes/Metadata** | Free-text and references | notes, additional_references |

---

## Recommended Field Order (by Category)

### Category 1: IDENTIFIERS
| # | Field Name | Type | Length | Layer | Description | Keep? |
|---|-----------|------|--------|-------|-------------|-------|
| 1 | record_level | TEXT | 20 | ALL | 'Building' or 'Campus' | ✅ |
| 2 | unique_id | TEXT | 100 | BLDG | Unique record ID: {Source}_{id} | ✅ |
| 3 | ucid | TEXT | 75 | ALL | Universal Campus ID | ✅ |
| 4 | building_ucid | TEXT | 100 | BLDG | Building-level UCID | ✅ |
| 5 | campus_id | TEXT | 100 | BLDG | Legacy campus ID (deprecated by ucid) | ⚠️ Review |
| 6 | source_unique_id | TEXT | 100 | BLDG | Original ID from source system | ✅ |

### Category 2: COMPANY/OWNERSHIP
| # | Field Name | Type | Length | Layer | Description | Keep? |
|---|-----------|------|--------|-------|-------------|-------|
| 7 | company_clean | TEXT | 100 | ALL | Standardized company name | ✅ |
| 8 | company_source | TEXT | 255 | ALL | Original company name from source | ✅ |
| 9 | company_clean_filter | TEXT | 100 | XB | Simplified company for XB filtering | ✅ XB only |
| 10 | developer | TEXT | 100 | ALL | Developer company (v2.0) | ✅ |
| 11 | tenant | TEXT | 100 | ALL | Tenant company (v2.0) | ✅ |
| 12 | end_user | TEXT | 100 | ALL | End user company (v2.0) | ✅ |
| 13 | developer_list | TEXT | 500 | CAMPUS | Aggregated developer list | ✅ Campus only |
| 14 | tenant_list | TEXT | 500 | CAMPUS | Aggregated tenant list | ✅ Campus only |
| 15 | end_user_list | TEXT | 500 | CAMPUS | Aggregated end user list | ✅ Campus only |

### Category 3: LOCATION
| # | Field Name | Type | Length | Layer | Description | Keep? |
|---|-----------|------|--------|-------|-------------|-------|
| 16 | campus_name | TEXT | 255 | ALL | Campus/facility name | ✅ |
| 17 | building_designation | TEXT | 100 | BLDG | Building number within campus | ✅ |
| 18 | address | TEXT | 255 | ALL | Street address | ✅ |
| 19 | city | TEXT | 100 | ALL | City name | ✅ |
| 20 | state | TEXT | 100 | ALL | State/province full name | ✅ |
| 21 | state_abbr | TEXT | 10 | ALL | State abbreviation | ✅ |
| 22 | county | TEXT | 128 | BLDG | County name | ⚠️ Sparse |
| 23 | postal_code | TEXT | 16 | BLDG | Zip/postal code | ⚠️ Sparse |
| 24 | country | TEXT | 100 | ALL | Country name | ✅ |
| 25 | region | TEXT | 20 | ALL | AMER, EMEA, APAC | ✅ |
| 26 | market | TEXT | 128 | BLDG | Market region | ⚠️ Sparse |
| 27 | latitude | DOUBLE | - | ALL | WGS84 latitude | ✅ |
| 28 | longitude | DOUBLE | - | ALL | WGS84 longitude | ✅ |
| 29 | gold_lat | DOUBLE | - | BLDG | Backup latitude | ❌ Redundant |
| 30 | gold_lon | DOUBLE | - | BLDG | Backup longitude | ❌ Redundant |

### Category 4: CAPACITY - POWER (MW)
| # | Field Name | Type | Length | Layer | Description | Keep? |
|---|-----------|------|--------|-------|-------------|-------|
| 31 | commissioned_power_mw | DOUBLE | - | ALL | Operational capacity (MW) | ✅ |
| 32 | uc_power_mw | DOUBLE | - | ALL | Under construction (MW) | ✅ |
| 33 | planned_power_mw | DOUBLE | - | ALL | Planned/announced (MW) | ✅ |
| 34 | planned_plus_uc_mw | DOUBLE | - | ALL | Planned + UC calculated | ⚠️ Derived |
| 35 | full_capacity_mw | DOUBLE | - | ALL | Total full-build capacity (MW) | ✅ PRIMARY |
| 36 | available_power_kw | DOUBLE | - | BLDG | Available for lease (kW) | ⚠️ Sparse |

### Category 5: CAPACITY - AREA
| # | Field Name | Type | Length | Layer | Description | Keep? |
|---|-----------|------|--------|-------|-------------|-------|
| 37 | facility_sqft | DOUBLE | - | ALL | Total facility area | ✅ |
| 38 | whitespace_sqft | DOUBLE | - | ALL | Data hall/raised floor area | ✅ |

### Category 6: CAPACITY - YEAR FORECAST (Semianalysis)
| # | Field Name | Type | Length | Layer | Description | Keep? |
|---|-----------|------|--------|-------|-------------|-------|
| 39 | mw_2023 | DOUBLE | - | BLDG/CAMPUS | 2023 capacity forecast | ✅ |
| 40 | mw_2024 | DOUBLE | - | BLDG/CAMPUS | 2024 capacity forecast | ✅ |
| 41 | mw_2025 | DOUBLE | - | BLDG/CAMPUS | 2025 capacity forecast | ✅ |
| 42 | mw_2026 | DOUBLE | - | BLDG/CAMPUS | 2026 capacity forecast | ✅ |
| 43 | mw_2027 | DOUBLE | - | BLDG/CAMPUS | 2027 capacity forecast | ✅ |
| 44 | mw_2028 | DOUBLE | - | BLDG/CAMPUS | 2028 capacity forecast | ✅ |
| 45 | mw_2029 | DOUBLE | - | BLDG/CAMPUS | 2029 capacity forecast | ✅ |
| 46 | mw_2030 | DOUBLE | - | BLDG/CAMPUS | 2030 capacity forecast | ✅ |
| 47 | mw_2031 | DOUBLE | - | BLDG/CAMPUS | 2031 capacity forecast | ✅ |
| 48 | mw_2032 | DOUBLE | - | BLDG/CAMPUS | 2032 capacity forecast | ✅ |

### Category 7: STATUS
| # | Field Name | Type | Length | Layer | Description | Keep? |
|---|-----------|------|--------|-------|-------------|-------|
| 49 | facility_status | TEXT | 50 | ALL | Current status | ✅ |
| 50 | cancelled | SHORT | - | ALL | Project cancelled (0/1) | ✅ |
| 51 | status_rank_tmp | SHORT | - | BLDG | Internal ranking | ❌ Internal only |

### Category 8: DATES/TIMELINE
| # | Field Name | Type | Length | Layer | Description | Keep? |
|---|-----------|------|--------|-------|-------------|-------|
| 52 | construction_start_date | DATE | - | ALL | Ground-breaking date | ✅ |
| 53 | construction_end_date | DATE | - | ALL | Construction completion | ✅ |
| 54 | actual_live_date | DATE | - | ALL | Operational go-live date | ✅ |
| 55 | announced | DATE | - | BLDG | Public announcement date | ⚠️ Sparse |
| 56 | land_acquisition | DATE | - | BLDG | Land purchase date | ⚠️ Sparse |
| 57 | permitting | DATE | - | BLDG | Permitting phase date | ⚠️ Sparse |
| 58 | construction_started | DATE | - | BLDG | Legacy construction start | ❌ Duplicate |
| 59 | cod | DATE | - | BLDG | Certificate of Occupancy | ⚠️ Sparse |
| 60 | lease_start_date | DATE | - | ALL | Lease start (v2.0) | ✅ |
| 61 | lease_end_date | DATE | - | ALL | Lease end (v2.0) | ✅ |
| 62 | data_vintage | DATE | - | ALL | Source data publish date | ✅ |
| 63 | date_reported | DATE | - | BLDG | Date info reported by vendor | ⚠️ Sparse |
| 64 | ingest_date | DATE | - | ALL | Record ingestion date | ✅ |

### Category 9: INFRASTRUCTURE
| # | Field Name | Type | Length | Layer | Description | Keep? |
|---|-----------|------|--------|-------|-------------|-------|
| 65 | pue | DOUBLE | - | ALL | Power Usage Effectiveness | ✅ |
| 66 | tier_design | TEXT | 32 | BLDG | Uptime Tier (I-IV) | ⚠️ Sparse |
| 67 | power_provider | TEXT | 128 | BLDG | Utility provider | ⚠️ Sparse |
| 68 | power_grid | TEXT | 128 | BLDG | Grid connection details | ⚠️ Sparse |
| 69 | feed_config | TEXT | 16 | BLDG | Power feed config (2N, N+1) | ⚠️ Sparse |
| 70 | substation_count | SHORT | - | BLDG | Number of substations | ⚠️ Sparse |
| 71 | onsite_substation | SHORT | - | BLDG | Has onsite substation (0/1) | ⚠️ Sparse |

### Category 10: CLASSIFICATION
| # | Field Name | Type | Length | Layer | Description | Keep? |
|---|-----------|------|--------|-------|-------------|-------|
| 72 | type_category | TEXT | 32 | BLDG | Hyperscale/Colo/Enterprise/Edge | ⚠️ Sparse |
| 73 | owned_leased | TEXT | 32 | BLDG | Ownership model | ⚠️ Sparse |
| 74 | building_type | TEXT | 50 | BLDG | Building classification | ❌ Redundant |
| 75 | purpose | TEXT | 32 | BLDG | Primary purpose | ⚠️ Sparse |

### Category 11: ENERGY (v2.0)
| # | Field Name | Type | Length | Layer | Description | Keep? |
|---|-----------|------|--------|-------|-------------|-------|
| 76 | energy_source | TEXT | 50 | ALL | Energy source type | ✅ |
| 77 | ai_gpu_indicator | TEXT | 20 | ALL | AI/GPU workload indicator | ✅ |

### Category 12: COSTS & LAND
| # | Field Name | Type | Length | Layer | Description | Keep? |
|---|-----------|------|--------|-------|-------------|-------|
| 78 | total_cost_usd_million | DOUBLE | - | ALL | Total project cost ($M) | ✅ |
| 79 | land_cost_usd_million | DOUBLE | - | ALL | Land acquisition cost ($M) | ✅ |
| 80 | total_site_acres | DOUBLE | - | ALL | Total site acreage | ✅ |
| 81 | data_center_acres | DOUBLE | - | ALL | DC footprint acreage | ✅ |

### Category 13: ECOSYSTEM (DCH specialty)
| # | Field Name | Type | Length | Layer | Description | Keep? |
|---|-----------|------|--------|-------|-------------|-------|
| 82 | ecosystem_ixps | SHORT | - | BLDG | IXP connections | ⚠️ Sparse |
| 83 | ecosystem_cloud | SHORT | - | BLDG | Cloud provider presence | ⚠️ Sparse |
| 84 | ecosystem_children | SHORT | - | BLDG | Child facilities | ⚠️ Sparse |
| 85 | ecosystem_networkproviders | SHORT | - | BLDG | Network providers | ⚠️ Sparse |
| 86 | ecosystem_networkpresence | SHORT | - | BLDG | Network presence score | ⚠️ Sparse |
| 87 | ecosystem_serviceproviders | SHORT | - | BLDG | Service providers | ⚠️ Sparse |

### Category 14: CAMPUS AGGREGATES
| # | Field Name | Type | Length | Layer | Description | Keep? |
|---|-----------|------|--------|-------|-------------|-------|
| 88 | building_count | LONG | - | CAMPUS/XB | Buildings in campus | ✅ |
| 89 | source_count | LONG | - | CAMPUS | Data sources for campus | ✅ |

### Category 15: SOURCE TRACKING
| # | Field Name | Type | Length | Layer | Description | Keep? |
|---|-----------|------|--------|-------|-------------|-------|
| 90 | source | TEXT | 200 | ALL | Data source name(s) | ✅ |
| 91 | source_id | TEXT | 100 | BLDG | Source record ID | ✅ |

### Category 16: FLAGS
| # | Field Name | Type | Length | Layer | Description | Keep? |
|---|-----------|------|--------|-------|-------------|-------|
| 92 | is_essential | SHORT | - | ALL | Essential DC flag (0/1) | ✅ |

### Category 17: NOTES/METADATA
| # | Field Name | Type | Length | Layer | Description | Keep? |
|---|-----------|------|--------|-------|-------------|-------|
| 93 | notes | TEXT | 1000 | ALL | General notes | ✅ |
| 94 | additional_references | TEXT | 512 | BLDG | URLs, references | ⚠️ Sparse |

---

## Recommendations

### Fields to DEPRECATE (remove from schema)
| Field | Reason |
|-------|--------|
| gold_lat, gold_lon | Redundant with latitude/longitude |
| building_type | Overlaps with type_category |
| construction_started | Duplicate of construction_start_date |
| status_rank_tmp | Internal processing only |

### Fields to KEEP IN BUILDINGS ONLY (not XB)
| Field | Reason |
|-------|--------|
| ecosystem_* fields | DCH-specific, low general utility |
| county, postal_code | Sparse, detail-level data |
| tier_design, feed_config | Sparse infrastructure details |
| announced, permitting, cod | Sparse timeline milestones |

### XB Layer Optimization
The XB layer (42 fields) is already well-optimized for visualization. The current field set is appropriate.

---

## Proposed Field Order for Attribute Tables

To make navigating attribute tables easier, fields should be ordered by category:

1. **Record Identification** - record_level, ucid, building_ucid, unique_id
2. **Company** - company_clean, company_clean_filter, developer, tenant, end_user
3. **Location** - campus_name, address, city, state, state_abbr, country, region, lat, lon
4. **Power Capacity** - commissioned_power_mw, uc_power_mw, planned_power_mw, full_capacity_mw
5. **Area** - facility_sqft, whitespace_sqft
6. **Status** - facility_status, cancelled, is_essential
7. **Dates** - construction_start_date, actual_live_date, data_vintage, ingest_date
8. **Energy** - energy_source, ai_gpu_indicator, pue
9. **Costs** - total_cost_usd_million, land_cost_usd_million
10. **Land** - total_site_acres, data_center_acres
11. **Aggregates** - building_count, source_count
12. **Source** - source, source_id
13. **Notes** - notes

---

## Implementation Notes

### Reorganizing Field Order in ArcGIS
ArcGIS does not allow direct field reordering. Options:
1. **Export/Import** - Export to new FC with fields in desired order
2. **Field Maps** - Use field mapping during export
3. **Script-based recreation** - Recreate FC with ordered schema

### Script Updates Required
To implement reorganized field order:
1. Update `validate_gold_build_schema.py` with ordered GOLD_BUILDINGS_SCHEMA
2. Update `create_xb_combined_layer.py` UNIFIED_SCHEMA
3. Update campus_rollup_new.py insert_fields order
4. Recreate feature classes with new field order

---

*Document generated by schema audit process*
