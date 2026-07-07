"""
Pydantic schemas for the MTO data model.

These mirror the JSON schema from the assessment spec exactly.
The frontend's Zod models will be generated to match these.
"""
from __future__ import annotations

import re
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator, model_validator


# ── Enumerations ─────────────────────────────────────────────────────────────

class ItemCategory(str, Enum):
    PIPE = "PIPE"
    FITTING = "FITTING"
    FLANGE = "FLANGE"
    VALVE = "VALVE"
    GASKET = "GASKET"
    BOLT = "BOLT"
    SUPPORT = "SUPPORT"
    INSTRUMENT = "INSTRUMENT"


class ItemUnit(str, Enum):
    M = "M"       # metres — for pipe length
    EA = "EA"     # each — for discrete items
    SET = "SET"   # bolt+nut set per flanged joint
    NO = "NO"     # alternate for EA


class EndType(str, Enum):
    BW = "BW"       # butt-weld
    SW = "SW"       # socket-weld
    THD = "THD"     # threaded
    FLGD = "FLGD"   # flanged
    PE = "PE"       # plain end
    BE = "BE"       # beveled end


# ── Sub-models ────────────────────────────────────────────────────────────────

class BoundingBox(BaseModel):
    """Normalized bounding box (0.0–1.0 relative to image dimensions)."""
    x: float = Field(ge=0.0, le=1.0)
    y: float = Field(ge=0.0, le=1.0)
    width: float = Field(ge=0.0, le=1.0)
    height: float = Field(ge=0.0, le=1.0)


class LineNumberParsed(BaseModel):
    """Decoded parts of a piping line number like 6\"-P-1501-A1A-IH."""
    size: Optional[str] = None           # e.g. "6\""
    service: Optional[str] = None        # e.g. "P" (process)
    sequence: Optional[str] = None       # e.g. "1501"
    material_class: Optional[str] = None # e.g. "A1A"
    insulation: Optional[str] = None     # e.g. "IH"
    raw: Optional[str] = None            # original unparsed string


class DrawingMeta(BaseModel):
    """Metadata extracted from the title block of the isometric drawing."""
    drawing_no: Optional[str] = None
    revision: Optional[str] = None
    line_number: Optional[str] = None
    line_number_parsed: Optional[LineNumberParsed] = None
    nps: Optional[str] = None            # Nominal Pipe Size
    material_class: Optional[str] = None
    service: Optional[str] = None
    design_pressure: Optional[str] = None
    design_temperature: Optional[str] = None
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)


class MTOItem(BaseModel):
    """One row in the Material Take-Off table."""
    item_no: int = Field(ge=1)
    category: ItemCategory
    description: str = Field(min_length=1)
    size_nps: str  # e.g. "6\"" or "6\"x4\""
    schedule_rating: Optional[str] = None  # e.g. "SCH 40" / "CL150"
    material_spec: Optional[str] = None    # e.g. "ASTM A106 Gr.B"
    end_type: Optional[EndType] = None
    quantity: float = Field(ge=0)
    unit: ItemUnit
    length_m: Optional[float] = Field(default=None, ge=0)
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)
    remarks: Optional[str] = ""
    bbox: Optional[BoundingBox] = None  # For SVG overlay

    @field_validator("size_nps")
    @classmethod
    def validate_size_nps(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("size_nps cannot be empty")
        return v

    @model_validator(mode="after")
    def validate_pipe_has_length(self) -> "MTOItem":
        if self.category == ItemCategory.PIPE and self.length_m is None:
            # Default to 0 rather than raising — AI may not always provide length
            self.length_m = 0.0
        if self.category != ItemCategory.PIPE and self.unit == ItemUnit.M:
            # Non-pipe items should not use M unit
            self.unit = ItemUnit.EA
        return self


class Summary(BaseModel):
    """Aggregated totals across all MTO items."""
    total_pipe_length_m: float = Field(default=0.0, ge=0)
    fittings: int = Field(default=0, ge=0)
    flanges: int = Field(default=0, ge=0)
    valves: int = Field(default=0, ge=0)
    gaskets: int = Field(default=0, ge=0)
    bolt_sets: int = Field(default=0, ge=0)
    field_welds: int = Field(default=0, ge=0)
    low_confidence_items: int = Field(default=0, ge=0)  # confidence < 0.6


class MTOResult(BaseModel):
    """The complete MTO result returned to the frontend."""
    drawing_meta: DrawingMeta
    items: list[MTOItem]
    summary: Summary
    source: str = Field(default="ai")  # "ai" | "mock"
    processing_time_s: Optional[float] = None


class JobStatusResponse(BaseModel):
    """Response from GET /api/mto/{job_id}."""
    job_id: str
    status: str  # "processing" | "completed" | "failed"
    result: Optional[MTOResult] = None
    error: Optional[str] = None
    filename: Optional[str] = None
