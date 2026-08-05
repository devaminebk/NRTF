"""main.py — Pipeline orchestrator.

End-to-end flow:
    1. Extract from Excel, PDFs, and images (scanned documents via Gemini Vision OCR).
    2. Normalize units to kWh (only for energy measurements).
    3. Convert cumulative meter indices to per-period deltas.
    4. Compute CO2 emissions on the deltas.
    5. (Optional) Detect anomalies.
    6. Save consolidated CSV for the Streamlit dashboard.
"""
from pathlib import Path

import pandas as pd
from loguru import logger

from src.extraction.extract_excel import extract_all_excels
from src.extraction.extract_image import extract_all_images
from src.extraction.extract_pdf import extract_all_pdfs
from src.normalization.normalize import normalize_to_kwh
from src.emissions.co2 import add_co2_emissions, cumulative_to_delta
from src.utils.config import RAW_DATA_DIR, PROCESSED_DATA_DIR


def run_pipeline() -> pd.DataFrame:
    logger.info("=== Re·Tech Fusion pipeline started ===")

    # 1. EXTRACT — from Excel, images, and PDFs
    raw_dir = Path(RAW_DATA_DIR)
    dfs = []
    
    # Excel extraction
    df_excel = extract_all_excels(raw_dir)
    if not df_excel.empty:
        dfs.append(df_excel)
        logger.info(f"Excel: {len(df_excel)} rows")
    
    # Image extraction (Gemini Vision OCR or Tesseract fallback)
    image_dir = raw_dir / "images"
    if image_dir.exists():
        try:
            df_images = extract_all_images(image_dir)
            if not df_images.empty:
                dfs.append(df_images)
                logger.info(f"Images: {len(df_images)} rows")
        except Exception as e:
            logger.warning(f"Image extraction failed: {e}")
    
    # PDF extraction (table + OCR)
    pdf_dir = raw_dir / "pdfs"
    if pdf_dir.exists():
        try:
            df_pdfs = extract_all_pdfs(pdf_dir)
            if not df_pdfs.empty:
                dfs.append(df_pdfs)
                logger.info(f"PDFs: {len(df_pdfs)} rows")
        except Exception as e:
            logger.warning(f"PDF extraction failed: {e}")
    
    if not dfs:
        logger.error(f"No data extracted from {RAW_DATA_DIR}. Aborting.")
        return pd.DataFrame()
    
    df = pd.concat(dfs, ignore_index=True)
    logger.info(f"Combined: {len(df)} total rows")

    # 2. NORMALIZE units
    df = normalize_to_kwh(df)

    # 3. Cumulative indices -> per-period deltas
    df = cumulative_to_delta(df, group_cols=("source", "measure"))

    # 4. CO2 on the DELTA, not the cumulative index
    df_for_co2 = df.copy()
    df_for_co2["value_kwh"] = df_for_co2["delta_kwh"]
    df_with_co2 = add_co2_emissions(df_for_co2)
    df["co2_kg"] = df_with_co2["co2_kg"]
    df["co2_source"] = df_with_co2["co2_source"]
    df["co2_factor"] = df_with_co2["co2_factor"]

    # 5. Anomaly detection — optional, skip if module not ready
    try:
        from src.anomalies.detect import detect_anomalies
        df = detect_anomalies(df)
    except Exception as e:
        logger.warning(f"Anomaly detection skipped: {e}")

    # 6. SAVE
    out_path = Path(PROCESSED_DATA_DIR) / "energy_consolidated.csv"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_path, index=False)
    logger.success(f"Saved {len(df):,} rows -> {out_path}")
    return df


if __name__ == "__main__":
    run_pipeline()

# Run the app
# streamlit run "c:\Users\dell\Desktop\NRTF\part2\src\dashboard\app.py" --server.port 8501 --server.address 0.0.0.0