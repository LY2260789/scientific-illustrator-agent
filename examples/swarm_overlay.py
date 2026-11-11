"""Transparent, click-through presentation cursors for the swarm renderer."""
from __future__ import annotations

import queue
import math
import time
import tkinter as tk

COLORS = ['#38bdf8', '#a78bfa', '#fb7185', '#34d399', '#fbbf24', '#f472b6',
          '#22d3ee', '#818cf8', '#fb923c', '#a3e635', '#e879f9', '#2dd4bf']
KEY = '#010203'


def trace_position(points, progress):
    lengths = [math.dist(start, end) for start, end in zip(points, points[1:])]
    distance = min(1, max(0, progress)) * sum(lengths)
    visited = [points[0]]
    for start, end, length in zip(points, points[1:], lengths):
        if distance <= length and length > 0:
            fraction = distance / length
            point = (start[0] + (end[0] - start[0]) * fraction,
                     start[1] + (end[1] - start[1]) * fraction)
            return point, visited + [point]
        visited.append(end)
        distance -= length
    return points[-1], visited


def perimeter(bounds, progress):
    """Walk around a normalized object boundary with consistent speed."""
    left, top, right, bottom = bounds
    width, height = max(right - left, .001), max(bottom - top, .001)
    distance = (progress % 1) * 2 * (width + height)
    if distance < width:
        return left + distance, top
    distance -= width
    if distance < height:
        return right, top + distance
    distance -= height
    if distance < width:
        return right - distance, bottom
    return left, bottom - (distance - width)


class SwarmOverlay:
    """Tk runs on the main thread while one worker owns the Illustrator COM client."""

    def __init__(self, events, ready, cancel, rectangle, agents, timeout=180):
        import win32api
        import win32gui
        self.win32api, self.win32gui = win32api, win32gui
        self.events, self.ready, self.cancel = events, ready, cancel
        self.rectangle, self.agents = rectangle, agents
        self.timeout = timeout
        self.root = tk.Tk()
        self.root.withdraw()
        self.root.title('Illustrator Swarm Demo')
        self.root.overrideredirect(True)
        self.root.attributes('-topmost', True)
        self.root.configure(bg=KEY)
        self.root.attributes('-transparentcolor', KEY)
        self.screen = (win32api.GetSystemMetrics(76), win32api.GetSystemMetrics(77),
                       win32api.GetSystemMetrics(78), win32api.GetSystemMetrics(79))
        x, y, width, height = self.screen
        self.root.geometry(f'{width}x{height}+0+0')
        self.canvas = tk.Canvas(self.root, bg=KEY, highlightthickness=0)
        self.canvas.pack(fill='both', expand=True)
        self.root.update_idletasks()
        self.hwnd = win32gui.GetParent(self.root.winfo_id())
        win32gui.SetWindowPos(self.hwnd, -1, x, y, width, height, 0x0010)
        self.owner = None
        self.status = 'Connecting to Illustrator'
        self.jobs = []
        self.origins = {}
        self.positions = {}
        self.wave_start = time.perf_counter()
        self.wave_seconds = 1
        self.completed = self.total = 0
        self.unit = 'groups'
        self.drag_start = None
        self.calibrating = False
        self.deadline = None
        self.finished = False
        self.root.protocol('WM_DELETE_WINDOW', self.close)
        self.root.bind('<Escape>', lambda event: self.close())
        self.canvas.bind('<ButtonPress-1>', self.start_drag)
        self.canvas.bind('<B1-Motion>', self.drag)
        self.canvas.bind('<ButtonRelease-1>', self.end_drag)
        self.click_through(True)
        # Discard a key tap from before this process started.
        self.win32api.GetAsyncKeyState(0x1B)

    def click_through(self, enabled):
        style = self.win32gui.GetWindowLong(self.hwnd, -20)
        bits = 0x20 | 0x08000000  # WS_EX_TRANSPARENT and WS_EX_NOACTIVATE
        if enabled:
            style = (style | bits | 0x80) & ~0x40000
        else:
            # Expose calibration as an ordinary app window, including Alt+Tab.
            style = (style | 0x40000) & ~(bits | 0x80)
        self.win32gui.SetWindowLong(self.hwnd, -20, style | 0x80000)

    def local(self, x, y):
        return x - self.screen[0], y - self.screen[1]

    def point(self, x, y):
        left, top, width, height = self.rectangle
        return self.local(left + x * width, top + y * height)

    def start_drag(self, event):
        if self.calibrating:
            self.drag_start = (event.x_root, event.y_root)

    def drag(self, event):
        if self.calibrating and self.drag_start:
            self.canvas.delete('calibration')
            x, y = self.local(*self.drag_start)
            end_x, end_y = self.local(event.x_root, event.y_root)
            self.canvas.create_rectangle(x, y, end_x, end_y, outline='#38bdf8',
                                         width=3, tags='calibration')

    def end_drag(self, event):
        if not self.calibrating or not self.drag_start:
            return
        x, y = self.drag_start
        left, top = min(x, event.x_root), min(y, event.y_root)
        width, height = abs(x - event.x_root), abs(y - event.y_root)
        if min(width, height) < 80:
            return
        self.rectangle = (left, top, width, height)
        self.calibrating = False
        self.deadline = None
        self.canvas.delete('calibration')
        self.root.attributes('-alpha', 1)
        self.canvas.configure(bg=KEY)
        self.click_through(True)
        self.status = 'Ready'
        self.ready.set()

    def receive(self):
        while True:
            try:
                event = self.events.get_nowait()
            except queue.Empty:
                break
            kind = event['type']
            if kind == 'init':
                self.owner, self.total = event['hwnd'], event['total']
                self.unit = event.get('unit', 'groups')
                if event.get('rectangle') is not None:
                    self.rectangle = event['rectangle']
                self.root.deiconify()
                self.root.attributes('-topmost', True)
                try:
                    self.win32gui.SetForegroundWindow(self.owner)
                except self.win32gui.error:
                    pass  # The user can activate Illustrator if Windows keeps terminal focus.
                if self.rectangle is None:
                    self.calibrating = True
                    self.deadline = time.perf_counter() + self.timeout
                    self.canvas.configure(bg='#111827')
                    self.root.attributes('-alpha', .28)
                    self.click_through(False)
                    self.status = 'Drag from artboard top-left to bottom-right. Esc cancels.'
                else:
                    self.status = 'Starting'
                    self.ready.set()
            elif kind == 'wave':
                self.jobs = event['jobs']
                self.origins = dict(self.positions)
                self.wave_start = time.perf_counter()
                self.wave_seconds = max(.1, event['seconds'])
                self.status = f"Wave {event['wave']} / {event['waves']}"
            elif kind == 'progress':
                self.completed = event['completed']
            elif kind == 'saving':
                self.status = 'Saving editable artwork'
                self.jobs = []
            elif kind in ('done', 'error'):
                self.status = 'Complete' if kind == 'done' else 'Stopped - see console'
                self.jobs = []
                self.finished = True
                self.deadline = time.perf_counter() + 3

    def draw_cursor(self, job, now):
        worker = job['agent']
        color = COLORS[worker % len(COLORS)]
        bounds = job['bounds']
        elapsed = now - self.wave_start
        progress = min(1, max(0, elapsed / self.wave_seconds))
        drawing_progress = min(1, max(0, (progress - .2) / .8))
        trace = job.get('trace')
        if trace:
            target, visited = trace_position(trace, drawing_progress)
            if drawing_progress > 0:
                coordinates = [coordinate for point in visited for coordinate in self.point(*point)]
                self.canvas.create_line(*coordinates, fill=color, width=2, tags='animation')
        else:
            target = perimeter(bounds, drawing_progress * .98)
        origin = self.origins.get(worker, (.08 + (worker % 6) * .16, .06))
        travel = min(1, progress / .2)
        smooth = travel * travel * (3 - 2 * travel)
        position = (origin[0] + (target[0] - origin[0]) * smooth,
                    origin[1] + (target[1] - origin[1]) * smooth)
        self.positions[worker] = position
        x, y = self.point(*position)
        left, top = self.point(bounds[0], bounds[1])
        right, bottom = self.point(bounds[2], bounds[3])
        self.canvas.create_rectangle(left, top, right, bottom, outline=color,
                                     width=1, dash=(4, 3), tags='animation')
        for corner_x, corner_y in [(left, top), (right, top), (left, bottom), (right, bottom)]:
            self.canvas.create_rectangle(corner_x - 2, corner_y - 2, corner_x + 2,
                                         corner_y + 2, fill=color, outline='', tags='animation')
        # A readable pointer with an outline, followed by its colored name tag.
        self.canvas.create_polygon(x, y, x + 4, y + 23, x + 10, y + 16,
                                   x + 17, y + 25, x + 21, y + 22,
                                   x + 14, y + 13, x + 24, y + 11,
                                   fill=color, outline='white', width=1.5, tags='animation')
        label = f'DRAW {worker + 1:02d}'
        self.canvas.create_rectangle(x + 23, y + 24, x + 96, y + 45,
                                     fill=color, outline='', tags='animation')
        self.canvas.create_text(x + 59, y + 34, text=label, fill='#0f172a',
                                font=('Segoe UI', 9, 'bold'), tags='animation')

    def draw_hud(self):
        if self.rectangle:
            x, y = self.point(.5, 1)
            y = min(y + 40, self.screen[3] - 55)
        else:
            x, y = self.screen[2] / 2, self.screen[3] - 90
        width = 650
        self.canvas.create_rectangle(x - width / 2, y - 27, x + width / 2, y + 27,
                                     fill='#101827', outline='#334155', tags='animation')
        for index, color in enumerate(COLORS[:min(self.agents, 6)]):
            self.canvas.create_oval(x - 308 + index * 8, y - 5, x - 298 + index * 8,
                                    y + 5, fill=color, outline='', tags='animation')
        text = f'{self.agents} cursors  |  {self.completed}/{self.total} {self.unit}  |  {self.status}'
        self.canvas.create_text(x - 240, y - 5, anchor='w', text=text, fill='#e2e8f0',
                                font=('Segoe UI', 10), tags='animation')
        self.canvas.create_text(x - 240, y + 14, anchor='w',
                                text='DEMO ANIMATION  /  REAL VECTOR OUTPUT     Esc stops',
                                fill='#94a3b8', font=('Segoe UI', 8), tags='animation')
        ratio = self.completed / max(1, self.total)
        self.canvas.create_rectangle(x - 325, y + 25, x - 325 + 650 * ratio, y + 28,
                                     fill='#38bdf8', outline='', tags='animation')

    def tick(self):
        self.receive()
        now = time.perf_counter()
        # Include the pressed-since-last-poll bit so a quick tap is observed.
        if self.win32api.GetAsyncKeyState(0x1B) & 0x8001:
            self.close()
            return
        if self.deadline and now >= self.deadline:
            self.close()
            return
        self.canvas.delete('animation')
        foreground = self.win32gui.GetForegroundWindow()
        visible = self.calibrating or self.owner is None or foreground in (self.owner, self.hwnd)
        if visible:
            if self.rectangle:
                for job in self.jobs:
                    self.draw_cursor(job, now)
            self.draw_hud()
        self.root.after(16, self.tick)

    def close(self):
        if not self.finished:
            self.cancel.set()
        self.ready.set()
        self.root.destroy()

    def run(self):
        self.tick()
        self.root.mainloop()
