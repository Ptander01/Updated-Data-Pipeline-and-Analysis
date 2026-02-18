"""
SA vs DCH Data Refresh and Comparison Orchestration
====================================================

This script orchestrates:
1. SemiAnalysis data refresh (from Excel via semianalysis_pipeline.py)
2. DataCenterHawk data refresh (from Hive via fetch_dch_hive.py OR existing raw tables)
3. Running the comparison between SA and DCH feature classes

Use this script as a single entry point for refreshing both data sources
and generating a comprehensive comparison report.

Author: Meta Data Center GIS Team
Created: 2026-01-29

USAGE (in ArcGIS Pro Python window):
    exec(open(r"C:\\Users\\ptanderson\\Documents\\ArcGIS\\Projects\\Lean Consensus DC Model\\scripts\\05_accuracy\\refresh_and_compare.py", encoding='utf-8').read())
"""

import os
import sys
from datetime import datetime
from pathlib import Path

# Script locations
SCRIPTS_DIR = Path(r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\scripts")
UTILS_DIR = SCRIPTS_DIR / "_utils"
INGESTION_DIR = SCRIPTS_DIR / "01_ingestion"
ACCURACY_DIR = SCRIPTS_DIR / "05_accuracy"

# Add utils to path
if str(UTILS_DIR) not in sys.path:
    sys.path.insert(0, str(UTILS_DIR))

from config import GDB, GOLD_BUILDINGS


def run_script(script_path, description):
    """Execute a Python script and capture results."""
    print(f"\n{'='*70}")
    print(f"RUNNING: {description}")
    print(f"Script: {script_path}")
    print('='*70)

    if not os.path.exists(script_path):
        print(f"  ERROR: Script not found: {script_path}")
        return False

    try:
        exec(open(script_path, encoding='utf-8').read(), {'__name__': '__exec__'})
        print(f"\n  [OK] {description} completed")
        return True
    except Exception as e:
        print(f"\n  [ERROR] {description} failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def check_data_vintage():
    """Check current data vintage in gold_buildings for SA and DCH."""
    import arcpy

    print("\n" + "="*70)
    print("CURRENT DATA VINTAGE CHECK")
    print("="*70)

    if not arcpy.Exists(GOLD_BUILDINGS):
        print("  ERROR: gold_buildings_full not found")
        return

    # Check SA vintage
    sa_query = "source = 'Semianalysis'"
    with arcpy.da.SearchCursor(GOLD_BUILDINGS, ['data_vintage'], sa_query) as cursor:
        sa_vintages = [row[0] for row in cursor if row[0]]

    if sa_vintages:
        latest_sa = max(sa_vintages)
        print(f"\n  SemiAnalysis:")
        print(f"    Records: {len(sa_vintages)}")
        print(f"    Latest data_vintage: {latest_sa}")
    else:
        print(f"\n  SemiAnalysis: No records found")

    # Check DCH vintage
    dch_query = "source = 'DataCenterHawk'"
    with arcpy.da.SearchCursor(GOLD_BUILDINGS, ['data_vintage', 'ingest_date'], dch_query) as cursor:
        dch_data = [(row[0], row[1]) for row in cursor]

    if dch_data:
        dch_vintages = [d[0] for d in dch_data if d[0]]
        dch_ingests = [d[1] for d in dch_data if d[1]]

        print(f"\n  DataCenterHawk:")
        print(f"    Records: {len(dch_data)}")
        if dch_vintages:
            print(f"    Latest data_vintage: {max(dch_vintages)}")
        if dch_ingests:
            print(f"    Latest ingest_date: {max(dch_ingests)}")
    else:
        print(f"\n  DataCenterHawk: No records found")


def refresh_semianalysis():
    """
    Refresh SemiAnalysis data.

    This runs two scripts:
    1. semianalysis_pipeline.py - Extracts data from Excel and exports CSV
    2. ingest_semianalysis_v2.py - Ingests CSV into geodatabase

    NOTE: Before running, ensure:
    - The INPUT_FILE path in semianalysis_pipeline.py points to the latest SA Excel
    - The SOURCE_CSV path in ingest_semianalysis_v2.py points to the output from step 1
    """
    print("\n" + "#"*70)
    print("# SEMIANALYSIS REFRESH")
    print("#"*70)

    # Step 1: Run SA pipeline (extract from Excel)
    sa_pipeline = UTILS_DIR / "semianalysis_pipeline.py"
    success1 = run_script(str(sa_pipeline), "SemiAnalysis Excel Extraction")

    if not success1:
        print("\n  WARNING: SA extraction failed. Skipping ingestion.")
        return False

    # Step 2: Run SA ingestion (insert to geodatabase)
    # Note: User may need to update SOURCE_CSV path first
    sa_ingest = INGESTION_DIR / "ingest_semianalysis_v2.py"
    success2 = run_script(str(sa_ingest), "SemiAnalysis Geodatabase Ingestion")

    return success2


def refresh_datacenterhawk(use_hive=False):
    """
    Refresh DataCenterHawk data.

    Args:
        use_hive: If True, attempt to pull from Hive tables (requires access)
                  If False, use existing raw tables (manual CSV import required)

    NOTE: Hive access is pending. For now, manual workflow:
    1. Export DCH data from portal as CSV
    2. Import CSV to dch_hyper_raw / dch_lease_raw tables in geodatabase
    3. Run the ingestion scripts
    """
    print("\n" + "#"*70)
    print("# DATACENTERHAWK REFRESH")
    print("#"*70)

    if use_hive:
        print("\n  Attempting Hive data pull...")
        hive_script = INGESTION_DIR / "fetch_dch_hive.py"
        if run_script(str(hive_script), "DCH Hive Data Pull"):
            print("\n  Hive pull successful. Now ingesting to geodatabase...")
        else:
            print("\n  Hive pull failed. Falling back to existing raw tables...")
    else:
        print("\n  Using existing raw tables (manual CSV import workflow)")
        print("  Ensure dch_hyper_raw and dch_lease_raw are up to date")

    # Run DCH Hyper ingestion
    dch_hyper_ingest = INGESTION_DIR / "ingest_dch.py"
    success1 = run_script(str(dch_hyper_ingest), "DCH Hyperscale Ingestion")

    # Run DCH Lease ingestion
    dch_lease_ingest = INGESTION_DIR / "ingest_dch_lease.py"
    success2 = run_script(str(dch_lease_ingest), "DCH Lease Ingestion")

    return success1 and success2


def run_comparison():
    """Run the SA vs DCH comparison script."""
    print("\n" + "#"*70)
    print("# SA vs DCH COMPARISON")
    print("#"*70)

    compare_script = ACCURACY_DIR / "compare_sa_vs_dch.py"
    return run_script(str(compare_script), "SA vs DCH Comparison Analysis")


def run_post_processing():
    """Run post-processing steps after data refresh."""
    print("\n" + "#"*70)
    print("# POST-PROCESSING")
    print("#"*70)

    # Company field standardization
    company_script = SCRIPTS_DIR / "02_processing" / "migrate_company_fields_v2.py"
    if company_script.exists():
        run_script(str(company_script), "Company Field Standardization")

    # UCID generation
    ucid_script = SCRIPTS_DIR / "03_ucid" / "generate_text_ucid.py"
    if ucid_script.exists():
        run_script(str(ucid_script), "UCID Generation")

    # Campus rollup
    rollup_script = SCRIPTS_DIR / "02_processing" / "campus_rollup_new.py"
    if rollup_script.exists():
        run_script(str(rollup_script), "Campus Rollup")


def main(
    refresh_sa=True,
    refresh_dch=True,
    use_hive=False,
    run_post_proc=True,
    run_compare=True
):
    """
    Main orchestration function.

    Args:
        refresh_sa: Whether to refresh SemiAnalysis data
        refresh_dch: Whether to refresh DataCenterHawk data
        use_hive: Whether to attempt Hive pull for DCH (requires access)
        run_post_proc: Whether to run post-processing (company fields, UCID, rollup)
        run_compare: Whether to run the comparison analysis
    """
    print("="*70)
    print("SA vs DCH DATA REFRESH AND COMPARISON")
    print(f"Started: {datetime.now()}")
    print("="*70)

    # Show current state
    check_data_vintage()

    # Refresh data sources
    if refresh_sa:
        refresh_semianalysis()

    if refresh_dch:
        refresh_datacenterhawk(use_hive=use_hive)

    # Post-processing
    if run_post_proc and (refresh_sa or refresh_dch):
        run_post_processing()

    # Run comparison
    if run_compare:
        run_comparison()

    # Final summary
    print("\n" + "="*70)
    print("ORCHESTRATION COMPLETE")
    print(f"Finished: {datetime.now()}")
    print("="*70)

    print("\nSummary of actions:")
    print(f"  - SemiAnalysis refresh: {'Yes' if refresh_sa else 'Skipped'}")
    print(f"  - DataCenterHawk refresh: {'Yes' if refresh_dch else 'Skipped'}")
    print(f"  - Post-processing: {'Yes' if run_post_proc else 'Skipped'}")
    print(f"  - Comparison analysis: {'Yes' if run_compare else 'Skipped'}")

    print("\nOutput locations:")
    print(f"  - Comparison report: scripts/00_docs/reports/SA_vs_DCH_Comparison_*.html")
    print(f"  - Pipeline reports: G:/My Drive/.../Admin Documentation/pipeline_diagnostics/")


# ==============================================================================
# INTERACTIVE MODE
# ==============================================================================

def interactive_menu():
    """Display interactive menu for manual execution."""
    print("\n" + "="*70)
    print("SA vs DCH REFRESH AND COMPARISON - INTERACTIVE MODE")
    print("="*70)
    print("""
Choose an option:

  1. Full refresh + comparison (SA + DCH + post-processing + compare)
  2. Refresh SA only (Excel extraction + ingestion)
  3. Refresh DCH only (using existing raw tables)
  4. Run comparison only (no data refresh)
  5. Check current data vintages
  6. Exit

Note: Option 3 requires manual CSV import to raw tables first.
      Hive data pull is pending ACL access.
""")


# ==============================================================================
# EXECUTE
# ==============================================================================

if __name__ == "__main__":
    # Default: Run comparison only (no refresh)
    main(refresh_sa=False, refresh_dch=False, run_compare=True)
else:
    # Running via exec() - print menu
    print("""
SA vs DCH REFRESH AND COMPARISON SCRIPT LOADED
==============================================

Quick commands (copy/paste into Python window):

# Run FULL refresh and comparison:
main(refresh_sa=True, refresh_dch=True, run_compare=True)

# Run COMPARISON ONLY (no data refresh):
main(refresh_sa=False, refresh_dch=False, run_compare=True)

# Refresh SA ONLY:
main(refresh_sa=True, refresh_dch=False, run_compare=False)

# Refresh DCH ONLY:
main(refresh_sa=False, refresh_dch=True, run_compare=False)

# Check current data vintages:
check_data_vintage()

Note: Before SA refresh, update INPUT_FILE in semianalysis_pipeline.py
      Before DCH refresh, import latest CSV to raw tables
""")
