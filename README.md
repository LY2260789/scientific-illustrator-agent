# Scientific Illustrator Agent

**Editable scientific figures in Adobe Illustrator, driven by structured specifications.**

Scientific Illustrator Agent connects AI agents to desktop Adobe Illustrator through Python, Windows COM and ExtendScript. An agent interprets a drawing request or reference image, creates a validated FigureSpec, and renders native vector objects with editable text.

**Status: experimental v0.3 — installable CLI Skill.** Includes sequential element construction, optional multi-cursor swarm presentations, direct generation, speed presets and GIF replay. The core renderer and the SOC cursor presentation have been exercised on Illustrator 2022.

## Capabilities

| Capability | Current support |
| --- | --- |
| Natural-language workflow design | Agent creates FigureSpec; horizontal and vertical layout |
| Simple reference reconstruction | Agent interprets image; normalized positions in FigureSpec |
| Editable graphics | Rectangles, rounded rectangles, ellipses, text, lines and arrows |
| Text integrity | One text block per label, including multiline labels; contents checked after rendering |
| Object identification | Named objects and an exported registry |
| Deliverables | Native AI document, PNG preview, specification and rendering trace |
| Sequential element construction（逐元素叠加） | Add editable SVG graphical units in order, with adjustable pacing and optional GIF replay |
| Multi-cursor swarm presentation（多鼠标集群，可选） | 2–30 colored cursors accompany spatial batches of real vector objects |
| MCP, PDF/SVG export, automated visual QC | Planned |

The Python CLI does not contain a language model or an OCR service. Image interpretation and specification authoring are performed by the host agent. Complex illustration reconstruction and recovery of original chart data are outside the current FigureSpec renderer's scope.

## Architecture

```mermaid
flowchart TD
    A[User idea or reference image] --> B[AI agent + Skill]
    B --> C[FigureSpec JSON]
    C --> D[Pydantic validation + layout]
    D --> E[Python renderer]
    E --> F[Windows COM]
    F --> G[ExtendScript]
    G --> H[Adobe Illustrator: editable vectors and text]
    H --> I[AI document + PNG preview]
```

The intermediate specification keeps automatic workflow placement in the layout engine. COM serves as the bridge to Illustrator; reusable JSX performs document operations.

## Requirements

- Windows 10/11 with an interactive desktop session.
- A licensed, locally installed Adobe Illustrator, with initial setup completed.
- Python 3.9 or later, pywin32, Pydantic and Pillow.
- An AI agent capable of reading this Skill and running local Python commands, when using natural-language input.

**Verified environment:** Illustrator 2022 (26.3.1), Python 3.9.13. Compatibility with Illustrator 2020 is a design target, not a tested guarantee. This project does not depend on Adobe's newer MCP integrations.

## Installation

### Python engine

```powershell
git clone https://github.com/LY2260789/scientific-illustrator-agent.git
cd scientific-illustrator-agent
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### Agent Skill

The repository root contains [SKILL.md](SKILL.md) and its runtime resources. Install the **whole repository**, not only the Markdown file.

In Codex, ask:

> Install the Skill from https://github.com/LY2260789/scientific-illustrator-agent, using the repository root as the skill directory.

For manual installation, place the repository contents in `~/.codex/skills/scientific-illustrator-agent/`, then install the Python dependencies there. Other agents need a compatible Skill loader and permission to execute local commands. The package provides a CLI Skill with local COM execution.

## Quick start

Run the following from the repository root using the virtual environment created above.

### Check Illustrator

```powershell
.\.venv\Scripts\python.exe examples/hello_illustrator.py --connect-only
```

Expected output includes the Illustrator version and `Illustrator connected successfully`. COM may launch Illustrator automatically; bringing its window to the foreground is not guaranteed.

### Create a first document

```powershell
.\.venv\Scripts\python.exe examples/hello_illustrator.py --output outputs/hello.ai
```

Creates a new document with a blue rounded rectangle, editable text and a line, then saves an AI file.

### Render a scientific workflow

```powershell
.\.venv\Scripts\python.exe examples/render_spec.py examples/specs/pm25_workflow.json --validate-only
.\.venv\Scripts\python.exe examples/render_spec.py examples/specs/pm25_workflow.json --output outputs/workflow.ai
```

Use a new output name for subsequent runs: existing outputs are intentionally not overwritten.

### Use natural language

Example requests for an agent with this Skill installed:

> Create a vertical workflow in Illustrator: data input, preprocessing, analysis, evaluation and results. Keep each label editable.

> Reconstruct this simple reference diagram with editable shapes and one text frame per original text block.

The agent should read the schema, write and validate a FigureSpec, render it, and inspect the PNG preview. See [input modes](docs/input_modes.md), [the schema](src/models/figure_spec.py), and [example specifications](examples/specs).

### Sequential element construction（逐元素叠加）

Watch an editable figure build up in the source order. Illustrator adds a real
graphical unit at each step. A unit is one top-level SVG shape or group and may
contain several paths and a complete text block. `--batch-size 1` refreshes after
each unit. Larger batches add several units at each refresh.

```powershell
.\.venv\Scripts\python.exe examples/progressive_svg.py --source-svg examples/specs/progressive_demo.svg --output-dir outputs/sequential_01 --mode progressive --batch-size 1 --duration 30 --start-delay 5 --live-only
```

The command saves `progressive.ai` and `final.png`. Omit `--live-only` to also
export intermediate PNG frames and a `build.gif` replay. Whole gradient-filled
paths stay together as graphical units. Timing and supported SVG features are
described in the progressive construction guide. [Sequential drawing options](docs/progressive_svg.md)

### Multi-cursor swarm presentation（多鼠标集群，可选）

Open and maximize Illustrator, then run the public SOC reconstruction example.

```powershell
.\.venv\Scripts\python.exe examples/swarm_draw.py --scene-json examples/soc_graphical_abstract/scene.json --output-dir outputs/soc_swarm_01 --cursors 12 --duration 40 --start-delay 5
```

The canvas aligns automatically. Several regions advance together while colored
cursors follow their primitives. A single COM worker submits spatial drawing
batches, and a local Tk window animates the cursors. `--cursors` selects the
presentation cursor count, with `--agents` accepted as an alias. The standard
workflow and progressive SVG commands remain available through their existing
entry points.

The scene and JSX renderer are loaded once. The SOC case uses 572 objects,
including 11 native gradient fills. Each colored ribbon is one complete path.
Small index-only COM calls draw the spatial batches, followed by full object
and text verification before saving.

![Editable SOC reconstruction](examples/soc_graphical_abstract/preview.png)

The case includes 512 paths and 60 complete editable text blocks. Curves and
decorative textures are visual approximations. See the [case and replay commands](examples/soc_graphical_abstract/README.md) and [cursor presentation guide](docs/swarm_demo.md).

The case also includes the original reference PNG at 3180 × 2184 pixels,
copied byte-for-byte from the supplied source. [Download the original-resolution reference](examples/soc_graphical_abstract/reference.png?raw=true)

### Execute generated commands through COM

Native scene runs emit `commands.jsx`. From a Python session with pywin32,
use the absolute path to the generated file.

```python
import win32com.client

app = win32com.client.Dispatch("Illustrator.Application")
app.DoJavaScriptFile(r"C:\work\scientific-illustrator-agent\outputs\soc_swarm_01\commands.jsx")
```

`DoJavaScriptFile` creates the editable artwork in a new document. The Python
`swarm_draw.py` entry point also runs the desktop cursor animation and saves AI
and PNG outputs. Short scripts can be submitted with `app.DoJavaScript(...)`.

## Outputs and document handling

For optional progressive drawing of existing vector SVG artwork, see [progressive construction](docs/progressive_svg.md). The command supports `--mode progressive --duration 30` or `--mode instant`; both save editable AI and a PNG preview. GIF recording is optional. This entry point does not trace bitmap images.

Each FigureSpec render produces:

- `.ai`: native Illustrator document.
- `.png`: preview exported from Illustrator.
- `.spec.json`: the input specification.
- `.registry.json`: observed object names, text counts and warnings.
- `.jsx.log`: rendering trace for troubleshooting.

Rendering creates a new document and checks text contents and object counts. It does not adopt the user's existing document for editing. There is no transactional rollback: a failed operation can leave a partial new document or partial output files for inspection. The renderer does not automatically close Illustrator or retry failed mutations.

The public SOC reconstruction scene and its exported preview are included under
`examples/soc_graphical_abstract/`. Other private research examples, output files
and runtime logs are excluded from this repository.

## Development and validation

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests
```

The current suite contains 29 offline tests covering the COM wrapper,
specification validation, layout, SVG input validation, cursor planning,
alignment and cancellation. The complete SOC cursor run was also checked in
Illustrator 2022, including actual object names, counts and text contents.

```text
SKILL.md              Agent workflow and operational guidance
src/illustrator/      COM bridge, JSX builder and drawing scripts
src/models/           FigureSpec validation
src/layout/           Layout computation
src/renderer/         Document rendering and output verification
examples/             Connection demo and generic specifications
tests/                Offline tests and manual connection entry point
docs/                 Input modes and development notes
```

## Troubleshooting

| Symptom | Suggested check |
| --- | --- |
| Dispatch fails or COM is not registered | Confirm local Illustrator installation; complete first-launch dialogs; repair the installation if necessary. |
| Illustrator cannot start / `0x80080005` | Try a normal interactive desktop terminal and inspect pending application dialogs; a restricted execution environment can block desktop COM. |
| COM reports Illustrator is busy | Finish modal dialogs and wait for the application to become idle before a new operation. |
| DoJavaScript or JSX error | Inspect the exception and rendering trace; ExtendScript uses legacy syntax and API availability varies by version. |
| Native application error / `0x80010105` | Preserve any open work, recover Illustrator, then run the connection check before attempting a new render. |
| Missing characters | Choose an installed font that supports the required language; keep JSON and logs encoded as UTF-8. |
| Save or export fails | Check the output directory, `.ai` extension and existing files; quote paths containing spaces. |

A native crash occurred during early text-property experiments. The simplified renderer subsequently passed local integration checks, but the root cause was not established. The project remains experimental.

## Roadmap

- Structured MCP tools backed by the existing renderer.
- Extend progressive rendering to more input formats and layouts.
- Broader scientific primitives and graph routing.
- Additional export formats and object editing operations.
- Geometry checks and a preview-driven visual review loop.

## Contributing

Issues with minimal specifications and reproducible steps are welcome. Include Windows, Python and Illustrator versions, expected behavior and relevant error messages. Remove confidential research content and credentials before sharing logs or reference files.

No open-source license has been selected yet. Public repository visibility does not itself grant a license to redistribute or commercially reuse the code.

## References

- [Adobe Illustrator scripting documentation](https://helpx.adobe.com/illustrator/using/scripting.html)
- [Skill entry point](SKILL.md)
- [Input modes and text preservation](docs/input_modes.md)
