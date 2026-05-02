"""extract_pdf.py — Read energy data from PDF invoices/reports."""
from pathlib import Path
from typing import Union

import pandas as pd
import pdfplumber
from loguru import logger


def extract_pdf(filepath: Union[str, Path]) -> pd.DataFrame:
    """Extract tables and key fields from a single PDF.

    Returns a DataFrame with columns: ['source', 'timestamp', 'value', 'unit']
    """
    filepath = Path(filepath)
    logger.info(f"Reading PDF: {filepath.name}")
    rows = []
    with pdfplumber.open(filepath) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables()
            for table in tables:
                for row in table:
                    rows.append(row)
    # TODO: parse rows into structured columns
    df = pd.DataFrame(rows)
    df["source"] = filepath.name
    return df


def extract_all_pdfs(folder: Union[str, Path]) -> pd.DataFrame:
    """Extract every .pdf in a folder."""
    folder = Path(folder)
    files = list(folder.glob("*.pdf"))
    logger.info(f"Found {len(files)} PDF file(s) in {folder}")
    dfs = [extract_pdf(f) for f in files]
    return pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()
