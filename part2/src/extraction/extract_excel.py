"""extract_excel.py — Read energy data from BILAN TOTAL cogeneration reports.

The Excel files have a "pivoted" layout:
  - Row 10:    date of each reading (one column per timestamp)
  - Row 11:    time of each reading
  - Rows 12-63: 52 measurement labels (gaz, electricity, water flow, temps, ...)
  - Column A:  measurement category (often empty -> inherit from previous)
  - Column B:  measurement label (contains the unit in plain text)
  - Columns E onward: the numeric values, one column per timestamp

We unpivot this into a long-format DataFrame:
    source | timestamp | category | measure | value | unit | sheet

This is the standard "tidy" format expected by the rest of the pipeline.
"""
from __future__ import annotations

import re
from datetime import date, datetime, time
from pathlib import Path
from typing import Optional, Union

import openpyxl
import pandas as pd
from loguru import logger

# ---------------------------------------------------------------------------
# Layout constants (1-indexed because openpyxl uses 1-indexed rows/columns)
# ---------------------------------------------------------------------------
DATE_ROW = 10
TIME_ROW = 11
MEASURE_ROW_START = 12
MEASURE_ROW_END = 63
DATA_COL_START = 5  # column E

CATEGORY_COL = 1   # column A
LABEL_COL = 2      # column B


# ---------------------------------------------------------------------------
# Unit detection
# ---------------------------------------------------------------------------
_UNIT_REGEX = re.compile(
    r"\b(kVARh|KVARh|kWh|KWh|Nm3/h|Nm3|m3/h|m3|kW|KW|rpm|V|A|°C)\b"
)


def detect_unit(label: Optional[str]) -> str:
    """Extract the unit from a measurement label.

    Tries explicit units first, then falls back to keyword-based heuristics.
    Returns "" if no unit can be determined (dimensionless quantity).
    """
    if not label:
        return ""
    s = str(label).strip()
    s_low = s.lower()

    # 1. Explicit unit token in the label
    m = _UNIT_REGEX.search(s)
    if m:
        # Normalize case (kWh, kW, kVARh ...)
        token = m.group(1)
        # canonical forms
        canonical = {
            "kwh": "kWh", "kvarh": "kVARh", "kw": "kW",
            "nm3": "Nm3", "nm3/h": "Nm3/h",
            "m3": "m3", "m3/h": "m3/h",
            "rpm": "rpm", "v": "V", "a": "A", "°c": "°C",
        }
        return canonical.get(token.lower(), token)

    # 2. Percentage sign
    if "%" in s:
        return "%"

    # 3. Temperature-related labels
    if (
        re.search(r"temp[eé]r", s_low)
        or "consigne" in s_low
        or "lecture" in s_low
    ):
        return "°C"

    # 4. Hours of operation
    if "heure" in s_low and "fonctionnement" in s_low:
        return "h"

    # 5. Facteur de puissance is dimensionless — check BEFORE "puissance" rule
    if "facteur" in s_low and "puissance" in s_low:
        return ""

    # 6. Generic "puissance" -> kW
    if "puissance" in s_low:
        return "kW"

    return ""


# ---------------------------------------------------------------------------
# Timestamp parsing
# ---------------------------------------------------------------------------
def _to_date(value) -> Optional[date]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
            try:
                return datetime.strptime(value.strip(), fmt).date()
            except ValueError:
                continue
    return None


def _to_time(value) -> Optional[time]:
    if value is None:
        return None
    if isinstance(value, time):
        return value
    if isinstance(value, datetime):
        return value.time()
    if isinstance(value, str):
        for fmt in ("%H:%M:%S", "%H:%M"):
            try:
                return datetime.strptime(value.strip(), fmt).time()
            except ValueError:
                continue
    return None


def _build_timestamp(d, t) -> Optional[datetime]:
    d_parsed = _to_date(d)
    t_parsed = _to_time(t)
    if d_parsed is None or t_parsed is None:
        return None
    return datetime.combine(d_parsed, t_parsed)


# ---------------------------------------------------------------------------
# Core extraction
# ---------------------------------------------------------------------------
def extract_excel(filepath: Union[str, Path]) -> pd.DataFrame:
    """Extract one BILAN TOTAL Excel file into a long-format DataFrame.

    Returns columns:
        source, sheet, timestamp, category, measure, value, unit

    Implementation note: we do ONE full pass through each sheet (streaming)
    and store row 1..MEASURE_ROW_END in memory as a small 2D matrix.
    Random `ws.cell()` access is too slow on large sheets (4000+ columns).
    """
    filepath = Path(filepath)
    logger.info(f"Reading Excel: {filepath.name}")

    # data_only=True returns formula RESULTS (not formula text)
    wb = openpyxl.load_workbook(filepath, data_only=True)
    all_rows: list[dict] = []

    for sheet_name in wb.sheetnames:
        ws = wb[sheet_name]

        # --- ONE PASS: read rows 1..MEASURE_ROW_END into a list-of-tuples ---
        max_row_needed = MEASURE_ROW_END
        rows_buffer: list[tuple] = []
        for r_idx, row in enumerate(
            ws.iter_rows(min_row=1, max_row=max_row_needed, values_only=True),
            start=1,
        ):
            rows_buffer.append(row)

        if len(rows_buffer) < TIME_ROW:
            logger.warning(f"  Sheet '{sheet_name}': too few rows, skipping")
            continue

        date_row_vals = rows_buffer[DATE_ROW - 1]
        time_row_vals = rows_buffer[TIME_ROW - 1]

        # 1. Locate timestamp columns
        timestamp_cols: list[tuple[int, datetime]] = []
        n_cols = max(len(date_row_vals), len(time_row_vals))
        for col_idx in range(DATA_COL_START - 1, n_cols):
            d = date_row_vals[col_idx] if col_idx < len(date_row_vals) else None
            t = time_row_vals[col_idx] if col_idx < len(time_row_vals) else None
            ts = _build_timestamp(d, t)
            if ts is not None:
                timestamp_cols.append((col_idx, ts))

        if not timestamp_cols:
            logger.warning(f"  Sheet '{sheet_name}': no timestamp columns found")
            continue

        # 2. Build measure descriptors (row_idx, category, label, unit)
        measures: list[tuple[int, str, str, str]] = []
        current_category = ""
        for r in range(MEASURE_ROW_START, MEASURE_ROW_END + 1):
            row = rows_buffer[r - 1]
            cat = row[CATEGORY_COL - 1] if len(row) > CATEGORY_COL - 1 else None
            label = row[LABEL_COL - 1] if len(row) > LABEL_COL - 1 else None
            if cat:
                current_category = str(cat).strip()
            if label:
                measures.append(
                    (r, current_category, str(label).strip(), detect_unit(label))
                )

        # 3. Emit one row per (measure × timestamp)
        for row_idx, category, measure, unit in measures:
            row = rows_buffer[row_idx - 1]
            row_len = len(row)
            for col_idx, ts in timestamp_cols:
                value = row[col_idx] if col_idx < row_len else None
                all_rows.append(
                    {
                        "source": filepath.name,
                        "sheet": sheet_name,
                        "timestamp": ts,
                        "category": category,
                        "measure": measure,
                        "value": value,
                        "unit": unit,
                    }
                )

        logger.info(
            f"  Sheet '{sheet_name}': {len(measures)} measures x "
            f"{len(timestamp_cols)} timestamps = "
            f"{len(measures) * len(timestamp_cols):,} data points"
        )

    df = pd.DataFrame(all_rows)
    if not df.empty:
        df["value"] = pd.to_numeric(df["value"], errors="coerce")
    return df


def extract_all_excels(folder: Union[str, Path]) -> pd.DataFrame:
    """Extract every .xlsx / .xls in a folder and concatenate into one DataFrame."""
    folder = Path(folder)
    files = sorted(
        f for f in (list(folder.glob("*.xlsx")) + list(folder.glob("*.xls")))
        if not f.name.startswith("~$")
    )
    logger.info(f"Found {len(files)} Excel file(s) in {folder}")

    dfs: list[pd.DataFrame] = []
    for f in files:
        try:
            df = extract_excel(f)
            if not df.empty:
                dfs.append(df)
        except Exception as e:
            logger.error(f"  Failed to extract {f.name}: {e}")

    if not dfs:
        return pd.DataFrame(
            columns=["source", "sheet", "timestamp", "category", "measure", "value", "unit"]
        )

    result = pd.concat(dfs, ignore_index=True)
    logger.success(f"Total Excel rows extracted: {len(result):,}")
    return result


# ---------------------------------------------------------------------------
# CLI helper for quick testing:  python -m src.extraction.extract_excel <file>
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        df = extract_excel(sys.argv[1])
    else:
        from src.utils.config import RAW_DATA_DIR
        df = extract_all_excels(RAW_DATA_DIR)

    print(df.head(15))
    print(f"\nShape: {df.shape}")
    print(f"\nUnits found: {df['unit'].value_counts().to_dict()}")
    print(f"\nCategories: {df['category'].unique().tolist()}")