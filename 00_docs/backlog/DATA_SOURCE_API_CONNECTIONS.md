# Feature Backlog: Automated Data Source API Connections

**Status:** 📋 Backlog
**Priority:** High (Long-term)
**Created:** 2026-01-21
**Requested By:** P. Anderson

---

## Overview

Replace manual CSV exports with automated API/database connections to pull DCH (DataCenterHawk) and NPM (NewProjectMedia) data directly from internal Meta Hive tables on SQL servers.

---

## Current State (Manual Process)

```
┌─────────────────┐     Manual      ┌─────────────────┐     Manual      ┌─────────────────┐
│  External Data  │ ──── Export ───▶│  CSV in         │ ──── Import ───▶│  Geodatabase    │
│  Sources        │                 │  Downloads/     │                 │  (arcpy)        │
└─────────────────┘                 └─────────────────┘                 └─────────────────┘
     DCH, NPM,                         NPM_DC_1_15.csv                    npm_raw
     SemiAnalysis                      DCH_Hyper.csv                      dch_hyper_raw
```

**Pain Points:**
- Manual CSV export from vendor portals
- Manual download to local machine
- Version control challenges (which file is latest?)
- No automatic refresh of data
- Time-consuming for regular updates

---

## Proposed State (Automated)

```
┌─────────────────┐                 ┌─────────────────┐                 ┌─────────────────┐
│  Meta Hive      │ ── Presto/SQL ─▶│  Python ETL     │ ── arcpy ──────▶│  Geodatabase    │
│  Tables         │    Query        │  Pipeline       │                 │  gold_buildings │
└─────────────────┘                 └─────────────────┘                 └─────────────────┘
     dch_raw_*                         Scheduled or                       Automated
     npm_raw_*                         On-demand                          ingestion
```

---

## Data Sources to Connect

### Status Update (2026-01-21)

✅ **Confirmed:** Source data is ALREADY ingested into Meta Hive
✅ **Confirmed:** Adjacent team owns the tables and manages data refreshes
⏳ **Next Step:** Request read access (ACL) to the Hive tables

---

### 1. DataCenterHawk (DCH)

**Current:** Manual CSV export from DCH portal
**Target:** Query from Meta Hive table ✅ (data already in Hive)

| Item | Details |
|------|---------|
| Hive Table (TBD) | Need table name from adjacent team |
| Update Frequency | Managed by adjacent team |
| Key Fields | Company, Location, Capacity, Status, Coordinates |
| Record Volume | ~7,000 records |
| Data in Hive | ✅ Yes |

**Remaining Questions:**
- [x] ~~Is DCH data already being ingested to Meta Hive?~~ → Yes!
- [ ] What is the exact Hive table name?
- [ ] What is the refresh cadence?
- [ ] What ACL group is needed for read access?

### 2. NewProjectMedia (NPM)

**Current:** Manual CSV export from NPM platform
**Target:** Query from Meta Hive table ✅ (data already in Hive)

| Item | Details |
|------|---------|
| Hive Table (TBD) | Need table name from adjacent team |
| Update Frequency | Managed by adjacent team |
| Key Fields | Project, Organizations, Status, Lat/Lon, Cost, MW |
| Record Volume | ~1,500 records |
| Data in Hive | ✅ Yes |

**Remaining Questions:**
- [x] ~~Is NPM data already being ingested to Meta Hive?~~ → Yes!
- [ ] What is the exact Hive table name?
- [ ] What ACL group is needed for read access?

### 3. SemiAnalysis (Future)

**Current:** Manual CSV from SemiAnalysis reports
**Target:** Potentially automate if data becomes available via API/Hive

---

## Technical Approach

### Option A: Presto/Hive Direct Query (Preferred)

**Requirements:**
- Access to Meta's Presto/Hive infrastructure
- Appropriate ACLs for data tables
- Python Presto client (e.g., `pyhive`, `presto-python-client`)

**Implementation:**
```python
# Example: Query DCH from Hive
from pyhive import presto

conn = presto.connect(
    host='presto.intern.facebook.com',
    port=8080,
    username='ptanderson',
    catalog='hive',
    schema='datalake'
)

cursor = conn.cursor()
cursor.execute("""
    SELECT
        company, campus_name, city, state, country,
        latitude, longitude, capacity_mw, status,
        data_vintage
    FROM dch_hyperscale
    WHERE data_vintage >= DATE_SUB(CURRENT_DATE, 30)
""")

results = cursor.fetchall()
# Convert to DataFrame, then to geodatabase...
```

**Pros:**
- Direct access to source of truth
- Can leverage existing data pipelines
- Scheduled queries possible via Dataswarm

**Cons:**
- Requires Hive table access permissions
- Dependent on upstream data quality
- May need VPN/on-network access

### Option B: REST API (If Available)

**Requirements:**
- API endpoint for DCH/NPM data
- API credentials/tokens
- Rate limiting considerations

**Implementation:**
```python
import requests

def fetch_npm_data():
    response = requests.get(
        'https://api.internal.meta.com/npm/projects',
        headers={'Authorization': f'Bearer {API_TOKEN}'},
        params={'updated_since': '2026-01-01'}
    )
    return response.json()
```

**Pros:**
- Cleaner abstraction
- Built-in pagination/filtering
- Versioned endpoints

**Cons:**
- May not exist for these data sources
- Additional API development needed

### Option C: Dataswarm Pipeline (Enterprise)

**Requirements:**
- Dataswarm access and pipeline creation
- Hive table outputs
- Scheduled execution

**Implementation:**
- Create Dataswarm pipeline that:
  1. Queries source Hive tables
  2. Applies transformations
  3. Outputs to a "clean" Hive table
  4. Triggers downstream GIS ingestion

**Pros:**
- Enterprise-grade scheduling
- Monitoring and alerting
- Audit trail

**Cons:**
- Higher setup complexity
- Requires Dataswarm expertise

---

## Implementation Plan

### Phase 1: Discovery & Access (1-2 weeks)

- [ ] Identify which Hive tables contain DCH/NPM data
- [ ] Request ACL access to relevant tables
- [ ] Document table schemas and update frequencies
- [ ] Validate data quality and completeness
- [ ] Compare Hive data to current CSV exports

### Phase 2: Python ETL Development (1-2 weeks)

- [ ] Create `scripts/01_ingestion/fetch_dch_hive.py`
- [ ] Create `scripts/01_ingestion/fetch_npm_hive.py`
- [ ] Add Presto/Hive connection utilities to `_utils/`
- [ ] Implement data validation and logging
- [ ] Handle incremental updates (only fetch new/changed records)

### Phase 3: Integration & Testing (1 week)

- [ ] Integrate with existing ingestion scripts
- [ ] Compare automated results to manual CSV imports
- [ ] Validate record counts, field mappings, data quality
- [ ] Update pipeline documentation

### Phase 4: Scheduling (Optional)

- [ ] Set up scheduled execution (daily/weekly)
- [ ] Add monitoring and alerting
- [ ] Create data freshness dashboard

---

## New Files to Create

```
scripts/
├── 01_ingestion/
│   ├── fetch_dch_hive.py          # NEW - DCH Hive query
│   ├── fetch_npm_hive.py          # NEW - NPM Hive query
│   └── fetch_semianalysis_api.py  # FUTURE - SemiAnalysis API
├── _utils/
│   ├── hive_connection.py         # NEW - Presto/Hive utilities
│   └── config.py                  # UPDATE - Add Hive connection params
```

---

## Configuration Updates

```python
# config.py additions

# ==============================================================================
# HIVE/PRESTO CONNECTION (Internal Meta Data Sources)
# ==============================================================================

PRESTO_HOST = 'presto.intern.facebook.com'
PRESTO_PORT = 8080
PRESTO_CATALOG = 'hive'
PRESTO_SCHEMA = 'datalake'

# Source table names (TBD - need to confirm with data owners)
HIVE_TABLES = {
    'dch_hyperscale': 'datalake.dch_hyperscale_raw',
    'dch_lease': 'datalake.dch_lease_raw',
    'npm': 'datalake.npm_projects_raw',
}

# Refresh cadence
DATA_REFRESH_SCHEDULE = {
    'dch_hyperscale': 'weekly',   # Every Monday
    'dch_lease': 'weekly',
    'npm': 'daily',               # Every day at 6am
}
```

---

## Effort Estimate

| Phase | Effort | Dependencies |
|-------|--------|--------------|
| Discovery & Access | 1-2 weeks | Data team coordination |
| Python ETL Dev | 1-2 weeks | Phase 1 complete |
| Integration & Testing | 1 week | Phase 2 complete |
| Scheduling (Optional) | 3-5 days | Phase 3 complete |

**Total:** 4-6 weeks (including coordination time)

---

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Hive tables don't exist | Work with data team to create ingestion pipeline |
| ACL access denied | Escalate through proper channels, justify business need |
| Data quality issues | Add validation layer, compare to known-good CSV data |
| Schema changes upstream | Version schema mappings, add alerting on schema drift |
| Network access (VPN) | Document requirements, test from on-network and VPN |

---

## Questions to Answer

1. **DCH Data:**
   - Is DCH data already ingested to Meta Hive?
   - Who owns the pipeline? (Infra Data team? Real Estate?)
   - What is the table name and schema?

2. **NPM Data:**
   - Is NPM data available in Hive?
   - Is there an API alternative?
   - Who is the data steward?

3. **Access:**
   - What ACL groups are needed?
   - Is there a data catalog entry for these tables?

4. **Scheduling:**
   - Should this run on a schedule or on-demand?
   - What's the acceptable data latency?

---

## Related

- Current ingestion scripts: `scripts/01_ingestion/`
- Config module: `scripts/_utils/config.py`
- Pipeline architecture: `scripts/00_docs/workflows/`

---

## Next Steps

1. Schedule meeting with Data Infrastructure team to identify existing Hive tables
2. Request read access to relevant data tables
3. Document table schemas and compare to current CSV field mappings
4. Prototype Presto connection from local dev environment
