# NPM Data Source Comparison: Manual CSV vs. Hive API

**Created:** 2026-01-21
**Purpose:** Compare field schemas between manual CSV export and new Hive API
**Hive Table:** `test_idc_lsim_s_npm_data_center_data`
**DaiQuery:** https://fburl.com/daiquery/usokh4m8

---

## Current Manual CSV Schema (NPM_DC_1_15_2026.csv)

From our `import_npm_csv.py` script - 24 fields from CSV + 2 derived:

| # | CSV Column | ArcGIS Field | Type | Notes |
|---|------------|--------------|------|-------|
| 1 | Project | Project | TEXT(255) | Project/facility name |
| 2 | Organizations | Organizations | TEXT(500) | Company/partners (pipe-separated) |
| 3 | Status | Status | TEXT(50) | Operational, Planned, Under Construction |
| 4 | Total MWs | Total_MWs | DOUBLE | Power capacity |
| 5 | Building Size (sq ft) | Building_Size__sq_ft_ | TEXT(50) | Has "M" suffix for millions |
| 6 | Land Size (acre) | Land_Size__acre_ | DOUBLE | Acreage |
| 7 | Planned Operation Date | Planned_Operation_Date | DATE | Target live date |
| 8 | Country | Country | TEXT(100) | Country name |
| 9 | State / Region | State___Region | TEXT(100) | State or region |
| 10 | County | County | TEXT(100) | County name |
| 11 | Onsite Generation (MW) | Onsite_Generation__MW_ | DOUBLE | On-site power gen |
| 12 | Backup Generation (MW) | Backup_Generation__MW_ | DOUBLE | Backup power gen |
| 13 | Lat/Lon | Lat_Lon | TEXT(100) | Combined "lat, lon" string |
| 14 | — | Lat_Lon_Y | DOUBLE | **Derived:** Parsed latitude |
| 15 | — | Lat_Lon_X | DOUBLE | **Derived:** Parsed longitude |
| 16 | Location | Location | TEXT(500) | Address/location description |
| 17 | Coordinates Precision | Coordinates_Precision | TEXT(50) | "project", "approximate", etc. |
| 18 | Sectors | Sectors | TEXT(255) | Industry sectors |
| 19 | Applications | Applications | TEXT(255) | Use cases |
| 20 | Cost | Cost | TEXT(100) | Investment cost string |
| 21 | Documents | Documents | LONG | Document count |
| 22 | Key People | Key_People | LONG | Key people count |
| 23 | Signals | Signals | LONG | Signal count |
| 24 | Created | Created | DATE | Record creation date |
| 25 | Modified | Modified | DATE | Last modified date |
| 26 | Audiences | Audiences | TEXT(50) | Audience type (e.g., "DC") |

**Total:** 26 fields (24 from CSV + 2 derived lat/lon)

---

## Hive API Schema (`test_idc_lsim_s_npm_data_center_data`)

**Source:** DaiQuery sample export (2026-01-21)
**Total Fields:** 30

| # | Hive Column | Type | Notes |
|---|-------------|------|-------|
| 1 | project_name | STRING | Project/facility name |
| 2 | data_center_id | STRING | **NEW** - Unique DC identifier |
| 3 | total_mw | DOUBLE | Power capacity |
| 4 | country | STRING | Country name |
| 5 | state | STRING | State name |
| 6 | city | STRING | **NEW** - City (parsed) |
| 7 | county | STRING | County name |
| 8 | organizations | JSON | Company/partners with roles (JSON array) |
| 9 | status | JSON | Status with ID (JSON array) |
| 10 | geo_lat | DOUBLE | **NEW** - Already parsed latitude |
| 11 | geo_lon | DOUBLE | **NEW** - Already parsed longitude |
| 12 | geo_default_value | STRING | Precision indicator |
| 13 | location_id | STRING | **NEW** - Location unique ID |
| 14 | location_identifier | STRING | Location description |
| 15 | location_is_approximate | BOOLEAN | **NEW** - Explicit approximate flag |
| 16 | location_lat | DOUBLE | Location latitude |
| 17 | location_lng | DOUBLE | Location longitude |
| 18 | location_city | STRING | Parsed city |
| 19 | location_state | STRING | State full name |
| 20 | location_state_code | STRING | **NEW** - State abbreviation |
| 21 | location_country | STRING | Country full name |
| 22 | location_country_code | STRING | **NEW** - Country code (us, etc.) |
| 23 | location_continent | STRING | **NEW** - Continent name |
| 24 | location_county | STRING | County name |
| 25 | location_full | JSON | **NEW** - Full geocoded location JSON |
| 26 | regions | JSON | **NEW** - Region identifiers |
| 27 | sectors | JSON | Industry sectors |
| 28 | extraction_date | DATE | **NEW** - Data extraction date |
| 29 | created | TIMESTAMP | Record creation timestamp |
| 30 | ds | DATE | **NEW** - Partition date |

---

## Field Comparison

### ✅ Fields in BOTH Sources (Equivalent)

| Concept | CSV Field | Hive Field | Match Quality |
|---------|-----------|------------|---------------|
| Project Name | Project | project_name | ✅ Exact |
| Company | Organizations | organizations | ⚠️ Hive is JSON with roles |
| Status | Status | status | ⚠️ Hive is JSON array |
| Power (MW) | Total MWs | total_mw | ✅ Exact |
| Country | Country | country | ✅ Exact |
| State | State / Region | state | ✅ Exact |
| County | County | county | ✅ Exact |
| Latitude | Lat/Lon (parsed) | geo_lat | ✅ **Better** - pre-parsed |
| Longitude | Lat/Lon (parsed) | geo_lon | ✅ **Better** - pre-parsed |
| Location | Location | location_identifier | ✅ Exact |
| Coord Precision | Coordinates Precision | geo_default_value | ✅ Similar |
| Sectors | Sectors | sectors | ⚠️ Hive is JSON |
| Created Date | Created | created | ✅ Exact |

### ❌ Fields ONLY in CSV (Missing from Hive)

| CSV Field | Impact if Missing | Severity |
|-----------|-------------------|----------|
| Building Size (sq ft) | Lose facility size data | 🔴 High |
| Land Size (acre) | Lose land acreage | 🟡 Medium |
| Planned Operation Date | Lose COD/target date | 🔴 High |
| Onsite Generation (MW) | Lose on-site power data | 🟡 Medium |
| Backup Generation (MW) | Lose backup power data | 🟡 Medium |
| Cost | Lose investment cost | 🔴 High |
| Applications | Lose use case info | 🟢 Low |
| Documents | Lose doc count | 🟢 Low |
| Key People | Lose people count | 🟢 Low |
| Signals | Lose signal count | 🟢 Low |
| Modified | Lose last modified date | 🟡 Medium |
| Audiences | Lose audience type | 🟢 Low |

### 🆕 Fields ONLY in Hive (NEW DATA!)

| Hive Field | Potential Value | Priority |
|------------|-----------------|----------|
| **data_center_id** | Unique ID for deduplication/matching | 🔴 High |
| **city** | Pre-parsed city name (no parsing needed) | 🔴 High |
| **geo_lat / geo_lon** | Pre-parsed coordinates (no parsing needed) | 🔴 High |
| **location_state_code** | State abbreviation (e.g., TX, KY) | 🟡 Medium |
| **location_country_code** | Country code (e.g., us) | 🟡 Medium |
| **location_continent** | Continent (e.g., North America) | 🟡 Medium |
| **location_is_approximate** | Explicit flag for coordinate precision | 🟡 Medium |
| **location_id** | Unique location identifier | 🟡 Medium |
| **location_full** | Full geocoded JSON with components | 🟢 Low |
| **regions** | Region identifiers (JSON) | 🟢 Low |
| **extraction_date** | When data was extracted | 🟢 Low |
| **ds** | Partition date for Hive | 🟢 Low |
| **organizations.role** | Role info (developer, offtaker, etc.) | 🔴 High |

---

## 🔑 Key Findings

### Hive Advantages (Why Switch)
1. **Pre-parsed coordinates** - `geo_lat`/`geo_lon` already split (no parsing needed)
2. **Pre-parsed city** - `city` field extracted (no parsing from Location)
3. **State abbreviation** - `location_state_code` ready to use
4. **Unique identifiers** - `data_center_id` and `location_id` for matching
5. **Organization roles** - JSON includes role (developer, offtaker, etc.) — maps to our v2.0 `developer`, `tenant` fields!
6. **Automated refresh** - No manual CSV export needed

### CSV Advantages (What's Missing from Hive)
1. **Building Size** - Critical capacity metric not in Hive
2. **Land Size** - Site acreage not in Hive
3. **Planned Operation Date** - Target COD not in Hive
4. **Cost** - Investment amount not in Hive
5. **Power generation** - On-site/backup generation not in Hive

---

## Recommendations

### 🎯 Recommended Approach: HYBRID

Use **Hive as primary source** but **request missing fields** be added to the Hive pipeline.

#### Immediate Actions:
1. **Request these fields be added to Hive** (high-value gaps):
   - `building_size_sqft` - Building Size (sq ft)
   - `land_size_acres` - Land Size (acre)
   - `planned_operation_date` - Planned Operation Date / COD
   - `cost` - Investment cost
   - `onsite_generation_mw` - On-site power generation
   - `backup_generation_mw` - Backup power generation

2. **Create Hive ingestion script** using existing fields:
   - Use `geo_lat`/`geo_lon` (no parsing needed)
   - Use `city`, `location_state_code` (pre-parsed)
   - Parse `organizations` JSON to extract `developer` role
   - Use `data_center_id` as `source_unique_id`

3. **Continue CSV supplement** until Hive parity is achieved

#### Value of Organization Roles (JSON)
The Hive `organizations` field contains structured role data:
```json
[
  {"identifier": "AMD", "id": "...", "role": "offtaker"},
  {"identifier": "Riot Platforms", "id": "...", "role": "developer"}
]
```

This maps directly to our v2.0 schema fields:
- `role: "developer"` → `developer` field
- `role: "offtaker"` → `tenant` or `end_user` field

**This is a major value-add the CSV doesn't have!**

---

## Next Steps

1. [x] ~~Get Hive schema from DaiQuery results~~ ✅ Done
2. [x] ~~Complete field-by-field comparison~~ ✅ Done
3. [x] ~~Identify unique fields in each source~~ ✅ Done
4. [ ] Request missing fields from GIS dev team
5. [ ] Create `fetch_npm_hive.py` script
6. [ ] Update `DATA_SOURCE_API_CONNECTIONS.md` with NPM Hive details
7. [ ] Test hybrid approach (Hive + CSV supplement)

---

## Notes

- Hive table name: `test_idc_lsim_s_npm_data_center_data`
- "test_" prefix suggests this may be a dev/staging table
- Check with GIS dev team if there's a production table name
- Confirm refresh cadence of Hive table
