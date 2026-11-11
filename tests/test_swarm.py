"""Regression checks for spatial waves and single-redraw batch submission."""
import sys
import json
import queue
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'examples'))
from swarm_draw import copy_wave, plan_waves, render
from swarm_overlay import SwarmOverlay, perimeter
from swarm_alignment import map_artboard
from swarm_primitives import plan_primitive_waves, draw_primitive_wave, validate_scene


class SwarmTests(unittest.TestCase):
    def test_every_group_drawn_once_and_each_cursor_once_per_wave(self):
        for count in (1, 4, 12, 65, 100):
            bounds = [[i / count, .1, (i + 1) / count, .9] for i in range(count)]
            waves = plan_waves(bounds, 12)
            indices = [job['index'] for wave in waves for job in wave]
            self.assertEqual(sorted(indices), list(range(count)))
            for wave in waves:
                workers = [job['agent'] for job in wave]
                self.assertEqual(len(workers), len(set(workers)))
            for worker in range(12):
                order = [job['index'] for wave in waves for job in wave if job['agent'] == worker]
                self.assertEqual(order, sorted(order))

    def test_regions_remain_spatially_separate(self):
        bounds = [[i / 24, .2, (i + 1) / 24, .8] for i in reversed(range(24))]
        waves = plan_waves(bounds, 12)
        first = [job['bounds'][0] for job in waves[0]]
        self.assertEqual(first, sorted(first))
        self.assertEqual(len(waves), 2)

    def test_wave_is_one_com_call_and_redraw(self):
        class Client:
            def execute_jsx(self, script):
                self.script = script
                return '50|12'
        client = Client()
        result = copy_wave(client, 'key', [{'index': 9}, {'index': 1}])
        self.assertEqual(result, (50, 12))
        self.assertEqual(client.script.count('app.redraw()'), 1)
        self.assertIn('"indices": [9, 1]', client.script)
        self.assertIn('SWARM_SLOT', client.script)
        self.assertIn('Wave was already applied', client.script)

    def test_cursor_boundary(self):
        bounds = [.1, .2, .9, .8]
        for step in range(100):
            x, y = perimeter(bounds, step / 100)
            self.assertTrue(.1 - 1e-9 <= x <= .9 + 1e-9)
            self.assertTrue(.2 - 1e-9 <= y <= .8 + 1e-9)
            self.assertTrue(any(abs(value) < 1e-9 for value in (x - .1, x - .9, y - .2, y - .8)))

    def test_invalid_cursor_count(self):
        with self.assertRaises(ValueError):
            plan_waves([], 1)

    def test_cancelled_calibration_closes_only_temporary_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            client = MagicMock()
            ready, cancel = threading.Event(), MagicMock()
            ready.set()
            cancel.is_set.side_effect = [False, True]
            args = SimpleNamespace(output_dir=Path(tmp), agents=2,
                                   calibration_timeout=10, duration=1, scene_json=None,
                                   artboard_rect=[0, 0, 100, 100], manual_align=False)
            result = {}
            with patch('swarm_draw.IllustratorClient') as factory, \
                    patch('swarm_draw.source_info', return_value=(100, 100, 1, 0, [[0, 0, 1, 1]])), \
                    patch('swarm_draw.create_slots'), \
                    patch('swarm_draw.illustrator_window', return_value=123):
                factory.return_value.__enter__.return_value = client
                render(args, Path(tmp) / 'prepared.svg', 1, queue.Queue(), ready, cancel, result)
            self.assertEqual(result['report']['status'], 'cancelled')
            client.save_document.assert_not_called()
            client.execute_jsx.assert_called_once()
            cleanup = client.execute_jsx.call_args.args[0]
            self.assertIn('DONOTSAVECHANGES', cleanup)
            self.assertNotIn('app.quit', cleanup)
            report = json.loads((Path(tmp) / 'process.json').read_text())
            self.assertEqual(report['steps'], [])

    def test_calibration_deadline_ends_when_drawing_starts(self):
        overlay = SwarmOverlay.__new__(SwarmOverlay)
        overlay.calibrating = True
        overlay.drag_start = (100, 200)
        overlay.deadline = 123
        overlay.canvas, overlay.root = MagicMock(), MagicMock()
        overlay.ready = threading.Event()
        overlay.click_through = MagicMock()
        overlay.end_drag(SimpleNamespace(x_root=900, y_root=700))
        self.assertEqual(overlay.rectangle, (100, 200, 800, 500))
        self.assertIsNone(overlay.deadline)
        self.assertFalse(overlay.calibrating)
        self.assertTrue(overlay.ready.is_set())

    def test_quick_escape_tap_cancels_overlay(self):
        overlay = SwarmOverlay.__new__(SwarmOverlay)
        overlay.receive = MagicMock()
        overlay.win32api = MagicMock()
        overlay.win32api.GetAsyncKeyState.return_value = 1
        overlay.close = MagicMock()
        overlay.tick()
        overlay.close.assert_called_once()

    def test_artboard_mapping_uses_canvas_and_view_coordinates(self):
        result = map_artboard([0, 100, 200, 0], [-50, 125, 250, -25], [100, 200, 1300, 800])
        self.assertEqual(result, [300, 300, 800, 400])
        shifted = map_artboard([0, 100, 200, 0], [-50, 125, 250, -25], [-1300, 200, -100, 800])
        self.assertEqual(shifted, [-1100, 300, 800, 400])

    def test_primitive_waves_cover_scene_without_resending_payload(self):
        scene = {'width': 400, 'height': 300, 'items': [
            {'kind': 'rect', 'x': i * 3, 'y': i % 3 * 90, 'width': 5, 'height': 10,
             'id': str(i), 'text': 'SCIENCE'} for i in range(120)]}
        waves = plan_primitive_waves(scene, 12)
        indices = [index for wave in waves for job in wave for index in job['indices']]
        self.assertEqual(sorted(indices), list(range(120)))
        client = MagicMock()
        client.execute_jsx.return_value = 'OK|3|0|'
        draw_primitive_wave(client, scene, 'session', [0, 10, 20], 3, 0)
        command = client.execute_jsx.call_args.args[0]
        self.assertLess(len(command), 100)
        self.assertNotIn('SCIENCE', command)

    def test_public_case_draws_each_gradient_as_one_native_object(self):
        path = Path(__file__).resolve().parents[1] / 'examples/soc_graphical_abstract/scene.json'
        scene = json.loads(path.read_text(encoding='utf-8'))
        validate_scene(scene)
        ribbons = [item for item in scene['items'] if item.get('group') == 'ribbons']
        self.assertEqual(len(ribbons), 6)
        self.assertTrue(all(item.get('closed') and 'gradient' in item for item in ribbons))
        self.assertEqual(sum('gradient' in item for item in scene['items']), 11)
        self.assertEqual(sum(item['kind'] == 'text' for item in scene['items']), 60)

    def test_invalid_gradient_rejected_before_com(self):
        item = {'id': 'gradient', 'kind': 'rect', 'x': 0, 'y': 0, 'width': 100, 'height': 50,
                'gradient': {'start': [0, 0], 'end': [100, 0],
                             'stops': [{'offset': 90, 'color': '#000000'},
                                       {'offset': 10, 'color': '#FFFFFF'}]}}
        with self.assertRaises(ValueError):
            validate_scene({'width': 100, 'height': 50, 'items': [item]})


if __name__ == '__main__':
    unittest.main()
