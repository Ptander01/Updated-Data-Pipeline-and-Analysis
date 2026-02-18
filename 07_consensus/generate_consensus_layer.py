# -*- coding: utf-8 -*-
"""
generate_consensus_layer.py
Generates the consensus_campus feature class with BAV (Best Available Value) attributes.

This script creates a single pre-computed layer for Experience Builder that:
- Has ONE geometry per UCID (from highest-authority source)
- Uses Best Available Value logic for each attribute
- Includes source_details_json for popup drill-down
- Calculates confidence scores

Architecture: Option A (Pre-computed Single Layer)
See: 00_docs/workflows/CONSENSUS_XB_ARCHITECTURE.md

Run: exec(open(r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\scripts\07_consensus\generate_consensus_layer.py", encoding="utf-8").read())
"""

import arcpy
import os
import json
from datetime import datetime
from collections import defaultdict

# =============================================================================
# CONFIGURATION
# =============================================================================

try:
    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
except NameError:
    SCRIPT_DIR = r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\scripts\07_consensus"

PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
GDB = os.path.join(os.path.dirname(PROJECT_ROOT), "Default.gdb")

# Input/Output paths
GOLD_BUILDINGS = os.path.join(GDB, "gold_buildings_full")
GOLD_CAMPUS = os.path.join(GDB, "gold_campus_full")
CONSENSUS_CAMPUS = os.path.join(GDB, "consensus_campus")

arcpy.env.overwriteOutput = True

# Import authority config
import sys
sys.path.insert(0, SCRIPT_DIR)
try:
    from authority_config import (
        AUTHORITY_RANKING,
        FIELD_AUTHORITY_MATRIX,
        SOURCE_METADATA,
        HYPERSCALER_COMPANIES,
        MAJOR_COLO_COMPANIES,
        COMPANY_TIER_WEIGHTS,
        get_company_tier,
        get_authority_rank,
    )
except ImportError:
    print("WARNING: Could not import authority_config. Using defaults.")
    AUTHORITY_RANKING = {
        "Meta Canonical": 1, "Semianalysis": 2, "DataCenterHawk": 3,
        "DCH Lease": 4, "NPM": 5, "DataCenterMap": 6,
    }

# =============================================================================
# SCHEMA DEFINITION
# =============================================================================

CONSENSUS_SCHEMA = [
    # Identity
    ("ucid", "TEXT", 50),
    ("canonical_name", "TEXT", 100),
    ("company_clean", "TEXT", 50),
    ("company_clean_filter", "TEXT", 50),
    # Location
    ("region", "TEXT", 10),
    ("country", "TEXT", 50),
    ("state_abbr", "TEXT", 10),
    ("city", "TEXT", 50),
    ("latitude", "DOUBLE", None),
    ("longitude", "DOUBLE", None),
    ("geometry_source", "TEXT", 30),
    # Capacity (BAV)
    ("full_capacity_mw", "DOUBLE", None),
    ("full_capacity_source", "TEXT", 30),
    ("commissioned_mw", "DOUBLE", None),
    ("commissioned_source", "TEXT", 30),
    ("uc_mw", "DOUBLE", None),
    ("uc_source", "TEXT", 30),
    ("planned_mw", "DOUBLE", None),
    ("planned_source", "TEXT", 30),
    # Forecasts (Semianalysis only)
    ("mw_2025", "DOUBLE", None),
    ("mw_2026", "DOUBLE", None),
    ("mw_2027", "DOUBLE", None),
    ("mw_2028", "DOUBLE", None),
    ("mw_2029", "DOUBLE", None),
    ("mw_2030", "DOUBLE", None),
    # Status (BAV)
    ("facility_status", "TEXT", 30),
    ("status_source", "TEXT", 30),
    ("building_count", "SHORT", None),
    ("building_count_source", "TEXT", 30),
    # Flags
    ("is_essential", "SHORT", None),
    # Source Tracking
    ("source_count", "SHORT", None),
    ("sources", "TEXT", 200),
    ("data_vintage", "DATE", None),
    # Drill-Down JSON
    ("source_details_json", "TEXT", 4000),
    # Quality
    ("confidence_score", "DOUBLE", None),
    ("consensus_generated", "DATE", None),
]

# Fields to extract from each source record for BAV
BAV_FIELDS = {
    "full_capacity_mw": ["full_capacity_mw"],
    "commissioned_mw": ["commissioned_power_mw"],
    "uc_mw": ["uc_power_mw"],
    "planned_mw": ["planned_power_mw"],
    "facility_status": ["facility_status"],
    "building_count": ["building_count"],
    "mw_2025": ["mw_2025"],
    "mw_2026": ["mw_2026"],
    "mw_2027": ["mw_2027"],
    "mw_2028": ["mw_2028"],
    "mw_2029": ["mw_2029"],
    "mw_2030": ["mw_2030"],
}

# Field priority overrides (which source is best for which field)
FIELD_PRIORITY = {
    "full_capacity_mw": ["Semianalysis", "DataCenterHawk", "DCH Lease", "NPM", "DataCenterMap", "Meta Canonical"],
    "commissioned_mw": ["Meta Canonical", "DataCenterHawk", "Semianalysis", "DCH Lease", "DataCenterMap"],
    "uc_mw": ["Semianalysis", "DataCenterHawk", "NPM", "Meta Canonical"],
    "planned_mw": ["Semianalysis", "NPM", "DataCenterHawk", "Meta Canonical"],
    "facility_status": ["Meta Canonical", "DataCenterHawk", "DCH Lease", "NPM", "Semianalysis", "DataCenterMap"],
    "building_count": ["DataCenterHawk", "Meta Canonical", "Semianalysis", "DataCenterMap"],
    "mw_2025": ["Semianalysis"],
    "mw_2026": ["Semianalysis"],
    "mw_2027": ["Semianalysis"],
    "mw_2028": ["Semianalysis"],
    "mw_2029": ["Semianalysis"],
    "mw_2030": ["Semianalysis"],
}

# Geometry priority (which source provides best coordinates)
GEOMETRY_PRIORITY = ["Meta Canonical", "Semianalysis", "DataCenterHawk", "DataCenterMap", "DCH Lease", "NPM"]

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_bav(records_by_source, field_name, priority_list):
    """
    Get Best Available Value for a field from multiple source records.

    Args:
        records_by_source: dict of {source: record_dict}
        field_name: field to get value for
        priority_list: ordered list of source names by priority

    Returns:
        (value, source_name) or (None, None)
    """
    for source in priority_list:
        if source in records_by_source:
            record = records_by_source[source]
            value = record.get(field_name)
            if value is not None and value != "" and value != 0:
                return value, source
    return None, None


def get_best_geometry(records_by_source, priority_list):
    """
    Get the best geometry from multiple source records.

    Returns:
        (geometry, latitude, longitude, source_name) or (None, None, None, None)
    """
    for source in priority_list:
        if source in records_by_source:
            record = records_by_source[source]
            geom = record.get("SHAPE@")
            lat = record.get("latitude")
            lon = record.get("longitude")
            if geom is not None or (lat and lon):
                return geom, lat, lon, source
    return None, None, None, None


def build_source_details_json(records_by_source):
    """
    Build the source_details_json field for popup drill-down.

    Returns JSON string with per-source values.
    """
    details = {}

    for source, record in records_by_source.items():
        authority_rank = AUTHORITY_RANKING.get(source, 99)

        # Extract relevant values for this source
        values = {}
        for field in ["full_capacity_mw", "commissioned_power_mw", "uc_power_mw",
                      "planned_power_mw", "facility_status", "building_count",
                      "mw_2025", "mw_2026", "mw_2027", "mw_2028", "mw_2029", "mw_2030"]:
            val = record.get(field)
            if val is not None and val != "" and val != 0:
                # Shorten field names for JSON compactness
                short_name = field.replace("_power_mw", "_mw").replace("commissioned", "comm")
                values[short_name] = val

        if values:  # Only include sources with data
            details[source] = {
                "rank": authority_rank,
                "has_data": True,
                "vintage": str(record.get("data_vintage", ""))[:10] if record.get("data_vintage") else None,
                "values": values
            }

    return json.dumps(details, separators=(',', ':'))  # Compact JSON


def calculate_confidence_score(records_by_source, has_meta):
    """
    Calculate confidence score (0-1) based on:
    - Number of sources (20%)
    - Has Meta Canonical (30%)
    - Data freshness (25%)
    - Field coverage (15%)
    - Source agreement (10%)
    """
    score = 0.0

    # Source count (0-1, max at 4+ sources)
    source_count = len(records_by_source)
    source_score = min(source_count / 4.0, 1.0)
    score += source_score * 0.20

    # Has Meta Canonical
    if has_meta:
        score += 0.30

    # Data freshness (assume recent if data_vintage within 180 days)
    # Simplified: just check if any record has recent vintage
    freshness_score = 0.5  # Default moderate
    for record in records_by_source.values():
        vintage = record.get("data_vintage")
        if vintage:
            try:
                if hasattr(vintage, 'year'):
                    days_old = (datetime.now() - datetime(vintage.year, vintage.month, vintage.day)).days
                    if days_old < 90:
                        freshness_score = 1.0
                        break
                    elif days_old < 180:
                        freshness_score = max(freshness_score, 0.7)
            except:
                pass
    score += freshness_score * 0.25

    # Field coverage (check key fields)
    key_fields = ["full_capacity_mw", "commissioned_power_mw", "facility_status", "building_count"]
    fields_present = 0
    for field in key_fields:
        for record in records_by_source.values():
            if record.get(field):
                fields_present += 1
                break
    coverage_score = fields_present / len(key_fields)
    score += coverage_score * 0.15

    # Source agreement (simplified - check if capacity values are within 20%)
    agreement_score = 0.5  # Default moderate
    capacities = []
    for record in records_by_source.values():
        cap = record.get("full_capacity_mw")
        if cap and cap > 0:
            capacities.append(cap)
    if len(capacities) >= 2:
        avg = sum(capacities) / len(capacities)
        max_deviation = max(abs(c - avg) / avg for c in capacities) if avg > 0 else 0
        if max_deviation < 0.1:
            agreement_score = 1.0
        elif max_deviation < 0.2:
            agreement_score = 0.8
        elif max_deviation < 0.5:
            agreement_score = 0.5
        else:
            agreement_score = 0.2
    score += agreement_score * 0.10

    return round(score, 3)


# =============================================================================
# MAIN PROCESSING
# =============================================================================

def load_campus_data():
    """
    Load campus data from gold_campus_full grouped by UCID.
    Returns dict of {ucid: {source: record_dict}}
    """
    print("\n[Step 1] Loading campus data from gold_campus_full...")

    # Get field list
    fields = [f.name for f in arcpy.ListFields(GOLD_CAMPUS)]

    # Core fields we need
    core_fields = [
        "SHAPE@", "ucid", "campus_id", "campus_name", "company_clean", "company_clean_filter",
        "region", "country", "state_abbr", "city", "latitude", "longitude",
        "full_capacity_mw", "commissioned_power_mw", "uc_power_mw", "planned_power_mw",
        "facility_status", "building_count", "source", "sources", "data_vintage",
        "mw_2025", "mw_2026", "mw_2027", "mw_2028", "mw_2029", "mw_2030",
        "is_essential"
    ]

    # Filter to fields that exist
    read_fields = ["SHAPE@"] + [f for f in core_fields if f in fields and f != "SHAPE@"]

    # Load data grouped by UCID
    ucid_data = defaultdict(dict)
    record_count = 0

    with arcpy.da.SearchCursor(GOLD_CAMPUS, read_fields) as cursor:
        for row in cursor:
            record = dict(zip(read_fields, row))
            ucid = record.get("ucid")
            source = record.get("source", "Unknown")

            if ucid:
                # Handle semicolon-separated sources
                if ";" in str(source):
                    # Multi-source campus - use first source as primary
                    primary_source = source.split(";")[0].strip()
                    ucid_data[ucid][primary_source] = record
                else:
                    ucid_data[ucid][source] = record
                record_count += 1

    print(f"  Loaded {record_count} campus records")
    print(f"  Unique UCIDs: {len(ucid_data)}")

    return ucid_data


def create_consensus_feature_class():
    """Create the consensus_campus feature class with schema."""
    print("\n[Step 2] Creating consensus_campus feature class...")

    # Get spatial reference from source
    spatial_ref = arcpy.Describe(GOLD_CAMPUS).spatialReference

    # Delete if exists
    if arcpy.Exists(CONSENSUS_CAMPUS):
        arcpy.management.Delete(CONSENSUS_CAMPUS)

    # Create feature class
    arcpy.management.CreateFeatureclass(
        GDB, "consensus_campus", "POINT", spatial_reference=spatial_ref
    )

    # Add fields
    for field_def in CONSENSUS_SCHEMA:
        field_name, field_type, field_length = field_def
        if field_length:
            arcpy.management.AddField(CONSENSUS_CAMPUS, field_name, field_type, field_length=field_length)
        else:
            arcpy.management.AddField(CONSENSUS_CAMPUS, field_name, field_type)

    print(f"  Created with {len(CONSENSUS_SCHEMA)} fields")
    return CONSENSUS_CAMPUS


def generate_consensus_records(ucid_data):
    """
    Generate consensus records from grouped campus data.
    Returns list of record tuples ready for insertion.
    """
    print("\n[Step 3] Generating consensus records...")

    consensus_records = []
    stats = {
        "total": 0,
        "with_meta": 0,
        "multi_source": 0,
        "essential": 0,
    }

    for ucid, records_by_source in ucid_data.items():
        stats["total"] += 1

        # Check for Meta Canonical
        has_meta = "Meta Canonical" in records_by_source
        if has_meta:
            stats["with_meta"] += 1

        # Multi-source
        if len(records_by_source) >= 2:
            stats["multi_source"] += 1

        # Get best geometry
        geom, lat, lon, geometry_source = get_best_geometry(records_by_source, GEOMETRY_PRIORITY)

        # If no geometry, try to create from lat/lon
        if geom is None and lat and lon:
            try:
                geom = arcpy.PointGeometry(arcpy.Point(lon, lat), arcpy.SpatialReference(4326))
            except:
                pass

        if geom is None:
            # Skip records without geometry
            continue

        # Get BAV for each field
        full_cap, full_cap_src = get_bav(records_by_source, "full_capacity_mw", FIELD_PRIORITY["full_capacity_mw"])
        comm_mw, comm_src = get_bav(records_by_source, "commissioned_power_mw", FIELD_PRIORITY["commissioned_mw"])
        uc_mw, uc_src = get_bav(records_by_source, "uc_power_mw", FIELD_PRIORITY["uc_mw"])
        planned_mw, planned_src = get_bav(records_by_source, "planned_power_mw", FIELD_PRIORITY["planned_mw"])
        status, status_src = get_bav(records_by_source, "facility_status", FIELD_PRIORITY["facility_status"])
        bldg_count, bldg_src = get_bav(records_by_source, "building_count", FIELD_PRIORITY["building_count"])

        # Forecasts (Semianalysis only)
        mw_2025, _ = get_bav(records_by_source, "mw_2025", ["Semianalysis"])
        mw_2026, _ = get_bav(records_by_source, "mw_2026", ["Semianalysis"])
        mw_2027, _ = get_bav(records_by_source, "mw_2027", ["Semianalysis"])
        mw_2028, _ = get_bav(records_by_source, "mw_2028", ["Semianalysis"])
        mw_2029, _ = get_bav(records_by_source, "mw_2029", ["Semianalysis"])
        mw_2030, _ = get_bav(records_by_source, "mw_2030", ["Semianalysis"])

        # Get identity/location from first available source (by priority)
        first_record = None
        for src in GEOMETRY_PRIORITY:
            if src in records_by_source:
                first_record = records_by_source[src]
                break
        if first_record is None:
            first_record = list(records_by_source.values())[0]

        canonical_name = first_record.get("campus_name", "")
        company_clean = first_record.get("company_clean", "")
        company_filter = first_record.get("company_clean_filter", "")
        region = first_record.get("region", "")
        country = first_record.get("country", "")
        state_abbr = first_record.get("state_abbr", "")
        city = first_record.get("city", "")

        # Is essential (MAX across sources)
        is_essential = 0
        for record in records_by_source.values():
            if record.get("is_essential") == 1:
                is_essential = 1
                stats["essential"] += 1
                break

        # Source tracking
        source_count = len(records_by_source)
        sources_list = "; ".join(sorted(records_by_source.keys()))

        # Data vintage (most recent)
        data_vintage = None
        for record in records_by_source.values():
            vintage = record.get("data_vintage")
            if vintage:
                if data_vintage is None or vintage > data_vintage:
                    data_vintage = vintage

        # Build JSON for drill-down
        source_json = build_source_details_json(records_by_source)

        # Calculate confidence score
        confidence = calculate_confidence_score(records_by_source, has_meta)

        # Build record tuple (matches CONSENSUS_SCHEMA order)
        record_tuple = (
            geom,  # SHAPE@
            ucid,
            canonical_name,
            company_clean,
            company_filter,
            region,
            country,
            state_abbr,
            city,
            lat,
            lon,
            geometry_source,
            full_cap,
            full_cap_src,
            comm_mw,
            comm_src,
            uc_mw,
            uc_src,
            planned_mw,
            planned_src,
            mw_2025,
            mw_2026,
            mw_2027,
            mw_2028,
            mw_2029,
            mw_2030,
            status,
            status_src,
            bldg_count,
            bldg_src,
            is_essential,
            source_count,
            sources_list,
            data_vintage,
            source_json,
            confidence,
            datetime.now(),
        )

        consensus_records.append(record_tuple)

    print(f"  Generated {len(consensus_records)} consensus records")
    print(f"  With Meta Canonical: {stats['with_meta']}")
    print(f"  Multi-source (2+): {stats['multi_source']}")
    print(f"  Essential sites: {stats['essential']}")

    return consensus_records


def insert_consensus_records(records):
    """Insert consensus records into feature class."""
    print("\n[Step 4] Inserting records into consensus_campus...")

    # Build field list from schema
    insert_fields = ["SHAPE@"] + [f[0] for f in CONSENSUS_SCHEMA]

    insert_count = 0
    with arcpy.da.InsertCursor(CONSENSUS_CAMPUS, insert_fields) as cursor:
        for record in records:
            try:
                cursor.insertRow(record)
                insert_count += 1
            except Exception as e:
                print(f"  ERROR inserting record: {e}")
                if insert_count < 5:
                    print(f"    Record: {record[:5]}...")  # Print first few fields

    print(f"  Inserted {insert_count} records")
    return insert_count


def validate_output():
    """Validate the consensus_campus output."""
    print("\n[Step 5] Validating output...")

    count = int(arcpy.management.GetCount(CONSENSUS_CAMPUS)[0])
    print(f"  Total records: {count}")

    # Check for duplicates by UCID
    ucid_counts = defaultdict(int)
    with arcpy.da.SearchCursor(CONSENSUS_CAMPUS, ["ucid"]) as cursor:
        for row in cursor:
            ucid_counts[row[0]] += 1

    duplicates = [(u, c) for u, c in ucid_counts.items() if c > 1]
    if duplicates:
        print(f"  WARNING: {len(duplicates)} duplicate UCIDs found!")
        for ucid, cnt in duplicates[:5]:
            print(f"    {ucid}: {cnt} records")
    else:
        print("  ✓ No duplicate UCIDs")

    # Check JSON field lengths
    max_json_len = 0
    with arcpy.da.SearchCursor(CONSENSUS_CAMPUS, ["source_details_json"]) as cursor:
        for row in cursor:
            if row[0]:
                max_json_len = max(max_json_len, len(row[0]))

    print(f"  Max JSON length: {max_json_len} chars (limit: 4000)")
    if max_json_len > 3500:
        print("  ⚠️ WARNING: JSON approaching field limit!")
    else:
        print("  ✓ JSON field size OK")

    # Sample some records
    print("\n  Sample records:")
    with arcpy.da.SearchCursor(
        CONSENSUS_CAMPUS,
        ["ucid", "company_clean", "full_capacity_mw", "source_count", "confidence_score"],
        where_clause="is_essential = 1"
    ) as cursor:
        for i, row in enumerate(cursor):
            if i >= 5:
                break
            print(f"    {row[0]}: {row[1]}, {row[2]} MW, {row[3]} sources, conf={row[4]}")

    return count


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

def main():
    """Main execution function."""
    print("="*70)
    print("CONSENSUS LAYER GENERATION")
    print("="*70)
    print(f"Started: {datetime.now()}")
    print(f"Input: {GOLD_CAMPUS}")
    print(f"Output: {CONSENSUS_CAMPUS}")

    # Step 1: Load data
    ucid_data = load_campus_data()

    # Step 2: Create feature class
    create_consensus_feature_class()

    # Step 3: Generate consensus records
    consensus_records = generate_consensus_records(ucid_data)

    # Step 4: Insert records
    insert_count = insert_consensus_records(consensus_records)

    # Step 5: Validate
    final_count = validate_output()

    print("\n" + "="*70)
    print("CONSENSUS LAYER COMPLETE")
    print("="*70)
    print(f"""
    Records created: {final_count}
    Output: {CONSENSUS_CAMPUS}

    Next steps:
    1. Review in ArcGIS Pro
    2. Run validate_consensus.py for detailed QA
    3. Publish to Portal
    """)

    return final_count


if __name__ == "__main__":
    main()
else:
    # Running via exec()
    main()
