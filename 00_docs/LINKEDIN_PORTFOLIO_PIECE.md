# 🏗️ Portfolio Piece: Building a Production-Grade Geospatial Data Pipeline — From Zero Coding Experience

*A LinkedIn Portfolio Summary by Patrick Anderson*

---

## The Hook

In November 2025, I had never written a line of code. By February 2026 — across **50+ development sessions** and hundreds of hours — I had built a **production-ready geospatial data engineering pipeline** that ingests, harmonizes, validates, and visualizes data center infrastructure data from **9 independent industry sources** into a unified analytical layer of **34,000+ records** spanning three continents.

This is the story of that project — what I built, what I learned, and why it matters.

---

## 📊 By the Numbers

| Metric | Value |
|--------|-------|
| **Total lines of code written** | **233,007** |
| **Python scripts authored** | **192 files** (74,527 lines) |
| **Documentation authored** | **69 Markdown files** (23,406 lines) |
| **Custom HTML reports & dashboards** | **78 files** (148,674 lines) |
| **React/TypeScript frontend components** | **23 files** (5,579 lines) |
| **Total project files** | **657** |
| **Data sources integrated** | **9 vendor + 1 internal ground truth** |
| **Records in final dataset** | **34,000+** (buildings + campuses) |
| **Geographic scope** | **Global** (AMER, EMEA, APAC) |
| **Pipeline stages** | **8 sequential automated steps** |
| **Validation & QA scripts** | **41** |
| **Accuracy analysis scripts** | **21** |
| **Development sessions** | **50+** (Nov 2025 – Feb 2026) |
| **AI context document versions** | **56 iterations** (living documentation) |
| **Early ChatGPT browser sessions** | **~17** (first month of learning) |

---

## 🎯 The Problem

The data center industry is booming, but **no single data provider has the full picture**. Each vendor has different coverage, different schemas, different coordinate systems, different definitions of "capacity," and different levels of accuracy. Our team needed a way to:

1. **Ingest** data from multiple competing industry sources (each with its own format, quirks, and gaps)
2. **Harmonize** them into a single, standardized schema
3. **Deduplicate** records across sources using spatial proximity clustering
4. **Validate** accuracy against a known ground-truth dataset
5. **Score** each source on reliability, coverage, and precision
6. **Visualize** everything in an interactive, filterable geospatial dashboard
7. **Repeat** all of the above on demand — not a one-off analysis, but a **repeatable pipeline**

---

## 🏗️ What I Built

### 1. Multi-Source Ingestion Engine (9 scripts)

I wrote **9 dedicated ingestion scripts**, each tailored to a specific vendor's data format and quirks. Every script:
- Auto-deletes existing records before inserting (idempotent / safe to re-run)
- Handles coordinate system transformations
- Normalizes field names and units (e.g., kW → MW conversions, PUE adjustments)
- Maps source-specific schemas to a unified "gold" schema
- Generates unique, source-prefixed IDs (e.g., `DCH_12345`, `SA_uuid`, `dcm_1001`)

Data sources ranged from **~640 records** (internal ground truth) to **~8,450 records** (largest external vendor), with geocoding coverage ranging from 0% to 100%.

### 2. Universal Campus ID (UCID) System

One of the most novel components: a **spatial proximity clustering algorithm** that assigns a human-readable campus-level identifier across all data sources:

- **Format:** `{country}-{state}-{city}-{nnn}` (e.g., `US-VA-Ashburn-001`)
- **Clustering threshold:** 500 meters
- **Source-agnostic:** The same UCID links a record from Vendor A to a record from Vendor B if they're within 500m of each other
- **Enables cross-source deduplication and campus-level aggregation** without requiring vendors to use the same ID system

This is the backbone of the entire consensus model — it's what allows us to say "these 5 records from 3 different vendors are actually the same campus."

### 3. Processing & Transformation Layer (12 scripts)

After ingestion, records flow through:
- **Geography enrichment** — region, state, and country normalization from raw coordinates
- **Company name standardization** — hundreds of raw company names collapsed into a clean taxonomy with tier groupings (Hyperscalers vs. Colocation vs. All Other)
- **Campus rollup** — individual buildings aggregated to campus-level summaries with capacity sums, source overlap tracking, and building counts
- **Essential site flagging** — curated strategic sites matched by exact unique ID
- **Combined XB layer creation** — a unified union of buildings + campuses optimized for dashboard consumption

### 4. Validation & Quality Assurance Framework (41 scripts)

This is where data engineering becomes data science. I built **41 validation scripts** organized into:

- **Core validators** — schema integrity, coordinate independence, granularity checks, data torture tests
- **Diagnostic investigators** — company name audits, duplicate detection, data vintage tracking, schema comparison
- **Data quality fixes** — automated standardization of company names, regions, status values
- **Automated reporting** — pipeline diagnostic HTML reports with quality scoring

### 5. Accuracy Analysis Suite (21 scripts)

To answer the question *"Which vendor is most accurate?"*, I built a comprehensive statistical analysis framework:

- **MAPE (Mean Absolute Percentage Error)** with grade assignment (A–F scale)
- **Bias analysis** — systematic over/under-reporting detection
- **Coefficient of Variation** — variance in disagreements
- **Pearson correlation** — strength of linear relationship
- **Bootstrap 95% confidence intervals** for all metrics
- **Tier-weighted composite scoring** — prioritizing hyperscaler accuracy (60% weight)
- **Spatial accuracy analysis** — distance-based matching between source coordinates and ground truth
- **Net New Sites analysis** — identifying exclusive pipeline coverage per source

### 6. Automated Pipeline Diagnostic Report (5,809 lines)

One of my proudest deliverables: a **fully automated HTML diagnostic report** that generates after every pipeline run. It features:

- **Glassmorphism/liquid-glass UI design** — a polished, modern aesthetic
- **6-category weighted quality scoring** — Core Identity, Capacity Data, Location Quality, Spatial Accuracy, Strategic Intel, Infrastructure
- **Per-source scorecards** with letter grades
- **Interactive Chart.js visualizations** — scatter plots, histograms, company distribution charts
- **Hover tooltips** explaining what each metric means
- **Natural language interpretation boxes** that translate statistical results into plain English
- **Excel workbook exports** with styled multi-tab output

This report became one of the most valued deliverables of the project — it turned a complex multi-source comparison into something a non-technical stakeholder could immediately understand.

### 7. Custom Web Dashboard (React + MapLibre + FastAPI)

When the out-of-the-box ESRI Experience Builder hit its limits with 34K+ data points, I built a **custom web dashboard from scratch**:

- **Frontend:** React + TypeScript + Vite + Tailwind CSS
- **Map engine:** MapLibre GL JS (open-source, no API key, handles 34K+ points)
- **Backend:** FastAPI with caching, filtering, and export endpoints
- **Features:**
  - Zoom-based layer visibility (campuses at all zooms, buildings at 14+)
  - Company-branded color coding (AWS orange, Microsoft green, Google red, etc.)
  - Arc/pie status indicators showing development progress
  - Slide-in feature popup with executive summary, drill-down sections, and 10-year capacity trend charts
  - Multi-dimensional filtering (company, source, status, region, state, tier, capacity range, hyperscaler toggle)
  - CSV and GeoJSON export
- **Deployed** to an internal shared server for team access

### 8. Project Management & Documentation

Over **69 Markdown documents** (23,406 lines) covering:
- **Field mappings** for every source → gold schema transformation
- **Workflow SOPs** for pipeline execution, report generation, and data refresh
- **Schema design documents** with capacity field definitions and UCID architecture
- **Session logs** tracking 33 development sessions
- **10 HTML progress update reports** with timeline visualizations
- **A living AI context document** (updated 56 times) that served as the project's single source of truth

---

## 🛠️ Technology Stack

| Category | Technologies |
|----------|-------------|
| **Languages** | Python, TypeScript, HTML/CSS, PowerShell, SQL |
| **GIS Platform** | ArcGIS Pro, arcpy, ESRI Geodatabases |
| **Web Frontend** | React, TypeScript, Vite, Tailwind CSS, MapLibre GL JS |
| **Web Backend** | FastAPI (Python) |
| **Visualization** | Chart.js, custom HTML report templates |
| **Data Formats** | GeoJSON, CSV, Excel, JSON, Feature Classes |
| **Data Warehousing** | Hive, Presto, DaiQuery (SQL) |
| **Statistics** | MAPE, Pearson r, Bootstrap CI, Bias analysis, CV |
| **DevOps** | PowerShell automation, Google Drive sync, network deployment |
| **IDE** | VS Code with AI-assisted development (Copilot/Claude) |

---

## 📈 What Makes This Special

### It's Not a One-Off Analysis — It's Infrastructure

Every script is **idempotent** (safe to re-run). The entire pipeline can be refreshed end-to-end with a single command. When new vendor data arrives, the process is: drop in the new data, run the pipeline, generate a fresh diagnostic report. **What used to take days of manual work now runs in minutes.**

### The Scale is Significant

- **34,000+ records** from 9+ sources, across 3 continents
- **10-year capacity forecasts** (2023–2032) for thousands of facilities
- **~130 data center markets** geocoded with centroid coordinates
- **Global coverage** spanning the US, Europe, Asia-Pacific, and Latin America

### The Statistical Rigor is Real

This isn't just "put dots on a map." The accuracy analysis uses **MAPE, bias detection, coefficient of variation, Pearson correlation, and bootstrap confidence intervals** to quantitatively grade each vendor source. The weighted composite scoring system prioritizes what matters most to the business — hyperscaler accuracy gets 60% weight.

### I Built It With Zero Prior Coding Experience

In November 2025, I had never opened VS Code. I had never written a Python script. I had never built a web application. By February 2026:

- **192 Python scripts** (74,527 lines)
- **50+ development sessions** (including ~17 early ChatGPT sessions before migrating to VS Code)
- A full-stack **React + FastAPI web dashboard**
- Automated **HTML report generation** with custom CSS themes
- **PowerShell automation** for deployment and sync
- A **living documentation system** with 56 versioned updates

I learned Python, arcpy, React, TypeScript, FastAPI, MapLibre, Chart.js, SQL, PowerShell, and version-controlled documentation practices — all in the context of solving a real business problem.

---

## 🔑 Key Lessons Learned

1. **Documentation is a force multiplier.** The 56 versions of my AI context document became the project's memory. Any collaborator (human or AI) could pick up exactly where the last session left off.

2. **Idempotent pipelines save your sanity.** Making every script safe to re-run (auto-delete before insert) meant I could iterate fearlessly. Break something? Just re-run the pipeline.

3. **Validation is not optional — it IS the product.** The diagnostic report became more valuable than the raw data. Stakeholders didn't just want answers — they wanted *confidence in the answers*.

4. **Start with the ugly version.** My first scripts were messy. But they worked. Then I refactored. Then I refactored again. The archive folder (65 superseded scripts) is proof of iteration.

5. **AI-assisted development is a legitimate accelerator.** Using AI tools (Copilot, Claude) didn't write the code for me — but it dramatically compressed the learning curve. I could ask "how do I do X in arcpy?" and immediately apply the answer to my specific problem.

---

## 🏆 Impact

- **Automated what was previously manual** — multi-day vendor comparison processes reduced to a single pipeline run
- **Quantified vendor accuracy** for the first time — providing data-driven evidence for vendor evaluation decisions
- **Created a repeatable framework** that outlives any single analyst — the pipeline is documented, modular, and maintained
- **Replaced a limited out-of-the-box tool** (ESRI Experience Builder) with a custom dashboard that handles 34K+ records with filtering, export, and interactive visualization
- **Established data quality standards** — weighted scoring rubric with letter grades that make quality conversations concrete

---

## 🔗 Tags

`#DataEngineering` `#GIS` `#Python` `#GeospatialAnalysis` `#DataPipeline` `#React` `#MapLibre` `#ArcGIS` `#DataScience` `#ETL` `#DataVisualization` `#CareerGrowth` `#LearnToCode` `#SelfTaught` `#DataQuality` `#Infrastructure`

---

*Built November 2025 – February 2026. 50+ sessions. 233,007 lines of code. Zero prior coding experience.*
