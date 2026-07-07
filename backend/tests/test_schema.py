"""Tests for Pydantic schema validation."""
import pytest
from pydantic import ValidationError

from models.mto import (
    BoundingBox, DrawingMeta, EndType, ItemCategory, ItemUnit,
    LineNumberParsed, MTOItem, MTOResult, Summary,
)


class TestMTOItem:
    def test_valid_pipe_item(self):
        item = MTOItem(
            item_no=1,
            category=ItemCategory.PIPE,
            description="Pipe, Seamless, BE, ASME B36.10",
            size_nps='6"',
            schedule_rating="SCH 40",
            material_spec="ASTM A106 Gr.B",
            end_type=EndType.BW,
            quantity=1,
            unit=ItemUnit.M,
            length_m=12.45,
            confidence=0.9,
        )
        assert item.category == ItemCategory.PIPE
        assert item.unit == ItemUnit.M
        assert item.length_m == 12.45

    def test_pipe_gets_default_length(self):
        item = MTOItem(
            item_no=1,
            category=ItemCategory.PIPE,
            description="Pipe",
            size_nps='4"',
            quantity=1,
            unit=ItemUnit.M,
            confidence=0.5,
        )
        assert item.length_m == 0.0

    def test_invalid_confidence(self):
        with pytest.raises(ValidationError):
            MTOItem(
                item_no=1,
                category=ItemCategory.FITTING,
                description="Elbow",
                size_nps='6"',
                quantity=2,
                unit=ItemUnit.EA,
                confidence=1.5,  # > 1.0
            )

    def test_fitting_item(self):
        item = MTOItem(
            item_no=2,
            category=ItemCategory.FITTING,
            description="Elbow 90 Deg LR, BW, ASME B16.9",
            size_nps='6"',
            quantity=4,
            unit=ItemUnit.EA,
            confidence=0.88,
        )
        assert item.quantity == 4
        assert item.unit == ItemUnit.EA

    def test_bbox_validation(self):
        item = MTOItem(
            item_no=3,
            category=ItemCategory.VALVE,
            description="Gate Valve",
            size_nps='4"',
            quantity=1,
            unit=ItemUnit.EA,
            confidence=0.85,
            bbox=BoundingBox(x=0.1, y=0.2, width=0.05, height=0.08),
        )
        assert item.bbox is not None
        assert item.bbox.x == 0.1


class TestSummary:
    def test_summary_fields(self):
        s = Summary(
            total_pipe_length_m=12.45,
            fittings=4,
            flanges=2,
            valves=1,
            gaskets=2,
            bolt_sets=2,
            field_welds=1,
            low_confidence_items=0,
        )
        assert s.total_pipe_length_m == 12.45
        assert s.flanges == 2


class TestDrawingMeta:
    def test_line_number_parsed(self):
        meta = DrawingMeta(
            line_number='6"-P-1501-A1A-IH',
            line_number_parsed=LineNumberParsed(
                size='6"', service="P", sequence="1501",
                material_class="A1A", insulation="IH",
            ),
            confidence=0.85,
        )
        assert meta.line_number_parsed.service == "P"

    def test_optional_fields(self):
        meta = DrawingMeta(confidence=0.5)
        assert meta.drawing_no is None
        assert meta.revision is None


class TestMTOResult:
    def test_full_result(self):
        from services.mock_pipeline import generate_mock_mto
        result = generate_mock_mto("test.png")
        assert result.source == "mock"
        assert len(result.items) > 0
        assert result.summary.total_pipe_length_m > 0
