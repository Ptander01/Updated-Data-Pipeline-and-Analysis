"""
ACRES Data Ingestion Script
============================

Pulls ACRES datacenter parcel data from multiple sources:
1. CSV files (exported from Bento/HIVE) - RECOMMENDED
2. Map layers (if already added to ArcGIS Pro)
3. ArcGIS Enterprise Portal service (direct)

Data Source (Portal): https://esri-prod.thefacebook.com/Portal/apps/mapviewer/index.html?layers=f6470b4720324422ba122a67db30c1a5
Data Source (HIVE): idc_lsim_datacenter_index_* tables

USAGE (in ArcGIS Pro Python window):

    # From map layers (if ACRES layers added to map) - DEFAULT:
    exec(open(r"C:/Users/ptanderson/Documents/ArcGIS/Projects/Lean Consensus DC Model/scripts/08_acres/ingest_acres.py", encoding='utf-8').read())

    # From CSV files (exported from Bento):
    main(use_csv=True)

    # Direct portal access:
    main(use_map_layers=False)

Author: Meta Data Center GIS Team
Created: 2026-01-29
Updated: 2026-02-02 (added CSV import support, improved layer matching)
"""

import arcpy
import os
import sys
from datetime import datetime

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

# ArcGIS Enterprise Portal service URL (Item ID from the webmap URL)
ITEM_ID = "f6470b4720324422ba122a67db30c1a5"
PORTAL_URL = "https://esri-prod.thefacebook.com/Portal"

# CSV directory for Bento exports
CSV_DIR = os.path.join(script_dir, "data", "acres_exports")

# Feature service layers (index positions within the hosted service)
# Portal layer names follow pattern: idc_acres_datacenter_index_{layer_type}_FC
LAYER_CONFIG = {
    'parcel_changes_centroid': {
        'index': 0,
        'output_fc': 'acres_parcel_changes_centroid',
        'csv_file': 'acres_parcel_changes_centroid.csv',
        'geometry_type': 'POINT',
        'portal_pattern': 'parcel_changes_centroid',
        'description': 'Parcel changes centroid points'
    },
    'parcels_centroid': {
        'index': 1,
        'output_fc': 'acres_parcels_centroid',
        'csv_file': 'acres_parcels_centroid.csv',
        'geometry_type': 'POINT',
        'portal_pattern': 'parcels_centroid',
        'description': 'Parcels centroid points'
    },
    'transactions_centroid': {
        'index': 2,
        'output_fc': 'acres_transactions_centroid',
        'csv_file': 'acres_transactions_centroid.csv',
        'geometry_type': 'POINT',
        'portal_pattern': 'transactions_centroid',
        'description': 'Transactions centroid points'
    },
    'parcel_changes_polygon': {
        'index': 3,
        'output_fc': 'acres_parcel_changes_polygon',
        'csv_file': 'acres_parcel_changes_polygon.csv',
        'geometry_type': 'POLYGON',
        'portal_pattern': 'parcel_changes_polygon',
        'description': 'Parcel changes polygons'
    },
    'parcels_polygon': {
        'index': 4,
        'output_fc': 'acres_parcels_polygon',
        'csv_file': 'acres_parcels_polygon.csv',
        'geometry_type': 'POLYGON',
        'portal_pattern': 'parcels_polygon',
        'description': 'Parcels polygons (boundaries)'
    },
    'transactions_polygon': {
        'index': 5,
        'output_fc': 'acres_transactions_polygon',
        'csv_file': 'acres_transactions_polygon.csv',
        'geometry_type': 'POLYGON',
        'portal_pattern': 'transactions_polygon',
        'description': 'Transactions polygons'
    }
}

# Key layers for analysis (subset to speed up ingestion)
PRIMARY_LAYERS = ['parcel_changes_polygon', 'parcels_polygon', 'transactions_polygon']

# Centroid layers (faster to load, smaller file size)
CENTROID_LAYERS = ['parcel_changes_centroid', 'parcels_centroid', 'transactions_centroid']


def get_service_url():
    """Construct the feature service URL from the item ID."""
    return f"{PORTAL_URL}/sharing/rest/content/items/{ITEM_ID}/data"


def ingest_layer_from_csv(layer_name, layer_config, csv_dir=CSV_DIR):
    """
    Ingest a layer from CSV files exported from Bento/HIVE.

    Expected CSV format:
    - Must have 'latitude' and 'longitude' columns for point data
    - OR 'geometry_wkt' column for polygon data (WKT format)
    - All other columns will be imported as attribute fields
    """
    print(f"\n{'='*60}")
    print(f"Ingesting from CSV: {layer_name}")
    print(f"{'='*60}")

    csv_file = os.path.join(csv_dir, layer_config['csv_file'])
    output_fc = os.path.join(GDB, layer_config['output_fc'])
    geom_type = layer_config.get('geometry_type', 'POINT')

    if not os.path.exists(csv_file):
        print(f"  ERROR: CSV file not found: {csv_file}")
        print(f"  Export from Bento notebook using:")
        print(f"    df.to_csv('{layer_config['csv_file']}', index=False)")
        return 0

    print(f"  Source: {csv_file}")
    print(f"  Output: {output_fc}")
    print(f"  Geometry: {geom_type}")

    # Delete existing
    if arcpy.Exists(output_fc):
        print(f"  Deleting existing feature class...")
        arcpy.management.Delete(output_fc)

    try:
        # Check if we have geometry columns
        import csv
        with open(csv_file, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            headers = reader.fieldnames
            sample_row = next(reader, None)

        has_lat_lon = 'latitude' in headers and 'longitude' in headers
        has_wkt = 'geometry_wkt' in headers or 'wkt' in headers or 'geom' in headers

        if has_lat_lon and geom_type == 'POINT':
            # Point data with lat/lon columns
            print(f"  Creating XY event layer...")

            # Make XY Event Layer
            temp_layer = "temp_acres_layer"
            arcpy.management.MakeXYEventLayer(
                csv_file,
                "longitude",
                "latitude",
                temp_layer,
                arcpy.SpatialReference(4326)
            )

            # Export to feature class
            arcpy.management.CopyFeatures(temp_layer, output_fc)

            # Cleanup
            arcpy.management.Delete(temp_layer)

        elif has_wkt:
            # Polygon/geometry data with WKT column
            wkt_field = 'geometry_wkt' if 'geometry_wkt' in headers else ('wkt' if 'wkt' in headers else 'geom')
            print(f"  Converting WKT geometry from '{wkt_field}' column...")

            # Create empty feature class
            spatial_ref = arcpy.SpatialReference(4326)
            arcpy.management.CreateFeatureclass(
                GDB,
                os.path.basename(output_fc),
                geom_type,
                spatial_reference=spatial_ref
            )

            # Add fields from CSV (excluding geometry)
            for header in headers:
                if header.lower() not in [wkt_field.lower(), 'objectid', 'fid', 'shape']:
                    # Determine field type (default to TEXT)
                    if sample_row:
                        val = sample_row.get(header, '')
                        if val and val.replace('.', '').replace('-', '').isdigit():
                            if '.' in val:
                                field_type = 'DOUBLE'
                            else:
                                field_type = 'LONG'
                        else:
                            field_type = 'TEXT'
                    else:
                        field_type = 'TEXT'

                    try:
                        if field_type == 'TEXT':
                            arcpy.management.AddField(output_fc, header[:31], field_type, field_length=500)
                        else:
                            arcpy.management.AddField(output_fc, header[:31], field_type)
                    except:
                        pass  # Skip if field exists or invalid name

            # Insert rows
            insert_fields = ['SHAPE@WKT'] + [h[:31] for h in headers if h.lower() not in [wkt_field.lower(), 'objectid', 'fid', 'shape']]

            with open(csv_file, 'r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                with arcpy.da.InsertCursor(output_fc, insert_fields) as cursor:
                    for row in reader:
                        wkt = row.get(wkt_field, '')
                        if wkt:
                            values = [wkt] + [row.get(h, '') for h in headers if h.lower() not in [wkt_field.lower(), 'objectid', 'fid', 'shape']]
                            try:
                                cursor.insertRow(values)
                            except:
                                pass  # Skip invalid geometries
        else:
            print(f"  ERROR: CSV must have 'latitude'/'longitude' columns or 'geometry_wkt' column")
            return 0

        # Get record count
        count = int(arcpy.management.GetCount(output_fc)[0])
        print(f"  SUCCESS: Imported {count:,} features")

        # List fields
        fields = [f.name for f in arcpy.ListFields(output_fc)
                  if f.name not in ['OBJECTID', 'Shape', 'Shape_Length', 'Shape_Area', 'SHAPE']]
        print(f"  Fields: {', '.join(fields[:8])}{'...' if len(fields) > 8 else ''}")

        return count

    except Exception as e:
        print(f"  ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return 0


def ingest_layer_from_portal(layer_name, layer_config, portal_url=PORTAL_URL):
    """
    Ingest a single layer from the ArcGIS Enterprise Portal.
    """
    print(f"\n{'='*60}")
    print(f"Ingesting: {layer_name}")
    print(f"{'='*60}")

    layer_index = layer_config['index']
    output_fc = os.path.join(GDB, layer_config['output_fc'])

    service_url = f"{portal_url}/sharing/rest/content/items/{ITEM_ID}/FeatureServer/{layer_index}"

    print(f"  Source: {service_url}")
    print(f"  Output: {output_fc}")

    if arcpy.Exists(output_fc):
        print(f"  Deleting existing feature class...")
        arcpy.management.Delete(output_fc)

    try:
        print(f"  Copying features from service...")
        arcpy.management.CopyFeatures(service_url, output_fc)

        count = int(arcpy.management.GetCount(output_fc)[0])
        print(f"  SUCCESS: Copied {count:,} features")

        fields = [f.name for f in arcpy.ListFields(output_fc)
                  if f.name not in ['OBJECTID', 'Shape', 'Shape_Length', 'Shape_Area', 'SHAPE']]
        print(f"  Fields: {', '.join(fields[:10])}{'...' if len(fields) > 10 else ''}")

        return count

    except Exception as e:
        print(f"  ERROR: {str(e)}")

        try:
            print(f"  Retrying with FeatureSet...")
            fs = arcpy.FeatureSet()
            fs.load(service_url)
            arcpy.management.CopyFeatures(fs, output_fc)

            count = int(arcpy.management.GetCount(output_fc)[0])
            print(f"  SUCCESS (FeatureSet): Copied {count:,} features")
            return count

        except Exception as e2:
            print(f"  ERROR (FeatureSet): {str(e2)}")
            return 0


def ingest_layer_from_map(layer_name, layer_config):
    """
    Ingest from an existing map layer in the current ArcGIS Pro project.

    Handles Portal layer names like:
    - idc_acres_datacenter_index_parcel_changes_polygon_FC
    - idc_acres_datacenter_index_parcels_polygon_FC
    - idc_acres_datacenter_index_transactions_polygon_FC

    IMPORTANT: Prefers Portal source layers (containing 'idc_acres_datacenter_index')
    over local geodatabase output layers to avoid copying from our own output.
    """
    print(f"\n{'='*60}")
    print(f"Ingesting from map: {layer_name}")
    print(f"{'='*60}")

    output_fc = os.path.join(GDB, layer_config['output_fc'])
    output_fc_name = layer_config['output_fc'].lower()

    aprx = arcpy.mp.ArcGISProject("CURRENT")
    active_map = aprx.activeMap

    if not active_map:
        print("  ERROR: No active map found. Please open a map with the ACRES layers.")
        return 0

    target_layer = None

    # Build search patterns from layer_name
    search_pattern = layer_config.get('portal_pattern', layer_name)
    pattern_normalized = search_pattern.replace('_', '').lower()

    print(f"  Looking for pattern: '{search_pattern}' (normalized: '{pattern_normalized}')")

    # Collect matching Portal source layers (prefer idc_acres_datacenter_index)
    portal_layers = []
    other_layers = []

    for lyr in active_map.listLayers():
        lyr_name_lower = lyr.name.lower()

        # Skip group layers
        if lyr.isGroupLayer:
            continue

        # Skip our own output layers (start with 'acres_' but NOT 'idc_acres_')
        if lyr_name_lower.startswith('acres_') and not lyr_name_lower.startswith('idc_acres_'):
            print(f"  Skipping local output layer: '{lyr.name}'")
            continue

        # Check if this is a Portal ACRES layer
        if 'idc_acres_datacenter_index' in lyr_name_lower:
            lyr_normalized = lyr_name_lower.replace('_', '').replace(' ', '').replace('fc', '')
            if pattern_normalized in lyr_normalized:
                portal_layers.append(lyr)
                print(f"  Found Portal source: '{lyr.name}'")
        elif 'datacenter_index' in lyr_name_lower or 'datacenter index' in lyr_name_lower:
            lyr_normalized = lyr_name_lower.replace('_', '').replace(' ', '').replace('fc', '')
            if pattern_normalized in lyr_normalized:
                other_layers.append(lyr)
                print(f"  Found other source: '{lyr.name}'")

    # Prefer Portal layers, fall back to other layers
    if portal_layers:
        target_layer = portal_layers[0]
    elif other_layers:
        target_layer = other_layers[0]

    if not target_layer:
        print(f"  ERROR: Layer not found in map.")
        print(f"  Looking for pattern: {pattern_normalized}")

        # List all ACRES-related layers for debugging
        acres_layers = []
        for lyr in active_map.listLayers():
            if not lyr.isGroupLayer:
                if 'acres' in lyr.name.lower() or 'datacenter' in lyr.name.lower():
                    acres_layers.append(lyr.name)

        if acres_layers:
            print(f"  Available ACRES layers:")
            for name in acres_layers:
                print(f"    - {name}")
        else:
            print(f"  No ACRES layers found in map. Add them from the Portal first.")
        return 0

    print(f"  Selected source layer: {target_layer.name}")

    if arcpy.Exists(output_fc):
        print(f"  Deleting existing feature class...")
        arcpy.management.Delete(output_fc)

    try:
        print(f"  Copying features...")
        arcpy.management.CopyFeatures(target_layer, output_fc)

        count = int(arcpy.management.GetCount(output_fc)[0])
        print(f"  SUCCESS: Copied {count:,} features")

        # Show field info
        fields = [f.name for f in arcpy.ListFields(output_fc)
                  if f.name not in ['OBJECTID', 'Shape', 'Shape_Length', 'Shape_Area', 'SHAPE']]
        print(f"  Fields ({len(fields)}): {', '.join(fields[:8])}{'...' if len(fields) > 8 else ''}")

        return count

    except Exception as e:
        print(f"  ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return 0


def list_available_layers():
    """List all layers available in the current map for verification."""
    print("\n" + "=" * 60)
    print("AVAILABLE LAYERS IN CURRENT MAP")
    print("=" * 60)

    try:
        aprx = arcpy.mp.ArcGISProject("CURRENT")
        active_map = aprx.activeMap

        if not active_map:
            print("No active map found.")
            return

        for i, lyr in enumerate(active_map.listLayers()):
            layer_type = "GROUP" if lyr.isGroupLayer else "FEATURE"
            print(f"  [{i}] {lyr.name} ({layer_type})")

    except Exception as e:
        print(f"  Error listing layers: {e}")


def list_available_csvs():
    """List available CSV files for import."""
    print("\n" + "=" * 60)
    print("AVAILABLE CSV FILES")
    print("=" * 60)

    if not os.path.exists(CSV_DIR):
        print(f"  CSV directory not found: {CSV_DIR}")
        print(f"  Create directory and add exported CSVs from Bento")
        return

    csv_files = [f for f in os.listdir(CSV_DIR) if f.endswith('.csv')]

    if not csv_files:
        print(f"  No CSV files found in: {CSV_DIR}")
        print(f"  Export from Bento and place files here")
    else:
        for f in csv_files:
            filepath = os.path.join(CSV_DIR, f)
            size_mb = os.path.getsize(filepath) / (1024 * 1024)
            print(f"  - {f} ({size_mb:.1f} MB)")


def main(use_csv=False, use_map_layers=True, layers=None, use_centroids=False):
    """
    Main ingestion function.

    Args:
        use_csv: If True, import from CSV files (exported from Bento).
        use_map_layers: If True, copy from map layers. If False, try direct service access.
        layers: List of layer keys to ingest. If None, ingests PRIMARY_LAYERS.
        use_centroids: If True, use centroid layers instead of polygons (faster).
    """
    print("=" * 70)
    print("ACRES DATA INGESTION")
    print(f"Started: {datetime.now()}")
    print("=" * 70)

    print(f"\nGeodatabase: {GDB}")

    if use_csv:
        print(f"Ingestion method: CSV files from {CSV_DIR}")
    elif use_map_layers:
        print(f"Ingestion method: Map layers")
    else:
        print(f"Ingestion method: Direct service access")

    # Determine which layers to process
    if layers is None:
        if use_centroids:
            layers = CENTROID_LAYERS
        else:
            layers = PRIMARY_LAYERS

    print(f"\nLayers to ingest: {', '.join(layers)}")

    # List available sources for reference
    if use_csv:
        list_available_csvs()
    elif use_map_layers:
        list_available_layers()

    results = {}

    for layer_name in layers:
        if layer_name not in LAYER_CONFIG:
            print(f"\n  WARNING: Unknown layer '{layer_name}', skipping.")
            continue

        config = LAYER_CONFIG[layer_name]

        if use_csv:
            count = ingest_layer_from_csv(layer_name, config)
        elif use_map_layers:
            count = ingest_layer_from_map(layer_name, config)
        else:
            count = ingest_layer_from_portal(layer_name, config)

        results[layer_name] = count

    # Summary
    print("\n" + "=" * 70)
    print("INGESTION COMPLETE")
    print("=" * 70)

    total = 0
    for layer_name, count in results.items():
        status = "SUCCESS" if count > 0 else "FAILED"
        print(f"  {layer_name}: {count:,} records ({status})")
        total += count

    print(f"\n  Total records ingested: {total:,}")

    print("\n  Output feature classes:")
    for layer_name in layers:
        if layer_name in LAYER_CONFIG:
            fc_name = LAYER_CONFIG[layer_name]['output_fc']
            fc_path = os.path.join(GDB, fc_name)
            if arcpy.Exists(fc_path):
                print(f"    - {fc_name}")

    print("\n  Next steps:")
    print("    1. Run phase1_acres_match.py to match DC sites to land parcels")
    print("    2. Run phase1_timeline_calc.py for land-to-MW timeline analysis")
    print("    3. Or run acres_parcel_rollup.py for campus grouping")

    return results


# ==============================================================================
# EXECUTE
# ==============================================================================

if __name__ == "__main__":
    main(use_map_layers=True)
else:
    # When run via exec() in ArcGIS Pro Python window
    main(use_map_layers=True)
