"""Validated scene descriptions shared by reference reconstruction and creation."""

from __future__ import annotations

from typing import Literal, Optional

try:
    from pydantic.v1 import BaseModel, Field, root_validator, validator
except ImportError:
    from pydantic import BaseModel, Field, root_validator, validator


class SpecModel(BaseModel):
    """Reject misspelled options and non-finite geometry before touching Illustrator."""

    class Config:
        extra = "forbid"
        allow_inf_nan = False


class Position(SpecModel):
    """Top-left-relative position; normalized in reference mode, points otherwise."""

    x: float = Field(ge=0)
    y: float = Field(ge=0)


class TextStyle(SpecModel):
    """Text appearance at final artwork size, in points."""

    font: str = "ArialMT"
    size: float = Field(default=9, ge=7, le=100)
    color: str = "#16324F"

    @validator("color")
    def valid_color(cls, value: str) -> str:
        """Accept only explicit RGB hex colors."""
        if len(value) != 7 or value[0] != "#" or any(c not in "0123456789abcdefABCDEF" for c in value[1:]):
            raise ValueError("Color must be #RRGGBB")
        return value


class StyleSpec(SpecModel):
    """Common, renderer-independent shape styling."""

    fill: Optional[str] = "#E8F1F8"
    stroke: Optional[str] = "#2867A0"
    stroke_width: float = Field(default=1, ge=0, le=10)
    radius: float = Field(default=6, ge=0, le=100)
    text: TextStyle = Field(default_factory=TextStyle)

    @validator("fill", "stroke")
    def valid_color(cls, value: Optional[str]) -> Optional[str]:
        """Validate colors while allowing absent fill or stroke."""
        return TextStyle.valid_color(value) if value is not None else None


class ArrowStyle(SpecModel):
    """Polyline and editable triangular arrowhead appearance."""

    color: str = "#2867A0"
    width: float = Field(default=1, gt=0, le=10)
    head: bool = True
    head_size: float = Field(default=6, ge=2, le=20)

    _color = validator("color", allow_reuse=True)(TextStyle.valid_color.__func__)


class NodeSpec(SpecModel):
    """Logical node; reference reconstruction adds normalized geometry."""

    id: str = Field(regex=r"^[A-Za-z][A-Za-z0-9_-]{0,63}$")
    label: str = Field(default="", max_length=300)
    node_type: Literal["input", "process", "analysis", "model", "result", "annotation"] = "process"
    shape: Literal["rectangle", "rounded_rectangle", "ellipse", "text"] = "rounded_rectangle"
    width: Optional[float] = Field(default=None, gt=0)
    height: Optional[float] = Field(default=None, gt=0)
    position: Optional[Position] = None
    style: Optional[StyleSpec] = None


class EdgeSpec(SpecModel):
    """Semantic connection or a measured polyline in the reference image."""

    id: str = Field(regex=r"^[A-Za-z][A-Za-z0-9_-]{0,63}$")
    source: Optional[str] = None
    target: Optional[str] = None
    points: Optional[list[Position]] = Field(default=None, min_items=2, max_items=100)
    arrow_style: ArrowStyle = Field(default_factory=ArrowStyle)


class CanvasSpec(SpecModel):
    """Optional dimensions in points; creation can size its canvas automatically."""

    width: Optional[float] = Field(default=None, ge=1, le=16383)
    height: Optional[float] = Field(default=None, ge=1, le=16383)
    margin: float = Field(default=40, ge=0, le=500)


class LayoutSpec(SpecModel):
    """First layouts: ordered horizontal/vertical or measured reference geometry."""

    kind: Literal["horizontal", "vertical", "reference"] = "vertical"
    node_width: float = Field(default=160, ge=20, le=1000)
    node_height: float = Field(default=60, ge=20, le=1000)
    spacing: float = Field(default=45, ge=20, le=500)


class FigureSpec(SpecModel):
    """Common entry point; reading images and understanding language belongs to the Agent."""

    schema_version: Literal["0.1"] = "0.1"
    mode: Literal["create", "reconstruct"] = "create"
    figure_type: Literal["workflow", "mechanism", "conceptual", "reference"] = "workflow"
    title: str = Field(default="", max_length=120)
    canvas: CanvasSpec = Field(default_factory=CanvasSpec)
    layout: LayoutSpec = Field(default_factory=LayoutSpec)
    style: StyleSpec = Field(default_factory=StyleSpec)
    nodes: list[NodeSpec] = Field(min_items=1, max_items=100)
    edges: list[EdgeSpec] = Field(default_factory=list, max_items=200)
    source_note: str = Field(default="", max_length=1000)

    @root_validator(skip_on_failure=True)
    def consistent_graph(cls, values: dict) -> dict:
        """Reject ambiguous modes, missing endpoints and unsupported geometry."""
        nodes, edges = values["nodes"], values["edges"]
        ids = [node.id for node in nodes] + [edge.id for edge in edges]
        if len(ids) != len(set(ids)):
            raise ValueError("Node and edge IDs must be globally unique")
        reference = values["mode"] == "reconstruct"
        if reference != (values["layout"].kind == "reference"):
            raise ValueError("reconstruct mode requires reference layout; create mode uses automatic layout")
        if reference and (values["canvas"].width is None or values["canvas"].height is None):
            raise ValueError("Reference mode needs explicit canvas width and height")
        node_ids = {n.id for n in nodes}
        for node in nodes:
            if reference:
                if node.position is None or node.width is None or node.height is None:
                    raise ValueError("Each reference node needs normalized position, width and height")
                if node.position.x + node.width > 1.000001 or node.position.y + node.height > 1.000001:
                    raise ValueError("Reference node must fit within normalized [0, 1] canvas")
            elif node.position is not None:
                raise ValueError("Creation mode computes positions; omit position")
        for edge in edges:
            if reference:
                if edge.points is None or edge.source is not None or edge.target is not None:
                    raise ValueError("Reference edges require points only")
                if any(p.x > 1 or p.y > 1 for p in edge.points):
                    raise ValueError("Reference edge points must be normalized [0, 1]")
            elif edge.points is not None or edge.source not in node_ids or edge.target not in node_ids:
                raise ValueError("Creation edges require valid source and target IDs only")
            elif edge.source == edge.target:
                raise ValueError("Self-loop routing is not supported yet")
        return values
