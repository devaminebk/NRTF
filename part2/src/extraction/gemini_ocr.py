"""gemini_ocr.py — Gemini Vision OCR client for structured energy document extraction.

Uses Gemini's multimodal capabilities to classify and extract data from scanned
Tunisian utility documents (STEG electricity invoices, meter reading sheets,
SONEDE water bills).

Advantages over Tesseract:
  - No local binary dependency
  - Handles Arabic, French, and English in one pass
  - Understands table layout natively — no regex fragility
  - Returns structured JSON directly via response_mime_type

Public API:
  client = GeminiOCRClient(api_key)
  df     = client.extract_to_dataframe(Path("invoice.jpg"))

The DataFrame schema matches extract_excel output:
  source | sheet | timestamp | category | measure | value | unit
"""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Optional, Union

import pandas as pd
from loguru import logger

try:
    import google.generativeai as genai
    from google.generativeai.types import GenerationConfig
    _GENAI_AVAILABLE = True
except ImportError:
    _GENAI_AVAILABLE = False


# ---------------------------------------------------------------------------
# Extraction prompt
# ---------------------------------------------------------------------------
_EXTRACTION_PROMPT = """\
You are an OCR specialist for Tunisian utility documents. Analyze the image carefully and extract energy data.

STEP 1 — Classify the document as exactly one of:
  • STEG_INVOICE_MT  — STEG electricity invoice "FACTURE MOYENNE TENSION"
  • STEG_METER_READ  — STEG meter reading sheet "FICHE RELEVE ENERGIE" / "INDEX D'ENERGIE" / "ACHAT ET VENTE"
  • SONEDE_WATER     — SONEDE water consumption bill
  • UNKNOWN          — any other document

STEP 2 — Extract all readable fields for that document type.

For STEG_INVOICE_MT, extract:
  - Active energy total in kWh  ("Consommation à facturer", "Énergie active", "Total")
  - Reactive energy in kVARh if present
  - Net amount to pay in DT   ("NET A PAYER", "Montant net")
  - Invoice number            ("N° Facture", "N° de la facture")
  - Billing period            ("Mois" field in MM/YYYY format)
  - District name             ("District")

For STEG_METER_READ, extract per tariff band (Jour, Pointe, Nuit, Soir, Réactive/Reactive):
  - ancien index  (old meter reading, 7–9 digit integer)
  - nouveau index (new meter reading, 7–9 digit integer)
  - consumption   = nouveau − ancien (always ≥ 0)
  - unit: "kWh" for active bands, "kVARh" for reactive
  - Billing period (MM/YYYY)

For SONEDE_WATER, extract:
  - Water consumption in m³
  - Billing period (MM/YYYY)

STEP 3 — Return ONLY valid JSON, no markdown fences, no extra text.

JSON structure:
{
  "doc_type":   "<STEG_INVOICE_MT | STEG_METER_READ | SONEDE_WATER | UNKNOWN>",
  "period":     "<MM/YYYY or null>",
  "invoice_no": "<string or null>",
  "district":   "<string or null>",
  "rows": [
    {
      "category": "<string>",
      "measure":  "<string>",
      "value":    <number or null>,
      "unit":     "<string>"
    }
  ]
}

Number format rules:
  • French thousands separator is a space or dot: "23 391 547" or "23.391.547" = 23391547
  • French decimal separator is a comma:          "10 173,290" = 10173.29
  • Convert all numbers to plain float/int in the JSON output.

If a field is illegible or absent, use null rather than guessing.
"""

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_period(period_str: Optional[str]) -> Optional[datetime]:
    """Parse 'MM/YYYY' string into a datetime(year, month, 1)."""
    if not period_str:
        return None
    m = re.match(r"(\d{1,2})[/.\-](\d{4})", period_str.strip())
    if m:
        try:
            return datetime(int(m.group(2)), int(m.group(1)), 1)
        except ValueError:
            pass
    return None


def _safe_float(val: Any) -> Optional[float]:
    """Return float or None; guard against Gemini occasionally returning a string."""
    if val is None:
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        # Try French number string as last resort
        if isinstance(val, str):
            cleaned = val.replace(" ", "").replace("\xa0", "").replace(".", "").replace(",", ".")
            try:
                return float(cleaned)
            except ValueError:
                pass
    return None


def _strip_fences(text: str) -> str:
    """Remove markdown code fences that some model versions still emit."""
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-z]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text.strip())
    return text.strip()


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------

class GeminiOCRClient:
    """Gemini Vision client for energy document extraction.

    Usage:
        client = GeminiOCRClient(api_key="...")
        df = client.extract_to_dataframe(Path("scan.jpg"))
    """

    def __init__(
        self,
        api_key: str,
        model_name: str = "gemini-2.0-flash",
    ) -> None:
        if not _GENAI_AVAILABLE:
            raise ImportError(
                "google-generativeai is not installed. "
                "Run: pip install google-generativeai"
            )
        genai.configure(api_key=api_key)
        self._model = genai.GenerativeModel(model_name=model_name)
        self._model_name = model_name
        logger.debug(f"[GeminiOCR] Initialized — model={model_name}")

    # ------------------------------------------------------------------
    # Low-level API call
    # ------------------------------------------------------------------

    def _call_api(self, image_path: Path) -> dict[str, Any]:
        """Send image to Gemini and return parsed JSON dict.

        Raises on network errors; returns {"doc_type": "UNKNOWN", "rows": []}
        on JSON parse failure so callers always get a well-formed dict.
        """
        try:
            from PIL import Image as PilImage
            img = PilImage.open(image_path)
        except Exception as e:
            raise OSError(f"Cannot open image {image_path}: {e}") from e

        try:
            response = self._model.generate_content(
                [_EXTRACTION_PROMPT, img],
                generation_config=GenerationConfig(
                    temperature=0.1,
                    response_mime_type="application/json",
                ),
            )
            raw = _strip_fences(response.text)
        except Exception:
            # Older SDK versions may not support response_mime_type — retry without it
            logger.debug("[GeminiOCR] Retrying without response_mime_type")
            response = self._model.generate_content(
                [_EXTRACTION_PROMPT, img],
                generation_config=GenerationConfig(temperature=0.1),
            )
            raw = _strip_fences(response.text)

        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            logger.warning(
                f"[GeminiOCR] JSON parse failed ({exc}). "
                f"Raw snippet: {raw[:200]!r}"
            )
            return {"doc_type": "UNKNOWN", "period": None,
                    "invoice_no": None, "district": None, "rows": []}

    # ------------------------------------------------------------------
    # DataFrame builder
    # ------------------------------------------------------------------

    def extract_to_dataframe(self, image_path: Union[str, Path]) -> pd.DataFrame:
        """Full pipeline: image → Gemini API → structured DataFrame.

        Returns an empty DataFrame on unrecoverable errors.
        The DataFrame schema mirrors extract_excel output:
            source | sheet | timestamp | category | measure | value | unit
        Optional extra columns for invoice docs: doc_id, district
        """
        image_path = Path(image_path)
        source = image_path.name
        logger.info(f"[GeminiOCR] Extracting: {source}")

        try:
            data = self._call_api(image_path)
        except Exception as exc:
            logger.error(f"[GeminiOCR] API call failed for {source}: {exc}")
            return pd.DataFrame()

        doc_type  = data.get("doc_type", "UNKNOWN")
        timestamp = _parse_period(data.get("period")) or pd.NaT
        invoice_no = data.get("invoice_no") or ""
        district   = data.get("district") or ""
        raw_rows   = data.get("rows") or []

        logger.info(
            f"[GeminiOCR] {source} → {doc_type} | "
            f"period={data.get('period')} | {len(raw_rows)} field(s) found"
        )

        if not raw_rows:
            if doc_type == "UNKNOWN":
                logger.warning(f"[GeminiOCR] Unclassified document: {source}")
                return pd.DataFrame([{
                    "source": source, "sheet": "UNKNOWN",
                    "timestamp": pd.NaT,
                    "category": "OCR_RAW",
                    "measure": "Document non classifié (Gemini)",
                    "value": None, "unit": "",
                }])
            logger.warning(f"[GeminiOCR] {doc_type} classified but no rows extracted: {source}")
            return pd.DataFrame()

        base = {"source": source, "sheet": doc_type, "timestamp": timestamp}
        rows: list[dict] = []

        if doc_type == "STEG_INVOICE_MT":
            for r in raw_rows:
                rows.append({
                    **base,
                    "category": r.get("category") or "Consommation électrique",
                    "measure":  r.get("measure")  or "",
                    "value":    _safe_float(r.get("value")),
                    "unit":     r.get("unit")     or "",
                    "doc_id":   invoice_no,
                    "district": district,
                })

        elif doc_type == "STEG_METER_READ":
            for r in raw_rows:
                rows.append({
                    **base,
                    "category": r.get("category") or "Index énergie",
                    "measure":  r.get("measure")  or "",
                    "value":    _safe_float(r.get("value")),
                    "unit":     r.get("unit")     or "kWh",
                })

        elif doc_type == "SONEDE_WATER":
            for r in raw_rows:
                rows.append({
                    **base,
                    "category": r.get("category") or "Eau",
                    "measure":  r.get("measure")  or "Quantité consommée",
                    "value":    _safe_float(r.get("value")),
                    "unit":     r.get("unit")     or "m3",
                })

        else:  # UNKNOWN with rows (shouldn't happen but handle gracefully)
            for r in raw_rows:
                rows.append({
                    **base,
                    "category": r.get("category") or "",
                    "measure":  r.get("measure")  or "",
                    "value":    _safe_float(r.get("value")),
                    "unit":     r.get("unit")     or "",
                })

        return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Module-level availability check
# ---------------------------------------------------------------------------

def is_available() -> bool:
    """True if google-generativeai is installed."""
    return _GENAI_AVAILABLE


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import os
    import sys
    from dotenv import load_dotenv

    load_dotenv()
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        print("Error: GEMINI_API_KEY not set in environment or .env", file=sys.stderr)
        sys.exit(1)

    if len(sys.argv) < 2:
        print("Usage: python gemini_ocr.py <image_path>")
        sys.exit(1)

    client = GeminiOCRClient(api_key=key)
    df = client.extract_to_dataframe(Path(sys.argv[1]))
    print(df.to_string())
    print(f"\nShape: {df.shape}")
