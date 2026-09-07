"""Input contract and whole-text-block semantics without Illustrator."""

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from models.figure_spec import FigureSpec
from layout.base import compute_layout


class FigureSpecTests(unittest.TestCase):
    """Malformed or unsupported requests fail before creating any document."""

    def load(self, name: str) -> dict:
        """Read a checked-in example fixture."""
        return json.loads((ROOT / "examples" / "specs" / name).read_text(encoding="utf-8"))

    def test_duplicate_ids_rejected(self) -> None:
        data = self.load("pm25_workflow.json")
        data["edges"][0]["id"] = data["nodes"][0]["id"]
        with self.assertRaises(ValueError):
            FigureSpec.parse_obj(data)

    def test_dangling_edge_rejected(self) -> None:
        data = self.load("pm25_workflow.json")
        data["edges"][0]["target"] = "missing"
        with self.assertRaises(ValueError):
            FigureSpec.parse_obj(data)

    def test_reference_geometry_required(self) -> None:
        data = self.load("reference_demo.json")
        del data["nodes"][0]["position"]
        with self.assertRaises(ValueError):
            FigureSpec.parse_obj(data)

    def test_no_infinite_geometry(self) -> None:
        data = self.load("reference_demo.json")
        data["nodes"][0]["position"]["x"] = float("nan")
        with self.assertRaises(ValueError):
            FigureSpec.parse_obj(data)

    def test_reference_paragraph_preserves_breaks_and_one_node(self) -> None:
        data = self.load("reference_demo.json")
        paragraph = 'First line\nSecond line with "quotes"\n第三行'
        data["nodes"][0]["label"] = paragraph
        scene = compute_layout(FigureSpec.parse_obj(data))
        self.assertEqual(len(scene["nodes"]), 1)
        self.assertEqual(scene["nodes"][0]["label"], paragraph)


if __name__ == "__main__":
    unittest.main()
