"""Opt-in desktop regression test for Illustrator's native gradient orientation."""
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))


@unittest.skipUnless(os.environ.get('ILLUSTRATOR_INTEGRATION') == '1',
                     'Requires an interactive Windows Illustrator session')
class GradientDirectionIntegrationTests(unittest.TestCase):
    def test_rendered_vertical_and_horizontal_gradients(self):
        from PIL import Image
        from illustrator.com_client import IllustratorClient, jsx_literal
        items = []
        for index in range(3):
            x = 10 + index * 120
            start, end = [x, 10], [x, 150]
            colors = ['#FFFFFF', '#FF0000']
            if index == 1:
                start, end = end, start
                colors.reverse()
            if index == 2:
                start, end = [x, 80], [x + 100, 80]
            items.append({'id': 'direction_' + str(index), 'kind': 'rect',
                          'layer': 'Gradient regression', 'group': None,
                          'x': x, 'y': 10, 'width': 100, 'height': 140,
                          'fill': '#FFFFFF', 'stroke': None,
                          'gradient': {'start': start, 'end': end,
                                       'stops': [{'offset': 0, 'color': colors[0]},
                                                 {'offset': 100, 'color': colors[1]}]}})
        scene = {'items': items}
        template = (ROOT / 'src/illustrator/jsx/artwork.jsx').read_text(encoding='utf-8')
        with tempfile.TemporaryDirectory() as directory, IllustratorClient() as client:
            client.create_document(360, 160)
            try:
                script = '(function(){' + template + '\nreturn renderArtwork(' + jsx_literal(scene) + ');})();'
                self.assertEqual(client.execute_jsx(script), 'OK|3|0|')
                output = Path(directory) / 'directions.png'
                export = '''(function(path){var o=new ExportOptionsPNG24();
                    o.antiAliasing=true;o.transparency=false;o.artBoardClipping=true;
                    o.horizontalScale=100;o.verticalScale=100;
                    app.activeDocument.exportFile(new File(path),ExportType.PNG24,o);return 'OK';
                })(PATH);'''.replace('PATH', jsx_literal(output.as_posix()))
                client.execute_jsx(export)
                with Image.open(output) as image:
                    pixels = image.convert('RGB')
                    for x in (10, 130):
                        self.assertGreater(pixels.getpixel((x + 50, 20))[1], 220)
                        self.assertLess(pixels.getpixel((x + 50, 140))[1], 35)
                        self.assertLess(abs(pixels.getpixel((x + 10, 80))[1]
                                            - pixels.getpixel((x + 90, 80))[1]), 3)
                    self.assertGreater(pixels.getpixel((260, 80))[1], 220)
                    self.assertLess(pixels.getpixel((340, 80))[1], 35)
                    pixels.close()
            finally:
                client.execute_jsx("app.activeDocument.close(SaveOptions.DONOTSAVECHANGES); 'closed test document';")


if __name__ == '__main__':
    unittest.main()
