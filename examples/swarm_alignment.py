"""Map Illustrator document coordinates to its native canvas without screenshots."""
import math


def map_artboard(artboard, view, viewport):
    left, top, right, bottom = viewport
    scale_x = (right - left) / (view[2] - view[0])
    scale_y = (bottom - top) / (view[1] - view[3])
    return [round(left + (artboard[0] - view[0]) * scale_x),
            round(top + (view[1] - artboard[1]) * scale_y),
            round((artboard[2] - artboard[0]) * scale_x),
            round((artboard[1] - artboard[3]) * scale_y)]


def align_artboard(client, hwnd):
    import win32gui
    raw = client.execute_jsx('''(function(){
        var d=app.activeDocument,v=d.views[0];
        return d.artboards[0].artboardRect.join(',')+'|'+v.bounds.join(',')+'|'+v.zoom;
    })();''')
    artboard_raw, view_raw, zoom_raw = raw.split('|')
    artboard = list(map(float, artboard_raw.split(',')))
    view = list(map(float, view_raw.split(',')))
    zoom = float(zoom_raw)
    if not all(math.isfinite(value) for value in artboard + view + [zoom]):
        raise ValueError('Illustrator returned non-finite view coordinates')
    expected_width = (view[2] - view[0]) * zoom
    expected_height = (view[1] - view[3]) * zoom
    if min(expected_width, expected_height) <= 0:
        raise ValueError('Illustrator view has no visible area')
    candidates = []

    def visit(child, unused):
        # Illustrator can mark the canvas hidden while its window is in the
        # background. Its geometry still matches the current document view.
        if win32gui.GetWindowText(child) == 'OS_ViewContainer':
            bounds = win32gui.GetWindowRect(child)
            width, height = bounds[2] - bounds[0], bounds[3] - bounds[1]
            if min(width, height) > 200:
                error = abs(width / expected_width - 1) + abs(height / expected_height - 1)
                candidates.append((error, bounds))
        return True

    win32gui.EnumChildWindows(hwnd, visit, None)
    if not candidates:
        raise RuntimeError('Illustrator canvas could not be located. Use --manual-align.')
    error, viewport = min(candidates)
    if error > .08:
        raise RuntimeError('Illustrator canvas geometry differs from its view. Use --manual-align.')
    return map_artboard(artboard, view, viewport)
