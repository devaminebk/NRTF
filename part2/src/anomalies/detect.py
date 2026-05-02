"""detect.py — Detect anomalies in energy data.

Three complementary detectors, applied PER MEASURE (not globally):

  1. Z-score        : flags values > N std deviations from this measure's mean.
                      Fast, interpretable, good for "stuck-at-zero" or "spike".
  2. IsolationForest: ML-based, catches multivariate outliers a Z-score misses.
  3. Rate-of-change : flags impossible jumps in cumulative meter readings
                      (a meter can't lose 100 000 kWh in 10 minutes).

Why per-measure
---------------
A temperature of 80 °C is normal for hot water but anomalous for ambient air.
A power of 1 200 kW is normal for the engine but absurd for a sensor reading
itself in volts. Mixing all measures into one statistical model would either
flood the dashboard with false positives or hide real issues. We therefore
group by `measure` and run each detector inside the group.

Output
------
Adds three boolean columns + one combined flag:
    anomaly_zscore   : bool
    anomaly_iforest  : bool
    anomaly_jump     : bool   (only meaningful for cumulative energy indices)
    is_anomaly       : bool   (logical OR of the three)
    anomaly_reason   : str    (human-readable explanation, empty if not anomaly)
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from loguru import logger

# Lazy import — sklearn is optional. We fall back gracefully if missing.
try:
    from sklearn.ensemble import IsolationForest
    _HAS_SKLEARN = True
except ImportError:
    _HAS_SKLEARN = False
    logger.warning("scikit-learn not installed — IsolationForest detector disabled")


# ---------------------------------------------------------------------------
# Detector parameters (tunable)
# ---------------------------------------------------------------------------
ZSCORE_THRESHOLD = 3.5             # std deviations
IFOREST_CONTAMINATION = 0.02       # expected fraction of outliers
MIN_POINTS_FOR_DETECTION = 20      # below that, we skip — not enough signal
JUMP_FACTOR = 5.0                  # delta_kwh > 5 × median(non-zero deltas) -> flag


# ---------------------------------------------------------------------------
# Per-group detectors
# ---------------------------------------------------------------------------
def _zscore_flags(values: pd.Series, threshold: float = ZSCORE_THRESHOLD) -> pd.Series:
    """Return a boolean series: True where |z| > threshold."""
    s = pd.to_numeric(values, errors="coerce")
    if s.notna().sum() < MIN_POINTS_FOR_DETECTION:
        return pd.Series(False, index=values.index)
    mean, std = s.mean(), s.std()
    if not std or np.isnan(std):
        return pd.Series(False, index=values.index)
    z = (s - mean) / std
    return z.abs() > threshold


def _iforest_flags(values: pd.Series, contamination: float = IFOREST_CONTAMINATION) -> pd.Series:
    """Return a boolean series: True where IsolationForest flags the value."""
    if not _HAS_SKLEARN:
        return pd.Series(False, index=values.index)
    s = pd.to_numeric(values, errors="coerce")
    valid = s.dropna()
    if len(valid) < MIN_POINTS_FOR_DETECTION:
        return pd.Series(False, index=values.index)
    X = valid.values.reshape(-1, 1)
    model = IsolationForest(contamination=contamination, random_state=42, n_estimators=100)
    preds = model.fit_predict(X) == -1   # -1 = outlier
    flags = pd.Series(False, index=values.index)
    flags.loc[valid.index] = preds
    return flags


def _jump_flags(deltas: pd.Series, factor: float = JUMP_FACTOR) -> pd.Series:
    """Flag impossibly-large per-period jumps (only meaningful for cumulative indices).

    Compares each delta against the median of non-zero deltas in the same group.
    """
    s = pd.to_numeric(deltas, errors="coerce")
    nonzero = s[s > 0]
    if len(nonzero) < MIN_POINTS_FOR_DETECTION:
        return pd.Series(False, index=deltas.index)
    median = nonzero.median()
    if not median or np.isnan(median):
        return pd.Series(False, index=deltas.index)
    return s > median * factor


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def detect_anomalies(df: pd.DataFrame) -> pd.DataFrame:
    """Add anomaly flags + reason column to df.

    Detection is performed per `measure` group. Energy rows are checked on
    `delta_kwh` (consumption rate); other rows on raw `value`.
    """
    if df.empty or "value" not in df.columns:
        out = df.copy()
        for col in ("anomaly_zscore", "anomaly_iforest", "anomaly_jump", "is_anomaly"):
            out[col] = False
        out["anomaly_reason"] = ""
        return out

    out = df.copy()
    out["anomaly_zscore"] = False
    out["anomaly_iforest"] = False
    out["anomaly_jump"] = False

    group_col = "measure" if "measure" in out.columns else "unit"
    has_delta = "delta_kwh" in out.columns

    for measure, group in out.groupby(group_col, dropna=False):
        idx = group.index

        # Pick the detection signal:
        #   - for energy rows that have a per-period delta -> use delta_kwh
        #   - otherwise -> use raw value
        is_energy_with_delta = (
            has_delta
            and group.get("quantity_type", pd.Series()).eq("energy").any()
            and group["delta_kwh"].notna().any()
        )
        signal = group["delta_kwh"] if is_energy_with_delta else group["value"]

        out.loc[idx, "anomaly_zscore"] = _zscore_flags(signal).values
        out.loc[idx, "anomaly_iforest"] = _iforest_flags(signal).values
        if is_energy_with_delta:
            out.loc[idx, "anomaly_jump"] = _jump_flags(group["delta_kwh"]).values

    # Combined flag + human-readable reason
    out["is_anomaly"] = (
        out["anomaly_zscore"] | out["anomaly_iforest"] | out["anomaly_jump"]
    )

    def _reason(row) -> str:
        reasons = []
        if row["anomaly_zscore"]:
            reasons.append("statistical outlier (Z-score)")
        if row["anomaly_iforest"]:
            reasons.append("ML outlier (IsolationForest)")
        if row["anomaly_jump"]:
            reasons.append("impossible jump in meter reading")
        return " · ".join(reasons)

    out["anomaly_reason"] = out.apply(_reason, axis=1)

    n_total = int(out["is_anomaly"].sum())
    breakdown = {
        "zscore": int(out["anomaly_zscore"].sum()),
        "iforest": int(out["anomaly_iforest"].sum()),
        "jump": int(out["anomaly_jump"].sum()),
    }
    logger.info(
        f"Detected {n_total:,} anomalies / {len(out):,} rows "
        f"({100*n_total/max(len(out),1):.2f}%). Breakdown: {breakdown}"
    )
    return out


# ---------------------------------------------------------------------------
# CLI helper
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    # Self-test on synthetic data
    np.random.seed(42)
    rng = np.random.default_rng(42)
    n = 200
    test = pd.DataFrame({
        "measure": ["Energie en kWh"] * n + ["Temperature"] * n,
        "quantity_type": ["energy"] * n + ["temperature"] * n,
        "value": np.concatenate([
            rng.normal(1000, 50, n),    # normal energy
            rng.normal(40, 5, n),        # normal temperature
        ]),
        "delta_kwh": np.concatenate([
            rng.normal(10, 2, n),
            [np.nan] * n,
        ]),
    })
    # Inject 3 obvious anomalies
    test.loc[10, "value"] = 99999
    test.loc[10, "delta_kwh"] = 999
    test.loc[250, "value"] = 200       # very hot
    test.loc[300, "value"] = -50       # impossible cold
    out = detect_anomalies(test)
    print(out[out["is_anomaly"]][["measure", "value", "delta_kwh", "anomaly_reason"]].to_string())