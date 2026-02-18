# BI Air-Permit Dataset Validation - Quick Start Guide

## Overview

This guide helps you run the BI Air-Permit Dataset Validation Study to evaluate whether Business Insider's air-permit-derived dataset can identify parent companies behind holding companies in our DC pipeline.

## Prerequisites

1. **ArcGIS Pro** with Python environment
2. **gold_buildings** feature class populated with pipeline data
3. **BI Air-Permit Dataset** (CSV file from Business Insider trial access)

## Step 1: Prepare the BI Dataset

### Expected File Location
Place the BI dataset at:
```
C:\Users\ptanderson\Downloads\Pipeline_Ingestion\BI_AirPermit_Dataset.csv
```

### Required Columns (rename as needed)
The script will auto-detect columns, but ideally your BI dataset should have:

| Column Name | Description | Example |
|-------------|-------------|---------|
| `bi_id` or `id` | Unique record identifier | `BI-00001` |
| `permit_holder` or `shell_company` | Company on the permit | `Blue Ridge Properties LLC` |
| `parent_company` or `linked_company` | **KEY VALUE-ADD**: Identified parent | `Microsoft Corporation` |
| `latitude` | Decimal latitude | `38.9072` |
| `longitude` | Decimal longitude | `-77.0369` |
| `state` | State name or abbreviation | `Virginia` |
| `county` | County name | `Loudoun` |
| `permit_id` | Air permit reference | `AQCP-2024-12345` |

### Sample BI Dataset Template

Create a test CSV with this structure:
```csv
bi_id,permit_holder,parent_company,latitude,longitude,state,county,permit_id,capacity_mw
BI-001,Cascade Properties LLC,Microsoft,38.9072,-77.0369,VA,Loudoun,AQCP-001,150
BI-002,Glacier Data Holdings,Amazon Web Services,39.0458,-77.4875,VA,Loudoun,AQCP-002,200
BI-003,Mesa Verde Development,Google,33.4484,-112.0740,AZ,Maricopa,AQCP-003,180
```

## Step 2: Run the Validation Script

### Option A: From ArcGIS Pro Python Window

```python
# Navigate to the script directory
import sys
sys.path.append(r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\scripts\05_accuracy")

# Import and run
from bi_airpermit_validation import main

# Run with default BI path
results = main()

# Or specify custom BI dataset path
results = main(bi_dataset_path=r"C:\path\to\your\bi_dataset.csv")
```

### Option B: From Command Line

```bash
cd "C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\scripts\05_accuracy"
python bi_airpermit_validation.py "C:\path\to\bi_dataset.csv"
```

## Step 3: Review Outputs

All outputs are saved to:
```
G:\My Drive\Consensus GIS Model Cleaned Inputs\Admin Documentation\accuracy_reports\
```

Or local fallback:
```
C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\scripts\00_docs\reports\accuracy_reports\
```

### Output Files

| File | Description |
|------|-------------|
| `bi_validation_sample_selection_*.csv` | The 20 stratified sample sites selected |
| `bi_validation_match_results_*.csv` | Detailed match results for each site |
| `bi_validation_site_analysis_*.md` | Markdown report with site-by-site analysis |
| `bi_validation_executive_summary_*.md` | Executive summary for supervisor review |
| `bi_validation_report_*.html` | Interactive HTML report with charts |

## Step 4: Interpret Results

### Key Metrics to Review

| Metric | Target | Interpretation |
|--------|--------|----------------|
| **Full ID Rate** | ≥25% (5/20) | BI identifies specific hyperscaler |
| **Partial ID Rate** | ≥40% (8/20) | BI links to parent holding company |
| **Coverage Rate** | N/A | What % of sample BI has at all |

### Decision Framework

| Full IDs Found | Recommendation |
|----------------|----------------|
| ≥5 | **Strongly Recommend** full dataset integration |
| 3-4 | **Recommend** targeted use |
| 1-2 | **Consider** for high-value investigations |
| 0 (high coverage) | **Not Useful** for parent ID |
| 0 (low coverage) | **Not Useful** - methodologies don't overlap |

## Troubleshooting

### "No eligible records found"
- Ensure `gold_buildings` has records with `company_source` or `company_clean` populated
- Check that records aren't already identified as hyperscalers

### "BI dataset not found"
- Place the CSV at the expected path
- Check the file encoding (should be UTF-8)

### No matches found
- Verify BI dataset has lat/lon coordinates
- Expand distance thresholds (edit `MATCH_TIERS` in script)
- Check for coordinate system differences

## Customization

### Change Sample Size
Edit `SAMPLE_SIZE` in the script:
```python
SAMPLE_SIZE = 30  # Increase for larger spot-check
```

### Adjust Distance Thresholds
Edit `MATCH_TIERS`:
```python
MATCH_TIERS = {
    'tier_2': {'distance': 500, ...},  # Increase from 250m
    'tier_3': {'distance': 1000, ...}, # Increase from 500m
}
```

### Add Company Aliases
Add to `HYPERSCALER_ALIASES` or `DEVELOPER_ALIASES`:
```python
HYPERSCALER_ALIASES = {
    'openai': ['openai', 'chatgpt'],  # Add new hyperscaler
    ...
}
```

## Contact

For questions about this validation study, contact the Meta Data Center GIS Team.
