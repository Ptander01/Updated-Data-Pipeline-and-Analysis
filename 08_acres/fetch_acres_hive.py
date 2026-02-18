"""
ACRES Hive Query Script
=======================

Queries ACRES datacenter parcel/transaction data from Meta Hive tables.

TABLE SOURCES:
  - idc_lsim_datacenter_index_parcel_changes_centroid
  - idc_lsim_datacenter_index_parcel_changes_polygon
  - idc_lsim_datacenter_index_parcels_centroid
  - idc_lsim_datacenter_index_parcels_polygon
  - idc_lsim_datacenter_index_transactions_centroid
  - idc_lsim_datacenter_index_transactions_polygon

DATA LAYERS:
  - Parcels: Who owns what currently (snapshot)
  - Transactions: Courthouse/assessor transaction records
  - Parcel Changes: Monthly diff on owner name (catches non-disclosure states)

PREREQUISITES:
1. Access to Meta Hive infrastructure (VPN or on-network)
2. ACL permissions for ACRES tables
3. Presto/Hive Python client installed (pyhive or presto-python-client)

USAGE IN BENTO:
  Use %%presto magic or bento.common.presto for direct queries

SAMPLE QUERY:
  SELECT * FROM idc_lsim_datacenter_index_parcel_changes_centroid WHERE ds = '2025-11-21'

Author: Meta Data Center GIS Team
Created: 2026-01-30
"""

import os
import sys
from datetime import datetime
from pathlib import Path

# Configuration
OUTPUT_DIR = Path(r"C:\Users\ptanderson\Downloads\Pipeline_Ingestion\ACRES")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ==============================================================================
# HIVE CONNECTION CONFIGURATION
# ==============================================================================

PRESTO_HOST = 'presto.intern.facebook.com'
PRESTO_PORT = 8080
PRESTO_CATALOG = 'hive'
PRESTO_SCHEMA = 'default'

# ==============================================================================
# ACRES TABLE CONFIGURATION
# ==============================================================================

ACRES_TABLES = {
    # Parcel Changes - Monthly diff on owner name (best for catching ownership changes)
    'parcel_changes_centroid': 'idc_lsim_datacenter_index_parcel_changes_centroid',
    'parcel_changes_polygon': 'idc_lsim_datacenter_index_parcel_changes_polygon',

    # Parcels - Current ownership snapshot
    'parcels_centroid': 'idc_lsim_datacenter_index_parcels_centroid',
    'parcels_polygon': 'idc_lsim_datacenter_index_parcels_polygon',

    # Transactions - Courthouse/assessor records (has sale dates, prices in disclosure states)
    'transactions_centroid': 'idc_lsim_datacenter_index_transactions_centroid',
    'transactions_polygon': 'idc_lsim_datacenter_index_transactions_polygon',
}

# Key fields expected in ACRES data (based on sample attribute table)
ACRES_EXPECTED_FIELDS = [
    'entity',               # Owner/company (parent entity)
    'new_record',           # "new" for recent additions, None for existing
    'owner_change_type',    # "new owner", "internal transfer", "previous owner"
    'state',                # State abbreviation
    'county',               # County name
    'apn',                  # Assessor Parcel Number (unique identifier)
    'change_date',          # Date of ownership change
    'change_date_year',     # Year+month in YYYYMMDD format
    'computed_acres',       # Parcel size in acres
    'sale_date',            # Transaction date (from Transactions layer)
    'source',               # Data source ("Web Source" = scraped)
]


def get_latest_ds():
    """Get the latest ds partition value (today's date in YYYY-MM-DD format)."""
    return datetime.now().strftime('%Y-%m-%d')


def check_presto_available():
    """Check if Presto client is installed."""
    try:
        from pyhive import presto
        return True
    except ImportError:
        print("WARNING: pyhive not installed. Install with: pip install pyhive")
        return False


def get_presto_connection():
    """Get Presto connection to Meta Hive."""
    try:
        from pyhive import presto

        conn = presto.connect(
            host=PRESTO_HOST,
            port=PRESTO_PORT,
            username=os.environ.get('USER', 'ptanderson'),
            catalog=PRESTO_CATALOG,
            schema=PRESTO_SCHEMA
        )
        return conn
    except Exception as e:
        print(f"ERROR: Could not connect to Presto: {e}")
        return None


def query_acres_table(conn, table_key, ds=None, limit=None, filter_new_only=False):
    """
    Query ACRES data from Hive.

    Args:
        conn: Presto connection
        table_key: Key from ACRES_TABLES dict
        ds: Date partition (YYYY-MM-DD format). Defaults to latest available.
        limit: Optional row limit for testing
        filter_new_only: If True, only return records where new_record = 'new'

    Returns DataFrame with all columns from the table.
    """
    import pandas as pd

    if table_key not in ACRES_TABLES:
        raise ValueError(f"Unknown table key: {table_key}. Valid keys: {list(ACRES_TABLES.keys())}")

    table_name = ACRES_TABLES[table_key]

    if ds is None:
        ds = get_latest_ds()

    # Build query
    where_clauses = [f"ds = '{ds}'"]
    if filter_new_only:
        where_clauses.append("new_record = 'new'")

    query = f"""
        SELECT *
        FROM {table_name}
        WHERE {' AND '.join(where_clauses)}
        {"LIMIT " + str(limit) if limit else ""}
    """

    print(f"\nExecuting query against {table_name} (ds={ds})...")
    if filter_new_only:
        print("  Filtering: new_record = 'new' only")

    cursor = conn.cursor()
    cursor.execute(query)

    columns = [desc[0] for desc in cursor.description]
    rows = cursor.fetchall()

    df = pd.DataFrame(rows, columns=columns)
    print(f"  Retrieved {len(df):,} records")
    print(f"  Columns: {len(columns)}")

    return df


def query_parcel_changes(conn, ds=None, limit=None, new_only=False):
    """
    Query ACRES Parcel Changes data - the best source for ownership changes.

    The parcel_changes layer does monthly diffs on owner name, which catches
    transactions even in non-disclosure states.

    Use new_only=True to get only recent additions (new_record = 'new').
    """
    return query_acres_table(conn, 'parcel_changes_polygon', ds, limit, new_only)


def query_parcels(conn, ds=None, limit=None):
    """
    Query ACRES Parcels data - current ownership snapshot.

    Shows who owns what parcels currently.
    """
    return query_acres_table(conn, 'parcels_polygon', ds, limit)


def query_transactions(conn, ds=None, limit=None):
    """
    Query ACRES Transactions data - courthouse/assessor records.

    Has sale dates and prices in disclosure states.
    """
    return query_acres_table(conn, 'transactions_polygon', ds, limit)


def export_to_csv(df, output_name, output_dir=OUTPUT_DIR):
    """Export DataFrame to CSV with timestamp."""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M')
    filename = f"acres_{output_name}_{timestamp}.csv"
    filepath = output_dir / filename

    df.to_csv(filepath, index=False)
    print(f"  Exported: {filepath}")
    print(f"  Records: {len(df):,}")

    return filepath


def analyze_new_records(df):
    """Analyze distribution of new vs existing records."""
    if 'new_record' not in df.columns:
        print("  new_record field not found")
        return

    print("\n  New Record Distribution:")
    counts = df['new_record'].value_counts()
    for val, count in counts.items():
        print(f"    {val}: {count:,}")


def analyze_entities(df, top_n=20):
    """Show top entities by parcel count."""
    if 'entity' not in df.columns:
        print("  entity field not found")
        return

    print(f"\n  Top {top_n} Entities by Parcel Count:")
    counts = df['entity'].value_counts().head(top_n)
    for entity, count in counts.items():
        entity_display = entity[:50] + '...' if len(str(entity)) > 50 else entity
        print(f"    {entity_display}: {count:,}")


def analyze_owner_change_types(df):
    """Show distribution of owner change types."""
    if 'owner_change_type' not in df.columns:
        print("  owner_change_type field not found")
        return

    print("\n  Owner Change Type Distribution:")
    counts = df['owner_change_type'].value_counts()
    for val, count in counts.items():
        print(f"    {val}: {count:,}")


def analyze_states(df, top_n=10):
    """Show top states by parcel count."""
    if 'state' not in df.columns:
        print("  state field not found")
        return

    print(f"\n  Top {top_n} States by Parcel Count:")
    counts = df['state'].value_counts().head(top_n)
    for state, count in counts.items():
        print(f"    {state}: {count:,}")


def main(ds=None, export_all=False, analyze=True):
    """
    Main execution function.

    Args:
        ds: Date partition to query. Defaults to latest.
        export_all: If True, export all tables. If False, only parcel_changes.
        analyze: If True, print analysis summary.
    """
    print("=" * 70)
    print("ACRES HIVE DATA PULL")
    print(f"Started: {datetime.now()}")
    print("=" * 70)

    # Check prerequisites
    if not check_presto_available():
        print("\nPresto client not available. Please install pyhive:")
        print("  pip install pyhive")
        print("\nAlternatively, run this notebook in Bento where pyhive is pre-installed.")
        return

    # Get connection
    print(f"\nConnecting to Presto ({PRESTO_HOST})...")
    conn = get_presto_connection()

    if conn is None:
        print("\nCould not establish Presto connection.")
        print("Please check:")
        print("  1. You are on Meta network (VPN or on-site)")
        print("  2. You have ACL access to the ACRES Hive tables")
        print("  3. The Presto host/port are correct")
        return

    print("  Connected successfully!")

    results = {}

    # Query Parcel Changes (primary table for ownership analysis)
    print("\n" + "-" * 50)
    print("Querying ACRES Parcel Changes data...")
    print("-" * 50)
    try:
        df_changes = query_parcel_changes(conn, ds=ds)
        results['parcel_changes'] = df_changes

        if analyze:
            analyze_new_records(df_changes)
            analyze_entities(df_changes)
            analyze_owner_change_types(df_changes)
            analyze_states(df_changes)

        export_to_csv(df_changes, "parcel_changes_polygon")
    except Exception as e:
        print(f"  ERROR: {e}")
        df_changes = None

    # Query additional tables if requested
    if export_all:
        # Parcels
        print("\n" + "-" * 50)
        print("Querying ACRES Parcels data...")
        print("-" * 50)
        try:
            df_parcels = query_parcels(conn, ds=ds)
            results['parcels'] = df_parcels
            export_to_csv(df_parcels, "parcels_polygon")
        except Exception as e:
            print(f"  ERROR: {e}")

        # Transactions
        print("\n" + "-" * 50)
        print("Querying ACRES Transactions data...")
        print("-" * 50)
        try:
            df_transactions = query_transactions(conn, ds=ds)
            results['transactions'] = df_transactions
            export_to_csv(df_transactions, "transactions_polygon")
        except Exception as e:
            print(f"  ERROR: {e}")

    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)

    for name, df in results.items():
        if df is not None:
            print(f"  {name}: {len(df):,} records exported")
        else:
            print(f"  {name}: FAILED")

    print(f"\nOutput directory: {OUTPUT_DIR}")
    print("\nNext Steps:")
    print("  1. Run ingest_acres.py with source='csv' to import CSVs to geodatabase")
    print("  2. Run acres_parcel_rollup.py to create campus centroids")
    print("  3. Run analysis scripts for time-lag and transaction analysis")
    print("=" * 70)

    return results


# ==============================================================================
# BENTO/JUPYTER QUERIES
# ==============================================================================

BENTO_EXAMPLES = """
# ============================================================================
# BENTO NOTEBOOK EXAMPLES
# ============================================================================

# Example 1: Basic query with %%presto magic
%%presto
SELECT entity, COUNT(*) as parcel_count
FROM idc_lsim_datacenter_index_parcel_changes_polygon
WHERE ds = '2025-11-21'
GROUP BY entity
ORDER BY parcel_count DESC
LIMIT 20

# Example 2: New records only (recent additions)
%%presto
SELECT *
FROM idc_lsim_datacenter_index_parcel_changes_polygon
WHERE ds = '2025-11-21'
  AND new_record = 'new'
ORDER BY change_date DESC

# Example 3: Filter by entity (e.g., Meta sites)
%%presto
SELECT *
FROM idc_lsim_datacenter_index_parcel_changes_polygon
WHERE ds = '2025-11-21'
  AND entity LIKE '%META%'

# Example 4: Filter by state (e.g., Wisconsin for Vantage case study)
%%presto
SELECT *
FROM idc_lsim_datacenter_index_parcel_changes_polygon
WHERE ds = '2025-11-21'
  AND state = 'WI'
ORDER BY change_date DESC

# Example 5: Using bento.common.presto
from bento.common.presto import presto

df = presto.query('''
    SELECT entity, state, county, apn, change_date, computed_acres
    FROM idc_lsim_datacenter_index_parcel_changes_polygon
    WHERE ds = '2025-11-21'
      AND entity LIKE '%VANTAGE%' OR entity LIKE '%CLOVERLEAF%'
    ORDER BY change_date
''')
df.head()

# Example 6: Summary stats
%%presto
SELECT
    COUNT(DISTINCT apn) as unique_parcels,
    COUNT(DISTINCT entity) as unique_entities,
    SUM(computed_acres) as total_acres,
    COUNT(CASE WHEN new_record = 'new' THEN 1 END) as new_records
FROM idc_lsim_datacenter_index_parcel_changes_polygon
WHERE ds = '2025-11-21'
"""


def print_bento_examples():
    """Print example Bento/Jupyter queries."""
    print(BENTO_EXAMPLES)


# ==============================================================================
# EXECUTE
# ==============================================================================

if __name__ == "__main__":
    print("\n" + "!" * 70)
    print("ACRES HIVE DATA FETCH")
    print("Tables: idc_lsim_datacenter_index_*")
    print("!" * 70 + "\n")

    # Print instructions
    print("USAGE OPTIONS:")
    print("-" * 50)
    print("\n1. Run in Bento notebook (recommended):")
    print("   from bento.common.presto import presto")
    print("   df = presto.query('SELECT * FROM idc_lsim_datacenter_index_parcel_changes_polygon WHERE ds = \\'2025-11-21\\'')")
    print("\n2. Run this script with pyhive installed:")
    print("   main(ds='2025-11-21', export_all=True)")
    print("\n3. Export only new records:")
    print("   query_parcel_changes(conn, ds='2025-11-21', new_only=True)")
    print("\n" + "-" * 50)
    print("\nSample Bento queries:")
    print_bento_examples()

    # Uncomment to run when access is available:
    # main(export_all=True)
