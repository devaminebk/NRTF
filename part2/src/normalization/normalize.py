"""normalize.py — Convert energy units to kWh and tag every row by quantity type.

Why this is more than a unit-conversion table
---------------------------------------------
The BILAN TOTAL Excel files mix THREE kinds of measurements:

  1. Energy (cumulative, e.g. kWh, kVARh, Nm3 of gas, MJ)
       -> convertible to kWh, additive across time.
  2. Power / Flow (instantaneous rates, e.g. kW, m3/h, Nm3/h)
       -> NOT convertible to kWh without a duration.
  3. Physical measurements (e.g. °C, %, V, A, rpm)
       -> not energy at all; never convert.

Naively mapping every unit to a kWh factor would silently corrupt the
dataset (e.g. multiplying a temperature by 1e-3 makes no physical sense).

Therefore this module:
  * adds `quantity_type` ∈ {energy, power, flow, temperature, electrical,
    speed, ratio, dimensionless, unknown}
  * adds `value_kwh` only for rows where `quantity_type == "energy"`
  * adds `unit_normalized` (canonical unit string) for everything else,
    so downstream code (anomaly detection, dashboard) can still use it.

Special case — natural gas
--------------------------
In cogeneration plants, gas consumption is reported in Nm3. To express it
in kWh we need the PCI (Pouvoir Calorifique Inférieur).
The BILAN TOTAL header (row 7) gives:  PCI = 9.082 thermie/Nm3.
1 thermie = 1.163 kWh, so 1 Nm3 of gas ≈ 9.082 × 1.163 ≈ 10.562 kWh.
This factor is centralized as `GAS_PCI_KWH_PER_NM3` and configurable via .env.
"""
from __future__ import annotations

import os
from typing import Optional

import pandas as pd
from loguru import logger

# ---------------------------------------------------------------------------
# Conversion tables
# ---------------------------------------------------------------------------

# True energy units -> kWh
ENERGY_TO_KWH: dict[str, float] = {
    "kwh":   1.0,
    "wh":    1e-3,
    "mwh":   1e3,
    "gwh":   1e6,
    "kvarh": 1.0,            # kVARh treated like kWh in magnitude (reactive energy)
    "j":     2.7778e-7,
    "kj":    2.7778e-4,
    "mj":    0.27778,
    "gj":    277.78,
    "btu":   2.9307e-4,
    "kbtu":  0.29307,
    "therm": 29.3001,
    "thermie": 1.163,         # 1 thermie = 1.163 kWh
    "kcal":  1.163e-3,
}

# Gas volume -> kWh requires the PCI (calorific value).
# Default from the BILAN TOTAL header: PCI = 9.082 thermie/Nm3 = 10.562 kWh/Nm3.
GAS_PCI_KWH_PER_NM3: float = float(os.getenv("GAS_PCI_KWH_PER_NM3", 10.562))

# Quantity-type classification.
# Every key here is the unit in lowercase, stripped.
UNIT_TO_QUANTITY: dict[str, str] = {
    # Energy (convertible)
    "kwh": "energy", "wh": "energy", "mwh": "energy", "gwh": "energy",
    "kvarh": "energy", "j": "energy", "kj": "energy", "mj": "energy",
    "gj": "energy", "btu": "energy", "kbtu": "energy",
    "therm": "energy", "thermie": "energy", "kcal": "energy",
    "nm3": "energy",          # gas — convertible via PCI
    "m3 (gaz)": "energy",
    # Power & flow (not convertible)
    "kw": "power", "w": "power", "mw": "power",
    "m3/h": "flow", "nm3/h": "flow", "l/h": "flow", "l/s": "flow",
    # Pure physical
    "°c": "temperature", "c": "temperature", "k": "temperature",
    "%": "ratio",
    "v": "electrical", "a": "electrical", "kv": "electrical",
    "rpm": "speed", "hz": "speed",
    "h": "duration",
    "": "dimensionless",
    "nan": "dimensionless",
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def _classify_unit(unit: str) -> str:
    """Return the quantity_type for a given unit string."""
    if unit is None:
        return "unknown"
    u = str(unit).strip().lower()
    return UNIT_TO_QUANTITY.get(u, "unknown")


def _energy_factor(unit: str, gas_pci: float = GAS_PCI_KWH_PER_NM3) -> Optional[float]:
    """Return the multiplicative factor to convert `unit` to kWh, or None if N/A."""
    u = (unit or "").strip().lower()
    if u in ("nm3", "m3 (gaz)"):
        return gas_pci
    return ENERGY_TO_KWH.get(u)


def normalize_to_kwh(
    df: pd.DataFrame,
    gas_pci_kwh_per_nm3: float = GAS_PCI_KWH_PER_NM3,
) -> pd.DataFrame:
    """Add quantity_type, unit_normalized and value_kwh columns to df.

    Schema of the returned DataFrame:
        ... original columns ...
        quantity_type     : energy | power | flow | temperature | ... | unknown
        unit_normalized   : canonical lowercase unit (or original if unknown)
        value_kwh         : float for energy rows, NaN otherwise
    """
    if df.empty:
        logger.warning("Empty DataFrame — nothing to normalize.")
        out = df.copy()
        for col in ("quantity_type", "unit_normalized", "value_kwh"):
            out[col] = pd.Series(dtype="object")
        return out

    if "value" not in df.columns or "unit" not in df.columns:
        logger.warning("Missing 'value' or 'unit' column — skipping normalization.")
        out = df.copy()
        out["quantity_type"] = "unknown"
        out["unit_normalized"] = ""
        out["value_kwh"] = pd.NA
        return out

    out = df.copy()
    out["unit_normalized"] = out["unit"].astype(str).str.strip().str.lower()
    out["quantity_type"] = out["unit_normalized"].map(_classify_unit)

    # Convert only the energy rows
    energy_mask = out["quantity_type"] == "energy"
    factors = out.loc[energy_mask, "unit_normalized"].apply(
        lambda u: _energy_factor(u, gas_pci_kwh_per_nm3)
    )
    out["value_kwh"] = pd.NA
    out.loc[energy_mask, "value_kwh"] = (
        pd.to_numeric(out.loc[energy_mask, "value"], errors="coerce") * factors
    )

    # ---- Logging summary --------------------------------------------------
    summary = out["quantity_type"].value_counts().to_dict()
    n_energy = int(energy_mask.sum())
    n_converted = int(out["value_kwh"].notna().sum())
    n_unknown = int((out["quantity_type"] == "unknown").sum())
    logger.info(f"Quantity-type breakdown: {summary}")
    logger.info(f"Energy rows: {n_energy:,} | converted to kWh: {n_converted:,}")
    if n_unknown:
        unknown_units = (
            out.loc[out["quantity_type"] == "unknown", "unit_normalized"]
            .value_counts()
            .head(5)
            .to_dict()
        )
        logger.warning(f"{n_unknown:,} rows with unknown units. Top 5: {unknown_units}")

    return out


# ---------------------------------------------------------------------------
# CLI helper
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    # Quick self-test
    test = pd.DataFrame([
        {"unit": "kWh",   "value": 100},
        {"unit": "MWh",   "value": 1},
        {"unit": "Nm3",   "value": 50},
        {"unit": "kW",    "value": 200},
        {"unit": "°C",    "value": 25},
        {"unit": "%",     "value": 87},
        {"unit": "blah",  "value": 1},
    ])
    out = normalize_to_kwh(test)
    print(out.to_string())