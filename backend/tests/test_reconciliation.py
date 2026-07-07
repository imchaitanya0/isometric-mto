"""Tests for the reconciliation layer."""
import pytest

from services.reconciliation import (
    _derive_consumables,
    _merge_items,
    _normalise_item,
    reconcile,
)


def make_item(category: str, description: str, size: str = '6"', qty: float = 1.0, **kw) -> dict:
    return {
        "source": "a",
        "item_no": 0,
        "category": category,
        "description": description,
        "size_nps": size,
        "schedule_rating": "SCH 40",
        "material_spec": "ASTM A234 WPB",
        "end_type": "BW",
        "quantity": qty,
        "unit": "M" if category == "PIPE" else "EA",
        "length_m": 12.45 if category == "PIPE" else None,
        "confidence": 0.85,
        "remarks": "",
        "bbox": None,
        **kw,
    }


class TestNormaliseItem:
    def test_category_normalised(self):
        raw = {"category": "fittings", "description": "Elbow", "size_nps": '6"',
               "quantity": 2, "unit": "EA"}
        item = _normalise_item(raw, "a")
        assert item["category"] == "FITTING"

    def test_unit_pipe(self):
        raw = {"category": "PIPE", "description": "Pipe", "size_nps": '6"',
               "quantity": 1, "unit": "MTR"}
        item = _normalise_item(raw, "a")
        assert item["unit"] == "M"

    def test_quantity_default(self):
        raw = {"category": "FLANGE", "description": "Flange", "size_nps": '4"'}
        item = _normalise_item(raw, "b")
        assert item["quantity"] == 1.0


class TestMergeItems:
    def test_identical_items_merged(self):
        a = [make_item("FITTING", "Elbow 90 LR, BW, ASME B16.9", qty=4)]
        b = [make_item("FITTING", "Elbow 90 LR, BW, ASME B16.9", qty=4, source="b")]
        merged = _merge_items(a, b)
        assert len(merged) == 1
        assert merged[0]["quantity"] == 4

    def test_qty_mismatch_flagged(self):
        a = [make_item("FITTING", "Elbow 90 LR, BW, ASME B16.9", qty=4)]
        b = [make_item("FITTING", "Elbow 90 LR, BW, ASME B16.9", qty=3, source="b")]
        merged = _merge_items(a, b)
        assert len(merged) == 1
        assert "qty mismatch" in merged[0]["remarks"]
        # BOM qty (pass B) should win
        assert merged[0]["quantity"] == 3

    def test_unmatched_b_item_appended(self):
        a = [make_item("PIPE", "Pipe, Seamless", qty=1)]
        b = [make_item("VALVE", "Gate Valve, Flanged", source="b")]
        merged = _merge_items(a, b)
        assert len(merged) == 2
        cats = {m["category"] for m in merged}
        assert "PIPE" in cats
        assert "VALVE" in cats


class TestDeriveConsumables:
    def test_gasket_and_bolt_derived_from_flanges(self):
        items = [
            make_item("PIPE", "Pipe", qty=1),
            make_item("FLANGE", "Weld Neck Flange", qty=2, end_type="BW"),
        ]
        result = _derive_consumables(items)
        cats = [i["category"] for i in result]
        assert "GASKET" in cats
        assert "BOLT" in cats

    def test_no_consumables_when_no_flanges(self):
        items = [make_item("PIPE", "Pipe", qty=1)]
        result = _derive_consumables(items)
        cats = [i["category"] for i in result]
        assert "GASKET" not in cats
        assert "BOLT" not in cats

    def test_existing_gasket_not_duplicated(self):
        items = [
            make_item("FLANGE", "Flange", qty=2),
            make_item("GASKET", "Spiral Wound Gasket", qty=1),
        ]
        result = _derive_consumables(items)
        gaskets = [i for i in result if i["category"] == "GASKET"]
        assert len(gaskets) == 1  # Not duplicated


class TestReconcile:
    def test_full_reconcile(self):
        pass_a = {
            "drawing_meta": {
                "drawing_no": "ISO-1501-01",
                "revision": "2",
                "line_number": '6"-P-1501-A1A-IH',
                "confidence": 0.85,
            },
            "items": [
                {
                    "item_no": 1, "category": "PIPE",
                    "description": "Pipe, Seamless, BE, ASME B36.10",
                    "size_nps": '6"', "schedule_rating": "SCH 40",
                    "material_spec": "ASTM A106 Gr.B", "end_type": "BW",
                    "quantity": 1, "unit": "M", "length_m": 12.45,
                    "confidence": 0.9, "remarks": "",
                    "bbox": {"x": 0.1, "y": 0.2, "width": 0.4, "height": 0.05},
                },
                {
                    "item_no": 2, "category": "FLANGE",
                    "description": "Weld Neck Flange, ASME B16.5",
                    "size_nps": '6"', "schedule_rating": "CL150",
                    "material_spec": "ASTM A105", "end_type": "BW",
                    "quantity": 2, "unit": "EA", "confidence": 0.85,
                },
            ],
            "field_welds": 1,
        }
        pass_b = {"bom_rows": [], "confidence": 0.0}
        ocr_meta = {"drawing_no": None, "revision": None, "line_number": None, "confidence": 0.0}

        meta, items, summary = reconcile(pass_a, pass_b, ocr_meta)

        assert meta.drawing_no == "ISO-1501-01"
        assert meta.line_number_parsed.service == "P"
        assert summary.total_pipe_length_m == 12.45
        assert summary.flanges == 2
        # Gaskets and bolts should be derived
        cats = {i.category.value for i in items}
        assert "GASKET" in cats
        assert "BOLT" in cats
        assert summary.field_welds == 1
