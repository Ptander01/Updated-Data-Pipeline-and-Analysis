# Peer Self-Build Planning Timeline / Land Banking Assessment

## Project Overview

**Status:** Active Sprint
**Timeline:** February 9-13, 2026 (1-Week Sprint)
**POC:** Aman Dulay, Katie Ballard-Bloomfield, Yash Gokhale
**Last Updated:** February 2, 2026

---

## Objective

Benchmark the site development and pre-construction timelines of major cloud providers for their data center capacity growth. This is a rapid feasibility assessment to determine if existing data sources can answer key questions about peers' planning horizons.

---

## Key Business Questions

1. **Planning Horizon:** How far in advance did peers (Amazon, Google, Microsoft, Oracle) plan for current capacity growth (AI capacity ramp)?
2. **Land/Energy Banking:** Is there evidence of strategic land or energy banking? What are the timelines?
3. **Capacity Planning Horizons:** What are typical planning horizons for peer self-build data centers?
4. **2025-2027 Analysis:** For DCs coming online in 2025-2027, what was the planning horizon from land acquisition to operation?

---

## Scope Definition

### In-Scope Companies
| Company | Filter Value (company_clean) |
|---------|------------------------------|
| Amazon | `AWS` |
| Google | `Google` |
| Microsoft | `Microsoft` |
| Oracle | `Oracle` |

### Geographic Scope
- **Region:** North America only
- **Countries:** United States, Canada, Mexico

### Temporal Scope
- **First MW Date:** January 2025 - December 2027
- **Analysis uses:** `mw_2025`, `mw_2026`, `mw_2027` from Semianalysis data

### Facility Type Scope
- **Type:** Self-Build / On-Prem / Owned
- **Includes:** Build-to-suit lease (SemiAnalysis classifies as "self build")
- **Excludes:** Leased colocation, pure retail colo

### Filtering Logic (Semianalysis)
```python
# Semianalysis record_level values for self-build:
# - Building (with owner = hyperscaler)
# - TLBM_Hyperscaler (market-level aggregates)

# Filter criteria:
company_clean IN ('AWS', 'Google', 'Microsoft', 'Oracle')
AND region = 'AMER'
AND country IN ('United States', 'Canada', 'Mexico')
AND (mw_2025 > 0 OR mw_2026 > 0 OR mw_2027 > 0)
AND record_level IN ('Building', 'TLBM_Hyperscaler')
```

---

## Phase 1: Land Acquisition & Initial Timeline Analysis

### Step 1.1: Data Matching & Filtering

**Objective:** Identify and match in-scope DC sites to land parcels

**Data Sources:**
| Source | Purpose | Key Fields |
|--------|---------|------------|
| Consensus Model (`gold_buildings_full`) | DC locations with capacity data | `company_clean`, `mw_2025-2027`, `lat/lon` |
| ACRES Parcels | Land ownership data | `entity`, `apn`, `computed_acres` |
| ACRES Transactions | Transaction dates & prices | `transaction_date`, `transaction_amount`, `buyer_name`, `seller_name` |
| CoreLogic/Cotality | Additional transaction data | TBD (data access pending) |

**Matching Method:**
1. Spatial join: Consensus DC points → ACRES parcel polygons (point-in-polygon)
2. Buffer fallback: 500m radius for edge cases
3. Company name validation: Match ACRES `entity` to Consensus `company_clean`

### Step 1.2: Ownership Analysis

**Objective:** Determine % of self-build DCs on land owned by hyperscaler vs developer

**Output Metrics:**
| Metric | Description |
|--------|-------------|
| `pct_hyperscaler_owned` | % of sites where land owned directly by hyperscaler or affiliate |
| `pct_developer_owned` | % of sites where land owned by developer/other entity |
| `pct_unknown` | % of sites with no ACRES parcel match |

**Company Ownership Patterns:**
| Company | Known Land-Owning Entities |
|---------|---------------------------|
| AWS | Amazon Data Centers, Amazon Data Services, various state-specific LLCs |
| Google | Google, Alphabet subsidiaries |
| Microsoft | Microsoft Corporation, various subsidiaries |
| Oracle | Oracle Corporation, Oracle America |

### Step 1.3: Timeline Calculation

**Objective:** Calculate months from land sale to first MW

**Formula:**
```
timeline_months = (first_mw_date - land_sale_date) / 30.44

Where:
- land_sale_date = ACRES transaction_date OR change_date
- first_mw_date = First year where mw_YYYY > 0 (converted to date)
```

**Output Fields:**
| Field | Description |
|-------|-------------|
| `land_sale_date` | Earliest recorded transaction date |
| `first_mw_date` | Estimated first MW quarter (from mw_YYYY fields) |
| `timeline_months` | Difference in months |
| `timeline_years` | Difference in years |

### Step 1.4: Sale Price Analysis

**Objective:** Calculate sale price per acre

**Formula:**
```
price_per_acre = transaction_amount / computed_acres
```

**Notes:**
- `transaction_amount` available in ACRES Transactions layer
- Only available for disclosure states
- Non-disclosure states: Use Parcel Changes layer for ownership timing (no price)

---

## Phase 2: Detailed Timeline Reconstruction (Sampled Sites)

### Site Selection Criteria

Select ~3 sites per peer (9-12 total) based on:
1. Data completeness (has ACRES match with dates)
2. Representative capacity size
3. Geographic diversity
4. Mix of 2025/2026/2027 first MW dates

### Timeline Milestones to Reconstruct

| Milestone | Data Source | Notes |
|-----------|-------------|-------|
| Land Acquisition / Purchase | ACRES Transactions | `transaction_date` |
| Local Approvals (rezoning) | Manual research | News, planning documents |
| Energy Procurement (load study) | PJM TEAC, utility filings | See energy signals section |
| Interconnection Queue Position | Utility queue data | If available |
| Substation Construction | Manual research | Permits, news |
| Construction Permitting | Manual research | Building permits |
| Construction Start | NewProjectMedia, news | Construction announcements |
| Public Announcement | NewProjectMedia, news | "Out of stealth" |
| First MW Operational | Semianalysis mw_YYYY | Estimated from capacity ramp |

### Energy Application Signals

**PJM TEAC (Transmission Expansion Advisory Committee):**
- URL: https://www.pjm.com/committees-and-groups/committees/teac
- Contains: Need assessment documents, load study requests
- Example: PPL Transmission Zone requests (Orefield PA, Lackawanna PA)

**Key Data Points from TEAC:**
- Need Number (e.g., PPL-2025-0006)
- Process Stage (Need Meeting, Solution Meeting)
- Requested In-Service Date
- Initial Load (MW) and Projected Load trajectory

---

## Deliverables

### End of Sprint (Feb 13, 2026)

1. **Initial Analysis Report (MVP)**
   - Calculated time difference: land acquisition → first MW for in-scope sites
   - Ownership breakdown: hyperscaler vs developer
   - Sale price per acre summary statistics

2. **Detailed Timeline Reconstructions**
   - 9-12 sampled site timelines with all available milestones

3. **Feasibility Assessment**
   - Data gaps identified
   - Recommendations for Phase 2 expansion

---

## Future Expansion (Post-Sprint)

1. **Deeper Dive Analysis:** Manual data collection for gaps
2. **Expanded Scope:**
   - Include major colo providers and neoclouds
   - Expand geography (Rest of World)
3. **Powered Land Premium Analysis:**
   - Multi-transaction parcels (Vantage WI / Cloverleaf case study)
   - Resale premium calculations
   - Requires ACRES + CoreLogic/Cotality linkage

---

## Scripts

| Script | Purpose | Status |
|--------|---------|--------|
| `phase1_scope_filter.py` | Filter Consensus Model to in-scope sites | NEW |
| `phase1_acres_match.py` | Match DC sites to ACRES parcels | NEW |
| `phase1_ownership_analysis.py` | Calculate ownership % breakdown | NEW |
| `phase1_timeline_calc.py` | Calculate land → first MW timeline | NEW |
| `phase1_price_analysis.py` | Calculate $/acre metrics | NEW |
| `phase2_site_selection.py` | Select sampled sites for detailed analysis | NEW |
| `ingest_acres.py` | Import ACRES data | EXISTING |
| `acres_parcel_rollup.py` | Campus rollup from parcels | EXISTING |
| `analyze_land_to_mw_lag.py` | Time lag analysis | UPDATE |
| `analyze_transaction_history.py` | Multi-transaction analysis | EXISTING |

---

## Data Access Requirements

| Data Source | Access Status | Contact |
|-------------|---------------|---------|
| Consensus Model (gold_buildings_full) | ✅ Available | Local GDB |
| ACRES (Portal) | ✅ Available | Portal service |
| ACRES (Hive) | ✅ Available | idc_lsim_datacenter_index_* |
| CoreLogic/Cotality | ⏳ Pending | Real Estate Analytics Team |
| NewProjectMedia | ✅ Available | CSV + Hive |
| PJM TEAC Documents | 🔗 Public | https://pjm.com/committees-and-groups/committees/teac |

---

## Appendix: Sample TEAC Data

### PPL-2025-0006 (Orefield, PA)
- **Process Stage:** Solution Meeting TEAC - 11/04/2025
- **Previously Presented:** Need Meeting 05/06/2025
- **Total Facility Load:** ~1,000 MW (2031)
- **Requested In-Service:** 10/2026
- **Initial 2026 Load:** 75 MW
- **Projected 2028 Load:** 450 MW
- **Projected 2030 Load:** 920 MW

### PPL-2025-0013 (Lackawanna, PA)
- **Process Stage:** Need Meeting 9/09/2025
- **Total Facility Load:** ~1,400 MW (2031)
- **Requested In-Service:** 07/2028
- **Initial 2028 Load:** 200 MW
- **Projected 2030 Load:** 1,200 MW

---

*Document Version: 1.0*
*Created: February 2, 2026*
