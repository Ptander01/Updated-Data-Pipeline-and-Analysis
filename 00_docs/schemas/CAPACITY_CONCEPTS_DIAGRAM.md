# Data Center Capacity Concepts

## Overview

Data center capacity can be measured in multiple ways, each serving different analytical purposes.

---

## 1. Time-Based Capacity (Development Stage)

```mermaid
flowchart LR
    subgraph Timeline["📅 Development Timeline"]
        direction LR
        P["🔮 Planned<br/><i>planned_power_mw</i>"]
        UC["🏗️ Under Construction<br/><i>uc_power_mw</i>"]
        C["✅ Commissioned<br/><i>commissioned_power_mw</i>"]

        P --> UC --> C
    end

    subgraph Total["📊 Total Capacity"]
        F["🎯 Full Capacity<br/><i>full_capacity_mw</i><br/><br/>= Commissioned + UC + Planned"]
    end

    P & UC & C --> F

    style P fill:#e1bee7,stroke:#7b1fa2,color:#4a148c
    style UC fill:#fff9c4,stroke:#f9a825,color:#5d4037
    style C fill:#c8e6c9,stroke:#388e3c,color:#1b5e20
    style F fill:#bbdefb,stroke:#1976d2,color:#0d47a1
```

| Field | Status | Example | Use Case |
|-------|--------|---------|----------|
| `planned_power_mw` | Announced, permits filed | 50 MW | Future pipeline |
| `uc_power_mw` | Actively building | 30 MW | Construction tracking |
| `commissioned_power_mw` | Operational today | 100 MW | Current state analysis |
| `full_capacity_mw` | Total potential | 180 MW | **Investment analysis** ⭐ |

---

## 2. Power Type (What's Being Measured)

> **Note:** The `it_power_mw` and `facility_power_mw` fields have been **removed from the schema**.
> The data already exists in `commissioned_power_mw` - use the `source` field to interpret:
> - **Semianalysis, DCH Lease, DCH Hyper** → All report IT Power (directly comparable to Meta)
>
> **December 2024 Finding:** Testing confirmed DCH reports IT capacity, NOT facility power. No PUE adjustment needed.
> See `CAPACITY_FIELD_DEFINITIONS.md` for detailed source-specific guidance.

```mermaid
flowchart TB
    subgraph Facility["🏢 Total Facility Power"]
        FP["Facility Power<br/><i>DCH Hyper reports this</i>"]
    end

    subgraph Components["Power Components"]
        IT["💻 IT Power<br/><i>Semianalysis & DCH Lease report this</i><br/>Servers, storage, network"]
        COOL["❄️ Cooling<br/><i>~30-40% of IT</i>"]
        INFRA["⚡ Infrastructure<br/><i>UPS, lighting, etc.</i>"]
    end

    IT --> FP
    COOL --> FP
    INFRA --> FP

    subgraph PUE["📐 PUE Relationship"]
        FORMULA["PUE = Facility Power ÷ IT Power<br/><br/>Typical: 1.2 - 1.5<br/>Efficient: < 1.2"]
    end

    FP -.-> FORMULA
    IT -.-> FORMULA

    style IT fill:#c8e6c9,stroke:#388e3c,color:#1b5e20
    style FP fill:#bbdefb,stroke:#1976d2,color:#0d47a1
    style COOL fill:#e1f5fe,stroke:#0288d1,color:#01579b
    style INFRA fill:#fff8e1,stroke:#ffa000,color:#5d4037
    style FORMULA fill:#fff3e0,stroke:#ef6c00,color:#e65100
```

| Source | Reports | How to Interpret `commissioned_power_mw` |
|--------|---------|------------------------------------------|
| Semianalysis | IT Capacity | Use directly - comparable to Meta |
| DCH Lease | IT Capacity | Use directly - comparable to Meta |
| DCH Hyper | IT Capacity | Use directly - comparable to Meta (Dec 2024 validated) |
| NPM | Design Capacity | Full buildout only - not status-split |

---

## 3. Source Data Variations

```mermaid
flowchart TB
    subgraph Sources["📊 Data Sources Report Different Things"]
        SA["Semianalysis<br/>Reports: IT Capacity"]
        DCH_L["DCH Lease<br/>Reports: IT Capacity"]
        DCH_H["DCH Hyperscale<br/>Reports: IT Capacity<br/><i>(Dec 2024 validated)</i>"]
        NPM["NPM<br/>Reports: Design Capacity"]
    end

    subgraph Normalization["🔄 Direct Comparison"]
        IT_NORM["All DCH & SA sources<br/>directly comparable to Meta"]
    end

    SA --> IT_NORM
    DCH_L --> IT_NORM
    DCH_H --> IT_NORM
    NPM -->|"Needs context"| IT_NORM

    style SA fill:#c8e6c9,stroke:#388e3c,color:#1b5e20
    style DCH_L fill:#c8e6c9,stroke:#388e3c,color:#1b5e20
    style DCH_H fill:#c8e6c9,stroke:#388e3c,color:#1b5e20
    style NPM fill:#ffcdd2,stroke:#c62828,color:#b71c1c
    style IT_NORM fill:#e8f5e9,stroke:#43a047,color:#1b5e20
```

---

## 4. Recommended Default Field

```mermaid
flowchart TD
    Q["Which capacity field<br/>should I use?"]

    Q --> A1{"What's your<br/>question?"}

    A1 -->|"Total site potential"| R1["🎯 full_capacity_mw<br/><b>RECOMMENDED DEFAULT</b>"]
    A1 -->|"What's live now"| R2["✅ commissioned_power_mw"]
    A1 -->|"Growth pipeline"| R3["🏗️ uc_power_mw +<br/>planned_power_mw"]
    A1 -->|"Technical analysis"| R4["💻 it_power_mw"]
    A1 -->|"Utility planning"| R5["⚡ facility_power_mw"]

    style R1 fill:#bbdefb,stroke:#1976d2,stroke-width:3px,color:#0d47a1
    style R2 fill:#c8e6c9,stroke:#388e3c,color:#1b5e20
    style R3 fill:#fff9c4,stroke:#f9a825,color:#5d4037
    style R4 fill:#e8f5e9,stroke:#43a047,color:#1b5e20
    style R5 fill:#e3f2fd,stroke:#1e88e5,color:#0d47a1
    style Q fill:#f5f5f5,stroke:#424242,color:#212121
    style A1 fill:#fafafa,stroke:#616161,color:#212121
```

---

## 5. Complete Field Hierarchy

```mermaid
flowchart TB
    subgraph Primary["⭐ Primary (Default for XB)"]
        FULL["full_capacity_mw"]
    end

    subgraph Timeline["📅 By Development Stage"]
        COMM["commissioned_power_mw"]
        UC["uc_power_mw"]
        PLAN["planned_power_mw"]
    end

    subgraph Type["💡 By Power Type"]
        IT["it_power_mw"]
        FAC["facility_power_mw"]
    end

    COMM --> FULL
    UC --> FULL
    PLAN --> FULL

    IT -.->|"× PUE"| FAC

    style FULL fill:#bbdefb,stroke:#1976d2,stroke-width:3px,color:#0d47a1
    style COMM fill:#c8e6c9,stroke:#388e3c,color:#1b5e20
    style UC fill:#fff9c4,stroke:#f9a825,color:#5d4037
    style PLAN fill:#e1bee7,stroke:#7b1fa2,color:#4a148c
    style IT fill:#e8f5e9,stroke:#43a047,color:#1b5e20
    style FAC fill:#e3f2fd,stroke:#1e88e5,color:#0d47a1
```

---

## Summary Table

| Field | Category | Default? | Best For |
|-------|----------|----------|----------|
| **`full_capacity_mw`** | Timeline | ⭐ **YES** | Investment, comparison, total potential |
| `commissioned_power_mw` | Timeline | Alternate | Current operations, live capacity |
| `uc_power_mw` | Timeline | No | Construction pipeline |
| `planned_power_mw` | Timeline | No | Future growth analysis |

> **Note:** `it_power_mw` and `facility_power_mw` were **removed** from the schema.
> Use the `source` field + `CAPACITY_FIELD_DEFINITIONS.md` to interpret power type.

---

## ⚠️ Coverage Considerations

**Important:** The "best" default field also depends on **data coverage** - how many records actually have values populated.

Run the coverage analysis script to see actual population rates:
```python
exec(open(r"...scripts/04_validation/analyze_capacity_coverage.py", encoding='utf-8').read())
```

### Coverage by Source (from CAPACITY_FIELD_DEFINITIONS.md)

| Source | commissioned | full_capacity | Notes |
|--------|-------------|---------------|-------|
| **Semianalysis** | ✅ 69.6% | ✅ 91.8% | Also has mw_2023-2032; reports IT capacity |
| **DCH Hyper** | ✅ 60.1% | ✅ 94.6% | Reports IT capacity (Dec 2024 validated) |
| **DCH Lease** | ✅ 60.1% | ✅ 94.6% | Reports IT capacity |
| **DCM** | ⚠️ 28.5% | ⚠️ 32.5% | No hyperscaler capacity |
| **NPM** | ❌ 0% | ✅ 52.8% | Only populates full_capacity |

### Recommendation

```mermaid
flowchart TD
    Q["Choosing Default Capacity Field"]

    Q --> C1{"Is coverage<br/>≥50%?"}

    C1 -->|"Yes"| C2{"Is it conceptually<br/>appropriate?"}
    C1 -->|"No"| R1["⚠️ Consider composite field<br/>or different default"]

    C2 -->|"Yes"| R2["✅ Use as default"]
    C2 -->|"No"| R3["🔄 Balance coverage<br/>vs meaning"]

    style Q fill:#f5f5f5,stroke:#424242,color:#212121
    style C1 fill:#fff9c4,stroke:#f9a825,color:#5d4037
    style C2 fill:#fff9c4,stroke:#f9a825,color:#5d4037
    style R1 fill:#ffcdd2,stroke:#c62828,color:#b71c1c
    style R2 fill:#c8e6c9,stroke:#388e3c,color:#1b5e20
    style R3 fill:#bbdefb,stroke:#1976d2,color:#0d47a1
```

---

## Formula Reference

```
full_capacity_mw = commissioned_power_mw + uc_power_mw + planned_power_mw

facility_power_mw = it_power_mw × PUE

PUE (Power Usage Effectiveness) = Total Facility Power ÷ IT Power
   • Industry average: 1.5 - 1.8
   • Good: 1.2 - 1.4
   • Excellent: < 1.2
```

---

*Created: January 2, 2026*
