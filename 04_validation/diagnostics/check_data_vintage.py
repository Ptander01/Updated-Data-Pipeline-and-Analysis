# Check Data Vintage by Source
# =============================
#
# Queries gold_buildings_full, gold_campus_full, and gold_combined_xb
# to show the latest data_vintage and record counts for each source.
#
# This helps determine if re-running the pipeline would overwrite recent ingestions.
#
# Usage in ArcGIS Pro Python window:
#     exec(open(r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\scripts\04_validation\diagnostics\check_data_vintage.py", encoding='utf-8').read())
#
# Author: Meta Data Center GIS Team
# Created: 2026-02-02

import arcpy
import os
import sys
from datetime import datetime
from collections import defaultdict

# Add utils to path
SCRIPTS_DIR = r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\scripts"
utils_dir = os.path.join(SCRIPTS_DIR, "_utils")
if utils_dir not in sys.path:
    sys.path.insert(0, utils_dir)

from config import GDB, GOLD_BUILDINGS, GOLD_CAMPUS

# Feature classes to check
LAYERS = {
    "gold_buildings_full": GOLD_BUILDINGS,
    "gold_campus_full": GOLD_CAMPUS,
    "gold_combined_xb": os.path.join(GDB, "gold_combined_xb"),
}

def get_field_names(fc_path):
    """Get list of field names in a feature class."""
    if not arcpy.Exists(fc_path):
        return []
    return [f.name for f in arcpy.ListFields(fc_path)]

def check_data_vintage():
    """Check data vintage for each source in gold layers."""

    print("=" * 80)
    print("DATA VINTAGE CHECK - Current State of Gold Layers")
    print(f"Run at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)

    for layer_name, fc_path in LAYERS.items():
        print(f"\n{'=' * 80}")
        print(f"LAYER: {layer_name}")
        print(f"Path: {fc_path}")
        print("=" * 80)

        if not arcpy.Exists(fc_path):
            print("  [!] Layer does not exist")
            continue

        # Get field names
        fields = get_field_names(fc_path)

        # Determine which fields to query
        has_source = "source" in fields
        has_data_vintage = "data_vintage" in fields
        has_ingest_date = "ingest_date" in fields
        has_record_level = "record_level" in fields

        print(f"\n  Available tracking fields:")
        print(f"    - source: {'YES' if has_source else 'NO'}")
        print(f"    - data_vintage: {'YES' if has_data_vintage else 'NO'}")
        print(f"    - ingest_date: {'YES' if has_ingest_date else 'NO'}")
        print(f"    - record_level: {'YES' if has_record_level else 'NO'}")

        # Build query fields
        query_fields = ["OBJECTID"]
        if has_source:
            query_fields.append("source")
        if has_data_vintage:
            query_fields.append("data_vintage")
        if has_ingest_date:
            query_fields.append("ingest_date")
        if has_record_level:
            query_fields.append("record_level")

        # Collect stats by source
        source_stats = defaultdict(lambda: {
            "count": 0,
            "data_vintage_min": None,
            "data_vintage_max": None,
            "ingest_date_min": None,
            "ingest_date_max": None,
            "record_levels": defaultdict(int),
        })

        total_records = 0

        with arcpy.da.SearchCursor(fc_path, query_fields) as cursor:
            for row in cursor:
                total_records += 1

                # Get values
                source = row[query_fields.index("source")] if has_source else "Unknown"
                source = source or "NULL"

                data_vintage = row[query_fields.index("data_vintage")] if has_data_vintage else None
                ingest_date = row[query_fields.index("ingest_date")] if has_ingest_date else None
                record_level = row[query_fields.index("record_level")] if has_record_level else None

                stats = source_stats[source]
                stats["count"] += 1

                # Track data_vintage min/max
                if data_vintage:
                    if stats["data_vintage_min"] is None or data_vintage < stats["data_vintage_min"]:
                        stats["data_vintage_min"] = data_vintage
                    if stats["data_vintage_max"] is None or data_vintage > stats["data_vintage_max"]:
                        stats["data_vintage_max"] = data_vintage

                # Track ingest_date min/max
                if ingest_date:
                    if stats["ingest_date_min"] is None or ingest_date < stats["ingest_date_min"]:
                        stats["ingest_date_min"] = ingest_date
                    if stats["ingest_date_max"] is None or ingest_date > stats["ingest_date_max"]:
                        stats["ingest_date_max"] = ingest_date

                # Track record_level
                if record_level:
                    stats["record_levels"][record_level] += 1

        print(f"\n  Total Records: {total_records:,}")

        # Print stats by source
        print(f"\n  {'Source':<25} {'Count':>10} {'Data Vintage (Latest)':>25} {'Ingest Date (Latest)':>25}")
        print(f"  {'-'*25} {'-'*10} {'-'*25} {'-'*25}")

        for source in sorted(source_stats.keys()):
            stats = source_stats[source]

            # Format dates
            dv_max = stats["data_vintage_max"]
            if dv_max:
                if isinstance(dv_max, datetime):
                    dv_str = dv_max.strftime("%Y-%m-%d")
                else:
                    dv_str = str(dv_max)[:10]
            else:
                dv_str = "NULL"

            id_max = stats["ingest_date_max"]
            if id_max:
                if isinstance(id_max, datetime):
                    id_str = id_max.strftime("%Y-%m-%d %H:%M")
                else:
                    id_str = str(id_max)[:16]
            else:
                id_str = "NULL"

            print(f"  {source:<25} {stats['count']:>10,} {dv_str:>25} {id_str:>25}")

        # Print record_level breakdown if available
        if has_record_level and any(stats["record_levels"] for stats in source_stats.values()):
            print(f"\n  Record Level Breakdown by Source:")
            for source in sorted(source_stats.keys()):
                stats = source_stats[source]
                if stats["record_levels"]:
                    levels = ", ".join([f"{k}: {v:,}" for k, v in sorted(stats["record_levels"].items())])
                    print(f"    {source}: {levels}")

    print("\n" + "=" * 80)
    print("INTERPRETATION:")
    print("=" * 80)
    print("""
  - 'Data Vintage' = When the SOURCE data was published/extracted
  - 'Ingest Date' = When records were loaded into the geodatabase

  If ingest dates are recent (last week), re-running full pipeline will OVERWRITE.

  SAFE PIPELINE OPTIONS:

  1. SKIP INGESTION - Run only processing steps (Steps 2-8):
     Start from Step 2 (geography enrichment) onward.

  2. SELECTIVE INGESTION - Run only specific source ingestion:
     e.g., Only re-ingest DCM and NPM if those are stale.

  3. FULL PIPELINE - Only if you want to refresh ALL sources.
""")
    print("=" * 80)

# Run
if __name__ == "__main__":
    check_data_vintage()
else:
    check_data_vintage()
