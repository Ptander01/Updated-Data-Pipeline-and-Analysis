# 🔗 UCID (Universal Campus ID) Module

This folder contains scripts for generating and managing Universal Campus IDs — a source-agnostic identifier system that links campus records across all vendor data sources.

## 📋 Purpose

The UCID system solves a critical data integration problem:

**Before UCID:** The same physical campus (e.g., "AWS Ashburn") appears multiple times in `gold_campus_full` with different source-specific IDs. No way to link them.

**After UCID:** Every unique physical campus gets ONE UCID (e.g., `UCID-AMER-00142`). All source records reference this ID, enabling:
- Cross-source comparison
- Rumor/signal intake matching
- Historical tracking
- Ground truth benchmarking

## 🚀 Quick Start

### Step 1: Generate UCID Clusters (Both Tolerances)

```python
# In ArcGIS Pro Python window
exec(open(r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\scripts\06_ucid\generate_ucid_clusters.py", encoding='utf-8').read())
```

This creates:
- `campus_master_tight` — 250m clustering tolerance
- `campus_master_loose` — 1000m clustering tolerance

### Step 2: Validate and Compare

```python
exec(open(r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\scripts\06_ucid\validate_ucid_comparison.py", encoding='utf-8').read())
```

This analyzes:
- Potential false merges in LOOSE
- Potential orphan splits in TIGHT
- Meta Canonical matching accuracy
- Exports comparison CSVs

### Step 3: Choose Tolerance and Assign UCIDs

Edit `assign_ucid_to_gold.py` and set your choice:
```python
CHOSEN_METHOD = 'TIGHT'  # or 'LOOSE'
```

Then run:
```python
exec(open(r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\scripts\06_ucid\assign_ucid_to_gold.py", encoding='utf-8').read())
```

This:
- Creates final `campus_master` feature class
- Adds `ucid` field to `gold_campus_full` and `gold_buildings_full`
- Assigns UCIDs to all records

## 📁 Scripts

| Script | Purpose |
|--------|---------|
| `generate_ucid_clusters.py` | Main clustering script - tests both tolerances |
| `validate_ucid_comparison.py` | Compares TIGHT vs LOOSE, finds edge cases |
| `assign_ucid_to_gold.py` | Applies chosen method to production tables |
| `ucid_intake_matcher.py` | Utility to match new rumors/signals to UCIDs |

## 🔧 Configuration

All UCID configuration is in `_utils/config.py`:

```python
# Feature Classes
CAMPUS_MASTER = "...\Default.gdb\campus_master"
CAMPUS_MASTER_TIGHT = "...\Default.gdb\campus_master_tight"
CAMPUS_MASTER_LOOSE = "...\Default.gdb\campus_master_loose"

# Tolerances
UCID_TOLERANCE_TIGHT = 250   # meters
UCID_TOLERANCE_LOOSE = 1000  # meters
```

## 📊 UCID Format

```
UCID-{REGION}-{SEQUENCE}
```

Examples:
- `UCID-AMER-00001` — First campus in Americas
- `UCID-EMEA-00142` — 142nd campus in EMEA
- `UCID-APAC-00033` — 33rd campus in APAC

## 🔬 Matching Algorithm

1. **Company Normalization** — Standardize names (AWS = Amazon Web Services)
2. **Spatial Clustering** — Group campuses within tolerance distance
3. **Same company + within tolerance = same UCID**

### Tolerance Comparison

| Method | Distance | Best For |
|--------|----------|----------|
| **TIGHT** | 250m | Dense urban areas, neighboring campuses |
| **LOOSE** | 1000m | Sprawling rural campuses, multi-building sites |

## 🔍 Using the Intake Matcher

For matching new rumors/signals to existing UCIDs:

```python
from ucid_intake_matcher import match_rumor_to_ucid, find_nearby_campuses, search_by_name

# Match by location
result = match_rumor_to_ucid(
    company="Microsoft",
    city="San Antonio",
    lat=29.4241,
    lon=-98.4936
)
# Returns: {'ucid': 'UCID-AMER-00088', 'confidence': 0.92, ...}

# Find nearby campuses
nearby = find_nearby_campuses(39.0438, -77.4874, radius_m=5000, company="AWS")

# Search by name
results = search_by_name("Altoona", company="Meta")
```

## 📖 Documentation

See `00_docs/UCID_DESIGN.md` for full design documentation including:
- Schema details
- Matching algorithm
- Validation metrics
- Expected outcomes

## ⚠️ Important Notes

1. **Run in order**: Generate → Validate → Assign
2. **Choose carefully**: TIGHT vs LOOSE affects data linkage quality
3. **Re-run after data updates**: UCIDs should be regenerated when gold tables are refreshed
4. **Cache management**: Call `clear_cache()` in intake matcher after updating campus_master

---

*Created: December 18, 2024*
