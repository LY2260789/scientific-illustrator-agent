// Trusted ES3 implementation. Input is data, never evaluated as executable strings.
function renderScene(scene) {
    var doc = app.activeDocument;
    var previousSystem = app.coordinateSystem;
    var warnings = [];
    var count = 0;
    function checkpoint(message) {
        if (!scene.trace_path) return;
        var log = new File(scene.trace_path);
        log.encoding = "UTF-8";
        if (log.open("a")) { log.writeln(message); log.close(); }
    }
    function rgb(hex) {
        var c = new RGBColor();
        c.red = parseInt(hex.substr(1, 2), 16);
        c.green = parseInt(hex.substr(3, 2), 16);
        c.blue = parseInt(hex.substr(5, 2), 16);
        return c;
    }
    function layer(name) { var l = doc.layers.add(); l.name = name; return l; }
    try {
        app.coordinateSystem = CoordinateSystem.DOCUMENTCOORDINATESYSTEM;
        var board = doc.artboards[0].artboardRect;
        function point(p) { return [board[0] + p[0], board[1] - p[1]]; }
        function text(container, name, content, x, y, width, height, style) {
            checkpoint(name + ": create text frame");
            var t = container.textFrames.add(); t.name = name;
            t.contents = content.replace(/\r\n|\n/g, "\r");
            // Reacquire live host-object attributes after each mutation.
            checkpoint(name + ": size");
            t.textRange.characterAttributes.size = style.size;
            checkpoint(name + ": color");
            t.textRange.characterAttributes.fillColor = rgb(style.color);
            checkpoint(name + ": font");
            try { t.textRange.characterAttributes.textFont = app.textFonts.getByName(style.font); }
            catch (e) { warnings.push("Font unavailable: " + style.font + "; " + name); }
            checkpoint(name + ": redraw and measure");
            app.redraw();
            if (t.width > width + 0.5 || t.height > height + 0.5) {
                throw new Error("Text overflow: " + name + " (" + t.width + " x " + t.height + ")");
            }
            t.left = board[0] + x + (width - t.width) / 2;
            t.top = board[1] - y - (height - t.height) / 2;
            checkpoint(name + ": complete");
            count++;
            return t;
        }
        var edgeLayer = layer("SCI_EDGES");
        for (var i = 0; i < scene.edges.length; i++) {
            var edge = scene.edges[i], points = edge.points, style = edge.style;
            checkpoint("edge " + edge.id);
            var group = edgeLayer.groupItems.add(); group.name = "SCI_EDGE_" + edge.id;
            var path = group.pathItems.add(); path.name = "SCI_PATH_" + edge.id;
            var converted = [];
            for (var j = 0; j < points.length; j++) converted.push(point(points[j]));
            path.setEntirePath(converted); path.filled = false;
            path.stroked = true; path.strokeColor = rgb(style.color); path.strokeWidth = style.width;
            count++;
            if (style.head) {
                var tip = points[points.length - 1], prev = points[points.length - 2];
                var dx = tip[0] - prev[0], dy = tip[1] - prev[1];
                var length = Math.sqrt(dx * dx + dy * dy);
                var ux = dx / length, uy = dy / length, size = style.head_size;
                var bx = tip[0] - ux * size, by = tip[1] - uy * size;
                var head = group.pathItems.add(); head.name = "SCI_HEAD_" + edge.id;
                head.setEntirePath([point(tip), point([bx - uy * size * 0.45, by + ux * size * 0.45]),
                    point([bx + uy * size * 0.45, by - ux * size * 0.45])]);
                head.closed = true; head.filled = true; head.fillColor = rgb(style.color); head.stroked = false;
                count++;
            }
        }
        var nodeLayer = layer("SCI_NODES");
        for (var k = 0; k < scene.nodes.length; k++) {
            var n = scene.nodes[k], s = n.style;
            checkpoint("node " + n.id);
            var nodeGroup = nodeLayer.groupItems.add(); nodeGroup.name = "SCI_GROUP_" + n.id;
            if (n.shape !== "text") {
                var top = board[1] - n.y, left = board[0] + n.x, shape;
                if (n.shape === "rounded_rectangle") {
                    var radius = Math.min(s.radius, n.width / 2, n.height / 2);
                    shape = nodeGroup.pathItems.roundedRectangle(top, left, n.width, n.height, radius, radius);
                } else if (n.shape === "ellipse") {
                    shape = nodeGroup.pathItems.ellipse(top, left, n.width, n.height);
                } else { shape = nodeGroup.pathItems.rectangle(top, left, n.width, n.height); }
                shape.name = "SCI_NODE_" + n.id;
                shape.filled = s.fill !== null; if (shape.filled) shape.fillColor = rgb(s.fill);
                shape.stroked = s.stroke !== null && s.stroke_width > 0;
                if (shape.stroked) { shape.strokeColor = rgb(s.stroke); shape.strokeWidth = s.stroke_width; }
                count++;
            }
            if (n.label) text(nodeGroup, "SCI_TEXT_" + n.id, n.label, n.x, n.y, n.width, n.height, s.text);
        }
        if (scene.title) {
            var titleLayer = layer("SCI_TITLE"), titleStyle = scene.title_style;
            titleStyle.size = 12;
            text(titleLayer, "SCI_TITLE_text", scene.title, scene.margin, scene.margin,
                 scene.width - 2 * scene.margin, 20, titleStyle);
        }
        app.redraw();
        return "OK|" + count + "|" + warnings.join("; ");
    } finally { app.coordinateSystem = previousSystem; }
}
