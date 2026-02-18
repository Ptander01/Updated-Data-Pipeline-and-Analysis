# Semianalysis Data Relationship Investigation Report

## Investigation Date: January 26, 2026
## Purpose: Determine how Excel tabs relate for capacity aggregation

---

## Executive Summary

This investigation analyzed the relationships between different data sources in the Semianalysis Excel workbook to determine the correct formula for aggregating company capacity. The key question was: **Which tabs are ADDITIVE vs SUBSET?**

### Key Findings

| Data Source | Relationship | Add to Total? | Evidence |
|-------------|--------------|---------------|----------|
| **NA Data Center Supply** | Primary building records | ✅ YES | Base data |
| **Overseas Data Center Supply** | Primary building records | ✅ YES | Base data |
| **AI Labs** | **SUBSET** (99.6% overlap) | ❌ NO | Same UUIDs as NA/OS |
| **Hyperscalers Buildings** | **SUBSET** (95.4% overlap) | ❌ NO | Same UUIDs, HALF values |
| **TLBM** | Additional colo leasing | ✅ YES | Confirmed by user |

### Correct Aggregation Formula

```
Company Total Capacity = NA Buildings + Overseas Buildings + TLBM
                       (Hyperscaler overlaps should be deduplicated)
                       (AI Labs is enrichment only - no additional capacity)
```

---

## Detailed Findings

### 1. AI Labs = ENRICHMENT ONLY (Not Additive)

**Evidence:**
- 269 total AI Labs building records
- 268 records (99.6%) merged with NA or Overseas by UUID
- Only 1 record unique to AI Labs

**What AI Labs adds:**
- `end_user` field (estimated end user)
- `tenant` field (estimated tenant)
- `gpu_cloud` field (GPU cloud provider)

**Pipeline behavior:** Correctly merges by UUID, combines metadata fields, does NOT double capacity.

**Source_Sheet values after merge:**
- `AI Labs, NA`: 240 records
- `AI Labs, Overseas`: 28 records
- `AI Labs` (unique): 1 record

### 2. Hyperscalers Buildings = SUBSET with HALF Values (Bug Found)

**Evidence:**
- 283 total Hyperscaler building records (extracted from rows 82-740)
- 270 UUIDs (95.4%) overlap with NA/Overseas
- Only 13 UUIDs truly unique to Hyperscaler tab

**Critical Pattern - The "HALF" Finding:**

| Ratio (HS / Other) | Count | Percentage |
|--------------------|-------|------------|
| **0.5 (HALF)** | 995 | 69.6% |
| 1.0 (SAME) | 392 | 27.4% |
| Other ratios | 42 | 2.9% |

**Interpretation:**
- ~70% of overlapping records show Hyperscaler = EXACTLY HALF of NA/Overseas value
- This strongly suggests Hyperscaler tab tracks **ONE PHASE** of multi-phase facilities
- NA/Overseas tracks **TOTAL facility capacity** (all phases)

**Sample "HALF" cases:**
```
AWS | New Carlisle   | 2025: HS=60 MW,  Other=120 MW
QTS | New Albany     | 2025: HS=80 MW,  Other=160 MW
Meta | Mesa          | 2024: HS=30 MW,  Other=60 MW
Microsoft | West Des Moines | 2024: HS=24 MW, Other=48 MW
```

**Bug Status:** Current pipeline does NOT merge Hyperscaler duplicates with NA/Overseas.

### 3. Missing NA Records Explained

**Observation:** Zero standalone NA records in output (all show `Source_Sheet = 'AI Labs, NA'`)

**Explanation:**
- The AI Labs sheet contains **ALL 240 NA buildings** (100% overlap)
- Pipeline correctly merges by UUID
- Source_Sheet shows `AI Labs, NA` because both sources contributed data
- This is **correct behavior** - not a bug

### 4. Capacity Impact of Hyperscaler Bug

**Current Totals (WITH duplicate Hyperscaler records):**
- 2025: 78,158 MW
- 2026: 121,076 MW
- 2030: 356,097 MW

**Corrected Totals (deduplicated - take MAX per UUID):**
- 2025: 71,324 MW (**reduction of 6,834 MW = 8.7%**)
- 2026: 104,492 MW (**reduction of 16,584 MW = 13.7%**)
- 2030: 309,905 MW (**reduction of 46,192 MW = 13.0%**)

---

## Recommended Actions

### ✅ FIXED: Hyperscaler Deduplication Bug (2026-01-26)

Three changes were made to `semianalysis_pipeline.py`:

**Fix 1: Include Hyperscaler buildings in merge step**
- Moved Hyperscaler building extraction BEFORE Step 4 (merge_duplicates)
- Hyperscaler buildings now go through deduplication with NA/Overseas
- Source_Sheet values now correctly show `Hyperscalers, NA` for merged records

**Fix 2: Preserve tenant-attributed capacity as separate columns**
- AI Labs and Hyperscaler tabs are DESCRIPTIVE (WHO uses HOW MUCH)
- Their capacity values now preserved in prefixed columns:
  - `AI_2023, AI_2024, ... AI_2032` = Tenant-attributed capacity from AI Labs
  - `HS_2023, HS_2024, ... HS_2032` = Hyperscaler-attributed capacity
- Base capacity columns (`2023, 2024, ... 2032`) still use NA/OS as primary source

**Fix 3: Metadata enrichment preserved**
- AI Labs fields (end_user, tenant, gpu_cloud) are still joined to matching UUIDs
- Hyperscaler metadata is preserved for the 13 unique building records

### Output Column Structure After Fix

| Column Type | Count | Source | Purpose |
|-------------|-------|--------|---------|
| Base capacity (`2023`-`2032`) | 10 | NA/OS | Total building capacity |
| `AI_*` prefixed | 19 | AI Labs | Tenant-attributed capacity |
| `HS_*` prefixed | 16 | Hyperscaler | Hyperscaler-attributed capacity |
| Metadata (end_user, tenant, gpu_cloud) | 3 | AI Labs | WHO is using the facility |

### Sample Record (Multi-Source Merged)

```
UUID: 022180d4-3670-54d3-bf16-bba2a5a0ff0a
Company: QTS
Source_Sheet: AI Labs, Hyperscalers, NA

Capacity columns (2025):
  Base 2025 (total building):     295.0 MW  ← From NA/OS
  AI_2025 (tenant-attributed):    295.0 MW  ← From AI Labs
  HS_2025 (hyperscaler-attr):     295.0 MW  ← From Hyperscaler
```

### Source_Sheet Distribution After Fix

Records now show proper merge attribution:
- `AI Labs, Hyperscalers, NA`: 170 (all three sources merged)
- `AI Labs, NA`: 70 (AI Labs + NA merged)
- `Hyperscalers, NA`: 55 (Hyperscaler + NA merged)
- `Hyperscalers, Overseas`: 26 (Hyperscaler + Overseas merged)
- `Hyperscalers`: 13 (unique Hyperscaler records)

---

## Data Relationship Diagram (Updated)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    SEMIANALYSIS DATA RELATIONSHIPS                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  BUILDING-LEVEL RECORDS (Share UUIDs - MERGE before output)                 │
│  ═══════════════════════════════════════════════════════════                │
│                                                                             │
│  ┌─────────────────────┐     ┌─────────────────────┐                        │
│  │  NA Data Center     │     │  Overseas DC        │                        │
│  │  Supply             │     │  Supply             │                        │
│  │  ~240 buildings     │     │  ~2,500 buildings   │                        │
│  │  (all in AI Labs)   │     │  (28 in AI Labs)    │                        │
│  └──────────┬──────────┘     └──────────┬──────────┘                        │
│             │                           │                                   │
│             │    ┌──────────────────────┤                                   │
│             │    │                      │                                   │
│             ▼    ▼                      │                                   │
│  ┌─────────────────────────┐            │                                   │
│  │  AI Labs Sheet          │            │                                   │
│  │  ~269 records           │            │                                   │
│  │  99.6% overlap with NA/OS│           │                                   │
│  │  ENRICHES with:         │            │                                   │
│  │  - end_user             │            │                                   │
│  │  - tenant               │            │                                   │
│  │  - gpu_cloud            │            │                                   │
│  │                         │            │                                   │
│  │  [SUBSET - Correct]     │            │                                   │
│  └─────────────────────────┘            │                                   │
│                                         │                                   │
│  ┌─────────────────────────────────────┐│                                   │
│  │  Hyperscalers Buildings (rows 82+)  ││                                   │
│  │  ~283 records                       ││                                   │
│  │  95.4% overlap with NA/OS           ││                                   │
│  │                                     ││                                   │
│  │  KEY PATTERN:                       ││                                   │
│  │  - 70% show HALF capacity           ││                                   │
│  │  - Appears to track ONE PHASE       ││                                   │
│  │  - NA/OS has FULL capacity          ││                                   │
│  │                                     ││                                   │
│  │  [SUBSET - BUG: Not merged!]        ││                                   │
│  └─────────────────────────────────────┘│                                   │
│                                         │                                   │
│  ════════════════════════════════════════                                   │
│                      │                                                      │
│                      ▼                                                      │
│           ┌─────────────────────────┐                                       │
│           │  MERGE BY UUID          │                                       │
│           │  - SUM capacity cols    │                                       │
│           │  - FIRST for text       │                                       │
│           │  - Concat Source_Sheet  │                                       │
│           └─────────────────────────┘                                       │
│                      │                                                      │
│                      ▼                                                      │
│  ════════════════════════════════════════                                   │
│                                                                             │
│  MARKET-LEVEL AGGREGATES (ADDITIVE - Different UUIDs)                       │
│  ═══════════════════════════════════════════════════                        │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────┐            │
│  │  TLBM = Total Lease by Market                               │            │
│  │  - Hyperscaler leasing (~148 records)                       │            │
│  │  - Colo leasing (~135 records)                              │            │
│  │  - Synthetic UUIDs (TLBM_H_*, TLBM_C_*)                      │            │
│  │  - Market-level, not building-level                         │            │
│  │                                                              │            │
│  │  [ADDITIVE - Colo capacity not in building records]         │            │
│  └─────────────────────────────────────────────────────────────┘            │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Investigation Scripts Created

The following diagnostic scripts were created during this investigation:

| Script | Purpose |
|--------|---------|
| `check_source_overlap.py` | Initial overlap analysis |
| `check_source_overlap_v2.py` | UUID-level overlap check |
| `check_hyperscaler_duplicates.py` | Hyperscaler duplicate investigation |
| `investigate_hyperscaler_overlap.py` | Comprehensive 8-section analysis |
| `investigate_half_pattern.py` | Deep dive on the HALF ratio pattern |

All scripts are located in `scripts/_utils/`.

---

## Appendix: Raw Data

### Source_Sheet Distribution in Current Output

```
Source_Sheet           Count
---------------------------------
Overseas               2,503
Hyperscalers             386
AI Labs, NA              240
AI Labs, Overseas         28
AI Labs                    1
```

### Companies Most Affected by "HALF" Pattern

```
Company                Count of "HALF" Records
---------------------------------------------
AWS                    217
QTS                    156
Meta                   116
Microsoft               99
Compass Datacenters     51
Crusoe                  46
STACK Infrastructure    40
```

---

*Report generated: January 26, 2026*
*Author: Meta Data Center GIS Team*
