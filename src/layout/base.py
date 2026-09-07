"""Compute ordered flow geometry or scale reference proportions to points."""

from __future__ import annotations

import math
import textwrap
from typing import Any

from models.figure_spec import FigureSpec


def compute_layout(spec: FigureSpec) -> dict[str, Any]:
    """Resolve nodes and edges, refusing clipping before opening a document."""
    reference = spec.mode == "reconstruct"
    margin = spec.canvas.margin
    title_space = 30 if spec.title else 0
    vertical = spec.layout.kind == "vertical"
    nodes: list[dict[str, Any]] = []
    cursor = margin + (title_space if vertical else 0)
    for node in spec.nodes:
        style = node.style or spec.style
        if reference:
            width = node.width * spec.canvas.width
            height = node.height * spec.canvas.height
            x = node.position.x * spec.canvas.width
            y = node.position.y * spec.canvas.height
        else:
            width = node.width or spec.layout.node_width
            height = node.height or spec.layout.node_height
            x, y = (margin, cursor) if vertical else (cursor, margin + title_space)
            cursor += (height if vertical else width) + spec.layout.spacing
        label = node.label
        if not reference:
            # Approximate Latin wrapping; measured Illustrator bounds are checked later.
            capacity = max(1, int((width - 20) / (style.text.size * 0.58)))
            label = "\n".join(textwrap.fill(part, width=capacity, break_long_words=False) for part in label.splitlines())
        nodes.append(dict(id=node.id, shape=node.shape, label=label, x=x, y=y,
                          width=width, height=height, style=style.dict()))
    if not reference:
        if vertical:
            maximum = max(n["width"] for n in nodes)
            for node in nodes:
                node["x"] = margin + (maximum - node["width"]) / 2
        else:
            maximum = max(n["height"] for n in nodes)
            for node in nodes:
                node["y"] = margin + title_space + (maximum - node["height"]) / 2
    width = spec.canvas.width or max(n["x"] + n["width"] for n in nodes) + margin
    height = spec.canvas.height or max(n["y"] + n["height"] for n in nodes) + margin
    if width > 16383 or height > 16383:
        raise ValueError("Computed canvas exceeds legacy Illustrator limits")
    for node in nodes:
        if node["x"] + node["width"] > width + 0.001 or node["y"] + node["height"] > height + 0.001:
            raise ValueError(f"Canvas clips node {node['id']}; omit explicit canvas size or enlarge it")
    lookup = {n["id"]: n for n in nodes}
    edges = []
    for edge in spec.edges:
        if reference:
            points = [[p.x * width, p.y * height] for p in edge.points]
        else:
            source, target = lookup[edge.source], lookup[edge.target]
            if vertical:
                forward = target["y"] > source["y"]
                start = [source["x"] + source["width"] / 2, source["y"] + (source["height"] if forward else 0)]
                end = [target["x"] + target["width"] / 2, target["y"] + (0 if forward else target["height"])]
            else:
                forward = target["x"] > source["x"]
                start = [source["x"] + (source["width"] if forward else 0), source["y"] + source["height"] / 2]
                end = [target["x"] + (0 if forward else target["width"]), target["y"] + target["height"] / 2]
            # V0.1 only adjacent chain edges: fail rather than draw through intervening nodes.
            indices = [n.id for n in spec.nodes]
            if abs(indices.index(edge.source) - indices.index(edge.target)) != 1:
                raise ValueError("Automatic V0.1 routing supports adjacent nodes only; branch routing is a later milestone")
            points = [start, end]
        if any(math.hypot(b[0] - a[0], b[1] - a[1]) < 0.01 for a, b in zip(points, points[1:])):
            raise ValueError(f"Edge {edge.id} contains a zero-length segment")
        if edge.arrow_style.head and math.dist(points[-2], points[-1]) < edge.arrow_style.head_size:
            raise ValueError(f"Edge {edge.id} is too short for its arrowhead")
        edges.append(dict(id=edge.id, points=points, style=edge.arrow_style.dict()))
    return dict(width=width, height=height, title=spec.title, margin=margin,
                title_style=spec.style.text.dict(), nodes=nodes, edges=edges)
