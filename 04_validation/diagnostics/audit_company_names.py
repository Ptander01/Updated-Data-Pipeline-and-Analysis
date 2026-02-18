"""
Company Name Audit Script
Analyzes company_clean field across gold_buildings_full to identify
variations that need standardization.

Outputs to CSV file for easy review and sharing.

Run this first to see what needs fixing, then update standardize_company_names.py

Author: Meta Data Center GIS Team
Last Updated: 2024-12-17
"""

import arcpy
import os
import sys
import csv
from collections import defaultdict
from datetime import datetime

# Add _utils to path for config import
try:
    script_dir = os.path.dirname(os.path.abspath(__file__))
except NameError:
    script_dir = r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\scripts\04_validation"

utils_dir = os.path.join(os.path.dirname(script_dir), "_utils")
if utils_dir not in sys.path:
    sys.path.insert(0, utils_dir)

from config import GDB, GOLD_BUILDINGS, GOLD_CAMPUS

arcpy.env.workspace = GDB

# ============================================================================
# OUTPUT CONFIGURATION
# ============================================================================

OUTPUT_DIR = r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\outputs"
TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")

# Create output directory if it doesn't exist
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ============================================================================
# MAJOR HYPERSCALERS (these stay as distinct values)
# ============================================================================

HYPERSCALERS = {
    'Meta', 'AWS', 'Google', 'Microsoft', 'Oracle', 'Apple',
    'xAI', 'OpenAI', 'Anthropic', 'ByteDance', 'TikTok', 'Alibaba',
    'Tencent', 'Baidu', 'IBM', 'Salesforce'
}

# ============================================================================
# AUDIT FUNCTION
# ============================================================================

def audit_company_names():
    """Analyze company_clean values and output to CSV."""

    print("=" * 80)
    print("   COMPANY NAME AUDIT")
    print("=" * 80)

    # Count company occurrences
    company_counts = defaultdict(int)
    company_sources = defaultdict(set)
    company_capacity = defaultdict(float)  # Sum of full_capacity_mw

    # Check what fields exist
    fields = [f.name for f in arcpy.ListFields(GOLD_BUILDINGS)]
    read_fields = ['company_clean', 'source']
    if 'full_capacity_mw' in fields:
        read_fields.append('full_capacity_mw')

    with arcpy.da.SearchCursor(GOLD_BUILDINGS, read_fields) as cursor:
        for row in cursor:
            company = row[0] if row[0] else 'NULL'
            source = row[1] if row[1] else 'Unknown'
            capacity = row[2] if len(row) > 2 and row[2] else 0

            company_counts[company] += 1
            company_sources[company].add(source)
            company_capacity[company] += capacity

    total_records = sum(company_counts.values())
    unique_companies = len(company_counts)

    print(f"\n  Total records: {total_records:,}")
    print(f"  Unique company names: {unique_companies}")

    # =========================================================================
    # OUTPUT 1: Full company list CSV
    # =========================================================================

    csv_path = os.path.join(OUTPUT_DIR, f"company_audit_{TIMESTAMP}.csv")

    # Sort by count (descending)
    sorted_companies = sorted(company_counts.items(), key=lambda x: -x[1])

    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([
            'company_clean',
            'record_count',
            'pct_of_total',
            'total_capacity_mw',
            'sources',
            'is_hyperscaler',
            'recommended_action'
        ])

        for company, count in sorted_companies:
            sources = '; '.join(sorted(company_sources[company]))
            pct = (count / total_records * 100)
            capacity = company_capacity[company]

            # Determine if hyperscaler
            is_hyperscaler = 'Yes' if company in HYPERSCALERS else 'No'

            # Recommend action
            if company in HYPERSCALERS:
                action = 'KEEP'
            elif company == 'NULL':
                action = 'REVIEW - Missing company'
            elif count < 10:
                action = 'CONSIDER: Colo - All Other'
            else:
                action = 'REVIEW'

            writer.writerow([
                company,
                count,
                f"{pct:.2f}%",
                f"{capacity:.1f}",
                sources,
                is_hyperscaler,
                action
            ])

    print(f"\n  ✅ Full company list saved to:")
    print(f"     {csv_path}")

    # =========================================================================
    # OUTPUT 2: Summary by category
    # =========================================================================

    summary_path = os.path.join(OUTPUT_DIR, f"company_summary_{TIMESTAMP}.csv")

    # Categorize companies
    hyperscaler_records = 0
    hyperscaler_capacity = 0
    colo_records = 0
    colo_capacity = 0
    other_records = 0
    other_capacity = 0

    hyperscaler_detail = []
    colo_companies = []

    for company, count in sorted_companies:
        capacity = company_capacity[company]

        if company in HYPERSCALERS:
            hyperscaler_records += count
            hyperscaler_capacity += capacity
            hyperscaler_detail.append((company, count, capacity))
        elif company == 'NULL':
            other_records += count
            other_capacity += capacity
        else:
            colo_records += count
            colo_capacity += capacity
            colo_companies.append((company, count, capacity))

    with open(summary_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)

        # Summary section
        writer.writerow(['=== SUMMARY ===', '', '', ''])
        writer.writerow(['Category', 'Record Count', 'Pct of Total', 'Total Capacity MW'])
        writer.writerow(['Hyperscalers', hyperscaler_records, f"{hyperscaler_records/total_records*100:.1f}%", f"{hyperscaler_capacity:.1f}"])
        writer.writerow(['Colo/Other Companies', colo_records, f"{colo_records/total_records*100:.1f}%", f"{colo_capacity:.1f}"])
        writer.writerow(['NULL/Missing', other_records, f"{other_records/total_records*100:.1f}%", f"{other_capacity:.1f}"])
        writer.writerow([])

        # Hyperscaler detail
        writer.writerow(['=== HYPERSCALER DETAIL ===', '', '', ''])
        writer.writerow(['Company', 'Record Count', 'Capacity MW', ''])
        for company, count, cap in sorted(hyperscaler_detail, key=lambda x: -x[1]):
            writer.writerow([company, count, f"{cap:.1f}", ''])
        writer.writerow([])

        # Top 50 colo companies
        writer.writerow(['=== TOP 50 COLO/OTHER COMPANIES ===', '', '', ''])
        writer.writerow(['Company', 'Record Count', 'Capacity MW', 'Recommendation'])
        for company, count, cap in sorted(colo_companies, key=lambda x: -x[1])[:50]:
            rec = 'Keep distinct' if count >= 100 else 'Colo - All Other'
            writer.writerow([company, count, f"{cap:.1f}", rec])

    print(f"  ✅ Summary saved to:")
    print(f"     {summary_path}")

    # =========================================================================
    # Console summary
    # =========================================================================

    print(f"\n  --- QUICK SUMMARY ---")
    print(f"  Hyperscalers: {hyperscaler_records:,} records ({hyperscaler_records/total_records*100:.1f}%)")
    print(f"  Colo/Other:   {colo_records:,} records ({colo_records/total_records*100:.1f}%)")
    print(f"  NULL/Missing: {other_records:,} records ({other_records/total_records*100:.1f}%)")
    print(f"  Unique colo companies: {len(colo_companies)}")

    print(f"\n  --- TOP 10 HYPERSCALERS ---")
    for company, count, cap in sorted(hyperscaler_detail, key=lambda x: -x[1])[:10]:
        print(f"    {company:<20} {count:>6} records  {cap:>8.1f} MW")

    print(f"\n  --- TOP 10 COLO COMPANIES ---")
    for company, count, cap in sorted(colo_companies, key=lambda x: -x[1])[:10]:
        print(f"    {company:<30} {count:>6} records  {cap:>8.1f} MW")

    print(f"\n  📁 OUTPUT FILES:")
    print(f"     {csv_path}")
    print(f"     {summary_path}")
    print(f"\n  Review these CSVs and update standardize_company_names.py as needed.")

    return company_counts, company_sources


# ============================================================================
# EXECUTE
# ============================================================================

if __name__ == "__main__":
    try:
        audit_company_names()
    except Exception as e:
        print(f"\n❌ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()

# Also run when exec()'d
try:
    audit_company_names()
except Exception as e:
    print(f"\n❌ ERROR: {str(e)}")
    import traceback
    traceback.print_exc()
