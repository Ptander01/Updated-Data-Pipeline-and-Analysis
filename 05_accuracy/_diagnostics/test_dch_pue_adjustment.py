"""
DCH PUE Adjustment Test
Determine if DCH reports IT capacity or Facility power

Author: Data Center GIS Team
Date: December 11, 2024
"""

import arcpy
import numpy as np

GDB = r"C:\Users\ptanderson\Documents\ArcGIS\Projects\Lean Consensus DC Model\Default.gdb"


def main():
    print("=" * 70)
    print("DCH PUE ADJUSTMENT TEST")
    print("Does DCH report IT capacity or Facility power?")
    print("=" * 70)
    print()

    # Get Meta buildings
    meta = {}
    with arcpy.da.SearchCursor(
        GDB + "/meta_canonical_buildings",
        ["building_key", "it_load_total", "new_build_status"]
    ) as cursor:
        for bkey, it_load, status in cursor:
            if it_load and it_load > 0:
                meta[bkey] = {"it_load": it_load, "status": status}

    # Get DCH matches (closest per building)
    dch = {}
    with arcpy.da.SearchCursor(
        GDB + "/accuracy_analysis_multi_source_REBUILT",
        ["building_key", "commissioned_power_mw", "distance_m"],
        "source = 'DataCenterHawk'"
    ) as cursor:
        for bkey, cap, dist in cursor:
            d = dist if dist else 999999
            if bkey not in dch or d < dch[bkey]["dist"]:
                dch[bkey] = {"cap": cap or 0, "dist": d}

    # Test different PUE factors
    print("Testing PUE adjustment factors for Complete Builds:")
    print("-" * 60)
    print(f"{'PUE Factor':<15} {'MAPE':>10} {'Bias':>10} {'n':>6}")
    print("-" * 45)

    best_pue = 1.0
    best_mape = 999

    results = []

    for pue in [1.0, 1.1, 1.2, 1.3, 1.4, 1.5]:
        errors = []
        biases = []

        for bkey, data in dch.items():
            if bkey in meta and meta[bkey]["status"] == "Complete Build":
                meta_it = meta[bkey]["it_load"]
                dch_adjusted = data["cap"] / pue

                if meta_it > 0 and dch_adjusted > 0:
                    error = abs(dch_adjusted - meta_it) / meta_it
                    bias = (dch_adjusted - meta_it) / meta_it
                    errors.append(error)
                    biases.append(bias)

        if errors:
            mape = np.mean(errors) * 100
            avg_bias = np.mean(biases) * 100

            results.append({"pue": pue, "mape": mape, "bias": avg_bias, "n": len(errors)})

            if mape < best_mape:
                best_mape = mape
                best_pue = pue

            marker = " <-- best MAPE" if mape == best_mape else ""
            if abs(avg_bias) < 5:
                marker = " <-- near-zero bias"

            print(f"{pue:<15.1f} {mape:>9.1f}% {avg_bias:>+9.1f}% {len(errors):>6}{marker}")

    print()
    print("=" * 70)
    print("INTERPRETATION")
    print("=" * 70)

    # Find zero-bias PUE
    zero_bias_pue = None
    for r in results:
        if abs(r["bias"]) < 3:  # Within 3% of zero
            zero_bias_pue = r["pue"]
            break

    if best_pue == 1.0:
        print("PUE=1.0 gives best MAPE → DCH reports IT CAPACITY (same as Meta)")
        print("NO PUE adjustment needed!")
    elif best_pue >= 1.2:
        print(f"PUE={best_pue} gives best MAPE → DCH reports FACILITY POWER")
        print(f"Divide by {best_pue} to convert to IT capacity")

    if zero_bias_pue:
        print(f"\nPUE={zero_bias_pue} gives near-zero bias (most balanced)")

    print()
    print("Sample comparisons (Complete Builds, no adjustment):")
    print("-" * 60)

    comparisons = []
    for bkey, data in dch.items():
        if bkey in meta and meta[bkey]["status"] == "Complete Build":
            meta_it = meta[bkey]["it_load"]
            dch_cap = data["cap"]
            if meta_it > 0 and dch_cap > 0:
                ratio = dch_cap / meta_it
                comparisons.append({
                    "bkey": bkey,
                    "meta": meta_it,
                    "dch": dch_cap,
                    "ratio": ratio
                })

    # Sort by Meta IT load
    comparisons.sort(key=lambda x: -x["meta"])

    print(f"{'Building':<15} {'Meta IT':>10} {'DCH Cap':>10} {'Ratio':>8}")
    print("-" * 45)
    for c in comparisons[:15]:
        print(f"{c['bkey'][:15]:<15} {c['meta']:>10.1f} {c['dch']:>10.1f} {c['ratio']:>8.2f}")

    # Calculate average ratio
    avg_ratio = np.mean([c["ratio"] for c in comparisons])
    print()
    print(f"Average DCH/Meta ratio: {avg_ratio:.2f}")
    print(f"This suggests DCH reports approximately {avg_ratio:.1f}x Meta's IT load")

    if avg_ratio < 1.1:
        print("→ DCH likely reports IT CAPACITY (no adjustment needed)")
    elif avg_ratio > 1.1:
        print(f"→ DCH likely reports FACILITY POWER (use PUE = {avg_ratio:.1f})")


if __name__ == "__main__":
    main()
