"""Render Agent-authored JSON; this CLI itself does not call a vision/language model."""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from models.figure_spec import FigureSpec
from renderer.illustrator_renderer import render_figure_spec


def main() -> int:
    """Validate or render one FigureSpec JSON to a unique set of outputs."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("spec", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()
    (ROOT / "logs").mkdir(exist_ok=True)
    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s",
                        handlers=[logging.StreamHandler(), logging.FileHandler(ROOT / "logs" / "illustrator.log", encoding="utf-8")])
    try:
        spec = FigureSpec.parse_raw(args.spec.read_text(encoding="utf-8"))
        if args.validate_only:
            from layout.base import compute_layout
            scene = compute_layout(spec)
            print(f"Valid: mode={spec.mode}; canvas={scene['width']} x {scene['height']} pt")
            return 0
        output = args.output or ROOT / "outputs" / f"{args.spec.stem}_{datetime.now():%Y%m%d_%H%M%S_%f}.ai"
        print(render_figure_spec(spec, output), flush=True)
        return 0
    except Exception:
        logging.exception("Figure render failed")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
