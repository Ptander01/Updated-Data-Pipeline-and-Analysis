# NPM Schema Comparison: Manual CSV vs. Hive API

**Created:** 2026-02-09
**Updated:** 2026-02-09 (with actual Hive schema from GSheet exports)
**Purpose:** Compare field schemas for both NPM datasets across manual CSV export and Hive API
**Author:** Meta Data Center GIS Team

---

## Overview

This document compares schemas for **two NPM (New Project Media) datasets**:

1. **Data Centers** - Physical data center facility records
2. **Market Signals** - News, filings, and activity signals

Each dataset has two ingestion methods:
- **Manual CSV** - Exported from NPM website
- **Hive API** - Queried from internal Meta Hive tables

---

## Dataset 1: NPM Data Centers

### Source Information

| Aspect | Manual CSV | Hive API |
|--------|------------|----------|
| **File/Table** | `NPM_DC_1_15_2026.csv` | `test_idc_lsim_s_npm_data_center_data` |
| **DaiQuery** | N/A | `select * from test_idc_lsim_s_npm_data_center_data` |
| **Records** | ~1,568 | ~254 |
| **Field Count** | 24 | **36** |

### Manual CSV Schema (24 fields)

| # | Field Name | Type | Example | Notes |
|---|------------|------|---------|-------|
| 1 | `Project` | TEXT | "Microsoft Corporation – FTY01 Data Centers" | Project/facility name |
| 2 | `Organizations` | TEXT | "Microsoft Corporation" | Company/partners (pipe-separated) |
| 3 | `Status` | TEXT | "Planned", "Operational", "Under Construction" | Facility status |
| 4 | `Total MWs` | DOUBLE | 900 | Power capacity in MW |
| 5 | `Building Size (sq ft)` | TEXT | "3.90M", "399,987.08" | Has "M" suffix for millions |
| 6 | `Land Size (acre)` | DOUBLE | 468.14 | Land acreage |
| 7 | `Planned Operation Date` | DATE | "9/7/2025" | Target COD |
| 8 | `Country` | TEXT | "United States" | Country name |
| 9 | `State / Region` | TEXT | "Virginia", "Georgia" | State or region |
| 10 | `County` | TEXT | "Hanover", "Douglas" | County name |
| 11 | `Onsite Generation (MW)` | DOUBLE | - | On-site power generation |
| 12 | `Backup Generation (MW)` | DOUBLE | - | Backup power generation |
| 13 | `Lat/Lon` | TEXT | "33.7304868, -84.6176057" | Combined lat,lon string |
| 14 | `Location` | TEXT | "Kansas City Star Building, 1601 McGee Street..." | Full address/location |
| 15 | `Coordinates Precision` | TEXT | "project", "approximate" | Geocoding precision |
| 16 | `Sectors` | TEXT | - | Industry sectors |
| 17 | `Applications` | TEXT | - | Use cases |
| 18 | `Cost` | TEXT | "USD 700M", "USD 1,000M" | Investment cost string |
| 19 | `Documents` | INT | 1, 2, 5 | Document count |
| 20 | `Key People` | INT | 0 | Key people count |
| 21 | `Signals` | INT | 1, 5 | Related signal count |
| 22 | `Created` | DATE | "1/15/2026" | Record creation date |
| 23 | `Modified` | DATE | "1/15/2026" | Last modified date |
| 24 | `Audiences` | TEXT | "DC" | Audience type |

### Hive API Schema (36 fields) ✅ VERIFIED FROM GSHEET EXPORT

*Source: `New Project Media Test API data Pulls - Data Center Output.csv` (from Hive table `test_idc_lsim_s_npm_data_center_data`)*

| # | Field Name | Type | Example | Notes |
|---|------------|------|---------|-------|
| 1 | `project_name` | STRING | "Google - Redhawk Mesa Data Center Campus" | Project/facility name |
| 2 | `data_center_id` | STRING | "2KRRMLTtGcEhv2CtcwxThv" | ✅ Unique DC identifier |
| 3 | `total_mw` | DOUBLE | 2262 | Power capacity |
| 4 | `country` | STRING | "United States" | Country name |
| 5 | `state` | STRING | "Arizona", "Louisiana" | State name |
| 6 | `city` | STRING | "Mesa", "Holly Ridge" | ✅ Pre-parsed city |
| 7 | `county` | STRING | "Maricopa", "Richland Parish" | County name |
| 8 | `organizations` | JSON | `[{"identifier": "Google", "role": "developer"}...]` | Company/partners with roles |
| 9 | `status` | JSON | `[{"identifier": "Planned", "id": "inDevelopment"}]` | Status with ID |
| 10 | `geo_lat` | DOUBLE | 33.3498037 | ✅ Pre-parsed latitude |
| 11 | `geo_lon` | DOUBLE | -111.5893804 | ✅ Pre-parsed longitude |
| 12 | `geo_default_value` | STRING | "project" | Precision indicator |
| 13 | `location_id` | STRING | "9tbtsxphdyp0n48hwhzd" | ✅ Location unique ID |
| 14 | `location_identifier` | STRING | "East Elliot Road, Mesa, AZ 85212..." | Location description |
| 15 | `location_is_approximate` | BOOLEAN | (empty) | Approximate flag |
| 16 | `location_lat` | DOUBLE | 33.3498037 | Location latitude |
| 17 | `location_lng` | DOUBLE | -111.5893804 | Location longitude |
| 18 | `location_city` | STRING | "Mesa" | Parsed city |
| 19 | `location_state` | STRING | "Arizona" | State full name |
| 20 | `location_state_code` | STRING | "AZ", "LA" | ✅ State abbreviation |
| 21 | `location_country` | STRING | "United States of America" | Country full name |
| 22 | `location_country_code` | STRING | "us" | ✅ Country code |
| 23 | `location_continent` | STRING | "North America" | ✅ Continent name |
| 24 | `location_county` | STRING | "Maricopa County" | County name |
| 25 | `location_full` | JSON | Full geocoded location object | ✅ Complete geocode JSON |
| 26 | `regions` | JSON | `[{"identifier": "NA", "id": "NA"}]` | Region identifiers |
| 27 | `sectors` | JSON | (empty in DC data) | Industry sectors |
| 28 | `extraction_date` | DATE | "2026-01-30" | ✅ Data extraction date |
| 29 | `created` | TIMESTAMP | "2026-01-30T15:08:26.846Z" | Record creation timestamp |
| 30 | `building_square_foot` | DOUBLE | 750000, 3999978.472 | ✅ **BUILDING SIZE EXISTS!** |
| 31 | `land_acre` | DOUBLE | 2250 | ✅ **LAND SIZE EXISTS!** |
| 32 | `planned_operational_date` | DATE | "2030-01-01" | ✅ **COD EXISTS!** |
| 33 | `cost_value` | DOUBLE | 10000000000 | ✅ **COST EXISTS!** (in raw units) |
| 34 | `cost_unit` | STRING | "usd" | Cost currency unit |
| 35 | `onsite_generation` | JSON | (empty) | On-site generation data |
| 36 | `backup_generation` | JSON | `{"value": 3.5, "unit": "MW", ...}` | ✅ **BACKUP GEN EXISTS!** |
| 37 | `ds` | DATE | "2026-01-29" | Partition date |

**🎉 MAJOR FINDING:** The Hive API **DOES include** the critical fields previously thought to be missing:
- `building_square_foot` ✅
- `land_acre` ✅
- `planned_operational_date` ✅
- `cost_value` + `cost_unit` ✅
- `backup_generation` ✅ (as JSON with value/unit)

### Data Centers: Field Comparison

#### ✅ Fields in BOTH Sources (Full Parity Achieved!)

| Concept | CSV Field | Hive Field | Match Quality |
|---------|-----------|------------|---------------|
| Project Name | `Project` | `project_name` | ✅ Exact |
| Company | `Organizations` | `organizations` | ⚠️ Hive is JSON with roles |
| Status | `Status` | `status` | ⚠️ Hive is JSON array |
| Power (MW) | `Total MWs` | `total_mw` | ✅ Exact |
| Building Size | `Building Size (sq ft)` | `building_square_foot` | ✅ **BOTH HAVE IT!** |
| Land Size | `Land Size (acre)` | `land_acre` | ✅ **BOTH HAVE IT!** |
| COD | `Planned Operation Date` | `planned_operational_date` | ✅ **BOTH HAVE IT!** |
| Cost | `Cost` | `cost_value` + `cost_unit` | ✅ **BOTH HAVE IT!** (Hive is structured) |
| Backup Gen | `Backup Generation (MW)` | `backup_generation` | ✅ **BOTH HAVE IT!** (Hive is JSON) |
| On-site Gen | `Onsite Generation (MW)` | `onsite_generation` | ✅ Both (Hive may be sparse) |
| Country | `Country` | `country` | ✅ Exact |
| State | `State / Region` | `state` | ✅ Exact |
| County | `County` | `county` | ✅ Exact |
| Latitude | `Lat/Lon` (parsed) | `geo_lat` | ✅ **Better** - pre-parsed |
| Longitude | `Lat/Lon` (parsed) | `geo_lon` | ✅ **Better** - pre-parsed |
| Location | `Location` | `location_identifier` | ✅ Exact |
| Coord Precision | `Coordinates Precision` | `geo_default_value` | ✅ Similar |
| Sectors | `Sectors` | `sectors` | ⚠️ Hive is JSON |
| Created Date | `Created` | `created` | ✅ Exact |

#### ❌ Fields ONLY in Manual CSV (Minor Gaps)

| CSV Field | Impact | Severity |
|-----------|--------|----------|
| `Applications` | Lose use case info | 🟢 Low |
| `Documents` | Lose doc count | 🟢 Low |
| `Key People` | Lose people count | 🟢 Low |
| `Signals` | Lose signal count | 🟢 Low |
| `Modified` | Lose last modified date | 🟡 Medium |
| `Audiences` | Lose audience type | 🟢 Low |

#### 🆕 Fields ONLY in Hive (New Data!)

| Hive Field | Potential Value | Priority |
|------------|-----------------|----------|
| `data_center_id` | Unique ID for deduplication/matching | 🔴 **HIGH** |
| `city` | Pre-parsed city name | 🔴 **HIGH** |
| `geo_lat` / `geo_lon` | Pre-parsed coordinates (no parsing!) | 🔴 **HIGH** |
| `location_state_code` | State abbreviation (AZ, LA, VA) | 🟡 Medium |
| `location_country_code` | Country code (us) | 🟡 Medium |
| `location_continent` | Continent (North America) | 🟡 Medium |
| `location_is_approximate` | Explicit precision flag | 🟡 Medium |
| `location_id` | Unique location ID | 🟡 Medium |
| `location_full` | Complete geocoded JSON with components | 🟡 Medium |
| `organizations.role` | **Developer/EPC/Utility roles** | 🔴 **HIGH** |
| `cost_unit` | Currency unit (usd) | 🟢 Low |
| `regions` | Region identifiers (JSON) | 🟢 Low |
| `extraction_date` | Data extraction date | 🟢 Low |
| `ds` | Partition date | 🟢 Low |

---

## Dataset 2: NPM Market Signals

### Source Information

| Aspect | Manual CSV | Hive API |
|--------|------------|----------|
| **File/Table** | `signal (4).csv` | `test_idc_lsim_s_npm_signal_data` |
| **DaiQuery** | N/A | `select * from test_idc_lsim_s_npm_signal_data` |
| **Records** | ~2,000 | ~4,785 |
| **Field Count** | 22 | **20** |

### Manual CSV Schema (22 fields)

| # | Field Name | Type | Example | Notes |
|---|------------|------|---------|-------|
| 1 | `publishedDate` | TEXT | "10:31 am" | Time of publication |
| 2 | `filingDate` | DATE | "02/01/2026" | Filing/publication date |
| 3 | `headline` | TEXT | "SCE queue updated; 2 new renewable applications" | Signal headline |
| 4 | `organizations-advisors` | TEXT | - | Advisor organizations |
| 5 | `organizations-developers` | TEXT | "Solar Liberty", "Panattoni" | Developer organizations |
| 6 | `organizations-epcs` | TEXT | "McKenna \| Fishbeck" | EPC contractors |
| 7 | `organizations-isortos` | TEXT | - | ISO/RTO organizations |
| 8 | `organizations-offtakers` | TEXT | - | Offtaker organizations |
| 9 | `organizations-pucs` | TEXT | - | PUC organizations |
| 10 | `organizations-utilities` | TEXT | "DTE Electric", "PG&E" | Utility organizations |
| 11 | `type` | TEXT | "Queue Filings - Queue Update", "Local Watch - Meeting" | Signal type |
| 12 | `sectors` | TEXT | "Solar \| Storage", "Data Center" | Industry sectors (pipe-separated) |
| 13 | `state` | TEXT | "California", "Michigan" | State name |
| 14 | `county` | TEXT | "Eaton - MI", "Wayne - MI" | County with state suffix |
| 15 | `country` | TEXT | - | Country (often blank for US) |
| 16 | `mw` | DOUBLE | 200 | Power capacity in MW |
| 17 | `keyPeople` | TEXT | - | Key people involved |
| 18 | `documents` | TEXT | "Agenda \| Minutes \| Packet" | Document types (pipe-separated) |
| 19 | `facilityAddress` | TEXT | - | Facility address |
| 20 | `projects` | TEXT | "Las Camas Solar Project" | Related project names |
| 21 | `location` | TEXT | "36.7014631, -118.755997" | Combined lat,lon string |
| 22 | `commercialOperationDate` | DATE | - | COD date |

### Hive API Schema (20 fields) ✅ VERIFIED FROM GSHEET EXPORT

*Source: `New Project Media Test API data Pulls - MArket Signals Output.csv` (from Hive table `test_idc_lsim_s_npm_signal_data`)*

| # | Field Name | Type | Example | Notes |
|---|------------|------|---------|-------|
| 1 | `signal_id` | STRING | "4BWanm9S3675izEGna9A12" | ✅ **Unique signal ID** |
| 2 | `headline` | STRING | "Dayton City Plan Board to discuss text amendments..." | Signal headline |
| 3 | `body` | TEXT | Full HTML body content | ✅ **NEW** - Full signal body text |
| 4 | `filing_date` | DATE | "2026-01-13" | Filing date |
| 5 | `published_date` | TIMESTAMP | "2025-12-31T08:24:55.826Z" | ✅ Full timestamp (vs time-only in CSV) |
| 6 | `commercial_operation_date` | DATE | - | COD date |
| 7 | `mw` | DOUBLE | 200 | Power capacity |
| 8 | `type_id` | STRING | "LOCAL_WATCH", "COMPANY_FILINGS" | ✅ **NEW** - Signal type ID |
| 9 | `type_identifier` | STRING | "Local Watch", "Company Filings" | Signal type name |
| 10 | `geo_lat` | DOUBLE | 39.7589478 | ✅ Pre-parsed latitude |
| 11 | `geo_lon` | DOUBLE | -84.1916069 | ✅ Pre-parsed longitude |
| 12 | `geo_default_value` | STRING | "location" | Precision indicator |
| 13 | `sectors` | JSON | `[{'identifier': 'Data Center', 'id': '...'}]` | Industry sectors (JSON) |
| 14 | `states` | JSON | `[{'identifier': 'Ohio', 'id': '...'}]` | ✅ State with ID (JSON) |
| 15 | `counties` | JSON | `[{'identifier': 'Montgomery - OH', 'id': '...'}]` | County with ID (JSON) |
| 16 | `projects` | JSON | `[]` or project references | Related projects (JSON) |
| 17 | `organizations` | JSON | `[{"id": "...", "role": "meetingHost", "identifier": "PJM"}]` | ✅ Orgs with roles (JSON) |
| 18 | `extraction_date` | DATE | "2026-01-30" | Data extraction date |
| 19 | `record_url` | STRING | "https://app.newprojectmedia.com/view/signals/..." | ✅ **NEW** - Direct link to signal |
| 20 | `ds` | DATE | "2026-01-29" | Partition date |

### Market Signals: Field Comparison

#### ✅ Fields in BOTH Sources

| Concept | CSV Field | Hive Field | Match Quality |
|---------|-----------|------------|---------------|
| Headline | `headline` | `headline` | ✅ Exact |
| Filing Date | `filingDate` | `filing_date` | ✅ Exact |
| Published Date | `publishedDate` | `published_date` | ✅ **Better** - full timestamp |
| Signal Type | `type` | `type_identifier` | ✅ Exact |
| Sectors | `sectors` | `sectors` | ⚠️ Hive is JSON |
| State | `state` | `states` | ⚠️ Hive is JSON array |
| County | `county` | `counties` | ⚠️ Hive is JSON array |
| MW Capacity | `mw` | `mw` | ✅ Exact |
| Latitude | `location` (parsed) | `geo_lat` | ✅ **Better** - pre-parsed |
| Longitude | `location` (parsed) | `geo_lon` | ✅ **Better** - pre-parsed |
| COD | `commercialOperationDate` | `commercial_operation_date` | ✅ Exact |
| Projects | `projects` | `projects` | ⚠️ Hive is JSON |
| Organizations | 7 separate columns | `organizations` | ⚠️ Hive is single JSON |

#### ❌ Fields ONLY in Manual CSV

| CSV Field | Impact | Severity |
|-----------|--------|----------|
| `organizations-advisors` | Separate column per role | 🟡 Medium (can parse from Hive JSON) |
| `organizations-developers` | Separate column per role | 🟡 Medium |
| `organizations-epcs` | Separate column per role | 🟡 Medium |
| `organizations-isortos` | Separate column per role | 🟡 Medium |
| `organizations-offtakers` | Separate column per role | 🟡 Medium |
| `organizations-pucs` | Separate column per role | 🟡 Medium |
| `organizations-utilities` | Separate column per role | 🟡 Medium |
| `keyPeople` | Key people involved | 🟢 Low |
| `documents` | Document types | 🟢 Low |
| `facilityAddress` | Facility address | 🟢 Low |
| `country` | Country name | 🟢 Low (usually blank for US) |

#### 🆕 Fields ONLY in Hive (New Data!)

| Hive Field | Potential Value | Priority |
|------------|-----------------|----------|
| `signal_id` | **Unique ID** for deduplication | 🔴 **HIGH** |
| `body` | **Full signal body text** (HTML) | 🔴 **HIGH** |
| `type_id` | Signal type ID for filtering | 🟡 Medium |
| `geo_lat` / `geo_lon` | Pre-parsed coordinates | 🔴 **HIGH** |
| `record_url` | **Direct link to NPM signal** | 🔴 **HIGH** |
| `organizations.role` | Structured roles (meetingHost, meetingAttendee, etc.) | 🟡 Medium |
| `extraction_date` | Data extraction date | 🟢 Low |
| `ds` | Partition date | 🟢 Low |

#### 🔑 Key Difference: Organization Structure

**CSV** has 7 separate columns for org roles:
```
organizations-advisors, organizations-developers, organizations-epcs,
organizations-isortos, organizations-offtakers, organizations-pucs, organizations-utilities
```

**Hive** consolidates into a single JSON field with different role types:
```json
[
  {"id": "5efcdf1e36f87e001523b645", "role": "meetingHost", "identifier": "PJM Interconnection"},
  {"id": "5f037046bc02e10015b4f931", "role": "meetingAttendee", "identifier": "American Electric Power (AEP)"},
  {"id": "5f29a16577bbc90018a86af6", "role": "meetingParticipant", "identifier": "Public Service Enterprise Group (PSEG)"}
]
```

**Notable:** Hive has additional role types not in CSV:
- `meetingHost` (meeting organizer)
- `meetingAttendee` (attendees)
- `meetingParticipant` (participants)

**Impact:**
- CSV is easier for filtering by role (separate columns)
- Hive has richer role data but requires JSON parsing

---

## Summary Comparison Matrix

### Field Coverage by Source (UPDATED with actual Hive data)

| Field Category | DC CSV | DC Hive | Signal CSV | Signal Hive |
|----------------|:------:|:-------:|:----------:|:-----------:|
| **Unique ID** | ❌ | ✅ `data_center_id` | ❌ | ✅ `signal_id` |
| **Project/Headline** | ✅ | ✅ | ✅ | ✅ |
| **Full Body Text** | ❌ | ❌ | ❌ | ✅ `body` |
| **Record URL** | ❌ | ❌ | ❌ | ✅ `record_url` |
| **Organizations** | ✅ (text) | ✅ (JSON+roles) | ✅ (7 columns) | ✅ (JSON+roles) |
| **Status/Type** | ✅ | ✅ (JSON) | ✅ | ✅ + `type_id` |
| **MW Capacity** | ✅ | ✅ | ✅ | ✅ |
| **Building Size** | ✅ | ✅ `building_square_foot` | N/A | N/A |
| **Land Size** | ✅ | ✅ `land_acre` | N/A | N/A |
| **Cost** | ✅ (string) | ✅ `cost_value` + `cost_unit` | N/A | N/A |
| **Backup Generation** | ✅ | ✅ `backup_generation` (JSON) | N/A | N/A |
| **On-site Generation** | ✅ | ✅ `onsite_generation` (JSON) | N/A | N/A |
| **COD** | ✅ | ✅ `planned_operational_date` | ✅ | ✅ |
| **Lat/Lon** | ✅ (combined) | ✅ (separate) | ✅ (combined) | ✅ (separate) |
| **City** | ❌ (parsed) | ✅ `city` | N/A | N/A |
| **State** | ✅ | ✅ | ✅ | ✅ (JSON) |
| **State Code** | ❌ | ✅ `location_state_code` | ❌ | ❌ |
| **County** | ✅ | ✅ | ✅ | ✅ (JSON) |
| **Country** | ✅ | ✅ | ✅ | ❌ |
| **Continent** | ❌ | ✅ `location_continent` | ❌ | ❌ |
| **Sectors** | ✅ | ✅ (JSON) | ✅ | ✅ (JSON) |
| **Documents** | ✅ (count) | ❌ | ✅ (text) | ❌ |
| **Signals Count** | ✅ | ❌ | N/A | N/A |
| **Key People** | ✅ | ❌ | ✅ | ❌ |
| **Created/Modified** | ✅ / ✅ | ✅ / ❌ | ✅ / ❌ | ✅ / ❌ |
| **Extraction Date** | ❌ | ✅ | ❌ | ✅ |
| **Partition Date (ds)** | ❌ | ✅ | ❌ | ✅ |

---

## 🎉 Key Findings

### Data Centers: FULL PARITY ACHIEVED!

The Hive API (`test_idc_lsim_s_npm_data_center_data`) includes **ALL critical fields** previously thought to be missing:

| Field | CSV | Hive | Status |
|-------|-----|------|--------|
| Building Size | `Building Size (sq ft)` | `building_square_foot` | ✅ **PARITY** |
| Land Size | `Land Size (acre)` | `land_acre` | ✅ **PARITY** |
| Planned COD | `Planned Operation Date` | `planned_operational_date` | ✅ **PARITY** |
| Cost | `Cost` | `cost_value` + `cost_unit` | ✅ **BETTER** (structured) |
| Backup Gen | `Backup Generation (MW)` | `backup_generation` | ✅ **PARITY** (JSON) |
| On-site Gen | `Onsite Generation (MW)` | `onsite_generation` | ✅ **PARITY** |

**Recommendation: Switch to Hive API as primary source for Data Centers.**

### Market Signals: Hive has NEW valuable fields

| New Hive Field | Value |
|----------------|-------|
| `signal_id` | Unique identifier for deduplication |
| `body` | Full HTML signal content |
| `record_url` | Direct link to NPM signal page |
| `type_id` | Machine-readable signal type |

**Recommendation: Switch to Hive API as primary source for Signals.**

---

## Recommendations (UPDATED)

### For Data Centers

**🎯 Recommended Approach: HIVE ONLY**

Since the Hive API has full parity with CSV (and additional fields), switch entirely to Hive:

1. **Use Hive for everything:**
   - Unique ID (`data_center_id`) - enables deduplication
   - Pre-parsed coordinates (`geo_lat`, `geo_lon`) - no parsing needed
   - Pre-parsed city - no extraction from Location field
   - State abbreviations (`location_state_code`)
   - Organization roles (JSON with developer, epc, utility, etc.)
   - Building size (`building_square_foot`)
   - Land size (`land_acre`)
   - COD (`planned_operational_date`)
   - Cost (`cost_value` + `cost_unit`)
   - Backup/On-site generation (JSON)

2. **Minor fields only in CSV** (low priority):
   - `Documents` (count)
   - `Key People` (count)
   - `Signals` (count)
   - `Modified` date
   - `Audiences`
   - `Applications`

### For Market Signals

**🎯 Recommended Approach: HIVE ONLY**

1. **Use Hive for everything:**
   - Unique ID (`signal_id`)
   - Full body text (`body`)
   - Direct link (`record_url`)
   - Pre-parsed coordinates
   - Structured organizations JSON (parse by role)
   - Partition-based incremental loads (`ds`)

2. **Parse org roles from JSON** instead of using separate CSV columns:
   ```python
   # Example: Extract developers from organizations JSON
   orgs = json.loads(row['organizations'])
   developers = [o['identifier'] for o in orgs if o['role'] == 'developer']
   ```

---

## Next Steps

1. [ ] **Run DaiQuery** to capture actual Hive schema for `test_idc_lsim_s_npm_signal_data`
2. [ ] **Compare record counts** between CSV and Hive for both datasets
3. [ ] **Validate data quality** - compare sample records across sources
4. [ ] **Create fetch scripts**:
   - `fetch_npm_dc_hive.py` - Data Centers from Hive
   - `fetch_npm_signals_hive.py` - Market Signals from Hive
5. [ ] **Request missing fields** from GIS dev team for Hive tables
6. [ ] **Update ingestion pipeline** to use hybrid approach

---

## Appendix: DaiQuery Commands

```sql
-- Data Centers (full schema)
DESCRIBE test_idc_lsim_s_npm_data_center_data;

-- Data Centers (sample data)
SELECT * FROM test_idc_lsim_s_npm_data_center_data LIMIT 10;

-- Market Signals (full schema)
DESCRIBE test_idc_lsim_s_npm_signal_data;

-- Market Signals (sample data)
SELECT * FROM test_idc_lsim_s_npm_signal_data LIMIT 10;

-- Record counts
SELECT COUNT(*) FROM test_idc_lsim_s_npm_data_center_data;
SELECT COUNT(*) FROM test_idc_lsim_s_npm_signal_data;
```

---

*Document created: 2026-02-09*
*Last updated: 2026-02-10*

---

## Appendix A: Missing Fields Analysis

### Data Centers - Fields Missing from Hive

| CSV Field | What It Provides | Impact | Request Priority |
|-----------|------------------|--------|------------------|
| `Documents` | Count of attached documents (1, 2, 5) | 🟢 Low - metadata only | Low |
| `Key People` | Count of key people (0) | 🟢 Low - metadata only | Low |
| `Signals` | Count of related signals (1, 5) | 🟡 Medium - could link DC to signals | **Medium** |
| `Modified` | Last modified date | 🟡 Medium - useful for change tracking | Medium |
| `Audiences` | "DC" flag | 🟢 Low - can infer from table | Low |
| `Applications` | Use case info | 🟢 Low - rarely populated | Low |
| `Sectors` | Industry sectors | 🟢 Low - empty in DC data anyway | Low |

**Recommendation:** Request `Signals` count be added to Hive - enables linking Data Centers to related Market Signals.

### Market Signals - Fields Missing from Hive

| CSV Field | What It Provides | Impact | Request Priority |
|-----------|------------------|--------|------------------|
| `keyPeople` | Named individuals (e.g., "Luke Gildemeister") | 🟡 Medium - for stakeholder tracking | Medium |
| `documents` | Document types ("Agenda \| Minutes \| Packet") | 🟡 Medium - for evidence classification | Medium |
| `facilityAddress` | Facility address | 🟢 Low - rarely populated | Low |
| `country` | Country name | 🟢 Low - usually blank for US | Low |
| Separate org columns | `organizations-developers`, `organizations-utilities`, etc. | 🟡 Medium - easier to query by role | **See restructuring below** |

**Recommendation:** Request `keyPeople` and `documents` be added to Hive for stakeholder and evidence tracking.

---

## Appendix B: Restructuring Recommendations

The current Hive schema has several unwieldy JSON fields. We recommend creating a **flattened/parsed view** during ingestion.

### Problem Areas in Current Hive Format

#### A. `organizations` field is deeply nested JSON
```json
[{"identifier": "Google", "id": "5f034b60da77100015c997e6", "role": "developer"},
 {"identifier": "Salt River Project", "id": "5f10700aff41470016c55821", "role": "utility"}]
```

#### B. `location_full` is massive (100+ characters of redundant data)
```json
[{"identifier": "East Elliot Road, Mesa, AZ 85212...", "components": {"continent": "...",
  "country": "...", "_normalized_city": "...", ...}, "geometry": {...}, "id": "...",
  "override": false, "accuracy": [...]}]
```

#### C. `status` is an array when it's always a single value
```json
[{"identifier": "Planned", "id": "inDevelopment"}]
```

#### D. `backup_generation` and `onsite_generation` are nested JSON
```json
{"identifier": "backupGeneration", "value": 3.5, "unit": "MW",
 "sectors": [{"identifier": "Diesel", "id": "..."}]}
```

### Proposed Flattened Schema

#### Data Centers - Proposed Clean Fields

| Current Hive Field | Proposed Flat Field(s) | Transformation |
|--------------------|------------------------|----------------|
| `organizations` (JSON) | `developer`, `epc`, `utility`, `offtaker` | Parse by role, pipe-separate multiples |
| `status` (JSON array) | `status` (text), `status_id` | Extract `identifier`, `id` |
| `location_full` | **DROP** | Redundant - use individual location_* fields |
| `backup_generation` (JSON) | `backup_generation_mw` (double) | Extract `value` |
| `onsite_generation` (JSON) | `onsite_generation_mw` (double) | Extract `value` |
| `cost_value` + `cost_unit` | `cost_usd_million` | Convert to millions if needed |
| `regions` | **DROP** | Always `[{"identifier": "NA"}]` |

#### Market Signals - Proposed Clean Fields

| Current Hive Field | Proposed Flat Field(s) | Transformation |
|--------------------|------------------------|----------------|
| `organizations` (JSON) | `org_developer`, `org_utility`, `org_meeting_host`, `org_other` | Parse by role |
| `sectors` (JSON) | `sectors` (text) | Pipe-separate identifiers |
| `states` (JSON) | `state` (text) | Extract first identifier |
| `counties` (JSON) | `county` (text) | Extract first identifier |
| `projects` (JSON) | `project_name` (text) | Extract first identifier |
| `body` (HTML) | `body_text` (optional) | Strip HTML tags if needed |

### Python Parsing Functions for Ingestion

```python
import json

def parse_orgs_by_role(orgs_json):
    """Parse organizations JSON into role-based columns."""
    if not orgs_json:
        return {}

    try:
        orgs = json.loads(orgs_json) if isinstance(orgs_json, str) else orgs_json
    except:
        return {}

    result = {
        'developer': [],
        'epc': [],
        'utility': [],
        'offtaker': [],
        'other': []
    }

    for org in orgs:
        role = org.get('role', 'other').lower()
        name = org.get('identifier', '')

        if 'developer' in role:
            result['developer'].append(name)
        elif 'epc' in role:
            result['epc'].append(name)
        elif 'utility' in role:
            result['utility'].append(name)
        elif 'offtaker' in role:
            result['offtaker'].append(name)
        else:
            result['other'].append(name)

    # Pipe-separate each role
    return {k: ' | '.join(v) if v else None for k, v in result.items()}


def parse_status(status_json):
    """Extract status identifier from JSON array."""
    if not status_json:
        return None

    try:
        status = json.loads(status_json) if isinstance(status_json, str) else status_json
        if status and len(status) > 0:
            return status[0].get('identifier')
    except:
        pass
    return None


def parse_generation(gen_json):
    """Extract MW value from generation JSON."""
    if not gen_json:
        return None

    try:
        gen = json.loads(gen_json) if isinstance(gen_json, str) else gen_json
        return gen.get('value')
    except:
        pass
    return None


def parse_json_list(json_field, key='identifier'):
    """Extract identifiers from JSON array and pipe-separate."""
    if not json_field:
        return None

    try:
        items = json.loads(json_field) if isinstance(json_field, str) else json_field
        names = [item.get(key, '') for item in items if item.get(key)]
        return ' | '.join(names) if names else None
    except:
        pass
    return None
```

### Fields to Drop (Redundant)

| Field | Reason |
|-------|--------|
| `location_full` | All data already in individual `location_*` fields |
| `location_lat` / `location_lng` | Duplicate of `geo_lat` / `geo_lon` |
| `regions` | Always `[{"identifier": "NA", "id": "NA"}]` - no value |
| `location_country` | Duplicate of `country` |
| `location_state` | Duplicate of `state` |
| `location_city` | Duplicate of `city` |
| `location_county` | Duplicate of `county` |

---

## Appendix C: Record Count Discrepancy

**Issue Noted:** Hive has fewer records than CSV

| Dataset | Manual CSV | Hive API | Difference |
|---------|------------|----------|------------|
| Data Centers | ~1,568 | ~254 | -1,314 (84% fewer) |
| Market Signals | ~2,000 | ~4,785 | +2,785 (139% more) |

**Possible Causes:**
- Hive may have different filtering criteria (e.g., only recent data, only certain statuses)
- Hive `ds` partition date may be limiting results
- CSV may include historical/archived records not in Hive
- Different extraction dates

**Recommendation:** Investigate with GIS dev team to confirm expected record counts and filtering logic.

---
