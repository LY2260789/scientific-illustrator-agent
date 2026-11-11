# Sequential element construction（逐元素叠加）

`examples/progressive_svg.py` builds an editable SVG figure in a fresh Illustrator
document, adding graphical units in their source order. Each step adds real
vector paths and text to the growing figure. `--batch-size 1` shows one unit at a
time, and larger batches control how many units appear at each refresh.

A unit is a top-level SVG shape or group. A group may contain several paths and
a complete text block. A gradient-filled ribbon should be represented as one
complete path so that it appears together with its native gradient.

The optional multi-cursor mode advances spatial regions in batches while colored
cursors follow their elements. Its entry point and controls are described in the
cursor guide. [Multi-cursor swarm presentation](swarm_demo.md)

## Live demonstration, approximately 30 seconds

```powershell
python examples/progressive_svg.py --source-svg examples/specs/progressive_demo.svg --output-dir outputs/demo_live_01 --mode progressive --duration 30 --batch-size 1 --start-delay 10 --live-only
```

For detailed artwork with many top-level color groups, use `--batch-size 8` or `24`. Every batch adds real editable objects to the destination document. The original SVG is opened as a temporary source first; that document is closed after copying, and the destination is left open.

## Generate directly

```powershell
python examples/progressive_svg.py --source-svg examples/specs/progressive_demo.svg --output-dir outputs/demo_instant_01 --mode instant
```

Instant mode uses the same vectors and output verification, without staged drawing pauses or GIF recording. Importing and saving complex artwork still take time.

## Save a replay GIF

Omit `--live-only` in progressive mode. A PNG frame is exported after each batch; these frames form `build.gif`. `--frame-ms 1800` displays each intermediate frame for 1.8 seconds. Playback timing does not change Illustrator rendering speed.

| Option | Meaning |
| --- | --- |
| `--source-svg` | Existing vector SVG file; no embedded bitmap |
| `--output-dir` | New directory; existing directories are rejected |
| `--mode progressive` | Add actual graphical groups in stages (default) |
| `--mode instant` | Add all groups with one final redraw; skip GIF |
| `--duration 30` | Target 30 seconds for cumulative construction |
| `--delay-ms 80` | Alternative: pause 80 ms after each graphical group |
| `--speed 快速` / `正常` / `慢速` | Alternative presets: 0 / 80 / 300 ms per group |
| `--batch-size 8` | Groups per batch; controls refresh steps in duration mode |
| `--start-delay 10` | Preparation time after the blank destination opens |
| `--live-only` | Skip intermediate PNG/GIF recording |
| `--validate-only` | Validate and prepare SVG without connecting to Illustrator |

`--duration` and `--delay-ms` are mutually exclusive. The duration target excludes source import, the initial preparation delay, final AI/PNG saving and GIF encoding. Slow document operations can exceed the target. Actual timing is recorded in `process.json`.

Local performance example (Illustrator 2022): artwork containing about 264,000 paths took approximately 49 seconds for live construction with batches of 24 groups, and 67 seconds when recording intermediate PNG frames with batches of 8. A 30-second setting is a pacing target, not a performance guarantee. The replay can independently play in approximately 30 seconds without changing the vector output.

## Outputs

- `progressive.ai`: editable destination document.
- `final.png`: preview exported by Illustrator.
- `process.json`: object counts, steps and actual construction duration.
- `build.gif` and `frames/`: recorded process, when enabled.
- `prepared.svg`: local intermediate with stable group names.
- `process.log`: COM execution results and timing.

Top-level SVG elements define drawing units. A compound path may contain thousands of subpaths; preserving the unit avoids damaging holes. Text remains text where Illustrator supports the source font. Final path/text counts are checked against the imported source and raster/placed items are rejected.

The supported input subset includes vector shapes, groups, text, gradients, clipping and local references. Scripts, external resources, images, CSS, filters and DTDs are rejected. A PNG/JPEG first needs a separate vector reconstruction; this command does not trace bitmaps.

On failure, the new destination and partial output remain for inspection. The command does not overwrite existing work or retry partially completed copy operations.
