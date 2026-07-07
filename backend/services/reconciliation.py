"""
Reconciliation layer.

Merges:
  - Pass A results (symbol detection from full image)
  - Pass B results (BOM table transcription from cropped region)
  - OCR title block metadata

Logic:
  1. Merge items from Pass A and Pass B using fuzzy description matching
  2. Flag quantity mismatches in remarks
  3. Derive GASKET and BOLT SET rows from flange count
  4. Merge drawing_meta: pick higher-confidence source per field
  5. Compute summary totals
"""
import difflib
import re
from typing import Optional

from models.mto import (
    BoundingBox, DrawingMeta, EndType, ItemCategory, ItemUnit,
    LineNumberParsed, MTOItem, Summary,
)
from services.line_parser import parse_line_number


# ── Public entry point ────────────────────────────────────────────────────────

def reconcile(
    pass_a: dict,
    pass_b: dict,
    ocr_meta: dict,
) -> tuple[DrawingMeta, list[MTOItem], Summary]:
    """
    Main reconciliation function.

    Args:
        pass_a:   dict from gemini_client.pass_a_extract()
        pass_b:   dict from gemini_client.pass_b_extract()
        ocr_meta: dict from ocr_title.extract_title_block_meta()

    Returns:
        (DrawingMeta, list[MTOItem], Summary)
    """
    # Step 1: Build drawing metadata
    drawing_meta = _merge_meta(
        pass_a.get("drawing_meta", {}),
        pass_b,
        ocr_meta,
    )

    # Step 2: Normalise items from both passes
    a_items = [_normalise_item(it, source="a") for it in pass_a.get("items", [])]
    b_items = [_normalise_item(it, source="b") for it in pass_b.get("bom_rows", [])]

    # Step 3: Merge / deduplicate
    merged = _merge_items(a_items, b_items)

    # Step 4: Ensure gasket + bolt sets are present
    merged = _derive_consumables(merged)

    # Step 5: Assign sequential item numbers
    for idx, item in enumerate(merged, start=1):
        item["item_no"] = idx

    # Step 6: Convert to Pydantic MTOItem objects
    mto_items = _build_mto_items(merged)

    # Step 7: Compute summary
    summary = _compute_summary(mto_items, pass_a.get("field_welds", 0))

    return drawing_meta, mto_items, summary


# ── Meta merging ──────────────────────────────────────────────────────────────

def _merge_meta(
    gemini_meta: dict,
    pass_b: dict,
    ocr_meta: dict,
) -> DrawingMeta:
    """Pick the best available value for each metadata field."""

    def pick(gemini_val, ocr_val, pass_b_val=None):
        """Return the first non-empty value, preferring Gemini > Pass B > OCR."""
        for v in [gemini_val, pass_b_val, ocr_val]:
            if v and str(v).strip():
                return str(v).strip()
        return None

    drawing_no = pick(
        gemini_meta.get("drawing_no"),
        ocr_meta.get("drawing_no"),
        pass_b.get("drawing_no"),
    )
    revision = pick(
        gemini_meta.get("revision"),
        ocr_meta.get("revision"),
        pass_b.get("revision"),
    )
    line_number = pick(
        gemini_meta.get("line_number"),
        ocr_meta.get("line_number"),
        pass_b.get("line_number"),
    )

    parsed = parse_line_number(line_number)

    # Confidence: average of available sources
    confs = [
        float(gemini_meta.get("confidence", 0.5)),
        float(ocr_meta.get("confidence", 0.0)),
    ]
    confidence = round(sum(confs) / len(confs), 2)

    return DrawingMeta(
        drawing_no=drawing_no,
        revision=revision,
        line_number=line_number,
        line_number_parsed=parsed,
        nps=gemini_meta.get("nps") or parsed.size,
        material_class=gemini_meta.get("material_class") or parsed.material_class,
        service=gemini_meta.get("service") or parsed.service,
        design_pressure=gemini_meta.get("design_pressure"),
        design_temperature=gemini_meta.get("design_temperature"),
        confidence=confidence,
    )


# ── Item normalisation ────────────────────────────────────────────────────────

def _normalise_item(raw: dict, source: str) -> dict:
    """Normalise a raw item dict from either pass into a consistent structure."""
    return {
        "source": source,
        "item_no": raw.get("item_no", 0),
        "category": _normalise_category(raw.get("category", "")),
        "description": str(raw.get("description", "")).strip(),
        "size_nps": str(raw.get("size_nps", "")).strip() or "?",
        "schedule_rating": raw.get("schedule_rating") or raw.get("rating") or raw.get("schedule"),
        "material_spec": raw.get("material_spec") or raw.get("material") or raw.get("spec"),
        "end_type": _normalise_end_type(raw.get("end_type", "")),
        "quantity": _to_float(raw.get("quantity", 1)),
        "unit": _normalise_unit(raw.get("unit", "EA"), raw.get("category", "")),
        "length_m": _to_float(raw.get("length_m")),
        "confidence": min(1.0, max(0.0, float(raw.get("confidence", 0.7)))),
        "remarks": str(raw.get("remarks", "") or ""),
        "bbox": raw.get("bbox"),
    }


def _normalise_category(raw: str) -> str:
    raw = str(raw).upper().strip()
    mapping = {
        "PIPE": "PIPE", "PIPING": "PIPE",
        "FITTING": "FITTING", "FIT": "FITTING", "FITTINGS": "FITTING",
        "FLANGE": "FLANGE", "FLANGES": "FLANGE", "FLG": "FLANGE",
        "VALVE": "VALVE", "VALVES": "VALVE", "VLV": "VALVE",
        "GASKET": "GASKET", "GASKETS": "GASKET", "GSK": "GASKET",
        "BOLT": "BOLT", "BOLTS": "BOLT", "FASTENER": "BOLT", "STUD": "BOLT",
        "SUPPORT": "SUPPORT",
    }
    return mapping.get(raw, "FITTING")  # Default to FITTING if unknown


def _normalise_unit(raw: str, category: str) -> str:
    raw = str(raw).upper().strip()
    cat = _normalise_category(category)
    if cat == "PIPE" or raw in ("M", "LM", "MTR", "METRE", "METER"):
        return "M"
    if raw in ("SET", "SETS"):
        return "SET"
    return "EA"


def _normalise_end_type(raw: str) -> Optional[str]:
    mapping = {
        "BW": "BW", "BUTT": "BW", "BUTTWELD": "BW",
        "SW": "SW", "SOCKET": "SW",
        "THD": "THD", "THREAD": "THD", "THREADED": "THD",
        "FLGD": "FLGD", "FLANGED": "FLGD",
        "PE": "PE", "BE": "BE",
    }
    return mapping.get(str(raw).upper().strip())


def _to_float(v) -> Optional[float]:
    if v is None:
        return None
    try:
        return float(v)
    except (ValueError, TypeError):
        return None


# ── Item merging (fuzzy) ──────────────────────────────────────────────────────

_SIMILARITY_THRESHOLD = 0.75


def _item_key(item: dict) -> str:
    """Create a normalised key for fuzzy matching."""
    desc = re.sub(r"\s+", " ", item["description"].lower())
    size = item["size_nps"].lower().replace('"', '').replace("'", "")
    cat = item["category"].lower()
    return f"{cat}|{size}|{desc}"


def _similarity(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, a, b).ratio()


def _merge_items(a_items: list[dict], b_items: list[dict]) -> list[dict]:
    """
    Merge items from Pass A and Pass B.
    Items that match (by description + size + category similarity) are merged.
    Quantity mismatches are flagged in remarks.
    Items unique to one pass are kept as-is.
    """
    if not b_items:
        return a_items
    if not a_items:
        return b_items

    merged = []
    b_matched = set()

    for a_item in a_items:
        a_key = _item_key(a_item)
        best_match_idx = None
        best_score = 0.0

        for i, b_item in enumerate(b_items):
            if i in b_matched:
                continue
            b_key = _item_key(b_item)
            score = _similarity(a_key, b_key)
            if score > best_score:
                best_score = score
                best_match_idx = i

        if best_match_idx is not None and best_score >= _SIMILARITY_THRESHOLD:
            b_item = b_items[best_match_idx]
            b_matched.add(best_match_idx)

            # Merge: prefer Pass A for bbox/confidence, Pass B for description
            merged_item = {**a_item}

            # Flag quantity mismatch
            a_qty = a_item["quantity"]
            b_qty = b_item["quantity"]
            if abs(a_qty - b_qty) > 0.001:
                existing_remarks = merged_item.get("remarks", "") or ""
                mismatch_note = f"qty mismatch: A={a_qty}, B={b_qty}"
                merged_item["remarks"] = f"{existing_remarks}; {mismatch_note}".lstrip("; ")
                # Use the BOM (Pass B) quantity as it's more likely accurate
                merged_item["quantity"] = b_qty
                merged_item["confidence"] = min(
                    merged_item["confidence"], b_item.get("confidence", 0.7)
                ) * 0.9  # slight confidence penalty for mismatch

            # Use BOM description if more detailed
            if len(b_item["description"]) > len(a_item["description"]):
                merged_item["description"] = b_item["description"]

            # Fill in missing spec from BOM
            if not merged_item.get("material_spec") and b_item.get("material_spec"):
                merged_item["material_spec"] = b_item["material_spec"]

            merged.append(merged_item)
        else:
            merged.append(a_item)

    # Add unmatched Pass B items
    for i, b_item in enumerate(b_items):
        if i not in b_matched:
            b_item["remarks"] = (b_item.get("remarks") or "") + " [BOM only]"
            merged.append(b_item)

    return merged


# ── Consumable derivation ─────────────────────────────────────────────────────

def _derive_consumables(items: list[dict]) -> list[dict]:
    """
    Ensure GASKET and BOLT SET items are present.
    Counts flanged joints:
      - Each FLANGE item = 1 joint contribution (pairs assumed in flanged joints)
      - Each VALVE with FLGD end type = 2 joints
    """
    # Count flanges and flanged valves
    flanges = sum(
        int(it["quantity"]) for it in items if it["category"] == "FLANGE"
    )
    flanged_valves = sum(
        int(it["quantity"]) * 2
        for it in items
        if it["category"] == "VALVE" and it.get("end_type") == "FLGD"
    )

    # Estimate joints: assume flanges come in pairs (two flanges = 1 joint)
    # plus valve joints
    flange_joints = max(flanges // 2, flanges)  # if odd, round up
    total_joints = flange_joints + flanged_valves

    if total_joints == 0:
        return items  # No flanged joints, no consumables needed

    # Check if already present
    has_gasket = any(it["category"] == "GASKET" for it in items)
    has_bolt = any(it["category"] == "BOLT" for it in items)

    # Get representative size from flanges or first item
    size = "?"
    for it in items:
        if it["category"] in ("FLANGE", "PIPE", "VALVE"):
            size = it.get("size_nps", "?")
            break

    # Get rating from flanges
    rating = None
    for it in items:
        if it["category"] == "FLANGE" and it.get("schedule_rating"):
            rating = it["schedule_rating"]
            break

    if not has_gasket:
        items.append({
            "source": "derived",
            "item_no": 0,
            "category": "GASKET",
            "description": "Spiral Wound Gasket, SS316/Graphite, ASME B16.20",
            "size_nps": size,
            "schedule_rating": rating or "CL150",
            "material_spec": "SS316 / Graphite",
            "end_type": None,
            "quantity": float(total_joints),
            "unit": "EA",
            "length_m": None,
            "confidence": 0.85,
            "remarks": f"derived from {total_joints} flanged joint(s)",
            "bbox": None,
        })

    if not has_bolt:
        items.append({
            "source": "derived",
            "item_no": 0,
            "category": "BOLT",
            "description": "Stud Bolt with 2 Heavy Hex Nuts, ASTM A193 B7/A194 2H",
            "size_nps": size,
            "schedule_rating": rating or "CL150",
            "material_spec": "ASTM A193 B7 / A194 2H",
            "end_type": None,
            "quantity": float(total_joints),
            "unit": "SET",
            "length_m": None,
            "confidence": 0.85,
            "remarks": f"1 set per flanged joint — derived from {total_joints} joint(s)",
            "bbox": None,
        })

    return items


# ── Pydantic conversion ────────────────────────────────────────────────────────

def _build_mto_items(raw_items: list[dict]) -> list[MTOItem]:
    result = []
    for item in raw_items:
        try:
            bbox = None
            if item.get("bbox") and isinstance(item["bbox"], dict):
                b = item["bbox"]
                try:
                    bbox = BoundingBox(
                        x=float(b.get("x", 0)),
                        y=float(b.get("y", 0)),
                        width=float(b.get("width", 0.05)),
                        height=float(b.get("height", 0.05)),
                    )
                except Exception:
                    bbox = None

            mto_item = MTOItem(
                item_no=item["item_no"],
                category=ItemCategory(item["category"]),
                description=item["description"] or "Unknown",
                size_nps=item["size_nps"] or "?",
                schedule_rating=item.get("schedule_rating"),
                material_spec=item.get("material_spec"),
                end_type=EndType(item["end_type"]) if item.get("end_type") else None,
                quantity=item["quantity"],
                unit=ItemUnit(item["unit"]),
                length_m=item.get("length_m"),
                confidence=item["confidence"],
                remarks=item.get("remarks") or "",
                bbox=bbox,
            )
            result.append(mto_item)
        except Exception:
            continue  # Skip malformed items rather than crash

    return result


# ── Summary computation ────────────────────────────────────────────────────────

def _compute_summary(items: list[MTOItem], field_welds: int) -> Summary:
    total_pipe_length = 0.0
    fittings = 0
    flanges = 0
    valves = 0
    gaskets = 0
    bolt_sets = 0
    low_conf = 0

    for item in items:
        if item.confidence < 0.6:
            low_conf += 1
        if item.category == ItemCategory.PIPE:
            total_pipe_length += item.length_m or 0.0
        elif item.category == ItemCategory.FITTING:
            fittings += int(item.quantity)
        elif item.category == ItemCategory.FLANGE:
            flanges += int(item.quantity)
        elif item.category == ItemCategory.VALVE:
            valves += int(item.quantity)
        elif item.category == ItemCategory.GASKET:
            gaskets += int(item.quantity)
        elif item.category == ItemCategory.BOLT:
            bolt_sets += int(item.quantity)

    return Summary(
        total_pipe_length_m=round(total_pipe_length, 2),
        fittings=fittings,
        flanges=flanges,
        valves=valves,
        gaskets=gaskets,
        bolt_sets=bolt_sets,
        field_welds=max(0, int(field_welds)),
        low_confidence_items=low_conf,
    )
