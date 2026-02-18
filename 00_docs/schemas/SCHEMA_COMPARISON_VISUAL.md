# 📊 Schema Comparison — Visual Guide

**For Supervisor Review**
**Created:** December 29, 2024

---

## 🔍 4 Schema Sources Compared

```mermaid
flowchart LR
    subgraph CURRENT["✅ CURRENT PRODUCTION"]
        GB["🏢 Gold Buildings<br/>32 fields"]
        GC["🏘️ Gold Campus<br/>25 fields"]
    end

    subgraph REFERENCE["📝 REFERENCE SCHEMAS"]
        IF["📋 Intake Form<br/>27 fields"]
        AH["💭 Ad-hoc Brainstorm<br/>19 fields"]
    end

    GB --> MERGE["🎯 PROPOSED<br/>CONSENSUS v2.0<br/>48 fields"]
    GC --> MERGE
    IF --> MERGE
    AH --> MERGE
```

---

## 📋 Field Coverage by Category

```mermaid
pie title Field Coverage Across All 4 Schemas
    "Location (11)" : 11
    "Capacity - Power (12)" : 12
    "Capacity - Space (3)" : 3
    "Identity/Names (5)" : 5
    "Ownership (5)" : 5
    "Energy/Infra (4)" : 4
    "AI/GPU (2)" : 2
    "Provenance (6)" : 6
```

---

## ✅ What Each Schema Does Well

```mermaid
flowchart TB
    subgraph GOLD["🏆 Gold Buildings (Production)"]
        G1["✅ Capacity breakdown<br/>commissioned/UC/planned"]
        G2["✅ Year forecasts<br/>mw_2023-2032"]
        G3["✅ Full location parsing<br/>city/state/county/region"]
        G4["✅ Source tracking"]
    end

    subgraph INTAKE["📋 Intake Form (Google)"]
        I1["🔥 IT vs Facility Power<br/>separation"]
        I2["🔥 GPU Type & Count<br/>AI tracking"]
        I3["🔥 Energy fields<br/>utility/fuel/strategy"]
        I4["🔥 Confidence Score"]
    end

    subgraph ADHOC["💭 Ad-hoc Brainstorm"]
        A1["🔥 Developer/Tenant/User<br/>ownership split"]
        A2["🆕 Building ID<br/>within campus"]
        A3["🆕 Phase ID<br/>expansion tracking"]
        A4["🆕 Alternate names"]
    end
```

---

## 🔥 HIGH PRIORITY: Fields to Add

```mermaid
flowchart LR
    subgraph POWER["⚡ POWER TRACKING"]
        P1["it_power_mw<br/>Server/IT load"]
        P2["facility_power_mw<br/>Total site power"]
    end

    subgraph OWNERSHIP["🏢 OWNERSHIP"]
        O1["developer<br/>Who's building it"]
        O2["tenant<br/>Lease tenant"]
        O3["end_user<br/>Actual occupant"]
    end

    subgraph AI["🤖 AI/GPU"]
        AI1["gpu_type<br/>H100, B200, etc."]
        AI2["gpu_count<br/>Scale metric"]
    end

    subgraph ENERGY["🔌 ENERGY"]
        E1["utility_company<br/>Power provider"]
        E2["fuel_type<br/>Grid/solar/gas"]
    end

    subgraph QUALITY["📊 DATA QUALITY"]
        Q1["confidence_score<br/>1-5 reliability"]
    end

    POWER --> ADD["🎯 ADD TO<br/>GOLD SCHEMA"]
    OWNERSHIP --> ADD
    AI --> ADD
    ENERGY --> ADD
    QUALITY --> ADD
```

---

## 🆕 MEDIUM PRIORITY: Nice to Have

```mermaid
flowchart LR
    subgraph NAMES["📛 NAMING"]
        N1["building_name"]
        N2["project_name"]
        N3["campus_name_alt"]
    end

    subgraph IDS["🔑 IDENTIFIERS"]
        ID1["building_id"]
        ID2["phase_id"]
    end

    subgraph OTHER["📝 OTHER"]
        OT1["building_type"]
        OT2["power_strategy"]
        OT3["notes"]
    end

    NAMES --> CONSIDER["🤔 CONSIDER<br/>ADDING"]
    IDS --> CONSIDER
    OTHER --> CONSIDER
```

---

## 🏗️ Proposed Schema v2.0 Structure

```mermaid
flowchart TB
    subgraph BUILDING["🏢 gold_buildings_v2 (48 fields)"]
        direction TB

        subgraph ID["🔑 IDENTIFIERS"]
            id1["unique_id"]
            id2["source"]
            id3["building_id 🆕"]
            id4["campus_id"]
            id5["phase_id 🆕"]
        end

        subgraph NAME["📛 NAMING"]
            n1["building_name 🆕"]
            n2["campus_name"]
            n3["campus_name_alt 🆕"]
            n4["project_name 🆕"]
            n5["company_clean"]
        end

        subgraph OWN["🏢 OWNERSHIP 🆕"]
            o1["developer 🔥"]
            o2["tenant 🔥"]
            o3["end_user 🔥"]
            o4["owned_leased"]
        end

        subgraph LOC["📍 LOCATION"]
            l1["address, city, state..."]
            l2["lat/lon"]
        end

        subgraph CAP["⚡ CAPACITY"]
            c1["it_power_mw 🔥"]
            c2["facility_power_mw 🔥"]
            c3["commissioned_power_mw"]
            c4["uc_power_mw"]
            c5["planned_power_mw"]
            c6["mw_2023-2032"]
        end

        subgraph INFRA["🔌 INFRASTRUCTURE 🆕"]
            i1["utility_company 🔥"]
            i2["fuel_type 🔥"]
            i3["power_strategy"]
        end

        subgraph GPU["🤖 AI/GPU 🆕"]
            g1["gpu_type 🔥"]
            g2["gpu_count 🔥"]
        end

        subgraph PROV["📊 PROVENANCE"]
            p1["confidence_score 🔥"]
            p2["source, dates"]
        end
    end
```

---

## 🔄 Ownership Model Explained

```mermaid
flowchart LR
    subgraph EXAMPLE["Example: Meta in Vantage Facility"]
        DEV["🏗️ Developer<br/>Vantage Data Centers"]
        TEN["📋 Tenant<br/>Meta Platforms"]
        USE["👤 End User<br/>Meta AI Team"]
    end

    DEV -->|"builds"| BUILDING["🏢 Data Center"]
    TEN -->|"leases"| BUILDING
    USE -->|"occupies"| BUILDING

    subgraph CURRENT["❌ Current Schema"]
        CURR["company_clean = ???<br/>Who do we put?"]
    end

    subgraph NEW["✅ New Schema"]
        NEW1["developer = Vantage"]
        NEW2["tenant = Meta"]
        NEW3["end_user = Meta AI"]
    end
```

---

## ⚡ IT Power vs Facility Power

```mermaid
flowchart TB
    subgraph FACILITY["🏢 FACILITY (Total Site Power)"]
        IT["🖥️ IT POWER<br/>Servers, Storage, Network<br/>= What Meta cares about"]
        COOL["❄️ Cooling<br/>~30% of total"]
        OTHER["💡 Lighting, UPS, etc.<br/>~10% of total"]
    end

    IT --> PUE["PUE = Facility / IT<br/>Typically 1.2-1.4"]
    COOL --> PUE
    OTHER --> PUE

    subgraph PROBLEM["❌ Current Problem"]
        P1["Vendors report different things!"]
        P2["DCH Hyper = Facility Power"]
        P3["Semianalysis = IT Power"]
        P4["Can't compare directly"]
    end

    subgraph SOLUTION["✅ Solution: Track Both"]
        S1["it_power_mw = IT load"]
        S2["facility_power_mw = Total"]
        S3["Now we can calculate PUE"]
    end
```

---

## ❓ Questions for Supervisor

```mermaid
flowchart TB
    Q1["🤖 1. GPU Tracking<br/>Priority for current phase?"]
    Q2["🏢 2. Developer/Tenant/User<br/>Critical for use case?"]
    Q3["🔌 3. Energy Fields<br/>Now or future phase?"]
    Q4["📊 4. Confidence Scoring<br/>Who assigns? What scale?"]
    Q5["📈 5. Phase Tracking<br/>How granular?"]

    Q1 --> DECIDE["📋 DECIDE<br/>PRIORITIES"]
    Q2 --> DECIDE
    Q3 --> DECIDE
    Q4 --> DECIDE
    Q5 --> DECIDE

    DECIDE --> NEXT["🚀 NEXT STEPS"]

    NEXT --> N1["Create migration script"]
    NEXT --> N2["Update ingestion"]
    NEXT --> N3["Update intake form"]
```

---

## 📊 Field Count Summary

```mermaid
xychart-beta
    title "Field Count by Schema"
    x-axis ["Gold Buildings", "Gold Campus", "Intake Form", "Ad-hoc", "Proposed v2.0"]
    y-axis "Number of Fields" 0 --> 55
    bar [32, 25, 27, 19, 48]
```

---

## 🎯 TL;DR — Key Recommendations

| Priority | Add These Fields | Why |
|----------|------------------|-----|
| 🔥 HIGH | `it_power_mw`, `facility_power_mw` | Enable accurate capacity comparison |
| 🔥 HIGH | `developer`, `tenant`, `end_user` | Track ownership chain |
| 🔥 HIGH | `gpu_type`, `gpu_count` | AI datacenter tracking |
| 🔥 HIGH | `utility_company`, `fuel_type` | Power planning & sustainability |
| 🔥 HIGH | `confidence_score` | Data quality tracking |
| 🆕 MED | `building_name`, `building_id` | Multi-building campus tracking |
| 🆕 MED | `project_name`, `phase_id` | Expansion tracking |

---

*Visual guide created December 29, 2024*
