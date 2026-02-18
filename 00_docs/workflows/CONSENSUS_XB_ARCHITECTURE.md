# 🏗️ Consensus Layer XB Architecture — Performance Considerations

**Created:** January 9, 2026
**Status:** 📋 DESIGN DECISION NEEDED
**Context:** How to deliver consensus data to Experience Builder without performance bloat

---

## 🎯 The Core Question

> "How do we render ONE geometry per campus with BAV attributes, while still allowing users to drill down to per-source details, WITHOUT consuming excessive portal tokens or making XB slow?"

---

## 📊 Three Architectural Options

### Option A: Pre-computed Single Layer (RECOMMENDED)

**Concept:** Generate `consensus_campus` as a complete, pre-computed layer during the pipeline. XB consumes it as-is with no runtime processing.

```
┌─────────────────────────────────────────────────────────────────┐
│  PIPELINE (Python)                                               │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ gold_buildings_full → Group by UCID → consensus_campus      ││
│  │                                                              ││
│  │ For each UCID:                                               ││
│  │   1. Select geometry from highest-authority source           ││
│  │   2. Apply BAV logic for each attribute                      ││
│  │   3. Build source_details_json with all source values        ││
│  │   4. Calculate confidence_score                              ││
│  └─────────────────────────────────────────────────────────────┘│
│                            │                                     │
│                            ▼                                     │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ consensus_campus (Single Layer)                              ││
│  │ ─────────────────────────────────────────────────────────── ││
│  │ • ~11,715 records (one per UCID)                            ││
│  │ • All BAV attributes pre-computed                           ││
│  │ • source_details_json field (TEXT 4000)                     ││
│  │ • Fully indexed for filtering                               ││
│  └─────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────┘
                            │
                            │ Publish
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│  XB (Runtime)                                                    │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ Filter Widgets (Simple field queries - FAST)                ││
│  │ • company_clean_filter = 'AWS'                              ││
│  │ • full_capacity_mw >= 100                                   ││
│  │ • is_essential = 1                                          ││
│  │ • region = 'AMER'                                           ││
│  └─────────────────────────────────────────────────────────────┘│
│                                                                  │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ Popup (Arcade - ONLY on feature click)                      ││
│  │ • Parses source_details_json for drill-down                 ││
│  │ • Runs ONCE when user clicks a single feature               ││
│  │ • ~2-4KB JSON parse = instantaneous                         ││
│  └─────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────┘
```

**Pros:**
- ✅ **Fastest XB performance** - no runtime deduplication
- ✅ **Simple filters** - standard field queries on indexed columns
- ✅ **Minimal Arcade** - only for popup drill-down (on-click, not on-load)
- ✅ **Single layer to manage** - simpler than related tables
- ✅ **Works offline** - no server-side processing needed

**Cons:**
- ⚠️ JSON field length limit (4000 chars) - may need to test with 6 sources
- ⚠️ Popup JSON parsing is one-way (can't update source values from popup)
- ⚠️ Must regenerate layer when sources update (already doing this)

**Performance Characteristics:**
| Operation | Load Type | Expected Performance |
|-----------|-----------|---------------------|
| Initial map load | ~11,715 points | Fast (standard layer) |
| Filter by company | WHERE clause | Instant (indexed) |
| Filter by capacity | WHERE clause | Instant (indexed) |
| Click feature popup | Arcade JSON parse | Instant (~2-4KB) |
| Render all features | Standard symbology | Fast (pre-computed) |

---

### Option B: Main Layer + Related Table

**Concept:** Separate the consensus attributes from the per-source details using a relationship class.

```
┌─────────────────────────────────────────────────────────────────┐
│  consensus_campus (Main Layer)                                   │
│  ─────────────────────────────────────────────────────────────── │
│  • ucid (PK)                                                     │
│  • All BAV attributes (no JSON)                                  │
│  • geometry (from best authority)                                │
│  • confidence_score                                              │
│  └──────────────────────────────────────────────────────────────│
│           │                                                       │
│           │ 1:M Relationship                                      │
│           ▼                                                       │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │  consensus_source_values (Related Table)                     ││
│  │  • ucid (FK)                                                 ││
│  │  • source                                                    ││
│  │  • field_name                                                ││
│  │  • field_value                                               ││
│  │  • is_selected (Y/N - was this the BAV?)                     ││
│  └─────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────┘
```

**Pros:**
- ✅ **Normalized data** - no JSON parsing needed
- ✅ **No field length limits** - can store unlimited source details
- ✅ **Queryable related records** - can search/filter source values
- ✅ **Cleaner data model** - follows GIS best practices

**Cons:**
- ⚠️ **More complex to set up** - requires relationship class in Portal
- ⚠️ **Related record queries can be slower** - especially with many sources
- ⚠️ **Two layers to maintain** - sync issues possible
- ⚠️ **XB related table widget** - may not render as nicely as formatted popup

**Performance Characteristics:**
| Operation | Load Type | Expected Performance |
|-----------|-----------|---------------------|
| Initial map load | ~11,715 points | Fast |
| Filter by company | WHERE clause | Instant |
| Click feature popup | Related query | Moderate (~6 records per UCID) |
| Show all source values | Join query | Slower if many records |

---

### Option C: On-the-fly Deduplication in XB (NOT RECOMMENDED)

**Concept:** Keep `gold_combined_xb` (34k records) and use Arcade/layer views to deduplicate at runtime.

```
┌─────────────────────────────────────────────────────────────────┐
│  gold_combined_xb (34,411 records)                               │
│  • All 6 sources × all campuses                                  │
│  • Multiple geometries per physical location                     │
│                            │                                     │
│                            ▼                                     │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ XB Arcade/FeatureSet Deduplication (Runtime)                 ││
│  │ • GroupBy UCID                                               ││
│  │ • Select best source per field                               ││
│  │ • RUNS ON EVERY MAP INTERACTION                              ││
│  └─────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────┘
```

**Pros:**
- ✅ Always uses latest data (no regeneration needed)
- ✅ Users can toggle which source to prefer

**Cons:**
- ❌ **SLOW** - deduplication runs on every filter/pan/zoom
- ❌ **Token consumption** - complex Arcade expressions burn credits
- ❌ **34k records** - much larger dataset to process
- ❌ **Complex Arcade** - hard to maintain, error-prone
- ❌ **Poor UX** - visible lag during interactions

**Performance Characteristics:**
| Operation | Load Type | Expected Performance |
|-----------|-----------|---------------------|
| Initial map load | ~34,411 points + dedup | SLOW |
| Filter by company | Arcade + WHERE | SLOW |
| Pan/Zoom | Re-deduplication | SLOW |
| Any interaction | Runtime processing | SLOW |

---

## 🏆 RECOMMENDATION: Option A (Pre-computed Single Layer)

For your use case, **Option A is strongly recommended** because:

1. **Performance is critical** - XB should feel snappy, not laggy
2. **Filters are the main interaction** - simple WHERE clauses are fast
3. **Drill-down is secondary** - users only need source details occasionally
4. **You're already regenerating weekly** - no additional workflow complexity
5. **11k records is manageable** - well within Portal performance limits

### Hybrid Enhancement: "View Raw Data" Link

If users want to see the full multi-source view for a specific campus, add a **link in the popup** that opens a filtered view of `gold_combined_xb`:

```javascript
// In popup Arcade expression
var link = "https://your-portal.com/apps/xb/?ucid=" + $feature.ucid;
return "🔍 <a href='" + link + "'>View all source records</a>";
```

This gives users the best of both worlds:
- Fast consensus layer for normal browsing
- Full source data available on-demand

---

## 📋 Schema for Option A: `consensus_campus`

| Field | Type | Length | Purpose | XB Widget |
|-------|------|--------|---------|-----------|
| **Identity** |
| `ucid` | TEXT | 50 | Primary key | — |
| `canonical_name` | TEXT | 100 | Display name | Search |
| `company_clean` | TEXT | 50 | Standardized company | Filter |
| `company_clean_filter` | TEXT | 50 | XB categories | Filter dropdown |
| **Location** |
| `region` | TEXT | 10 | AMER/EMEA/APAC | Filter |
| `country` | TEXT | 50 | Country | Filter |
| `state_abbr` | TEXT | 10 | State/Province | Filter |
| `city` | TEXT | 50 | City | Filter |
| `latitude` | DOUBLE | — | Y coordinate | — |
| `longitude` | DOUBLE | — | X coordinate | — |
| `geometry_source` | TEXT | 30 | Which source provided geometry | Info |
| **Capacity (BAV)** |
| `full_capacity_mw` | DOUBLE | — | Best available | Range slider |
| `full_capacity_source` | TEXT | 30 | Attribution | Popup |
| `commissioned_mw` | DOUBLE | — | Best available | Range slider |
| `commissioned_source` | TEXT | 30 | Attribution | Popup |
| `uc_mw` | DOUBLE | — | Best available | — |
| `planned_mw` | DOUBLE | — | Best available | — |
| **Status (BAV)** |
| `facility_status` | TEXT | 30 | Best available | Filter dropdown |
| `status_source` | TEXT | 30 | Attribution | Popup |
| `building_count` | SHORT | — | Best available | — |
| **Flags** |
| `is_essential` | SHORT | — | Strategic site (0/1) | Toggle filter |
| **Source Tracking** |
| `source_count` | SHORT | — | How many sources | Symbology |
| `sources` | TEXT | 200 | Semicolon list | Popup |
| `data_vintage` | DATE | — | Most recent | Filter |
| **Drill-Down** |
| `source_details_json` | TEXT | 4000 | Per-source values | Popup Arcade |
| **Quality** |
| `confidence_score` | DOUBLE | — | 0-1 quality score | Symbology |
| `consensus_generated` | DATETIME | — | When layer was built | Info |

**Total Fields:** ~25 (manageable, well-indexed)

---

## 🔧 XB Widget Configuration

### Filter Panel (Left Sidebar)

| Widget | Field | Type |
|--------|-------|------|
| **Company Filter** | `company_clean_filter` | Dropdown (9 values) |
| **Region Filter** | `region` | Dropdown (3 values) |
| **Status Filter** | `facility_status` | Dropdown |
| **Capacity Range** | `full_capacity_mw` | Slider (0-5000 MW) |
| **Essential Toggle** | `is_essential` | Checkbox |
| **Multi-Source Toggle** | `source_count >= 2` | Checkbox |
| **Vintage Range** | `data_vintage` | Date range |

### Popup Configuration

```javascript
// Arcade expression for popup content
var details = JSON($feature.source_details_json);

// Header
var output = "━━━ CONSENSUS VALUES ━━━\n";
output += "Full Capacity: " + Round($feature.full_capacity_mw, 1) + " MW";
output += " (" + $feature.full_capacity_source + ")\n";
output += "Commissioned: " + Round($feature.commissioned_mw, 1) + " MW";
output += " (" + $feature.commissioned_source + ")\n";
output += "Status: " + $feature.facility_status;
output += " (" + $feature.status_source + ")\n\n";

// Source drill-down
output += "━━━ SOURCE DETAILS ━━━\n";
var sources = ["Meta Canonical", "Semianalysis", "DataCenterHawk",
               "DCH Lease", "NPM", "DataCenterMap"];

for (var i in sources) {
    var src = sources[i];
    if (HasKey(details, src) && details[src].has_data) {
        var d = details[src];
        output += "\n▸ " + src + " (Rank " + d.authority_rank + ")\n";
        for (var key in d.values) {
            if (d.values[key] != null) {
                output += "  " + key + ": " + d.values[key] + "\n";
            }
        }
    }
}

return output;
```

### Symbology Recommendations

| Renderer | Based On | Purpose |
|----------|----------|---------|
| **Primary** | `company_clean_filter` | Color by hyperscaler |
| **Secondary** | `is_essential` | Highlight strategic sites |
| **Size** | `full_capacity_mw` | Proportional symbols |
| **Transparency** | `confidence_score` | Low confidence = more transparent |

---

## 📐 JSON Field Size Analysis

**Question:** Will 4000 characters be enough for 6 sources?

**Estimate per source:**
```json
{
  "Semianalysis": {
    "authority_rank": 2,
    "has_data": true,
    "data_vintage": "2025-11-15",
    "values": {
      "full_capacity_mw": 450,
      "commissioned_mw": 280,
      "mw_2025": 280,
      "mw_2030": 450
    }
  }
}
```
**~200-300 characters per source with data**

**6 sources × 300 chars = ~1800 characters** → ✅ Well under 4000 limit

Even with verbose values, we have ~2x headroom.

---

## ✅ Decision Checklist

- [ ] Confirm Option A (Pre-computed Single Layer) is acceptable
- [ ] Confirm JSON field (4000 chars) is sufficient
- [ ] Confirm popup Arcade approach for drill-down
- [ ] Decide if "View Raw Data" link to gold_combined_xb is needed
- [ ] Proceed with `generate_consensus_layer.py` implementation

---

*Document Version: 1.0 — January 9, 2026*
