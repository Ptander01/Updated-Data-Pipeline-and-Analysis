"""
Analyze Gold Feature Classes in Geodatabase
============================================
Lists all gold-related feature classes with record counts and metadata
to help identify which are current vs. candidates for deletion.

Run in ArcGIS Pro Python window:
exec(open(r"...scripts/04_analysis/analyze_gold_feature_classes.py", encoding='utf-8').read())

Author: Meta Data Center GIS Team
Created: 2026-01-20
"""

import arcpy
import os
import sys
from datetime import datetime

# Add _utils to path for config import
try:
    script_dir = os.path.dirname(os.path.abspath(__file__))
except NameError:
    script_dir = r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\scripts\04_analysis"

utils_dir = os.path.join(os.path.dirname(script_dir), "_utils")
if utils_dir not in sys.path:
    sys.path.insert(0, utils_dir)

from config import GDB, GOLD_BUILDINGS, GOLD_CAMPUS

arcpy.env.workspace = GDB

print("=" * 80)
print("ANALYZE GOLD FEATURE CLASSES IN GEODATABASE")
print("=" * 80)
print(f"Geodatabase: {GDB}")
print(f"Analysis Date: {datetime.now()}")

# Get all feature classes and tables
all_fcs = arcpy.ListFeatureClasses()
all_tables = arcpy.ListTables()

# Filter for gold-related items
gold_patterns = ['gold', 'campus', 'building', 'combined', 'xb']

def matches_gold_pattern(name):
    """Check if name matches any gold-related pattern."""
    name_lower = name.lower()
    return any(pattern in name_lower for pattern in gold_patterns)

# Analyze feature classes
gold_fcs = [fc for fc in all_fcs if matches_gold_pattern(fc)]
gold_tables = [t for t in all_tables if matches_gold_pattern(t)]

print(f"\nFound {len(gold_fcs)} gold-related feature classes")
print(f"Found {len(gold_tables)} gold-related tables")

# Active/canonical feature classes from config
CANONICAL_FCS = {
    os.path.basename(GOLD_BUILDINGS): "ACTIVE - Primary buildings layer",
    os.path.basename(GOLD_CAMPUS): "ACTIVE - Primary campus layer",
    "gold_combined_xb": "ACTIVE - Combined XB layer for web dashboard",
    "gold_buildings": "LEAN MODEL - Original test data (keep for reference)",
    "gold_campus": "LEAN MODEL - Original test data (keep for reference)",
    "meta_canonical_v2": "REFERENCE - Meta ground truth data",
    "meta_canonical_buildings": "REFERENCE - Meta canonical buildings",
    "meta_canonical_campus": "REFERENCE - Meta canonical campus",
    "campus_master": "UCID - Master campus registry",
    "campus_master_tight": "UCID - Tight tolerance clustering",
    "campus_master_loose": "UCID - Loose tolerance clustering",
}

# Collect analysis data
analysis_results = []

print("\n" + "-" * 80)
print("FEATURE CLASS ANALYSIS")
print("-" * 80)

for fc in sorted(gold_fcs):
    try:
        fc_path = os.path.join(GDB, fc)
        
        # Get record count
        count = int(arcpy.management.GetCount(fc_path)[0])
        
        # Get field count
        fields = arcpy.ListFields(fc_path)
        field_count = len(fields)
        
        # Get geometry type
        desc = arcpy.Describe(fc_path)
        geom_type = desc.shapeType if hasattr(desc, 'shapeType') else 'Unknown'
        
        # Check for key fields
        field_names = [f.name.lower() for f in fields]
        has_ucid = 'ucid' in field_names
        has_source = 'source' in field_names
        has_ingest_date = 'ingest_date' in field_names
        has_type_category = 'type_category' in field_names
        
        # Get latest ingest_date if available
        latest_ingest = None
        if has_ingest_date:
            try:
                with arcpy.da.SearchCursor(fc_path, ['ingest_date'], 
                                           sql_clause=(None, 'ORDER BY ingest_date DESC')) as cursor:
                    for row in cursor:
                        if row[0]:
                            latest_ingest = row[0]
                            break
            except:
                pass
        
        # Determine status
        status = CANONICAL_FCS.get(fc, "⚠️ UNKNOWN - Review for deletion")
        
        # Check if this is the canonical version
        is_canonical = fc in CANONICAL_FCS
        
        analysis_results.append({
            'name': fc,
            'count': count,
            'fields': field_count,
            'geom_type': geom_type,
            'has_ucid': has_ucid,
            'has_source': has_source,
            'has_ingest_date': has_ingest_date,
            'has_type_category': has_type_category,
            'latest_ingest': latest_ingest,
            'status': status,
            'is_canonical': is_canonical
        })
        
    except Exception as e:
        analysis_results.append({
            'name': fc,
            'count': 'ERROR',
            'error': str(e),
            'status': f"❌ ERROR: {str(e)}",
            'is_canonical': False
        })

# Print results grouped by status
print("\n" + "=" * 80)
print("📊 ACTIVE/CANONICAL FEATURE CLASSES (KEEP)")
print("=" * 80)

for r in sorted(analysis_results, key=lambda x: x['name']):
    if r.get('is_canonical'):
        print(f"\n✅ {r['name']}")
        print(f"   Records: {r.get('count', 'N/A'):,}")
        print(f"   Fields: {r.get('fields', 'N/A')}, Geometry: {r.get('geom_type', 'N/A')}")
        if r.get('latest_ingest'):
            print(f"   Latest Ingest: {r['latest_ingest']}")
        print(f"   Status: {r['status']}")
        
        # Key field indicators
        indicators = []
        if r.get('has_ucid'): indicators.append('✓ ucid')
        if r.get('has_source'): indicators.append('✓ source')
        if r.get('has_type_category'): indicators.append('✓ type_category')
        if indicators:
            print(f"   Key Fields: {', '.join(indicators)}")

print("\n" + "=" * 80)
print("⚠️ UNKNOWN FEATURE CLASSES (REVIEW FOR DELETION)")
print("=" * 80)

unknown_fcs = [r for r in analysis_results if not r.get('is_canonical')]

if unknown_fcs:
    for r in sorted(unknown_fcs, key=lambda x: x['name']):
        print(f"\n⚠️ {r['name']}")
        if r.get('count') != 'ERROR':
            print(f"   Records: {r.get('count', 'N/A'):,}")
            print(f"   Fields: {r.get('fields', 'N/A')}, Geometry: {r.get('geom_type', 'N/A')}")
            if r.get('latest_ingest'):
                print(f"   Latest Ingest: {r['latest_ingest']}")
        else:
            print(f"   Error: {r.get('error', 'Unknown error')}")
else:
    print("\n   No unknown feature classes found.")

# Analyze tables
print("\n" + "=" * 80)
print("📋 RELATED TABLES")
print("=" * 80)

CANONICAL_TABLES = {
    'npm_raw': "RAW - NewProjectMedia source data",
    'dch_hyper_raw': "RAW - DCH Hyperscale source data",
    'dch_lease_raw': "RAW - DCH Lease source data",
    'semianalysis_raw': "RAW - SemiAnalysis source data",
    'dcm_raw': "RAW - DataCenterMap source data",
    'synergy_raw': "RAW - Synergy source data",
    'woodmac_campus_raw': "RAW - WoodMac campus data (validation only)",
    'woodmac_dc_raw': "RAW - WoodMac DC data (validation only)",
}

for table in sorted(gold_tables):
    try:
        table_path = os.path.join(GDB, table)
        count = int(arcpy.management.GetCount(table_path)[0])
        status = CANONICAL_TABLES.get(table, "⚠️ UNKNOWN")
        
        if table in CANONICAL_TABLES:
            print(f"\n✅ {table}: {count:,} records")
            print(f"   {status}")
        else:
            print(f"\n⚠️ {table}: {count:,} records")
            print(f"   {status} - Review for deletion")
            
    except Exception as e:
        print(f"\n❌ {table}: ERROR - {str(e)}")

# Summary recommendations
print("\n" + "=" * 80)
print("📋 CLEANUP RECOMMENDATIONS")
print("=" * 80)

delete_candidates = [r['name'] for r in analysis_results if not r.get('is_canonical')]

if delete_candidates:
    print("\nThe following feature classes are NOT in the canonical list and may be")
    print("old/test versions that can be deleted after verification:")
    print()
    for fc in sorted(delete_candidates):
        print(f"   • {fc}")
    
    print("\n⚠️ BEFORE DELETING:")
    print("   1. Verify these are not needed for any workflows")
    print("   2. Check if they contain unique data not in canonical layers")
    print("   3. Consider exporting to backup before deletion")
    
    print("\n📝 TO DELETE (run in ArcGIS Pro Python window):")
    print("   import arcpy")
    for fc in sorted(delete_candidates):
        print(f'   arcpy.management.Delete(r"{os.path.join(GDB, fc)}")')
else:
    print("\n✅ All feature classes appear to be canonical - no cleanup needed.")

print("\n" + "=" * 80)
print("ANALYSIS COMPLETE")
print("=" * 80)
