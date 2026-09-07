// Ordered vector scene renderer for complex reference artwork. ES3 / Illustrator 2020+.
function renderArtwork(scene) {
    var doc = app.activeDocument, prior = app.coordinateSystem, current = "start";
    var layers = {}, groups = {}, textCount = 0, warnings = [];
    function color(hex) {
        var c = new RGBColor();
        c.red = parseInt(hex.substr(1,2),16); c.green = parseInt(hex.substr(3,2),16); c.blue = parseInt(hex.substr(5,2),16);
        return c;
    }
    try {
        app.coordinateSystem = CoordinateSystem.DOCUMENTCOORDINATESYSTEM;
        var b = doc.artboards[0].artboardRect;
        function xy(p) { return [b[0] + p[0], b[1] - p[1]]; }
        for (var i = 0; i < scene.items.length; i++) {
            var o = scene.items[i]; current = o.id;
            if (!layers[o.layer]) {
                try { layers[o.layer] = doc.layers.getByName(o.layer); }
                catch (missingLayer) { layers[o.layer] = doc.layers.add(); layers[o.layer].name = o.layer; }
            }
            var parent = layers[o.layer];
            if (o.group) {
                var key = o.layer + "/" + o.group;
                if (!groups[key]) {
                    try { groups[key] = parent.groupItems.getByName("SCI_GROUP_" + o.group); }
                    catch (missingGroup) { groups[key] = parent.groupItems.add(); groups[key].name = "SCI_GROUP_" + o.group; }
                }
                parent = groups[key];
            }
            var item;
            if (o.kind === "text") {
                item = parent.textFrames.add(); item.name = "SCI_TEXT_" + o.id;
                item.contents = o.text.replace(/\n/g,"\r");
                item.textRange.characterAttributes.size = o.size;
                item.textRange.characterAttributes.fillColor = color(o.fill);
                try { item.textRange.characterAttributes.textFont = app.textFonts.getByName(o.font); }
                catch (fontError) { warnings.push("Font fallback: " + o.font); }
                if (o.runs) {
                    for (var r = 0; r < o.runs.length; r++) {
                        var run = o.runs[r];
                        for (var c = run.start; c < run.start + run.length; c++) {
                            if (run.color) item.characters[c].characterAttributes.fillColor = color(run.color);
                            if (run.size) item.characters[c].characterAttributes.size = run.size;
                            if (run.shift) item.characters[c].characterAttributes.baselineShift = run.shift;
                        }
                    }
                }
                if (o.rotation) item.rotate(o.rotation);
                app.redraw();
                if (item.width > o.width + 1 || item.height > o.height + 1)
                    warnings.push("Text box exceeded: " + o.id + " " + item.width.toFixed(1) + "x" + item.height.toFixed(1));
                item.left = b[0] + o.x + (o.align === "left" ? 0 : (o.width - item.width) / 2);
                item.top = b[1] - o.y - (o.height - item.height) / 2;
                if (item.contents !== o.text.replace(/\n/g,"\r")) throw new Error("Text changed: " + o.id);
                textCount++;
            } else {
                if (o.kind === "ellipse") item = parent.pathItems.ellipse(b[1]-o.y,b[0]+o.x,o.width,o.height);
                else if (o.kind === "rect") {
                    if (o.radius) item = parent.pathItems.roundedRectangle(b[1]-o.y,b[0]+o.x,o.width,o.height,o.radius,o.radius);
                    else item = parent.pathItems.rectangle(b[1]-o.y,b[0]+o.x,o.width,o.height);
                } else {
                    item = parent.pathItems.add(); var points = [];
                    for (var p = 0; p < o.points.length; p++) points.push(xy(o.points[p]));
                    item.setEntirePath(points); item.closed = !!o.closed;
                }
                item.name = "SCI_PATH_" + o.id;
                item.filled = !!o.fill; if (o.fill) item.fillColor = color(o.fill);
                item.stroked = !!o.stroke; if (o.stroke) { item.strokeColor = color(o.stroke); item.strokeWidth = o.stroke_width; }
                if (o.dash) item.strokeDashes = o.dash;
            }
            if (o.opacity !== undefined) item.opacity = o.opacity;
            if (scene.element_delay_ms) { app.redraw(); $.sleep(scene.element_delay_ms); }
        }
        var expectedText = scene.expected_text_total === undefined ? textCount : scene.expected_text_total;
        if (doc.textFrames.length !== expectedText) throw new Error("Unexpected split text frames");
        var leafCount = 0, rasterCount = 0;
        for (var k = 0; k < doc.pageItems.length; k++) {
            if (doc.pageItems[k].typename !== "GroupItem") leafCount++;
            if (doc.pageItems[k].typename === "RasterItem" || doc.pageItems[k].typename === "PlacedItem") rasterCount++;
        }
        var expectedTotal = scene.expected_total === undefined ? scene.items.length : scene.expected_total;
        if (leafCount !== expectedTotal || rasterCount !== 0) throw new Error("Object count or raster validation failed");
        app.redraw();
        return "OK|" + leafCount + "|" + expectedText + "|" + warnings.join("; ");
    } catch (e) { return "ERROR|" + current + "|line " + e.line + ": " + e.message; }
    finally { app.coordinateSystem = prior; }
}
