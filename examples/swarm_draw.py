"""Draw waves of editable Illustrator objects with synchronized presentation cursors."""
from __future__ import annotations

import argparse
import ctypes
import json
import logging
import math
import queue
import sys
import threading
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from illustrator.com_client import IllustratorClient, jsx_literal
from progressive_svg import export_png, prepare_svg


def plan_waves(bounds, agents):
    """Assign nearby source groups to lanes without changing their final stacking."""
    if not 2 <= agents <= 30:
        raise ValueError('agents must be 2..30')
    # Contiguous spatial slices balance work while keeping cursors in separate areas.
    ordered = sorted(range(len(bounds)), key=lambda i: ((bounds[i][0] + bounds[i][2]) / 2,
                                                       (bounds[i][1] + bounds[i][3]) / 2))
    lanes = [[] for _ in range(agents)]
    for rank, index in enumerate(ordered):
        lane = min(agents - 1, rank * agents // max(1, len(ordered)))
        lanes[lane].append(index)
    for lane in lanes:
        lane.sort()
    waves = []
    for step in range(max((len(lane) for lane in lanes), default=0)):
        waves.append([{'agent': agent, 'index': lane[step], 'bounds': bounds[lane[step]]}
                      for agent, lane in enumerate(lanes) if step < len(lane)])
    return waves


def source_info(client, prepared, key):
    script = '''(function(file,key){
        var s=app.open(new File(file)); $.global[key]=s;
        if(s.rasterItems.length || s.placedItems.length) throw new Error('Raster input');
        var b=s.artboards[0].artboardRect, w=b[2]-b[0], h=b[1]-b[3], rows=[];
        for(var i=0;;i++){
            var g; try{g=s.groupItems.getByName('SCIUNIT'+('00000'+i).slice(-5));}
            catch(e){break;}
            var r=g.geometricBounds;
            rows.push([(r[0]-b[0])/w,(b[1]-r[1])/h,(r[2]-b[0])/w,(b[1]-r[3])/h].join(','));
        }
        return [w,h,s.pathItems.length,s.textFrames.length].join('|')+';'+rows.join(';');
    })(FILE,KEY);'''.replace('FILE', jsx_literal(prepared.as_posix())).replace('KEY', jsx_literal(key))
    header, *rows = client.execute_jsx(script, owned_document=False).split(';')
    width, height, paths, texts = map(float, header.split('|'))
    bounds = [list(map(float, row.split(','))) for row in rows]
    if not all(math.isfinite(value) for box in bounds for value in box):
        raise ValueError('Source has non-finite bounds')
    return width, height, int(paths), int(texts), bounds


def create_slots(client, count):
    # Empty containers establish SVG stacking before any spatial wave is drawn.
    client.execute_jsx('''(function(count){
        var d=app.activeDocument, l=d.layers.add(); l.name='SCI_SWARM';
        for(var i=0;i<count;i++){
            var slot=l.groupItems.add(); slot.name='SWARM_SLOT'+('00000'+i).slice(-5);
        }
        app.executeMenuCommand('fitin'); app.redraw(); return 'ready';
    })(COUNT);'''.replace('COUNT', str(count)))


def copy_wave(client, key, jobs):
    payload = {'key': key, 'indices': [job['index'] for job in jobs]}
    result = client.execute_jsx('''(function(p){
        var d=app.activeDocument, s=$.global[p.key], l=d.layers.getByName('SCI_SWARM');
        var sb=s.artboards[0].artboardRect, db=d.artboards[0].artboardRect;
        for(var n=0;n<p.indices.length;n++){
            var num=('00000'+p.indices[n]).slice(-5);
            var slot=l.groupItems.getByName('SWARM_SLOT'+num);
            if(slot.pageItems.length) throw new Error('Wave was already applied');
            var source=s.groupItems.getByName('SCIUNIT'+num);
            var x=source.left-sb[0], y=source.top-sb[1];
            var added=source.duplicate(l,ElementPlacement.PLACEATBEGINNING);
            added.move(slot,ElementPlacement.PLACEATBEGINNING);
            added.position=[db[0]+x,db[1]+y];
        }
        d.activate(); app.redraw();
        if(d.rasterItems.length || d.placedItems.length) throw new Error('Raster output');
        return d.pathItems.length+'|'+d.textFrames.length;
    })(DATA);'''.replace('DATA', jsx_literal(payload)))
    return tuple(map(int, result.split('|')))


def illustrator_window():
    import win32gui
    windows = []
    def visit(hwnd, unused):
        if win32gui.IsWindowVisible(hwnd) and win32gui.GetClassName(hwnd) == 'illustrator':
            windows.append(hwnd)
    win32gui.EnumWindows(visit, None)
    if len(windows) != 1:
        raise RuntimeError(f'Expected one Illustrator main window, found {len(windows)}')
    return windows[0]


def render(args, prepared, units, events, ready, cancel, result):
    key = 'SCI_SWARM_' + uuid.uuid4().hex
    report = {'status': 'running', 'groups': units, 'cursors': args.agents, 'steps': [],
              'execution': 'single COM worker, batched vector waves, animated presentation cursors'}
    source_open = False
    try:
        with IllustratorClient() as client:
            try:
                if cancel.is_set():
                    raise InterruptedError('Cancelled before document creation')
                source_open = True
                if args.scene_json:
                    from swarm_primitives import initialize_scene, plan_primitive_waves
                    source_open = False
                    scene = json.loads(prepared.read_text(encoding='utf-8'))
                    client.create_document(scene['width'], scene['height'])
                    initialize_scene(client, scene, key)
                    waves = plan_primitive_waves(scene, args.agents)
                    expected_texts = sum(item['kind'] == 'text' for item in scene['items'])
                    expected_paths = units - expected_texts
                    report['execution'] = 'direct native primitives, one COM worker, spatial waves, synchronized cursor animation'
                    report['objects'] = report.pop('groups')
                    report['native_gradients'] = sum('gradient' in item for item in scene['items'])
                    report['native_arrows'] = sum(item['kind'] == 'arrow' for item in scene['items'])
                    report['reference_note'] = scene.get('note', '')
                else:
                    width, height, expected_paths, expected_texts, bounds = source_info(client, prepared, key)
                    if len(bounds) != units:
                        raise RuntimeError('Imported source group count differs')
                    client.create_document(width, height)
                    create_slots(client, units)
                    waves = plan_waves(bounds, args.agents)
                unit = 'objects' if args.scene_json else 'groups'
                hwnd = illustrator_window()
                rectangle = args.artboard_rect
                if rectangle is None and not args.manual_align:
                    from swarm_alignment import align_artboard
                    rectangle = align_artboard(client, hwnd)
                    print(f'Auto-aligned artboard: {rectangle}', flush=True)
                result['rectangle'] = rectangle
                events.put({'type': 'init', 'total': units, 'hwnd': hwnd, 'unit': unit,
                            'rectangle': rectangle})
                if not ready.wait(args.calibration_timeout) or cancel.is_set():
                    raise InterruptedError('Calibration cancelled or timed out')
                if cancel.wait(args.start_delay):
                    raise InterruptedError('Cancelled before drawing')
                paths = texts = completed = 0
                warnings = []
                started = time.perf_counter()
                for number, jobs in enumerate(waves, 1):
                    seconds = args.duration / len(waves)
                    events.put({'type': 'wave', 'jobs': jobs, 'seconds': seconds,
                                'wave': number, 'waves': len(waves)})
                    if cancel.wait(seconds):
                        raise InterruptedError('Drawing cancelled before next wave')
                    if args.scene_json:
                        from swarm_primitives import draw_primitive_wave
                        indices = [index for job in jobs for index in job['indices']]
                        completed += len(indices)
                        texts += sum(scene['items'][index]['kind'] == 'text' for index in indices)
                        paths = completed - texts
                        warning = draw_primitive_wave(client, scene, key, indices, completed, texts)
                        if warning:
                            warnings.append(warning)
                    else:
                        paths, texts = copy_wave(client, key, jobs)
                        indices = [job['index'] for job in jobs]
                        completed += len(jobs)
                    report['steps'].append({'wave': number, 'groups': completed,
                                            'indices': indices,
                                            'paths': paths, 'texts': texts})
                    events.put({'type': 'progress', 'completed': completed})
                    print(f'Wave {number}/{len(waves)}: {completed}/{units} {unit}', flush=True)
                if (paths, texts) != (expected_paths, expected_texts):
                    raise RuntimeError('Final source/output path or text counts differ')
                if args.scene_json:
                    from swarm_primitives import verify_scene
                    client.execute_jsx('$.global[' + jsx_literal(key) + '].releaseArrows(); "arrow templates released";')
                    verify_scene(client, scene)
                report['actual_construction_seconds'] = time.perf_counter() - started
                events.put({'type': 'saving'})
                client.save_document(args.output_dir / 'swarm.ai')
                export_png(client, args.output_dir / 'final.png')
                report.update(status='complete', paths=paths, texts=texts, warnings=warnings)
            finally:
                if source_open:
                    cleanup = '''(function(key){var s=$.global[key];
                        if(s){s.close(SaveOptions.DONOTSAVECHANGES);delete $.global[key];}
                        return 'closed source';})(KEY);'''.replace('KEY', jsx_literal(key))
                    client.execute_jsx(cleanup, owned_document=False)
                elif args.scene_json:
                    client.execute_jsx('(function(key){var state=$.global[key];if(state&&state.releaseArrows)state.releaseArrows();delete $.global[key];return "released session";})(' + jsx_literal(key) + ');',
                                       owned_document=False)
    except Exception as exc:
        logging.exception('Swarm drawing stopped')
        report.update(status='cancelled' if isinstance(exc, InterruptedError) else 'failed', error=str(exc))
        print(f'Stopped: {exc}', file=sys.stderr, flush=True)
    finally:
        report['target_animation_seconds'] = args.duration
        report['artboard_screen_rect'] = result.get('rectangle')
        (args.output_dir / 'process.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
        result['report'] = report
        events.put({'type': 'done' if report['status'] == 'complete' else 'error'})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    source_group = parser.add_mutually_exclusive_group()
    source_group.add_argument('--source-svg', type=Path)
    source_group.add_argument('--scene-json', type=Path, help='Direct native primitive scene')
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--cursors', '--agents', dest='agents', type=int, default=12,
                        help='Number of presentation cursors; --agents is an alias')
    parser.add_argument('--duration', type=float, default=30, help='Animation seconds plus COM work')
    parser.add_argument('--start-delay', type=float, default=3)
    parser.add_argument('--artboard-rect', type=int, nargs=4, metavar=('X', 'Y', 'WIDTH', 'HEIGHT'))
    parser.add_argument('--manual-align', action='store_true', help='Drag across the artboard instead of automatic alignment')
    parser.add_argument('--calibration-timeout', type=float, default=180)
    parser.add_argument('--validate-only', action='store_true')
    args = parser.parse_args()
    if not 2 <= args.agents <= 30 or not math.isfinite(args.duration) or not 1 <= args.duration <= 3600:
        parser.error('agents must be 2..30 and duration 1..3600')
    valid_delay = math.isfinite(args.start_delay) and 0 <= args.start_delay <= 60
    valid_timeout = math.isfinite(args.calibration_timeout) and 10 <= args.calibration_timeout <= 600
    if not valid_delay or not valid_timeout:
        parser.error('start-delay must be 0..60 and calibration-timeout 10..600')
    if args.artboard_rect and min(args.artboard_rect[2:]) < 80:
        parser.error('Artboard rectangle must be at least 80 x 80 screen pixels')
    args.output_dir = args.output_dir.expanduser().resolve()
    args.output_dir.mkdir(parents=True, exist_ok=False)
    if args.scene_json:
        from swarm_primitives import validate_scene, write_commands
        scene = json.loads(args.scene_json.expanduser().resolve().read_text(encoding='utf-8'))
        validate_scene(scene)
        prepared = args.output_dir / 'scene.json'
        prepared.write_text(json.dumps(scene, ensure_ascii=False, indent=2), encoding='utf-8')
        write_commands(scene, args.output_dir / 'commands.jsx', args.agents, args.duration)
        units = len(scene['items'])
    else:
        source = (args.source_svg or ROOT / 'examples/specs/swarm_demo.svg').expanduser().resolve()
        prepared = args.output_dir / 'prepared.svg'
        units = prepare_svg(source, prepared)
    print(f'Validated {units} drawing units; {args.agents} animated cursors', flush=True)
    if args.validate_only:
        return 0
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except OSError:
        pass  # An embedding process may already have selected DPI awareness.
    from swarm_overlay import SwarmOverlay
    logging.basicConfig(level=logging.INFO, handlers=[logging.FileHandler(args.output_dir / 'process.log', encoding='utf-8')])
    events, ready, cancel = queue.Queue(), threading.Event(), threading.Event()
    result = {}
    overlay = SwarmOverlay(events, ready, cancel, args.artboard_rect, args.agents, args.calibration_timeout)
    worker = threading.Thread(target=render, args=(args, prepared, units, events, ready, cancel, result))
    worker.start()
    try:
        overlay.run()
    finally:
        result['rectangle'] = overlay.rectangle
        cancel.set()
        ready.set()
        worker.join()  # Keep COM ownership alive until any in-flight operation finishes.
    report = result.get('report', {})
    report['artboard_screen_rect'] = overlay.rectangle
    (args.output_dir / 'process.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(f"{report.get('status', 'failed')}: {args.output_dir}", flush=True)
    return 0 if report.get('status') == 'complete' else 1


if __name__ == '__main__':
    raise SystemExit(main())
