"""
Tesseract OCR for title block extraction.

Tries to extract:
  - drawing_no   e.g. "ISO-1501-01"
  - revision     e.g. "2" or "Rev.2"
  - line_number  e.g. '6"-P-1501-A1A-IH'

Returns a dict with values + per-field confidence score.
Falls back gracefully to empty dict if Tesseract is not available or OCR fails.
"""
import re
from typing import Optional

from PIL import Image


def _safe_tesseract(img: Image.Image) -> str:
    """Run pytesseract on an image, return empty string on any failure."""
    try:
        import pytesseract
        text = pytesseract.image_to_string(img, config="--psm 6 --oem 3")
        return text
    except Exception:
        return ""


def extract_title_block_meta(img: Image.Image) -> dict:
    """
    Run OCR on a (pre-cropped) title block image.

    Returns:
        {
            "drawing_no": str | None,
            "revision": str | None,
            "line_number": str | None,
            "confidence": float (0.0–1.0, rough estimate based on fields found),
        }
    """
    # Enlarge small crops for better OCR accuracy
    w, h = img.size
    if max(w, h) < 800:
        scale = 800 / max(w, h)
        img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)

    text = _safe_tesseract(img)
    if not text.strip():
        return {"drawing_no": None, "revision": None, "line_number": None, "confidence": 0.0}

    result = {
        "drawing_no": _extract_drawing_no(text),
        "revision": _extract_revision(text),
        "line_number": _extract_line_number(text),
    }

    fields_found = sum(1 for v in result.values() if v)
    result["confidence"] = round(fields_found / 3, 2)  # 0, 0.33, 0.67, or 1.0

    return result


# ── Regex extractors ──────────────────────────────────────────────────────────

def _extract_drawing_no(text: str) -> Optional[str]:
    """Match patterns like ISO-1501-01, DWG-1234, P-001, etc."""
    patterns = [
        r"\b(ISO[-_]\d{3,6}[-_]\d{1,3}[A-Z]?)\b",
        r"\b(DWG[-_]\d{3,6})\b",
        r"drawing\s*(?:no\.?|number)?\s*[:\-]?\s*([A-Z0-9][-A-Z0-9_]{3,20})",
        r"\b([A-Z]{1,4}-\d{3,6}[-_]\d{1,3})\b",
    ]
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            return m.group(1).strip()
    return None


def _extract_revision(text: str) -> Optional[str]:
    """Match patterns like Rev.2, Revision: 3, R2, Rev A."""
    patterns = [
        r"rev(?:ision)?\.?\s*[:\-]?\s*([A-Z0-9]{1,3})\b",
        r"\brev\.?\s*([A-Z0-9]{1,3})\b",
        r"\bR(\d{1,2})\b",
    ]
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            return m.group(1).strip()
    return None


def _extract_line_number(text: str) -> Optional[str]:
    """
    Match piping line numbers like:
      6"-P-1501-A1A-IH
      4"-HV-2301-B2B-N
      12\"-CS-0401-C1C-HI
    Pattern: size-service-sequence-class-insulation
    """
    patterns = [
        r"""(\d+(?:\.\d+)?["''"″]?-[A-Z]{1,4}-\d{3,6}-[A-Z0-9]{2,6}-[A-Z]{1,4})""",
        r"""line\s*(?:no\.?|number|#)?\s*[:\-]?\s*(\d+["''"″]?-[A-Z0-9\-]{5,25})""",
    ]
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            return m.group(1).strip()
    return None
