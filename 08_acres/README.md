# ACRES Data Integration Module

## Overview

This module integrates ACRES parcel-level land transaction data with the Consensus DC Model to enable:

1. **Parcel-to-Campus Rollup** - Collapse adjacent parcels into single-point campus centroids
2. **Transaction Timeline Analysis** - Track land sale → first MW lag times
3. **Multi-Transaction Tracking** - Analyze ownership changes and resale premiums
4. **CoreLogic/Cotality Linkage** - Cross-reference with additional property data sources

---

## Active Project: Peer Self-Build Planning Timeline Analysis

**Sprint:** February 9-13, 2026 (1-Week MVP)
**Documentation:** [PEER_PLANNING_TIMELINE_ANALYSIS.md](PEER_PLANNING_TIMELINE_ANALYSIS.md)

### Quick Start (Phase 1)

```python
# Step 1: Ingest ACRES data (if not already loaded)
exec(open(r"C:/Users/ptanderson/Documents/ArcGIS/Projects/Lean Consensus DC Model/scripts/08_acres/ingest_acres.py", encoding='utf-8').read())

# Step 2: Filter to in-scope sites (AWS, Google, Microsoft, Oracle - North America - 2025-2027)
exec(open(r"C:/Users/ptanderson/Documents/ArcGIS/Projects/Lean Consensus DC Model/scripts/08_acres/phase1_scope_filter.py", encoding='utf-8').read())

# Step 3: Match DC sites to ACRES parcels
exec(open(r"C:/Users/ptanderson/Documents/ArcGIS/Projects/Lean Consensus DC Model/scripts/08_acres/phase1_acres_match.py", encoding='utf-8').read())

# Step 4: Calculate land-to-MW timelines
exec(open(r"C:/Users/ptanderson/Documents/ArcGIS/Projects/Lean Consensus DC Model/scripts/08_acres/phase1_timeline_calc.py", encoding='utf-8').read())
```

### Key Deliverables

| Output | Description |
|--------|-------------|
| `peer_selfbuild_2025_2027` | Filtered DC sites (scope: AWS/Google/Microsoft/Oracle, NA, 2025-2027 first MW) |
| `peer_selfbuild_acres_matched` | Sites matched to ACRES parcels |
| `peer_selfbuild_timeline_analysis` | Final analysis with land→MW timeline, ownership, $/acre |

---

## Data Sources

### Primary: HIVE Tables (Recommended)

ACRES data is available in HIVE for direct query access:

| HIVE Table | Type | Description |
|------------|------|-------------|
| `idc_lsim_datacenter_index_parcel_changes_centroid` | Point | Parcel ownership changes (centroids) |
| `idc_lsim_datacenter_index_parcel_changes_polygon` | Polygon | Parcel ownership changes (boundaries) |
| `idc_lsim_datacenter_index_parcels_centroid` | Point | Current parcel ownership (centroids) |
| `idc_lsim_datacenter_index_parcels_polygon` | Polygon | Current parcel ownership (boundaries) |
| `idc_lsim_datacenter_index_transactions_centroid` | Point | Courthouse/assessor transactions (centroids) |
| `idc_lsim_datacenter_index_transactions_polygon` | Polygon | Courthouse/assessor transactions (boundaries) |

**Sample Query:**
```sql
SELECT *
FROM idc_lsim_datacenter_index_parcel_changes_centroid
WHERE ds = '2025-11-21'
```

### Secondary: ArcGIS Enterprise Portal

- **Portal Service**: `https://esri-prod.thefacebook.com/Portal/apps/mapviewer/index.html?layers=f6470b4720324422ba122a67db30c1a5`
- **Feature Service Group**: `idc_acres_datacenter_index_hosted`

## Understanding the Data Layers

### Three Core Layer Types

| Layer Type | Purpose | Key Use Case |
|------------|---------|--------------|
| **Parcels** | Who owns what currently | Current ownership snapshot |
| **Transactions** | Courthouse/assessor transaction records | Sale dates, prices (disclosure states) |
| **Parcel Changes** | Monthly diff on owner name | Catches transactions in non-disclosure states |

### Key Concepts

1. **Deduplication**: ACRES joins multi-parcel purchases into single transaction records with unioned geometry

2. **Parent Entity Mapping**: Sub-entities/LLCs are continuously mapped to parent companies (e.g., various Google LLCs → Google)

3. **Campus vs Parcel**: One campus (parent entity) may contain multiple unique parcels

4. **Web Source Records**: Parcels with "Web Source" in source column are scraped from known locations

5. **New Records Filter**: `new_record = "new"` AND `sale_date` within last 2 months indicates recent additions

### Key Fields

| Field | Description |
|-------|-------------|
| `entity` | Owner/company (parent entity - MICROSOFT_DATA_CENTERS, META_DATA_CENTERS, etc.) |
| `new_record` | Flag: "new" for recent additions, "None" for existing |
| `owner_change_type` | Change type: "new owner", "internal transfer", "previous owner" |
| `state` | State abbreviation (IL, ID, WI, etc.) |
| `county` | County name |
| `apn` | Assessor Parcel Number (unique parcel identifier) |
| `change_date` | Date of ownership change (YYYY-MM-DD) |
| `change_date_year` | Year + Month in YYYYMMDD format (20240601) |
| `computed_acres` | Parcel size in acres |
| `sale_date` | Transaction date (from Transactions layer) |
| `transaction_amount` | Sale price (Transactions layer - disclosure states only) |
| `buyer_name` / `seller_name` | Ownership chain tracking (Transactions layer) |
| `source` | Data source ("Web Source" = scraped) |

### Data Update Frequency

- **Monthly updates** (mid-month delivery, ~15th)
- ACRES provides notable/relevant purchase reports monthly
- Continuously updating entity-to-parent mappings

## Scripts

### Phase 1: Peer Planning Timeline Analysis (Sprint Feb 9-13, 2026)

| Script | Purpose |
|--------|---------|
| `phase1_scope_filter.py` | Filter to in-scope sites (AWS/Google/Microsoft/Oracle, NA, 2025-2027) |
| `phase1_acres_match.py` | Match DC sites to ACRES parcels |
| `phase1_timeline_calc.py` | Calculate land→MW timeline, ownership %, $/acre |

### Data Ingestion

| Script | Purpose |
|--------|---------|
| `fetch_acres_hive.py` | Query ACRES data from Hive tables (recommended for fresh data) |
| `ingest_acres.py` | Import ACRES data from ArcGIS Portal or CSV files |

### Core Integration

| Script | Purpose |
|--------|---------|
| `acres_parcel_rollup.py` | Collapse adjacent parcels into campus centroids + crosswalk |

### Analysis

| Script | Purpose |
|--------|---------|
| `analyze_land_to_mw_lag.py` | Calculate time from land acquisition to first MW |
| `analyze_transaction_history.py` | Track multi-transaction parcels and resale premiums |

## Workflow

```
Phase 1 Sprint Workflow (Feb 9-13, 2026):
=========================================

Step 1: Data Ingestion
    ingest_acres.py → acres_parcels_polygon, acres_transactions_polygon, etc.

Step 2: Scope Filtering
    phase1_scope_filter.py → peer_selfbuild_2025_2027

Step 3: ACRES Matching
    phase1_acres_match.py → peer_selfbuild_acres_matched

Step 4: Timeline Analysis
    phase1_timeline_calc.py → peer_selfbuild_timeline_analysis
                           → Peer_Timeline_Analysis_YYYYMMDD.md (report)


General Analysis Workflow:
==========================

Step 1: Data Ingestion
    ingest_acres.py → acres_parcels_raw, acres_transactions_raw, acres_parcel_changes_raw

Step 2: Parcel Rollup
    acres_parcel_rollup.py → acres_campus_centroids (with adjacent parcel grouping)

Step 3: Crosswalk Generation
    generate_parcel_crosswalk.py → acres_parcel_campus_xwalk

Step 4: Join with Consensus Model
    - Match ACRES parcels to gold_buildings_full by spatial proximity
    - Match ACRES entities to company_clean via entity mapping table

Step 5: Analysis
    analyze_land_to_mw_lag.py → land_to_mw_analysis (per-site lag times)
    analyze_transaction_history.py → transaction_history_analysis
```

## Entity Mapping

ACRES entity names → Consensus company_clean:

| ACRES Entity | Consensus company_clean |
|--------------|------------------------|
| `META_DATA_CENTERS` | `Meta` |
| `MICROSOFT_DATA_CENTERS` | `Microsoft` |
| `DIGITAL_REALTY_DATA_CENTERS` | `Digital Realty` |
| `T5_DATA_CENTERS` | `T5` |
| `AWS_DATA_CENTERS` / `AMAZON_DATA_CENTERS` | `AWS` |
| `GOOGLE_DATA_CENTERS` | `Google` |
| `ORACLE_DATA_CENTERS` | `Oracle` |
| `VANTAGE_DATA_CENTERS` | `Vantage` |
| `EQUINIX_DATA_CENTERS` | `Equinix` |
| `QTS_DATA_CENTERS` | `QTS` |

## Usage

```python
# Full ingestion and rollup
exec(open(r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\scripts\08_acres\ingest_acres.py", encoding='utf-8').read())
exec(open(r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\scripts\08_acres\acres_parcel_rollup.py", encoding='utf-8').read())

# Analysis
exec(open(r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\scripts\08_acres\analyze_land_to_mw_lag.py", encoding='utf-8').read())
```

## Related Documentation

- `PEER_PLANNING_TIMELINE_ANALYSIS.md` - Sprint project brief and requirements
- `ACRES_SCHEMA_REFERENCE.md` - Full field definitions from ACRES data delivery
- `PARCEL_CAMPUS_METHODOLOGY.md` - Methodology for parcel grouping and campus assignment
