# Full Pipeline Execution Script
# ==============================
#
# Runs the complete Data Center Consensus GIS pipeline from start to finish.
#
# Features:
# - Sequential execution (won't overload ArcGIS Pro)
# - Memory cleanup between steps
# - Progress indicators and timing
# - Optional interactive mode with pauses between steps
# - Error handling with graceful failure
#
# Usage in ArcGIS Pro Python window:
#     exec(open(r"...\scripts\run_full_pipeline.py", encoding='utf-8').read())
#
# Or with interactive mode (pauses between steps):
#     INTERACTIVE = True
#     exec(open(r"...\scripts\run_full_pipeline.py", encoding='utf-8').read())
#
# Author: Meta Data Center GIS Team
# Created: January 2, 2026

import os
import sys
import gc
import time
from datetime import datetime

# =============================================================================
# CONFIGURATION
# =============================================================================

# Set to True to pause between each step (allows you to check results)
# Set to False for fully automated execution
try:
    INTERACTIVE
except NameError:
    INTERACTIVE = False  # Default: run without pauses

# Set to True to generate HTML diagnostic report at end of pipeline
try:
    GENERATE_REPORT
except NameError:
    GENERATE_REPORT = True  # Default: generate report

# Base path for scripts
SCRIPTS_DIR = r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\scripts"

# Define pipeline steps in order
PIPELINE_STEPS = [
    # Step 1: Ingestion (6 sources)
    {
        "name": "1a. Ingest DCH Hyper",
        "script": r"01_ingestion\ingest_dch.py",
        "description": "DataCenterHawk hyperscale buildings (~1,876 records)",
    },
    {
        "name": "1b. Ingest DCH Lease",
        "script": r"01_ingestion\ingest_dch_lease.py",
        "description": "DataCenterHawk leased facilities (~5,176 records)",
    },
    {
        "name": "1c. Ingest Semianalysis",
        "script": r"01_ingestion\ingest_semianalysis.py",
        "description": "Semianalysis buildings with 10-year forecasts (~5,472 records)",
    },
    {
        "name": "1d. Ingest DCM",
        "script": r"01_ingestion\ingest_dcm.py",
        "description": "DataCenterMap buildings (~8,453 records)",
    },
    {
        "name": "1e. Ingest NPM",
        "script": r"01_ingestion\ingest_npm.py",
        "description": "NewProjectMedia US announcements (~1,399 records)",
    },
    {
        "name": "1f. Ingest Meta Canonical",
        "script": r"01_ingestion\ingest_meta_canonical.py",
        "description": "Meta internal ground truth (~318 records)",
    },
    # Step 2: Geography Enrichment
    {
        "name": "2. Geography Enrichment",
        "script": r"02_processing\enrich_geography_fields.py",
        "description": "Enrich region, state, state_abbr from existing data + lookups",
    },
    # Step 3: Company Standardization
    {
        "name": "3. Company Standardization",
        "script": r"02_processing\migrate_company_fields_v2.py",
        "description": "Standardize company names for UCID clustering",
    },
    # Step 4: UCID Generation
    {
        "name": "4. UCID Generation",
        "script": r"03_ucid\generate_text_ucid.py",
        "description": "Assign Universal Campus IDs to buildings",
    },
    # Step 5: Essential DC Flag
    {
        "name": "5. Essential DC Flag",
        "script": r"02_processing\integrate_essential_by_uid.py",
        "description": "Flag 127 Essential DC buildings from curated strategic sites list",
    },
    # Step 6: Campus Rollup
    {
        "name": "6. Campus Rollup",
        "script": r"02_processing\campus_rollup_new.py",
        "description": "Aggregate buildings into campuses (grouped by UCID), rolls up is_essential",
    },
    # Step 7: Cleanup Gold Campus
    {
        "name": "7. Cleanup Gold Campus",
        "script": r"02_processing\cleanup_gold_campus.py",
        "description": "Populate lat/lon from geometry, verify fields",
    },
    # Step 8: Create XB Combined Layer
    {
        "name": "8. Create XB Combined Layer",
        "script": r"02_processing\create_xb_combined_layer.py",
        "description": "Combine buildings + campuses for Experience Builder",
    },
]


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def print_banner(text, char="="):
    """Print a banner for visual separation."""
    width = 80
    print("\n" + char * width)
    print(f"  {text}")
    print(char * width)


def print_step_header(step_num, total_steps, step_info):
    """Print step header with progress info."""
    print("\n" + "=" * 80)
    print(f"  STEP {step_num}/{total_steps}: {step_info['name']}")
    print(f"  {step_info['description']}")
    print("=" * 80)


def format_duration(seconds):
    """Format duration in human-readable format."""
    if seconds < 60:
        return f"{seconds:.1f} seconds"
    elif seconds < 3600:
        minutes = seconds / 60
        return f"{minutes:.1f} minutes"
    else:
        hours = seconds / 3600
        return f"{hours:.1f} hours"


def run_script(script_path):
    """
    Run a Python script using exec().
    Returns True on success, False on failure.
    """
    full_path = os.path.join(SCRIPTS_DIR, script_path)

    if not os.path.exists(full_path):
        print(f"\n❌ ERROR: Script not found: {full_path}")
        return False

    try:
        print(f"\n   Running: {script_path}")
        print("-" * 60)

        with open(full_path, encoding='utf-8') as f:
            script_content = f.read()

        # Execute the script
        exec(script_content, globals())

        return True

    except Exception as e:
        print(f"\n❌ ERROR running {script_path}:")
        print(f"   {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def cleanup_memory():
    """Force garbage collection to free memory."""
    collected = gc.collect()
    print(f"   🧹 Memory cleanup: {collected} objects collected")


def wait_for_user():
    """
    Wait for user input (interactive mode only).

    NOTE: ArcGIS Pro's Python window doesn't support input(), so we just
    print a message and add a small delay instead. For true interactive
    mode, run the script from a standalone Python console.
    """
    if INTERACTIVE:
        print("\n" + "-" * 40)
        print("   [INTERACTIVE MODE] Pausing for 3 seconds...")
        print("   (For full interactive control, run from standalone Python)")
        print("-" * 40)
        time.sleep(3)  # Brief pause instead of waiting for input


def get_record_counts():
    """Get current record counts from gold tables."""
    try:
        import arcpy

        # Add utils to path
        utils_dir = os.path.join(SCRIPTS_DIR, "_utils")
        if utils_dir not in sys.path:
            sys.path.insert(0, utils_dir)

        from config import GOLD_BUILDINGS, GOLD_CAMPUS, GDB

        counts = {}

        for name, path in [("gold_buildings_full", GOLD_BUILDINGS),
                           ("gold_campus_full", GOLD_CAMPUS)]:
            if arcpy.Exists(path):
                counts[name] = int(arcpy.GetCount_management(path)[0])
            else:
                counts[name] = 0

        # Check for XB combined
        xb_path = os.path.join(GDB, "gold_combined_xb")
        if arcpy.Exists(xb_path):
            counts["gold_combined_xb"] = int(arcpy.GetCount_management(xb_path)[0])
        else:
            counts["gold_combined_xb"] = 0

        return counts

    except Exception as e:
        print(f"   ⚠️ Could not get record counts: {e}")
        return {}


# =============================================================================
# MAIN PIPELINE EXECUTION
# =============================================================================

def run_pipeline():
    """Run the complete pipeline."""

    pipeline_start = time.time()

    print_banner("DATA CENTER CONSENSUS GIS PIPELINE", "█")
    print(f"\n   Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"   Mode: {'INTERACTIVE (pauses between steps)' if INTERACTIVE else 'AUTOMATED (no pauses)'}")
    print(f"   Total Steps: {len(PIPELINE_STEPS)}")

    # Get initial record counts
    print("\n   📊 Initial Record Counts:")
    initial_counts = get_record_counts()
    for name, count in initial_counts.items():
        print(f"      {name}: {count:,}")

    # Track results
    results = []
    failed_step = None

    # Execute each step
    for i, step in enumerate(PIPELINE_STEPS, 1):
        step_start = time.time()

        print_step_header(i, len(PIPELINE_STEPS), step)

        # Run the script
        success = run_script(step["script"])

        step_duration = time.time() - step_start

        results.append({
            "name": step["name"],
            "success": success,
            "duration": step_duration
        })

        if success:
            print(f"\n   ✅ {step['name']} completed in {format_duration(step_duration)}")
        else:
            print(f"\n   ❌ {step['name']} FAILED after {format_duration(step_duration)}")
            failed_step = step["name"]

            # In ArcGIS Pro, we can't use input(), so we just stop on error
            print("\n   Pipeline stopped due to error.")
            print("   Fix the issue and re-run the pipeline.")
            break

        # Memory cleanup between steps
        cleanup_memory()

        # Wait for user in interactive mode
        if i < len(PIPELINE_STEPS):  # Don't wait after last step
            wait_for_user()

    # Pipeline complete
    pipeline_duration = time.time() - pipeline_start

    print_banner("PIPELINE EXECUTION COMPLETE", "█")

    # Summary
    successful = sum(1 for r in results if r["success"])
    failed = len(results) - successful

    print(f"\n   📊 SUMMARY")
    print(f"   " + "-" * 40)
    print(f"   Total Steps: {len(results)}/{len(PIPELINE_STEPS)}")
    print(f"   Successful:  {successful}")
    print(f"   Failed:      {failed}")
    print(f"   Total Time:  {format_duration(pipeline_duration)}")

    # Step timing breakdown
    print(f"\n   ⏱️ STEP TIMING")
    print(f"   " + "-" * 40)
    for r in results:
        status = "✅" if r["success"] else "❌"
        print(f"   {status} {r['name']}: {format_duration(r['duration'])}")

    # Final record counts
    print(f"\n   📊 FINAL RECORD COUNTS")
    print(f"   " + "-" * 40)
    final_counts = get_record_counts()
    for name, count in final_counts.items():
        initial = initial_counts.get(name, 0)
        diff = count - initial
        diff_str = f"(+{diff:,})" if diff > 0 else f"({diff:,})" if diff < 0 else "(no change)"
        print(f"   {name}: {count:,} {diff_str}")

    print(f"\n   Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    if failed > 0:
        print(f"\n   ⚠️ Pipeline completed with errors. Check output above.")
    else:
        print(f"\n   🎉 Pipeline completed successfully!")

        # Generate diagnostic report if enabled
        if GENERATE_REPORT:
            print("\n   📊 Generating diagnostic report...")
            try:
                report_script = os.path.join(SCRIPTS_DIR, "04_validation", "reports", "generate_pipeline_report.py")
                if os.path.exists(report_script):
                    with open(report_script, encoding='utf-8') as f:
                        exec(f.read(), globals())
                    print("   ✅ Diagnostic report generated successfully!")
                else:
                    print(f"   ⚠️ Report script not found: {report_script}")
            except Exception as e:
                print(f"   ⚠️ Could not generate report: {e}")

    print("█" * 80 + "\n")

    return failed == 0


# =============================================================================
# EXECUTE
# =============================================================================

if __name__ == "__main__":
    run_pipeline()
else:
    # Running via exec() in ArcGIS Pro
    run_pipeline()
