# V2.0 Field Ingestion Audit - Task List

**Created:** January 2, 2026
**Updated:** January 2, 2026 (Post-Audit)
**Status:** ✅ AUDIT COMPLETE - Ingestion Scripts Updated

---

## 🔍 Audit Results Summary (January 2, 2026)

Ran `audit_raw_tables_v2_fields.py` to check all raw source tables for V2.0 fields.

### V2.0 Field Availability Matrix

| V2.0 Field | semianalysis | dch_hyper | dch_lease | dcm | npm | synergy |
|------------|--------------|-----------|-----------|-----|-----|---------|
| `developer` | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| `tenant` | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| `end_user` | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| `energy_source` | ❌ | ❌ | ⚠️ False* | ❌ | ❌ | ❌ |
| `construction_start_date` | ❌ | ⚠️ False* | ⚠️ False* | ❌ | ❌ | ❌ |
| `data_vintage` | ✅ Field43 | ✅ date_updated | ✅ date_updated | ✅ Data_Vintage | ✅ Modified | ✅ Data_Vintage |

**False Positives Explained:**
- `energy_source` → `compliance_energy_star` is certification status, not power source
- `construction_start_date` → `capacity_under_construction_power` is MW capacity, not a date

---

## ✅ Completed Updates

### Ingestion Scripts Updated for `data_vintage`

| Script | Source Field | Status |
|--------|--------------|--------|
| `ingest_semianalysis.py` | `Field43` (Data Vintage) | ✅ Updated |
| `ingest_dch.py` | `date_updated` | ✅ Updated |
| `ingest_dch_lease.py` | `date_updated` | ✅ Updated |
| `ingest_dcm.py` | `Data_Vintage` | ✅ Updated |
| `ingest_npm.py` | `Modified` | ✅ Updated |

### Key Findings

1. **`data_vintage`** is the only V2.0 field available across multiple sources
2. **Ownership fields** (`developer`, `tenant`, `end_user`) are **NOT available** in any raw source
3. **Energy fields** (`energy_source`) require vendor data updates or manual entry
4. **Timeline fields** (`construction_start_date`) require vendor data updates

---

## 📋 Phase 1: Audit Raw Source Tables ✅ COMPLETE

### Task Checklist

- [x] **Semianalysis (`semianalysis_raw`)** - 5,732 records, 44 fields
  - [x] Check for developer/owner fields - ❌ Not found
  - [x] Check for energy/power source fields - ❌ Not found
  - [x] Check for AI/GPU workload indicators - ❌ Not found
  - [x] Check for construction timeline dates - ❌ Not found
  - [x] Check for data vintage - ✅ `Field43` (Data Vintage)
  - [x] Document field mappings - See `ingest_semianalysis.py` header

- [x] **DataCenterHawk Hyper (`dch_hyper_raw`)** - 1,876 records, 26 fields
  - [x] Check for developer/tenant fields - ❌ Not found
  - [x] Check for energy source fields - ❌ Not found
  - [x] Check for construction dates - ❌ Not found (capacity_under_construction_power is MW, not date)
  - [x] Check for data vintage - ✅ `date_updated`, `extraction_date`
  - [x] Document field mappings - ✅ Complete

- [x] **DataCenterHawk Lease (`dch_lease_raw`)** - 5,236 records, 78 fields
  - [x] Check for tenant/end_user fields - ❌ Not found
  - [x] Check for lease date fields - ❌ Not found
  - [x] Check for data vintage - ✅ `date_updated`, `extraction_date`
  - [x] Document field mappings - ✅ Complete

- [x] **DataCenterMap (`dcm_raw`)** - 8,897 records, 35 fields
  - [x] Check for ownership fields - ❌ Not found
  - [x] Check for power/energy fields - ❌ Not found
  - [x] Check for data vintage - ✅ `Data_Vintage`
  - [x] Document field mappings - ✅ Complete

- [x] **NewProjectMedia (`npm_raw`)** - 1,401 records, 27 fields
  - [x] Check for developer fields - ❌ Not found (Organizations field has company, not developer)
  - [x] Check for construction timeline - ❌ Not found (Planned_Operation_Date is completion, not start)
  - [x] Check for cost breakdown fields - ✅ `Cost` field exists
  - [x] Check for data vintage - ✅ `Modified`, `Created`
  - [x] Document field mappings - ✅ Complete

- [x] **Synergy (`synergy_raw`)** - 956 records, 11 fields
  - [x] Check for data vintage - ✅ `Data_Vintage`
  - Note: Synergy skipped from pipeline (no coordinates)

---

## 📋 Phase 2: Update Ingestion Scripts ✅ COMPLETE

| Script | Fields Added | Status |
|--------|--------------|--------|
| `ingest_semianalysis.py` | `data_vintage` from Field43 | ✅ Complete |
| `ingest_dch.py` | `data_vintage` from date_updated | ✅ Complete |
| `ingest_dch_lease.py` | `data_vintage` from date_updated | ✅ Complete |
| `ingest_dcm.py` | `data_vintage` from Data_Vintage | ✅ Complete |
| `ingest_npm.py` | `data_vintage` from Modified | ✅ Complete |

---

## 🔮 Phase 3: Future Work (Requires Vendor Data or Manual Entry)

### Fields Not Available in Current Raw Data

| Field | Type | Purpose | Recommendation |
|-------|------|---------|----------------|
| `developer` | TEXT | Who developed the facility | Request from vendors or manual research |
| `tenant` | TEXT | Who leases space | Request from DCH in next data refresh |
| `end_user` | TEXT | Ultimate user of capacity | Request from DCH in next data refresh |
| `energy_source` | TEXT | Renewable/Grid/Hybrid | Research and manual entry |
| `ai_gpu_indicator` | TEXT | AI workload flag | Derive from company or manual entry |
| `construction_start_date` | DATE | Ground-breaking | Request from NPM or manual research |
| `construction_end_date` | DATE | Completion date | Map from Planned_Operation_Date (NPM) |
| `lease_start_date` | DATE | Lease begin | Not available |
| `lease_end_date` | DATE | Lease end | Not available |

### Potential Workarounds

1. **`developer`**: For hyperscalers, company often = developer. Could default to company_clean
2. **`tenant`**: DCH Lease `provider_name` is the colo provider, not the tenant
3. **`end_user`**: For hyperscale-owned facilities, end_user = owner
4. **`energy_source`**: Research Meta's sustainability reports for Meta facilities
5. **`ai_gpu_indicator`**: Flag sites with known AI workloads (xAI Memphis, etc.)

---

## 📋 Phase 4: Validation

After re-running ingestion with updated scripts:

- [ ] Re-run full ingestion pipeline
- [ ] Run `analyze_capacity_coverage.py` to verify `data_vintage` population
- [ ] Create coverage report for V2.0 fields
- [ ] Update documentation

### Commands to Re-run Pipeline

```python
# 1. Recreate empty gold_buildings_full (if needed)
exec(open(r"...\scripts\02_processing\recreate_gold_buildings.py", encoding='utf-8').read())

# 2. Run updated ingestion scripts
exec(open(r"...\scripts\01_ingestion\ingest_dch.py", encoding='utf-8').read())
exec(open(r"...\scripts\01_ingestion\ingest_dch_lease.py", encoding='utf-8').read())
exec(open(r"...\scripts\01_ingestion\ingest_semianalysis.py", encoding='utf-8').read())
exec(open(r"...\scripts\01_ingestion\ingest_dcm.py", encoding='utf-8').read())
exec(open(r"...\scripts\01_ingestion\ingest_npm.py", encoding='utf-8').read())

# 3. Run campus rollup
exec(open(r"...\scripts\02_processing\campus_rollup_new.py", encoding='utf-8').read())

# 4. Verify data_vintage coverage
import arcpy
GDB = r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\Default.gdb"

# Count non-null data_vintage
with arcpy.da.SearchCursor(f"{GDB}\\gold_buildings_full", ['data_vintage']) as cursor:
    total = 0
    populated = 0
    for row in cursor:
        total += 1
        if row[0] is not None:
            populated += 1
    print(f"data_vintage: {populated}/{total} ({100*populated/total:.1f}%)")
```

---

## 📁 Output Files

- `scripts/outputs/v2_field_audit_20260102_134523.txt` - Full audit report

---

## Notes

- Supervisor returns January 7, 2026
- Review this plan with supervisor before starting Phase 3 work
- Some fields may require manual data entry or external data sources
- Consider data quality implications of each new field

---

*Last Updated: January 2, 2026*
