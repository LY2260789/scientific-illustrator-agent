"""Offline checks for progressive SVG isolation, ordering and speed options."""
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'examples'))
from progressive_svg import prepare_svg, resolve_delay


class ProgressiveSVGTests(unittest.TestCase):
    def test_order_and_compound_holes_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            source=Path(tmp)/'input.svg'; target=Path(tmp)/'prepared.svg'
            d='M0 0H10V10H0Z M2 2V8H8V2Z'
            source.write_text(f'<svg xmlns="http://www.w3.org/2000/svg"><defs/><path d="{d}" fill-rule="evenodd"/><g><text>Two lines</text></g></svg>')
            self.assertEqual(prepare_svg(source,target),2)
            root=ET.parse(target).getroot()
            self.assertEqual(root[1].get('id'),'SCIUNIT00000')
            self.assertEqual(root[1][0].get('d'),d)
            self.assertEqual(root[1][0].get('fill-rule'),'evenodd')
            self.assertEqual(root[2][0][0].text,'Two lines')

    def test_external_or_raster_input_rejected(self):
        for element in ['<image href="x.png"/>','<script/>','<use href="https://example.com/a.svg"/>']:
            with self.subTest(element=element), tempfile.TemporaryDirectory() as tmp:
                source=Path(tmp)/'input.svg'; target=Path(tmp)/'prepared.svg'
                source.write_text('<svg xmlns="http://www.w3.org/2000/svg">'+element+'</svg>')
                with self.assertRaises(ValueError): prepare_svg(source,target)
                self.assertFalse(target.exists())

    def test_chinese_speed(self):
        self.assertEqual(resolve_delay('快速生成',None),0)
        self.assertEqual(resolve_delay('放慢速度',None),300)
        self.assertEqual(resolve_delay('正常',120),120)
