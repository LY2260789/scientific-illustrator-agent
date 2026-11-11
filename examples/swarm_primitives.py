"""Plan spatial waves and create native paths/text through the bundled COM renderer."""
from __future__ import annotations

import json
import math
import re
from pathlib import Path

from illustrator.com_client import jsx_literal

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / 'src/illustrator/jsx/artwork.jsx'

INITIALIZE = '''function initializeSwarm(scene,key){
    var doc=app.activeDocument, layers={}, groups={}, slots=[];
    for(var i=0;i<scene.items.length;i++){
        var item=scene.items[i];
        if(!layers[item.layer]){
            var layer=doc.layers.add(); layer.name=item.layer; layers[item.layer]=layer;
        }
        var parent=layers[item.layer];
        if(item.group){
            var groupKey=item.layer+'/'+item.group;
            if(!groups[groupKey]){
                groups[groupKey]=parent.groupItems.add();
                groups[groupKey].name='SCI_GROUP_'+item.group;
            }
            parent=groups[groupKey];
        }
        slots[i]=parent.groupItems.add();
        slots[i].name='SWARM_SLOT'+('00000'+i).slice(-5);
    }
    $.global[key]={slots:slots};
    app.executeMenuCommand('fitin'); app.redraw(); return 'ready';
}'''


def validate_scene(scene):
    for dimension in ('width', 'height'):
        value = scene[dimension]
        if not isinstance(value, (int, float)) or not math.isfinite(value) or not 1 <= value <= 16383:
            raise ValueError('Scene dimensions must be finite and 1..16383 points')
    items = scene['items']
    if not items or len({item['id'] for item in items}) != len(items):
        raise ValueError('Scene needs primitives with unique IDs')
    for item in items:
        if item['kind'] not in ('rect', 'ellipse', 'path', 'text'):
            raise ValueError('Unsupported primitive kind')
        if item['kind'] == 'path' and len(item['points']) < 2:
            raise ValueError('A path needs at least two points')
        for point in item_trace(item):
            if not all(math.isfinite(value) for value in point):
                raise ValueError('Primitive coordinates must be finite')
        if 'gradient' in item:
            validate_gradient(item)
    # Validate all nested numeric attributes, including opacity and rich text runs.
    json.dumps(scene, allow_nan=False)


def validate_gradient(item):
    if item['kind'] == 'text':
        raise ValueError('Gradient fills require a shape primitive')
    gradient = item['gradient']
    start, end = gradient['start'], gradient['end']
    if len(start) != 2 or len(end) != 2 or not all(math.isfinite(v) for v in start + end):
        raise ValueError('Gradient start and end require two finite coordinates')
    if math.dist(start, end) <= 0:
        raise ValueError('Gradient start and end must differ')
    stops = gradient['stops']
    if len(stops) < 2:
        raise ValueError('A gradient requires at least two stops')
    offsets = [stop['offset'] for stop in stops]
    if offsets != sorted(offsets) or not all(math.isfinite(v) and 0 <= v <= 100 for v in offsets):
        raise ValueError('Gradient offsets must increase within 0..100')
    for stop in stops:
        if not re.fullmatch(r'#[0-9A-Fa-f]{6}', stop['color']):
            raise ValueError('Gradient colors must use #RRGGBB')
        opacity = stop.get('opacity', 100)
        if not math.isfinite(opacity) or not 0 <= opacity <= 100:
            raise ValueError('Gradient opacity must be 0..100')


def item_trace(item):
    if item['kind'] == 'path':
        points = [list(point) for point in item['points']]
        if item.get('closed'):
            points.append(points[0])
        return points
    x, y, width, height = (item[key] for key in ('x', 'y', 'width', 'height'))
    if item['kind'] == 'ellipse':
        return [[x + width / 2 * (1 + math.cos(i * math.tau / 32)),
                 y + height / 2 * (1 + math.sin(i * math.tau / 32))] for i in range(33)]
    return [[x, y], [x + width, y], [x + width, y + height], [x, y + height], [x, y]]


def item_bounds(item, width, height):
    points = item_trace(item)
    xs, ys = zip(*points)
    return [min(xs) / width, min(ys) / height, max(xs) / width, max(ys) / height]


def plan_primitive_waves(scene, agents, max_waves=72):
    if not 2 <= agents <= 30:
        raise ValueError('agents must be 2..30')
    width, height = scene['width'], scene['height']
    columns = min(agents, math.ceil(math.sqrt(agents * width / height)))
    rows = math.ceil(agents / columns)
    lanes = [[] for _ in range(agents)]
    boxes = [item_bounds(item, width, height) for item in scene['items']]
    for index, bounds in enumerate(boxes):
        center_x = (bounds[0] + bounds[2]) / 2
        center_y = (bounds[1] + bounds[3]) / 2
        column = max(0, min(columns - 1, int(center_x * columns)))
        row = max(0, min(rows - 1, int(center_y * rows)))
        lanes[min(agents - 1, row * columns + column)].append(index)
    count = min(max_waves, max(map(len, lanes)))
    waves = []
    for step in range(count):
        jobs = []
        for agent, lane in enumerate(lanes):
            start, stop = step * len(lane) // count, (step + 1) * len(lane) // count
            indices = lane[start:stop]
            if not indices:
                continue
            # Show the actual geometry of the current primitive under the cursor.
            index = indices[-1]
            trace = [[x / width, y / height] for x, y in item_trace(scene['items'][index])]
            jobs.append({'agent': agent, 'indices': indices, 'bounds': boxes[index], 'trace': trace})
        waves.append(jobs)
    return waves


def initialize_scene(client, scene, key):
    return client.execute_jsx(installation_script(scene, key))


def installation_script(scene, key):
    # Keep the scene and renderer in one ExtendScript closure for the entire run.
    setup = '(function(){' + INITIALIZE + TEMPLATE.read_text(encoding='utf-8')
    setup += '\nvar scene=' + jsx_literal(scene) + ', key=' + jsx_literal(key) + ';\n'
    return setup + '''
        initializeSwarm(scene,key);
        var state=$.global[key]; state.total=0; state.texts=0;
        state.draw=function(indices){
            var items=[], texts=state.texts;
            for(var i=0;i<indices.length;i++){
                var index=indices[i], item=scene.items[index];
                item.swarm_index=index; items.push(item);
                if(item.kind==='text') texts++;
            }
            var total=state.total+items.length;
            var result=renderArtwork({items:items,session_key:key,defer_redraw:true,
                defer_validation:true,expected_total:total,expected_text_total:texts});
            if(result.indexOf('OK|')===0){state.total=total;state.texts=texts;}
            return result;
        };
        return 'cached|'+scene.items.length;
    })();'''


def draw_primitive_wave(client, scene, key, indices, completed, texts):
    script = '$.global[' + jsx_literal(key) + '].draw(' + jsx_literal(indices) + ');'
    result = client.execute_jsx(script)
    if not result.startswith(f'OK|{completed}|{texts}|'):
        raise RuntimeError(result)
    return result.split('|', 3)[3]


def verify_scene(client, scene):
    expected = {('SCI_TEXT_' if item['kind'] == 'text' else 'SCI_PATH_') + item['id']:
                item.get('text', '').replace('\n', '\r') for item in scene['items']}
    gradients = {'SCI_PATH_' + item['id']: item['gradient'] for item in scene['items'] if 'gradient' in item}
    script = '''(function(expected,gradients){
        var doc=app.activeDocument, seen={}, leaves=0;
        if(doc.rasterItems.length || doc.placedItems.length) throw new Error('Raster output');
        for(var i=0;i<doc.pageItems.length;i++){
            var item=doc.pageItems[i]; if(item.typename==='GroupItem') continue;
            if(!expected.hasOwnProperty(item.name) || seen[item.name]) throw new Error('Unexpected primitive');
            if(item.typename==='TextFrame' && item.contents!==expected[item.name]) throw new Error('Text changed');
            if(gradients.hasOwnProperty(item.name)){
                var paint=item.fillColor, stops=gradients[item.name].stops;
                if(paint.typename!=='GradientColor' || paint.gradient.gradientStops.length!==stops.length)
                    throw new Error('Native gradient missing: '+item.name);
                for(var j=0;j<stops.length;j++){
                    var actual=paint.gradient.gradientStops[j];
                    if(Math.abs(actual.rampPoint-stops[j].offset)>.01)
                        throw new Error('Gradient stop changed: '+item.name);
                }
            }
            seen[item.name]=true; leaves++;
        }
        var count=0; for(var name in expected){if(expected.hasOwnProperty(name)) count++;}
        if(count!==leaves) throw new Error('Missing primitive'); return 'verified|'+leaves;
    })(EXPECTED,GRADIENTS);'''.replace('EXPECTED', jsx_literal(expected)).replace('GRADIENTS', jsx_literal(gradients))
    result = client.execute_jsx(script)
    if result != f"verified|{len(scene['items'])}":
        raise RuntimeError(result)


def write_commands(scene, path, agents, duration):
    """Emit a standalone JSX command file for app.DoJavaScriptFile(path)."""
    waves = plan_primitive_waves(scene, agents)
    key = 'SCI_SWARM_COMMANDS'
    parts = ['// Native Illustrator primitive reconstruction. Generated from a visual reference.',
             '// Run with Illustrator.Application.DoJavaScriptFile using an absolute path.',
             '(function(){',
             f"app.documents.add(DocumentColorSpace.RGB,{scene['width']},{scene['height']});",
             installation_script(scene, key), 'var result;']
    for jobs in waves:
        indices = [index for job in jobs for index in job['indices']]
        parts.append(f'result=$.global[{jsx_literal(key)}].draw({jsx_literal(indices)});')
        parts.append("if(result.indexOf('OK|')!==0) throw new Error(result);")
        parts.append(f'$.sleep({round(duration * 1000 / len(waves))});')
    parts.extend([f'delete $.global[{jsx_literal(key)}];', 'return result;', '})();'])
    path.write_text('\n'.join(parts), encoding='utf-8')
