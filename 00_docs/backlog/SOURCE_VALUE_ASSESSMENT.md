# Feature Backlog: Data Source Value Assessment — WoodMac & Synergy

**Status:** 📋 Backlog
**Priority:** Medium
**Created:** 2026-01-21
**Requested By:** P. Anderson (per supervisor feedback)

---

## Overview

The current pipeline diagnostic report scores all data sources equally, which unfairly penalizes sources like WoodMac and Synergy that were purchased for **specific, supplemental purposes** rather than comprehensive coverage.

**Supervisor Feedback:**
> "I didn't want to weigh them all equally because they were bought to serve different, supplemental purposes."

This document outlines a plan to:
1. Identify unique value-adds from WoodMac and Synergy
2. Define source-specific evaluation criteria
3. Update the diagnostic scoring methodology

---

## Current State

### Current Scoring Approach (Equal Weighting)

All sources are graded on the same criteria:
- Spatial accuracy (distance to canonical)
- Capacity accuracy (MAPE vs canonical)
- Field completeness (% of required fields populated)
- Record coverage (% of known facilities)

**Result:** WoodMac and Synergy fail on capacity/spatial metrics despite providing unique data.

### Archive Notes (Why Excluded)

| Source | Archive Reason | Current Status |
|--------|----------------|----------------|
| **WoodMac** | "Requires manual geocoding" | Excluded from gold_buildings |
| **Synergy** | "No coordinates or capacity data" | Excluded from gold_buildings |

---

## Proposed Approach: Source-Specific Evaluation

### Step 1: Identify Unique Value-Adds

#### WoodMac — Potential Unique Fields

| Field Category | Potential Unique Data | Value-Add |
|----------------|----------------------|-----------|
| **Development Phases** | Tracks expansion phases, not just buildings | Phase-level capacity forecasting |
| **Cost Data** | Investment amounts, land costs | Financial analysis |
| **Developer/Owner** | More granular ownership tracking | M&A analysis, lease tracking |
| **Planned Capacity** | Future buildout projections | Long-term planning |
| **Market Analysis** | Market-level aggregations | Strategic planning |

**Recommended Analysis:**
```python
# Compare WoodMac fields to gold_buildings_full
woodmac_fields = set([f.name for f in arcpy.ListFields(woodmac_raw)])
gold_fields = set([f.name for f in arcpy.ListFields(gold_buildings_full)])

unique_to_woodmac = woodmac_fields - gold_fields
print(f"Fields unique to WoodMac: {unique_to_woodmac}")
```

#### Synergy — Potential Unique Fields

| Field Category | Potential Unique Data | Value-Add |
|----------------|----------------------|-----------|
| **News/Announcements** | Project announcement dates | Early warning signals |
| **Company Relationships** | Parent/subsidiary links | Corporate structure mapping |
| **Project Status Updates** | Detailed status tracking | Pipeline monitoring |
| **Geographic Coverage** | Different regional focus? | Fill gaps in other sources |

**Recommended Analysis:**
```python
# Compare Synergy fields to gold_buildings_full
synergy_fields = set([f.name for f in arcpy.ListFields(synergy_raw)])
unique_to_synergy = synergy_fields - gold_fields
print(f"Fields unique to Synergy: {unique_to_synergy}")
```

---

## Step 2: Define Source-Specific Evaluation Criteria

### Proposed Tiered Scoring System

#### Tier 1: Core Sources (Full Evaluation)
- DataCenterHawk Hyperscale
- DataCenterHawk Lease
- SemiAnalysis

**Evaluation Criteria:**
- Spatial accuracy (25%)
- Capacity accuracy (25%)
- Field completeness (25%)
- Record coverage (25%)

#### Tier 2: Supplemental Sources (Value-Add Evaluation)
- WoodMac
- Synergy
- NewProjectMedia

**Evaluation Criteria:**
- **Unique field contribution** (40%) — Fields not in Tier 1 sources
- **Incremental coverage** (30%) — Facilities/regions not in Tier 1
- **Data freshness** (20%) — How current is the data?
- **Accuracy where applicable** (10%) — Only for overlapping fields

#### Tier 3: Reference Sources (Validation Only)
- Meta Canonical
- DataCenterMap

**Evaluation Criteria:**
- Ground truth comparison
- Not scored, used for validation

---

## Step 3: Implementation Plan

### Phase 1: Data Discovery (2-3 hours)

**Goal:** Catalog unique fields from WoodMac and Synergy

**Tasks:**
- [ ] Query `woodmac_campus_raw` and `woodmac_dc_raw` schemas
- [ ] Query `synergy_raw` schema
- [ ] Compare to `gold_buildings_full` schema
- [ ] Document unique fields with sample values
- [ ] Identify fields that align with v2.0 schema gaps (developer, tenant, end_user, etc.)

**Script:** `scripts/04_analysis/analyze_source_unique_fields.py`

### Phase 2: Value Assessment (2-3 hours)

**Goal:** Quantify the unique contribution of each source

**Metrics to Calculate:**
- % of facilities with data in WoodMac/Synergy but NOT in core sources
- Unique fields populated (e.g., developer, cost data)
- Regional coverage gaps filled
- Historical data depth

**Output:** Value assessment report with recommendations

### Phase 3: Scoring Methodology Update (3-4 hours)

**Goal:** Update pipeline diagnostic to use tiered scoring

**Changes:**
- [ ] Add source tier classification to diagnostic
- [ ] Create separate scoring rubrics by tier
- [ ] Update report template with tiered grading
- [ ] Add "Unique Value" section for Tier 2 sources

---

## Effort vs. Return Analysis

| Phase | Effort | Return | Priority |
|-------|--------|--------|----------|
| Data Discovery | 2-3 hrs | High — Identifies what we're missing | 🔴 High |
| Value Assessment | 2-3 hrs | High — Quantifies ROI of each source | 🔴 High |
| Scoring Update | 3-4 hrs | Medium — Better diagnostic reports | 🟡 Medium |

**Total Effort:** 7-10 hours

**Expected Return:**
- Clear understanding of WoodMac/Synergy value
- Fair evaluation that reflects source purpose
- Potential to unlock new fields for consensus model
- Better-informed data procurement decisions

---

## Key Questions to Answer

### WoodMac
1. What fields does WoodMac provide that no other source has?
2. Does WoodMac have better **developer/owner** tracking?
3. Does WoodMac provide **cost/investment** data?
4. Is WoodMac's **phase tracking** valuable for expansion forecasting?
5. What is WoodMac's geographic coverage vs. DCH/SemiAnalysis?

### Synergy
1. What unique fields does Synergy provide?
2. Does Synergy have better **announcement/news** tracking?
3. Does Synergy cover **different regions** than other sources?
4. Is Synergy's data more **current** for certain project types?
5. Does Synergy track **company relationships** (parent/subsidiary)?

### General
1. Should WoodMac/Synergy be added to gold_buildings or kept as reference?
2. What fields from v2.0 schema can WoodMac/Synergy populate?
3. Should diagnostic reports show "Tier 1" and "Tier 2" grades separately?

---

## Potential Outcomes

### Outcome A: Significant Unique Value Found

If WoodMac/Synergy have valuable unique fields:
1. Create ingestion scripts to add to gold_buildings
2. Map unique fields to v2.0 schema (developer, tenant, cost, etc.)
3. Update diagnostic to credit unique contributions
4. Document which use cases each source serves

### Outcome B: Limited Unique Value

If overlap is high and unique value is low:
1. Keep as reference/validation sources only
2. Update diagnostic to exempt from capacity scoring
3. Document decision rationale for stakeholders
4. Consider ROI for future renewals

### Outcome C: Valuable for Specific Use Cases

If valuable for niche purposes (e.g., cost analysis, regional coverage):
1. Create separate "supplemental" feature class
2. Link to gold_buildings via UCID but keep separate
3. Build specialized reports/dashboards for those use cases
4. Update diagnostic with use-case-specific scoring

---

## Scripts to Create

```
scripts/
├── 04_analysis/
│   ├── analyze_source_unique_fields.py   # NEW - Field comparison
│   ├── assess_source_value.py            # NEW - Value quantification
│   └── compare_source_coverage.py        # NEW - Coverage gap analysis
├── 06_visualization/
│   └── generate_diagnostic_report.py     # UPDATE - Tiered scoring
```

---

## Related Documents

- Archive README: `scripts/_archive/README.md`
- Schema comparison: `scripts/00_docs/schemas/SCHEMA_COMPARISON_ANALYSIS.md`
- Capacity definitions: `scripts/00_docs/schemas/CAPACITY_FIELD_DEFINITIONS.md`
- Current diagnostic: `scripts/06_visualization/generate_capacity_presentation_charts.py`

---

## Next Steps

1. **Quick Win:** Run field comparison to identify unique WoodMac/Synergy fields (30 min)
2. **Assessment:** Document which v2.0 fields each source could populate (1 hr)
3. **Decision:** Recommend whether to integrate or keep as reference (with supervisor)
4. **Implementation:** Update diagnostic and/or create ingestion scripts

---

## Sample Analysis Query

```python
# Quick field comparison script
import arcpy
from config import GDB

def compare_source_fields():
    """Compare fields across all sources to identify unique contributions."""

    sources = {
        'gold_buildings_full': 'Core schema',
        'woodmac_campus_raw': 'WoodMac Campus',
        'woodmac_dc_raw': 'WoodMac DC',
        'synergy_raw': 'Synergy',
    }

    all_fields = {}
    for table, label in sources.items():
        path = os.path.join(GDB, table)
        if arcpy.Exists(path):
            fields = [f.name for f in arcpy.ListFields(path)]
            all_fields[label] = set(fields)
            print(f"\n{label}: {len(fields)} fields")

    # Find unique fields
    core = all_fields.get('Core schema', set())

    for source, fields in all_fields.items():
        if source != 'Core schema':
            unique = fields - core
            if unique:
                print(f"\n{source} unique fields ({len(unique)}):")
                for f in sorted(unique):
                    print(f"  - {f}")
```

---

*Created to address supervisor feedback on source-specific evaluation*
