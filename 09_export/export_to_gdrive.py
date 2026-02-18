# -*- coding: utf-8 -*-
# Export Gold Feature Classes to Shared Google Drive
# Exports gold_buildings_full, gold_campus_full, gold_combined_xb
# Run: exec(open(r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\scripts\05_export\export_to_gdrive.py", encoding='utf-8').read())

import arcpy
import os
import json
import csv
from datetime import datetime
from pathlib import Path

# =============================================================================
# CONFIGURATION
# =============================================================================

GDB = r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\Default.gdb"

FEATURE_CLASSES = {
    "gold_buildings_full": os.path.join(GDB, "gold_buildings_full"),
    "gold_campus_full": os.path.join(GDB, "gold_campus_full"),
    "gold_combined_xb": os.path.join(GDB, "gold_combined_xb"),
}

GDRIVE_OUTPUT_ROOT = Path("G:/My Drive/Consensus GIS Model Cleaned Inputs/Admin Documentation")
GDRIVE_EXPORT_DIR = GDRIVE_OUTPUT_ROOT / "data_exports"
LOCAL_EXPORT_DIR = Path(r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\exports")

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_export_dir():
    try:
        if GDRIVE_OUTPUT_ROOT.parent.exists():
            GDRIVE_EXPORT_DIR.mkdir(parents=True, exist_ok=True)
            print(f"Export directory: {GDRIVE_EXPORT_DIR}")
            return GDRIVE_EXPORT_DIR
        else:
            raise Exception("Google Drive not mounted")
    except Exception as e:
        print(f"Google Drive unavailable ({e}). Using local fallback.")
        LOCAL_EXPORT_DIR.mkdir(parents=True, exist_ok=True)
        print(f"Export directory: {LOCAL_EXPORT_DIR}")
        return LOCAL_EXPORT_DIR


def get_field_info(fc_path):
    exclude_fields = ["OBJECTID", "Shape", "Shape_Length", "Shape_Area", "GlobalID"]
    fields = []
    for f in arcpy.ListFields(fc_path):
        if f.name not in exclude_fields and not f.name.startswith("Shape"):
            fields.append(f.name)
    return fields


def safe_value(val):
    if val is None:
        return ""
    if isinstance(val, (int, float)):
        if val != val:
            return ""
        return val
    if hasattr(val, 'isoformat'):
        return val.strftime("%Y-%m-%d")
    return str(val)


def export_to_csv(fc_path, output_path, fc_name):
    print(f"\nExporting {fc_name} to CSV...")
    if not arcpy.Exists(fc_path):
        print(f"   Feature class not found: {fc_path}")
        return False

    fields = get_field_info(fc_path)
    desc = arcpy.Describe(fc_path)
    include_coords = desc.shapeType == "Point"

    if include_coords:
        search_fields = ["SHAPE@XY"] + fields
        csv_headers = ["longitude", "latitude"] + fields
    else:
        search_fields = fields
        csv_headers = fields

    record_count = int(arcpy.GetCount_management(fc_path)[0])

    with open(output_path, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(csv_headers)
        with arcpy.da.SearchCursor(fc_path, search_fields) as cursor:
            for row in cursor:
                if include_coords:
                    coords = row[0]
                    if coords and coords[0] is not None:
                        csv_row = [round(coords[0], 6), round(coords[1], 6)]
                    else:
                        csv_row = ["", ""]
                    csv_row.extend([safe_value(v) for v in row[1:]])
                else:
                    csv_row = [safe_value(v) for v in row]
                writer.writerow(csv_row)

    file_size = os.path.getsize(output_path) / (1024 * 1024)
    print(f"   Exported {record_count:,} records ({file_size:.1f} MB)")
    return True


def export_to_geojson(fc_path, output_path, fc_name):
    print(f"\nExporting {fc_name} to GeoJSON...")
    if not arcpy.Exists(fc_path):
        print(f"   Feature class not found: {fc_path}")
        return False

    fields = get_field_info(fc_path)
    search_fields = ["SHAPE@XY"] + fields
    features = []
    record_count = int(arcpy.GetCount_management(fc_path)[0])

    with arcpy.da.SearchCursor(fc_path, search_fields) as cursor:
        for row in cursor:
            coords = row[0]
            if coords is None or coords[0] is None:
                continue
            properties = {}
            for i, field in enumerate(fields):
                val = row[i + 1]
                if val is None:
                    properties[field] = None
                elif isinstance(val, float) and val != val:
                    properties[field] = None
                elif hasattr(val, 'isoformat'):
                    properties[field] = val.isoformat()
                else:
                    properties[field] = val
            feature = {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [round(coords[0], 6), round(coords[1], 6)]
                },
                "properties": properties
            }
            features.append(feature)

    geojson = {
        "type": "FeatureCollection",
        "metadata": {
            "source": fc_name,
            "exported": datetime.now().isoformat(),
            "record_count": len(features),
            "crs": "EPSG:4326"
        },
        "features": features
    }

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(geojson, f, indent=2)

    file_size = os.path.getsize(output_path) / (1024 * 1024)
    print(f"   Exported {len(features):,} features ({file_size:.1f} MB)")
    return True


def export_to_fgdb(source_gdb, export_dir, timestamp):
    print(f"\nCreating File Geodatabase export...")
    fgdb_name = f"gold_export_{timestamp}.gdb"
    fgdb_path = os.path.join(export_dir, fgdb_name)

    if arcpy.Exists(fgdb_path):
        arcpy.Delete_management(fgdb_path)

    arcpy.CreateFileGDB_management(str(export_dir), fgdb_name)
    print(f"   Created: {fgdb_name}")

    for fc_name, fc_path in FEATURE_CLASSES.items():
        if arcpy.Exists(fc_path):
            output_fc = os.path.join(fgdb_path, fc_name)
            arcpy.CopyFeatures_management(fc_path, output_fc)
            count = int(arcpy.GetCount_management(output_fc)[0])
            print(f"   {fc_name}: {count:,} records")
        else:
            print(f"   Skipped (not found): {fc_name}")

    return fgdb_path


def create_readme(export_dir, timestamp, record_counts):
    readme_path = export_dir / f"README_{timestamp}.txt"
    content = f"""================================================================================
CONSENSUS DC MODEL - DATA EXPORT
================================================================================

Export Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Export ID: {timestamp}

--------------------------------------------------------------------------------
CONTENTS
--------------------------------------------------------------------------------

1. gold_buildings_full - Individual data center buildings
   Records: {record_counts.get('gold_buildings_full', 0):,}

2. gold_campus_full - Aggregated campus-level data (grouped by UCID)
   Records: {record_counts.get('gold_campus_full', 0):,}

3. gold_combined_xb - Combined buildings + campuses for visualization
   Records: {record_counts.get('gold_combined_xb', 0):,}

--------------------------------------------------------------------------------
FILE FORMATS
--------------------------------------------------------------------------------

  - CSV (.csv)     - For Excel, Google Sheets, data analysis
  - GeoJSON (.geojson) - For web mapping, QGIS, geospatial tools
  - File GDB (.gdb)    - For ArcGIS Pro users

--------------------------------------------------------------------------------
KEY FIELDS
--------------------------------------------------------------------------------

Identifiers:
  - ucid: Universal Campus ID (groups buildings into campuses)
  - building_ucid: Building-level unique identifier

Company:
  - company_clean: Standardized company name
  - company_clean_filter: Hyperscaler or "Colo - All Other"

Location:
  - latitude, longitude: WGS84 coordinates
  - market, state, country, region

Capacity:
  - full_capacity_mw: Total capacity (MW)
  - commissioned_power_mw: Operational capacity

Status:
  - facility_status: Active, Under Construction, Announced, etc.
  - is_essential: Flag for Essential DC list (127 buildings, 79 campuses)

--------------------------------------------------------------------------------
Contact: Data Center GIS Team
================================================================================
"""
    with open(readme_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"\nCreated README: {readme_path.name}")
    return readme_path


# =============================================================================
# MAIN EXECUTION
# =============================================================================

def main():
    print("=" * 70)
    print("GOLD DATA EXPORT TO GOOGLE DRIVE")
    print("=" * 70)
    print(f"\nStarted: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    export_dir = get_export_dir()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    export_subdir = export_dir / f"export_{timestamp}"
    export_subdir.mkdir(parents=True, exist_ok=True)
    print(f"Export folder: {export_subdir}")

    record_counts = {}

    for fc_name, fc_path in FEATURE_CLASSES.items():
        if arcpy.Exists(fc_path):
            record_counts[fc_name] = int(arcpy.GetCount_management(fc_path)[0])
            csv_path = export_subdir / f"{fc_name}.csv"
            export_to_csv(fc_path, str(csv_path), fc_name)
            geojson_path = export_subdir / f"{fc_name}.geojson"
            export_to_geojson(fc_path, str(geojson_path), fc_name)
        else:
            print(f"\nFeature class not found: {fc_name}")

    export_to_fgdb(GDB, export_subdir, timestamp)
    create_readme(export_subdir, timestamp, record_counts)

    print("\n" + "=" * 70)
    print("EXPORT COMPLETE")
    print("=" * 70)
    print(f"\nFiles exported to:\n   {export_subdir}")
    print(f"\nSummary:")
    for fc_name, count in record_counts.items():
        print(f"   - {fc_name}: {count:,} records")
    print("\nFormats: .csv (Excel), .geojson (mapping), .gdb (ArcGIS Pro)")


main()
