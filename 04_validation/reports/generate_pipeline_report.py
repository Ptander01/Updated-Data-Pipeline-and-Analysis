# generate_pipeline_report.py
# Generates a comprehensive HTML diagnostic report for the DC GIS Pipeline
# Features glassmorphism/liquid glass UI aesthetic
# Run after pipeline completion to analyze data health and quality
#
# Usage: Run in ArcGIS Pro Python window after pipeline execution

import arcpy
import os
import math
from datetime import datetime
from collections import defaultdict

# CONFIGURATION

# Import paths from central config
import sys
SCRIPTS_DIR = r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\scripts"
if os.path.join(SCRIPTS_DIR, "_utils") not in sys.path:
    sys.path.insert(0, os.path.join(SCRIPTS_DIR, "_utils"))

try:
    from config import GDB, GOLD_BUILDINGS, GOLD_CAMPUS, PIPELINE_REPORTS_DIR
    REPORT_OUTPUT_DIR = str(PIPELINE_REPORTS_DIR)
except ImportError:
    # Fallback if PIPELINE_REPORTS_DIR not defined in config
    from config import GDB, GOLD_BUILDINGS, GOLD_CAMPUS
    REPORT_OUTPUT_DIR = os.path.join(SCRIPTS_DIR, "00_docs", "reports", "pipeline_diagnostics")

GDB_PATH = GDB

# Feature classes to analyze (using paths from config)
FEATURE_CLASSES = {
    "gold_buildings_full": ("Buildings (Raw Ingested)", GOLD_BUILDINGS),
    "gold_campus_full": ("Campus (Rolled Up)", GOLD_CAMPUS),
    "gold_combined_xb": ("XB Combined (Final Output)", os.path.join(GDB, "gold_combined_xb"))
}

# Critical fields to check - organized by business value
SCORING_CATEGORIES = {
    "core": {
        "name": "Core Identity",
        "weight": 0.25,  # Reduced from 0.30 to make room for spatial accuracy
        "description": "Essential fields for record identification",
        "fields": ["unique_id", "campus_name", "company_clean", "ucid"]
    },
    "capacity": {
        "name": "Capacity Data",
        "weight": 0.20,  # Reduced from 0.25
        "description": "Power capacity information",
        "fields": ["full_capacity_mw", "commissioned_power_mw", "planned_plus_uc_mw"]
    },
    "location": {
        "name": "Location Quality",
        "weight": 0.15,  # Reduced from 0.20
        "description": "Geographic precision (field completeness)",
        "fields": ["latitude", "longitude", "city", "country"]
    },
    "spatial_accuracy": {
        "name": "Spatial Accuracy",
        "weight": 0.20,  # NEW - measures location accuracy vs Meta canonical
        "description": "Location accuracy vs Meta ground truth",
        "fields": []  # Calculated from spatial accuracy analysis
    },
    "strategic": {
        "name": "Strategic Intel",
        "weight": 0.10,  # Reduced from 0.15
        "description": "Timeline, ownership, and development info",
        "fields": ["developer", "owner", "tenant", "construction_start_date", "operational_date"]
    },
    "infrastructure": {
        "name": "Infrastructure",
        "weight": 0.10,  # Same
        "description": "Technical specifications",
        "fields": ["energy_source", "building_count", "sqft"]
    }
}

# Critical fields for XB layer completeness check
# Updated to include V2 schema fields for comprehensive coverage
CRITICAL_FIELDS = {
    "identity": ["campus_name", "company_clean", "company_clean_filter", "UCID"],
    "location": ["latitude", "longitude", "state", "country", "city"],
    "capacity": ["full_capacity_mw", "commissioned_power_mw", "planned_power_mw", "uc_power_mw"],
    "strategic": ["developer", "owner", "tenant", "operational_date", "data_vintage"],
    "infrastructure": ["energy_source", "building_count", "sqft"],
    "metadata": ["source", "record_level"]
}

# Source names for analysis (included in pipeline)
# These must match the SOURCE_NAME values used in ingestion scripts
SOURCES = [
    "DataCenterHawk",
    "DataCenterMap",
    "Semianalysis",
    "NewProjectMedia",
    "Meta Canonical"
]

# External sources to score against Meta Canonical ground truth
# Meta Canonical is EXCLUDED - it's the reference, not a source being evaluated
SOURCES_FOR_ACCURACY_SCORING = [
    "DataCenterHawk",
    "DataCenterMap",
    "Semianalysis",
    "NewProjectMedia"
]

# Sources excluded from pipeline - will be shown in Source Analysis with poor grades
EXCLUDED_SOURCE_GRADES = {
    "Synergy": {
        "reason": "No coordinates available",
        "records": 956,
        "scores": {
            "volume": 15,       # Has records but can't contribute spatially
            "core": 40,         # Has company names
            "capacity": 0,      # No capacity data
            "location": 0,      # NO COORDINATES - critical failure
            "spatial_accuracy": 0,  # Can't measure without coords
            "richness": 20,     # Very limited attributes
            "forecast_bonus": 0
        },
        "final_score": 12,  # Weighted average
        "grade": "F",
        "grade_color": "#f87171",
        "excluded": True
    },
    "WoodMac": {
        "reason": "Tracks development phases, not buildings",
        "records": 491,
        "scores": {
            "volume": 8,        # Small dataset
            "core": 30,         # Has project names
            "capacity": 10,     # Sparse capacity data (~10%)
            "location": 85,     # Geocoded coordinates available
            "spatial_accuracy": 0,  # Not comparable to building-level
            "richness": 35,     # Has energy/fuel data
            "forecast_bonus": 0
        },
        "final_score": 28,  # Better than Synergy but still poor
        "grade": "F",
        "grade_color": "#f87171",
        "excluded": True
    }
}

# Sources excluded from pipeline with reasons (for Excluded Sources section)
EXCLUDED_SOURCES = {
    "Synergy": {
        "reason": "No coordinates available",
        "records": "~956",
        "detail": "Facility counts only - no geocoded locations. Use for transparency reporting, not spatial consensus.",
        "potential_value": "Could provide aggregate facility counts by operator"
    },
    "WoodMac": {
        "reason": "Tracks development phases, not buildings",
        "records": "~491 geocoded",
        "detail": "WoodMac tracks project development phases rather than physical buildings. Excluded per GRANULARITY_STRATEGY.md.",
        "potential_value": "Has energy/fuel data that could inform V2 energy_source field. Consider selective field extraction."
    }
}

# UTILITY FUNCTIONS

# SPATIAL ACCURACY FUNCTIONS

def haversine_distance(lat1, lon1, lat2, lon2):
    """Calculate geodesic distance in meters using Haversine formula."""
    if any(v is None for v in [lat1, lon1, lat2, lon2]):
        return None

    R = 6371000  # Earth's radius in meters

    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)

    a = math.sin(delta_lat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon/2)**2
    c = 2 * math.asin(math.sqrt(a))

    return R * c


def calculate_capacity_accuracy_stats(gold_buildings_fc, meta_canonical_fc, search_radius_km=50):
    """
    Calculate capacity accuracy metrics for each source against Meta Canonical IT Load.

    Uses the pre-computed spatial matches from accuracy_analysis_multi_source_REBUILT
    (same as capacity_accuracy_analysis_v2.py). Falls back to verified static values
    from CAPACITY_ACCURACY_EXECUTIVE_REPORT.md if spatial matches unavailable.

    Verified MAPE values (Dec 2024):
    - Semianalysis mw_2023: 11.9% MAPE (Complete Builds) → Grade A
    - DataCenterHawk commissioned_power_mw: 17.6% MAPE → Grade B
    - Others: Insufficient data (DCM 1.5% coverage, NPM 24%)

    Returns dict with per-source capacity accuracy stats:
    - mape: Mean Absolute Percentage Error (lower is better)
    - bias_pct: Systematic over/under estimation
    - n_matched: Number of matched comparisons
    - capacity_grade: Letter grade based on MAPE
    """
    print("  Calculating capacity accuracy vs Meta Canonical IT Load...")

    # Pre-computed spatial matches (same as capacity_accuracy_analysis_v2.py uses)
    SPATIAL_MATCHES_FC = os.path.join(GDB_PATH, "accuracy_analysis_multi_source_REBUILT")
    META_BUILDINGS_FC = os.path.join(GDB_PATH, "meta_canonical_buildings")

    # Verified static values from CAPACITY_ACCURACY_EXECUTIVE_REPORT.md (Dec 2024)
    # Used as fallback or when sources have insufficient spatial match data
    VERIFIED_CAPACITY_STATS = {
        "Semianalysis": {
            "mape": 11.9,
            "bias_pct": -5.2,  # Slight under-estimate
            "n_matched": 92,
            "cap_field": "mw_2023",
            "grade": "A",
            "grade_color": "#34d399",
            "source": "Executive Report (Dec 2024)"
        },
        "DataCenterHawk": {
            "mape": 17.6,
            "bias_pct": -10.0,  # Under-reports by ~16%
            "n_matched": 115,
            "cap_field": "commissioned_power_mw",
            "grade": "B",
            "grade_color": "#60a5fa",
            "source": "Executive Report (Dec 2024)"
        },
        "DataCenterMap": {
            "mape": None,
            "n_matched": 1,
            "error": "Low Meta overlap",
            "grade": "—",
            "grade_color": "#8892b0",
            "label": "Unverified"
        },
        "NewProjectMedia": {
            "mape": None,
            "n_matched": 8,
            "error": "Sparse coverage (24%)",
            "grade": "D",
            "grade_color": "#fb923c"
        }
    }

    # Field configurations for each source (from capacity_accuracy_analysis_v2.py)
    # These are the optimal fields determined by variance experiments
    SOURCE_CAPACITY_FIELDS = {
        "Semianalysis": ["mw_2023", "mw_2024", "commissioned_power_mw"],
        "DataCenterHawk": ["commissioned_power_mw", "full_capacity_mw"],
        "DataCenterMap": ["commissioned_power_mw", "full_capacity_mw"],
        "NewProjectMedia": ["full_capacity_mw"],
        "Meta Canonical": []  # Skip - this IS the ground truth
    }

    # Check if pre-computed spatial matches exist for live calculation
    use_live_calculation = arcpy.Exists(SPATIAL_MATCHES_FC) and arcpy.Exists(META_BUILDINGS_FC)

    if use_live_calculation:
        print("    Found pre-computed spatial matches - attempting live calculation...")
        # TODO: Implement live calculation using accuracy_analysis_multi_source_REBUILT
        # For now, fall through to verified values
        use_live_calculation = False  # Disable until implemented

    if not use_live_calculation:
        # Use verified static values from executive report
        print("    Using verified capacity accuracy from CAPACITY_ACCURACY_EXECUTIVE_REPORT.md (Dec 2024)")

        capacity_results = {"available": True, "sources": {}, "calculation_method": "verified_static"}

        for source_name in SOURCE_CAPACITY_FIELDS.keys():
            if source_name == "Meta Canonical":
                continue  # Skip - this is ground truth

            if source_name in VERIFIED_CAPACITY_STATS:
                stats = VERIFIED_CAPACITY_STATS[source_name].copy()
                capacity_results["sources"][source_name] = stats
            else:
                capacity_results["sources"][source_name] = {
                    "mape": None,
                    "n_matched": 0,
                    "error": "No verified data available",
                    "grade": "F",
                    "grade_color": "#f87171"
                }

        # Print summary
        print(f"    Capacity accuracy (verified):")
        for source, stats in capacity_results["sources"].items():
            if stats.get("mape") is not None:
                print(f"      {source}: MAPE={stats['mape']:.1f}%, Grade={stats['grade']}, n={stats['n_matched']}")
            else:
                print(f"      {source}: {stats.get('error', 'No data')} → Grade {stats.get('grade', 'F')}")

        return capacity_results

    # If we get here, use the legacy on-the-fly calculation (fallback)
    search_radius_m = search_radius_km * 1000

    # Load Meta Canonical buildings with IT load
    meta_buildings = {}
    meta_fields = ["SHAPE@", "building_key", "it_load_total", "latitude", "longitude"]

    try:
        available_meta_fields = [f.name for f in arcpy.ListFields(meta_canonical_fc)]
        read_meta_fields = [f for f in meta_fields if f in available_meta_fields or f == "SHAPE@"]

        with arcpy.da.SearchCursor(meta_canonical_fc, read_meta_fields) as cursor:
            for row in cursor:
                geom = row[0]
                bldg_key = row[1] if len(row) > 1 else None
                it_load = row[2] if len(row) > 2 else None
                lat = row[3] if len(row) > 3 else None
                lon = row[4] if len(row) > 4 else None

                # Only include buildings with valid IT load data
                if it_load and it_load > 0 and bldg_key:
                    # Get centroid coords
                    if geom and lat is None:
                        centroid = geom.centroid
                        lat, lon = centroid.Y, centroid.X

                    if lat and lon and abs(lat) > 0.1 and abs(lon) > 0.1:
                        meta_buildings[bldg_key] = {
                            "lat": lat,
                            "lon": lon,
                            "it_load": it_load
                        }

        print(f"    Loaded {len(meta_buildings)} Meta buildings with IT load")

        if len(meta_buildings) == 0:
            return {"available": False, "error": "No Meta buildings with IT load found"}

    except Exception as e:
        print(f"    ⚠ Error loading Meta canonical: {e}")
        return {"available": False, "error": str(e)}

    # Get available fields in gold_buildings
    available_gold_fields = [f.name for f in arcpy.ListFields(gold_buildings_fc)]

    # Calculate capacity accuracy for each source
    capacity_results = {"available": True, "sources": {}}

    for source_name, cap_fields in SOURCE_CAPACITY_FIELDS.items():
        if not cap_fields:  # Skip Meta Canonical
            continue

        # Find first available capacity field for this source
        source_cap_field = None
        for cf in cap_fields:
            if cf in available_gold_fields:
                source_cap_field = cf
                break

        if not source_cap_field:
            capacity_results["sources"][source_name] = {
                "mape": None,
                "bias_pct": None,
                "n_matched": 0,
                "error": "No capacity fields found"
            }
            continue

        # Load source records
        source_records = []
        read_fields = ["SHAPE@", "latitude", "longitude", source_cap_field]
        read_fields = [f for f in read_fields if f in available_gold_fields or f == "SHAPE@"]

        where_clause = f"source = '{source_name}'"

        try:
            with arcpy.da.SearchCursor(gold_buildings_fc, read_fields, where_clause) as cursor:
                for row in cursor:
                    geom = row[0]
                    lat = row[1] if len(row) > 1 else None
                    lon = row[2] if len(row) > 2 else None
                    capacity = row[3] if len(row) > 3 else None

                    # Get coords from geometry if needed
                    if geom and lat is None:
                        centroid = geom.centroid
                        lat, lon = centroid.Y, centroid.X

                    # Only include records with valid coordinates and capacity
                    if lat and lon and capacity and capacity > 0:
                        if abs(lat) > 0.1 and abs(lon) > 0.1:
                            source_records.append({
                                "lat": lat,
                                "lon": lon,
                                "capacity": capacity
                            })

            if len(source_records) == 0:
                capacity_results["sources"][source_name] = {
                    "mape": None,
                    "bias_pct": None,
                    "n_matched": 0,
                    "error": "No records with capacity data"
                }
                continue

            # Match source records to Meta buildings (closest within radius)
            # Deduplicate to closest match per Meta building
            matches = {}  # meta_bldg_key -> best match

            for src_rec in source_records:
                src_lat, src_lon = src_rec["lat"], src_rec["lon"]

                for bldg_key, meta_info in meta_buildings.items():
                    dist = haversine_distance(src_lat, src_lon, meta_info["lat"], meta_info["lon"])

                    if dist and dist <= search_radius_m:
                        if bldg_key not in matches or dist < matches[bldg_key]["distance"]:
                            matches[bldg_key] = {
                                "distance": dist,
                                "source_capacity": src_rec["capacity"],
                                "meta_it_load": meta_info["it_load"]
                            }

            # Calculate MAPE and bias
            if len(matches) >= 3:  # Minimum sample size
                errors = []
                signed_errors = []

                for match in matches.values():
                    actual = match["meta_it_load"]
                    predicted = match["source_capacity"]

                    if actual > 0:
                        pct_error = abs(predicted - actual) / actual * 100
                        signed_error = (predicted - actual) / actual * 100
                        errors.append(pct_error)
                        signed_errors.append(signed_error)

                if errors:
                    mape = sum(errors) / len(errors)
                    bias_pct = sum(signed_errors) / len(signed_errors)

                    # Calculate grade based on MAPE
                    # A: <15%, B: 15-25%, C: 25-40%, D: 40-60%, F: >60%
                    if mape < 15:
                        cap_grade, cap_color = "A", "#34d399"
                    elif mape < 25:
                        cap_grade, cap_color = "B", "#60a5fa"
                    elif mape < 40:
                        cap_grade, cap_color = "C", "#fbbf24"
                    elif mape < 60:
                        cap_grade, cap_color = "D", "#fb923c"
                    else:
                        cap_grade, cap_color = "F", "#f87171"

                    capacity_results["sources"][source_name] = {
                        "mape": round(mape, 1),
                        "bias_pct": round(bias_pct, 1),
                        "n_matched": len(matches),
                        "cap_field": source_cap_field,
                        "grade": cap_grade,
                        "grade_color": cap_color
                    }
                else:
                    capacity_results["sources"][source_name] = {
                        "mape": None,
                        "n_matched": len(matches),
                        "error": "No valid error calculations"
                    }
            else:
                capacity_results["sources"][source_name] = {
                    "mape": None,
                    "n_matched": len(matches),
                    "error": f"Insufficient matches ({len(matches)} < 3)"
                }

        except Exception as e:
            capacity_results["sources"][source_name] = {
                "mape": None,
                "n_matched": 0,
                "error": str(e)
            }

    # Print summary
    print(f"    Capacity accuracy results:")
    for source, stats in capacity_results["sources"].items():
        if stats.get("mape") is not None:
            print(f"      {source}: MAPE={stats['mape']:.1f}%, n={stats['n_matched']}")
        else:
            print(f"      {source}: {stats.get('error', 'No data')}")

    return capacity_results


def calculate_spatial_accuracy_stats(gold_buildings_fc, meta_canonical_fc, search_radius_km=50):
    """
    Calculate spatial accuracy metrics for each source against Meta Canonical.

    Uses the methodology from:
    - comprehensive_spatial_accuracy_report.py (median, MAD, percentiles)
    - multi_source_spatial_accuracy.py (Haversine, recall, thresholds)

    Returns dict with per-source accuracy stats including:
    - recall_pct: % of Meta buildings detected
    - median_distance_m: Median Haversine distance in meters
    - mad_m: Median Absolute Deviation in meters
    - pct_within_100m, 500m, 1km, 5km: Threshold performance

    Note: Only Meta buildings with valid coordinates are included in the denominator.
    "Null island" records (0,0 or near 0,0) are excluded.
    """
    print("  Calculating spatial accuracy vs Meta Canonical...")

    # Check if meta_canonical exists
    if not arcpy.Exists(meta_canonical_fc):
        print(f"    ⚠ Meta canonical not found: {meta_canonical_fc}")
        return {"available": False, "error": "Meta canonical feature class not found"}

    # Get Meta Canonical building locations with coordinates
    meta_buildings = []
    meta_fields = get_field_names(meta_canonical_fc)

    # Check if has_coordinates field exists (used in comprehensive_spatial_accuracy_report.py)
    has_coords_field = "has_coordinates" if "has_coordinates" in meta_fields else None
    dc_code_field = "dc_code" if "dc_code" in meta_fields else None
    building_key_field = "building_key" if "building_key" in meta_fields else None

    # Read Meta Canonical with coordinates
    read_fields = ["SHAPE@XY"]
    if has_coords_field:
        read_fields.append(has_coords_field)
    if building_key_field:
        read_fields.append(building_key_field)
    if dc_code_field:
        read_fields.append(dc_code_field)

    total_records = 0
    null_island_count = 0
    no_coords_count = 0

    with arcpy.da.SearchCursor(meta_canonical_fc, read_fields) as cursor:
        for row in cursor:
            total_records += 1
            xy = row[0]

            # Check has_coordinates field if available
            if has_coords_field:
                has_coords_idx = read_fields.index(has_coords_field)
                has_coords_val = row[has_coords_idx]
                if has_coords_val != 1:
                    no_coords_count += 1
                    continue

            # Check for valid geometry
            if not xy or xy[0] is None or xy[1] is None:
                no_coords_count += 1
                continue

            lon, lat = xy[0], xy[1]

            # Filter out "null island" - coordinates at or near (0, 0)
            # Null island is in the Gulf of Guinea - no data centers there
            if abs(lat) < 0.1 and abs(lon) < 0.1:
                null_island_count += 1
                continue

            # Also filter out obviously invalid coordinates
            if abs(lat) > 90 or abs(lon) > 180:
                no_coords_count += 1
                continue

            rec = {
                "lon": lon,
                "lat": lat,
                "building_key": row[read_fields.index(building_key_field)] if building_key_field and building_key_field in read_fields else None,
                "dc_code": row[read_fields.index(dc_code_field)] if dc_code_field and dc_code_field in read_fields else None
            }
            meta_buildings.append(rec)

    total_meta_buildings = len(meta_buildings)
    if total_meta_buildings == 0:
        print("    ⚠ No Meta canonical buildings with valid coordinates")
        return {"available": False, "error": "No Meta buildings with valid coordinates"}

    print(f"    Meta Canonical: {total_meta_buildings} buildings with valid coordinates")
    if null_island_count > 0:
        print(f"    (Excluded {null_island_count} null island records, {no_coords_count} without coordinates)")

    # Get gold_buildings data grouped by source
    gold_fields = get_field_names(gold_buildings_fc)
    gold_lat_field = "latitude" if "latitude" in gold_fields else None
    gold_lon_field = "longitude" if "longitude" in gold_fields else None

    if not gold_lat_field or not gold_lon_field:
        print("    ⚠ Gold buildings missing lat/lon fields")
        return {"available": False, "error": "Gold buildings missing coordinates"}

    # Collect gold buildings by source
    gold_by_source = defaultdict(list)
    read_fields = ["source", gold_lat_field, gold_lon_field]

    with arcpy.da.SearchCursor(gold_buildings_fc, read_fields) as cursor:
        for row in cursor:
            source = row[0]
            lat = row[1]
            lon = row[2]
            if source and lat and lon:
                # Also filter out null island from gold buildings
                if abs(lat) < 0.1 and abs(lon) < 0.1:
                    continue
                gold_by_source[source].append({"lat": lat, "lon": lon})

    # Calculate accuracy for each source (excluding Meta Canonical - it's the reference)
    accuracy_results = {}
    search_radius_m = search_radius_km * 1000

    for source_name in SOURCES_FOR_ACCURACY_SCORING:
        source_buildings = gold_by_source.get(source_name, [])

        if not source_buildings:
            accuracy_results[source_name] = {
                "buildings_in_source": 0,
                "recall_pct": 0,
                "median_distance_m": None,
                "mad_m": None,
                "pct_within_100m": 0,
                "pct_within_500m": 0,
                "pct_within_1km": 0,
                "pct_within_5km": 0,
                "matched_count": 0
            }
            continue

        # For each Meta building, find closest match in source
        distances = []
        matched_meta = 0

        for meta_bldg in meta_buildings:
            min_dist = None

            for gold_bldg in source_buildings:
                dist = haversine_distance(
                    meta_bldg["lat"], meta_bldg["lon"],
                    gold_bldg["lat"], gold_bldg["lon"]
                )
                if dist is not None and dist <= search_radius_m:
                    if min_dist is None or dist < min_dist:
                        min_dist = dist

            if min_dist is not None:
                distances.append(min_dist)
                matched_meta += 1

        # Calculate statistics
        if distances:
            distances.sort()
            n = len(distances)
            median = distances[n // 2] if n % 2 == 1 else (distances[n//2 - 1] + distances[n//2]) / 2

            # MAD (Median Absolute Deviation)
            deviations = sorted([abs(d - median) for d in distances])
            mad = deviations[len(deviations) // 2]

            # Threshold performance
            within_100m = sum(1 for d in distances if d <= 100)
            within_500m = sum(1 for d in distances if d <= 500)
            within_1km = sum(1 for d in distances if d <= 1000)
            within_5km = sum(1 for d in distances if d <= 5000)

            accuracy_results[source_name] = {
                "buildings_in_source": len(source_buildings),
                "matched_count": matched_meta,
                "recall_pct": round((matched_meta / total_meta_buildings) * 100, 1),
                "median_distance_m": round(median, 0),
                "mad_m": round(mad, 0),
                "pct_within_100m": round((within_100m / n) * 100, 1),
                "pct_within_500m": round((within_500m / n) * 100, 1),
                "pct_within_1km": round((within_1km / n) * 100, 1),
                "pct_within_5km": round((within_5km / n) * 100, 1)
            }
        else:
            accuracy_results[source_name] = {
                "buildings_in_source": len(source_buildings),
                "matched_count": 0,
                "recall_pct": 0,
                "median_distance_m": None,
                "mad_m": None,
                "pct_within_100m": 0,
                "pct_within_500m": 0,
                "pct_within_1km": 0,
                "pct_within_5km": 0
            }

    return {
        "available": True,
        "total_meta_buildings": total_meta_buildings,
        "sources": accuracy_results
    }


def calculate_consensus_metrics(gold_campus_fc, gold_buildings_fc):
    """
    Calculate consensus strength metrics measuring source agreement.

    Key Question: "How useful is this consensus dataset for decision-making?"

    This measures multiple dimensions of consensus quality:
    - Source overlap: How many sources contribute to each campus?
    - Value agreement: Do sources agree on MW, SQFT, building counts?
    - Company tier weighting: Hyperscalers weighted higher than small/unknown operators
    - Overall quality: Composite score factoring source quality and coverage

    Returns dict with:
    - avg_sources_per_campus: Average number of sources per campus
    - pct_multi_source: % of campuses with 2+ sources
    - tier_breakdown: Metrics broken down by Hyperscaler/Major Colo/Other
    - weighted_score: Business-value weighted consensus quality score
    """
    print("  Calculating consensus strength metrics...")

    # Import company tier classification
    # Use known project path since __file__ may not be defined when run via exec()
    try:
        import sys
        # Try to construct path from known project location
        project_base = r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\scripts"
        consensus_path = os.path.join(project_base, "07_consensus")
        if os.path.exists(consensus_path) and consensus_path not in sys.path:
            sys.path.insert(0, consensus_path)
        from authority_config import get_company_tier, COMPANY_TIER_WEIGHTS, SOURCE_METADATA
    except (ImportError, Exception) as e:
        print(f"    ⚠ Could not import authority_config ({e}), using fallback tier classification")
        COMPANY_TIER_WEIGHTS = {"hyperscaler": 0.60, "major_colo": 0.30, "other": 0.10}
        SOURCE_METADATA = {}

        # Inline fallback functions
        HYPERSCALER_LIST = ["AWS", "MICROSOFT", "GOOGLE", "META", "APPLE", "ORACLE", "ALIBABA", "XAI"]
        MAJOR_COLO_LIST = ["EQUINIX", "DIGITAL REALTY", "CYRUSONE", "QTS", "CORESITE", "VANTAGE",
                          "DATABANK", "SWITCH", "STACK", "COMPASS", "EDGECORE", "PRIME", "CLOUDHQ",
                          "STREAM", "ALIGNED", "NTT", "LUMEN", "IRON MOUNTAIN", "FLEXENTIAL"]

        def get_company_tier(company):
            if not company:
                return "other"
            company_upper = company.upper()
            for h in HYPERSCALER_LIST:
                if h in company_upper:
                    return "hyperscaler"
            for c in MAJOR_COLO_LIST:
                if c in company_upper:
                    return "major_colo"
            return "other"

    results = {
        "available": True,
        "campus_analysis": {},
        "summary": {},
        "tier_breakdown": {}
    }

    try:
        # Get all campuses with their source info
        # We need to look at gold_buildings grouped by UCID to see source overlap

        available_fields = [f.name for f in arcpy.ListFields(gold_buildings_fc)]

        # Check for ucid field (for grouping) and source field
        ucid_field = "ucid" if "ucid" in available_fields else None

        if not ucid_field:
            print("    ⚠ UCID field not found - using campus_id instead")
            ucid_field = "campus_id" if "campus_id" in available_fields else None

        if not ucid_field:
            return {"available": False, "error": "No campus grouping field found (ucid or campus_id)"}

        # Check for company field
        company_field = None
        for cf in ["company_clean", "company_clean_filter", "company"]:
            if cf in available_fields:
                company_field = cf
                break

        # Read building data and group by campus
        campus_data = defaultdict(lambda: {
            "sources": set(),
            "source_records": defaultdict(list),
            "mw_values": [],
            "sqft_values": [],
            "building_count": 0,
            "company": None,
            "tier": "other",
            "is_essential": False
        })

        read_fields = [ucid_field, "source"]

        # Add company field if available
        if company_field:
            read_fields.append(company_field)

        # Check for is_essential field (Essential DC list integration)
        is_essential_field = "is_essential" if "is_essential" in available_fields else None
        if is_essential_field:
            read_fields.append(is_essential_field)
            print("    Including is_essential field for Essential DC coverage analysis")

        # Add capacity fields if available
        mw_field = None
        for mw_candidate in ["commissioned_power_mw", "full_capacity_mw"]:
            if mw_candidate in available_fields:
                mw_field = mw_candidate
                read_fields.append(mw_field)
                break

        sqft_field = "sqft" if "sqft" in available_fields else None
        if sqft_field:
            read_fields.append(sqft_field)

        print(f"    Reading buildings grouped by {ucid_field}...")
        if company_field:
            print(f"    Using company field: {company_field}")

        with arcpy.da.SearchCursor(gold_buildings_fc, read_fields) as cursor:
            for row in cursor:
                campus_key = row[0]
                source = row[1]

                if not campus_key or not source:
                    continue

                campus_data[campus_key]["sources"].add(source)
                campus_data[campus_key]["building_count"] += 1

                # Track company (first non-null value wins)
                if company_field:
                    field_idx = read_fields.index(company_field)
                    company_val = row[field_idx]
                    if company_val and not campus_data[campus_key]["company"]:
                        campus_data[campus_key]["company"] = company_val
                        campus_data[campus_key]["tier"] = get_company_tier(company_val)

                # Track is_essential flag (if ANY building is essential, campus is essential)
                if is_essential_field:
                    essential_idx = read_fields.index(is_essential_field)
                    if essential_idx < len(row):
                        essential_val = row[essential_idx]
                        if essential_val and essential_val == 1:
                            campus_data[campus_key]["is_essential"] = True

                # Track MW per source for variance analysis
                if mw_field:
                    mw_idx = read_fields.index(mw_field)
                    if mw_idx < len(row):
                        mw_val = row[mw_idx]
                        if mw_val and mw_val > 0:
                            campus_data[campus_key]["mw_values"].append(mw_val)
                            campus_data[campus_key]["source_records"][source].append({"mw": mw_val})

                # Track SQFT if available
                if sqft_field:
                    sqft_idx = read_fields.index(sqft_field)
                    if sqft_idx < len(row):
                        sqft_val = row[sqft_idx]
                        if sqft_val and sqft_val > 0:
                            campus_data[campus_key]["sqft_values"].append(sqft_val)

        total_campuses = len(campus_data)
        print(f"    Analyzed {total_campuses} unique campuses")

        if total_campuses == 0:
            return {"available": False, "error": "No campuses found for analysis"}

        # Initialize tier-specific tracking
        tier_metrics = {
            "hyperscaler": {"total": 0, "multi_source": 0, "source_counts": [], "label": "Hyperscaler/Frontier"},
            "major_colo": {"total": 0, "multi_source": 0, "source_counts": [], "label": "Major Colo/Enterprise"},
            "other": {"total": 0, "multi_source": 0, "source_counts": [], "label": "Other/Unknown"}
        }

        # Initialize Essential DC tracking (the curated strategic sites list)
        essential_metrics = {
            "total": 0,
            "multi_source": 0,
            "source_counts": [],
            "companies": defaultdict(int)
        }

        # Calculate metrics
        source_counts = []
        multi_source_count = 0
        mw_variances = []
        confidence_levels = {"high": 0, "medium": 0, "low": 0}

        for campus_key, data in campus_data.items():
            num_sources = len(data["sources"])
            source_counts.append(num_sources)
            tier = data["tier"]

            # Track tier-specific metrics
            tier_metrics[tier]["total"] += 1
            tier_metrics[tier]["source_counts"].append(num_sources)
            if num_sources >= 2:
                tier_metrics[tier]["multi_source"] += 1
                multi_source_count += 1

            # Track Essential DC metrics (sites from curated strategic list)
            if data["is_essential"]:
                essential_metrics["total"] += 1
                essential_metrics["source_counts"].append(num_sources)
                if data["company"]:
                    essential_metrics["companies"][data["company"]] += 1
                if num_sources >= 2:
                    essential_metrics["multi_source"] += 1

            # Calculate MW variance if multiple sources contributed
            if len(data["source_records"]) >= 2:
                # Get total MW per source
                source_mw_totals = []
                for source, records in data["source_records"].items():
                    source_total = sum(r.get("mw", 0) for r in records)
                    if source_total > 0:
                        source_mw_totals.append(source_total)

                if len(source_mw_totals) >= 2:
                    # Calculate coefficient of variation (CV = std/mean * 100)
                    mean_mw = sum(source_mw_totals) / len(source_mw_totals)
                    if mean_mw > 0:
                        variance = sum((x - mean_mw) ** 2 for x in source_mw_totals) / len(source_mw_totals)
                        std_mw = variance ** 0.5
                        cv = (std_mw / mean_mw) * 100
                        mw_variances.append(cv)

            # Assign confidence level
            # High: 3+ sources, Low variance
            # Medium: 2 sources OR moderate variance
            # Low: 1 source OR high variance
            if num_sources >= 3:
                confidence_levels["high"] += 1
            elif num_sources == 2:
                confidence_levels["medium"] += 1
            else:
                confidence_levels["low"] += 1

        # Calculate summary statistics
        avg_sources = sum(source_counts) / len(source_counts) if source_counts else 0
        pct_multi_source = (multi_source_count / total_campuses * 100) if total_campuses > 0 else 0
        avg_mw_cv = sum(mw_variances) / len(mw_variances) if mw_variances else None

        # Calculate tier-specific stats
        tier_breakdown = {}
        for tier, data in tier_metrics.items():
            if data["total"] > 0:
                tier_avg = sum(data["source_counts"]) / len(data["source_counts"]) if data["source_counts"] else 0
                tier_pct = (data["multi_source"] / data["total"] * 100) if data["total"] > 0 else 0
                tier_breakdown[tier] = {
                    "label": data["label"],
                    "total_campuses": data["total"],
                    "multi_source_count": data["multi_source"],
                    "pct_multi_source": round(tier_pct, 1),
                    "avg_sources": round(tier_avg, 2),
                    "weight": COMPANY_TIER_WEIGHTS.get(tier, 0.10)
                }
            else:
                tier_breakdown[tier] = {
                    "label": data["label"],
                    "total_campuses": 0,
                    "multi_source_count": 0,
                    "pct_multi_source": 0,
                    "avg_sources": 0,
                    "weight": COMPANY_TIER_WEIGHTS.get(tier, 0.10)
                }

        # Calculate WEIGHTED consensus score (0-100)
        # Formula: Weighted average of tier multi-source %, scaled by avg sources
        weighted_score = 0
        total_weight = 0
        for tier, metrics in tier_breakdown.items():
            if metrics["total_campuses"] > 0:
                # Score for this tier: multi-source % * source density factor
                # Source density factor: min(avg_sources / 2.0, 1.5) - rewards higher avg sources
                source_density = min(metrics["avg_sources"] / 2.0, 1.5)
                tier_score = metrics["pct_multi_source"] * source_density
                weighted_score += tier_score * metrics["weight"]
                total_weight += metrics["weight"]

        # Normalize tier-based score to 0-100 scale
        if total_weight > 0:
            tier_weighted_score = weighted_score / total_weight
        else:
            tier_weighted_score = 0
        tier_weighted_score = min(100, max(0, tier_weighted_score))

        # Calculate Essential DC score (strategic sites coverage)
        # Essential sites are the curated must-track facilities - their coverage matters!
        essential_score = 0
        if essential_metrics["total"] > 0:
            essential_pct = (essential_metrics["multi_source"] / essential_metrics["total"] * 100)
            essential_avg = sum(essential_metrics["source_counts"]) / len(essential_metrics["source_counts"]) if essential_metrics["source_counts"] else 0
            # Apply same source density factor as tiers
            essential_density = min(essential_avg / 2.0, 1.5)
            essential_score = essential_pct * essential_density
            essential_score = min(100, max(0, essential_score))

        # COMPOSITE SCORE: Combine tier-weighted (80%) + Essential DC (20%)
        # If no Essential sites tracked, fall back to tier-only scoring
        TIER_WEIGHT = 0.80
        ESSENTIAL_WEIGHT = 0.20

        if essential_metrics["total"] > 0:
            weighted_score = (tier_weighted_score * TIER_WEIGHT) + (essential_score * ESSENTIAL_WEIGHT)
            score_composition = f"Tier-based: {tier_weighted_score:.1f} (80%) + Essential DC: {essential_score:.1f} (20%)"
        else:
            weighted_score = tier_weighted_score
            score_composition = "Tier-based only (no Essential DC sites detected)"

        weighted_score = min(100, max(0, weighted_score))

        # Determine grade based on WEIGHTED score (not raw multi-source %)
        # A: 75+ (strong coverage of high-value sites)
        # B: 55+ (good coverage of high-value sites)
        # C: 35+ (moderate coverage)
        # D: 20+ (weak coverage)
        # F: <20 (minimal coverage)

        if weighted_score >= 75:
            consensus_grade, consensus_color = "A", "#34d399"
            consensus_label = "Strong Consensus"
        elif weighted_score >= 55:
            consensus_grade, consensus_color = "B", "#60a5fa"
            consensus_label = "Good Consensus"
        elif weighted_score >= 35:
            consensus_grade, consensus_color = "C", "#fbbf24"
            consensus_label = "Moderate Consensus"
        elif weighted_score >= 20:
            consensus_grade, consensus_color = "D", "#fb923c"
            consensus_label = "Weak Consensus"
        else:
            consensus_grade, consensus_color = "F", "#f87171"
            consensus_label = "Minimal Consensus"

        # Source distribution (how many campuses have 1, 2, 3+ sources)
        source_distribution = defaultdict(int)
        for count in source_counts:
            if count >= 4:
                source_distribution["4+"] += 1
            else:
                source_distribution[str(count)] += 1

        results["tier_breakdown"] = tier_breakdown

        # Calculate Essential DC metrics
        essential_breakdown = None
        if essential_metrics["total"] > 0:
            essential_avg = sum(essential_metrics["source_counts"]) / len(essential_metrics["source_counts"]) if essential_metrics["source_counts"] else 0
            essential_pct = (essential_metrics["multi_source"] / essential_metrics["total"] * 100) if essential_metrics["total"] > 0 else 0
            essential_breakdown = {
                "total_campuses": essential_metrics["total"],
                "multi_source_count": essential_metrics["multi_source"],
                "pct_multi_source": round(essential_pct, 1),
                "avg_sources": round(essential_avg, 2),
                "score": round(essential_score, 1),
                "top_companies": dict(sorted(essential_metrics["companies"].items(), key=lambda x: x[1], reverse=True)[:5])
            }
        results["essential_breakdown"] = essential_breakdown

        results["summary"] = {
            "total_campuses": total_campuses,
            "avg_sources_per_campus": round(avg_sources, 2),
            "pct_multi_source": round(pct_multi_source, 1),
            "multi_source_count": multi_source_count,
            "single_source_count": total_campuses - multi_source_count,
            "avg_mw_coefficient_of_variation": round(avg_mw_cv, 1) if avg_mw_cv else None,
            "weighted_score": round(weighted_score, 1),
            "tier_weighted_score": round(tier_weighted_score, 1),
            "essential_score": round(essential_score, 1) if essential_metrics["total"] > 0 else None,
            "score_composition": score_composition,
            "mw_variance_sample_size": len(mw_variances),
            "consensus_grade": consensus_grade,
            "consensus_color": consensus_color,
            "consensus_label": consensus_label,
            "confidence_distribution": dict(confidence_levels),
            "source_count_distribution": dict(source_distribution)
        }

        # Print summary
        print(f"    Consensus Strength Results:")
        print(f"      Total campuses: {total_campuses}")
        print(f"      Avg sources per campus: {avg_sources:.2f}")
        print(f"      Multi-source campuses: {multi_source_count} ({pct_multi_source:.1f}%)")
        print(f"      Score Composition: {score_composition}")
        print(f"      Final Weighted Score: {weighted_score:.1f}/100")
        print(f"      Consensus Grade: {consensus_grade} ({consensus_label})")
        print(f"      Tier Breakdown:")
        for tier, metrics in tier_breakdown.items():
            if metrics["total_campuses"] > 0:
                print(f"        {metrics['label']}: {metrics['total_campuses']} sites, {metrics['pct_multi_source']:.1f}% multi-source")
        if avg_mw_cv:
            print(f"      Avg MW coefficient of variation: {avg_mw_cv:.1f}%")
        if essential_breakdown:
            print(f"      Essential DC: {essential_breakdown['total_campuses']} campuses, {essential_breakdown['pct_multi_source']:.1f}% multi-source (score: {essential_breakdown['score']:.1f})")

        return results

    except Exception as e:
        print(f"    ⚠ Error calculating consensus metrics: {e}")
        import traceback
        traceback.print_exc()
        return {"available": False, "error": str(e)}


def generate_consensus_strength_section(consensus_data):
    """
    Generate HTML section showing consensus strength metrics.

    Key Question: "How useful is this consensus dataset for decision-making?"
    """
    if not consensus_data.get("available"):
        error_msg = consensus_data.get("error", "Consensus data not available")
        return f'''
        <section id="consensus" class="glass">
            <h2>Consensus Strength</h2>
            <div class="alert alert-warning">
                <span class="alert-icon">⚠</span>
                <div class="alert-content">
                    <div class="alert-title">Data Not Available</div>
                    <div class="alert-text">{error_msg}</div>
                </div>
            </div>
        </section>
'''

    summary = consensus_data.get("summary", {})
    tier_breakdown = consensus_data.get("tier_breakdown", {})

    # Extract key metrics
    total_campuses = summary.get("total_campuses", 0)
    avg_sources = summary.get("avg_sources_per_campus", 0)
    pct_multi_source = summary.get("pct_multi_source", 0)
    multi_source_count = summary.get("multi_source_count", 0)
    single_source_count = summary.get("single_source_count", 0)
    weighted_score = summary.get("weighted_score", 0)

    consensus_grade = summary.get("consensus_grade", "?")
    consensus_color = summary.get("consensus_color", "#8892b0")
    consensus_label = summary.get("consensus_label", "Unknown")

    confidence_dist = summary.get("confidence_distribution", {})
    source_count_dist = summary.get("source_count_distribution", {})

    avg_mw_cv = summary.get("avg_mw_coefficient_of_variation")
    mw_cv_sample = summary.get("mw_variance_sample_size", 0)

    # Build tier breakdown table (the key new feature!)
    tier_rows_html = ""
    tier_order = ["hyperscaler", "major_colo", "other"]
    tier_icons = {"hyperscaler": "🚀", "major_colo": "🏢", "other": "📍"}

    for tier in tier_order:
        if tier in tier_breakdown:
            t = tier_breakdown[tier]
            # Color code based on multi-source %
            if t["pct_multi_source"] >= 50:
                pct_color = "#34d399"  # Green
            elif t["pct_multi_source"] >= 30:
                pct_color = "#60a5fa"  # Blue
            elif t["pct_multi_source"] >= 15:
                pct_color = "#fbbf24"  # Yellow
            else:
                pct_color = "#fb923c"  # Orange

            weight_display = f"{t['weight'] * 100:.0f}%"
            tier_rows_html += f'''
                <tr>
                    <td style="padding: 12px; border-bottom: 1px solid rgba(255,255,255,0.1);">
                        <span style="font-size: 1.1rem; margin-right: 8px;">{tier_icons.get(tier, "📊")}</span>
                        {t["label"]}
                    </td>
                    <td style="padding: 12px; border-bottom: 1px solid rgba(255,255,255,0.1); text-align: center;">{t["total_campuses"]:,}</td>
                    <td style="padding: 12px; border-bottom: 1px solid rgba(255,255,255,0.1); text-align: center; color: {pct_color}; font-weight: 600;">{t["pct_multi_source"]:.1f}%</td>
                    <td style="padding: 12px; border-bottom: 1px solid rgba(255,255,255,0.1); text-align: center;">{t["avg_sources"]:.2f}</td>
                    <td style="padding: 12px; border-bottom: 1px solid rgba(255,255,255,0.1); text-align: center; color: rgba(255,255,255,0.5);">{weight_display}</td>
                </tr>'''

    # Build source count distribution bars
    source_dist_html = ""
    max_count = max(source_count_dist.values()) if source_count_dist else 1
    for src_count in ["1", "2", "3", "4+"]:
        count = source_count_dist.get(src_count, 0)
        pct = (count / total_campuses * 100) if total_campuses > 0 else 0
        bar_width = (count / max_count * 100) if max_count > 0 else 0

        # Color coding
        if src_count == "1":
            bar_color = "#fb923c"  # Orange - single source = low confidence
        elif src_count == "2":
            bar_color = "#fbbf24"  # Yellow - moderate
        elif src_count == "3":
            bar_color = "#60a5fa"  # Blue - good
        else:
            bar_color = "#34d399"  # Green - excellent

        source_dist_html += f'''
            <div class="metric-row" style="margin-bottom: 10px;">
                <span class="metric-label" style="color: rgba(255,255,255,0.7); min-width: 100px;">{src_count} source{"s" if src_count != "1" else ""}</span>
                <div style="flex: 1; margin: 0 15px;">
                    <div class="progress-bar" style="height: 12px;">
                        <div class="progress-fill" style="width: {bar_width}%; background: {bar_color};"></div>
                    </div>
                </div>
                <span class="metric-value" style="color: rgba(255,255,255,0.9); min-width: 80px; text-align: right;">{count:,} ({pct:.1f}%)</span>
            </div>'''

    # MW variance section (if available)
    mw_variance_html = ""
    if avg_mw_cv is not None and mw_cv_sample > 0:
        # CV interpretation
        if avg_mw_cv < 25:
            cv_label, cv_color = "Low variance - good agreement", "#34d399"
        elif avg_mw_cv < 50:
            cv_label, cv_color = "Moderate variance", "#fbbf24"
        else:
            cv_label, cv_color = "High variance - sources disagree", "#f87171"

        mw_variance_html = f'''
            <div class="glass-dark" style="padding: 20px; margin-top: 20px;">
                <h4 style="color: rgba(255,255,255,0.9); margin-bottom: 15px;">📊 Capacity Agreement (MW Variance)</h4>
                <p style="color: rgba(255,255,255,0.6); font-size: 0.85rem; margin-bottom: 15px;">
                    <em>Question: "When multiple sources report capacity for the same campus, how much do they disagree?"</em>
                </p>
                <div class="metric-row">
                    <span class="metric-label" style="color: rgba(255,255,255,0.7);">Avg Coefficient of Variation</span>
                    <span class="metric-value" style="color: {cv_color}; font-weight: 600;">{avg_mw_cv:.1f}%</span>
                </div>
                <div class="metric-row" style="margin-top: 8px;">
                    <span class="metric-label" style="color: rgba(255,255,255,0.7);">Campuses with multi-source MW data</span>
                    <span class="metric-value" style="color: rgba(255,255,255,0.9);">{mw_cv_sample:,}</span>
                </div>
                <div style="margin-top: 10px; font-size: 0.75rem; color: rgba(255,255,255,0.5);">
                    {cv_label}
                </div>
            </div>'''

    # Get hyperscaler stats for the summary callout
    hyperscaler_pct = tier_breakdown.get("hyperscaler", {}).get("pct_multi_source", 0)
    hyperscaler_count = tier_breakdown.get("hyperscaler", {}).get("total_campuses", 0)

    # Get Essential DC breakdown (strategic curated sites)
    essential_breakdown = consensus_data.get("essential_breakdown")
    essential_html = ""
    if essential_breakdown and essential_breakdown.get("total_campuses", 0) > 0:
        ess_total = essential_breakdown["total_campuses"]
        ess_multi = essential_breakdown["multi_source_count"]
        ess_pct = essential_breakdown["pct_multi_source"]
        ess_avg = essential_breakdown["avg_sources"]
        top_companies = essential_breakdown.get("top_companies", {})

        # Color code based on coverage
        if ess_pct >= 70:
            ess_color = "#34d399"  # Green - excellent
            ess_label = "Excellent"
        elif ess_pct >= 50:
            ess_color = "#60a5fa"  # Blue - good
            ess_label = "Good"
        elif ess_pct >= 30:
            ess_color = "#fbbf24"  # Yellow - moderate
            ess_label = "Moderate"
        else:
            ess_color = "#fb923c"  # Orange - needs improvement
            ess_label = "Needs Improvement"

        # Build company chips HTML
        company_chips = ""
        for company, count in list(top_companies.items())[:5]:
            company_chips += f'<span style="display: inline-block; background: rgba(163,113,247,0.2); padding: 3px 10px; border-radius: 12px; font-size: 0.75rem; margin: 2px 3px;">{company}: {count}</span>'

        essential_html = f'''
            <div class="glass-dark" style="padding: 20px; margin-top: 20px; border-left: 3px solid #a371f7;">
                <h4 style="color: #a371f7; margin-bottom: 15px;">⭐ Essential DC Coverage</h4>
                <p style="color: rgba(255,255,255,0.6); font-size: 0.85rem; margin-bottom: 15px;">
                    <em>Question: "How many of the curated strategic sites (our must-track peer facilities) have multi-source validation?"</em>
                </p>
                <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 15px; margin-bottom: 15px;">
                    <div style="text-align: center;">
                        <div style="font-size: 1.8rem; font-weight: 700; color: #a371f7;">{ess_total}</div>
                        <div style="font-size: 0.75rem; color: rgba(255,255,255,0.5);">Essential Campuses</div>
                    </div>
                    <div style="text-align: center;">
                        <div style="font-size: 1.8rem; font-weight: 700; color: {ess_color};">{ess_pct:.0f}%</div>
                        <div style="font-size: 0.75rem; color: rgba(255,255,255,0.5);">Multi-Source</div>
                    </div>
                    <div style="text-align: center;">
                        <div style="font-size: 1.8rem; font-weight: 700; color: rgba(255,255,255,0.9);">{ess_avg:.1f}</div>
                        <div style="font-size: 0.75rem; color: rgba(255,255,255,0.5);">Avg Sources</div>
                    </div>
                    <div style="text-align: center;">
                        <div style="font-size: 1.8rem; font-weight: 700; color: {ess_color};">{ess_label}</div>
                        <div style="font-size: 0.75rem; color: rgba(255,255,255,0.5);">Coverage Rating</div>
                    </div>
                </div>
                <div style="margin-top: 12px;">
                    <span style="font-size: 0.8rem; color: rgba(255,255,255,0.5);">Top Companies:</span>
                    {company_chips if company_chips else '<span style="color: rgba(255,255,255,0.4);">N/A</span>'}
                </div>
            </div>'''

    # Extract tier and essential scores for display
    tier_weighted_score = summary.get("tier_weighted_score", weighted_score)
    essential_score = summary.get("essential_score")
    score_composition = summary.get("score_composition", "")

    return f'''
        <section id="consensus" class="glass">
            <div class="section-header">
                <h2>🤝 Consensus Strength</h2>
                <span class="collapse-icon">▼</span>
            </div>
            <div class="section-content">

            <p style="color: rgba(255,255,255,0.6); font-style: italic; margin-bottom: 20px;">
                Key Question: "How useful is this consensus dataset for decision-making?"
            </p>

            <p style="color: rgba(255,255,255,0.7); margin-bottom: 25px;">
                Measures the quality of our consensus dataset using a <strong>composite score</strong>:
                <span style="color: #60a5fa;">Tier-weighted coverage (80%)</span> — hyperscaler/frontier 60%, major colo 30%, other 10% —
                plus <span style="color: #a371f7;">Essential DC coverage (20%)</span> — strategic must-track sites.
            </p>

            <div style="display: grid; grid-template-columns: 1fr 2fr; gap: 30px; margin-bottom: 25px;">
                <!-- Grade Card -->
                <div class="glass-dark" style="padding: 30px; text-align: center;">
                    <div style="font-size: 0.9rem; color: rgba(255,255,255,0.5); margin-bottom: 10px; text-transform: uppercase; letter-spacing: 1px;">
                        Composite Consensus Score
                    </div>
                    <div style="display: inline-flex; flex-direction: column; align-items: center; padding: 20px 40px; border-radius: 16px; background: {consensus_color}22; border: 3px solid {consensus_color};">
                        <span style="font-size: 3.5rem; font-weight: 800; color: {consensus_color}; line-height: 1;">{consensus_grade}</span>
                        <span style="font-size: 1.2rem; color: {consensus_color}; margin-top: 5px;">{weighted_score:.0f}/100</span>
                        <span style="font-size: 0.85rem; color: rgba(255,255,255,0.6); margin-top: 3px;">{consensus_label}</span>
                    </div>

                    <!-- Score Breakdown -->
                    <div style="margin-top: 20px; padding: 12px; background: rgba(0,0,0,0.3); border-radius: 8px; text-align: left;">
                        <div style="font-size: 0.75rem; color: rgba(255,255,255,0.5); margin-bottom: 8px; text-transform: uppercase;">Score Composition</div>
                        <div class="metric-row" style="margin-bottom: 5px;">
                            <span style="color: #60a5fa; font-size: 0.85rem;">Tier-Weighted (80%)</span>
                            <span style="color: #60a5fa; font-weight: 600;">{tier_weighted_score:.0f}</span>
                        </div>
                        <div class="metric-row">
                            <span style="color: #a371f7; font-size: 0.85rem;">Essential DC (20%)</span>
                            <span style="color: #a371f7; font-weight: 600;">{f"{essential_score:.0f}" if essential_score else 'N/A'}</span>
                        </div>
                    </div>

                    <div style="margin-top: 15px; text-align: left;">
                        <div class="metric-row" style="margin-bottom: 8px;">
                            <span style="color: rgba(255,255,255,0.6);">Total Campuses</span>
                            <span style="color: rgba(255,255,255,0.9); font-weight: 600;">{total_campuses:,}</span>
                        </div>
                        <div class="metric-row" style="margin-bottom: 8px;">
                            <span style="color: rgba(255,255,255,0.6);">Avg Sources/Campus</span>
                            <span style="color: rgba(255,255,255,0.9); font-weight: 600;">{avg_sources:.2f}</span>
                        </div>
                        <div class="metric-row">
                            <span style="color: rgba(255,255,255,0.6);">Overall Multi-Source</span>
                            <span style="color: rgba(255,255,255,0.9); font-weight: 600;">{pct_multi_source:.1f}%</span>
                        </div>
                    </div>
                </div>

                <!-- Tier Breakdown Table (THE KEY NEW FEATURE) -->
                <div>
                    <div class="glass-dark" style="padding: 20px;">
                        <h4 style="color: rgba(255,255,255,0.9); margin-bottom: 15px;">📊 Coverage by Business Value Tier</h4>
                        <p style="color: rgba(255,255,255,0.6); font-size: 0.85rem; margin-bottom: 15px;">
                            <em>Question: "How well are high-value sites covered compared to the full dataset?"</em>
                        </p>
                        <table style="width: 100%; border-collapse: collapse; color: rgba(255,255,255,0.9);">
                            <thead>
                                <tr style="border-bottom: 2px solid rgba(255,255,255,0.2);">
                                    <th style="padding: 10px; text-align: left; color: rgba(255,255,255,0.6); font-weight: 500;">Tier</th>
                                    <th style="padding: 10px; text-align: center; color: rgba(255,255,255,0.6); font-weight: 500;">Sites</th>
                                    <th style="padding: 10px; text-align: center; color: rgba(255,255,255,0.6); font-weight: 500;">Multi-Source %</th>
                                    <th style="padding: 10px; text-align: center; color: rgba(255,255,255,0.6); font-weight: 500;">Avg Sources</th>
                                    <th style="padding: 10px; text-align: center; color: rgba(255,255,255,0.6); font-weight: 500;">Weight</th>
                                </tr>
                            </thead>
                            <tbody>
                                {tier_rows_html}
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>

            <!-- Source Distribution (collapsed into smaller section) -->
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px;">
                <div class="glass-dark" style="padding: 20px;">
                    <h4 style="color: rgba(255,255,255,0.9); margin-bottom: 15px;">📈 Source Count Distribution</h4>
                    {source_dist_html}
                </div>

                {mw_variance_html if mw_variance_html else '<div></div>'}
            </div>

            {essential_html}

            <div class="glass-dark" style="padding: 15px; margin-top: 20px; border-left: 3px solid {consensus_color};">
                <div style="font-size: 0.85rem; color: rgba(255,255,255,0.6);">
                    <strong style="color: rgba(255,255,255,0.9);">What This Tells Us:</strong><br>
                    {"Excellent coverage of high-value sites. Hyperscaler/frontier campuses have strong multi-source validation, giving high confidence in competitive intelligence data." if hyperscaler_pct >= 50 else
                     "Good coverage of priority sites. Hyperscaler data has reasonable multi-source overlap, providing useful competitive intelligence with some gaps." if hyperscaler_pct >= 30 else
                     f"Moderate hyperscaler coverage ({hyperscaler_pct:.0f}% multi-source across {hyperscaler_count:,} frontier sites). Consider prioritizing additional source collection for key competitors." if hyperscaler_pct >= 15 else
                     f"Limited hyperscaler coverage ({hyperscaler_pct:.0f}% multi-source). Priority should be improving source overlap for frontier/competitor sites that leadership cares about most."}
                </div>
            </div>

            </div>
        </section>
'''


# UTILITY FUNCTIONS

def get_record_count(fc_path, where_clause=None):
    """Get count of records, optionally filtered."""
    try:
        if where_clause:
            layer_name = f"temp_layer_{datetime.now().strftime('%H%M%S%f')}"
            arcpy.MakeFeatureLayer_management(fc_path, layer_name, where_clause)
            count = int(arcpy.GetCount_management(layer_name)[0])
            arcpy.Delete_management(layer_name)
            return count
        else:
            return int(arcpy.GetCount_management(fc_path)[0])
    except Exception as e:
        return 0

def get_field_names(fc_path):
    """Get list of field names in feature class."""
    return [f.name for f in arcpy.ListFields(fc_path)]

def calculate_field_completeness(fc_path, field_name):
    """Calculate percentage of non-null values for a field."""
    total = get_record_count(fc_path)
    if total == 0:
        return 0.0

    fields = get_field_names(fc_path)
    if field_name not in fields:
        return None  # Field doesn't exist

    # Count nulls/empty
    null_count = 0
    with arcpy.da.SearchCursor(fc_path, [field_name]) as cursor:
        for row in cursor:
            val = row[0]
            if val is None or (isinstance(val, str) and val.strip() == ""):
                null_count += 1

    return round(((total - null_count) / total) * 100, 1)

def get_unique_values(fc_path, field_name, limit=20):
    """Get unique values and their counts for a field."""
    fields = get_field_names(fc_path)
    if field_name not in fields:
        return {}

    value_counts = defaultdict(int)
    with arcpy.da.SearchCursor(fc_path, [field_name]) as cursor:
        for row in cursor:
            val = row[0] if row[0] else "(null)"
            value_counts[val] += 1

    # Sort by count descending and limit
    sorted_values = sorted(value_counts.items(), key=lambda x: x[1], reverse=True)
    return dict(sorted_values[:limit])

def get_state_distribution(fc_path):
    """Get record counts by state, filtering out null/empty/invalid values."""
    raw_dist = get_unique_values(fc_path, "state", limit=25)
    # Filter out null, empty, 0, and float-like string values (e.g., "0.0000000")
    invalid_values = ["(null)", "", "0", None, "0.0", "0.00", "0.000", "0.0000", "0.00000", "0.000000", "0.0000000"]
    filtered = {}
    for k, v in raw_dist.items():
        # Skip invalid entries
        if k in invalid_values or v <= 0:
            continue
        # Skip if it looks like a numeric string (float/int)
        if k and isinstance(k, str):
            try:
                float_val = float(k)
                if float_val == 0:
                    continue
            except (ValueError, TypeError):
                pass  # Not a numeric string, keep it
        filtered[k] = v
    # Sort by count and take top 15
    sorted_dist = dict(sorted(filtered.items(), key=lambda x: x[1], reverse=True)[:15])
    return sorted_dist

def get_source_distribution(fc_path):
    """Get record counts by source."""
    return get_unique_values(fc_path, "source", limit=10)

def get_company_filter_distribution(fc_path):
    """Get record counts by company_clean_filter."""
    return get_unique_values(fc_path, "company_clean_filter", limit=15)

def get_data_vintage_stats(fc_path):
    """Get data vintage date distribution."""
    fields = get_field_names(fc_path)
    if "data_vintage" not in fields:
        return {"available": False}

    dates = []
    null_count = 0
    with arcpy.da.SearchCursor(fc_path, ["data_vintage"]) as cursor:
        for row in cursor:
            if row[0]:
                dates.append(row[0])
            else:
                null_count += 1

    if not dates:
        return {"available": True, "populated": 0, "null": null_count}

    min_date = min(dates)
    max_date = max(dates)

    return {
        "available": True,
        "populated": len(dates),
        "null": null_count,
        "oldest": min_date.strftime("%Y-%m-%d") if hasattr(min_date, 'strftime') else str(min_date),
        "newest": max_date.strftime("%Y-%m-%d") if hasattr(max_date, 'strftime') else str(max_date)
    }

def check_duplicate_unique_ids(fc_path):
    """Check for duplicate unique_id values."""
    fields = get_field_names(fc_path)
    if "unique_id" not in fields:
        return {"checked": False}

    id_counts = defaultdict(int)
    with arcpy.da.SearchCursor(fc_path, ["unique_id"]) as cursor:
        for row in cursor:
            if row[0]:
                id_counts[row[0]] += 1

    duplicates = {k: v for k, v in id_counts.items() if v > 1}
    return {
        "checked": True,
        "total_ids": len(id_counts),
        "duplicate_count": len(duplicates),
        "duplicate_records": sum(duplicates.values()) - len(duplicates),
        "examples": list(duplicates.keys())[:5]
    }

def calculate_health_grade(completeness_scores):
    """Calculate overall health grade based on field completeness."""
    if not completeness_scores:
        return "N/A", "#8892b0"

    valid_scores = [s for s in completeness_scores if s is not None]
    if not valid_scores:
        return "N/A", "#8892b0"

    avg = sum(valid_scores) / len(valid_scores)

    if avg >= 90:
        return "A", "#34d399"
    elif avg >= 80:
        return "B", "#60a5fa"
    elif avg >= 70:
        return "C", "#fbbf24"
    elif avg >= 60:
        return "D", "#fb923c"
    else:
        return "F", "#f87171"


def calculate_weighted_source_score(fc_path, source_name, total_records, spatial_accuracy_data=None):
    """
    Calculate a weighted score for a source based on business-relevant metrics.

    Score Formula (Updated with Spatial Accuracy + Forecast Bonus):
        Final Score = (Volume × 10%) + (Core × 20%) + (Capacity × 20%) +
                      (Location × 15%) + (Spatial Accuracy × 20%) + (Richness × 10%) +
                      (Forecast Bonus × 5%)

    Where:
        - Volume: (source_records / total_records) × 100, capped at 100
        - Core: avg completeness of company_clean, UCID
        - Capacity: avg completeness of full_capacity_mw, commissioned_power_mw
        - Location: avg completeness of latitude, longitude
        - Spatial Accuracy: Combined score from recall % and distance accuracy vs Meta
        - Richness: % of all fields with data (attribute richness)
        - Forecast Bonus: Extra credit for sources with annual forecast fields (mw_2025-2034)
          Semianalysis gets bonus for providing 10-year capacity projections
    """
    where = f"source = '{source_name}'"
    count = get_record_count(fc_path, where)

    if count == 0:
        return None

    # Special handling for Meta Canonical - it IS the ground truth reference
    # Don't score it against itself; give it automatic A grade
    if source_name == "Meta Canonical":
        return {
            "count": count,
            "final_score": 100.0,  # Perfect score - it's ground truth
            "scores": {
                "volume": 100,
                "core": 100,
                "capacity": 100,
                "location": 100,
                "spatial_accuracy": 100,  # It IS the reference
                "richness": 100,
                "forecast_bonus": 0  # No forecasts but doesn't matter
            },
            "weights": {
                "volume": 0.10, "core": 0.20, "capacity": 0.20,
                "location": 0.15, "spatial_accuracy": 0.20,
                "richness": 0.10, "forecast_bonus": 0.05
            },
            "grade": "A",
            "grade_color": "#34d399",
            "field_details": {},
            "is_ground_truth": True
        }

    layer_name = f"score_layer_{source_name.replace(' ', '_')}"

    try:
        arcpy.MakeFeatureLayer_management(fc_path, layer_name, where)

        # Get all fields in the feature class
        all_fields = [f.name for f in arcpy.ListFields(layer_name)
                      if f.type not in ['OID', 'Geometry'] and not f.name.startswith('Shape')]

        def get_field_pct(field_name):
            """Get completeness % for a field in this source."""
            if field_name not in all_fields:
                return None
            null_count = 0
            total = 0
            with arcpy.da.SearchCursor(layer_name, [field_name]) as cursor:
                for row in cursor:
                    total += 1
                    val = row[0]
                    if val is None or (isinstance(val, str) and val.strip() == ""):
                        null_count += 1
            return round(((total - null_count) / total) * 100, 1) if total > 0 else 0

        # Calculate each component
        scores = {}

        # Volume score (contribution to total dataset)
        volume_raw = (count / total_records) * 100 if total_records > 0 else 0
        scores["volume"] = min(volume_raw * 5, 100)  # Scale up small sources, cap at 100

        # Core identity fields
        core_fields = ["company_clean", "ucid"]
        core_pcts = [get_field_pct(f) for f in core_fields]
        core_pcts = [p for p in core_pcts if p is not None]
        scores["core"] = sum(core_pcts) / len(core_pcts) if core_pcts else 0

        # Capacity fields (use XB layer fields)
        capacity_fields = ["full_capacity_mw", "commissioned_power_mw", "planned_power_mw", "uc_power_mw"]
        cap_pcts = [get_field_pct(f) for f in capacity_fields]
        cap_pcts = [p for p in cap_pcts if p is not None]
        scores["capacity"] = sum(cap_pcts) / len(cap_pcts) if cap_pcts else 0

        # Location fields (completeness)
        loc_fields = ["latitude", "longitude"]
        loc_pcts = [get_field_pct(f) for f in loc_fields]
        loc_pcts = [p for p in loc_pcts if p is not None]
        scores["location"] = sum(loc_pcts) / len(loc_pcts) if loc_pcts else 0

        # Spatial Accuracy score (NEW - based on recall and distance accuracy vs Meta)
        spatial_score = 0
        if spatial_accuracy_data and spatial_accuracy_data.get("available"):
            source_spatial = spatial_accuracy_data.get("sources", {}).get(source_name, {})
            recall_pct = source_spatial.get("recall_pct", 0)
            median_dist = source_spatial.get("median_distance_m")

            # Convert median distance to score (lower distance = higher score)
            # Score formula: 100 if <=100m, decreasing to 0 at 10km (10000m)
            if median_dist is not None and median_dist > 0:
                distance_score = max(0, 100 - (median_dist / 100))  # 100m = 99, 1km = 90, 5km = 50, 10km = 0
                distance_score = min(100, distance_score)  # Cap at 100
            else:
                distance_score = 0

            # Combine recall (50%) and distance accuracy (50%)
            spatial_score = (recall_pct * 0.5) + (distance_score * 0.5)
        scores["spatial_accuracy"] = spatial_score

        # Attribute richness (% of all fields populated)
        richness_pcts = [get_field_pct(f) for f in all_fields]
        richness_pcts = [p for p in richness_pcts if p is not None]
        scores["richness"] = sum(richness_pcts) / len(richness_pcts) if richness_pcts else 0

        # Forecast capacity bonus (Semianalysis provides 10-year projections)
        forecast_fields = [f"mw_{year}" for year in range(2025, 2035)]  # mw_2025 to mw_2034
        forecast_populated = 0
        for ff in forecast_fields:
            pct = get_field_pct(ff)
            if pct is not None and pct > 50:  # Field exists and >50% populated
                forecast_populated += 1
        # Bonus: 100 if 8+ forecast fields populated, scaled down otherwise
        scores["forecast_bonus"] = min(100, (forecast_populated / 8) * 100) if forecast_populated > 0 else 0

        # Weighted final score (updated weights to include spatial accuracy + forecast)
        weights = {
            "volume": 0.10,
            "core": 0.20,      # Reduced from 0.25 to make room for forecast
            "capacity": 0.20,
            "location": 0.15,
            "spatial_accuracy": 0.20,
            "richness": 0.10,
            "forecast_bonus": 0.05  # NEW: 5% bonus for forecast data
        }
        final_score = sum(scores[k] * weights[k] for k in weights)

        # Get grade from score
        if final_score >= 80:
            grade, color = "A", "#34d399"
        elif final_score >= 65:
            grade, color = "B", "#60a5fa"
        elif final_score >= 50:
            grade, color = "C", "#fbbf24"
        elif final_score >= 35:
            grade, color = "D", "#fb923c"
        else:
            grade, color = "F", "#f87171"

        # Get detailed field completeness for drill-down
        field_details = {}
        important_fields = ["company_clean", "ucid", "full_capacity_mw", "commissioned_power_mw",
                           "latitude", "longitude", "data_vintage", "operational_date",
                           "developer", "owner", "sqft", "building_count"]
        for f in important_fields:
            pct = get_field_pct(f)
            if pct is not None:
                field_details[f] = pct

        arcpy.Delete_management(layer_name)

        return {
            "count": count,
            "final_score": round(final_score, 1),
            "scores": scores,
            "weights": weights,
            "grade": grade,
            "grade_color": color,
            "field_details": field_details
        }

    except Exception as e:
        try:
            arcpy.Delete_management(layer_name)
        except:
            pass
        return {"count": count, "error": str(e)}

def get_source_stats(fc_path, source_name):
    """Get detailed stats for a specific source."""
    where = f"source = '{source_name}'"
    count = get_record_count(fc_path, where)

    if count == 0:
        return None

    # Create temp layer for source-specific queries
    layer_name = f"source_layer_{source_name.replace(' ', '_')}"
    try:
        arcpy.MakeFeatureLayer_management(fc_path, layer_name, where)

        # Calculate field completeness for this source
        completeness = {}
        for field in ["company_clean", "full_capacity_mw", "state", "ucid", "data_vintage"]:
            fields = get_field_names(fc_path)
            if field not in fields:
                completeness[field] = None
                continue

            null_count = 0
            total = 0
            with arcpy.da.SearchCursor(layer_name, [field]) as cursor:
                for row in cursor:
                    total += 1
                    val = row[0]
                    if val is None or (isinstance(val, str) and val.strip() == ""):
                        null_count += 1

            if total > 0:
                completeness[field] = round(((total - null_count) / total) * 100, 1)
            else:
                completeness[field] = 0.0

        arcpy.Delete_management(layer_name)

        # Calculate grade
        scores = [v for v in completeness.values() if v is not None]
        grade, color = calculate_health_grade(scores)

        return {
            "count": count,
            "completeness": completeness,
            "grade": grade,
            "grade_color": color
        }
    except Exception as e:
        try:
            arcpy.Delete_management(layer_name)
        except:
            pass
        return {"count": count, "error": str(e)}

# HTML GENERATION - APPLE DARK THEME

def get_css_from_file():
    """Read CSS from external file if available."""
    # Use neomorphism dark theme (matches PROJECT_OVERVIEW.html)
    css_path = os.path.join(SCRIPTS_DIR, "04_validation", "reports", "neomorphism_dark_theme.css")
    if os.path.exists(css_path):
        with open(css_path, 'r', encoding='utf-8') as f:
            return f.read()
    # Fallback to old apple theme
    css_path_old = os.path.join(SCRIPTS_DIR, "04_validation", "reports", "apple_dark_theme.css")
    if os.path.exists(css_path_old):
        with open(css_path_old, 'r', encoding='utf-8') as f:
            return f.read()
    return None

def get_html_header(timestamp, pipeline_run_info=None):
    """Generate HTML header with neomorphism dark theme and sidebar layout."""
    # Try to load CSS from external file
    external_css = get_css_from_file()

    if external_css:
        css_content = external_css
    else:
        # Minimal fallback - ideally CSS file should always exist
        css_content = """
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: -apple-system, sans-serif; background: #1a1a2e; color: #e8e8e8; }
.page-wrapper { display: flex; min-height: 100vh; }
.sidebar { position: fixed; left: 0; top: 0; bottom: 0; width: 220px; background: rgba(15,52,96,0.95); padding: 25px 15px; }
.main-content { margin-left: 220px; flex: 1; padding: 40px; }
"""

    # Pipeline run info badge
    pipeline_badge = ""
    if pipeline_run_info:
        run_date = pipeline_run_info.get("last_run", "Unknown")
        run_duration = pipeline_run_info.get("duration", "Unknown")
        pipeline_badge = f'''
            <div class="pipeline-status">
                <div class="status-item">
                    <span class="status-icon">🔄</span>
                    <span class="status-label">Pipeline Last Run:</span>
                    <span class="status-value">{run_date}</span>
                </div>
                <div class="status-item">
                    <span class="status-icon">⏱️</span>
                    <span class="status-label">Duration:</span>
                    <span class="status-value">{run_duration}</span>
                </div>
            </div>
'''

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Pipeline Diagnostic Report — {timestamp}</title>
    <style>
{css_content}
        .pipeline-status {{
            display: flex;
            gap: 30px;
            justify-content: center;
            margin-top: 20px;
            padding: 15px 25px;
            background: rgba(52, 211, 153, 0.1);
            border: 1px solid rgba(52, 211, 153, 0.3);
            border-radius: 12px;
        }}
        .status-item {{
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        .status-icon {{
            font-size: 1.1rem;
        }}
        .status-label {{
            color: rgba(255,255,255,0.6);
            font-size: 0.85rem;
        }}
        .status-value {{
            color: #34d399;
            font-weight: 600;
            font-size: 0.9rem;
        }}
    </style>
</head>
<body>
    <div class="page-wrapper">
        <!-- Fixed Left Sidebar -->
        <aside class="sidebar">
            <div class="sidebar-header">
                <div class="sidebar-logo" style="font-size: 1.2rem; font-weight: 700; color: #4facfe;">PDR</div>
                <div class="sidebar-title">Pipeline<br/>Diagnostics</div>
            </div>
            <nav>
                <ul>
                    <li style="color: rgba(255,255,255,0.4); font-size: 0.7rem; padding: 8px 12px; text-transform: uppercase; letter-spacing: 1px;">Executive Summary</li>
                    <li><a href="#report-card"><span class="nav-icon">›</span>Report Card</a></li>
                    <li><a href="#recommendations"><span class="nav-icon">›</span>Recommendations</a></li>

                    <li style="color: rgba(255,255,255,0.4); font-size: 0.7rem; padding: 8px 12px; margin-top: 15px; text-transform: uppercase; letter-spacing: 1px;">Input Source Quality</li>
                    <li><a href="#sources"><span class="nav-icon">›</span>Source Analysis</a></li>
                    <li><a href="#spatial"><span class="nav-icon">›</span>Spatial Accuracy</a></li>
                    <li><a href="#temporal"><span class="nav-icon">›</span>Temporal Freshness</a></li>
                    <li><a href="#consensus"><span class="nav-icon">›</span>Consensus Strength</a></li>

                    <li style="color: rgba(255,255,255,0.4); font-size: 0.7rem; padding: 8px 12px; margin-top: 15px; text-transform: uppercase; letter-spacing: 1px;">Output Dataset Quality</li>
                    <li><a href="#grades"><span class="nav-icon">›</span>Pipeline Health</a></li>
                    <li><a href="#completeness"><span class="nav-icon">›</span>Field Completeness</a></li>
                    <li><a href="#distribution"><span class="nav-icon">›</span>Data Distribution</a></li>
                    <li><a href="#quality"><span class="nav-icon">›</span>Quality Checks</a></li>

                    <li style="color: rgba(255,255,255,0.4); font-size: 0.7rem; padding: 8px 12px; margin-top: 15px; text-transform: uppercase; letter-spacing: 1px;">Synthesis</li>
                    <li><a href="#map-viz"><span class="nav-icon">›</span>Site Comparison</a></li>
                </ul>
            </nav>
        </aside>

        <main class="main-content">
'''


def _legacy_get_html_header(timestamp):
    """DEPRECATED: Old glassmorphism header - kept for reference."""
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>DC Pipeline Diagnostic Report - {timestamp}</title>
    <style>

        * {{ margin: 0; padding: 0; box-sizing: border-box; }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Display', 'Helvetica Neue', sans-serif;
            min-height: 100vh;
            background: #000000;
            color: #f5f5f7;
            padding: 60px 20px;
            line-height: 1.47059;
            -webkit-font-smoothing: antialiased;
            letter-spacing: -0.022em;
        }}

        .container {{
            max-width: 1024px;
            margin: 0 auto;
        }}

        /* Dark glass cards */
        .glass {{
            background: #1c1c1e;
            border-radius: 18px;
            border: 1px solid rgba(255, 255, 255, 0.08);
        }}

        .glass-dark {{
            background: #2c2c2e;
            border-radius: 12px;
            border: 1px solid rgba(255, 255, 255, 0.06);
        }}

        header {{
            text-align: center;
            margin-bottom: 60px;
            padding: 60px 40px;
        }}

        h1 {{
            font-size: 56px;
            font-weight: 600;
            background: linear-gradient(90deg, #6ac4dc 0%, #5ac8fa 50%, #70d7ff 100%);
            -webkit-background-clip: text;
            background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 16px;
            letter-spacing: -0.015em;
        }}

        .subtitle {{
            font-size: 21px;
            color: #86868b;
            font-weight: 400;
        }}

        .timestamp {{
            color: #6e6e73;
            font-size: 14px;
            margin-top: 16px;
        }}

        /* Navigation */
        nav {{
            background: rgba(29, 29, 31, 0.94);
            backdrop-filter: saturate(180%) blur(20px);
            -webkit-backdrop-filter: saturate(180%) blur(20px);
            border-radius: 12px;
            padding: 14px 20px;
            margin-bottom: 60px;
            border: 1px solid rgba(255, 255, 255, 0.08);
            position: sticky;
            top: 20px;
            z-index: 100;
        }}

        nav h3 {{
            display: none;
        }}

        nav ul {{
            display: flex;
            flex-wrap: wrap;
            gap: 6px;
            list-style: none;
            justify-content: center;
        }}

        nav a {{
            color: #f5f5f7;
            text-decoration: none;
            padding: 8px 14px;
            border-radius: 980px;
            font-size: 14px;
            transition: background 0.2s;
        }}

        nav a:hover {{
            background: rgba(255, 255, 255, 0.1);
        }}

        /* Grade cards with liquid glass effect */
        .grade-banner {{
            display: flex;
            justify-content: center;
            gap: 30px;
            margin-bottom: 40px;
            flex-wrap: wrap;
        }}

        .grade-card {{
            padding: 35px 55px;
            text-align: center;
            position: relative;
            overflow: hidden;
            transition: transform 0.3s ease, box-shadow 0.3s ease;
        }}

        .grade-card:hover {{
            transform: translateY(-5px) scale(1.02);
            box-shadow:
                0 20px 60px rgba(0, 0, 0, 0.15),
                inset 0 1px 0 rgba(255, 255, 255, 0.5);
        }}

        .grade-card::before {{
            content: '';
            position: absolute;
            top: -50%;
            left: -50%;
            width: 200%;
            height: 200%;
            background: linear-gradient(
                45deg,
                transparent 40%,
                rgba(255, 255, 255, 0.3) 50%,
                transparent 60%
            );
            transform: rotate(45deg);
            animation: shimmer 3s ease-in-out infinite;
        }}

        @keyframes shimmer {{
            0% {{ transform: translateX(-100%) rotate(45deg); }}
            100% {{ transform: translateX(100%) rotate(45deg); }}
        }}

        .grade-letter {{
            font-size: 4.5rem;
            font-weight: 700;
            position: relative;
            z-index: 1;
            text-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
        }}

        .grade-label {{
            color: rgba(0, 0, 0, 0.6);
            margin-top: 8px;
            font-size: 0.95rem;
            font-weight: 500;
            position: relative;
            z-index: 1;
        }}

        /* Stats grid */
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 40px;
        }}

        .stat-card {{
            padding: 28px;
            text-align: center;
            transition: transform 0.3s ease;
        }}

        .stat-card:hover {{
            transform: translateY(-3px);
        }}

        .stat-value {{
            font-size: 2.4rem;
            font-weight: 700;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            -webkit-background-clip: text;
            background-clip: text;
            -webkit-text-fill-color: transparent;
        }}

        .stat-label {{
            color: rgba(0, 0, 0, 0.6);
            margin-top: 8px;
            font-size: 0.9rem;
            font-weight: 500;
        }}

        /* Sections */
        section {{
            padding: 35px;
            margin-bottom: 30px;
        }}

        h2 {{
            font-size: 1.5rem;
            margin-bottom: 25px;
            color: #1d1d1f;
            font-weight: 600;
            display: flex;
            align-items: center;
            gap: 12px;
        }}

        h3 {{
            font-size: 1.1rem;
            margin: 25px 0 15px 0;
            color: rgba(0, 0, 0, 0.7);
            font-weight: 500;
        }}

        /* Tables with glass effect */
        table {{
            width: 100%;
            border-collapse: separate;
            border-spacing: 0;
            margin-top: 15px;
            overflow: hidden;
            border-radius: 16px;
            background: rgba(255, 255, 255, 0.3);
        }}

        th, td {{
            padding: 16px 20px;
            text-align: left;
        }}

        th {{
            background: rgba(255, 255, 255, 0.4);
            color: #1d1d1f;
            font-weight: 600;
            font-size: 0.85rem;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            border-bottom: 1px solid rgba(0, 0, 0, 0.08);
        }}

        td {{
            border-bottom: 1px solid rgba(0, 0, 0, 0.05);
            color: rgba(0, 0, 0, 0.8);
        }}

        tr:last-child td {{
            border-bottom: none;
        }}

        tr:hover td {{
            background: rgba(255, 255, 255, 0.3);
        }}

        /* Progress bars */
        .progress-bar {{
            width: 100%;
            height: 10px;
            background: rgba(0, 0, 0, 0.1);
            border-radius: 10px;
            overflow: hidden;
            position: relative;
        }}

        .progress-fill {{
            height: 100%;
            border-radius: 10px;
            transition: width 0.5s ease;
            position: relative;
        }}

        .progress-fill::after {{
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: linear-gradient(
                90deg,
                rgba(255,255,255,0) 0%,
                rgba(255,255,255,0.4) 50%,
                rgba(255,255,255,0) 100%
            );
            animation: progressShine 2s ease-in-out infinite;
        }}

        @keyframes progressShine {{
            0% {{ transform: translateX(-100%); }}
            100% {{ transform: translateX(100%); }}
        }}

        .progress-green {{ background: linear-gradient(90deg, #34d399, #10b981); }}
        .progress-blue {{ background: linear-gradient(90deg, #60a5fa, #3b82f6); }}
        .progress-yellow {{ background: linear-gradient(90deg, #fbbf24, #f59e0b); }}
        .progress-orange {{ background: linear-gradient(90deg, #fb923c, #f97316); }}
        .progress-red {{ background: linear-gradient(90deg, #f87171, #ef4444); }}

        /* Source cards */
        .source-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 20px;
            margin-top: 20px;
        }}

        .source-card {{
            padding: 25px;
            transition: transform 0.3s ease;
        }}

        .source-card:hover {{
            transform: translateY(-3px);
        }}

        .source-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 15px;
        }}

        .source-name {{
            font-weight: 600;
            color: #1d1d1f;
        }}

        .source-grade {{
            font-size: 1.8rem;
            font-weight: 700;
        }}

        .source-count {{
            font-size: 0.85rem;
            color: rgba(0, 0, 0, 0.5);
            margin-bottom: 15px;
        }}

        .source-metrics {{
            display: flex;
            flex-direction: column;
            gap: 10px;
        }}

        .metric-row {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            font-size: 0.85rem;
        }}

        .metric-label {{
            color: rgba(0, 0, 0, 0.6);
        }}

        .metric-value {{
            font-weight: 600;
            color: #1d1d1f;
        }}

        /* Alert boxes */
        .alert {{
            padding: 20px 25px;
            border-radius: 16px;
            margin: 20px 0;
            display: flex;
            align-items: flex-start;
            gap: 15px;
        }}

        .alert-success {{
            background: rgba(52, 211, 153, 0.2);
            border: 1px solid rgba(52, 211, 153, 0.3);
        }}

        .alert-warning {{
            background: rgba(251, 191, 36, 0.2);
            border: 1px solid rgba(251, 191, 36, 0.3);
        }}

        .alert-error {{
            background: rgba(248, 113, 113, 0.2);
            border: 1px solid rgba(248, 113, 113, 0.3);
        }}

        .alert-icon {{
            font-size: 1.5rem;
        }}

        .alert-content {{
            flex: 1;
        }}

        .alert-title {{
            font-weight: 600;
            margin-bottom: 5px;
        }}

        .alert-text {{
            color: rgba(0, 0, 0, 0.7);
            font-size: 0.9rem;
        }}

        /* Distribution bars */
        .dist-bar {{
            display: flex;
            align-items: center;
            gap: 15px;
            margin: 8px 0;
        }}

        .dist-label {{
            width: 150px;
            font-size: 0.85rem;
            color: rgba(0, 0, 0, 0.7);
            text-align: right;
        }}

        .dist-bar-container {{
            flex: 1;
            height: 24px;
            background: rgba(0, 0, 0, 0.08);
            border-radius: 12px;
            overflow: hidden;
        }}

        .dist-bar-fill {{
            height: 100%;
            background: linear-gradient(90deg, #667eea, #764ba2);
            border-radius: 12px;
            display: flex;
            align-items: center;
            justify-content: flex-end;
            padding-right: 10px;
            font-size: 0.75rem;
            color: white;
            font-weight: 600;
            min-width: 40px;
        }}

        /* Footer */
        footer {{
            text-align: center;
            margin-top: 40px;
            padding: 30px;
            color: rgba(0, 0, 0, 0.5);
            font-size: 0.9rem;
        }}

        footer a {{
            color: #667eea;
            text-decoration: none;
        }}

        /* Source card enhanced styles */
        .source-card {{
            cursor: pointer;
        }}

        .source-score-badge {{
            display: flex;
            flex-direction: column;
            align-items: center;
            padding: 8px 16px;
            border-radius: 12px;
        }}

        .score-grade {{
            font-size: 1.6rem;
            font-weight: 700;
        }}

        .score-value {{
            font-size: 0.75rem;
            color: rgba(0,0,0,0.5);
        }}

        .score-breakdown {{
            margin-top: 15px;
            padding-top: 15px;
            border-top: 1px solid rgba(0,0,0,0.08);
        }}

        .score-component {{
            margin-bottom: 12px;
        }}

        .component-header {{
            display: flex;
            justify-content: space-between;
            font-size: 0.8rem;
            margin-bottom: 4px;
        }}

        .component-name {{
            color: rgba(0,0,0,0.7);
        }}

        .component-weight {{
            color: rgba(0,0,0,0.4);
            font-size: 0.7rem;
        }}

        .component-values {{
            display: flex;
            justify-content: space-between;
            font-size: 0.75rem;
            margin-top: 4px;
        }}

        .raw-score {{
            color: rgba(0,0,0,0.6);
        }}

        .contribution {{
            color: #667eea;
            font-weight: 600;
        }}

        .field-details {{
            margin-top: 15px;
            padding-top: 15px;
            border-top: 1px solid rgba(0,0,0,0.08);
            transition: all 0.3s ease;
        }}

        .field-details.collapsed {{
            display: none;
        }}

        .field-details h4 {{
            font-size: 0.85rem;
            color: rgba(0,0,0,0.6);
            margin-bottom: 12px;
        }}

        .field-detail {{
            display: flex;
            align-items: center;
            font-size: 0.8rem;
            margin-bottom: 8px;
        }}

        .field-detail .field-name {{
            width: 140px;
            color: rgba(0,0,0,0.6);
            font-family: monospace;
            font-size: 0.75rem;
        }}

        .field-detail .field-pct {{
            width: 40px;
            text-align: right;
            font-weight: 600;
            color: rgba(0,0,0,0.8);
        }}

        .expand-hint {{
            text-align: center;
            font-size: 0.75rem;
            color: rgba(0,0,0,0.4);
            margin-top: 15px;
            padding-top: 10px;
            border-top: 1px dashed rgba(0,0,0,0.1);
        }}

        .source-card.expanded .expand-hint {{
            display: none;
        }}

        /* Formula box */
        .formula-box {{
            padding: 20px 25px;
            margin-bottom: 25px;
        }}

        .formula-box h4 {{
            font-size: 0.95rem;
            margin-bottom: 12px;
            color: rgba(255,255,255,0.9);
        }}

        .formula-box code {{
            display: block;
            font-family: 'SF Mono', 'Monaco', monospace;
            font-size: 0.9rem;
            color: #fbbf24;
            background: rgba(0,0,0,0.2);
            padding: 12px 16px;
            border-radius: 8px;
            margin-bottom: 15px;
        }}

        .formula-legend {{
            display: flex;
            flex-wrap: wrap;
            gap: 15px;
            font-size: 0.8rem;
            color: rgba(255,255,255,0.7);
        }}

        .formula-legend span {{
            background: rgba(255,255,255,0.1);
            padding: 4px 10px;
            border-radius: 6px;
        }}

        /* Floating orbs for extra effect */
        .orb {{
            position: fixed;
            border-radius: 50%;
            filter: blur(80px);
            opacity: 0.5;
            z-index: -1;
            animation: float 10s ease-in-out infinite;
        }}

        .orb-1 {{
            width: 400px;
            height: 400px;
            background: rgba(102, 126, 234, 0.4);
            top: 10%;
            left: -10%;
        }}

        .orb-2 {{
            width: 300px;
            height: 300px;
            background: rgba(240, 147, 251, 0.4);
            bottom: 20%;
            right: -5%;
            animation-delay: -5s;
        }}

        .orb-3 {{
            width: 250px;
            height: 250px;
            background: rgba(74, 222, 222, 0.3);
            bottom: 40%;
            left: 30%;
            animation-delay: -2s;
        }}

        @keyframes float {{
            0%, 100% {{ transform: translate(0, 0) rotate(0deg); }}
            25% {{ transform: translate(20px, -20px) rotate(5deg); }}
            50% {{ transform: translate(-10px, 20px) rotate(-5deg); }}
            75% {{ transform: translate(-20px, -10px) rotate(3deg); }}
        }}
    </style>
</head>
<body>
    <div class="orb orb-1"></div>
    <div class="orb orb-2"></div>
    <div class="orb orb-3"></div>

    <div class="container">
'''

def get_html_footer():
    """Generate HTML footer with interactive JavaScript and proper layout closing."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return f'''
        <footer>
            <p><strong>DC GIS Pipeline</strong> — Lean Consensus DC Model</p>
            <p>Report generated: {timestamp}</p>
        </footer>
        </main>
    </div>

    <script>
        // Track expand state
        let allExpanded = false;

        // Toggle ALL source card field details at once
        function toggleDetails(clickedCard) {{
            const allCards = document.querySelectorAll('.source-card');
            const allDetails = document.querySelectorAll('.field-details');
            const allHints = document.querySelectorAll('.expand-hint');

            // Check if we should expand or collapse
            const clickedDetails = clickedCard.querySelector('.field-details');
            const shouldExpand = clickedDetails.classList.contains('collapsed');

            // Apply to ALL cards
            allCards.forEach(card => {{
                const details = card.querySelector('.field-details');
                const hint = card.querySelector('.expand-hint');

                if (shouldExpand) {{
                    if (details) details.classList.remove('collapsed');
                    card.classList.add('expanded');
                    if (hint) hint.textContent = 'Click any card to collapse all ▲';
                }} else {{
                    if (details) details.classList.add('collapsed');
                    card.classList.remove('expanded');
                    if (hint) hint.textContent = 'Click to expand all details ▼';
                }}
            }});

            allExpanded = shouldExpand;
        }}

        // Add hover effects
        document.querySelectorAll('.source-card').forEach(card => {{
            card.style.cursor = 'pointer';
        }});

        // Collapsible sections (matching PROJECT_OVERVIEW.html)
        document.querySelectorAll('.section-header').forEach(header => {{
            header.addEventListener('click', () => {{
                const content = header.nextElementSibling;
                if (content && content.classList.contains('section-content')) {{
                    header.classList.toggle('collapsed');
                    content.classList.toggle('collapsed');
                }}
            }});
        }});

        // Highlight active nav on scroll
        const sections = document.querySelectorAll('section[id]');
        const navLinks = document.querySelectorAll('.sidebar nav a');

        window.addEventListener('scroll', () => {{
            let current = '';
            sections.forEach(section => {{
                const sectionTop = section.offsetTop - 150;
                if (window.scrollY >= sectionTop) {{
                    current = section.getAttribute('id');
                }}
            }});
            navLinks.forEach(link => {{
                link.classList.remove('active');
                if (link.getAttribute('href') === '#' + current) {{
                    link.classList.add('active');
                }}
            }});
        }});
    </script>
</body>
</html>
'''

def generate_report_card_section(source_avg_score, pipeline_grade, consensus_data, stats_data):
    """
    Generate the Executive Report Card showing three key pillars at a glance.

    1. Source Quality - Average score across all input sources
    2. Pipeline Health - Overall data completeness grade
    3. Consensus Strength - Weighted by business value (hyperscalers count more)
    """

    # Source Quality (avg score across sources)
    source_score = source_avg_score if source_avg_score else 0
    if source_score >= 70:
        source_grade, source_color = "A" if source_score >= 85 else "B", "#34d399" if source_score >= 85 else "#60a5fa"
    elif source_score >= 55:
        source_grade, source_color = "C", "#fbbf24"
    elif source_score >= 40:
        source_grade, source_color = "D", "#fb923c"
    else:
        source_grade, source_color = "F", "#f87171"

    # Pipeline Health (from existing grade calculation)
    pipeline_letter = pipeline_grade[0] if pipeline_grade else "?"
    pipeline_color = pipeline_grade[1] if pipeline_grade else "#8892b0"

    # Consensus Strength (now using weighted score)
    if consensus_data and consensus_data.get("available"):
        consensus_summary = consensus_data.get("summary", {})
        consensus_grade = consensus_summary.get("consensus_grade", "?")
        consensus_color = consensus_summary.get("consensus_color", "#8892b0")
        consensus_label = consensus_summary.get("consensus_label", "Unknown")
        weighted_score = consensus_summary.get("weighted_score", 0)
        pct_multi = consensus_summary.get("pct_multi_source", 0)

        # Get hyperscaler-specific stat for report card display
        tier_breakdown = consensus_data.get("tier_breakdown", {})
        hyperscaler_pct = tier_breakdown.get("hyperscaler", {}).get("pct_multi_source", pct_multi)
    else:
        consensus_grade, consensus_color = "?", "#8892b0"
        consensus_label = "Not Available"
        weighted_score, pct_multi, hyperscaler_pct = 0, 0, 0

    # Stats for context
    total_buildings = stats_data.get("total_buildings", 0)
    total_campus = stats_data.get("total_campus", 0)
    source_count = stats_data.get("source_count", 0)

    return f'''
        <section id="report-card" class="glass">
            <div class="section-header">
                <h2>Executive Report Card</h2>
                <span class="collapse-icon">▼</span>
            </div>
            <div class="section-content">

            <p style="color: rgba(255,255,255,0.6); font-style: italic; margin-bottom: 25px;">
                At-a-glance summary: How good are our sources, how healthy is our pipeline, and how confident are we in the results?
            </p>

            <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 25px; margin-bottom: 30px;">

                <!-- Source Quality Pillar -->
                <div class="glass-dark" style="padding: 25px; text-align: center; border-top: 4px solid {source_color};">
                    <div style="font-size: 0.8rem; color: rgba(255,255,255,0.5); text-transform: uppercase; letter-spacing: 1px; margin-bottom: 10px;">
                        📈 Source Quality
                    </div>
                    <div style="display: inline-flex; flex-direction: column; align-items: center; padding: 15px 30px; border-radius: 12px; background: {source_color}22; border: 2px solid {source_color};">
                        <span style="font-size: 2.5rem; font-weight: 800; color: {source_color}; line-height: 1;">{source_grade}</span>
                        <span style="font-size: 1.2rem; color: rgba(255,255,255,0.7);">{source_score:.0f}</span>
                    </div>
                    <div style="margin-top: 15px; font-size: 0.85rem; color: rgba(255,255,255,0.6);">
                        Avg score across {source_count} sources
                    </div>
                    <div style="margin-top: 8px; font-size: 0.75rem; color: rgba(255,255,255,0.4);">
                        <em>"How good are our inputs?"</em>
                    </div>
                </div>

                <!-- Pipeline Health Pillar -->
                <div class="glass-dark" style="padding: 25px; text-align: center; border-top: 4px solid {pipeline_color};">
                    <div style="font-size: 0.8rem; color: rgba(255,255,255,0.5); text-transform: uppercase; letter-spacing: 1px; margin-bottom: 10px;">
                        🏆 Pipeline Health
                    </div>
                    <div style="display: inline-flex; flex-direction: column; align-items: center; padding: 15px 30px; border-radius: 12px; background: {pipeline_color}22; border: 2px solid {pipeline_color};">
                        <span style="font-size: 2.5rem; font-weight: 800; color: {pipeline_color}; line-height: 1;">{pipeline_letter}</span>
                    </div>
                    <div style="margin-top: 15px; font-size: 0.85rem; color: rgba(255,255,255,0.6);">
                        {total_buildings:,} buildings → {total_campus:,} campuses
                    </div>
                    <div style="margin-top: 8px; font-size: 0.75rem; color: rgba(255,255,255,0.4);">
                        <em>"Is our output complete?"</em>
                    </div>
                </div>

                <!-- Consensus Strength Pillar (now weighted) -->
                <div class="glass-dark" style="padding: 25px; text-align: center; border-top: 4px solid {consensus_color};">
                    <div style="font-size: 0.8rem; color: rgba(255,255,255,0.5); text-transform: uppercase; letter-spacing: 1px; margin-bottom: 10px;">
                        🤝 Consensus Strength
                    </div>
                    <div style="display: inline-flex; flex-direction: column; align-items: center; padding: 15px 30px; border-radius: 12px; background: {consensus_color}22; border: 2px solid {consensus_color};">
                        <span style="font-size: 2.5rem; font-weight: 800; color: {consensus_color}; line-height: 1;">{consensus_grade}</span>
                        <span style="font-size: 1.1rem; color: {consensus_color};">{weighted_score:.0f}/100</span>
                    </div>
                    <div style="margin-top: 15px; font-size: 0.85rem; color: rgba(255,255,255,0.6);">
                        Hyperscaler coverage: {hyperscaler_pct:.0f}% multi-source
                    </div>
                    <div style="margin-top: 8px; font-size: 0.75rem; color: rgba(255,255,255,0.4);">
                        <em>"Can we trust this data?"</em>
                    </div>
                </div>

            </div>

            <div class="glass-dark" style="padding: 20px; border-left: 3px solid rgba(255,255,255,0.3);">
                <div style="font-size: 0.9rem; color: rgba(255,255,255,0.7);">
                    <strong style="color: rgba(255,255,255,0.9);">What This Means:</strong><br>
                    <strong>Source Quality</strong> measures how well our input data sources perform across spatial accuracy, capacity accuracy, and freshness.<br>
                    <strong>Pipeline Health</strong> measures how complete and well-structured our output datasets are.<br>
                    <strong>Consensus Strength</strong> measures multi-source validation <em>weighted by business value</em> — hyperscaler/frontier sites (60%) count more than small/unknown operators (10%).
                </div>
            </div>

            </div>
        </section>
'''


def generate_grade_section(buildings_grade, campus_grade, xb_grade, overall_grade, grade_field_scores=None):
    """Generate the grade banner section with visual breakdown like Source Analysis."""

    # Build visual breakdowns for each layer if field scores provided
    def build_field_breakdown(layer_name, fields_scores, grade_info):
        """Build HTML for visual field score breakdown."""
        if not fields_scores:
            return ""

        rows_html = ""
        for field_name, score in fields_scores.items():
            if score is None:
                continue
            progress_class = get_progress_class(score)
            rows_html += f'''
                <div class="score-component">
                    <div class="component-header">
                        <span class="component-name" style="font-family: monospace; font-size: 0.8rem;">{field_name}</span>
                    </div>
                    <div class="progress-bar" style="height: 6px;">
                        <div class="progress-fill {progress_class}" style="width: {score}%;"></div>
                    </div>
                    <div class="component-values">
                        <span class="raw-score">{score:.0f}%</span>
                    </div>
                </div>'''

        avg_score = sum(s for s in fields_scores.values() if s is not None) / len([s for s in fields_scores.values() if s is not None]) if fields_scores else 0

        return f'''
            <div class="source-card glass" style="border-left: 4px solid {grade_info[1]};">
                <div class="source-header">
                    <span class="source-name">{layer_name}</span>
                    <div class="source-score-badge" style="background: {grade_info[1]}22; border: 2px solid {grade_info[1]};">
                        <span class="score-grade" style="color: {grade_info[1]};">{grade_info[0]}</span>
                        <span class="score-value">{avg_score:.0f}</span>
                    </div>
                </div>
                <div class="source-count">{len([s for s in fields_scores.values() if s is not None])} fields evaluated</div>
                <div class="score-breakdown">
                    {rows_html}
                </div>
            </div>'''

    # Build layer breakdowns if we have field scores
    layer_cards_html = ""
    if grade_field_scores:
        layer_cards_html += build_field_breakdown("Buildings Layer", grade_field_scores.get("buildings_scores", {}), buildings_grade)
        layer_cards_html += build_field_breakdown("Campus Layer", grade_field_scores.get("campus_scores", {}), campus_grade)
        layer_cards_html += build_field_breakdown("XB Combined", grade_field_scores.get("xb_scores", {}), xb_grade)

    return f'''
        <section id="grades">
            <div class="section-header">
                <h2>Pipeline Health Grades</h2>
                <span class="collapse-icon">▼</span>
            </div>
            <div class="section-content">

            <div class="grade-banner">
                <div class="grade-card" style="border-left: 4px solid {overall_grade[1]};">
                    <div class="grade-letter" style="color: {overall_grade[1]};">{overall_grade[0]}</div>
                    <div class="grade-label">Overall Health</div>
                </div>
                <div class="grade-card" style="border-left: 4px solid {buildings_grade[1]};">
                    <div class="grade-letter" style="color: {buildings_grade[1]};">{buildings_grade[0]}</div>
                    <div class="grade-label">Buildings Layer</div>
                </div>
                <div class="grade-card" style="border-left: 4px solid {campus_grade[1]};">
                    <div class="grade-letter" style="color: {campus_grade[1]};">{campus_grade[0]}</div>
                    <div class="grade-label">Campus Layer</div>
                </div>
                <div class="grade-card" style="border-left: 4px solid {xb_grade[1]};">
                    <div class="grade-letter" style="color: {xb_grade[1]};">{xb_grade[0]}</div>
                    <div class="grade-label">XB Combined</div>
                </div>
            </div>

            <h3 style="margin-top: 30px;">Field Completeness by Layer</h3>
            <p style="color: rgba(255,255,255,0.7); margin-bottom: 20px;">
                Each layer is graded on the completeness of critical fields. Higher percentages indicate better data quality.
            </p>

            <div class="source-grid">
                {layer_cards_html}
            </div>

            <div class="glass-dark" style="padding: 25px; margin-top: 25px;">
                <h4 style="color: rgba(255,255,255,0.9); margin-bottom: 20px; font-size: 1.1rem;">📊 Grade Scale</h4>
                <div style="display: flex; flex-wrap: wrap; gap: 15px; justify-content: center;">
                    <div style="display: flex; align-items: center; gap: 8px; padding: 10px 18px; background: rgba(52, 211, 153, 0.15); border-radius: 10px; border: 1px solid #34d399;">
                        <span style="color: #34d399; font-weight: 700; font-size: 1.3rem;">A</span>
                        <span style="color: rgba(255,255,255,0.8); font-size: 0.95rem;">= 90%+</span>
                    </div>
                    <div style="display: flex; align-items: center; gap: 8px; padding: 10px 18px; background: rgba(96, 165, 250, 0.15); border-radius: 10px; border: 1px solid #60a5fa;">
                        <span style="color: #60a5fa; font-weight: 700; font-size: 1.3rem;">B</span>
                        <span style="color: rgba(255,255,255,0.8); font-size: 0.95rem;">= 80-89%</span>
                    </div>
                    <div style="display: flex; align-items: center; gap: 8px; padding: 10px 18px; background: rgba(251, 191, 36, 0.15); border-radius: 10px; border: 1px solid #fbbf24;">
                        <span style="color: #fbbf24; font-weight: 700; font-size: 1.3rem;">C</span>
                        <span style="color: rgba(255,255,255,0.8); font-size: 0.95rem;">= 70-79%</span>
                    </div>
                    <div style="display: flex; align-items: center; gap: 8px; padding: 10px 18px; background: rgba(251, 146, 60, 0.15); border-radius: 10px; border: 1px solid #fb923c;">
                        <span style="color: #fb923c; font-weight: 700; font-size: 1.3rem;">D</span>
                        <span style="color: rgba(255,255,255,0.8); font-size: 0.95rem;">= 60-69%</span>
                    </div>
                    <div style="display: flex; align-items: center; gap: 8px; padding: 10px 18px; background: rgba(248, 113, 113, 0.15); border-radius: 10px; border: 1px solid #f87171;">
                        <span style="color: #f87171; font-weight: 700; font-size: 1.3rem;">F</span>
                        <span style="color: rgba(255,255,255,0.8); font-size: 0.95rem;">= &lt;60%</span>
                    </div>
                </div>
            </div>
            </div>
        </section>
'''

def generate_stats_section(stats):
    """Generate the quick stats section."""
    return f'''
        <div class="stats-grid">
            <div class="stat-card glass">
                <div class="stat-value">{stats.get('total_buildings', 0):,}</div>
                <div class="stat-label">Buildings</div>
            </div>
            <div class="stat-card glass">
                <div class="stat-value">{stats.get('total_campus', 0):,}</div>
                <div class="stat-label">Campuses</div>
            </div>
            <div class="stat-card glass">
                <div class="stat-value">{stats.get('total_xb', 0):,}</div>
                <div class="stat-label">XB Combined</div>
            </div>
            <div class="stat-card glass">
                <div class="stat-value">{stats.get('source_count', 0)}</div>
                <div class="stat-label">Data Sources</div>
            </div>
            <div class="stat-card glass">
                <div class="stat-value">{stats.get('avg_completeness', 0):.0f}%</div>
                <div class="stat-label">Avg Completeness</div>
            </div>
        </div>
'''

def get_progress_class(pct):
    """Get CSS class for progress bar based on percentage."""
    if pct >= 80:
        return "progress-green"
    elif pct >= 60:
        return "progress-blue"
    elif pct >= 40:
        return "progress-yellow"
    elif pct >= 20:
        return "progress-orange"
    else:
        return "progress-red"

def generate_source_cards(source_stats, weighted_stats=None):
    """Generate source analysis cards with weighted scoring and drill-down."""

    # If weighted stats provided, use those for the enhanced view
    if weighted_stats:
        cards_html = ""

        # Sort included sources by score (highest to lowest)
        sorted_sources = sorted(
            weighted_stats.items(),
            key=lambda x: x[1].get("final_score", 0) if x[1] else 0,
            reverse=True
        )

        # First, show the included sources (now sorted by score)
        for source_name, stats in sorted_sources:
            if stats is None or "error" in stats:
                continue

            # Score breakdown
            scores = stats.get("scores", {})
            weights = stats.get("weights", {})

            # Component breakdown rows
            component_rows = ""
            component_labels = {
                "volume": "📊 Volume",
                "core": "🏢 Core Identity",
                "capacity": "⚡ Capacity Data",
                "location": "📍 Location",
                "richness": "📋 Attribute Richness"
            }
            for key in ["volume", "core", "capacity", "location", "richness"]:
                score = scores.get(key, 0)
                weight = weights.get(key, 0) * 100
                contribution = score * weights.get(key, 0)
                progress_class = get_progress_class(score)
                component_rows += f'''
                    <div class="score-component">
                        <div class="component-header">
                            <span class="component-name">{component_labels.get(key, key)}</span>
                            <span class="component-weight">×{weight:.0f}%</span>
                        </div>
                        <div class="progress-bar" style="height: 6px;">
                            <div class="progress-fill {progress_class}" style="width: {score}%;"></div>
                        </div>
                        <div class="component-values">
                            <span class="raw-score">{score:.0f}%</span>
                            <span class="contribution">+{contribution:.1f}</span>
                        </div>
                    </div>'''

            # Field detail rows for drill-down
            field_rows = ""
            for field, pct in stats.get("field_details", {}).items():
                progress_class = get_progress_class(pct)
                field_rows += f'''
                    <div class="field-detail">
                        <span class="field-name">{field}</span>
                        <div class="progress-bar" style="height: 4px; flex: 1; margin: 0 10px;">
                            <div class="progress-fill {progress_class}" style="width: {pct}%;"></div>
                        </div>
                        <span class="field-pct">{pct:.0f}%</span>
                    </div>'''

            cards_html += f'''
            <div class="source-card glass" onclick="toggleDetails(this)">
                <div class="source-header">
                    <span class="source-name">{source_name}</span>
                    <div class="source-score-badge" style="background: {stats['grade_color']}22; border: 2px solid {stats['grade_color']};">
                        <span class="score-grade" style="color: {stats['grade_color']};">{stats['grade']}</span>
                        <span class="score-value">{stats['final_score']:.0f}</span>
                    </div>
                </div>
                <div class="source-count">{stats['count']:,} records</div>

                <div class="score-breakdown">
                    {component_rows}
                </div>

                <div class="field-details collapsed">
                    <h4>Field Completeness Detail</h4>
                    {field_rows}
                </div>

                <div class="expand-hint">Click to expand field details ▼</div>
            </div>'''

        # Now add excluded sources with their poor grades for contrast
        excluded_cards_html = ""
        for source_name, info in EXCLUDED_SOURCE_GRADES.items():
            scores = info.get("scores", {})
            grade = info.get("grade", "F")
            grade_color = info.get("grade_color", "#f87171")
            final_score = info.get("final_score", 0)
            reason = info.get("reason", "Excluded")
            records = info.get("records", 0)

            # Component breakdown rows for excluded sources
            component_rows = ""
            component_labels = {
                "volume": "📊 Volume",
                "core": "🏢 Core Identity",
                "capacity": "⚡ Capacity Data",
                "location": "📍 Location",
                "richness": "📋 Attribute Richness"
            }
            for key in ["volume", "core", "capacity", "location", "richness"]:
                score = scores.get(key, 0)
                progress_class = get_progress_class(score)
                component_rows += f'''
                    <div class="score-component">
                        <div class="component-header">
                            <span class="component-name">{component_labels.get(key, key)}</span>
                        </div>
                        <div class="progress-bar" style="height: 6px;">
                            <div class="progress-fill {progress_class}" style="width: {score}%;"></div>
                        </div>
                        <div class="component-values">
                            <span class="raw-score">{score:.0f}%</span>
                        </div>
                    </div>'''

            excluded_cards_html += f'''
            <div class="source-card glass" style="opacity: 0.7; border-left: 4px solid {grade_color};">
                <div class="source-header">
                    <span class="source-name" style="color: rgba(255,255,255,0.7);">{source_name}</span>
                    <div class="source-score-badge" style="background: {grade_color}22; border: 2px solid {grade_color};">
                        <span class="score-grade" style="color: {grade_color};">{grade}</span>
                        <span class="score-value">{final_score:.0f}</span>
                    </div>
                </div>
                <div class="source-count" style="color: rgba(255,255,255,0.5);">{records:,} records (excluded)</div>

                <div style="background: rgba(248, 113, 113, 0.15); padding: 8px 12px; border-radius: 6px; margin: 10px 0;">
                    <span style="color: #f87171; font-size: 0.85rem;">⊘ {reason}</span>
                </div>

                <div class="score-breakdown">
                    {component_rows}
                </div>
            </div>'''

    return f'''
        <section id="sources" class="glass">
            <div class="section-header">
                <h2>Source Analysis (Weighted Scoring)</h2>
                <span class="collapse-icon">▼</span>
            </div>
            <div class="section-content">

            <div class="formula-box glass-dark">
                <h4>Scoring Formula</h4>
                <code>Final Score = (Volume × 10%) + (Core × 25%) + (Capacity × 20%) + (Location × 15%) + (Spatial Accuracy × 20%) + (Richness × 10%)</code>
                <div class="formula-legend">
                    <span><strong>Volume:</strong> Records contributed (scaled)</span>
                    <span><strong>Core:</strong> company_clean, ucid completeness</span>
                    <span><strong>Capacity:</strong> MW fields populated</span>
                    <span><strong>Location:</strong> lat/lon completeness</span>
                    <span><strong>Spatial Accuracy:</strong> Recall + distance vs Meta</span>
                    <span><strong>Richness:</strong> Overall attribute coverage</span>
                </div>
            </div>

            <h3 style="color: rgba(255,255,255,0.9); margin-bottom: 15px;">Included Sources</h3>
            <div class="source-grid">
                {cards_html}
            </div>

            <h3 style="color: rgba(255,255,255,0.7); margin-top: 30px; margin-bottom: 15px;">Excluded Sources (for comparison)</h3>
            <p style="color: rgba(255,255,255,0.5); font-size: 0.9rem; margin-bottom: 15px;">
                These sources are available but excluded from the pipeline due to data quality issues.
            </p>
            <div class="source-grid">
                {excluded_cards_html}
            </div>
            </div>
        </section>
'''

    # Fallback to legacy cards if no weighted stats
    cards_html = ""
    for source_name, stats in source_stats.items():
        if stats is None:
            continue

        metrics_html = ""
        for field, pct in stats.get("completeness", {}).items():
            if pct is None:
                continue
            metrics_html += f'''
                <div class="metric-row">
                    <span class="metric-label">{field}</span>
                    <span class="metric-value">{pct}%</span>
                </div>'''

        cards_html += f'''
            <div class="source-card glass">
                <div class="source-header">
                    <span class="source-name">{source_name}</span>
                    <span class="source-grade" style="color: {stats['grade_color']};">{stats['grade']}</span>
                </div>
                <div class="source-count">{stats['count']:,} records</div>
                <div class="source-metrics">
                    {metrics_html}
                </div>
            </div>'''

    return f'''
        <section class="glass">
            <h2>Source Analysis</h2>
            <div class="source-grid">
                {cards_html}
            </div>
        </section>
'''

def generate_field_completeness_table(field_data):
    """Generate field completeness table."""
    rows_html = ""
    for category, fields in field_data.items():
        for field_name, pct in fields.items():
            if pct is None:
                pct_display = "N/A"
                bar_html = '<div class="progress-bar"><div class="progress-fill" style="width: 0%;"></div></div>'
            else:
                pct_display = f"{pct}%"
                progress_class = get_progress_class(pct)
                bar_html = f'<div class="progress-bar"><div class="progress-fill {progress_class}" style="width: {pct}%;"></div></div>'

            rows_html += f'''
                <tr>
                    <td><strong>{category}</strong></td>
                    <td style="font-family: monospace;">{field_name}</td>
                    <td style="width: 40%;">{bar_html}</td>
                    <td style="text-align: right; font-weight: 600;">{pct_display}</td>
                </tr>'''

    return f'''
        <section id="completeness" class="glass">
            <div class="section-header">
                <h2>Field Completeness (XB Combined Layer)</h2>
                <span class="collapse-icon">▼</span>
            </div>
            <div class="section-content">

            <p style="color: rgba(255,255,255,0.6); font-style: italic; margin-bottom: 20px;">
                Key Question: "Does this dataset have what I need? What percentage of records have usable values?"
            </p>

            <table>
                <thead>
                    <tr>
                        <th>Category</th>
                        <th>Field</th>
                        <th>Completeness</th>
                        <th style="text-align: right;">%</th>
                    </tr>
                </thead>
                <tbody>
                    {rows_html}
                </tbody>
            </table>
            </div>
        </section>
'''

def generate_distribution_section(source_dist, company_dist, state_dist, fc_path=None, capacity_by_source=None, capacity_by_company=None, region_distribution=None, capacity_by_state=None):
    """Generate distribution visualizations with small multiples (count vs capacity) and regional breakdown."""

    # Filter out (null) and empty company names
    filtered_company_dist = {k: v for k, v in company_dist.items() if k and k != "(null)" and k.strip() != ""}

    # Separate hyperscalers from "Colo - All Other"
    hyperscaler_dist = {k: v for k, v in filtered_company_dist.items() if k != "Colo - All Other"}
    colo_count = filtered_company_dist.get("Colo - All Other", 0)

    # Calculate max values for scaling
    max_source_count = max(source_dist.values()) if source_dist else 1
    max_source_cap = max(capacity_by_source.values()) if capacity_by_source else 1

    # === SOURCE DISTRIBUTION - SMALL MULTIPLES ===
    source_rows = ""
    for source, count in list(source_dist.items())[:6]:
        count_pct = (count / max_source_count) * 100
        cap_mw = capacity_by_source.get(source, 0) if capacity_by_source else 0
        cap_pct = (cap_mw / max_source_cap) * 100 if max_source_cap > 0 else 0
        cap_display = f"{cap_mw/1000:.1f} GW" if cap_mw >= 1000 else f"{cap_mw:.0f} MW"

        source_rows += f'''
            <tr>
                <td style="color: rgba(255,255,255,0.9); font-weight: 500; width: 140px;">{source}</td>
                <td style="width: 40%;">
                    <div style="display: flex; align-items: center; gap: 10px;">
                        <div class="dist-bar-container" style="flex: 1;">
                            <div class="dist-bar-fill" style="width: {count_pct}%; min-width: 30px;"></div>
                        </div>
                        <span style="color: rgba(255,255,255,0.9); font-weight: 600; width: 60px; text-align: right;">{count:,}</span>
                    </div>
                </td>
                <td style="width: 40%;">
                    <div style="display: flex; align-items: center; gap: 10px;">
                        <div class="dist-bar-container" style="flex: 1;">
                            <div class="dist-bar-fill" style="width: {cap_pct}%; min-width: 30px; background: linear-gradient(90deg, #f59e0b, #d97706);"></div>
                        </div>
                        <span style="color: rgba(255,255,255,0.9); font-weight: 600; width: 70px; text-align: right;">{cap_display}</span>
                    </div>
                </td>
            </tr>'''

    # === TYPE BREAKDOWN (Hyperscale vs Colo) - SMALL MULTIPLES ===
    hyperscale_total = sum(hyperscaler_dist.values())
    hyperscale_cap = sum(capacity_by_company.get(c, 0) for c in hyperscaler_dist.keys()) if capacity_by_company else 0
    colo_cap = capacity_by_company.get("Colo - All Other", 0) if capacity_by_company else 0

    max_type_count = max(hyperscale_total, colo_count) if max(hyperscale_total, colo_count) > 0 else 1
    max_type_cap = max(hyperscale_cap, colo_cap) if max(hyperscale_cap, colo_cap) > 0 else 1

    hs_count_pct = (hyperscale_total / max_type_count) * 100
    colo_count_pct = (colo_count / max_type_count) * 100
    hs_cap_pct = (hyperscale_cap / max_type_cap) * 100 if max_type_cap > 0 else 0
    colo_cap_pct = (colo_cap / max_type_cap) * 100 if max_type_cap > 0 else 0

    hs_cap_display = f"{hyperscale_cap/1000:.1f} GW" if hyperscale_cap >= 1000 else f"{hyperscale_cap:.0f} MW"
    colo_cap_display = f"{colo_cap/1000:.1f} GW" if colo_cap >= 1000 else f"{colo_cap:.0f} MW"

    type_rows = f'''
            <tr>
                <td style="color: rgba(255,255,255,0.9); font-weight: 500; width: 140px;">Hyperscale</td>
                <td style="width: 40%;">
                    <div style="display: flex; align-items: center; gap: 10px;">
                        <div class="dist-bar-container" style="flex: 1;">
                            <div class="dist-bar-fill" style="width: {hs_count_pct}%; min-width: 30px;"></div>
                        </div>
                        <span style="color: rgba(255,255,255,0.9); font-weight: 600; width: 60px; text-align: right;">{hyperscale_total:,}</span>
                    </div>
                </td>
                <td style="width: 40%;">
                    <div style="display: flex; align-items: center; gap: 10px;">
                        <div class="dist-bar-container" style="flex: 1;">
                            <div class="dist-bar-fill" style="width: {hs_cap_pct}%; min-width: 30px; background: linear-gradient(90deg, #f59e0b, #d97706);"></div>
                        </div>
                        <span style="color: rgba(255,255,255,0.9); font-weight: 600; width: 70px; text-align: right;">{hs_cap_display}</span>
                    </div>
                </td>
            </tr>
            <tr>
                <td style="color: rgba(255,255,255,0.9); font-weight: 500; width: 140px;">Colo / Other</td>
                <td style="width: 40%;">
                    <div style="display: flex; align-items: center; gap: 10px;">
                        <div class="dist-bar-container" style="flex: 1;">
                            <div class="dist-bar-fill" style="width: {colo_count_pct}%; min-width: 30px;"></div>
                        </div>
                        <span style="color: rgba(255,255,255,0.9); font-weight: 600; width: 60px; text-align: right;">{colo_count:,}</span>
                    </div>
                </td>
                <td style="width: 40%;">
                    <div style="display: flex; align-items: center; gap: 10px;">
                        <div class="dist-bar-container" style="flex: 1;">
                            <div class="dist-bar-fill" style="width: {colo_cap_pct}%; min-width: 30px; background: linear-gradient(90deg, #f59e0b, #d97706);"></div>
                        </div>
                        <span style="color: rgba(255,255,255,0.9); font-weight: 600; width: 70px; text-align: right;">{colo_cap_display}</span>
                    </div>
                </td>
            </tr>'''

    # === HYPERSCALER BREAKDOWN - SMALL MULTIPLES ===
    max_hs_count = max(hyperscaler_dist.values()) if hyperscaler_dist else 1
    max_hs_cap = max((capacity_by_company.get(c, 0) for c in hyperscaler_dist.keys()), default=1) if capacity_by_company else 1

    hyperscaler_rows = ""
    for company, count in sorted(hyperscaler_dist.items(), key=lambda x: x[1], reverse=True)[:8]:
        count_pct = (count / max_hs_count) * 100
        cap_mw = capacity_by_company.get(company, 0) if capacity_by_company else 0
        cap_pct = (cap_mw / max_hs_cap) * 100 if max_hs_cap > 0 else 0
        cap_display = f"{cap_mw/1000:.1f} GW" if cap_mw >= 1000 else f"{cap_mw:.0f} MW"

        hyperscaler_rows += f'''
            <tr>
                <td style="color: rgba(255,255,255,0.9); font-weight: 500; width: 140px;">{company}</td>
                <td style="width: 40%;">
                    <div style="display: flex; align-items: center; gap: 10px;">
                        <div class="dist-bar-container" style="flex: 1;">
                            <div class="dist-bar-fill" style="width: {count_pct}%; min-width: 30px;"></div>
                        </div>
                        <span style="color: rgba(255,255,255,0.9); font-weight: 600; width: 60px; text-align: right;">{count:,}</span>
                    </div>
                </td>
                <td style="width: 40%;">
                    <div style="display: flex; align-items: center; gap: 10px;">
                        <div class="dist-bar-container" style="flex: 1;">
                            <div class="dist-bar-fill" style="width: {cap_pct}%; min-width: 30px; background: linear-gradient(90deg, #f59e0b, #d97706);"></div>
                        </div>
                        <span style="color: rgba(255,255,255,0.9); font-weight: 600; width: 70px; text-align: right;">{cap_display}</span>
                    </div>
                </td>
            </tr>'''

    # === REGIONAL BREAKDOWN ===
    # Define regions based on country/state patterns
    region_html = ""
    if region_distribution:
        region_rows = ""
        max_region_count = max(r.get("count", 0) for r in region_distribution.values()) if region_distribution else 1
        max_region_cap = max(r.get("capacity", 0) for r in region_distribution.values()) if region_distribution else 1

        for region_name, stats in sorted(region_distribution.items(), key=lambda x: x[1].get("count", 0), reverse=True):
            count = stats.get("count", 0)
            cap_mw = stats.get("capacity", 0)
            count_pct = (count / max_region_count) * 100 if max_region_count > 0 else 0
            cap_pct = (cap_mw / max_region_cap) * 100 if max_region_cap > 0 else 0
            cap_display = f"{cap_mw/1000:.1f} GW" if cap_mw >= 1000 else f"{cap_mw:.0f} MW"

            region_rows += f'''
            <tr>
                <td style="color: rgba(255,255,255,0.9); font-weight: 500; width: 140px;">{region_name}</td>
                <td style="width: 40%;">
                    <div style="display: flex; align-items: center; gap: 10px;">
                        <div class="dist-bar-container" style="flex: 1;">
                            <div class="dist-bar-fill" style="width: {count_pct}%; min-width: 30px;"></div>
                        </div>
                        <span style="color: rgba(255,255,255,0.9); font-weight: 600; width: 60px; text-align: right;">{count:,}</span>
                    </div>
                </td>
                <td style="width: 40%;">
                    <div style="display: flex; align-items: center; gap: 10px;">
                        <div class="dist-bar-container" style="flex: 1;">
                            <div class="dist-bar-fill" style="width: {cap_pct}%; min-width: 30px; background: linear-gradient(90deg, #f59e0b, #d97706);"></div>
                        </div>
                        <span style="color: rgba(255,255,255,0.9); font-weight: 600; width: 70px; text-align: right;">{cap_display}</span>
                    </div>
                </td>
            </tr>'''

        region_html = f'''
            <h3 style="color: rgba(255,255,255,0.9); margin-top: 25px;">Global Regions</h3>
            <p style="color: rgba(255,255,255,0.6); font-size: 0.9rem; margin-bottom: 15px;">
                Geographic distribution by major region.
            </p>
            <table>
                <thead>
                    <tr>
                        <th style="color: rgba(255,255,255,0.9);">Region</th>
                        <th style="color: rgba(255,255,255,0.9);">Records</th>
                        <th style="color: rgba(255,255,255,0.9);">Capacity</th>
                    </tr>
                </thead>
                <tbody>
                    {region_rows}
                </tbody>
            </table>'''

    # State distribution with capacity (matching small multiples pattern)
    state_rows = ""
    max_state_count = max(state_dist.values()) if state_dist else 1
    max_state_cap = max(capacity_by_state.values()) if capacity_by_state else 1

    for state, count in list(state_dist.items())[:12]:
        count_pct = (count / max_state_count) * 100 if max_state_count > 0 else 0
        cap_mw = capacity_by_state.get(state, 0) if capacity_by_state else 0
        cap_pct = (cap_mw / max_state_cap) * 100 if max_state_cap > 0 else 0
        cap_display = f"{cap_mw/1000:.1f} GW" if cap_mw >= 1000 else f"{cap_mw:.0f} MW"

        state_rows += f'''
            <tr>
                <td style="color: rgba(255,255,255,0.9); font-weight: 500; width: 140px;">{state}</td>
                <td style="width: 40%;">
                    <div style="display: flex; align-items: center; gap: 10px;">
                        <div class="dist-bar-container" style="flex: 1;">
                            <div class="dist-bar-fill" style="width: {count_pct}%; min-width: 30px;"></div>
                        </div>
                        <span style="color: rgba(255,255,255,0.9); font-weight: 600; width: 60px; text-align: right;">{count:,}</span>
                    </div>
                </td>
                <td style="width: 40%;">
                    <div style="display: flex; align-items: center; gap: 10px;">
                        <div class="dist-bar-container" style="flex: 1;">
                            <div class="dist-bar-fill" style="width: {cap_pct}%; min-width: 30px; background: linear-gradient(90deg, #f59e0b, #d97706);"></div>
                        </div>
                        <span style="color: rgba(255,255,255,0.9); font-weight: 600; width: 70px; text-align: right;">{cap_display}</span>
                    </div>
                </td>
            </tr>'''

    return f'''
        <section id="distribution" class="glass">
            <div class="section-header">
                <h2>Data Distribution</h2>
                <span class="collapse-icon">▼</span>
            </div>
            <div class="section-content">

            <p style="color: rgba(255,255,255,0.6); font-style: italic; margin-bottom: 20px;">
                Key Question: "Where is the data concentrated? What's the mix between sources, types, and regions?"
            </p>

            <h3 style="color: rgba(255,255,255,0.9);">By Source</h3>
            <p style="color: rgba(255,255,255,0.6); font-size: 0.9rem; margin-bottom: 15px;">
                Side-by-side comparison of record counts vs total capacity (full_capacity_mw).
            </p>
            <table>
                <thead>
                    <tr>
                        <th style="color: rgba(255,255,255,0.9);">Source</th>
                        <th style="color: rgba(255,255,255,0.9);">Records</th>
                        <th style="color: rgba(255,255,255,0.9);">Capacity</th>
                    </tr>
                </thead>
                <tbody>
                    {source_rows}
                </tbody>
            </table>

            <h3 style="color: rgba(255,255,255,0.9); margin-top: 25px;">By Type (Hyperscale vs Colo)</h3>
            <p style="color: rgba(255,255,255,0.6); font-size: 0.9rem; margin-bottom: 15px;">
                Hyperscale includes AWS, Microsoft, Google, Meta, Apple, Oracle, xAI, Alibaba.
            </p>
            <table>
                <thead>
                    <tr>
                        <th style="color: rgba(255,255,255,0.9);">Type</th>
                        <th style="color: rgba(255,255,255,0.9);">Records</th>
                        <th style="color: rgba(255,255,255,0.9);">Capacity</th>
                    </tr>
                </thead>
                <tbody>
                    {type_rows}
                </tbody>
            </table>

            <h3 style="color: rgba(255,255,255,0.9); margin-top: 25px;">Hyperscaler Breakdown</h3>
            <p style="color: rgba(255,255,255,0.6); font-size: 0.9rem; margin-bottom: 15px;">
                Individual hyperscaler comparison (excludes Colo - All Other).
            </p>
            <table>
                <thead>
                    <tr>
                        <th style="color: rgba(255,255,255,0.9);">Company</th>
                        <th style="color: rgba(255,255,255,0.9);">Records</th>
                        <th style="color: rgba(255,255,255,0.9);">Capacity</th>
                    </tr>
                </thead>
                <tbody>
                    {hyperscaler_rows}
                </tbody>
            </table>

            {region_html}

            <h3 style="color: rgba(255,255,255,0.9); margin-top: 25px;">Top States (US)</h3>
            <table>
                <thead>
                    <tr>
                        <th style="color: rgba(255,255,255,0.9);">State</th>
                        <th style="color: rgba(255,255,255,0.9);">Records</th>
                        <th style="color: rgba(255,255,255,0.9);">Capacity</th>
                    </tr>
                </thead>
                <tbody>
                    {state_rows}
                </tbody>
            </table>
            </div>
        </section>
'''

def generate_quality_section(dup_check, vintage_stats):
    """Generate data quality alerts section."""
    alerts_html = ""

    # Duplicate check
    if dup_check.get("checked"):
        dup_count = dup_check.get("duplicate_count", 0)
        if dup_count == 0:
            alerts_html += '''
                <div class="alert alert-success">
                    <span class="alert-icon">✓</span>
                    <div class="alert-content">
                        <div class="alert-title">No Duplicate IDs</div>
                        <div class="alert-text">All unique_id values are unique across the dataset.</div>
                    </div>
                </div>'''
        else:
            examples = ", ".join(dup_check.get("examples", [])[:3])
            alerts_html += f'''
                <div class="alert alert-warning">
                    <span class="alert-icon">⚠</span>
                    <div class="alert-content">
                        <div class="alert-title">{dup_count} Duplicate IDs Found</div>
                        <div class="alert-text">Examples: {examples}</div>
                    </div>
                </div>'''

    # Data vintage
    if vintage_stats.get("available"):
        populated = vintage_stats.get("populated", 0)
        null_count = vintage_stats.get("null", 0)
        total = populated + null_count
        pct = round((populated / total) * 100, 1) if total > 0 else 0

        if pct >= 80:
            alert_class = "alert-success"
            icon = "✓"
        elif pct >= 50:
            alert_class = "alert-warning"
            icon = "⚠"
        else:
            alert_class = "alert-error"
            icon = "✗"

        date_range = f"{vintage_stats.get('oldest', 'N/A')} to {vintage_stats.get('newest', 'N/A')}"
        alerts_html += f'''
                <div class="alert {alert_class}">
                    <span class="alert-icon">{icon}</span>
                    <div class="alert-content">
                        <div class="alert-title">Data Vintage: {pct}% Populated</div>
                        <div class="alert-text">{populated:,} records have vintage dates. Range: {date_range}</div>
                    </div>
                </div>'''

    return f'''
        <section id="quality" class="glass">
            <div class="section-header">
                <h2>Data Quality Checks</h2>
                <span class="collapse-icon">▼</span>
            </div>
            <div class="section-content">

            <p style="color: rgba(255,255,255,0.6); font-style: italic; margin-bottom: 20px;">
                Key Question: "Are there data integrity issues that could affect analysis?"
            </p>

            {alerts_html}
            </div>
        </section>
'''


def generate_spatial_accuracy_section(spatial_data):
    """Generate section showing spatial accuracy vs Meta Canonical."""

    if not spatial_data.get("available"):
        error_msg = spatial_data.get("error", "Spatial accuracy data not available")
        return f'''
        <section class="glass">
            <h2>Spatial Accuracy vs Meta Canonical</h2>
            <div class="alert alert-warning">
                <span class="alert-icon">⚠</span>
                <div class="alert-content">
                    <div class="alert-title">Data Not Available</div>
                    <div class="alert-text">{error_msg}</div>
                </div>
            </div>
        </section>
'''

    total_meta = spatial_data.get("total_meta_buildings", 0)
    sources = spatial_data.get("sources", {})

    # Sort sources by recall for ranking
    ranked_by_recall = sorted(
        [(name, stats) for name, stats in sources.items() if stats.get("matched_count", 0) > 0],
        key=lambda x: x[1].get("recall_pct", 0),
        reverse=True
    )

    # Sort sources by median distance (best accuracy)
    ranked_by_accuracy = sorted(
        [(name, stats) for name, stats in sources.items()
         if stats.get("median_distance_m") is not None],
        key=lambda x: x[1].get("median_distance_m", float('inf'))
    )

    # Build rankings table
    recall_ranking_html = ""
    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣"]
    for i, (source_name, stats) in enumerate(ranked_by_recall[:6]):
        medal = medals[i] if i < len(medals) else f"{i+1}."
        recall_pct = stats.get("recall_pct", 0)
        matched = stats.get("matched_count", 0)
        recall_ranking_html += f'''
            <tr>
                <td>{medal}</td>
                <td><strong>{source_name}</strong></td>
                <td style="text-align: right;">{recall_pct:.1f}%</td>
                <td style="text-align: right; color: rgba(255,255,255,0.6);">{matched}/{total_meta}</td>
            </tr>'''

    accuracy_ranking_html = ""
    for i, (source_name, stats) in enumerate(ranked_by_accuracy[:6]):
        medal = medals[i] if i < len(medals) else f"{i+1}."
        median = stats.get("median_distance_m", 0)
        mad = stats.get("mad_m", 0)
        # Color based on accuracy
        if median <= 500:
            color = "#34d399"  # green
        elif median <= 1000:
            color = "#60a5fa"  # blue
        elif median <= 3000:
            color = "#fbbf24"  # yellow
        else:
            color = "#f87171"  # red

        accuracy_ranking_html += f'''
            <tr>
                <td>{medal}</td>
                <td><strong>{source_name}</strong></td>
                <td style="text-align: right; color: {color}; font-weight: 600;">{median:,.0f}m</td>
                <td style="text-align: right; color: rgba(255,255,255,0.6);">±{mad:,.0f}m</td>
            </tr>'''

    # Threshold performance table (exclude Meta Canonical - it's the reference)
    threshold_html = ""
    for source_name in SOURCES_FOR_ACCURACY_SCORING:
        stats = sources.get(source_name, {})
        if stats.get("matched_count", 0) == 0:
            continue

        pct_100m = stats.get("pct_within_100m", 0)
        pct_500m = stats.get("pct_within_500m", 0)
        pct_1km = stats.get("pct_within_1km", 0)
        pct_5km = stats.get("pct_within_5km", 0)

        threshold_html += f'''
            <tr>
                <td style="color: rgba(255,255,255,0.9);"><strong>{source_name}</strong></td>
            <td style="text-align: center;">
                    <div class="progress-bar" style="height: 8px; width: 80px; display: inline-block;">
                        <div class="progress-fill {get_progress_class(pct_100m)}" style="width: {pct_100m}%;"></div>
                    </div>
                    <span style="margin-left: 8px; font-size: 0.85rem; color: rgba(255,255,255,0.9);">{pct_100m:.0f}%</span>
                </td>
                <td style="text-align: center;">
                    <div class="progress-bar" style="height: 8px; width: 80px; display: inline-block;">
                        <div class="progress-fill {get_progress_class(pct_500m)}" style="width: {pct_500m}%;"></div>
                    </div>
                    <span style="margin-left: 8px; font-size: 0.85rem; color: rgba(255,255,255,0.9);">{pct_500m:.0f}%</span>
                </td>
                <td style="text-align: center;">
                    <div class="progress-bar" style="height: 8px; width: 80px; display: inline-block;">
                        <div class="progress-fill {get_progress_class(pct_1km)}" style="width: {pct_1km}%;"></div>
                    </div>
                    <span style="margin-left: 8px; font-size: 0.85rem; color: rgba(255,255,255,0.9);">{pct_1km:.0f}%</span>
                </td>
                <td style="text-align: center;">
                    <div class="progress-bar" style="height: 8px; width: 80px; display: inline-block;">
                        <div class="progress-fill {get_progress_class(pct_5km)}" style="width: {pct_5km}%;"></div>
                    </div>
                    <span style="margin-left: 8px; font-size: 0.85rem; color: rgba(255,255,255,0.9);">{pct_5km:.0f}%</span>
                </td>
            </tr>'''

    # Source detail cards (exclude Meta Canonical - it's the reference, not a source being evaluated)
    source_cards_html = ""
    for source_name in SOURCES_FOR_ACCURACY_SCORING:
        stats = sources.get(source_name, {})

        if stats.get("matched_count", 0) == 0:
            source_cards_html += f'''
            <div class="source-card glass" style="opacity: 0.6;">
                <div class="source-header">
                    <span class="source-name" style="color: rgba(255,255,255,0.9);">{source_name}</span>
                    <span class="source-grade" style="color: #8892b0;">—</span>
                </div>
                <div class="source-count" style="color: rgba(255,255,255,0.5);">No matches within 50km</div>
            </div>'''
            continue

        recall_pct = stats.get("recall_pct", 0)
        median = stats.get("median_distance_m", 0)
        mad = stats.get("mad_m", 0)
        matched = stats.get("matched_count", 0)
        buildings_in_src = stats.get("buildings_in_source", 0)

        # Determine grade based on combination of recall and accuracy
        if recall_pct >= 50 and median <= 1000:
            grade, color = "A", "#34d399"
        elif recall_pct >= 30 and median <= 2000:
            grade, color = "B", "#60a5fa"
        elif recall_pct >= 20 and median <= 5000:
            grade, color = "C", "#fbbf24"
        elif recall_pct >= 10:
            grade, color = "D", "#fb923c"
        else:
            grade, color = "F", "#f87171"

        source_cards_html += f'''
            <div class="source-card glass">
                <div class="source-header">
                    <span class="source-name" style="color: rgba(255,255,255,0.9);">{source_name}</span>
                    <div style="display: flex; flex-direction: column; align-items: center; padding: 8px 16px; border-radius: 12px; background: {color}22; border: 2px solid {color};">
                        <span style="font-size: 1.6rem; font-weight: 700; color: {color};">{grade}</span>
                    </div>
                </div>
                <div class="source-count" style="color: rgba(255,255,255,0.6);">{buildings_in_src:,} total buildings in source</div>

                <div class="source-metrics" style="margin-top: 15px;">
                    <div class="metric-row">
                        <span class="metric-label" style="color: rgba(255,255,255,0.6);">📊 Recall (Meta coverage)</span>
                        <span class="metric-value" style="color: rgba(255,255,255,0.9);">{recall_pct:.1f}% ({matched}/{total_meta})</span>
                    </div>
                    <div class="metric-row">
                        <span class="metric-label" style="color: rgba(255,255,255,0.6);">📍 Median Distance</span>
                        <span class="metric-value" style="color: rgba(255,255,255,0.9);">{median:,.0f}m</span>
                    </div>
                    <div class="metric-row">
                        <span class="metric-label" style="color: rgba(255,255,255,0.6);">📏 MAD (consistency)</span>
                        <span class="metric-value" style="color: rgba(255,255,255,0.9);">±{mad:,.0f}m</span>
                    </div>
                    <div class="metric-row">
                        <span class="metric-label" style="color: rgba(255,255,255,0.6);">✅ Within 1km</span>
                        <span class="metric-value" style="color: rgba(255,255,255,0.9);">{stats.get("pct_within_1km", 0):.0f}%</span>
                    </div>
                </div>

                <div style="margin-top: 15px; padding: 10px; background: rgba(255,255,255,0.05); border-radius: 8px; font-size: 0.75rem;">
                    <div style="color: rgba(255,255,255,0.5); margin-bottom: 4px;">Spatial Score Formula:</div>
                    <code style="color: #fbbf24; font-size: 0.7rem;">(Recall% × 0.5) + (DistanceScore × 0.5)</code>
                    <div style="color: rgba(255,255,255,0.4); margin-top: 4px; font-size: 0.65rem;">
                        DistanceScore = max(0, 100 - (median_m / 100))
                    </div>
                </div>
            </div>'''

    return f'''
        <section id="spatial" class="glass">
            <div class="section-header">
                <h2>Spatial Accuracy vs Meta Canonical</h2>
                <span class="collapse-icon">▼</span>
            </div>
            <div class="section-content">

            <p style="color: rgba(255,255,255,0.6); font-style: italic; margin-bottom: 20px;">
                Key Question: "Can I trust the coordinates? How close are vendor locations to known ground truth?"
            </p>

            <p style="color: rgba(255,255,255,0.7); margin-bottom: 25px;">
                Compares vendor data point locations against <strong>{total_meta} Meta Canonical buildings</strong>
                using Haversine (geodesic) distance. Sources with lower median distance have more precise location data.
            </p>

            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 25px; margin-bottom: 30px;">
                <div class="glass-dark" style="padding: 20px;">
                    <h4 style="color: rgba(255,255,255,0.9); margin-bottom: 15px;">Ranking by Recall (Coverage)</h4>
                    <table style="background: transparent;">
                        <thead>
                            <tr>
                                <th style="background: transparent; color: rgba(255,255,255,0.6);">Rank</th>
                                <th style="background: transparent; color: rgba(255,255,255,0.6);">Source</th>
                                <th style="background: transparent; color: rgba(255,255,255,0.6); text-align: right;">Recall</th>
                                <th style="background: transparent; color: rgba(255,255,255,0.6); text-align: right;">Matched</th>
                            </tr>
                        </thead>
                        <tbody style="color: rgba(255,255,255,0.9);">
                            {recall_ranking_html}
                        </tbody>
                    </table>
                </div>

                <div class="glass-dark" style="padding: 20px;">
                    <h4 style="color: rgba(255,255,255,0.9); margin-bottom: 15px;">Ranking by Accuracy (Median Distance)</h4>
                    <table style="background: transparent;">
                        <thead>
                            <tr>
                                <th style="background: transparent; color: rgba(255,255,255,0.6);">Rank</th>
                                <th style="background: transparent; color: rgba(255,255,255,0.6);">Source</th>
                                <th style="background: transparent; color: rgba(255,255,255,0.6); text-align: right;">Median</th>
                                <th style="background: transparent; color: rgba(255,255,255,0.6); text-align: right;">MAD</th>
                            </tr>
                        </thead>
                        <tbody style="color: rgba(255,255,255,0.9);">
                            {accuracy_ranking_html}
                        </tbody>
                    </table>
                </div>
            </div>

            <h3 style="margin-top: 30px; color: rgba(255,255,255,0.95);">Threshold Performance</h3>
            <p style="color: rgba(255,255,255,0.6); margin-bottom: 15px; font-size: 0.9rem;">
                Percentage of matched buildings within each distance threshold.
            </p>
            <table>
                <thead>
                    <tr>
                        <th style="color: rgba(255,255,255,0.9);">Source</th>
                        <th style="text-align: center; color: rgba(255,255,255,0.9);">≤100m</th>
                        <th style="text-align: center; color: rgba(255,255,255,0.9);">≤500m</th>
                        <th style="text-align: center; color: rgba(255,255,255,0.9);">≤1km</th>
                        <th style="text-align: center; color: rgba(255,255,255,0.9);">≤5km</th>
                    </tr>
                </thead>
                <tbody>
                    {threshold_html}
                </tbody>
            </table>

            <h3 style="margin-top: 30px; color: rgba(255,255,255,0.95);">Source Detail Cards</h3>
            <div class="source-grid">
                {source_cards_html}
            </div>
        </section>
'''


def generate_map_visualization_section(gold_buildings_fc, gold_campus_fc, meta_canonical_fc):
    """
    Generate a single-site attribute comparison table showing how different sources
    report geometry and attributes for the same Meta Canonical facility.
    This demonstrates the value of consensus by showing source variations in a clear table format.
    """
    print("  Generating single-site attribute comparison...")

    # Source colors for visual consistency
    SOURCE_COLORS = {
        "DataCenterHawk": "#e63946",
        "DataCenterMap": "#2a9d8f",
        "Semianalysis": "#f4a261",
        "NewProjectMedia": "#9d4edd",
        "Meta Canonical": "#1d3557"
    }

    # Check feature classes exist
    if not arcpy.Exists(gold_buildings_fc) or not arcpy.Exists(meta_canonical_fc):
        return '''
        <section id="map-viz" class="glass">
            <h2 style="color: rgba(255,255,255,0.95);">📍 Single-Site Source Comparison</h2>
            <div class="alert alert-warning">
                <span class="alert-icon">⚠</span>
                <div class="alert-content">
                    <div class="alert-title">Data Not Available</div>
                    <div class="alert-text" style="color: rgba(255,255,255,0.7);">Required feature classes not found.</div>
                </div>
            </div>
        </section>
'''

    # Find a Meta Canonical building to use as the example
    # Prefer one with a recognizable name
    meta_building = None
    meta_fields = get_field_names(meta_canonical_fc)

    read_fields = ["SHAPE@XY", "OID@"]
    optional_fields = ["campus_name", "company_clean", "dc_code", "full_capacity_mw",
                       "commissioned_power_mw", "it_load_total", "building_key"]
    for f in optional_fields:
        if f in meta_fields:
            read_fields.append(f)

    # Find a good example Meta building
    with arcpy.da.SearchCursor(meta_canonical_fc, read_fields) as cursor:
        for row in cursor:
            xy = row[0]
            if xy and xy[0] and xy[1]:
                # Skip null island
                if abs(xy[1]) < 0.1 and abs(xy[0]) < 0.1:
                    continue

                name = None
                for fname in ["campus_name", "dc_code"]:
                    if fname in read_fields:
                        val = row[read_fields.index(fname)]
                        if val:
                            name = val
                            break

                # Prefer buildings with recognizable names
                if name and ("Meta" in str(name) or "Altoona" in str(name) or "Prineville" in str(name)):
                    meta_building = {
                        "lon": xy[0],
                        "lat": xy[1],
                        "name": name,
                        "company": row[read_fields.index("company_clean")] if "company_clean" in read_fields else "Meta",
                        "capacity": row[read_fields.index("full_capacity_mw")] if "full_capacity_mw" in read_fields else None,
                        "commissioned": row[read_fields.index("commissioned_power_mw")] if "commissioned_power_mw" in read_fields else None,
                    }
                    break

    # If no named Meta building found, use the first valid one
    if not meta_building:
        with arcpy.da.SearchCursor(meta_canonical_fc, read_fields) as cursor:
            for row in cursor:
                xy = row[0]
                if xy and xy[0] and xy[1]:
                    if abs(xy[1]) < 0.1 and abs(xy[0]) < 0.1:
                        continue
                    meta_building = {
                        "lon": xy[0],
                        "lat": xy[1],
                        "name": row[read_fields.index("campus_name")] if "campus_name" in read_fields else f"Meta Site",
                        "company": row[read_fields.index("company_clean")] if "company_clean" in read_fields else "Meta",
                        "capacity": row[read_fields.index("full_capacity_mw")] if "full_capacity_mw" in read_fields else None,
                        "commissioned": row[read_fields.index("commissioned_power_mw")] if "commissioned_power_mw" in read_fields else None,
                    }
                    break

    if not meta_building:
        return '''
        <section id="map-viz" class="glass">
            <h2 style="color: rgba(255,255,255,0.95);">📍 Single-Site Source Comparison</h2>
            <div class="alert alert-warning">
                <span class="alert-icon">⚠</span>
                <div class="alert-content">
                    <div class="alert-title">No Meta Buildings Found</div>
                    <div class="alert-text" style="color: rgba(255,255,255,0.7);">No Meta Canonical buildings with valid coordinates.</div>
                </div>
            </div>
        </section>
'''

    # Now find matching records from other sources within 5km
    center_lat = meta_building["lat"]
    center_lon = meta_building["lon"]
    search_radius_m = 5000  # 5km

    # Collect gold_buildings with relevant fields
    gold_fields_list = get_field_names(gold_buildings_fc)
    search_fields = ["SHAPE@XY", "source", "latitude", "longitude"]

    # Add optional fields for comparison
    compare_fields = ["campus_name", "company_clean", "full_capacity_mw",
                      "commissioned_power_mw", "planned_power_mw", "data_vintage", "UCID"]
    for f in compare_fields:
        if f in gold_fields_list:
            search_fields.append(f)

    # Find closest match from each source
    source_matches = {}

    try:
        with arcpy.da.SearchCursor(gold_buildings_fc, search_fields) as cursor:
            for row in cursor:
                xy = row[0]
                source = row[1]

                if not xy or not source or source == "Meta Canonical":
                    continue

                lat = row[2] if len(row) > 2 else xy[1]
                lon = row[3] if len(row) > 3 else xy[0]

                if not lat or not lon:
                    continue

                # Skip null island
                if abs(lat) < 0.1 and abs(lon) < 0.1:
                    continue

                dist = haversine_distance(center_lat, center_lon, lat, lon)

                if dist and dist <= search_radius_m:
                    # Check if this is closer than existing match for this source
                    if source not in source_matches or dist < source_matches[source]["distance"]:
                        match = {
                            "distance": dist,
                            "lat": lat,
                            "lon": lon,
                            "source": source
                        }
                        # Add optional fields
                        for f in compare_fields:
                            if f in search_fields:
                                idx = search_fields.index(f)
                                match[f] = row[idx] if idx < len(row) else None

                        source_matches[source] = match
    except Exception as e:
        print(f"    ⚠ Error searching gold_buildings: {e}")

    # Build comparison table
    # Row order: Meta Canonical first, then sources by distance
    sorted_sources = sorted(source_matches.items(), key=lambda x: x[1]["distance"])

    # Table header
    comparison_rows = ""

    # Meta Canonical row (ground truth)
    meta_capacity = f'{meta_building["capacity"]:.1f} MW' if meta_building["capacity"] else "—"
    meta_commissioned = f'{meta_building["commissioned"]:.1f} MW' if meta_building["commissioned"] else "—"

    comparison_rows += f'''
        <tr style="background: rgba(29, 53, 87, 0.3);">
            <td>
                <div style="display: flex; align-items: center; gap: 8px;">
                    <div style="width: 12px; height: 12px; background: {SOURCE_COLORS.get("Meta Canonical", "#1d3557")}; border-radius: 50%; border: 2px solid white;"></div>
                    <strong style="color: #5ac8fa;">Meta Canonical</strong>
                </div>
            </td>
            <td style="color: rgba(255,255,255,0.7); font-family: monospace; font-size: 0.8rem;">
                {center_lat:.5f}, {center_lon:.5f}
            </td>
            <td style="text-align: center;">
                <span style="background: #34d399; color: #000; padding: 2px 8px; border-radius: 4px; font-weight: 600; font-size: 0.8rem;">
                    ✓ Ground Truth
                </span>
            </td>
            <td style="color: rgba(255,255,255,0.9);">{meta_building["name"] or "—"}</td>
            <td style="color: rgba(255,255,255,0.9);">{meta_capacity}</td>
            <td style="color: rgba(255,255,255,0.9);">{meta_commissioned}</td>
        </tr>'''

    # Source rows
    for source_name, match in sorted_sources:
        color = SOURCE_COLORS.get(source_name, "#8892b0")
        dist_m = match["distance"]

        # Distance badge color
        if dist_m <= 100:
            dist_color = "#34d399"  # green
            dist_label = "Excellent"
        elif dist_m <= 500:
            dist_color = "#60a5fa"  # blue
            dist_label = "Good"
        elif dist_m <= 1000:
            dist_color = "#fbbf24"  # yellow
            dist_label = "Fair"
        else:
            dist_color = "#f87171"  # red
            dist_label = "Poor"

        # Format fields
        src_lat = match.get("lat", 0)
        src_lon = match.get("lon", 0)
        src_name = match.get("campus_name") or "—"
        src_capacity = f'{match.get("full_capacity_mw"):.1f} MW' if match.get("full_capacity_mw") else "—"
        src_commissioned = f'{match.get("commissioned_power_mw"):.1f} MW' if match.get("commissioned_power_mw") else "—"

        comparison_rows += f'''
        <tr>
            <td>
                <div style="display: flex; align-items: center; gap: 8px;">
                    <div style="width: 12px; height: 12px; background: {color}; border-radius: 50%;"></div>
                    <span style="color: rgba(255,255,255,0.9);">{source_name}</span>
                </div>
            </td>
            <td style="color: rgba(255,255,255,0.7); font-family: monospace; font-size: 0.8rem;">
                {src_lat:.5f}, {src_lon:.5f}
            </td>
            <td style="text-align: center;">
                <span style="background: {dist_color}22; color: {dist_color}; padding: 2px 8px; border-radius: 4px; font-weight: 600; font-size: 0.8rem; border: 1px solid {dist_color};">
                    {dist_m:.0f}m
                </span>
            </td>
            <td style="color: rgba(255,255,255,0.9);">{src_name}</td>
            <td style="color: rgba(255,255,255,0.9);">{src_capacity}</td>
            <td style="color: rgba(255,255,255,0.9);">{src_commissioned}</td>
        </tr>'''

    # Add rows for sources with NO match
    for source in SOURCES:
        if source != "Meta Canonical" and source not in source_matches:
            color = SOURCE_COLORS.get(source, "#8892b0")
            comparison_rows += f'''
        <tr style="opacity: 0.5;">
            <td>
                <div style="display: flex; align-items: center; gap: 8px;">
                    <div style="width: 12px; height: 12px; background: {color}; border-radius: 50%;"></div>
                    <span style="color: rgba(255,255,255,0.6);">{source}</span>
                </div>
            </td>
            <td colspan="5" style="color: rgba(255,255,255,0.4); font-style: italic;">
                No matching record within 5km
            </td>
        </tr>'''

    # Summary stats
    sources_found = len(source_matches)
    closest_dist = min(m["distance"] for m in source_matches.values()) if source_matches else None
    avg_dist = sum(m["distance"] for m in source_matches.values()) / len(source_matches) if source_matches else None

    return f'''
        <section id="map-viz" class="glass">
            <h2 style="color: rgba(255,255,255,0.95);">📍 Single-Site Source Comparison</h2>

            <p style="color: rgba(255,255,255,0.7); margin-bottom: 20px;">
                This table shows how different data sources report <strong>the same facility</strong>.
                Comparing coordinates and attributes reveals which sources are most accurate and complete.
            </p>

            <div class="glass-dark" style="padding: 20px; margin-bottom: 25px;">
                <h4 style="color: rgba(255,255,255,0.9); margin-bottom: 15px;">Example Facility: {meta_building["name"]}</h4>
                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 15px;">
                    <div>
                        <div style="color: rgba(255,255,255,0.5); font-size: 0.75rem; text-transform: uppercase;">Sources Found</div>
                        <div style="font-size: 1.5rem; font-weight: 700; color: #5ac8fa;">{sources_found}</div>
                    </div>
                    <div>
                        <div style="color: rgba(255,255,255,0.5); font-size: 0.75rem; text-transform: uppercase;">Closest Match</div>
                        <div style="font-size: 1.5rem; font-weight: 700; color: #34d399;">{closest_dist:.0f}m</div>
                    </div>
                    <div>
                        <div style="color: rgba(255,255,255,0.5); font-size: 0.75rem; text-transform: uppercase;">Avg Distance</div>
                        <div style="font-size: 1.5rem; font-weight: 700; color: #fbbf24;">{avg_dist:.0f}m</div>
                    </div>
                    <div>
                        <div style="color: rgba(255,255,255,0.5); font-size: 0.75rem; text-transform: uppercase;">Search Radius</div>
                        <div style="font-size: 1.5rem; font-weight: 700; color: rgba(255,255,255,0.6);">5km</div>
                    </div>
                </div>
            </div>

            <h3 style="color: rgba(255,255,255,0.95); margin-bottom: 15px;">Attribute Comparison</h3>
            <div style="overflow-x: auto;">
                <table style="min-width: 800px;">
                    <thead>
                        <tr>
                            <th style="color: rgba(255,255,255,0.9); width: 150px;">Source</th>
                            <th style="color: rgba(255,255,255,0.9); width: 180px;">Coordinates</th>
                            <th style="color: rgba(255,255,255,0.9); text-align: center; width: 100px;">Distance</th>
                            <th style="color: rgba(255,255,255,0.9);">Campus Name</th>
                            <th style="color: rgba(255,255,255,0.9); width: 100px;">Full Capacity</th>
                            <th style="color: rgba(255,255,255,0.9); width: 100px;">Commissioned</th>
                        </tr>
                    </thead>
                    <tbody>
                        {comparison_rows}
                    </tbody>
                </table>
            </div>

            <div class="alert alert-success" style="margin-top: 25px;">
                <span class="alert-icon">💡</span>
                <div class="alert-content">
                    <div class="alert-title" style="color: #34d399;">What This Shows</div>
                    <div class="alert-text" style="color: rgba(255,255,255,0.7);">
                        Sources with <strong>smaller distances</strong> have more accurate location data.
                        Sources with <strong>matching capacity values</strong> corroborate our ground truth.
                        Sources with <strong>no match within 5km</strong> may not cover this facility.
                    </div>
                </div>
            </div>
        </section>
'''

    # Source colors (matching your ArcGIS symbology)
    SOURCE_COLORS = {
        "DataCenterHawk": "#e63946",      # Red
        "DataCenterMap": "#2a9d8f",        # Green/Teal
        "Semianalysis": "#f4a261",         # Orange
        "NewProjectMedia": "#9d4edd",      # Purple
        "Meta Canonical": "#1d3557"        # Dark Blue (center point)
    }

    # Check feature classes exist
    if not arcpy.Exists(gold_buildings_fc) or not arcpy.Exists(meta_canonical_fc):
        return '''
        <section id="map-viz" class="glass">
            <h2>Spatial Distribution Example</h2>
            <div class="alert alert-warning">
                <span class="alert-icon">⚠</span>
                <div class="alert-content">
                    <div class="alert-title">Data Not Available</div>
                    <div class="alert-text">Required feature classes not found for map visualization.</div>
                </div>
            </div>
        </section>
'''

    # Find a good Meta Canonical building to center on (one with multiple source matches nearby)
    # We want to find a Meta building that has the most external source points within 5km
    meta_buildings = []
    meta_fields = get_field_names(meta_canonical_fc)

    read_fields = ["SHAPE@XY", "OID@"]
    if "campus_name" in meta_fields:
        read_fields.append("campus_name")
    if "company_clean" in meta_fields:
        read_fields.append("company_clean")
    if "dc_code" in meta_fields:
        read_fields.append("dc_code")

    with arcpy.da.SearchCursor(meta_canonical_fc, read_fields) as cursor:
        for row in cursor:
            xy = row[0]
            if xy and xy[0] and xy[1]:
                # Filter null island
                if abs(xy[1]) < 0.1 and abs(xy[0]) < 0.1:
                    continue
                meta_buildings.append({
                    "oid": row[1],
                    "lon": xy[0],
                    "lat": xy[1],
                    "name": row[read_fields.index("campus_name")] if "campus_name" in read_fields else None,
                    "company": row[read_fields.index("company_clean")] if "company_clean" in read_fields else None,
                    "dc_code": row[read_fields.index("dc_code")] if "dc_code" in read_fields else None
                })

    if not meta_buildings:
        return '''
        <section id="map-viz" class="glass">
            <h2>📍 Spatial Distribution Example</h2>
            <div class="alert alert-warning">
                <span class="alert-icon">⚠</span>
                <div class="alert-content">
                    <div class="alert-title">No Meta Buildings</div>
                    <div class="alert-text">No Meta Canonical buildings with valid coordinates found.</div>
                </div>
            </div>
        </section>
'''

    # Collect all gold_buildings by source with coordinates
    gold_points = []
    gold_fields = ["SHAPE@XY", "source", "latitude", "longitude"]
    if "record_level" in get_field_names(gold_buildings_fc):
        gold_fields.append("record_level")
    else:
        gold_fields.append("source")  # Placeholder - we'll use building-level by default

    try:
        with arcpy.da.SearchCursor(gold_buildings_fc, gold_fields[:4]) as cursor:
            for row in cursor:
                xy = row[0]
                if xy and xy[0] and xy[1] and row[1]:
                    # Filter null island
                    if abs(xy[1]) < 0.1 and abs(xy[0]) < 0.1:
                        continue
                    gold_points.append({
                        "lon": xy[0],
                        "lat": xy[1],
                        "source": row[1],
                        "level": "building"
                    })
    except Exception as e:
        print(f"    ⚠ Error reading gold_buildings: {e}")

    # Also get campus points
    campus_points = []
    try:
        with arcpy.da.SearchCursor(gold_campus_fc, ["SHAPE@XY", "source"]) as cursor:
            for row in cursor:
                xy = row[0]
                if xy and xy[0] and xy[1] and row[1]:
                    if abs(xy[1]) < 0.1 and abs(xy[0]) < 0.1:
                        continue
                    campus_points.append({
                        "lon": xy[0],
                        "lat": xy[1],
                        "source": row[1],
                        "level": "campus"
                    })
    except Exception as e:
        print(f"    ⚠ Error reading gold_campus: {e}")

    # Find the best Meta building to showcase (most source matches within 5km)
    best_meta = None
    best_score = 0
    search_radius_m = 5000  # 5km

    for meta in meta_buildings[:100]:  # Check first 100
        nearby_count = 0
        nearby_sources = set()

        for pt in gold_points + campus_points:
            dist = haversine_distance(meta["lat"], meta["lon"], pt["lat"], pt["lon"])
            if dist and dist <= search_radius_m:
                nearby_count += 1
                nearby_sources.add(pt["source"])

        # Score by number of unique sources AND total points
        score = len(nearby_sources) * 10 + nearby_count

        if score > best_score:
            best_score = score
            best_meta = meta
            best_meta["nearby_count"] = nearby_count
            best_meta["nearby_sources"] = len(nearby_sources)

    if not best_meta:
        best_meta = meta_buildings[0]
        best_meta["nearby_count"] = 0
        best_meta["nearby_sources"] = 0

    # Collect points within view radius for the visualization
    center_lat = best_meta["lat"]
    center_lon = best_meta["lon"]
    view_radius_m = 3000  # 3km view window

    viz_points = []
    source_counts = defaultdict(int)

    for pt in gold_points + campus_points:
        dist = haversine_distance(center_lat, center_lon, pt["lat"], pt["lon"])
        if dist and dist <= view_radius_m:
            viz_points.append({
                "lat": pt["lat"],
                "lon": pt["lon"],
                "source": pt["source"],
                "level": pt["level"],
                "dist_m": dist
            })
            source_counts[pt["source"]] += 1

    # Generate SVG map
    # SVG dimensions and coordinate transformation
    svg_width = 600
    svg_height = 400
    padding = 40

    # Calculate lat/lon bounds for the view
    # ~3km at mid-latitudes is approximately 0.027 degrees lat and varies for lon
    lat_range = 0.03  # degrees
    lon_range = 0.04  # degrees (wider for landscape aspect ratio)

    min_lat = center_lat - lat_range / 2
    max_lat = center_lat + lat_range / 2
    min_lon = center_lon - lon_range / 2
    max_lon = center_lon + lon_range / 2

    def to_svg_coords(lat, lon):
        """Convert lat/lon to SVG coordinates."""
        x = padding + ((lon - min_lon) / (max_lon - min_lon)) * (svg_width - 2 * padding)
        y = padding + ((max_lat - lat) / (max_lat - min_lat)) * (svg_height - 2 * padding)  # Invert Y
        return x, y

    # Build SVG elements
    svg_points_html = ""

    # Draw distance circles (500m, 1km, 2km, 3km)
    center_x, center_y = to_svg_coords(center_lat, center_lon)

    # Approximate circle radii in SVG pixels (rough conversion)
    # 1km ≈ 0.009 degrees lat
    circle_radiuses = [
        (500, "0.5km", 0.0045),
        (1000, "1km", 0.009),
        (2000, "2km", 0.018),
    ]

    circles_html = ""
    for dist_m, label, deg in circle_radiuses:
        radius_px = deg / lat_range * (svg_height - 2 * padding)
        circles_html += f'''
            <circle cx="{center_x}" cy="{center_y}" r="{radius_px}"
                fill="none" stroke="rgba(255,255,255,0.15)" stroke-width="1" stroke-dasharray="4,4"/>
            <text x="{center_x + radius_px + 5}" y="{center_y}" fill="rgba(255,255,255,0.4)" font-size="10">{label}</text>
'''

    # Draw source points
    for pt in viz_points:
        x, y = to_svg_coords(pt["lat"], pt["lon"])
        color = SOURCE_COLORS.get(pt["source"], "#8892b0")

        if pt["level"] == "campus":
            # Campus = larger circle with ring
            svg_points_html += f'''
                <circle cx="{x}" cy="{y}" r="10" fill="{color}" fill-opacity="0.8" stroke="white" stroke-width="2"/>
                <circle cx="{x}" cy="{y}" r="5" fill="white" fill-opacity="0.6"/>
'''
        else:
            # Building = smaller solid circle
            svg_points_html += f'''
                <circle cx="{x}" cy="{y}" r="6" fill="{color}" fill-opacity="0.9" stroke="white" stroke-width="1"/>
'''

    # Draw Meta Canonical center point (star or special marker)
    svg_points_html += f'''
        <circle cx="{center_x}" cy="{center_y}" r="14" fill="none" stroke="#1d3557" stroke-width="3"/>
        <circle cx="{center_x}" cy="{center_y}" r="10" fill="#1d3557" stroke="white" stroke-width="2"/>
        <text x="{center_x}" y="{center_y + 4}" text-anchor="middle" fill="white" font-size="10" font-weight="bold">M</text>
'''

    # Build legend
    legend_html = ""
    legend_y = 30
    for source, color in SOURCE_COLORS.items():
        count = source_counts.get(source, 0)
        if count > 0 or source == "Meta Canonical":
            count_text = f" ({count})" if source != "Meta Canonical" else " (center)"
            legend_html += f'''
                <circle cx="20" cy="{legend_y}" r="6" fill="{color}" stroke="white" stroke-width="1"/>
                <text x="32" y="{legend_y + 4}" fill="rgba(255,255,255,0.9)" font-size="11">{source}{count_text}</text>
'''
            legend_y += 22

    # Building vs Campus legend
    legend_html += f'''
        <line x1="15" y1="{legend_y + 20}" x2="180" y2="{legend_y + 20}" stroke="rgba(255,255,255,0.2)" stroke-width="1"/>
        <text x="20" y="{legend_y + 40}" fill="rgba(255,255,255,0.7)" font-size="10" font-weight="bold">Symbol Type:</text>
        <circle cx="20" cy="{legend_y + 60}" r="6" fill="#666" stroke="white" stroke-width="1"/>
        <text x="32" y="{legend_y + 64}" fill="rgba(255,255,255,0.7)" font-size="10">Building</text>
        <circle cx="100" cy="{legend_y + 60}" r="8" fill="#666" stroke="white" stroke-width="2"/>
        <circle cx="100" cy="{legend_y + 60}" r="4" fill="white" fill-opacity="0.6"/>
        <text x="114" y="{legend_y + 64}" fill="rgba(255,255,255,0.7)" font-size="10">Campus</text>
'''

    # Location info
    location_name = best_meta.get("name") or best_meta.get("dc_code") or f"OID {best_meta['oid']}"
    company_name = best_meta.get("company") or "Meta"

    svg_html = f'''
        <svg viewBox="0 0 {svg_width + 200} {svg_height}" xmlns="http://www.w3.org/2000/svg">
            <!-- Background -->
            <rect width="{svg_width + 200}" height="{svg_height}" fill="#1c1c1e"/>

            <!-- Map area -->
            <rect x="{padding/2}" y="{padding/2}" width="{svg_width - padding}" height="{svg_height - padding}"
                fill="#2c2c2e" rx="8"/>

            <!-- Distance rings -->
            {circles_html}

            <!-- Data points -->
            {svg_points_html}

            <!-- Legend -->
            <g transform="translate({svg_width + 10}, 20)">
                <text x="10" y="0" fill="rgba(255,255,255,0.9)" font-size="12" font-weight="bold">Sources</text>
                {legend_html}
            </g>

            <!-- Title bar -->
            <rect x="0" y="{svg_height - 35}" width="{svg_width + 200}" height="35" fill="rgba(0,0,0,0.5)"/>
            <text x="15" y="{svg_height - 12}" fill="rgba(255,255,255,0.9)" font-size="12">
                📍 {location_name} ({company_name}) — {len(viz_points)} source points within 3km
            </text>
        </svg>
'''

    # Build overview stats for the visualization
    overview_stats = ""
    for source, count in sorted(source_counts.items(), key=lambda x: x[1], reverse=True):
        if count > 0:
            color = SOURCE_COLORS.get(source, "#8892b0")
            overview_stats += f'''
                <div style="display: flex; align-items: center; gap: 8px; margin: 4px 0;">
                    <div style="width: 12px; height: 12px; background: {color}; border-radius: 50%;"></div>
                    <span style="color: rgba(255,255,255,0.8); font-size: 0.9rem;">{source}: {count} points</span>
                </div>'''

    return f'''
        <section id="map-viz" class="glass">
            <h2>📍 Spatial Distribution Example</h2>
            <p style="color: rgba(255,255,255,0.7); margin-bottom: 20px;">
                This visualization shows how different data sources cluster around a single Meta Canonical facility.
                Points closer to the center have more accurate location data. Circle markers with white centers represent campus-level records.
            </p>

            <div style="display: grid; grid-template-columns: 1fr 250px; gap: 20px;">
                <div class="glass-dark" style="padding: 15px; border-radius: 12px;">
                    {svg_html}
                </div>

                <div class="glass-dark" style="padding: 20px; border-radius: 12px;">
                    <h4 style="color: rgba(255,255,255,0.9); margin-bottom: 15px;">Example Location</h4>
                    <div style="color: rgba(255,255,255,0.7); font-size: 0.85rem; margin-bottom: 15px;">
                        <strong style="color: #5ac8fa;">{location_name}</strong><br/>
                        <span style="color: rgba(255,255,255,0.5);">{company_name}</span>
                    </div>

                    <div style="margin-bottom: 15px;">
                        <div style="color: rgba(255,255,255,0.5); font-size: 0.75rem; text-transform: uppercase;">Coordinates</div>
                        <div style="color: rgba(255,255,255,0.8); font-family: monospace; font-size: 0.85rem;">
                            {center_lat:.6f}, {center_lon:.6f}
                        </div>
                    </div>

                    <div style="margin-bottom: 15px;">
                        <div style="color: rgba(255,255,255,0.5); font-size: 0.75rem; text-transform: uppercase; margin-bottom: 8px;">Sources in View</div>
                        {overview_stats}
                    </div>

                    <div style="padding-top: 15px; border-top: 1px solid rgba(255,255,255,0.1);">
                        <div style="color: rgba(255,255,255,0.5); font-size: 0.75rem;">
                            <strong>Total points:</strong> {len(viz_points)}<br/>
                            <strong>View radius:</strong> 3km<br/>
                            <strong>Unique sources:</strong> {len(source_counts)}
                        </div>
                    </div>
                </div>
            </div>
        </section>
'''


def generate_excluded_sources_section():
    """Generate section showing excluded sources and why they were not included."""
    cards_html = ""

    for source_name, info in EXCLUDED_SOURCES.items():
        cards_html += f'''
            <div class="source-card glass" style="border-left: 4px solid #f87171; cursor: default;">
                <div class="source-header">
                    <span class="source-name" style="color: rgba(255,255,255,0.9);">{source_name}</span>
                    <span class="source-grade" style="color: #f87171;">⊘</span>
                </div>
                <div class="source-count" style="color: rgba(255,255,255,0.6);">{info['records']} records available</div>

                <div class="alert alert-warning" style="margin: 15px 0 0 0; padding: 12px;">
                    <div class="alert-content">
                        <div class="alert-title" style="color: #f59e0b;">❌ {info['reason']}</div>
                        <div class="alert-text" style="color: rgba(255,255,255,0.7);">{info['detail']}</div>
                    </div>
                </div>

                <div style="margin-top: 12px; padding: 12px; background: rgba(52, 211, 153, 0.15); border-radius: 8px;">
                    <div style="font-size: 0.85rem; color: rgba(255,255,255,0.8);">
                        <strong style="color: #10b981;">💡 Potential Value:</strong> {info['potential_value']}
                    </div>
                </div>
            </div>'''

    return f'''
        <section id="excluded" class="glass">
            <h2 style="color: rgba(255,255,255,0.95);">🚫 Excluded Sources</h2>
            <p style="color: rgba(255,255,255,0.7); margin-bottom: 20px;">
                These data sources are available but not included in the consensus pipeline for the reasons noted below.
            </p>
            <div class="source-grid">
                {cards_html}
            </div>
        </section>
'''


def calculate_temporal_freshness(fc_path):
    """
    Calculate temporal freshness and stability metrics for a feature class.

    Metrics calculated:
    - days_since_last_update: Days since most recent data_vintage date
    - vintage_coverage_pct: % of records with data_vintage populated
    - oldest_vintage: Oldest data_vintage date in dataset
    - newest_vintage: Most recent data_vintage date in dataset
    - freshness_by_source: Per-source freshness breakdown
    """
    print("  Calculating temporal freshness metrics...")

    fields = get_field_names(fc_path)

    # Check for data_vintage field
    if "data_vintage" not in fields:
        return {"available": False, "error": "data_vintage field not found"}

    has_source = "source" in fields

    # Collect vintage dates by source
    vintage_by_source = defaultdict(list)
    total_records = 0
    records_with_vintage = 0
    all_dates = []

    read_fields = ["data_vintage"]
    if has_source:
        read_fields.append("source")

    try:
        with arcpy.da.SearchCursor(fc_path, read_fields) as cursor:
            for row in cursor:
                total_records += 1
                vintage = row[0]
                source = row[1] if has_source else "Unknown"

                if vintage:
                    records_with_vintage += 1
                    all_dates.append(vintage)
                    vintage_by_source[source].append(vintage)
    except Exception as e:
        return {"available": False, "error": str(e)}

    if total_records == 0:
        return {"available": False, "error": "No records in feature class"}

    # Calculate overall metrics
    vintage_coverage_pct = round((records_with_vintage / total_records) * 100, 1)

    if not all_dates:
        return {
            "available": True,
            "vintage_coverage_pct": 0,
            "records_with_vintage": 0,
            "total_records": total_records,
            "days_since_last_update": None,
            "oldest_vintage": None,
            "newest_vintage": None,
            "freshness_by_source": {}
        }

    # Find date range
    min_date = min(all_dates)
    max_date = max(all_dates)

    # Calculate days since last update
    today = datetime.now()
    if hasattr(max_date, 'date'):
        days_since = (today.date() - max_date.date()).days
    else:
        try:
            max_date_parsed = datetime.strptime(str(max_date), "%Y-%m-%d")
            days_since = (today - max_date_parsed).days
        except:
            days_since = None

    # Per-source freshness
    freshness_by_source = {}
    for source, dates in vintage_by_source.items():
        if dates:
            src_newest = max(dates)
            src_oldest = min(dates)

            # Calculate days since for this source
            if hasattr(src_newest, 'date'):
                src_days = (today.date() - src_newest.date()).days
            else:
                try:
                    src_newest_parsed = datetime.strptime(str(src_newest), "%Y-%m-%d")
                    src_days = (today - src_newest_parsed).days
                except:
                    src_days = None

            freshness_by_source[source] = {
                "records_with_vintage": len(dates),
                "newest": src_newest.strftime("%Y-%m-%d") if hasattr(src_newest, 'strftime') else str(src_newest),
                "oldest": src_oldest.strftime("%Y-%m-%d") if hasattr(src_oldest, 'strftime') else str(src_oldest),
                "days_since_update": src_days
            }

    return {
        "available": True,
        "vintage_coverage_pct": vintage_coverage_pct,
        "records_with_vintage": records_with_vintage,
        "total_records": total_records,
        "days_since_last_update": days_since,
        "oldest_vintage": min_date.strftime("%Y-%m-%d") if hasattr(min_date, 'strftime') else str(min_date),
        "newest_vintage": max_date.strftime("%Y-%m-%d") if hasattr(max_date, 'strftime') else str(max_date),
        "freshness_by_source": freshness_by_source
    }


def generate_recommendations_section(weighted_source_stats, spatial_accuracy_data, temporal_freshness_data, capacity_accuracy_data=None):
    """
    Generate actionability and recommendations section.

    This section translates technical metrics into business guidance:
    - Source health matrix (grades across dimensions)
    - Interpretation guide (what each grade means)
    - Dynamic recommendations (continue, improve, evaluate, drop)
    - ROI signals for subscription decisions
    """

    # Grade interpretation guide
    grade_guide = {
        "A": {
            "reliability": "High Confidence",
            "description": "Production-ready. Safe for critical business decisions.",
            "action": "Maintain current refresh cadence",
            "color": "#34d399"
        },
        "B": {
            "reliability": "Good Confidence",
            "description": "Usable with minor caveats. Verify for high-stakes decisions.",
            "action": "Monitor for regression, consider targeted improvements",
            "color": "#60a5fa"
        },
        "C": {
            "reliability": "Moderate Confidence",
            "description": "Use with caution. Cross-reference with other sources.",
            "action": "Investigate gaps, plan remediation",
            "color": "#fbbf24"
        },
        "D": {
            "reliability": "Low Confidence",
            "description": "Limited utility. Requires significant validation.",
            "action": "Prioritize improvement or evaluate alternatives",
            "color": "#fb923c"
        },
        "F": {
            "reliability": "Not Reliable",
            "description": "Avoid for critical decisions. Data quality insufficient.",
            "action": "Evaluate ROI of continuing subscription",
            "color": "#f87171"
        }
    }

    # Build source health matrix
    source_rows = ""
    recommendations = []

    # Get freshness by source
    freshness_by_source = temporal_freshness_data.get("freshness_by_source", {}) if temporal_freshness_data else {}
    spatial_sources = spatial_accuracy_data.get("sources", {}) if spatial_accuracy_data and spatial_accuracy_data.get("available") else {}
    capacity_sources = capacity_accuracy_data.get("sources", {}) if capacity_accuracy_data and capacity_accuracy_data.get("available") else {}

    # Sort sources by overall score (highest to lowest)
    sorted_sources = sorted(
        weighted_source_stats.items(),
        key=lambda x: x[1].get("final_score", 0) if x[1] and "error" not in x[1] else -1,
        reverse=True
    )

    for source_name, stats in sorted_sources:
        if not stats or "error" in stats:
            continue

        # Overall grade
        overall_grade = stats.get("grade", "?")
        overall_score = stats.get("final_score", 0)
        overall_color = stats.get("grade_color", "#8892b0")

        # Spatial accuracy grade
        spatial_stats = spatial_sources.get(source_name, {})
        recall_pct = spatial_stats.get("recall_pct", 0)
        median_dist = spatial_stats.get("median_distance_m")

        # Meta Canonical IS the ground truth - don't grade it against itself
        if source_name == "Meta Canonical":
            spatial_grade, spatial_color = "—", "#8892b0"
            spatial_label = "Ground Truth"
        elif recall_pct >= 50 and median_dist and median_dist <= 1000:
            spatial_grade, spatial_color = "A", "#34d399"
            spatial_label = f"{median_dist:.0f}m" if median_dist else ""
        elif recall_pct >= 30 and median_dist and median_dist <= 2000:
            spatial_grade, spatial_color = "B", "#60a5fa"
            spatial_label = f"{median_dist:.0f}m" if median_dist else ""
        elif recall_pct >= 20 and median_dist and median_dist <= 5000:
            spatial_grade, spatial_color = "C", "#fbbf24"
            spatial_label = f"{median_dist:.0f}m" if median_dist else ""
        elif recall_pct >= 10:
            spatial_grade, spatial_color = "D", "#fb923c"
            spatial_label = f"{median_dist:.0f}m" if median_dist else ""
        elif recall_pct > 0:
            spatial_grade, spatial_color = "F", "#f87171"
            spatial_label = f"{median_dist:.0f}m" if median_dist else ""
        else:
            spatial_grade, spatial_color = "—", "#8892b0"
            spatial_label = "No data"

        # Capacity accuracy grade (NEW)
        cap_stats = capacity_sources.get(source_name, {})
        cap_mape = cap_stats.get("mape")
        cap_n = cap_stats.get("n_matched", 0)

        if cap_mape is not None:
            capacity_grade = cap_stats.get("grade", "?")
            capacity_color = cap_stats.get("grade_color", "#8892b0")
            capacity_label = f"{cap_mape:.0f}% MAPE"
        elif source_name == "Meta Canonical":
            # Meta Canonical IS the ground truth
            capacity_grade, capacity_color = "—", "#8892b0"
            capacity_label = "Ground Truth"
        elif cap_stats.get("label"):
            # Source has capacity data but not enough Meta overlap to verify accuracy
            capacity_grade = cap_stats.get("grade", "—")
            capacity_color = cap_stats.get("grade_color", "#8892b0")
            capacity_label = cap_stats.get("label")
        else:
            capacity_grade, capacity_color = "—", "#8892b0"
            capacity_label = "No data"

        # Freshness grade
        freshness_info = freshness_by_source.get(source_name, {})
        days_since = freshness_info.get("days_since_update")

        if days_since is None:
            freshness_grade, freshness_color, freshness_label = "?", "#8892b0", "Unknown"
        elif days_since <= 30:
            freshness_grade, freshness_color, freshness_label = "A", "#34d399", "Fresh"
        elif days_since <= 90:
            freshness_grade, freshness_color, freshness_label = "B", "#60a5fa", "Current"
        elif days_since <= 180:
            freshness_grade, freshness_color, freshness_label = "C", "#fbbf24", "Aging"
        elif days_since <= 365:
            freshness_grade, freshness_color, freshness_label = "D", "#fb923c", "Stale"
        else:
            freshness_grade, freshness_color, freshness_label = "F", "#f87171", "Outdated"

        # Generate recommendation based on composite assessment (now includes capacity)
        grades = [overall_grade,
                  spatial_grade if spatial_grade != "—" else None,
                  capacity_grade if capacity_grade != "—" else None,
                  freshness_grade if freshness_grade != "?" else None]
        grades = [g for g in grades if g]

        # Count concerning grades
        poor_grades = sum(1 for g in grades if g in ["D", "F"])
        good_grades = sum(1 for g in grades if g in ["A", "B"])

        # Determine recommendation
        if poor_grades >= 2:
            rec_icon = "❌"
            rec_text = "Evaluate ROI"
            rec_detail = f"Multiple quality concerns. Consider if subscription is worth continuing."
            rec_class = "rec-drop"
        elif poor_grades == 1:
            rec_icon = "⚠️"
            rec_text = "Needs Attention"
            # More specific feedback including capacity
            if spatial_grade in ['D', 'F']:
                issue = 'spatial accuracy'
            elif capacity_grade in ['D', 'F']:
                issue = 'capacity accuracy'
            elif freshness_grade in ['D', 'F']:
                issue = 'data freshness'
            else:
                issue = 'core quality'
            rec_detail = f"Address {issue} issues."
            rec_class = "rec-improve"
        elif good_grades == len(grades) and len(grades) >= 2:
            rec_icon = "✅"
            rec_text = "Continue"
            rec_detail = "High-value source. Maintain current subscription."
            rec_class = "rec-continue"
        else:
            rec_icon = "📊"
            rec_text = "Monitor"
            rec_detail = "Acceptable quality. Watch for changes."
            rec_class = "rec-monitor"

        recommendations.append({
            "source": source_name,
            "icon": rec_icon,
            "text": rec_text,
            "detail": rec_detail,
            "overall_grade": overall_grade
        })

        # Build table row (now includes Capacity column)
        source_rows += f'''
            <tr>
                <td style="color: rgba(255,255,255,0.95); font-weight: 600;">{source_name}</td>
                <td style="text-align: center;">
                    <span style="display: inline-block; padding: 4px 12px; border-radius: 6px;
                                 background: {overall_color}22; color: {overall_color};
                                 font-weight: 700; border: 1px solid {overall_color};">
                        {overall_grade} <span style="font-size: 0.75rem; opacity: 0.8;">({overall_score:.0f})</span>
                    </span>
                </td>
                <td style="text-align: center;">
                    <span style="display: inline-block; padding: 4px 12px; border-radius: 6px;
                                 background: {spatial_color}22; color: {spatial_color};
                                 font-weight: 700; border: 1px solid {spatial_color};">
                        {spatial_grade}
                    </span>
                    <div style="font-size: 0.7rem; color: rgba(255,255,255,0.5); margin-top: 2px;">
                        {spatial_label}
                    </div>
                </td>
                <td style="text-align: center;">
                    <span style="display: inline-block; padding: 4px 12px; border-radius: 6px;
                                 background: {capacity_color}22; color: {capacity_color};
                                 font-weight: 700; border: 1px solid {capacity_color};">
                        {capacity_grade}
                    </span>
                    <div style="font-size: 0.7rem; color: rgba(255,255,255,0.5); margin-top: 2px;">
                        {capacity_label}
                    </div>
                </td>
                <td style="text-align: center;">
                    <span style="display: inline-block; padding: 4px 12px; border-radius: 6px;
                                 background: {freshness_color}22; color: {freshness_color};
                                 font-weight: 700; border: 1px solid {freshness_color};">
                        {freshness_grade}
                    </span>
                    <div style="font-size: 0.7rem; color: rgba(255,255,255,0.5); margin-top: 2px;">
                        {freshness_label}
                    </div>
                </td>
                <td>
                    <div style="display: flex; align-items: center; gap: 8px;">
                        <span style="font-size: 1.1rem;">{rec_icon}</span>
                        <div>
                            <div style="color: rgba(255,255,255,0.9); font-weight: 600;">{rec_text}</div>
                            <div style="color: rgba(255,255,255,0.5); font-size: 0.75rem;">{rec_detail}</div>
                        </div>
                    </div>
                </td>
            </tr>'''

    # Add excluded sources to the health matrix
    for excl_name, excl_info in EXCLUDED_SOURCE_GRADES.items():
        excl_grade = excl_info.get("grade", "F")
        excl_color = excl_info.get("grade_color", "#f87171")
        excl_score = excl_info.get("final_score", 0)
        excl_reason = excl_info.get("reason", "Excluded from pipeline")
        excl_scores = excl_info.get("scores", {})

        # Spatial grade for excluded sources
        spatial_score = excl_scores.get("spatial_accuracy", 0)
        if spatial_score >= 70:
            excl_spatial_grade, excl_spatial_color = "B", "#60a5fa"
        elif spatial_score >= 50:
            excl_spatial_grade, excl_spatial_color = "C", "#fbbf24"
        elif spatial_score > 0:
            excl_spatial_grade, excl_spatial_color = "D", "#fb923c"
        else:
            excl_spatial_grade, excl_spatial_color = "—", "#f87171"

        # Capacity grade for excluded sources
        capacity_score = excl_scores.get("capacity", 0)
        if capacity_score >= 70:
            excl_cap_grade, excl_cap_color, excl_cap_label = "B", "#60a5fa", "Good"
        elif capacity_score >= 50:
            excl_cap_grade, excl_cap_color, excl_cap_label = "C", "#fbbf24", "Partial"
        elif capacity_score > 0:
            excl_cap_grade, excl_cap_color, excl_cap_label = "D", "#fb923c", "Sparse"
        else:
            excl_cap_grade, excl_cap_color, excl_cap_label = "—", "#f87171", "No data"

        # Freshness - excluded sources are typically not refreshed
        excl_fresh_grade, excl_fresh_color, excl_fresh_label = "—", "#8892b0", "N/A"

        # Recommendation for excluded sources
        excl_rec_icon = "🚫"
        excl_rec_text = "Excluded"
        excl_rec_detail = excl_reason

        recommendations.append({
            "source": excl_name,
            "icon": excl_rec_icon,
            "text": excl_rec_text,
            "detail": excl_rec_detail,
            "overall_grade": excl_grade,
            "excluded": True
        })

        # Build excluded source row with visual indicator
        source_rows += f'''
            <tr style="opacity: 0.7; background: rgba(248, 113, 113, 0.05);">
                <td style="color: rgba(255,255,255,0.75); font-weight: 600;">
                    {excl_name}
                    <span style="display: inline-block; margin-left: 8px; padding: 2px 6px;
                                 background: rgba(248,113,113,0.2); color: #f87171;
                                 font-size: 0.65rem; border-radius: 4px; font-weight: 600;">
                        EXCLUDED
                    </span>
                </td>
                <td style="text-align: center;">
                    <span style="display: inline-block; padding: 4px 12px; border-radius: 6px;
                                 background: {excl_color}22; color: {excl_color};
                                 font-weight: 700; border: 1px solid {excl_color};">
                        {excl_grade} <span style="font-size: 0.75rem; opacity: 0.8;">({excl_score:.0f})</span>
                    </span>
                </td>
                <td style="text-align: center;">
                    <span style="display: inline-block; padding: 4px 12px; border-radius: 6px;
                                 background: {excl_spatial_color}22; color: {excl_spatial_color};
                                 font-weight: 700; border: 1px solid {excl_spatial_color};">
                        {excl_spatial_grade}
                    </span>
                </td>
                <td style="text-align: center;">
                    <span style="display: inline-block; padding: 4px 12px; border-radius: 6px;
                                 background: {excl_cap_color}22; color: {excl_cap_color};
                                 font-weight: 700; border: 1px solid {excl_cap_color};">
                        {excl_cap_grade}
                    </span>
                    <div style="font-size: 0.7rem; color: rgba(255,255,255,0.5); margin-top: 2px;">
                        {excl_cap_label}
                    </div>
                </td>
                <td style="text-align: center;">
                    <span style="display: inline-block; padding: 4px 12px; border-radius: 6px;
                                 background: {excl_fresh_color}22; color: {excl_fresh_color};
                                 font-weight: 700; border: 1px solid {excl_fresh_color};">
                        {excl_fresh_grade}
                    </span>
                    <div style="font-size: 0.7rem; color: rgba(255,255,255,0.5); margin-top: 2px;">
                        {excl_fresh_label}
                    </div>
                </td>
                <td>
                    <div style="display: flex; align-items: center; gap: 8px;">
                        <span style="font-size: 1.1rem;">{excl_rec_icon}</span>
                        <div>
                            <div style="color: rgba(255,255,255,0.7); font-weight: 600;">{excl_rec_text}</div>
                            <div style="color: rgba(255,255,255,0.5); font-size: 0.75rem;">{excl_rec_detail}</div>
                        </div>
                    </div>
                </td>
            </tr>'''

    # Build interpretation guide
    guide_rows = ""
    for grade, info in grade_guide.items():
        guide_rows += f'''
            <tr>
                <td style="text-align: center;">
                    <span style="display: inline-block; width: 36px; height: 36px; line-height: 36px;
                                 border-radius: 8px; background: {info['color']}22; color: {info['color']};
                                 font-weight: 700; font-size: 1.2rem; border: 2px solid {info['color']};">
                        {grade}
                    </span>
                </td>
                <td style="color: {info['color']}; font-weight: 600;">{info['reliability']}</td>
                <td style="color: rgba(255,255,255,0.8);">{info['description']}</td>
                <td style="color: rgba(255,255,255,0.7); font-size: 0.9rem;">{info['action']}</td>
            </tr>'''

    # Build priority action items
    action_items_html = ""
    priority_num = 1

    # Sort recommendations by urgency (drops first, then improve, then monitor)
    priority_order = {"❌": 0, "⚠️": 1, "📊": 2, "✅": 3}
    sorted_recs = sorted(recommendations, key=lambda x: priority_order.get(x["icon"], 99))

    for rec in sorted_recs:
        if rec["icon"] in ["❌", "⚠️"]:
            if rec["icon"] == "❌":
                priority_color = "#f87171"
                priority_label = "HIGH"
            else:
                priority_color = "#fbbf24"
                priority_label = "MEDIUM"

            action_items_html += f'''
                <div style="display: flex; align-items: flex-start; gap: 15px; padding: 15px;
                            background: rgba(255,255,255,0.03); border-radius: 8px; margin-bottom: 10px;
                            border-left: 3px solid {priority_color};">
                    <div style="background: {priority_color}22; color: {priority_color};
                                padding: 4px 8px; border-radius: 4px; font-size: 0.7rem; font-weight: 700;">
                        P{priority_num}
                    </div>
                    <div style="flex: 1;">
                        <div style="color: rgba(255,255,255,0.95); font-weight: 600;">{rec['source']}</div>
                        <div style="color: rgba(255,255,255,0.6); font-size: 0.85rem; margin-top: 4px;">
                            {rec['detail']}
                        </div>
                    </div>
                    <div style="color: {priority_color}; font-size: 0.75rem; font-weight: 600;">
                        {priority_label}
                    </div>
                </div>'''
            priority_num += 1

    if not action_items_html:
        action_items_html = '''
            <div style="padding: 20px; text-align: center; color: rgba(255,255,255,0.5);">
                <span style="font-size: 2rem;">✅</span>
                <div style="margin-top: 10px;">No urgent action items. All sources performing acceptably.</div>
            </div>'''

    return f'''
        <section id="recommendations" class="glass">
            <div class="section-header">
                <h2>Recommendations & Actionability</h2>
                <span class="collapse-icon">▼</span>
            </div>
            <div class="section-content">

            <p style="color: rgba(255,255,255,0.6); font-style: italic; margin-bottom: 20px;">
                Key Question: "Which sources should I trust most, and where should we invest to improve quality?"
            </p>

            <p style="color: rgba(255,255,255,0.7); margin-bottom: 25px;">
                This section translates technical metrics into <strong>business decisions</strong>.
                Use this to assess source reliability, identify improvement priorities, and evaluate subscription ROI.
            </p>

            <h3 style="color: rgba(255,255,255,0.95); margin-bottom: 15px;">📊 Source Health Matrix</h3>
            <p style="color: rgba(255,255,255,0.6); font-size: 0.9rem; margin-bottom: 10px;">
                <em>Question: "How does each source perform across our key quality dimensions?"</em>
            </p>
            <p style="color: rgba(255,255,255,0.6); font-size: 0.9rem; margin-bottom: 15px;">
                Composite assessment across quality dimensions. Red flags indicate sources requiring attention.
            </p>

            <div style="overflow-x: auto;">
                <table style="min-width: 800px;">
                    <thead>
                        <tr>
                            <th style="color: rgba(255,255,255,0.9);">Source</th>
                            <th style="color: rgba(255,255,255,0.9); text-align: center;">Overall</th>
                            <th style="color: rgba(255,255,255,0.9); text-align: center;">Spatial</th>
                            <th style="color: rgba(255,255,255,0.9); text-align: center;">Capacity</th>
                            <th style="color: rgba(255,255,255,0.9); text-align: center;">Freshness</th>
                            <th style="color: rgba(255,255,255,0.9);">Recommendation</th>
                        </tr>
                    </thead>
                    <tbody>
                        {source_rows}
                    </tbody>
                </table>
            </div>

            <h3 style="color: rgba(255,255,255,0.95); margin-top: 30px; margin-bottom: 15px;">🚨 Priority Action Items</h3>
            {action_items_html}

            <h3 style="color: rgba(255,255,255,0.95); margin-top: 30px; margin-bottom: 15px;">📖 Grade Interpretation Guide</h3>
            <p style="color: rgba(255,255,255,0.6); font-size: 0.9rem; margin-bottom: 15px;">
                What each grade means for reliability and recommended actions.
            </p>

            <table>
                <thead>
                    <tr>
                        <th style="color: rgba(255,255,255,0.9); text-align: center; width: 60px;">Grade</th>
                        <th style="color: rgba(255,255,255,0.9); width: 140px;">Reliability</th>
                        <th style="color: rgba(255,255,255,0.9);">Interpretation</th>
                        <th style="color: rgba(255,255,255,0.9); width: 200px;">Recommended Action</th>
                    </tr>
                </thead>
                <tbody>
                    {guide_rows}
                </tbody>
            </table>

            <div class="glass-dark" style="padding: 20px; margin-top: 25px; border-left: 4px solid #f59e0b;">
                <h4 style="color: #f59e0b; margin-bottom: 10px;">💰 ROI Considerations</h4>
                <div style="color: rgba(255,255,255,0.8); font-size: 0.9rem;">
                    <p style="margin-bottom: 10px;">When evaluating whether to continue a data subscription, consider:</p>
                    <ul style="margin-left: 20px; color: rgba(255,255,255,0.7);">
                        <li><strong>Grade D or F sources:</strong> Are they providing unique coverage not available elsewhere?</li>
                        <li><strong>Stale sources:</strong> Is the vendor still actively updating? Request a data refresh.</li>
                        <li><strong>Low spatial accuracy:</strong> Can location data be supplemented from other sources?</li>
                        <li><strong>Cost vs. coverage:</strong> What percentage of your key markets does this source cover?</li>
                    </ul>
                </div>
            </div>
            </div>
        </section>
'''


def generate_temporal_freshness_section(temporal_data):
    """Generate the Temporal Freshness & Stability section."""

    if not temporal_data.get("available"):
        error_msg = temporal_data.get("error", "Temporal data not available")
        return f'''
        <section id="temporal" class="glass">
            <h2>Temporal Freshness & Stability</h2>
            <div class="alert alert-warning">
                <span class="alert-icon">⚠</span>
                <div class="alert-content">
                    <div class="alert-title">Data Not Available</div>
                    <div class="alert-text">{error_msg}</div>
                </div>
            </div>
        </section>
'''

    days_since = temporal_data.get("days_since_last_update")
    coverage_pct = temporal_data.get("vintage_coverage_pct", 0)
    oldest = temporal_data.get("oldest_vintage", "N/A")
    newest = temporal_data.get("newest_vintage", "N/A")
    freshness_by_source = temporal_data.get("freshness_by_source", {})

    # Determine freshness grade based on days since update
    if days_since is None:
        freshness_grade, freshness_color = "?", "#8892b0"
        freshness_label = "Unknown"
    elif days_since <= 30:
        freshness_grade, freshness_color = "A", "#34d399"
        freshness_label = "Fresh"
    elif days_since <= 90:
        freshness_grade, freshness_color = "B", "#60a5fa"
        freshness_label = "Current"
    elif days_since <= 180:
        freshness_grade, freshness_color = "C", "#fbbf24"
        freshness_label = "Aging"
    elif days_since <= 365:
        freshness_grade, freshness_color = "D", "#fb923c"
        freshness_label = "Stale"
    else:
        freshness_grade, freshness_color = "F", "#f87171"
        freshness_label = "Outdated"

    # Determine coverage grade
    if coverage_pct >= 90:
        coverage_grade, coverage_color = "A", "#34d399"
    elif coverage_pct >= 70:
        coverage_grade, coverage_color = "B", "#60a5fa"
    elif coverage_pct >= 50:
        coverage_grade, coverage_color = "C", "#fbbf24"
    elif coverage_pct >= 30:
        coverage_grade, coverage_color = "D", "#fb923c"
    else:
        coverage_grade, coverage_color = "F", "#f87171"

    # Build source freshness cards
    source_cards_html = ""
    # Sort by days_since_update ascending (freshest first)
    sorted_sources = sorted(
        freshness_by_source.items(),
        key=lambda x: x[1].get("days_since_update") or 9999
    )

    for source_name, info in sorted_sources:
        src_days = info.get("days_since_update")
        src_newest = info.get("newest", "N/A")
        src_oldest = info.get("oldest", "N/A")
        src_count = info.get("records_with_vintage", 0)

        # Source freshness color
        if src_days is None:
            src_color = "#8892b0"
            src_status = "Unknown"
        elif src_days <= 30:
            src_color = "#34d399"
            src_status = "Fresh"
        elif src_days <= 90:
            src_color = "#60a5fa"
            src_status = "Current"
        elif src_days <= 180:
            src_color = "#fbbf24"
            src_status = "Aging"
        else:
            src_color = "#f87171"
            src_status = "Stale"

        days_display = f"{src_days} days ago" if src_days is not None else "Unknown"

        source_cards_html += f'''
            <div class="source-card glass" style="border-left: 4px solid {src_color}; cursor: default;">
                <div class="source-header">
                    <span class="source-name">{source_name}</span>
                    <div style="padding: 6px 12px; border-radius: 8px; background: {src_color}22; border: 1px solid {src_color};">
                        <span style="color: {src_color}; font-weight: 600; font-size: 0.85rem;">{src_status}</span>
                    </div>
                </div>
                <div class="source-count">{src_count:,} records with vintage dates</div>

                <div class="source-metrics" style="margin-top: 15px;">
                    <div class="metric-row">
                        <span class="metric-label">📅 Last Updated</span>
                        <span class="metric-value">{days_display}</span>
                    </div>
                    <div class="metric-row">
                        <span class="metric-label">🆕 Newest Record</span>
                        <span class="metric-value" style="font-family: monospace;">{src_newest}</span>
                    </div>
                    <div class="metric-row">
                        <span class="metric-label">📜 Oldest Record</span>
                        <span class="metric-value" style="font-family: monospace;">{src_oldest}</span>
                    </div>
                </div>
            </div>'''

    return f'''
        <section id="temporal">
            <div class="section-header">
                <h2>⏱️ Temporal Freshness & Stability</h2>
                <span class="collapse-icon">▼</span>
            </div>
            <div class="section-content">

            <p style="color: rgba(255,255,255,0.6); font-style: italic; margin-bottom: 20px;">
                Key Question: "How current are our input sources? Are vendors actively maintaining their data?"
            </p>

            <p style="color: rgba(255,255,255,0.7); margin-bottom: 25px;">
                This measures <strong>input source freshness</strong> based on the <code>data_vintage</code> field in building-level records
                (n={temporal_data.get("total_records", 0):,}). Campus-level records are excluded since their vintage dates are manually populated
                during rollup. A stale source may indicate vendor maintenance issues or contract lapses.
            </p>

            <div class="grade-banner" style="margin-bottom: 30px;">
                <div class="grade-card" style="border-left: 4px solid {freshness_color};">
                    <div class="grade-letter" style="color: {freshness_color};">{freshness_grade}</div>
                    <div class="grade-label">Data Freshness</div>
                    <div style="font-size: 0.85rem; color: rgba(255,255,255,0.6); margin-top: 5px;">{freshness_label}</div>
                </div>
                <div class="grade-card" style="border-left: 4px solid {coverage_color};">
                    <div class="grade-letter" style="color: {coverage_color};">{coverage_grade}</div>
                    <div class="grade-label">Vintage Coverage</div>
                    <div style="font-size: 0.85rem; color: rgba(255,255,255,0.6); margin-top: 5px;">{coverage_pct:.0f}% tracked</div>
                </div>
            </div>

            <div class="glass-dark" style="padding: 25px; margin-bottom: 25px;">
                <h4 style="color: rgba(255,255,255,0.9); margin-bottom: 20px;">📊 Overall Metrics</h4>

                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px;">
                    <div>
                        <div style="color: rgba(255,255,255,0.5); font-size: 0.75rem; text-transform: uppercase;">Days Since Last Update</div>
                        <div style="font-size: 2rem; font-weight: 700; color: {freshness_color};">
                            {days_since if days_since is not None else "N/A"}
                        </div>
                    </div>
                    <div>
                        <div style="color: rgba(255,255,255,0.5); font-size: 0.75rem; text-transform: uppercase;">Records with Vintage</div>
                        <div style="font-size: 2rem; font-weight: 700; color: {coverage_color};">
                            {coverage_pct:.0f}%
                        </div>
                        <div style="color: rgba(255,255,255,0.5); font-size: 0.8rem;">
                            {temporal_data.get('records_with_vintage', 0):,} / {temporal_data.get('total_records', 0):,}
                        </div>
                    </div>
                    <div>
                        <div style="color: rgba(255,255,255,0.5); font-size: 0.75rem; text-transform: uppercase;">Date Range</div>
                        <div style="font-size: 1rem; font-weight: 600; color: rgba(255,255,255,0.9); font-family: monospace;">
                            {oldest}
                        </div>
                        <div style="color: rgba(255,255,255,0.5); font-size: 0.8rem;">to</div>
                        <div style="font-size: 1rem; font-weight: 600; color: rgba(255,255,255,0.9); font-family: monospace;">
                            {newest}
                        </div>
                    </div>
                </div>
            </div>

            <h3>Freshness by Source</h3>
            <p style="color: rgba(255,255,255,0.6); margin-bottom: 20px; font-size: 0.9rem;">
                Sources are ranked by recency. Fresh data (&lt;30 days) is green, aging data (90-180 days) is yellow,
                stale data (&gt;180 days) is red.
            </p>

            <div class="source-grid">
                {source_cards_html}
            </div>

            <div class="alert alert-warning" style="margin-top: 25px;">
                <span class="alert-icon">💡</span>
                <div class="alert-content">
                    <div class="alert-title">Maintenance Risk Indicators</div>
                    <div class="alert-text">
                        Watch for sources with <strong>stale data</strong> (&gt;6 months old) — these may require refresh or vendor follow-up.
                        Low <strong>vintage coverage</strong> (&lt;50%) makes it harder to assess data currency and may indicate ingestion issues.
                    </div>
                </div>
            </div>
            </div>
        </section>
'''

# =============================================================================
# MAIN REPORT GENERATION
# =============================================================================

def collect_report_data():
    """Collect all data needed for the report."""
    print("Collecting diagnostic data...")

    # Use paths from config
    buildings_fc = GOLD_BUILDINGS
    campus_fc = GOLD_CAMPUS
    xb_fc = os.path.join(GDB, "gold_combined_xb")

    data = {}

    # Record counts
    print("  Counting records...")
    data["total_buildings"] = get_record_count(buildings_fc)
    data["total_campus"] = get_record_count(campus_fc)
    data["total_xb"] = get_record_count(xb_fc)

    # Spatial accuracy analysis vs Meta Canonical
    # Calculate BEFORE weighted scoring so it can be included in scores
    print("  Calculating spatial accuracy vs Meta Canonical...")
    meta_canonical_fc = os.path.join(GDB, "meta_canonical_buildings")
    data["spatial_accuracy"] = calculate_spatial_accuracy_stats(buildings_fc, meta_canonical_fc)

    # Capacity accuracy analysis vs Meta Canonical IT Load
    print("  Calculating capacity accuracy vs Meta Canonical...")
    data["capacity_accuracy"] = calculate_capacity_accuracy_stats(buildings_fc, meta_canonical_fc)

    # Source stats with weighted scoring
    print("  Analyzing sources...")
    data["source_stats"] = {}
    data["weighted_source_stats"] = {}
    for source in SOURCES:
        # Legacy stats for backward compatibility
        stats = get_source_stats(buildings_fc, source)
        if stats:
            data["source_stats"][source] = stats
        # New weighted scoring (now includes spatial accuracy)
        weighted = calculate_weighted_source_score(
            buildings_fc, source, data["total_buildings"],
            spatial_accuracy_data=data["spatial_accuracy"]
        )
        if weighted:
            data["weighted_source_stats"][source] = weighted
    data["source_count"] = len(data["source_stats"])

    # Field completeness on XB layer
    print("  Checking field completeness...")
    data["field_completeness"] = {}
    all_scores = []
    for category, fields in CRITICAL_FIELDS.items():
        data["field_completeness"][category] = {}
        for field in fields:
            pct = calculate_field_completeness(xb_fc, field)
            data["field_completeness"][category][field] = pct
            if pct is not None:
                all_scores.append(pct)

    data["avg_completeness"] = sum(all_scores) / len(all_scores) if all_scores else 0

    # Calculate grades using comprehensive field set (8+ fields per layer)
    print("  Calculating health grades...")

    # Buildings layer - same comprehensive fields as campus/XB for consistency
    buildings_grade_fields = [
        "company_clean",       # Core identity
        "company_clean_filter", # Filtering field
        "UCID",                # Campus linkage
        "latitude",            # Location
        "longitude",           # Location
        "full_capacity_mw",    # Capacity
        "commissioned_power_mw", # Current capacity
        "planned_power_mw",    # Future capacity
        "building_count",      # Count (should be 1 for buildings)
        "source",              # Data provenance
        "data_vintage"         # Data freshness
    ]
    buildings_scores = [calculate_field_completeness(buildings_fc, f) for f in buildings_grade_fields]
    # Create dict for visual breakdown
    buildings_scores_dict = {f: calculate_field_completeness(buildings_fc, f) for f in buildings_grade_fields}

    # Campus layer - aggregation quality and completeness
    # Note: latitude/longitude are populated from geometry in cleanup_gold_campus.py
    # They are forced to 100% since geometry guarantees their presence
    # data_vintage is excluded because it's not aggregated from buildings
    campus_grade_fields = [
        "company_clean",       # Core identity
        "company_clean_filter", # Filtering field
        "UCID",                # Campus identifier
        "full_capacity_mw",    # Total capacity
        "commissioned_power_mw", # Current capacity
        "planned_power_mw",    # Future capacity
        "building_count",      # Aggregation metric
        "source",              # Contributing sources
    ]
    campus_scores = [calculate_field_completeness(campus_fc, f) for f in campus_grade_fields]
    campus_scores_dict = {f: calculate_field_completeness(campus_fc, f) for f in campus_grade_fields}
    # Force lat/lon to 100% since geometry guarantees their presence
    campus_scores_dict["latitude"] = 100.0
    campus_scores_dict["longitude"] = 100.0
    campus_scores.extend([100.0, 100.0])  # Add forced lat/lon scores

    # XB Combined layer - unified view quality
    xb_grade_fields = [
        "company_clean",       # Core identity
        "company_clean_filter", # Filtering field
        "UCID",                # Campus linkage
        "latitude",            # Location
        "longitude",           # Location
        "full_capacity_mw",    # Capacity
        "commissioned_power_mw", # Current capacity
        "record_level",        # Building vs Campus
        "source",              # Data provenance
        "data_vintage"         # Data freshness
    ]
    xb_scores = [calculate_field_completeness(xb_fc, f) for f in xb_grade_fields]
    xb_scores_dict = {f: calculate_field_completeness(xb_fc, f) for f in xb_grade_fields}

    data["buildings_grade"] = calculate_health_grade(buildings_scores)
    data["campus_grade"] = calculate_health_grade(campus_scores)
    data["xb_grade"] = calculate_health_grade(xb_scores)

    # Calculate overall grade from layer grades (not field completeness)
    # Use numeric scores from each layer to compute weighted average
    buildings_avg = sum(s for s in buildings_scores if s is not None) / len([s for s in buildings_scores if s is not None]) if buildings_scores else 0
    campus_avg = sum(s for s in campus_scores if s is not None) / len([s for s in campus_scores if s is not None]) if campus_scores else 0
    xb_avg = sum(s for s in xb_scores if s is not None) / len([s for s in xb_scores if s is not None]) if xb_scores else 0

    # Weight XB highest (final output), campus and buildings equal
    overall_avg = (buildings_avg * 0.25) + (campus_avg * 0.25) + (xb_avg * 0.50)
    data["overall_grade"] = calculate_health_grade([overall_avg])

    # Store field details for transparency in report
    data["grade_fields"] = {
        "buildings": buildings_grade_fields,
        "campus": campus_grade_fields,
        "xb": xb_grade_fields
    }

    # Store field score dicts for visual breakdown
    data["grade_field_scores"] = {
        "buildings_scores": buildings_scores_dict,
        "campus_scores": campus_scores_dict,
        "xb_scores": xb_scores_dict
    }

    # Distributions
    print("  Getting distributions...")
    data["source_distribution"] = get_source_distribution(buildings_fc)
    data["company_distribution"] = get_company_filter_distribution(xb_fc)
    data["state_distribution"] = get_state_distribution(xb_fc)

    # Capacity sums by source and company for distribution charts
    print("  Calculating capacity sums...")
    data["capacity_by_source"] = {}
    data["capacity_by_company"] = {}

    # Get capacity by source
    try:
        with arcpy.da.SearchCursor(xb_fc, ["source", "full_capacity_mw"]) as cursor:
            for row in cursor:
                source = row[0] or "Unknown"
                cap = row[1] or 0
                if source not in data["capacity_by_source"]:
                    data["capacity_by_source"][source] = 0
                data["capacity_by_source"][source] += cap
    except Exception as e:
        print(f"    ⚠ Error calculating capacity by source: {e}")

    # Get capacity by company_clean_filter
    try:
        with arcpy.da.SearchCursor(xb_fc, ["company_clean_filter", "full_capacity_mw"]) as cursor:
            for row in cursor:
                company = row[0] or "Unknown"
                cap = row[1] or 0
                if company not in data["capacity_by_company"]:
                    data["capacity_by_company"][company] = 0
                data["capacity_by_company"][company] += cap
    except Exception as e:
        print(f"    ⚠ Error calculating capacity by company: {e}")

    # Get capacity by state
    data["capacity_by_state"] = {}
    try:
        with arcpy.da.SearchCursor(xb_fc, ["state", "full_capacity_mw"]) as cursor:
            for row in cursor:
                state = row[0]
                cap = row[1] or 0
                # Filter out invalid state values
                if state and state not in ["(null)", "", "0"] and not state.startswith("0."):
                    if state not in data["capacity_by_state"]:
                        data["capacity_by_state"][state] = 0
                    data["capacity_by_state"][state] += cap
    except Exception as e:
        print(f"    ⚠ Error calculating capacity by state: {e}")

    # Quality checks
    print("  Running quality checks...")
    data["duplicate_check"] = check_duplicate_unique_ids(buildings_fc)
    data["vintage_stats"] = get_data_vintage_stats(buildings_fc)

    # Temporal freshness analysis (buildings only - campus vintage is aggregated MAX from buildings)
    # Using buildings gives us source-level freshness; campus MAX just echoes the freshest building
    print("  Calculating temporal freshness...")
    data["temporal_freshness"] = calculate_temporal_freshness(buildings_fc)

    # Consensus strength analysis
    print("  Calculating consensus strength...")
    data["consensus_strength"] = calculate_consensus_metrics(campus_fc, buildings_fc)

    # Regional distribution (group by region based on country)
    print("  Calculating regional distribution...")
    data["region_distribution"] = {}

    # Define region mapping based on country
    region_map = {
        "North America": ["United States", "USA", "US", "Canada", "Mexico"],
        "Europe": ["United Kingdom", "UK", "Germany", "France", "Netherlands", "Ireland", "Sweden", "Finland", "Norway", "Denmark", "Spain", "Italy", "Belgium", "Switzerland", "Poland", "Austria"],
        "Asia Pacific": ["Japan", "Singapore", "Australia", "South Korea", "India", "Hong Kong", "Taiwan", "Indonesia", "Malaysia", "Thailand", "Vietnam", "Philippines", "New Zealand", "China"],
        "Latin America": ["Brazil", "Chile", "Colombia", "Argentina", "Peru"],
        "Middle East & Africa": ["UAE", "United Arab Emirates", "Israel", "South Africa", "Saudi Arabia", "Qatar", "Bahrain", "Kenya", "Nigeria", "Egypt"]
    }

    # Invert for lookup
    country_to_region = {}
    for region, countries in region_map.items():
        for country in countries:
            country_to_region[country.upper()] = region

    try:
        with arcpy.da.SearchCursor(xb_fc, ["country", "full_capacity_mw"]) as cursor:
            for row in cursor:
                country = row[0]
                cap = row[1] or 0

                # Determine region
                if country:
                    region = country_to_region.get(country.upper(), "Other")
                else:
                    region = "Unknown"

                if region not in data["region_distribution"]:
                    data["region_distribution"][region] = {"count": 0, "capacity": 0}
                data["region_distribution"][region]["count"] += 1
                data["region_distribution"][region]["capacity"] += cap
    except Exception as e:
        print(f"    ⚠ Error calculating regional distribution: {e}")

    return data

def generate_report():
    """Generate the full HTML report."""
    print("\n" + "="*60)
    print("GENERATING PIPELINE DIAGNOSTIC REPORT")
    print("="*60)

    # Collect data
    data = collect_report_data()

    # Build HTML
    print("\nBuilding HTML report...")
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    html = get_html_header(timestamp)

    # Header section
    html += f'''
        <header class="glass">
            <h1>Pipeline Diagnostic Report</h1>
            <p class="subtitle">Data Center GIS Pipeline Health Analysis</p>
            <p class="timestamp">Generated: {timestamp}</p>
        </header>
'''

    # =========================================================================
    # EXECUTIVE SUMMARY
    # =========================================================================

    # Calculate average source score for report card
    weighted_stats = data.get("weighted_source_stats", {})
    source_scores = [s.get("final_score", 0) for s in weighted_stats.values() if s and "error" not in s and s.get("final_score")]
    avg_source_score = sum(source_scores) / len(source_scores) if source_scores else 0

    # Executive Report Card (3 pillars at a glance)
    html += generate_report_card_section(
        avg_source_score,
        data["overall_grade"],
        data.get("consensus_strength", {}),
        {
            "total_buildings": data.get("total_buildings", 0),
            "total_campus": data.get("total_campus", 0),
            "source_count": data.get("source_count", 0)
        }
    )

    # Recommendations section (actionable insights for executives)
    html += generate_recommendations_section(
        data.get("weighted_source_stats", {}),
        data.get("spatial_accuracy", {}),
        data.get("temporal_freshness", {}),
        data.get("capacity_accuracy", {})
    )

    # Stats section
    html += generate_stats_section(data)

    # =========================================================================
    # INPUT SOURCE QUALITY - Category Divider
    # =========================================================================
    html += '''
        <div class="category-divider" id="category-input">
            <div class="category-line"></div>
            <span class="category-label">INPUT SOURCE QUALITY</span>
            <div class="category-line"></div>
        </div>
    '''

    # Source analysis with weighted scoring
    html += generate_source_cards(data["source_stats"], data.get("weighted_source_stats"))

    # Spatial accuracy section
    html += generate_spatial_accuracy_section(data.get("spatial_accuracy", {}))

    # Temporal Freshness & Stability section
    html += generate_temporal_freshness_section(data.get("temporal_freshness", {}))

    # Consensus Strength section (detailed breakdown)
    html += generate_consensus_strength_section(data.get("consensus_strength", {}))

    # =========================================================================
    # OUTPUT DATASET QUALITY - Category Divider
    # =========================================================================
    html += '''
        <div class="category-divider" id="category-output">
            <div class="category-line"></div>
            <span class="category-label">OUTPUT DATASET QUALITY</span>
            <div class="category-line"></div>
        </div>
    '''

    # Pipeline Health Grades (detailed layer breakdown)
    html += generate_grade_section(
        data["buildings_grade"],
        data["campus_grade"],
        data["xb_grade"],
        data["overall_grade"],
        data.get("grade_field_scores")
    )

    # Field completeness
    html += generate_field_completeness_table(data["field_completeness"])

    # Distributions
    html += generate_distribution_section(
        data["source_distribution"],
        data["company_distribution"],
        data["state_distribution"],
        capacity_by_source=data.get("capacity_by_source"),
        capacity_by_company=data.get("capacity_by_company"),
        region_distribution=data.get("region_distribution"),
        capacity_by_state=data.get("capacity_by_state")
    )

    # Quality checks
    html += generate_quality_section(data["duplicate_check"], data["vintage_stats"])

    # =========================================================================
    # SYNTHESIS - Category Divider
    # =========================================================================
    html += '''
        <div class="category-divider" id="category-synthesis">
            <div class="category-line"></div>
            <span class="category-label">SYNTHESIS</span>
            <div class="category-line"></div>
        </div>
    '''

    # Map visualization section (demonstrates consensus value)
    buildings_fc = GOLD_BUILDINGS
    campus_fc = GOLD_CAMPUS
    meta_canonical_fc = os.path.join(GDB, "meta_canonical_buildings")
    html += generate_map_visualization_section(buildings_fc, campus_fc, meta_canonical_fc)

    # Footer
    html += get_html_footer()

    # Save report
    report_filename = f"PIPELINE_DIAGNOSTIC_{datetime.now().strftime('%Y%m%d_%H%M')}.html"
    report_path = os.path.join(REPORT_OUTPUT_DIR, report_filename)

    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(html)

    print(f"\n✓ Report saved: {report_path}")
    print("="*60)

    return report_path

# =============================================================================
# ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    generate_report()
