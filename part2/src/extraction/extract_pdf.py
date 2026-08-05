"""extract_pdf.py — Read energy data from PDF invoices/reports.

For scanned PDFs (no text layer), converts pages to images and uses Gemini Vision or Tesseract.
For digital PDFs, extracts tables directly.
"""
from pathlib import Path
from typing import Union
import io

import pandas as pd
import pdfplumber
from pdf2image import convert_from_path
from loguru import logger


def extract_pdf(filepath: Union[str, Path]) -> pd.DataFrame:
    """Extract tables and key fields from a single PDF.

    Strategy:
      1. Try to extract tables using pdfplumber (for digital PDFs)
      2. If minimal data found, convert to images and use OCR (Gemini or Tesseract)

    Returns a DataFrame with schema: ['source', 'sheet', 'timestamp', 'category', 'measure', 'value', 'unit']
    """
    filepath = Path(filepath)
    logger.info(f"Reading PDF: {filepath.name}")
    
    rows: list[dict] = []
    has_tables = False
    
    # Step 1: Try table extraction (digital PDFs)
    try:
        with pdfplumber.open(filepath) as pdf:
            for page_num, page in enumerate(pdf.pages, 1):
                tables = page.extract_tables()
                if tables:
                    has_tables = True
                    for table in tables:
                        for row in table:
                            rows.append(row)
    except Exception as e:
        logger.warning(f"  pdfplumber failed: {e}")
    
    if rows and has_tables:
        # Found tables — convert to DataFrame with minimal schema
        df = pd.DataFrame(rows)
        df["source"] = filepath.name
        df["sheet"] = "PDF_TABLE"
        df["timestamp"] = pd.NaT
        # Try to extract numbers and units from table cells
        df = _parse_pdf_table_rows(df, filepath.name)
        if not df.empty:
            logger.info(f"  Extracted {len(df)} rows from tables")
            return df
    
    # Step 2: No tables or minimal data → convert to images and use OCR
    logger.info(f"  No structured tables found; converting to images for OCR")
    try:
        from src.extraction.extract_image import extract_image
        
        # Convert PDF pages to PIL images
        images = convert_from_path(str(filepath), fmt='png')
        dfs = []
        for page_num, img in enumerate(images, 1):
            # Save temp image
            temp_path = Path(f"/tmp/page_{page_num}.png")
            temp_path.parent.mkdir(exist_ok=True, parents=True)
            img.save(str(temp_path))
            try:
                df = extract_image(temp_path)
                if not df.empty:
                    df["source"] = f"{filepath.name}_page{page_num}"
                    dfs.append(df)
            finally:
                temp_path.unlink(missing_ok=True)
        
        if dfs:
            result = pd.concat(dfs, ignore_index=True)
            logger.info(f"  OCR extracted {len(result)} rows from {len(images)} pages")
            return result
    except Exception as e:
        logger.warning(f"  OCR conversion failed: {e}")
    
    # Return empty DataFrame with correct schema
    return pd.DataFrame(
        columns=["source", "sheet", "timestamp", "category", "measure", "value", "unit"]
    )


def _parse_pdf_table_rows(df: pd.DataFrame, source: str) -> pd.DataFrame:
    """Convert raw table rows into structured energy data format.
    
    Attempts to find numeric columns and map them to energy measurements.
    This is a best-effort parser for common PDF table layouts.
    """
    import re
    from datetime import datetime
    
    rows: list[dict] = []
    base = {
        "source": source,
        "sheet": "PDF_TABLE",
        "timestamp": pd.NaT,
    }
    
    # Flatten all cells into a single searchable text
    all_text = " ".join(str(cell) for cell in df.values.flatten()).upper()
    
    # Try to find energy-related keywords and associated numbers
    energy_patterns = [
        (r"CONSOMMATION.*?(\d+(?:[,.]\d+)?)\s*kWh", "Consommation", "kWh"),
        (r"ENERGY.*?(\d+(?:[,.]\d+)?)\s*kWh", "Énergie", "kWh"),
        (r"(\d+(?:[,.]\d+)?)\s*kVARh", "Énergie réactive", "kVARh"),
        (r"NET.*?(\d+(?:[,.]\d+)?)\s*DT", "Montant net", "DT"),
    ]
    
    for pattern, measure, unit in energy_patterns:
        m = re.search(pattern, all_text)
        if m:
            val_str = m.group(1).replace(",", ".")
            try:
                value = float(val_str)
                rows.append({
                    **base,
                    "category": "Énergie",
                    "measure": measure,
                    "value": value,
                    "unit": unit,
                })
            except ValueError:
                pass
    
    if rows:
        return pd.DataFrame(rows)
    
    # Fallback: return the raw table as-is
    df = df.copy()
    df.insert(0, "unit", "")
    df.insert(0, "value", None)
    df.insert(0, "measure", "")
    df.insert(0, "category", "PDF_RAW")
    df.insert(0, "timestamp", pd.NaT)
    df.insert(0, "sheet", "PDF_TABLE")
    df.insert(0, "source", source)
    return df


def extract_all_pdfs(folder: Union[str, Path]) -> pd.DataFrame:
    """Extract every .pdf in a folder. Errors on individual files don't stop the batch."""
    folder = Path(folder)
    files = sorted(list(folder.glob("*.pdf")) + list(folder.glob("*.PDF")))
    logger.info(f"Found {len(files)} PDF file(s) in {folder}")
    
    dfs: list[pd.DataFrame] = []
    for f in files:
        try:
            df = extract_pdf(f)
            if not df.empty:
                dfs.append(df)
        except Exception as e:
            logger.error(f"  Failed on {f.name}: {e}")
    
    if not dfs:
        return pd.DataFrame(
            columns=["source", "sheet", "timestamp", "category", "measure", "value", "unit"]
        )
    result = pd.concat(dfs, ignore_index=True)
    logger.success(f"Total PDF rows extracted: {len(result):,}")
    return result
