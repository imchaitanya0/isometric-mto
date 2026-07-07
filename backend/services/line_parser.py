"""
Line number parser for piping isometric drawings.

Decodes a line number like: 6"-P-1501-A1A-IH
Into structured fields:
  size       = "6\""        (Nominal Pipe Size)
  service    = "P"          (Process service code)
  sequence   = "1501"       (Line sequence number)
  material_class = "A1A"    (Piping material class / spec)
  insulation = "IH"         (Insulation code)

Common service codes:
  P = Process  |  HV = HVAC  |  CS = Cooling Steam  |  FW = Firewater
  HP = High Pressure  |  LP = Low Pressure  |  D = Drain  |  V = Vent

Common insulation codes:
  IH = Hot insulation  |  IC = Cold insulation  |  N = None / bare
  HT = Heat tracing  |  PD = Personnel protection
"""
import re
from typing import Optional

from models.mto import LineNumberParsed

# Full pattern: size-service-sequence-class-insulation
# e.g. 6"-P-1501-A1A-IH  or  4"-HV-2301-B2B-N
_LINE_NUMBER_RE = re.compile(
    r"""
    ^
    (?P<size>\d+(?:\.\d+)?["''"″]?)   # Nominal pipe size: 6" or 4 or 12"
    \s*-\s*
    (?P<service>[A-Z]{1,4})            # Service code: P, HV, CS ...
    \s*-\s*
    (?P<sequence>\d{3,6})              # Sequence: 1501
    \s*-\s*
    (?P<material_class>[A-Z0-9]{2,8}) # Material class: A1A, B2B
    (?:                                # Optional insulation segment
        \s*-\s*
        (?P<insulation>[A-Z]{1,4})
    )?
    $
    """,
    re.VERBOSE | re.IGNORECASE,
)

# Partial / relaxed pattern for messy OCR output
_LINE_NUMBER_RELAXED_RE = re.compile(
    r"""
    (\d+(?:\.\d+)?["''"″]?)   # size
    [-\s]+
    ([A-Z]{1,4})               # service
    [-\s]+
    (\d{3,6})                  # sequence
    """,
    re.VERBOSE | re.IGNORECASE,
)

SERVICE_NAMES: dict[str, str] = {
    "P": "Process",
    "HV": "HVAC",
    "CS": "Cooling Steam",
    "FW": "Firewater",
    "HP": "High Pressure Steam",
    "LP": "Low Pressure Steam",
    "D": "Drain",
    "V": "Vent",
    "CW": "Cooling Water",
    "IA": "Instrument Air",
    "PA": "Plant Air",
    "N2": "Nitrogen",
    "FG": "Fuel Gas",
    "SL": "Slop",
    "WW": "Waste Water",
}

INSULATION_NAMES: dict[str, str] = {
    "IH": "Hot insulation",
    "IC": "Cold / cryogenic insulation",
    "HT": "Heat tracing",
    "PD": "Personnel protection",
    "N": "None (bare)",
    "HW": "Hot water insulation",
}


def parse_line_number(line_number: Optional[str]) -> LineNumberParsed:
    """
    Parse a piping line number string into its component parts.
    Returns a LineNumberParsed object (all fields optional if parsing fails).
    """
    if not line_number:
        return LineNumberParsed()

    raw = line_number.strip()
    # Normalise: replace curly quotes, multiple spaces with single dash
    normalised = raw.replace("\u201c", '"').replace("\u201d", '"').replace("\u2033", '"')
    normalised = re.sub(r"\s*-\s*", "-", normalised)

    result = LineNumberParsed(raw=raw)

    m = _LINE_NUMBER_RE.match(normalised)
    if m:
        result.size = _normalise_size(m.group("size"))
        result.service = m.group("service").upper()
        result.sequence = m.group("sequence")
        result.material_class = m.group("material_class").upper() if m.group("material_class") else None
        result.insulation = m.group("insulation").upper() if m.group("insulation") else None
        return result

    # Try relaxed match
    m2 = _LINE_NUMBER_RELAXED_RE.search(normalised)
    if m2:
        result.size = _normalise_size(m2.group(1))
        result.service = m2.group(2).upper()
        result.sequence = m2.group(3)
        return result

    return result  # Return with only raw populated


def _normalise_size(raw_size: str) -> str:
    """Normalise size string: '6' → '6\"', '6in' → '6\"'."""
    s = raw_size.strip()
    if s and s[-1] not in ('"', "'", "″", '"', '"'):
        s = s + '"'
    # Replace fancy quotes with standard "
    s = s.replace("\u201c", '"').replace("\u201d", '"').replace("\u2033", '"')
    return s
