"""Opt-in regression for native endpoint arrows surviving AI save and reopen."""
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'examples'))


@unittest.skipUnless(os.environ.get('ILLUSTRATOR_INTEGRATION') == '1',
                     'Requires an interactive Windows Illustrator session')
class NativeArrowIntegrationTests(unittest.TestCase):
    def test_native_arrow_survives_save_and_reopen(self):
        from illustrator.com_client import IllustratorClient, jsx_literal
        from swarm_primitives import initialize_scene, draw_primitive_wave, verify_scene

        key = 'SCI_ARROW_REGRESSION'
        scene = {'width': 240, 'height': 120, 'items': [
            {'id': 'arrow', 'kind': 'arrow', 'layer': 'Regression', 'group': None,
             'points': [[20, 40], [200, 40]], 'stroke': '#262B75', 'stroke_width': 4,
             'arrowheads': {'start': 0, 'end': 7, 'end_scale': 40, 'align': 0}},
            {'id': 'box', 'kind': 'rect', 'layer': 'Regression', 'group': None,
             'x': 20, 'y': 70, 'width': 40, 'height': 20, 'fill': '#CCCCCC'}]}
        inspect = '''function inspectArrow(doc) {
            if(doc.pathItems.length!==2) throw new Error('Unexpected path count');
            var arrow=doc.pathItems.getByName('SCI_PATH_arrow');
            if(arrow.closed || arrow.pathPoints.length!==2)
                throw new Error('Arrow geometry changed');
            var bounds=arrow.visibleBounds;
            if(bounds[1]-bounds[3]<=arrow.strokeWidth+0.01)
                throw new Error('Native endpoint arrowhead missing');
        }'''
        with tempfile.TemporaryDirectory() as directory, IllustratorClient() as client:
            client.create_document(240, 120)
            client.execute_jsx('$.global.' + key + 'Doc=app.activeDocument; "tracked";')
            try:
                initialize_scene(client, scene, key)
                draw_primitive_wave(client, scene, key, [0, 1], 2, 0)
                client.execute_jsx('$.global.' + key + '.releaseArrows(); "released";')
                verify_scene(client, scene)
                client.execute_jsx('(function(){' + inspect + 'inspectArrow(app.activeDocument);return "checked";})();')
                output = client.save_document(Path(directory) / 'native_arrow.ai')
                script = '(function(path){' + inspect + '''
                    var doc=app.activeDocument;
                    doc.close(SaveOptions.DONOTSAVECHANGES);
                    delete $.global.SCI_ARROW_REGRESSIONDoc;
                    doc=app.open(new File(path));
                    $.global.SCI_ARROW_REGRESSIONDoc=doc;
                    inspectArrow(doc); return 'persisted|2';
                })(''' + jsx_literal(output.as_posix()) + ');'
                self.assertEqual(client.execute_jsx(script), 'persisted|2')
            finally:
                client.execute_jsx('''(function(){
                    var state=$.global.SCI_ARROW_REGRESSION;
                    if(state) state.releaseArrows();
                    var doc=$.global.SCI_ARROW_REGRESSIONDoc;
                    if(doc) doc.close(SaveOptions.DONOTSAVECHANGES);
                    delete $.global.SCI_ARROW_REGRESSION;
                    delete $.global.SCI_ARROW_REGRESSIONDoc;
                    return 'closed test document';
                })();''', owned_document=False)


if __name__ == '__main__':
    unittest.main()
