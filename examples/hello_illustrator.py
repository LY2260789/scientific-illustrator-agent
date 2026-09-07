"""Run milestones 1-2 on a Windows desktop with local Illustrator installed."""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, Sequence

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from illustrator.com_client import IllustratorClient  # noqa: E402


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Connect, create fresh editable artwork, verify objects, then save AI."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--connect-only", action="store_true", help="Read version and probe JSX without creating artwork")
    parser.add_argument("--output", type=Path, help="New .ai file; existing files are never overwritten")
    parser.add_argument("--debug", action="store_true", help="Include generated JSX in local logs")
    args = parser.parse_args(argv)
    log_dir = ROOT / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[logging.StreamHandler(), logging.FileHandler(log_dir / "illustrator.log", encoding="utf-8")],
    )
    output = args.output or ROOT / "outputs" / f"hello_illustrator_{datetime.now():%Y%m%d_%H%M%S_%f}.ai"
    try:
        if not args.connect_only:
            if output.suffix.lower() != ".ai":
                raise ValueError("--output must end in .ai")
            if output.exists():
                raise FileExistsError(f"Refusing to overwrite: {output}")
        with IllustratorClient() as client:
            print(f"Illustrator version: {client.get_version()}", flush=True)
            print(f"JSX version: {client.health_check()['jsx_version']}", flush=True)
            if args.connect_only:
                print("Illustrator connected successfully", flush=True)
                return 0
            client.create_document()
            script = (ROOT / "src" / "illustrator" / "jsx" / "hello.jsx").read_text(encoding="utf-8")
            print(client.execute_jsx(script), flush=True)
            count = client.execute_jsx("app.activeDocument.layers.getByName('SCI_DEMO').pageItems.length;")
            if count != "3":
                raise RuntimeError(f"Expected 3 editable objects, received {count}")
            saved = client.save_document(output)
            print("Illustrator connected successfully", flush=True)
            print(f"Saved: {saved}", flush=True)
        return 0
    except Exception:
        logging.getLogger(__name__).exception("Demo failed. Any newly created document is left open for inspection.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
