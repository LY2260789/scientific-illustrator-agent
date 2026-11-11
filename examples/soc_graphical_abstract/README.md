# SOC graphical abstract reconstruction

This example rebuilds a reference graphical abstract from editable rectangles,
ellipses, paths and complete text blocks. The reference combines meteorological
normalization, random forest diagrams, SHAP calibration and a GAM panel.

## Original reference

![Original SOC reference](reference.png)

The reference PNG is 3180 × 2184 pixels and 1,028,017 bytes. It is copied
byte-for-byte from the source supplied by the project owner. The file checksum
is recorded below. [Download the original-resolution PNG](reference.png?raw=true)

The source filename is `SOC定量（图表摘要）-v8.png`. Its SHA-256 checksum is
`06fa5a54016a4d0ce0c2c306f51adb2aebd8271c8f077e1c9e840e4f11acca4e`.

## Editable reconstruction

![SOC vector reconstruction](preview.png)

`scene.json` contains 553 primitives, including 60 text blocks, 11 native
Illustrator gradient fills and 19 native endpoint arrows. Each connecting ribbon
is a complete path with editable gradient stops. Each arrow is one open path
using Illustrator's filled triangular preset 7, with per-arrow scaling chosen
to approximate the reference. Arrowheads, stroke width and endpoint settings
remain editable in the Stroke panel. The published
scene and preview are shared by the project owner as a drawing demonstration.
The bottom background fades upward from pale blue at the lower edge to white.
The time-series curves, response curves and decorative textures were visually
approximated. The example demonstrates geometry reconstruction and editable
rendering, with scientific labels retained from the reference.

The Skill offers sequential element construction and an optional multi-cursor
swarm presentation. Sequential construction adds SVG graphical units in order,
with speed controls and optional GIF replay. The command below uses the native
SOC primitive scene for the multi-cursor presentation. [Sequential construction guide](../../docs/progressive_svg.md)

## Run the multi-cursor effect

From the repository root on Windows with Illustrator open, use a fresh output
directory for each run.

```powershell
python examples/swarm_draw.py --scene-json examples/soc_graphical_abstract/scene.json --output-dir outputs/soc_swarm_01 --cursors 12 --duration 40 --start-delay 5
```

Illustrator creates a new document and fits the artboard. The program calculates
the screen mapping from the native canvas and document view, then draws spatial
batches while colored cursors follow their elements. Keep the view fixed while
recording. Esc cancels between batches.

The output directory contains `swarm.ai`, `final.png`, `scene.json`,
`commands.jsx`, `process.json` and `process.log`. Final verification checks actual
primitive names, counts, text contents and the presence of raster/placed items.

## COM calls

The Python entry point connects through
`win32com.client.Dispatch("Illustrator.Application")`. It loads the scene and
JSX renderer once through `DoJavaScript`, followed by calls shaped like this.

```javascript
$.global["SCI_SWARM_<session-id>"].draw([5, 42, 108]);
```

The array contains indices into the cached primitive scene. Each call creates
the selected native objects and redraws the document. One COM worker submits
these batches while the local Python overlay animates multiple cursors.

For replay from a standalone Python process, point to the generated command file.

```python
from pathlib import Path
import win32com.client

command_file = Path("outputs/soc_swarm_01/commands.jsx").resolve()
app = win32com.client.Dispatch("Illustrator.Application")
result = app.DoJavaScriptFile(str(command_file))
print(result)
```

The standalone JSX creates a new editable document. The `swarm_draw.py` command
also drives the colored desktop cursors and saves the outputs.

To generate command files and validate the scene without starting Illustrator,
use the following command with a fresh directory.

```powershell
python examples/swarm_draw.py --scene-json examples/soc_graphical_abstract/scene.json --output-dir outputs/soc_commands_01 --validate-only
```

## Observed run

The tested run used Windows, Python 3.9 and Illustrator 2022 version 26.3.1.
It produced 493 paths, including 11 verified native gradient fills and 19 native
endpoint arrows, and 60 complete text frames, with zero rendering warnings.
Construction took 26.5 seconds with a 15-second animation setting. Import,
application startup and saving require additional time depending on the machine.
