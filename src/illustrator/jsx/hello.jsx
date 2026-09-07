// ES3 syntax: Illustrator 2020/2022. All geometry is in points.
(function () {
    var doc = app.activeDocument;
    var previousSystem = app.coordinateSystem;
    try {
        app.coordinateSystem = CoordinateSystem.DOCUMENTCOORDINATESYSTEM;
        var board = doc.artboards[0].artboardRect;
        // Map top-left x/right, y/down to Illustrator's document coordinates.
        var left = board[0] + 40;
        var top = board[1] - 60;
        var layer = doc.layers.add();
        layer.name = "SCI_DEMO";
        var blue = new RGBColor();
        blue.red = 35; blue.green = 104; blue.blue = 180;
        var white = new RGBColor();
        white.red = 255; white.green = 255; white.blue = 255;
        var box = layer.pathItems.roundedRectangle(top, left, 440, 100, 12, 12);
        box.name = "SCI_NODE_hello";
        box.filled = true; box.fillColor = blue; box.stroked = false;
        var label = layer.textFrames.add();
        label.name = "SCI_TEXT_hello";
        label.contents = "Scientific Illustrator Agent";
        label.textRange.characterAttributes.size = 18;
        label.textRange.characterAttributes.fillColor = white;
        var fontName = "default";
        try {
            var font = app.textFonts.getByName("ArialMT");
            label.textRange.characterAttributes.textFont = font;
            fontName = font.name;
        } catch (fontError) { /* Keep installed default if Arial is unavailable. */ }
        label.left = left + (440 - label.width) / 2;
        label.top = top - (100 - label.height) / 2;
        var line = layer.pathItems.add();
        line.name = "SCI_EDGE_hello";
        line.setEntirePath([[left, top - 130], [left + 440, top - 130]]);
        line.filled = false; line.stroked = true;
        line.strokeColor = blue; line.strokeWidth = 1;
        app.redraw();
        return "Created rounded rectangle, editable text and line; font=" + fontName;
    } finally {
        app.coordinateSystem = previousSystem;
    }
}());
