"""Render validated FigureSpec data using the same bridge for both entry modes."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from illustrator.com_client import IllustratorClient, IllustratorError, jsx_literal
from illustrator.jsx_builder import JSXBuilder
from layout.base import compute_layout
from models.figure_spec import FigureSpec

LOGGER = logging.getLogger(__name__)


def render_figure_spec(spec: FigureSpec, output: Path) -> dict[str, Any]:
    """Preflight, render to a fresh document, save AI, PNG, spec and object names.

    Failures leave only the new document/partial outputs for inspection. There is
    no automatic rollback or overwrite. Each retry must choose a fresh output.
    """
    output = Path(output).expanduser().resolve()
    if output.suffix.lower() != ".ai":
        raise ValueError("Output must end in .ai")
    paths = {"ai": output, "png": output.with_suffix(".png"),
             "spec": output.with_suffix(".spec.json"), "registry": output.with_suffix(".registry.json"),
             "trace": output.with_suffix(".jsx.log")}
    for path in paths.values():
        if path.exists():
            raise FileExistsError(f"Refusing to overwrite: {path}")
    scene = compute_layout(spec)
    scene["trace_path"] = paths["trace"].as_posix()
    output.parent.mkdir(parents=True, exist_ok=True)
    with paths["spec"].open("x", encoding="utf-8") as stream:
        stream.write(spec.json(ensure_ascii=False, indent=2))
    LOGGER.info("Render FigureSpec mode=%s nodes=%d edges=%d spec=%s", spec.mode, len(spec.nodes), len(spec.edges), paths["spec"])
    with IllustratorClient() as client:
        client.create_document(scene["width"], scene["height"])
        result = client.execute_jsx(JSXBuilder.render_scene(scene))
        if not result.startswith("OK|"):
            raise IllustratorError(f"Unexpected render result: {result}")
        _, count, warnings = result.split("|", 2)
        if warnings:
            LOGGER.warning("Illustrator: %s", warnings)
        # A paragraph is ONE text frame, including all its line breaks. Verify the
        # real Illustrator document, not just the parameters sent to the renderer.
        expected_text = {"SCI_TEXT_" + node["id"]: node["label"].replace("\r\n", "\n").replace("\n", "\r")
                         for node in scene["nodes"] if node["label"]}
        if scene["title"]:
            expected_text["SCI_TITLE_text"] = scene["title"].replace("\r\n", "\n").replace("\n", "\r")
        verify_text = """(function (expected) {
            var frames = app.activeDocument.textFrames, seen = {}, total = 0;
            for (var i = 0; i < frames.length; i++) {
                var frame = frames[i], name = frame.name;
                if (name.indexOf('SCI_') !== 0) continue;
                if (!expected.hasOwnProperty(name) || seen[name] || frame.contents !== expected[name])
                    throw new Error('Text block integrity failed: ' + name);
                seen[name] = true; total++;
            }
            for (var key in expected) {
                if (expected.hasOwnProperty(key) && !seen[key]) throw new Error('Missing text block: ' + key);
            }
            return total;
        })(DATA);""".replace("DATA", jsx_literal(expected_text))
        text_blocks = int(client.execute_jsx(verify_text))
        # Read actual objects back from Illustrator, rather than assuming successful creation.
        object_script = """(function () {
            var rows = [], items = app.activeDocument.pageItems;
            for (var i = 0; i < items.length; i++) {
                var item = items[i];
                if (item.name.indexOf('SCI_') === 0) rows.push(item.name + '\\t' + item.typename);
            }
            return rows.join('\\n');
        }());"""
        observed = dict(row.split("\t", 1) for row in client.execute_jsx(object_script).splitlines())
        registry: dict[str, Any] = {}
        for node in spec.nodes:
            name = "SCI_GROUP_" + node.id
            if observed.get(name) != "GroupItem":
                raise IllustratorError(f"Object verification failed: {name}")
            registry[node.id] = {"illustrator_name": name, "type": "node"}
        for edge in spec.edges:
            name = "SCI_EDGE_" + edge.id
            if observed.get(name) != "GroupItem":
                raise IllustratorError(f"Object verification failed: {name}")
            registry[edge.id] = {"illustrator_name": name, "type": "edge"}
        actual_leaves = sum(kind != "GroupItem" for kind in observed.values())
        if actual_leaves != int(count):
            raise IllustratorError(f"Object count mismatch: {actual_leaves} vs {count}")
        client.save_document(output)
        # PNG preview is the first narrow export interface, verified on Illustrator 2022.
        preview_script = """(function () {
            var file = new File(PATH);
            if (file.exists) throw new Error('Preview already exists');
            var options = new ExportOptionsPNG24();
            options.antiAliasing = true; options.transparency = false;
            options.artBoardClipping = true;
            options.horizontalScale = 150; options.verticalScale = 150;
            app.activeDocument.exportFile(file, ExportType.PNG24, options);
            return file.fsName;
        }());""".replace("PATH", jsx_literal(paths["png"].as_posix()))
        client.execute_jsx(preview_script)
        if not paths["png"].is_file() or paths["png"].stat().st_size == 0:
            raise IllustratorError(f"Preview missing: {paths['png']}")
        report = {"document": str(output), "version": client.get_version(), "mode": spec.mode,
                  "editable_objects": actual_leaves, "editable_text_blocks": text_blocks, "warnings": warnings,
                  "objects": registry, "observed_objects": observed}
    with paths["registry"].open("x", encoding="utf-8") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2)
    return {**{key: str(path) for key, path in paths.items()}, "editable_objects": actual_leaves,
            "editable_text_blocks": text_blocks, "warnings": warnings}
