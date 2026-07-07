"""
Mock pipeline — returns a realistic hardcoded MTO.

Used when GEMINI_API_KEY is not set, or in tests.
All confidence values are 0.5 and source='mock' so the UI can show a banner.
"""
from models.mto import (
    BoundingBox, DrawingMeta, EndType, ItemCategory, ItemUnit,
    LineNumberParsed, MTOItem, MTOResult, Summary,
)


def generate_mock_mto(filename: str = "sample.png") -> MTOResult:
    drawing_meta = DrawingMeta(
        drawing_no="ISO-1501-01",
        revision="2",
        line_number='6"-P-1501-A1A-IH',
        line_number_parsed=LineNumberParsed(
            size='6"',
            service="P",
            sequence="1501",
            material_class="A1A",
            insulation="IH",
            raw='6"-P-1501-A1A-IH',
        ),
        nps='6"',
        material_class="A1A",
        service="Process",
        design_pressure="10 barg",
        design_temperature="120 °C",
        confidence=0.5,
    )

    items = [
        MTOItem(
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
            confidence=0.5,
            remarks="mock data",
            bbox=BoundingBox(x=0.1, y=0.2, width=0.4, height=0.05),
        ),
        MTOItem(
            item_no=2,
            category=ItemCategory.FITTING,
            description="Elbow 90 Deg LR, BW, ASME B16.9",
            size_nps='6"',
            schedule_rating="SCH 40",
            material_spec="ASTM A234 WPB",
            end_type=EndType.BW,
            quantity=4,
            unit=ItemUnit.EA,
            confidence=0.5,
            remarks="mock data",
            bbox=BoundingBox(x=0.55, y=0.25, width=0.08, height=0.08),
        ),
        MTOItem(
            item_no=3,
            category=ItemCategory.FLANGE,
            description="Flange, Weld Neck, ASME B16.5",
            size_nps='6"',
            schedule_rating="CL150",
            material_spec="ASTM A105",
            end_type=EndType.BW,
            quantity=2,
            unit=ItemUnit.EA,
            confidence=0.5,
            remarks="mock data",
            bbox=BoundingBox(x=0.65, y=0.4, width=0.06, height=0.08),
        ),
        MTOItem(
            item_no=4,
            category=ItemCategory.VALVE,
            description="Gate Valve, Flanged, ASME B16.10",
            size_nps='6"',
            schedule_rating="CL150",
            material_spec="ASTM A216 WCB",
            end_type=EndType.FLGD,
            quantity=1,
            unit=ItemUnit.EA,
            confidence=0.5,
            remarks="mock data",
            bbox=BoundingBox(x=0.7, y=0.55, width=0.1, height=0.1),
        ),
        MTOItem(
            item_no=5,
            category=ItemCategory.GASKET,
            description="Spiral Wound Gasket, SS316/Graphite, ASME B16.20",
            size_nps='6"',
            schedule_rating="CL150",
            material_spec="SS316/Graphite",
            quantity=2,
            unit=ItemUnit.EA,
            confidence=0.5,
            remarks="derived from flange count — mock data",
        ),
        MTOItem(
            item_no=6,
            category=ItemCategory.BOLT,
            description="Stud Bolt with 2 Heavy Hex Nuts",
            size_nps='6"',
            schedule_rating="CL150",
            material_spec="ASTM A193 B7 / A194 2H",
            quantity=2,
            unit=ItemUnit.SET,
            confidence=0.5,
            remarks="1 set per flanged joint — mock data",
        ),
    ]

    summary = Summary(
        total_pipe_length_m=12.45,
        fittings=4,
        flanges=2,
        valves=1,
        gaskets=2,
        bolt_sets=2,
        field_welds=1,
        low_confidence_items=len(items),  # all are 0.5 in mock
    )

    return MTOResult(
        drawing_meta=drawing_meta,
        items=items,
        summary=summary,
        source="mock",
    )
