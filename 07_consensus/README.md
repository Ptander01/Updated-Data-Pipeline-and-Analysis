# 07_consensus — Consensus Layer Generation

**Purpose:** Generate a single authoritative record per campus from multiple data sources.

**Design Document:** `../00_docs/workflows/CONSENSUS_LAYER_DESIGN.md`

---

## 📁 Scripts

| Script | Purpose | Status |
|--------|---------|--------|
| `authority_config.py` | Source rankings & field-level priority matrices | ✅ Created |
| `generate_consensus_layer.py` | Main consensus generation script | 🔲 Planned |
| `bav_resolver.py` | Best Available Value resolution logic | 🔲 Planned |
| `validate_consensus.py` | QA checks on consensus output | 🔲 Planned |

---

## 🎯 Core Concept

**Problem:** Each campus can have up to 6 records (one per source) in `gold_combined_xb`, causing visual clutter.

**Solution:** Create `consensus_campus` with:
- **ONE geometry** per UCID (best authoritative source)
- **Best Available Value** attributes ranked by source authority
- **Source Details JSON** for drill-down capability in XB popups

---

## 🏆 Authority Hierarchy

| Rank | Source | Best For |
|------|--------|----------|
| 1 | Meta Canonical | Status, IT Load, Ownership |
| 2 | Semianalysis | Full capacity, Forecasts |
| 3 | DataCenterHawk | Commissioned, Building counts |
| 4 | DCH Lease | Lease details, Tenant info |
| 5 | NPM | Announced projects, Costs |
| 6 | DataCenterMap | Geographic coverage |

---

## 🔧 Usage

```python
# Run from ArcGIS Pro Python window

# 1. Generate consensus layer
exec(open(r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\scripts\07_consensus\generate_consensus_layer.py", encoding='utf-8').read())

# 2. Validate output
exec(open(r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\scripts\07_consensus\validate_consensus.py", encoding='utf-8').read())
```

---

## 📊 Output

**Feature Class:** `consensus_campus`

**Key Fields:**
- `ucid` — Universal Campus ID (primary key)
- `canonical_name` — Standardized campus name
- `company_clean` — Best available company name
- `full_capacity_mw` + `full_capacity_source`
- `commissioned_mw` + `commissioned_source`
- `source_count` — Number of sources with data
- `source_details_json` — JSON for popup drill-down
- `confidence_score` — Overall data quality (0-1)

---

*Created: January 6, 2026*
