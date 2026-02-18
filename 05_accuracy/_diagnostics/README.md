# Diagnostic Scripts — Accuracy Analysis

This folder contains investigation and debugging scripts used during the development of the accuracy analysis pipeline. These scripts are **valuable for ongoing QA** when loading new data.

---

## 📋 Script Reference

### Capacity Analysis Diagnostics

| Script | Purpose | When to Use |
|--------|---------|-------------|
| `audit_capacity_by_source.py` | Audit capacity data availability by source | **Run after loading new data** to verify capacity field coverage |
| `check_woodmac_npm_source.py` | Check source FCs for capacity fields | Debug missing capacity data in WoodMac/NPM extracts |

### DCH (DataCenterHawk) Investigation

| Script | Purpose | When to Use |
|--------|---------|-------------|
| `analyze_dch_source.py` | Analyze DCH source field structure | When loading new DCH extracts |
| `investigate_dch_granularity.py` | Determine if DCH is building vs campus level | Validate granularity assumptions |
| `investigate_dch_granularity_v2.py` | Enhanced granularity investigation | Alternative approach (may consolidate) |
| `test_dch_pue_adjustment.py` | Test PUE factor impact on accuracy | Re-validate if DCH methodology changes |
| `dch_building_level_accuracy.py` | DCH building-level accuracy deep dive | Detailed DCH accuracy analysis |

### Cross-Source Comparison

| Script | Purpose | When to Use |
|--------|---------|-------------|
| `compare_semi_vs_dch_campus.py` | Compare Semianalysis vs DCH at campus level | Validate cross-source consistency |

---

## 🔄 Recommended Workflow for New Data

When loading new data extracts (~25k records), run these scripts in order:

```bash
# 1. Check capacity data availability
python audit_capacity_by_source.py

# 2. If capacity issues found, investigate source
python check_woodmac_npm_source.py

# 3. Validate DCH granularity (if DCH data changed)
python investigate_dch_granularity.py

# 4. Verify PUE assumptions still valid
python test_dch_pue_adjustment.py
```

---

## 📊 Key Findings from Lean Model (Dec 2024)

These scripts helped establish:

1. **DCH is Building-level** (not Campus) — `record_level` field corrected
2. **No PUE adjustment needed** for DCH — both SA and DCH report IT capacity
3. **Only SA and DCH have usable capacity data** — NPM/WoodMac/DCM too sparse
4. **Semianalysis `mw_2023` is best** — 11.9% MAPE vs 14.7% for mw_2024

---

## 📁 Related Validation Scripts

See also `04_validation/` for coordinate and data quality validation:
- `validate_coordinate_independence.py` — Check coordinate sharing between sources
- `compare_raw_source_coordinates.py` — Compare raw source FC coordinates
- `validate_gold_buildings_data.py` — Core gold data validation

---

*Last Updated: December 11, 2024*
