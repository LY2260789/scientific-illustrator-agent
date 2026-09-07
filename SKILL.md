---
name: scientific-illustrator-agent
description: Create editable scientific workflow diagrams in desktop Adobe Illustrator from natural-language ideas or simple reference images, using a bundled Python FigureSpec renderer and Windows COM. Use when the user wants Illustrator vector objects and editable text rather than a raster image.
---

# Scientific Illustrator Agent

This skill bundles the Python engine beside this file. Resolve all relative paths below against this skill directory, not the user's working directory. Windows and locally installed Illustrator are required. Illustrator 2022 was tested; 2020 compatibility is intended but not verified. This is a CLI skill, not an MCP server.

## Prepare

Use an available Windows Python 3.9+ with pywin32, Pydantic and Pillow. If dependencies are missing, create a local virtual environment and install `requirements.txt`; do not replace the user's global Python packages. See `README.md` for installation and COM troubleshooting.

Run `python "<skill-directory>/examples/hello_illustrator.py" --connect-only` to check Illustrator. COM Dispatch can start Illustrator automatically. This does not guarantee the window is foreground. Never terminate Illustrator or repeatedly retry a failed mutation.

## Draw

1. Extract concepts, labels and relationships from the user's idea or reference. Read `docs/input_modes.md`, `src/models/figure_spec.py` and the relevant JSON under `examples/specs/` for the actual supported schema.
2. Write FigureSpec JSON to the user's output directory. For ideas use `mode: create` and horizontal or vertical layout; let the layout engine compute positions. For references use `mode: reconstruct` with normalized positions. Preserve uncertain text as a question or explicit uncertainty rather than inventing scientific content.
3. Keep one conceptual text block in one label, including embedded newlines; do not split words or lines into independent text objects. Use consistent semantic colors, generous whitespace and legible fonts. Prefer short labels and simple arrow topology.
4. Validate: `python "<skill-directory>/examples/render_spec.py" "<spec.json>" --validate-only`.
5. Render: `python "<skill-directory>/examples/render_spec.py" "<spec.json>" --output "<new-output.ai>"`. The renderer creates a new document and refuses existing output files. Preserve other open documents.
6. Inspect the exported PNG, report warnings and confirm editable object/text counts from the renderer. Revise the specification into a fresh output if needed. Deliver the AI and PNG paths.

## Scope and limitations

The CLI supports basic nodes, text and arrows, AI saving and PNG export. It does not call a language or vision model itself: the agent interprets the request and creates the spec. Do not claim pixel-exact reconstruction or original numerical data from a screenshot. Complex branched routing, full visual QC, PDF/SVG export and MCP are not implemented in this CLI.

The bundled `src/illustrator/jsx/artwork.jsx` has incremental drawing support, but a generic speed-controlled CLI is not yet included. If asked for slow live demonstrations, explain this limitation instead of passing nonexistent speed flags. Private research examples are not part of this skill.
