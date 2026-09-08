"""Build editable SVG artwork progressively in a fresh Illustrator document."""
from __future__ import annotations

import argparse
import json
import logging
import re
import sys
import time
import uuid
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from illustrator.com_client import IllustratorClient, jsx_literal

SPEEDS = {'fast': 0, 'normal': 80, 'slow': 300}
ALIASES = {'快速': 'fast', '快速生成': 'fast', '正常': 'normal', '正常演示': 'normal',
           '慢速': 'slow', '放慢速度': 'slow', '慢慢生成': 'slow'}


def resolve_delay(speed: str, explicit: int | None) -> int:
    """Translate named speed presets, allowing an explicit millisecond override."""
    key = ALIASES.get(speed, speed)
    if key not in SPEEDS:
        raise ValueError('speed must be fast/normal/slow or 快速/正常/慢速')
    delay = SPEEDS[key] if explicit is None else explicit
    if not 0 <= delay <= 5000:
        raise ValueError('delay-ms must be 0..5000')
    return delay


def prepare_svg(source: Path, target: Path) -> int:
    """Name top-level graphical units while preserving SVG order and holes.

    Support a bounded SVG subset: vectors, text, gradients and local references.
    External resources, scripts, images, CSS and filters are rejected before COM.
    """
    data = source.read_text(encoding='utf-8-sig')
    if re.search(r'<!\s*(DOCTYPE|ENTITY)', data, re.I):
        raise ValueError('DTD/entities are not supported')
    root = ET.fromstring(data)
    ns = '{http://www.w3.org/2000/svg}'
    allowed = {'svg','g','path','rect','circle','ellipse','line','polyline','polygon',
               'text','tspan','defs','linearGradient','radialGradient','stop','clipPath',
               'use','title','desc','metadata'}
    if root.tag not in (ns+'svg','svg'):
        raise ValueError('Expected SVG document')
    for element in root.iter():
        if element.tag.split('}')[-1] not in allowed:
            raise ValueError('Unsupported SVG element: '+element.tag)
        for key,value in element.attrib.items():
            local = key.split('}')[-1].lower()
            if local.startswith('on') or local == 'style':
                raise ValueError('Scripts and inline CSS are not supported')
            if local in ('href','base') and not value.startswith('#'):
                raise ValueError('External SVG references are not supported')
            for ref in re.findall(r'url\((.*?)\)',value,re.I):
                if not ref.strip(' \"\'').startswith('#'):
                    raise ValueError('External paint resources are not supported')
    count = 0
    for pos,child in enumerate(list(root)):
        if child.tag.split('}')[-1] in ('defs','title','desc','metadata'):
            continue
        unit = ET.Element(ns+'g', {'id': f'SCIUNIT{count:05d}'})
        root.remove(child)
        unit.append(child)
        root.insert(pos,unit)
        count += 1
    if not count:
        raise ValueError('SVG contains no graphical units')
    ET.register_namespace('',ns[1:-1])
    ET.ElementTree(root).write(target,encoding='utf-8',xml_declaration=True)
    return count


def export_png(client: IllustratorClient, path: Path) -> None:
    """Capture the actual cumulative artboard without altering vector objects."""
    script = '''(function(path) {
        var f=new File(path); if(f.exists) throw new Error('Output exists');
        var o=new ExportOptionsPNG24(); o.antiAliasing=true; o.transparency=false;
        o.artBoardClipping=true; o.horizontalScale=100; o.verticalScale=100;
        app.activeDocument.exportFile(f,ExportType.PNG24,o); return 'OK';
    })(DATA);'''.replace('DATA',jsx_literal(path.as_posix()))
    client.execute_jsx(script)
    if not path.is_file() or not path.stat().st_size:
        raise RuntimeError('PNG export missing')


def make_gif(frames: list[Path], target: Path, frame_ms: int) -> None:
    """Encode a replay; GIF timing is independent of desktop rendering time."""
    from PIL import Image
    images = []
    try:
        for path in frames:
            with Image.open(path) as image:
                images.append(image.convert('RGB').quantize(colors=256))
        durations = [frame_ms]*len(images)
        durations[0]=600; durations[-1]=2500
        images[0].save(target,save_all=True,append_images=images[1:],
                       duration=durations,loop=0,disposal=2)
    finally:
        for image in images: image.close()


def main() -> int:
    """Import source once, then add real vector copies to the new output document."""
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-svg',type=Path,required=True)
    parser.add_argument('--output-dir',type=Path,required=True)
    parser.add_argument('--batch-size',type=int,default=24)
    parser.add_argument('--delay-ms',type=int)
    parser.add_argument('--speed',default='normal')
    parser.add_argument('--start-delay',type=float,default=10)
    parser.add_argument('--frame-ms',type=int,default=250)
    parser.add_argument('--live-only',action='store_true')
    parser.add_argument('--mode',choices=['progressive','instant'],default='progressive')
    parser.add_argument('--duration',type=float,help='Target construction seconds; excludes initial import and final save')
    parser.add_argument('--validate-only',action='store_true')
    args=parser.parse_args()
    delay=resolve_delay(args.speed,args.delay_ms)
    if args.duration is not None and not 1 <= args.duration <= 3600:
        parser.error('duration must be 1..3600 seconds')
    if args.duration is not None and args.delay_ms is not None:
        parser.error('Use either --duration or --delay-ms, not both')
    instant=args.mode=='instant'
    capture=not args.live_only and not instant
    if not 1 <= args.batch_size <= 200 or not 0 <= args.start_delay <= 60 or not 20 <= args.frame_ms <= 10000:
        parser.error('batch-size 1..200; start-delay 0..60; frame-ms 20..10000')
    directory=args.output_dir.expanduser().resolve()
    directory.mkdir(parents=True,exist_ok=False)
    prepared=directory/'prepared.svg'
    units=prepare_svg(args.source_svg.expanduser().resolve(),prepared)
    timing = 'instant' if instant else (f'target {args.duration:g} seconds' if args.duration else f'{delay} ms/group')
    print(f'Validated {units} graphical groups; {timing}',flush=True)
    if args.validate_only: return 0
    from PIL import Image  # Fail before COM if GIF dependency is absent.
    logging.basicConfig(level=logging.INFO,handlers=[logging.FileHandler(directory/'process.log',encoding='utf-8')])
    frame_dir=directory/'frames'; frame_dir.mkdir()
    frames=[]; steps=[]
    key='SCI_PROGRESS_'+uuid.uuid4().hex
    source_open=False
    with IllustratorClient() as client:
        try:
            init='''(function(file,key) {
                var source=app.open(new File(file)); $.global[key]=source;
                if(source.rasterItems.length || source.placedItems.length) throw new Error('Raster input');
                var b=source.artboards[0].artboardRect;
                return [b[2]-b[0],b[1]-b[3],source.pathItems.length,source.textFrames.length].join('|');
            })(FILE,KEY);'''.replace('FILE',jsx_literal(prepared.as_posix())).replace('KEY',jsx_literal(key))
            source_open=True
            width,height,expected_paths,expected_text=map(float,client.execute_jsx(init,owned_document=False).split('|'))
            client.create_document(width,height)
            print('Blank document ready; '+('adding all groups' if instant else f'starts in {args.start_delay:g} seconds'),flush=True)
            if not instant: time.sleep(args.start_delay)
            if capture:
                blank=frame_dir/'frame_0000.png'; export_png(client,blank); frames.append(blank)
            started=time.perf_counter()
            size=units if instant else args.batch_size
            for start in range(0,units,size):
                stop=min(start+size,units)
                payload=dict(key=key,start=start,stop=stop,
                             delay=0 if instant or args.duration else delay,
                             redraw_each=not instant and args.duration is None)
                script='''(function(p) {
                    var dest=app.activeDocument, source=$.global[p.key];
                    var sb=source.artboards[0].artboardRect, db=dest.artboards[0].artboardRect;
                    var layer; try {layer=dest.layers.getByName('SCI_PROGRESSIVE');}
                    catch(e){layer=dest.layers.add();layer.name='SCI_PROGRESSIVE';}
                    for(var i=p.start;i<p.stop;i++){
                        var num=('00000'+i).slice(-5), name='SCIUNIT'+num;
                        var original=source.groupItems.getByName(name);
                        var x=original.left-sb[0], y=original.top-sb[1];
                        var added=original.duplicate(layer,ElementPlacement.PLACEATBEGINNING);
                        added.position=[db[0]+x,db[1]+y];
                        if(p.redraw_each){dest.activate();app.redraw();}
                        if(p.delay) $.sleep(p.delay);
                    }
                    dest.activate();app.redraw();
                    if(layer.groupItems.length!==p.stop) throw new Error('Group count mismatch');
                    if(dest.rasterItems.length || dest.placedItems.length) throw new Error('Raster output');
                    return dest.pathItems.length+'|'+dest.textFrames.length;
                })(DATA);'''.replace('DATA',jsx_literal(payload))
                paths,texts=map(int,client.execute_jsx(script).split('|'))
                if capture:
                    frame=frame_dir/f'frame_{len(frames):04d}.png'
                    export_png(client,frame); frames.append(frame)
                steps.append(dict(groups=stop,paths=paths,texts=texts))
                print(f'{stop}/{units} groups; {paths} paths; {texts} text frames',flush=True)
                if args.duration and not instant:
                    remaining=started+args.duration*stop/units-time.perf_counter()
                    if remaining>0: time.sleep(remaining)
            actual_duration=time.perf_counter()-started
            if paths != int(expected_paths) or texts != int(expected_text):
                raise RuntimeError('Final source/output object counts differ')
            client.save_document(directory/'progressive.ai')
            export_png(client,directory/'final.png')
        finally:
            if source_open:
                cleanup='''(function(key){var doc=$.global[key];if(doc){doc.close(SaveOptions.DONOTSAVECHANGES);delete $.global[key];}return 'closed temporary source';})(KEY);'''.replace('KEY',jsx_literal(key))
                # Only the source SVG document opened by this invocation is closed.
                client.execute_jsx(cleanup,owned_document=False)
    if capture: make_gif(frames,directory/'build.gif',args.frame_ms)
    report=dict(source=str(args.source_svg),groups=units,paths=paths,texts=texts,
                delay_ms=0 if instant or args.duration else delay,batch_size=size,frames=len(frames),steps=steps,
                mode=args.mode,target_seconds=args.duration,actual_construction_seconds=actual_duration)
    (directory/'process.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(f'Saved: {directory}',flush=True)
    return 0


if __name__=='__main__':
    raise SystemExit(main())
