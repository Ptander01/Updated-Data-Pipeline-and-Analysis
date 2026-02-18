# ACRES Data Schema Reference

## Overview

Official schema reference from ACRES Data Delivery Summary (June 2025).

**Layer Naming Convention:** `<Entity> - <Layer> - <Geometry> - <Date>`

Example: `Datacenters - Transactions - Boundaries - June 2025`

---

## Entities Included (11 Primary + Others)

| Entity Code | Display Name |
|-------------|--------------|
| `AMAZON_DATA_CENTERS` | Amazon (12.8%, 96 parcels) |
| `MICROSOFT_DATA_CENTERS` | Microsoft (11.6%, 87 parcels) |
| `DATABANK_DATA_CENTERS` | DataBank (8.8%, 66 parcels) |
| `DIGITAL_REALTY_DATA_CENTERS` | Digital Realty (7.1%, 53 parcels) |
| `EQUINIX_DATA_CENTERS` | Equinix (5.5%, 41 parcels) |
| `QTS_DATA_CENTERS` | QTS (5.3%, 40 parcels) |
| `GOOGLE_DATA_CENTERS` | Google (4.1%, 31 parcels) |
| `META_DATA_CENTERS` | Meta (3.7%, 28 parcels) |
| `ALIGNED_DATA_CENTERS` | Aligned (2.7%, 20 parcels) |
| `VANTAGE_DATA_CENTERS` | Vantage (2.4%, 18 parcels) |
| Others (14.4%, 108 parcels) | Cologix, CoreSite, Softlayer, Iron Mountain, NTT, T5, Powerhouse, Switch, Apple, Compass, DCBlox, Applied Digital, Oracle, xAI |

---

## Layer Types

| Layer | Description | Use Case |
|-------|-------------|----------|
| **Parcels** | County-assessed tax data for each property and parcel boundary | Current ownership snapshot |
| **Transactions** | All land acquisitions or dispositions involving the entity | Sale dates, prices, buyer/seller names |
| **Parcel Changes** | Tracks parcels with current and previous owner info | Critical for non-disclosure states |

## Geometry Options

| Option | Description |
|--------|-------------|
| **Points** | Centroids for viewing across multiple layers at broader map views |
| **Boundaries** | Full property boundaries for detailed, property-specific analysis |

---

## Data Dictionary: PARCEL DATA

| Column | Type | Description | Notes |
|--------|------|-------------|-------|
| `entity` | text | Name of associated organization | e.g., AMAZON_DATA_CENTERS |
| `new_record` | text | 'new' = parcel record is NEW relative to previous data release | Filter for recent additions |
| `source` | text | Data source for the site's location | "Web Source" = scraped |
| `computed_acres` | numeric | Parcel acres | Computed with GIS tools |
| `apn` | text | Assessor parcel number | **Primary key for joins** |
| `address` | text | Parcel street address | |
| `city` | text | Parcel city | |
| `state` | text | Parcel state (abbreviation) | |
| `zip` | text | Parcel zip code | |
| `status` | text | Status of site's operation | |

---

## Data Dictionary: PARCEL OWNER CHANGE LOG DATA

| Column | Type | Description | Notes |
|--------|------|-------------|-------|
| `entity` | text | Name of associated organization | Parent entity name |
| `new_record` | text | 'new' = parcel owner change record is NEW relative to previous data release | |
| `owner_change_type` | text | Is the entity the "new owner", "previous owner", or was it an "internal transfer" | Key for tracking ownership chain |
| `apn` | text | Assessor parcel number | **Primary key for joins** |
| `county` | text | County parcel is in | |
| `state` | text | US State Abbreviation | |
| `change_date` | date | Data ingest date which change was detected | |
| `change_date_yearmoda` | int | Data ingest date in INT form (YYYYMMDD) | e.g., 20250601 |
| `computed_acres` | numeric | Parcel acreage | Computed with GIS tools |

---

## Data Dictionary: TRANSACTIONS DATA

| Column | Type | Description | Notes |
|--------|------|-------------|-------|
| `entity` | text | Name of associated organization | Parent entity name |
| `new_record` | text | 'new' = parcel record is NEW relative to previous data release | |
| `buyer_name` | text | Name of buyer | **For ownership chain analysis** |
| `seller_name` | text | Name of seller | **For ownership chain analysis** |
| `state` | text | US State Abbreviation | |
| `county` | text | County parcel is in | |
| `transaction_amount` | numeric | Transaction amount ($) | **KEY: Sale price for premium calc** |
| `transaction_date` | datetime | Transaction date | {YYYY-MM-DD} formatted |
| `transaction_date_yearmoda` | int | Transaction date in INT form (YYYYMMDD) | e.g., 20250115 |
| `computed_acres` | text | Computed acres | Computed with GIS tools |
| `transaction_type` | text | 'buyer' = Entity was buyer in transaction, 'seller' = Entity was seller, 'internal transaction' = Entity was seller and buyer | **Key for filtering** |

---

## Key Analysis Fields Summary

### For Time-Lag Analysis (Land Sale → First MW)
- `transaction_date` (Transactions layer) → When land was acquired
- Join to Consensus Model `mw_YYYY` fields → When first MW commissioned

### For Resale Premium Analysis (Cloverleaf → Vantage)
- `transaction_amount` → Sale price
- `buyer_name` / `seller_name` → Ownership chain
- `transaction_type` → Who was buyer vs seller
- `computed_acres` → Calculate $/acre

### For Campus Rollup
- `apn` → Group parcels by assessor parcel number
- `entity` → Group by parent company
- `computed_acres` → Sum for total campus size

---

## Entity Name Mapping (ACRES → Consensus)

| ACRES Entity | Consensus company_clean |
|--------------|------------------------|
| `AMAZON_DATA_CENTERS` | `AWS` |
| `MICROSOFT_DATA_CENTERS` | `Microsoft` |
| `GOOGLE_DATA_CENTERS` | `Google` |
| `META_DATA_CENTERS` | `Meta` |
| `DIGITAL_REALTY_DATA_CENTERS` | `Digital Realty` |
| `EQUINIX_DATA_CENTERS` | `Equinix` |
| `QTS_DATA_CENTERS` | `QTS` |
| `DATABANK_DATA_CENTERS` | `DataBank` |
| `ALIGNED_DATA_CENTERS` | `Aligned` |
| `VANTAGE_DATA_CENTERS` | `Vantage` |
| `CYRUSONE_DATA_CENTERS` | `CyrusOne` |
| `CORESITE_DATA_CENTERS` | `CoreSite` |
| `T5_DATA_CENTERS` | `T5` |
| `SWITCH_DATA_CENTERS` | `Switch` |
| `APPLE_DATA_CENTERS` | `Apple` |
| `ORACLE_DATA_CENTERS` | `Oracle` |
| `XAI_DATA_CENTERS` | `xAI` |

---

## Notes

1. **Non-Disclosure States**: Use Parcel Changes layer - it tracks owner name changes monthly even when transactions aren't publicly reported

2. **Web Source**: Parcels with `source = "Web Source"` are scraped from known locations that ACRES didn't have in their database

3. **Monthly Updates**: Data delivered mid-month (~15th), layer names include delivery date (e.g., "June 2025")

4. **Deduplication**: ACRES joins multi-parcel purchases into single transaction records with unioned geometry

5. **Parent Entity Mapping**: Sub-entities/LLCs are continuously mapped to parent companies
