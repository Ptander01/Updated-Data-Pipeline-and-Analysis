"""
Multi-Transaction Parcel Analysis
=================================

Analyzes parcels that have undergone multiple ownership transactions to:
1. Track ownership chain (original owner → intermediate → final owner)
2. Calculate resale premiums between transactions
3. Identify "land flip" patterns (quick resale at higher prices)

Case Study: Vantage site in Wisconsin
- First purchase by Cloverleaf (over market price?)
- Resale from Cloverleaf to Vantage (resale premium?)

This analysis requires linking ACRES data with CoreLogic/Cotality data
for transaction price information.

USAGE (in ArcGIS Pro Python window):
    exec(open(r"C:/Users/ptanderson/Documents/ArcGIS/Projects/Lean Consensus DC Model/scripts/08_acres/analyze_transaction_history.py", encoding='utf-8').read())

Author: Meta Data Center GIS Team
Created: 2026-01-29
"""

import arcpy
import os
import sys
from datetime import datetime
from collections import defaultdict
import math

# Add _utils to path
try:
    script_dir = os.path.dirname(os.path.abspath(__file__))
except NameError:
    script_dir = r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\scripts\08_acres"

utils_dir = os.path.join(os.path.dirname(script_dir), "_utils")
if utils_dir not in sys.path:
    sys.path.insert(0, utils_dir)

from config import GDB

arcpy.env.workspace = GDB
arcpy.env.overwriteOutput = True

# ==============================================================================
# CONFIGURATION
# ==============================================================================

# Input feature classes (from ingest_acres.py)
INPUT_TRANSACTIONS = os.path.join(GDB, "acres_transactions_polygon")
INPUT_PARCEL_CHANGES = os.path.join(GDB, "acres_parcel_changes_polygon")
INPUT_PARCELS = os.path.join(GDB, "acres_parcels_polygon")

# Output feature classes
OUTPUT_TRANSACTION_HISTORY = os.path.join(GDB, "parcel_transaction_history")
OUTPUT_MULTI_TRANSACTION = os.path.join(GDB, "multi_transaction_parcels")
OUTPUT_OWNERSHIP_CHAINS = os.path.join(GDB, "ownership_chains")

# CoreLogic/Cotality linkage placeholder paths
# These would be populated once CoreLogic data is available
CORELOGIC_TRANSACTIONS = os.path.join(GDB, "corelogic_transactions")  # Not yet available

# Analysis parameters
MIN_TRANSACTIONS_FOR_ANALYSIS = 2  # Minimum transactions to flag as multi-transaction
LAND_FLIP_THRESHOLD_DAYS = 365 * 2  # Flag parcels resold within 2 years


def load_transactions():
    """
    Load transaction data from ACRES.

    The ACRES transactions layer should contain:
    - apn: Parcel number (unique identifier)
    - entity: Current/new owner
    - change_date: Transaction date
    - owner_change_type: Type of change (new owner, internal transfer, previous owner)
    - computed_acres: Parcel size
    """
    print("\n   Loading ACRES transaction data...")

    transactions = []

    # Try multiple sources in priority order
    input_sources = [
        INPUT_PARCEL_CHANGES,  # Most likely to have change history
        INPUT_TRANSACTIONS,
        INPUT_PARCELS
    ]

    input_fc = None
    for source in input_sources:
        if arcpy.Exists(source):
            input_fc = source
            break

    if not input_fc:
        print("   ERROR: No ACRES transaction data found. Run ingest_acres.py first.")
        return []

    print(f"   Using: {os.path.basename(input_fc)}")

    # Get available fields
    available_fields = [f.name for f in arcpy.ListFields(input_fc)]
    print(f"   Available fields: {available_fields[:15]}...")

# Build field mapping based on official ACRES schema
    field_map = {}
    expected_fields = {
        # Common fields
        'apn': ['apn', 'parcel_number', 'parcel_id'],
        'entity': ['entity', 'owner'],
        'state': ['state', 'state_abbr'],
        'county': ['county'],
        'acres': ['computed_acres', 'acres', 'area_acres'],
        'new_record': ['new_record'],

        # Parcel Changes layer fields
        'change_date': ['change_date', 'transaction_date'],
        'change_type': ['owner_change_type', 'change_type'],
        'change_date_yearmoda': ['change_date_yearmoda'],

        # Transactions layer fields (have sale prices!)
        'transaction_date': ['transaction_date'],
        'transaction_amount': ['transaction_amount', 'sale_price', 'price'],  # KEY: Sale price
        'buyer_name': ['buyer_name'],  # Who bought
        'seller_name': ['seller_name'],  # Who sold
        'transaction_type': ['transaction_type'],  # buyer/seller/internal transaction
        'transaction_date_yearmoda': ['transaction_date_yearmoda'],
    }

    for target, candidates in expected_fields.items():
        for candidate in candidates:
            for actual in available_fields:
                if actual.lower() == candidate.lower():
                    field_map[target] = actual
                    break
            if target in field_map:
                break

    print(f"   Field mapping: {field_map}")

    # Build cursor field list
    cursor_fields = ['SHAPE@', 'OBJECTID']
    for target, actual in field_map.items():
        if actual not in cursor_fields:
            cursor_fields.append(actual)

    # Read transactions
    with arcpy.da.SearchCursor(input_fc, cursor_fields) as cursor:
        for row in cursor:
            shape = row[0]
            if not shape:
                continue

            centroid = shape.centroid

            record = {
                'shape': shape,
                'oid': row[1],
                'lon': centroid.X if centroid else None,
                'lat': centroid.Y if centroid else None,
            }

            # Map field values
            for i, field in enumerate(cursor_fields[2:], 2):
                for target, actual in field_map.items():
                    if actual == field:
                        record[target] = row[i]
                        break

            transactions.append(record)

    print(f"   Loaded {len(transactions):,} transaction records")
    return transactions


def group_transactions_by_parcel(transactions):
    """
    Group transactions by parcel (APN) to build ownership history.
    """
    print("\n   Grouping transactions by parcel...")

    by_parcel = defaultdict(list)

    for txn in transactions:
        apn = txn.get('apn')
        if not apn:
            continue
        by_parcel[apn].append(txn)

    # Sort each parcel's transactions by date
    for apn, txn_list in by_parcel.items():
        # Sort by change_date
        txn_list.sort(key=lambda x: x.get('change_date') or datetime.min)

    print(f"   Found {len(by_parcel):,} unique parcels")

    # Count multi-transaction parcels
    multi_txn_count = sum(1 for apn, txns in by_parcel.items() if len(txns) >= MIN_TRANSACTIONS_FOR_ANALYSIS)
    print(f"   Parcels with {MIN_TRANSACTIONS_FOR_ANALYSIS}+ transactions: {multi_txn_count:,}")

    return by_parcel


def build_ownership_chains(transactions_by_parcel):
    """
    Build ownership chain records for each parcel.

    Chain format:
    - apn
    - transaction_sequence: 1, 2, 3...
    - date
    - new_owner
    - previous_owner (if available)
    - change_type
    - days_since_previous
    - sale_price (if available)
    - price_per_acre (if calculable)
    """
    print("\n   Building ownership chains...")

    chains = []

    for apn, txn_list in transactions_by_parcel.items():
        if len(txn_list) < 1:
            continue

        # Get parcel info from first transaction
        first_txn = txn_list[0]
        parcel_info = {
            'apn': apn,
            'state': first_txn.get('state'),
            'county': first_txn.get('county'),
            'acres': first_txn.get('acres'),
            'lat': first_txn.get('lat'),
            'lon': first_txn.get('lon'),
        }

        prev_date = None
        for seq, txn in enumerate(txn_list, 1):
            chain_record = {
                **parcel_info,
                'transaction_sequence': seq,
                'total_transactions': len(txn_list),
                'entity': txn.get('entity'),
                'change_date': txn.get('change_date'),
                'change_type': txn.get('change_type'),
                'previous_owner': txn.get('previous_owner'),
                'sale_price': txn.get('sale_price'),
            }

            # Calculate days since previous transaction
            current_date = txn.get('change_date')
            if prev_date and current_date:
                # Handle date objects
                if isinstance(prev_date, str):
                    try:
                        prev_date = datetime.strptime(str(prev_date)[:10], '%Y-%m-%d')
                    except:
                        pass
                if isinstance(current_date, str):
                    try:
                        current_date = datetime.strptime(str(current_date)[:10], '%Y-%m-%d')
                    except:
                        pass

                if hasattr(prev_date, 'days') or isinstance(prev_date, datetime):
                    if isinstance(current_date, datetime) and isinstance(prev_date, datetime):
                        delta = current_date - prev_date
                        chain_record['days_since_previous'] = delta.days

                        # Flag potential land flip
                        if delta.days <= LAND_FLIP_THRESHOLD_DAYS:
                            chain_record['potential_land_flip'] = True

            # Calculate price per acre if available
            acres = txn.get('acres')
            price = txn.get('sale_price')
            if acres and price and acres > 0:
                chain_record['price_per_acre'] = price / acres

            chains.append(chain_record)
            prev_date = txn.get('change_date')

    print(f"   Built {len(chains):,} ownership chain records")

    # Count potential land flips
    flip_count = sum(1 for c in chains if c.get('potential_land_flip'))
    print(f"   Potential land flips (resold within {LAND_FLIP_THRESHOLD_DAYS} days): {flip_count:,}")

    return chains


def identify_case_studies(transactions_by_parcel, chains):
    """
    Identify notable case studies:
    1. Vantage Wisconsin (Cloverleaf → Vantage)
    2. Other multi-transaction parcels
    """
    print("\n   Identifying case studies...")

    case_studies = []

    # Search for Vantage/Cloverleaf pattern
    for apn, txn_list in transactions_by_parcel.items():
        entities = [t.get('entity', '').lower() for t in txn_list if t.get('entity')]

        # Check for Vantage/Cloverleaf
        has_vantage = any('vantage' in e for e in entities)
        has_cloverleaf = any('cloverleaf' in e for e in entities)

        if has_vantage or has_cloverleaf:
            state = txn_list[0].get('state', 'Unknown')
            case_studies.append({
                'apn': apn,
                'case_type': 'Vantage/Cloverleaf',
                'state': state,
                'transaction_count': len(txn_list),
                'entities': list(set(t.get('entity') for t in txn_list if t.get('entity'))),
                'earliest_date': min((t.get('change_date') for t in txn_list if t.get('change_date')), default=None),
                'latest_date': max((t.get('change_date') for t in txn_list if t.get('change_date')), default=None),
            })

    # Find other notable multi-transaction parcels (3+ transactions)
    for apn, txn_list in transactions_by_parcel.items():
        if len(txn_list) >= 3:
            state = txn_list[0].get('state', 'Unknown')
            entities = list(set(t.get('entity') for t in txn_list if t.get('entity')))

            # Skip if already captured as Vantage/Cloverleaf
            if any(cs['apn'] == apn for cs in case_studies):
                continue

            case_studies.append({
                'apn': apn,
                'case_type': 'Multi-Transaction',
                'state': state,
                'transaction_count': len(txn_list),
                'entities': entities,
                'earliest_date': min((t.get('change_date') for t in txn_list if t.get('change_date')), default=None),
                'latest_date': max((t.get('change_date') for t in txn_list if t.get('change_date')), default=None),
            })

    # Sort by transaction count (most transactions first)
    case_studies.sort(key=lambda x: -x['transaction_count'])

    print(f"   Found {len(case_studies):,} notable case studies")

    # Print Vantage/Cloverleaf cases
    vantage_cases = [c for c in case_studies if c['case_type'] == 'Vantage/Cloverleaf']
    if vantage_cases:
        print(f"\n   VANTAGE/CLOVERLEAF CASE STUDIES:")
        for case in vantage_cases[:5]:
            print(f"     APN: {case['apn']} ({case['state']})")
            print(f"       Transactions: {case['transaction_count']}")
            print(f"       Entities: {', '.join(case['entities'][:3])}")

    return case_studies


def create_output_tables(chains, case_studies, transactions_by_parcel):
    """Create output feature classes for analysis results."""
    print("\n   Creating output tables...")

    records_created = {}

    # -------------------------------------------------------------------------
    # 1. Ownership Chains Table
    # -------------------------------------------------------------------------
    print(f"   Creating ownership chains table...")

    if arcpy.Exists(OUTPUT_OWNERSHIP_CHAINS):
        arcpy.management.Delete(OUTPUT_OWNERSHIP_CHAINS)

    # Create point feature class
    spatial_ref = arcpy.SpatialReference(4326)
    arcpy.management.CreateFeatureclass(
        GDB,
        os.path.basename(OUTPUT_OWNERSHIP_CHAINS),
        "POINT",
        spatial_reference=spatial_ref
    )

    # Add fields
    chain_fields = [
        ('apn', 'TEXT', 100),
        ('state', 'TEXT', 10),
        ('county', 'TEXT', 100),
        ('acres', 'DOUBLE', None),
        ('transaction_sequence', 'LONG', None),
        ('total_transactions', 'LONG', None),
        ('entity', 'TEXT', 200),
        ('change_date', 'DATE', None),
        ('change_type', 'TEXT', 100),
        ('previous_owner', 'TEXT', 200),
        ('days_since_previous', 'LONG', None),
        ('sale_price', 'DOUBLE', None),
        ('price_per_acre', 'DOUBLE', None),
        ('potential_land_flip', 'TEXT', 10),
    ]

    for field_name, field_type, field_length in chain_fields:
        if field_length:
            arcpy.management.AddField(OUTPUT_OWNERSHIP_CHAINS, field_name, field_type, field_length=field_length)
        else:
            arcpy.management.AddField(OUTPUT_OWNERSHIP_CHAINS, field_name, field_type)

    # Insert records
    insert_fields = ['SHAPE@XY'] + [f[0] for f in chain_fields]

    with arcpy.da.InsertCursor(OUTPUT_OWNERSHIP_CHAINS, insert_fields) as cursor:
        for chain in chains:
            if not chain.get('lon') or not chain.get('lat'):
                continue

            row = [
                (chain['lon'], chain['lat']),
                chain.get('apn'),
                chain.get('state'),
                chain.get('county'),
                chain.get('acres'),
                chain.get('transaction_sequence'),
                chain.get('total_transactions'),
                chain.get('entity'),
                chain.get('change_date'),
                chain.get('change_type'),
                chain.get('previous_owner'),
                chain.get('days_since_previous'),
                chain.get('sale_price'),
                chain.get('price_per_acre'),
                'Yes' if chain.get('potential_land_flip') else 'No',
            ]
            cursor.insertRow(row)

    count = int(arcpy.management.GetCount(OUTPUT_OWNERSHIP_CHAINS)[0])
    records_created['ownership_chains'] = count
    print(f"     Created {count:,} ownership chain records")

    # -------------------------------------------------------------------------
    # 2. Multi-Transaction Summary Table
    # -------------------------------------------------------------------------
    print(f"   Creating multi-transaction summary table...")

    if arcpy.Exists(OUTPUT_MULTI_TRANSACTION):
        arcpy.management.Delete(OUTPUT_MULTI_TRANSACTION)

    arcpy.management.CreateFeatureclass(
        GDB,
        os.path.basename(OUTPUT_MULTI_TRANSACTION),
        "POINT",
        spatial_reference=spatial_ref
    )

    # Add fields
    summary_fields = [
        ('apn', 'TEXT', 100),
        ('case_type', 'TEXT', 50),
        ('state', 'TEXT', 10),
        ('transaction_count', 'LONG', None),
        ('entities', 'TEXT', 500),
        ('earliest_date', 'DATE', None),
        ('latest_date', 'DATE', None),
        ('total_days', 'LONG', None),
    ]

    for field_name, field_type, field_length in summary_fields:
        if field_length:
            arcpy.management.AddField(OUTPUT_MULTI_TRANSACTION, field_name, field_type, field_length=field_length)
        else:
            arcpy.management.AddField(OUTPUT_MULTI_TRANSACTION, field_name, field_type)

    # Insert case studies
    insert_fields = ['SHAPE@XY'] + [f[0] for f in summary_fields]

    with arcpy.da.InsertCursor(OUTPUT_MULTI_TRANSACTION, insert_fields) as cursor:
        for case in case_studies:
            # Get coordinates from transactions
            apn = case['apn']
            if apn in transactions_by_parcel:
                txn = transactions_by_parcel[apn][0]
                lon, lat = txn.get('lon'), txn.get('lat')
            else:
                lon, lat = None, None

            if not lon or not lat:
                continue

            # Calculate total days
            total_days = None
            if case.get('earliest_date') and case.get('latest_date'):
                try:
                    d1 = case['earliest_date']
                    d2 = case['latest_date']
                    if isinstance(d1, str):
                        d1 = datetime.strptime(str(d1)[:10], '%Y-%m-%d')
                    if isinstance(d2, str):
                        d2 = datetime.strptime(str(d2)[:10], '%Y-%m-%d')
                    if isinstance(d1, datetime) and isinstance(d2, datetime):
                        total_days = (d2 - d1).days
                except:
                    pass

            row = [
                (lon, lat),
                case.get('apn'),
                case.get('case_type'),
                case.get('state'),
                case.get('transaction_count'),
                '; '.join(case.get('entities', [])[:10])[:499],
                case.get('earliest_date'),
                case.get('latest_date'),
                total_days,
            ]
            cursor.insertRow(row)

    count = int(arcpy.management.GetCount(OUTPUT_MULTI_TRANSACTION)[0])
    records_created['multi_transaction'] = count
    print(f"     Created {count:,} multi-transaction summary records")

    return records_created


def print_analysis_summary(chains, case_studies, transactions_by_parcel):
    """Print summary analysis."""
    print("\n" + "=" * 70)
    print("   MULTI-TRANSACTION PARCEL ANALYSIS SUMMARY")
    print("=" * 70)

    # Overall statistics
    total_parcels = len(transactions_by_parcel)
    multi_txn_parcels = sum(1 for apn, txns in transactions_by_parcel.items() if len(txns) >= 2)
    three_plus_parcels = sum(1 for apn, txns in transactions_by_parcel.items() if len(txns) >= 3)

    print(f"\n   Overview:")
    print(f"   {'Metric':<40} {'Value':>15}")
    print(f"   {'-'*40} {'-'*15}")
    print(f"   {'Total unique parcels':<40} {total_parcels:>15,}")
    print(f"   {'Parcels with 2+ transactions':<40} {multi_txn_parcels:>15,}")
    print(f"   {'Parcels with 3+ transactions':<40} {three_plus_parcels:>15,}")

    # Transaction count distribution
    print(f"\n   Transaction Count Distribution:")
    print(f"   {'# Transactions':<20} {'# Parcels':>15}")
    print(f"   {'-'*20} {'-'*15}")

    count_dist = defaultdict(int)
    for apn, txns in transactions_by_parcel.items():
        count_dist[len(txns)] += 1

    for txn_count in sorted(count_dist.keys())[:10]:
        print(f"   {txn_count:<20} {count_dist[txn_count]:>15,}")

    # Case studies by type
    if case_studies:
        print(f"\n   Case Studies by Type:")
        type_counts = defaultdict(int)
        for case in case_studies:
            type_counts[case['case_type']] += 1

        for case_type, count in sorted(type_counts.items()):
            print(f"   {case_type}: {count:,}")

    # Top entities with multi-transactions
    print(f"\n   Top Entities with Multiple Transactions:")
    entity_counts = defaultdict(int)
    for chain in chains:
        entity = chain.get('entity')
        if entity:
            entity_counts[entity] += 1

    print(f"   {'Entity':<40} {'Transactions':>15}")
    print(f"   {'-'*40} {'-'*15}")

    for entity, count in sorted(entity_counts.items(), key=lambda x: -x[1])[:15]:
        entity_display = entity[:38] + '..' if len(entity) > 40 else entity
        print(f"   {entity_display:<40} {count:>15,}")

    # Potential land flips
    flip_chains = [c for c in chains if c.get('potential_land_flip')]
    if flip_chains:
        print(f"\n   Potential Land Flips (resold within {LAND_FLIP_THRESHOLD_DAYS} days):")
        print(f"   Total: {len(flip_chains):,} transactions")

        # Show examples
        print(f"\n   Examples:")
        for chain in flip_chains[:5]:
            print(f"     APN: {chain.get('apn')}")
            print(f"       {chain.get('entity')} ({chain.get('days_since_previous')} days after previous)")


def generate_corelogic_linkage_guide():
    """Generate documentation for CoreLogic/Cotality data linkage."""
    print("\n   Generating CoreLogic linkage guide...")

    guide_content = """# CoreLogic/Cotality Data Linkage Guide

## Overview

To complete the resale premium analysis (e.g., Cloverleaf → Vantage transaction pricing),
we need to link ACRES parcel data with CoreLogic/Cotality transaction price data.

## Required Data Fields from CoreLogic/Cotality

| Field | Description | Priority |
|-------|-------------|----------|
| `apn` | Assessor Parcel Number (primary join key) | Required |
| `recording_date` | Date of deed recording | Required |
| `sale_price` | Transaction price / consideration | Required |
| `sale_date` | Date of sale | Required |
| `grantor` | Seller name | High |
| `grantee` | Buyer name | High |
| `document_type` | Deed type (warranty, quitclaim, etc.) | Medium |
| `assessed_value` | County assessed value | Medium |
| `market_value` | Estimated market value | Medium |
| `price_per_acre` | Calculated $/acre | Derived |

## Linkage Method

### Primary Key: APN (Assessor Parcel Number)

The APN is the primary join key between ACRES and CoreLogic data.
APNs are standardized within each county but formats vary by state/county.

```python
# Example join logic
arcpy.management.AddJoin(
    in_layer_or_view="acres_parcels_polygon",
    in_field="apn",
    join_table="corelogic_transactions",
    join_field="apn",
    join_type="KEEP_ALL"
)
```

### Secondary Matching (for missing APNs)

If APNs don't match directly:
1. Spatial join by parcel centroid (within 50m tolerance)
2. Fuzzy match on owner name + date
3. Address matching (if available)

## Analysis Workflow

1. **Import CoreLogic data** to geodatabase
2. **Standardize APNs** (remove formatting characters, leading zeros, etc.)
3. **Join ACRES to CoreLogic** by APN + date window
4. **Calculate metrics**:
   - Sale price vs. assessed value ratio
   - Resale premium (sale price / previous sale price)
   - Days between transactions
   - Price per acre trend

## Resale Premium Calculation

```python
# For each parcel with multiple transactions
resale_premium = (later_sale_price - earlier_sale_price) / earlier_sale_price * 100

# Annualized return
days_held = (later_date - earlier_date).days
annualized_return = ((1 + resale_premium/100) ** (365/days_held) - 1) * 100
```

## Data Access

Contact the following teams for CoreLogic/Cotality data access:
- Infrastructure Data Team
- Real Estate Analytics Team
- Land Acquisition Team

## Implementation Status

- [x] ACRES data ingested
- [x] Multi-transaction parcels identified
- [x] Ownership chains built
- [ ] CoreLogic data access obtained
- [ ] APN matching implemented
- [ ] Resale premium analysis completed
"""

    guide_path = os.path.join(
        script_dir,
        "..", "00_docs", "workflows", "CORELOGIC_LINKAGE_GUIDE.md"
    )

    try:
        os.makedirs(os.path.dirname(guide_path), exist_ok=True)
        with open(guide_path, 'w', encoding='utf-8') as f:
            f.write(guide_content)
        print(f"   Guide saved to: {guide_path}")
    except Exception as e:
        print(f"   Could not save guide: {e}")

    return guide_content


def main():
    """Main function for multi-transaction parcel analysis."""
    print("=" * 70)
    print("   MULTI-TRANSACTION PARCEL ANALYSIS")
    print("=" * 70)
    print(f"   Started: {datetime.now()}")
    print(f"\n   Purpose: Track parcels with multiple ownership changes")
    print(f"            Identify resale patterns (e.g., Cloverleaf → Vantage)")

    # Step 1: Load transactions
    print("\n" + "-" * 70)
    print("[Step 1] Loading ACRES transaction data...")
    print("-" * 70)
    transactions = load_transactions()

    if not transactions:
        print("\n   ERROR: No transactions found. Run ingest_acres.py first.")
        print("\n   NOTE: This analysis requires the parcel_changes layer from ACRES.")
        return

    # Step 2: Group by parcel
    print("\n" + "-" * 70)
    print("[Step 2] Grouping transactions by parcel (APN)...")
    print("-" * 70)
    transactions_by_parcel = group_transactions_by_parcel(transactions)

    # Step 3: Build ownership chains
    print("\n" + "-" * 70)
    print("[Step 3] Building ownership chains...")
    print("-" * 70)
    chains = build_ownership_chains(transactions_by_parcel)

    # Step 4: Identify case studies
    print("\n" + "-" * 70)
    print("[Step 4] Identifying case studies (Vantage WI, etc.)...")
    print("-" * 70)
    case_studies = identify_case_studies(transactions_by_parcel, chains)

    # Step 5: Create output tables
    print("\n" + "-" * 70)
    print("[Step 5] Creating output tables...")
    print("-" * 70)
    records_created = create_output_tables(chains, case_studies, transactions_by_parcel)

    # Step 6: Print summary
    print_analysis_summary(chains, case_studies, transactions_by_parcel)

    # Step 7: Generate CoreLogic linkage guide
    print("\n" + "-" * 70)
    print("[Step 7] Generating CoreLogic linkage documentation...")
    print("-" * 70)
    generate_corelogic_linkage_guide()

    # Final summary
    print("\n" + "=" * 70)
    print("   ANALYSIS COMPLETE")
    print("=" * 70)
    print(f"\n   Output feature classes:")
    for name, count in records_created.items():
        print(f"     - {name}: {count:,} records")

    print(f"\n   NOTE: To complete resale premium analysis, CoreLogic/Cotality")
    print(f"         data with transaction prices is required.")
    print(f"         See: CORELOGIC_LINKAGE_GUIDE.md")

    print(f"\n   Completed: {datetime.now()}")
    print("=" * 70)

    return chains, case_studies


# ==============================================================================
# EXECUTE
# ==============================================================================

if __name__ == "__main__":
    main()
else:
    main()
