# Report Output Standard Operating Procedure (SOP)

> **Last Updated:** January 14, 2026
> **Author:** Meta Data Center GIS Team

---

## Overview

This document defines the standard operating procedure for generating and distributing reports from the Data Center Consensus GIS Pipeline. All reports are automatically synced to Google Drive for team access.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  SOURCE CODE (Local)                      OUTPUT (Google Drive - Auto-Sync) │
│  ─────────────────────                    ─────────────────────────────────  │
│                                                                             │
│  C:\Users\ptanderson\Documents\           G:\My Drive\Consensus GIS Model   │
│  ArcGIS\Projects\Lean Consensus           Cleaned Inputs\Admin Documentation│
│  DC Model\scripts\                        │                                  │
│  ├── 00_docs\                             ├── _archive\                     │
│  ├── 01_ingestion\                        │   └── YYYY-MM-DD\               │
│  ├── 02_processing\         ───────►      ├── context\                      │
│  ├── 03_ucid\               (writes)      │   └── AI_CONTEXT_PROMPT.md      │
│  ├── 04_validation\                       ├── dashboards\                   │
│  ├── 05_accuracy\                         │   └── PROJECT_OVERVIEW.html     │
│  ├── _utils\                              │
│  │   └── config.py  ◄── OUTPUT PATHS      ├── pipeline_diagnostics\         │
│  └── run_full_pipeline.py                 │   └── PIPELINE_DIAGNOSTIC_*.html│
│                                           ├── progress_updates\              │
│                                           │   └── PROGRESS_UPDATE_*.html    │
│                                           ├── schemas\                       │
│                                           │   └── SCHEMA_*.md/.html         │
│                                           ├── visualizations\                │
│                                           │   └── FOLDER_STRUCTURE_*.html   │
│                                           └── workflows\                     │
│                                               └── PIPELINE_*.md             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Configuration

All output paths are defined in `_utils/config.py`:

```python
from pathlib import Path

# Root output directory on Google Drive (auto-syncs to cloud)
OUTPUT_ROOT = Path("G:/My Drive/Consensus GIS Model Cleaned Inputs/Admin Documentation")

# Report output directories (directly under Admin Documentation)
DASHBOARDS_DIR = OUTPUT_ROOT / "dashboards"
PIPELINE_REPORTS_DIR = OUTPUT_ROOT / "pipeline_diagnostics"
ACCURACY_REPORTS_DIR = OUTPUT_ROOT / "accuracy_reports"
PROGRESS_UPDATES_DIR = OUTPUT_ROOT / "progress_updates"
VISUALIZATIONS_DIR = OUTPUT_ROOT / "visualizations"
```

### To Change Output Location

1. Open `scripts/_utils/config.py`
2. Modify `OUTPUT_ROOT` to the new path
3. All scripts importing from config will use the new location

---

## Folder Structure

The Google Drive Admin Documentation folder mirrors the local 00_docs structure:

| Folder | Contents | Update Frequency |
|--------|----------|------------------|
| `_archive/` | Dated backups of previous script versions | As needed |
| `context/` | AI context prompts, project context | After major changes |
| `dashboards/` | Executive dashboards and weekly status | Weekly |
| `pipeline_diagnostics/` | Auto-generated pipeline health reports | Per pipeline run |
| `progress_updates/` | Session progress reports | Per work session |
| `schemas/` | Schema definitions, field documentation | After schema changes |
| `visualizations/` | Folder structure diagrams, visual aids | After reorganization |
| `workflows/` | Pipeline documentation, SOPs, execution guides | After workflow changes |

---

## Report Types

### 1. Dashboards (Manual Updates)
**Location:** `G:\My Drive\...\Admin Documentation\dashboards\`

| File | Description | Update Frequency |
|------|-------------|------------------|
| `PROJECT_OVERVIEW.html` | Executive summary with pipeline workflow, methodology, timeline | Weekly or after major milestones |

**Update Process:**
1. Edit HTML files locally in `scripts\00_docs\reports\dashboards\`
2. Save changes
3. Copy to Google Drive:
   ```powershell
   Copy-Item "scripts\00_docs\reports\dashboards\PROJECT_OVERVIEW.html" "G:\My Drive\Consensus GIS Model Cleaned Inputs\Admin Documentation\dashboards\" -Force
   ```

### 2. Visualizations
**Location:** `G:\My Drive\...\Admin Documentation\visualizations\`

| File | Description | Update Frequency |
|------|-------------|------------------|
| `FOLDER_STRUCTURE_INTERACTIVE.html` | Interactive folder tree with collapsible nodes | After script reorganization |
| `FOLDER_STRUCTURE_DIAGRAM.html` | Static folder structure diagram | After script reorganization |

### 3. Pipeline Diagnostics (Auto-Generated)
**Location:** `G:\My Drive\...\Admin Documentation\pipeline_diagnostics\`

| File Pattern | Description | Generated By |
|--------------|-------------|--------------|
| `PIPELINE_DIAGNOSTIC_YYYYMMDD_HHMM.html` | Full pipeline health report with grades, source analysis, spatial accuracy | `generate_pipeline_report.py` |

**Auto-Generation:**
- Reports are timestamped and don't overwrite previous versions
- Generated at end of `run_full_pipeline.py` if `GENERATE_REPORT = True`
- Can also run standalone:
  ```python
  exec(open(r"scripts\04_validation\reports\generate_pipeline_report.py", encoding='utf-8').read())
  ```

### 4. Progress Updates
**Location:** `G:\My Drive\...\Admin Documentation\progress_updates\`

| File Pattern | Description | Update Frequency |
|--------------|-------------|------------------|
| `WEEKLY_STATUS_DASHBOARD.html` | Sprint-style weekly progress tracking | Weekly |
| `PROGRESS_UPDATE_MMMDD.html` | Session progress reports | Per work session |

### 5. Accuracy Reports (Future)
**Location:** `G:\My Drive\...\Admin Documentation\accuracy_reports\`

Reserved for future accuracy analysis reports.

---

## Sharing with Team

### Initial Setup (One-Time)
1. Navigate to `G:\My Drive\Consensus GIS Model Cleaned Inputs\Admin Documentation`
2. Right-click the `Admin Documentation` folder
3. Select **Share** → **Get link**
4. Set permissions to "Anyone at Meta with the link can view"
5. Distribute link to team

### Team Access
- Team members open the shared link in Chrome
- HTML files render directly in browser
- Latest version is always available (no downloads needed)
- No file attachments or email distribution required

---

## Workflow Summary

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  Run Pipeline   │ ─► │ Generate Report │ ─► │ Auto-Sync to    │
│  or Edit HTML   │    │ (writes to G:\) │    │ Google Drive    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                                      │
                                                      ▼
                                              ┌─────────────────┐
                                              │ Team Views via  │
                                              │ Shared Link     │
                                              └─────────────────┘
```

---

## Benefits

| Before | After |
|--------|-------|
| Reports stored locally | Reports auto-sync to cloud |
| Email attachments for each update | Single shared link, always current |
| Version confusion | Timestamped reports preserve history |
| Manual distribution | Zero-effort distribution |
| Flat folder structure | Organized by category (mirrors 00_docs) |

---

## Troubleshooting

### Google Drive Not Syncing
1. Check Google Drive icon in system tray
2. Ensure you're signed in
3. Right-click → Preferences → check sync status

### Reports Not Generating
1. Verify `GENERATE_REPORT = True` in `run_full_pipeline.py`
2. Check that `G:\My Drive\` is accessible
3. Run `generate_pipeline_report.py` standalone to see errors

### Team Can't Access
1. Verify folder sharing settings (link sharing enabled)
2. Confirm they're using a Meta account
3. Try generating a new sharing link

---

## Archive Location

Previous script backups are stored in:
```
G:\My Drive\Consensus GIS Model Cleaned Inputs\Admin Documentation\_archive\YYYY-MM-DD\
```

---

## Related Documentation

- `PIPELINE_DOCUMENTATION.md` - Full pipeline workflow
- `PIPELINE_EXECUTION_ORDER.md` - Script execution sequence
- `AI_CONTEXT_PROMPT.md` - AI assistant context
