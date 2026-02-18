# Feature Backlog: Web Dashboard UI Improvements

**Status:** 📋 Backlog
**Priority:** Medium
**Created:** 2026-01-20
**Requested By:** P. Anderson

---

## Overview

UI/UX improvements for the MapLibre-based web dashboard to provide cleaner visuals and more actionable insights. These changes focus on making the dashboard more useful for hyperscaler-focused analysis.

---

## Improvement 1: Default Map Filter to Major Hyperscalers

**Current State:**
Map loads showing all 33,000+ features, which is visually overwhelming and cluttered.

**Proposed Change:**
- Default the `company_clean_filter` to show only major hyperscalers on initial load:
  - AWS
  - Microsoft
  - Google
  - Meta
  - Apple
  - Oracle
  - Alibaba
- Exclude "Colo - All Other" and "Unknown" by default
- User can toggle "Show All" to include all records

**Benefits:**
- Cleaner initial visual
- Focuses on the most strategically important data
- Faster initial render (fewer features to display)

**Implementation:**
```typescript
// App.tsx - Update initial filter state
const [filters, setFilters] = useState({
  company_clean_filter: ['AWS', 'Microsoft', 'Google', 'Meta', 'Apple', 'Oracle', 'Alibaba'],
  // ... other filters
});
```

**Files to Modify:**
- [ ] `web_dashboard/frontend/src/App.tsx` - Initial filter state
- [ ] `web_dashboard/frontend/src/components/FilterPanel.tsx` - Default checkbox selections
- [ ] Consider adding "Hyperscalers Only" / "Show All" quick toggle

**Effort:** Low (1-2 hours)

---

## Improvement 2: Stacked Bar Chart - Capacity by Company by Status

**Current State:**
Capacity by company bar chart shows total capacity as a single bar per company.

**Proposed Change:**
Convert to stacked bar chart showing capacity breakdown by facility status:
- **Commissioned/Active** - Green
- **Under Construction** - Amber/Orange
- **Planned/Announced** - Blue

**Mockup:**
```
AWS          [████████████████|████████|██████████████]  45 GW
Microsoft    [██████████████|██████████|████████████████]  42 GW
Google       [████████████████████|██████|████████████]  38 GW
Meta         [██████████████████████|████|████████]  32 GW
Apple        [██████████|██|████]  8 GW
             └─ Commissioned ──┘ UC └── Planned ──┘

Legend: ■ Commissioned  ■ Under Construction  ■ Planned/Announced
```

**Data Requirements:**
- Aggregate capacity by `company_clean_filter` AND `facility_status`
- Sum `commissioned_power_mw`, `uc_power_mw`, `planned_power_mw`

**Implementation:**
```typescript
// ChartsPanel.tsx - Use Recharts StackedBarChart
<BarChart data={capacityByCompanyStatus}>
  <Bar dataKey="commissioned" stackId="capacity" fill="#22c55e" name="Commissioned" />
  <Bar dataKey="under_construction" stackId="capacity" fill="#f59e0b" name="Under Construction" />
  <Bar dataKey="planned" stackId="capacity" fill="#3b82f6" name="Planned" />
</BarChart>
```

**Files to Modify:**
- [ ] `web_dashboard/frontend/src/components/ChartsPanel.tsx` - Replace bar chart
- [ ] `web_dashboard/backend/main.py` - Add aggregation endpoint if needed
- [ ] May need new data processing logic

**Effort:** Medium (3-4 hours)

---

## Improvement 3: Records by Source - Clean Up Overlapping Sources

**Current State:**
Records by source chart shows combinations of sources (e.g., "DCH; SemiAnalysis") when records have multiple sources, creating visual clutter.

**Proposed Change:**
- Show only primary/main sources as distinct categories:
  - DataCenterHawk
  - SemiAnalysis
  - DataCenterMap
  - NewProjectMedia
  - Meta Canonical
  - Synergy
- Do NOT show concatenated combinations (e.g., "DCH; SemiAnalysis; DCM")
- Option A: Use only the FIRST source in multi-source records
- Option B: Count each source separately (record counted multiple times)

**Mockup (Option A - First Source):**
```
DataCenterMap      ████████████████████████  8,453
DataCenterHawk     ██████████████████████    7,052
SemiAnalysis       ██████████████████        5,537
NewProjectMedia    ████                      1,567
Meta Canonical     █                           318
```

**Implementation:**
```python
# Option A: Extract first source
source = record.get('source', '').split(';')[0].strip()

# Option B: Split and count each
sources = record.get('source', '').split(';')
for s in sources:
    source_counts[s.strip()] += 1
```

**Files to Modify:**
- [ ] `web_dashboard/frontend/src/components/ChartsPanel.tsx` - Source chart logic
- [ ] Or handle in backend aggregation

**Effort:** Low (1-2 hours)

---

## Improvement 4: Capacity Forecast by Company (SemiAnalysis Data)

**Current State:**
Capacity forecast chart (mw_2023-2032) shows aggregate totals across all companies as a single trend line.

**Proposed Change:**
- Break down forecast by major hyperscaler
- Show stacked area chart or multi-line chart
- Color-coded by company:
  - AWS - Orange
  - Microsoft - Blue
  - Google - Green/Teal
  - Meta - Blue (different shade)
  - Apple - Gray
  - Other - Light gray

**Mockup (Stacked Area Chart):**
```
MW
│    ╭──────────── AWS (Orange)
│   ╱╲────────────── Microsoft (Blue)
│  ╱  ╲───────────────── Google (Green)
│ ╱    ╲──────────────────── Meta (Blue)
│╱      ╲───────────────────── Other (Gray)
└────────────────────────────────────────
 2023  2024  2025  2026  2027  2028  2029  2030  2031  2032
```

**Or Multi-Line Chart:**
```
MW
│     ╭─────────────────○ AWS
│   ╭─┼───────────────○ Microsoft
│  ╭┼─┼─────────────○ Google
│ ╭┼┼─┼───────────○ Meta
│╭┼┼┼─┼─────────○ Apple
└────────────────────────────────────────
 2023  2024  2025  2026  ...  2032
```

**Data Requirements:**
- Filter to records with `mw_2023-2032` fields (primarily SemiAnalysis data)
- Aggregate by `company_clean_filter` + year
- Sum MW values for each company per year

**Implementation:**
```typescript
// ChartsPanel.tsx - Multi-line or stacked area
<AreaChart data={forecastByCompany}>
  <Area type="monotone" dataKey="AWS" stackId="1" fill="#f97316" />
  <Area type="monotone" dataKey="Microsoft" stackId="1" fill="#3b82f6" />
  <Area type="monotone" dataKey="Google" stackId="1" fill="#14b8a6" />
  <Area type="monotone" dataKey="Meta" stackId="1" fill="#6366f1" />
  <Area type="monotone" dataKey="Other" stackId="1" fill="#9ca3af" />
</AreaChart>
```

**Files to Modify:**
- [ ] `web_dashboard/frontend/src/components/ChartsPanel.tsx` - New forecast chart
- [ ] `web_dashboard/backend/main.py` - Forecast aggregation by company endpoint
- [ ] May need to compute this from combined.geojson at load time

**Effort:** Medium-High (4-6 hours)

---

## Implementation Priority

| # | Improvement | Effort | Impact | Priority |
|---|-------------|--------|--------|----------|
| 1 | Default to Hyperscalers | Low | High | 🔴 High |
| 3 | Clean Source Chart | Low | Medium | 🟡 Medium |
| 2 | Stacked Capacity Bar | Medium | High | 🟡 Medium |
| 4 | Forecast by Company | Medium-High | High | 🟡 Medium |

**Suggested Order:** 1 → 3 → 2 → 4

---

## Color Palette Reference (Company Colors)

| Company | Primary Color | Hex |
|---------|---------------|-----|
| AWS | Orange | `#f97316` |
| Microsoft | Blue | `#3b82f6` |
| Google | Teal | `#14b8a6` |
| Meta | Indigo | `#6366f1` |
| Apple | Gray | `#6b7280` |
| Oracle | Red | `#ef4444` |
| Alibaba | Orange-Red | `#ea580c` |
| Other/Colo | Light Gray | `#9ca3af` |

---

## Status Colors Reference

| Status | Color | Hex |
|--------|-------|-----|
| Active/Commissioned | Green | `#22c55e` |
| Under Construction | Amber | `#f59e0b` |
| Planned/Announced | Blue | `#3b82f6` |
| Unknown | Gray | `#9ca3af` |

---

## Notes

- All changes should respect current filter selections
- Charts should update reactively when filters change
- Consider adding chart export functionality (PNG/CSV) in future
- Mobile responsiveness should be maintained

---

---

## Improvement 5: Supplemental GIS Layers (From Old XB)

**Current State:**
Dashboard only shows data center points from `combined.geojson`.

**Proposed Change:**
Add supplemental layers from the original Experience Builder:

### 5a. Large Parcel Layer

| Item | Details |
|------|---------|
| Data Type | Polygon layer |
| Purpose | Show land parcels for site analysis |
| Source | County/state parcel data |
| Complexity | **Medium** |

**Implementation:**
- Export parcel polygons to GeoJSON (may need tiling for large datasets)
- Add as separate MapLibre layer with toggle
- Style with transparent fill, visible on zoom

**Considerations:**
- File size may be large (consider vector tiles via `tippecanoe`)
- May need simplification for web performance

### 5b. OSM Infrastructure Layers

| Item | Details |
|------|---------|
| Data Type | Points/Lines (substations, transmission lines, etc.) |
| Purpose | Show power grid infrastructure |
| Source | OpenStreetMap exports |
| Complexity | **Low-Medium** |

**Implementation Options:**
1. **Static GeoJSON** - Export relevant OSM features, load as layer
2. **Vector Tiles** - Use existing OSM tile services (e.g., `mapbox://`, `maptiler`)
3. **Overpass API** - Query OSM dynamically (not recommended for large areas)

**Recommended Approach:**
```typescript
// MapContainer.tsx - Add OSM infrastructure layer
map.addSource('power-lines', {
  type: 'vector',
  url: 'mapbox://mapbox.mapbox-streets-v8'  // or custom tileset
});

map.addLayer({
  id: 'transmission-lines',
  type: 'line',
  source: 'power-lines',
  'source-layer': 'power',
  paint: {
    'line-color': '#ff6600',
    'line-width': 2
  }
});
```

### 5c. Network Infrastructure

| Item | Details |
|------|---------|
| Data Type | Points/Lines (fiber routes, POPs, IXPs) |
| Purpose | Show connectivity infrastructure |
| Source | Internal/licensed network data |
| Complexity | **Low** (if data available) |

**Implementation:**
- Export to GeoJSON
- Add as toggleable layer
- Style by infrastructure type (fiber, IXP, etc.)

### 5d. Market Signals Heatmap

| Item | Details |
|------|---------|
| Data Type | Points with intensity values |
| Purpose | Visualize market demand/activity hotspots |
| Source | Geocoded market signals database |
| Complexity | **Medium** |

**Implementation:**
```typescript
// MapContainer.tsx - Add heatmap layer
map.addSource('market-signals', {
  type: 'geojson',
  data: '/data/market_signals.geojson'
});

map.addLayer({
  id: 'market-heatmap',
  type: 'heatmap',
  source: 'market-signals',
  paint: {
    'heatmap-weight': ['get', 'signal_intensity'],
    'heatmap-intensity': 1,
    'heatmap-radius': 30,
    'heatmap-color': [
      'interpolate', ['linear'], ['heatmap-density'],
      0, 'rgba(0,0,255,0)',
      0.2, 'rgb(0,255,255)',
      0.4, 'rgb(0,255,0)',
      0.6, 'rgb(255,255,0)',
      0.8, 'rgb(255,128,0)',
      1, 'rgb(255,0,0)'
    ]
  }
});
```

**Data Requirements:**
- Points with lat/lon and intensity value
- Export from market signals database

---

### Layer Toggle UI

Add layer visibility controls to the dashboard:

```typescript
// LayerToggle.tsx component
const layers = [
  { id: 'parcels', label: 'Parcels', default: false },
  { id: 'power-lines', label: 'Power Infrastructure', default: false },
  { id: 'fiber-routes', label: 'Fiber Routes', default: false },
  { id: 'market-heatmap', label: 'Market Signals', default: false },
];

// Toggle visibility
map.setLayoutProperty(layerId, 'visibility', visible ? 'visible' : 'none');
```

---

### Complexity Summary - Supplemental Layers

| Layer | Complexity | Effort | Notes |
|-------|------------|--------|-------|
| Parcel Layer | Medium | 4-6 hrs | May need vector tiling for performance |
| OSM Infrastructure | Low-Medium | 2-4 hrs | Can use existing tile services |
| Network Infrastructure | Low | 2-3 hrs | Depends on data availability |
| Market Signals Heatmap | Medium | 3-4 hrs | Need to geocode/export data |
| Layer Toggle UI | Low | 1-2 hrs | Simple visibility controls |

**Total Estimate:** 12-19 hours for all layers

---

### Data Export Requirements

Each layer needs a GeoJSON export script:

```
scripts/
├── 08_web_export/
│   ├── export_to_geojson.py          # Existing - DC data
│   ├── export_parcels.py             # NEW - Parcel polygons
│   ├── export_osm_infrastructure.py  # NEW - Power/transmission
│   ├── export_network_infra.py       # NEW - Fiber/IXP
│   └── export_market_signals.py      # NEW - Heatmap data
```

**Output files:**
```
web_dashboard/data/
├── combined.geojson        # Existing
├── parcels.geojson         # NEW (or vector tiles)
├── power_infrastructure.geojson
├── network_infrastructure.geojson
└── market_signals.geojson
```

---

## Related Files

- `web_dashboard/frontend/src/App.tsx` - Main app state
- `web_dashboard/frontend/src/components/ChartsPanel.tsx` - Chart components
- `web_dashboard/frontend/src/components/FilterPanel.tsx` - Filter controls
- `web_dashboard/frontend/src/components/MapContainer.tsx` - Map component
- `web_dashboard/backend/main.py` - FastAPI endpoints
