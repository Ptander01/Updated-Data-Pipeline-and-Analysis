# 🎯 Consensus Layer Design — Single Authoritative Geometry with Source Drill-Down

**Created:** January 6, 2026
**Status:** 📋 DESIGN PHASE
**Version:** 1.0
**Session Focus:** Portal Publishing + Deduplication + XB Integration

---

## 📋 Executive Summary

**The Problem:**
Currently, each data center campus can have up to 6 records in `gold_combined_xb` (one per source), creating visual clutter and confusion when rendering in Experience Builder. Users see 6 dots for a single physical location.

**The Solution:**
Create a **Consensus Record Layer** (`consensus_campus`) that renders:
- **ONE geometry** per physical campus (based on most authoritative source)
- **"Best Available Value" attributes** ranked by source authority hierarchy
- **Drill-down capability** to see what each source reported

---

## 🏗️ End-State Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          XB Map Display                                      │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                                                                      │    │
│  │    📍 Single Dot Per Campus                                         │    │
│  │         ↓                                                           │    │
│  │    ┌─────────────────────────────────────────────────────────┐      │    │
│  │    │ 🏢 Microsoft San Antonio                                │      │    │
│  │    │ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ │      │    │
│  │    │ CONSENSUS VALUES (Best Available)                       │      │    │
│  │    │   Full Capacity:     450 MW (from Semianalysis)         │      │    │
│  │    │   Commissioned:      280 MW (from DCH Hyper)            │      │    │
│  │    │   Status:            Active (from Meta Canonical)       │      │    │
│  │    │   Building Count:    12 (from DCH Hyper)                │      │    │
│  │    │   Region:            AMER                               │      │    │
│  │    │ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ │      │    │
│  │    │ ▼ SOURCE DETAILS (Click to Expand)                      │      │    │
│  │    │ ┌─────────────────────────────────────────────────────┐ │      │    │
│  │    │ │ 🔵 Meta Canonical (Authority: 1)                    │ │      │    │
│  │    │ │    - Status: Active ✓                               │ │      │    │
│  │    │ │    - IT Load: 265 MW                                │ │      │    │
│  │    │ │    - Data Vintage: 2025-12-01                       │ │      │    │
│  │    │ ├─────────────────────────────────────────────────────┤ │      │    │
│  │    │ │ 🟢 Semianalysis (Authority: 2)                      │ │      │    │
│  │    │ │    - Full Capacity: 450 MW ✓                        │ │      │    │
│  │    │ │    - mw_2025: 280 MW                                │ │      │    │
│  │    │ │    - mw_2030: 450 MW                                │ │      │    │
│  │    │ │    - Data Vintage: 2025-11-15                       │ │      │    │
│  │    │ ├─────────────────────────────────────────────────────┤ │      │    │
│  │    │ │ 🟡 DCH Hyper (Authority: 3)                         │ │      │    │
│  │    │ │    - Commissioned: 280 MW ✓                         │ │      │    │
│  │    │ │    - Buildings: 12 ✓                                │ │      │    │
│  │    │ │    - Data Vintage: 2025-10-20                       │ │      │    │
│  │    │ └─────────────────────────────────────────────────────┘ │      │    │
│  │    └─────────────────────────────────────────────────────────┘      │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 🏆 Source Authority Hierarchy

### Overall Authority Ranking (for Geometry & Default Attributes)

| Rank | Source | Rationale | Best For |
|------|--------|-----------|----------|
| **1** | **Meta Canonical** | Internal ground truth, verified data | Status, IT Load, Ownership |
| **2** | **Semianalysis** | 43.2% accuracy vs Meta (best external) | Full capacity, Forecasts (mw_2024-2032) |
| **3** | **DCH Hyper** | 39.2% accuracy, building-level detail | Commissioned, Building counts |
| **4** | **DCH Lease** | Leased facility specifics | Lease details, Tenant info |
| **5** | **NPM** | US announced projects | Announced projects, Costs |
| **6** | **DataCenterMap** | Volume (37% of records) | Geographic coverage |

### Field-Level Authority Matrix

Different fields have different authoritative sources. When building consensus records, use the **first available** value based on this hierarchy:

| Field | Priority 1 | Priority 2 | Priority 3 | Priority 4 | Notes |
|-------|-----------|-----------|-----------|-----------|-------|
| **latitude/longitude** | Meta Canonical | Semianalysis | DCH Hyper | DCM | Geometry source |
| **company_clean** | Meta Canonical | DCH Hyper | Semianalysis | DCM | Company standardization |
| **facility_status** | Meta Canonical | DCH Hyper | DCH Lease | NPM | Operational state |
| **commissioned_power_mw** | Meta Canonical | DCH Hyper | Semianalysis | DCH Lease | Current IT power |
| **full_capacity_mw** | Semianalysis | DCH Hyper | DCH Lease | NPM | Total potential |
| **uc_power_mw** | Semianalysis | DCH Hyper | NPM | — | Under construction |
| **planned_power_mw** | Semianalysis | NPM | DCH Hyper | — | Future pipeline |
| **building_count** | DCH Hyper | Meta Canonical | Semianalysis | — | Physical structures |
| **sqft** | DCH Lease | DCH Hyper | DCM | — | Square footage |
| **mw_2024 - mw_2032** | Semianalysis | — | — | — | Only Semianalysis has forecasts |
| **data_vintage** | Most Recent | — | — | — | Latest update wins |

### PUE Adjustment Rules

> **✅ CONFIRMED (Session 10):** Testing revealed DCH reports IT capacity, NOT facility power.
> Applying ÷1.3 adjustment made accuracy WORSE (23.5% MAPE vs 17.6% without adjustment).
> **No PUE adjustment is needed for any source.**

| Source | Reports | Adjustment Needed |
|--------|---------|-------------------|
| Meta Canonical | IT Load | None |
| Semianalysis | IT Capacity | None |
| DCH Hyper | IT Capacity | **None** (confirmed) |
| DCH Lease | IT Capacity | None |
| NPM | Design Capacity | None |

---

## 📊 Data Model

### Option A: Flattened Consensus Table (Recommended for XB)

A single feature class where source details are stored as JSON attributes.

**Feature Class:** `consensus_campus`

| Field | Type | Description |
|-------|------|-------------|
| `ucid` | TEXT(20) | Universal Campus ID (primary key) |
| `canonical_name` | TEXT(100) | Standardized campus name |
| `company_clean` | TEXT(50) | Standardized company (BAV) |
| `company_clean_filter` | TEXT(50) | XB filter value |
| `region` | TEXT(10) | AMER/EMEA/APAC |
| `country` | TEXT(50) | Country |
| `state_abbr` | TEXT(10) | State/Province |
| `city` | TEXT(50) | City |
| `latitude` | DOUBLE | Consensus latitude |
| `longitude` | DOUBLE | Consensus longitude |
| `geometry_source` | TEXT(20) | Which source provided geometry |
| **Consensus Capacity Fields** |
| `full_capacity_mw` | DOUBLE | Best available value |
| `full_capacity_source` | TEXT(20) | Source of full_capacity |
| `commissioned_mw` | DOUBLE | Best available value |
| `commissioned_source` | TEXT(20) | Source of commissioned |
| `uc_mw` | DOUBLE | Best available value |
| `planned_mw` | DOUBLE | Best available value |
| **Consensus Status Fields** |
| `facility_status` | TEXT(30) | Best available status |
| `status_source` | TEXT(20) | Source of status |
| `building_count` | SHORT | Best available count |
| `building_count_source` | TEXT(20) | Source of building_count |
| **Source Tracking** |
| `source_count` | SHORT | Number of sources with data |
| `sources` | TEXT(200) | Semicolon-separated list |
| `data_vintage` | DATE | Most recent source update |
| **Source Detail JSON** |
| `source_details_json` | TEXT(4000) | JSON with per-source values |
| **Metadata** |
| `consensus_generated` | DATETIME | When record was generated |
| `confidence_score` | DOUBLE | Overall data confidence (0-1) |

### Source Details JSON Structure

```json
{
  "Meta Canonical": {
    "authority_rank": 1,
    "has_data": true,
    "data_vintage": "2025-12-01",
    "values": {
      "it_load_mw": 265,
      "status": "Active",
      "owned_leased": "Owned",
      "building_count": 8
    }
  },
  "Semianalysis": {
    "authority_rank": 2,
    "has_data": true,
    "data_vintage": "2025-11-15",
    "values": {
      "full_capacity_mw": 450,
      "commissioned_mw": 280,
      "mw_2025": 280,
      "mw_2026": 320,
      "mw_2030": 450
    }
  },
  "DataCenterHawk": {
    "authority_rank": 3,
    "has_data": true,
    "data_vintage": "2025-10-20",
    "values": {
      "commissioned_mw": 280,
      "building_count": 12,
      "sqft": 1250000
    }
  },
  "DCH Lease": {
    "authority_rank": 4,
    "has_data": false
  },
  "NPM": {
    "authority_rank": 5,
    "has_data": false
  },
  "DataCenterMap": {
    "authority_rank": 6,
    "has_data": true,
    "data_vintage": "2025-09-01",
    "values": {
      "full_capacity_mw": null,
      "lat": 29.4241,
      "lon": -98.4936
    }
  }
}
```

### Option B: Related Table Design (Alternative)

For more complex drill-down scenarios, use a related table.

**Main Table:** `consensus_campus` (as above, without `source_details_json`)

**Related Table:** `consensus_source_values`

| Field | Type | Description |
|-------|------|-------------|
| `record_id` | LONG | Auto-increment PK |
| `ucid` | TEXT(20) | FK to consensus_campus |
| `source` | TEXT(30) | Source name |
| `authority_rank` | SHORT | 1-6 ranking |
| `field_name` | TEXT(50) | Field being reported |
| `field_value` | TEXT(100) | Value as string |
| `field_value_numeric` | DOUBLE | Numeric value if applicable |
| `is_consensus_value` | TEXT(1) | Y/N - was this selected? |
| `data_vintage` | DATE | Source data date |
| `raw_value` | TEXT(100) | Original value before adjustment |
| `adjustment_applied` | TEXT(50) | e.g., "÷1.3 PUE" |

**Relationship:** `consensus_campus.ucid` → `consensus_source_values.ucid` (1:M)

---

## 🔧 Implementation Workflow

### Phase 1: Create Consensus Generation Script (Week 1)

```
07_consensus/
├── generate_consensus_layer.py      # Main script
├── authority_config.py              # Source rankings & field mappings
├── bav_resolver.py                  # Best Available Value logic
└── validate_consensus.py            # QA checks
```

**Algorithm:**

```python
def generate_consensus_record(ucid: str, source_records: List[Dict]) -> Dict:
    """
    Generate a single consensus record from multiple source records.

    1. Sort source_records by authority_rank
    2. For each field in FIELD_AUTHORITY_MATRIX:
       - Walk through sources in priority order
       - Take first non-null value
       - Apply adjustments (e.g., PUE)
       - Record which source provided the value
    3. Build source_details_json for drill-down
    4. Calculate confidence_score based on source agreement
    """
    consensus = {'ucid': ucid}
    source_details = {}

    for field, priority_list in FIELD_AUTHORITY_MATRIX.items():
        for source in priority_list:
            value = get_value(source_records, source, field)
            if value is not None:
                adjusted_value = apply_adjustment(source, field, value)
                consensus[field] = adjusted_value
                consensus[f"{field}_source"] = source
                break

    # Build JSON for popup drill-down
    for record in source_records:
        source_details[record['source']] = {
            'authority_rank': AUTHORITY_RANKING[record['source']],
            'has_data': True,
            'data_vintage': record.get('data_vintage'),
            'values': extract_relevant_fields(record)
        }

    consensus['source_details_json'] = json.dumps(source_details)
    return consensus
```

### Phase 2: XB Popup Configuration (Week 2)

**Arcade Expression for Dynamic Popup:**

```javascript
// Popup Arcade Expression for Source Details
var details = JSON($feature.source_details_json);
var output = "";

// Sort by authority rank
var sources = ["Meta Canonical", "Semianalysis", "DataCenterHawk",
               "DCH Lease", "NPM", "DataCenterMap"];

for (var i in sources) {
    var src = sources[i];
    if (HasKey(details, src) && details[src].has_data) {
        var d = details[src];
        output += "━━━ " + src + " (Rank " + d.authority_rank + ") ━━━\n";
        output += "  Data Vintage: " + d.data_vintage + "\n";

        for (var key in d.values) {
            if (d.values[key] != null) {
                output += "  • " + key + ": " + d.values[key] + "\n";
            }
        }
        output += "\n";
    }
}

return output;
```

### Phase 3: Portal Publishing (Week 3)

```python
# 08_publishing/publish_to_portal.py

import arcpy
from arcgis.gis import GIS

def publish_consensus_layer():
    """
    Publish consensus_campus to ArcGIS Enterprise Portal.
    """
    # Connect to portal
    gis = GIS("https://your-portal.esri.com", "username", "password")

    # Export feature class to File GDB
    export_gdb = r"C:\Temp\ConsensusExport.gdb"
    arcpy.conversion.FeatureClassToFeatureClass(
        CONSENSUS_CAMPUS,
        export_gdb,
        "consensus_campus"
    )

    # Create SD draft
    draft = arcpy.sharing.CreateSharingDraft(
        "HOSTING_SERVER",
        "FEATURE",
        "Consensus Data Centers",
        export_gdb + "/consensus_campus"
    )

    # Configure sharing
    draft.summary = "Consensus data center layer with best available values"
    draft.tags = "data centers, consensus, infrastructure"
    draft.portalFolder = "Infrastructure Planning"

    # Analyze and publish
    draft.exportToSDDraft(sd_draft_path)
    arcpy.server.StageService(sd_draft_path, sd_path)
    arcpy.server.UploadServiceDefinition(sd_path, "HOSTING_SERVER")
```

---

## 📅 Implementation Timeline

| Week | Phase | Deliverables |
|------|-------|--------------|
| **Week 1** | Consensus Layer Script | `generate_consensus_layer.py`, `authority_config.py` |
| **Week 2** | Validation & Refinement | `validate_consensus.py`, tuned authority matrix |
| **Week 3** | XB Integration | Popup Arcade expressions, symbology |
| **Week 4** | Portal Publishing | Published feature service, refresh automation |
| **Week 5** | Documentation & Training | User guide, refresh SOP |

---

## ✅ Success Criteria

| Metric | Target | Validation |
|--------|--------|------------|
| Single geometry per UCID | 100% | No duplicate UCIDs in consensus_campus |
| Meta Canonical attribution | 100% | All Meta sites show Meta as primary source |
| Popup drill-down works | 100% | JSON parses correctly in Arcade |
| Field-level source tracking | 100% | Every field has `*_source` populated |
| Confidence score calculated | 100% | All records have score 0-1 |
| XB filters functional | 100% | company_clean_filter works |

---

## 🔄 Refresh Strategy

**Trigger:** When any source ingestion script runs

**Process:**
1. Re-run campus rollup (`campus_rollup_new.py`)
2. Re-run consensus generation (`generate_consensus_layer.py`)
3. Truncate and reload portal feature service
4. Log refresh in pipeline diagnostics

**Frequency:** Weekly or on-demand

---

## 📝 Open Questions

1. **JSON field length:** Will 4000 chars be enough for 6 sources? (Need to test)
2. **Arcade performance:** How does JSON parsing perform with 11,000+ records?
3. **Related table vs JSON:** Should we pilot both and compare UX?
4. **Confidence scoring formula:** Weight by coverage + agreement + freshness?

---

## 📚 Related Documents

| Document | Path | Relationship |
|----------|------|--------------|
| UCID_DESIGN.md | `00_docs/workflows/` | Defines UCID clustering logic |
| GRANULARITY_STRATEGY.md | `00_docs/workflows/` | Building vs Campus rules |
| CAPACITY_FIELD_DEFINITIONS.md | `00_docs/schemas/` | Source-specific field meanings |
| CAPACITY_CONCEPTS_DIAGRAM.md | `00_docs/schemas/` | Capacity field hierarchy |

---

*Document Version: 1.0 — January 6, 2026*
