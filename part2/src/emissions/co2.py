"""co2.py — Estimate CO2 emissions (kg) from energy consumption.

Why this is more than `kwh × factor`
------------------------------------
Two pitfalls when computing emissions on this dataset:

1. The `value_kwh` column for kWh-units of an electricity meter is the
   CUMULATIVE METER INDEX (millions of kWh). Multiplying that by an
   emission factor would give millions of TONS of CO2 per reading — absurd.
   We compute CO2 only on rows that represent CONSUMPTION (a delta), and
   leave index rows alone via the helper `cumulative_to_delta()`.

2. Different energy sources have different carbon intensity:
     - Natural gas (combustion):  ~ 0.202 kg CO2 / kWh
     - Tunisia electricity grid:  ~ 0.468 kg CO2 / kWh
     - Reactive energy (kVARh):   does not produce CO2 directly
   We therefore pick the factor based on `category` + `unit_normalized`,
   not a single global constant.

Public API
----------
- add_co2_emissions(df) : adds `co2_kg` and `co2_factor` columns.
- cumulative_to_delta(df, group_cols): turns meter indices into per-period
  consumption (so CO2 can be computed safely on a real delta).
"""
from __future__ import annotations

from typing import Iterable, Optional

import pandas as pd
from loguru import logger

from src.utils.config import CO2_FACTOR_KG_PER_KWH

# ---------------------------------------------------------------------------
# Emission factors (kg CO2 per kWh)
# Sources:
#   - Tunisia grid 2023 average  (STEG / IEA): 0.468
#   - Natural gas combustion (IPCC 2006, GHG Protocol): 0.202
#   - Reactive energy is not directly emitting CO2 (set to 0).
# ---------------------------------------------------------------------------
EMISSION_FACTORS: dict[str, float] = {
    "grid_electricity":  CO2_FACTOR_KG_PER_KWH,   # 0.468 by default (.env)
    "natural_gas":       0.202,
    "reactive":          0.0,
    "default":           CO2_FACTOR_KG_PER_KWH,
}


# ---------------------------------------------------------------------------
# Source classification
# ---------------------------------------------------------------------------
def _classify_source(row) -> str:
    """Return the emission category for one row.

    Looks at `unit_normalized` first (most reliable), then `category` /
    `measure` text as a fallback.
    """
    unit = str(row.get("unit_normalized", "")).lower()
    category = str(row.get("category", "")).lower()
    measure = str(row.get("measure", "")).lower()

    # 1. Reactive energy
    if unit == "kvarh" or "reactiv" in measure or "réactiv" in measure:
        return "reactive"

    # 2. Natural gas (Nm3, or any measure mentioning gas)
    if unit == "nm3" or "gaz" in category or "gaz" in measure:
        return "natural_gas"

    # 3. Default = electricity from grid
    if unit == "kwh":
        return "grid_electricity"

    return "default"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def add_co2_emissions(
    df: pd.DataFrame,
    factors: Optional[dict[str, float]] = None,
) -> pd.DataFrame:
    """Add `co2_kg` and `co2_factor` columns to df.

    CO2 is computed only for rows where `quantity_type == "energy"`.
    For rows that are not energy (temperature, power, flow, ...) co2_kg is NaN.
    """
    factors = factors or EMISSION_FACTORS

    if df.empty:
        out = df.copy()
        out["co2_factor"] = pd.NA
        out["co2_kg"] = pd.NA
        return out

    out = df.copy()

    # If the upstream pipeline didn't add quantity_type, assume everything
    # with value_kwh is energy.
    if "quantity_type" not in out.columns:
        out["quantity_type"] = out["value_kwh"].notna().map(
            {True: "energy", False: "unknown"}
        )

    # Per-row source classification + factor lookup
    out["co2_source"] = out.apply(_classify_source, axis=1)
    out["co2_factor"] = out["co2_source"].map(factors).fillna(factors["default"])

    # Compute CO2 only where it makes sense
    energy_mask = out["quantity_type"] == "energy"
    out["co2_kg"] = pd.NA
    out.loc[energy_mask, "co2_kg"] = (
        pd.to_numeric(out.loc[energy_mask, "value_kwh"], errors="coerce")
        * out.loc[energy_mask, "co2_factor"]
    )

    n = int(energy_mask.sum())
    breakdown = out.loc[energy_mask, "co2_source"].value_counts().to_dict()
    logger.info(f"CO2 computed on {n:,} energy rows. Source mix: {breakdown}")
    return out


def cumulative_to_delta(
    df: pd.DataFrame,
    group_cols: Iterable[str] = ("source", "measure"),
    value_col: str = "value_kwh",
    sort_col: str = "timestamp",
    delta_col: str = "delta_kwh",
) -> pd.DataFrame:
    """Convert cumulative meter indices to per-period consumption.

    For each (source, measure) group, sort by timestamp and compute the
    diff between consecutive readings. Negative diffs (which can happen
    when meters reset or when readings were swapped) are clipped to 0.

    Adds a `delta_kwh` column. The first reading of each group is NaN
    (no previous index to diff against).

    Example
    -------
    Index reading at 10:00:  100 kWh
    Index reading at 10:10:  102 kWh   -> delta = 2 kWh consumed in 10 min
    """
    if df.empty or value_col not in df.columns:
        out = df.copy()
        out[delta_col] = pd.NA
        return out

    out = df.copy().sort_values(list(group_cols) + [sort_col])
    out[delta_col] = (
        out.groupby(list(group_cols))[value_col].diff().clip(lower=0)
    )
    n_deltas = int(out[delta_col].notna().sum())
    logger.info(f"Computed {n_deltas:,} per-period deltas (cumulative -> delta)")
    return out


# ---------------------------------------------------------------------------
# CLI helper
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    test = pd.DataFrame([
        {"source": "f.xlsx", "timestamp": "2025-01-01 10:00",
         "category": "Consommation gaz", "measure": "Gaz", "unit": "Nm3",
         "unit_normalized": "nm3", "value": 100, "value_kwh": 1056.2,
         "quantity_type": "energy"},
        {"source": "f.xlsx", "timestamp": "2025-01-01 10:00",
         "category": "Energie Moteur", "measure": "Energie active", "unit": "kWh",
         "unit_normalized": "kwh", "value": 5000, "value_kwh": 5000,
         "quantity_type": "energy"},
        {"source": "f.xlsx", "timestamp": "2025-01-01 10:00",
         "category": "Temperature", "measure": "T entrée", "unit": "°C",
         "unit_normalized": "°c", "value": 25, "value_kwh": None,
         "quantity_type": "temperature"},
    ])
    out = add_co2_emissions(test)
    print(out[["measure", "value_kwh", "co2_source", "co2_factor", "co2_kg"]].to_string())