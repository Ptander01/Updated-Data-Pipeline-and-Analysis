# 🔗 Universal Campus ID (UCID) Design Document

**Created:** December 18, 2025
**Last Updated:** February 11, 2026
**Status:** ✅ Implemented (TIGHT 250m selected)
**Version:** 2.0

---

## 📚 Related Documents

| Document | Purpose |
|----------|---------|
| [UCID_VISUAL_SUMMARY.md](../schemas/UCID_VISUAL_SUMMARY.md) | Visual diagrams and confidence analysis |
| [MATCH_CONFIDENCE_ANALYSIS.md](MATCH_CONFIDENCE_ANALYSIS.md) | Match validation strategies |
| [SA_DCH_METHODOLOGY_RECOMMENDATIONS.md](SA_DCH_METHODOLOGY_RECOMMENDATIONS.md) | Comparison methodology |

---

## 🎯 Purpose

Create a **source-agnostic universal identifier** for data center campuses that enables:
1. Cross-source comparison ("What does DCH vs Semianalysis report for campus X?")
2. Rumor/signal intake matching ("New rumor about Site Y" → instantly links to UCID)
3. Historical tracking across vendor data updates
4. Ground truth benchmarking against Meta Canonical

---

## 📊 The Problem

Currently, the same physical campus can appear multiple times in `gold_campus_full` with different source-specific `campus_id` values:

| Physical Campus | Source | Current campus_id |
|-----------------|--------|-------------------|
| AWS Ashburn | DCH | `aws\|ashburn\|awsashburn` |
| AWS Ashburn | Semianalysis | `amazonwebservices\|ashburn\|awsiad` |
| AWS Ashburn | DCM | `amazon\|ashburn\|amazonashburnva` |

**Result:** No way to link these 3 records as the same campus.

---

## 🏗️ Solution Architecture

### New Feature Class: `campus_master`

A canonical registry where each unique physical campus location gets ONE record with a UCID.

| Field | Type | Description |
|-------|------|-------------|
| `ucid` | TEXT(20) | Universal Campus ID (e.g., `UCID-AMER-00142`) |
| `canonical_name` | TEXT(100) | Standardized campus name |
| `company_canonical` | TEXT(50) | Standardized company name |
| `city` | TEXT(50) | City |
| `state_abbr` | TEXT(10) | State abbreviation |
| `country` | TEXT(50) | Country |
| `region` | TEXT(10) | AMER/EMEA/APAC |
| `latitude` | DOUBLE | Representative latitude |
| `longitude` | DOUBLE | Representative longitude |
| `source_count` | SHORT | Number of sources reporting this campus |
| `sources` | TEXT(200) | Semicolon-separated list of sources |
| `meta_canonical_match` | TEXT(1) | Y/N - matches Meta Canonical? |
| `match_tolerance_m` | SHORT | Tolerance used for matching (250 or 1000) |
| `cluster_method` | TEXT(20) | TIGHT or LOOSE |
| `created_date` | DATE | Date UCID was created |
| `last_updated` | DATE | Last update date |
| `notes` | TEXT(500) | Manual notes/overrides |

### UCID Format

```
UCID-{REGION}-{SEQUENCE}
```

Examples:
- `UCID-AMER-00001` — First campus in Americas
- `UCID-EMEA-00142` — 142nd campus in EMEA
- `UCID-APAC-00033` — 33rd campus in APAC

### Fields Added to Existing Feature Classes

| Feature Class | New Field | Description |
|---------------|-----------|-------------|
| `gold_campus_full` | `ucid` | Links to campus_master |
| `gold_buildings_full` | `ucid` | Inherited from campus assignment |

---

## 🔬 Matching Algorithm

### Distance Calculation: Haversine vs Euclidean

The UCID system uses **Haversine distance** for all spatial calculations, which is critical for accurate global matching.

#### Why Not Euclidean (Planar) Distance?

Euclidean distance treats coordinates as flat X/Y points, which fails for lat/lon:

```
Problem: 1° of longitude varies by latitude!
├── At Equator:  1° longitude ≈ 111 km
├── At 45°N:     1° longitude ≈ 78 km
├── At 60°N:     1° longitude ≈ 55 km
└── At 89°N:     1° longitude ≈ 2 km

Result: A "500m buffer" in Euclidean lat/lon would be:
├── Huge ellipse at equator
└── Tiny circle near poles
```

#### Haversine Distance (What We Use)

Calculates great-circle distance on a sphere, returning **actual meters**:

```python
def haversine_distance(lat1, lon1, lat2, lon2):
    """
    Calculate great-circle distance between two points in meters.
    Used in generate_text_ucid.py and compare_sa_vs_dch_v2.py
    """
    R = 6371000  # Earth's radius in meters

    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)

    a = math.sin(delta_lat/2)**2 + \
        math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

    return R * c  # Distance in meters
```

#### Visual Comparison

```
        EUCLIDEAN (Planar)              HAVERSINE (Spherical)

        ┌─────────────┐                        ___
        │             │                     .-'   '-.
        │  A────────B │                   .'    ⌢    '.
        │  straight   │                  /    A───B    \
        │  line       │                 |   great-circle|
        └─────────────┘                  \              /
                                          '.          .'
        Distance: √(Δx²+Δy²)                 '-.___..-'
        ❌ Wrong for lat/lon!
                                       Distance: 2R·arcsin(√a)
                                       ✅ Accounts for curvature
```

#### Accuracy at Different Scales

| Distance | Haversine Error* | Impact on Matching |
|----------|------------------|-------------------|
| 100 m | < 0.1 m | Negligible |
| 500 m | < 1.5 m | Negligible |
| 1 km | ~ 3 m | Negligible |
| 10 km | ~ 30 m | Negligible |
| 100 km | ~ 500 m | Minor (0.5%) |

*Error vs geodesic (ellipsoid) calculation. Haversine assumes perfect sphere.

**For UCID matching (250m - 1000m thresholds), Haversine error is <3 meters — completely acceptable.**

### Two-Tolerance Approach

We test two spatial tolerances to determine which performs better:

| Tolerance | Distance | Use Case |
|-----------|----------|----------|
| **TIGHT** | 250 meters | Dense urban areas, neighboring campuses |
| **LOOSE** | 1000 meters | Sprawling rural campuses, multi-building sites |

### Matching Steps

1. **Company Normalization**
   - Standardize company names (AWS = Amazon = Amazon Web Services)
   - Use `company_clean` field as primary match key

2. **Spatial Clustering**
   - Group campus centroids within tolerance distance
   - Same `company_clean` + within tolerance = candidate match

3. **Name Similarity (Tiebreaker)**
   - For ambiguous cases, use campus_name fuzzy matching
   - Levenshtein distance < 0.3 = likely same campus

4. **UCID Assignment**
   - Each unique cluster gets a new UCID
   - Sequence number auto-increments per region

### Validation Question

> "Are there more sprawling campuses that are difficult to capture (LOOSE wins),
> or more clustered neighboring campuses that are difficult to distinguish (TIGHT wins)?"

---

## 📁 Scripts

| Script | Purpose |
|--------|---------|
| `06_ucid/create_campus_master.py` | Creates empty campus_master FC |
| `06_ucid/generate_ucid_tight.py` | Generates UCIDs with 250m tolerance |
| `06_ucid/generate_ucid_loose.py` | Generates UCIDs with 1000m tolerance |
| `06_ucid/validate_ucid_comparison.py` | Compares TIGHT vs LOOSE results |
| `06_ucid/assign_ucid_to_gold.py` | Assigns final UCIDs to gold tables |
| `06_ucid/ucid_intake_matcher.py` | Matches new rumors/signals to UCIDs |

---

## 📈 Expected Outcomes

### Metrics to Compare

| Metric | TIGHT (250m) | LOOSE (1000m) |
|--------|--------------|---------------|
| Total unique UCIDs | Higher | Lower |
| Multi-source matches | Lower | Higher |
| False merges | Lower | Higher |
| Orphan splits | Higher | Lower |
| Meta Canonical match rate | ? | ? |

### Success Criteria

1. **Meta Canonical campuses**: Each should have exactly 1 UCID
2. **Major hyperscaler sites**: Known mega-campuses should merge correctly
3. **Urban clusters**: Distinct campuses in same city should stay separate

---

## 🔄 Workflow

### Initial Generation

```python
# 1. Create campus_master feature class
exec(open(r"...\scripts\06_ucid\create_campus_master.py").read())

# 2. Generate UCIDs with both tolerances
exec(open(r"...\scripts\06_ucid\generate_ucid_tight.py").read())
exec(open(r"...\scripts\06_ucid\generate_ucid_loose.py").read())

# 3. Compare and validate
exec(open(r"...\scripts\06_ucid\validate_ucid_comparison.py").read())

# 4. After choosing winner, assign to gold tables
exec(open(r"...\scripts\06_ucid\assign_ucid_to_gold.py").read())
```

### Rumor/Signal Intake

```python
# Match incoming rumor to existing UCID
from ucid_intake_matcher import find_ucid_match

match = find_ucid_match(
    company="Microsoft",
    city="San Antonio",
    lat=29.4241,
    lon=-98.4936
)
# Returns: {'ucid': 'UCID-AMER-00088', 'confidence': 0.92, 'canonical_name': 'Microsoft San Antonio'}
```

---

## 📝 Configuration

Added to `_utils/config.py`:

```python
# UCID Feature Classes
CAMPUS_MASTER = os.path.join(GDB, "campus_master")
CAMPUS_MASTER_TIGHT = os.path.join(GDB, "campus_master_tight")
CAMPUS_MASTER_LOOSE = os.path.join(GDB, "campus_master_loose")

# UCID Tolerances (meters)
UCID_TOLERANCE_TIGHT = 250
UCID_TOLERANCE_LOOSE = 1000
```

---

*Last Updated: December 18, 2024*
