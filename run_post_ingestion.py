# Post-Ingestion Pipeline Script
# ===============================
#
# Runs the pipeline from AFTER ingestion (processing → output → dashboard).
# Use this when you've already ingested new data and just need to rebuild
# the downstream tables and republish.
#
# Usage in ArcGIS Pro Python window:
#     exec(open(r"...\scripts\run_post_ingestion.py", encoding='utf-8').read())
#
# Author: Meta Data Center GIS Team
# Created: January 14, 2026
# Updated: February 2, 2026 - Added Geography Enrichment as Step 1

import os
import sys
import gc
import time
from datetime import datetime

# =============================================================================
# CONFIGURATION
# =============================================================================

SCRIPTS_DIR = r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\scripts"
WEB_DASHBOARD_DIR = r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\web_dashboard"

# Post-ingestion steps only (skips ingestion scripts)
PIPELINE_STEPS = [
    {
        "name": "1. Geography Enrichment",
        "script": r"02_processing\enrich_geography_fields.py",
        "description": "Enrich region, state, state_abbr from existing data + lookups",
    },
    {
        "name": "2. Company Standardization",
        "script": r"02_processing\migrate_company_fields_v2.py",
        "description": "Standardize company names (company_clean, company_clean_filter)",
    },
    {
        "name": "3. Essential DC Flag",
        "script": r"02_processing\integrate_essential_by_uid.py",
        "description": "Flag 127 Essential DC buildings from curated list",
    },
    {
        "name": "4. UCID Generation",
        "script": r"03_ucid\generate_text_ucid.py",
        "description": "Assign Universal Campus IDs to buildings",
    },
    {
        "name": "5. Campus Rollup",
        "script": r"02_processing\campus_rollup_new.py",
        "description": "Aggregate buildings into campuses (grouped by UCID)",
    },
    {
        "name": "6. Cleanup Gold Campus",
        "script": r"02_processing\cleanup_gold_campus.py",
        "description": "Populate lat/lon from geometry",
    },
    {
        "name": "7. Create XB Combined Layer",
        "script": r"06_visualization\create_xb_combined_layer.py",
        "description": "Combine buildings + campuses for dashboard",
    },
    {
        "name": "8. Export GeoJSON",
        "script": r"..\web_dashboard\08_web_export\export_to_geojson.py",
        "description": "Export to GeoJSON for web dashboard",
    },
]


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def print_banner(text, char="="):
    width = 80
    print("\n" + char * width)
    print(f"  {text}")
    print(char * width)


def format_duration(seconds):
    if seconds < 60:
        return f"{seconds:.1f}s"
    else:
        return f"{seconds / 60:.1f}m"


def run_script(script_path):
    """Run a Python script using exec()."""
    # Handle relative paths for web_dashboard
    if script_path.startswith(".."):
        full_path = os.path.normpath(os.path.join(SCRIPTS_DIR, script_path))
    else:
        full_path = os.path.join(SCRIPTS_DIR, script_path)

    if not os.path.exists(full_path):
        print(f"   [X] Script not found: {full_path}")
        return False

    try:
        print(f"   -> {os.path.basename(full_path)}")
        with open(full_path, encoding='utf-8') as f:
            exec(f.read(), globals())
        return True
    except Exception as e:
        print(f"   [X] ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def get_record_counts():
    """Get current record counts from gold tables."""
    try:
        import arcpy
        utils_dir = os.path.join(SCRIPTS_DIR, "_utils")
        if utils_dir not in sys.path:
            sys.path.insert(0, utils_dir)
        from config import GOLD_BUILDINGS, GOLD_CAMPUS, GDB

        counts = {}
        for name, path in [("Buildings", GOLD_BUILDINGS), ("Campus", GOLD_CAMPUS)]:
            if arcpy.Exists(path):
                counts[name] = int(arcpy.GetCount_management(path)[0])
        xb_path = os.path.join(GDB, "gold_combined_xb")
        if arcpy.Exists(xb_path):
            counts["XB Combined"] = int(arcpy.GetCount_management(xb_path)[0])
        return counts
    except:
        return {}


# =============================================================================
# MAIN EXECUTION
# =============================================================================

def run_post_ingestion_pipeline():
    """Run the post-ingestion pipeline."""

    start_time = time.time()

    print_banner("POST-INGESTION PIPELINE", "=")
    print(f"   Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"   Steps: {len(PIPELINE_STEPS)} (skipping ingestion)")

    # Initial counts
    print("\n   [i] Initial Counts:")
    for name, count in get_record_counts().items():
        print(f"      {name}: {count:,}")

    # Execute steps
    results = []
    for i, step in enumerate(PIPELINE_STEPS, 1):
        step_start = time.time()
        print(f"\n{'-' * 60}")
        print(f"   [{i}/{len(PIPELINE_STEPS)}] {step['name']}")
        print(f"   {step['description']}")
        print(f"{'-' * 60}")

        success = run_script(step["script"])
        duration = time.time() - step_start
        results.append({"name": step["name"], "success": success, "duration": duration})

        if success:
            print(f"   [OK] Done ({format_duration(duration)})")
        else:
            print(f"   [X] FAILED - stopping pipeline")
            break

        gc.collect()

    # Summary
    total_time = time.time() - start_time
    successful = sum(1 for r in results if r["success"])

    print_banner("PIPELINE COMPLETE", "=")
    print(f"   Steps: {successful}/{len(PIPELINE_STEPS)} successful")
    print(f"   Time: {format_duration(total_time)}")

    # Final counts
    print("\n   [i] Final Counts:")
    for name, count in get_record_counts().items():
        print(f"      {name}: {count:,}")

    if successful == len(PIPELINE_STEPS):
        print("\n   [OK] SUCCESS! All steps completed.")
        print("\n   [>] NEXT: Reload dashboard cache:")
        print("      -> http://localhost:8000/api/reload")
        print("      Or restart: .\\start_dashboard.ps1")
    else:
        print(f"\n   [!] Pipeline stopped with errors. Fix and re-run.")

    print("=" * 80 + "\n")
    return successful == len(PIPELINE_STEPS)


# Execute
run_post_ingestion_pipeline()
