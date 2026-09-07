"""Geometry invariants for the two entry modes."""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from models.figure_spec import FigureSpec
from layout.base import compute_layout


class LayoutTests(unittest.TestCase):
    """Check spacing, attachment, proportional scaling and refusal to clip."""

    def workflow(self) -> FigureSpec:
        """Load the natural-language-derived workflow fixture."""
        return FigureSpec.parse_raw((ROOT / "examples/specs/pm25_workflow.json").read_text(encoding="utf-8"))

    def test_vertical_spacing_and_edge_attachment(self) -> None:
        spec = self.workflow()
        scene = compute_layout(spec)
        for left, right in zip(scene["nodes"], scene["nodes"][1:]):
            self.assertAlmostEqual(right["y"] - (left["y"] + left["height"]), spec.layout.spacing)
        for index, edge in enumerate(scene["edges"]):
            self.assertAlmostEqual(edge["points"][0][1], scene["nodes"][index]["y"] + scene["nodes"][index]["height"])
            self.assertAlmostEqual(edge["points"][-1][1], scene["nodes"][index + 1]["y"])

    def test_horizontal_variable_sizes_do_not_overlap(self) -> None:
        spec = self.workflow()
        spec.layout.kind = "horizontal"
        spec.nodes[0].width = 250
        scene = compute_layout(spec)
        for left, right in zip(scene["nodes"], scene["nodes"][1:]):
            self.assertGreaterEqual(right["x"] - left["x"] - left["width"], spec.layout.spacing)

    def test_reference_scaling(self) -> None:
        spec = FigureSpec.parse_raw((ROOT / "examples/specs/reference_demo.json").read_text(encoding="utf-8"))
        first = compute_layout(spec)
        spec.canvas.width *= 2
        spec.canvas.height *= 2
        second = compute_layout(spec)
        for key in ("x", "y", "width", "height"):
            self.assertAlmostEqual(second["nodes"][0][key], first["nodes"][0][key] * 2)

    def test_clipped_canvas_rejected(self) -> None:
        spec = self.workflow()
        spec.canvas.height = 80
        with self.assertRaises(ValueError):
            compute_layout(spec)

    def test_skip_edge_rejected_instead_of_crossing_node(self) -> None:
        spec = self.workflow()
        spec.edges[0].target = "transport"
        with self.assertRaises(ValueError):
            compute_layout(spec)


if __name__ == "__main__":
    unittest.main()
