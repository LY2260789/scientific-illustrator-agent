// Native endpoint arrowheads, applied once to reusable path prototypes.
// Stroke action keys identify Illustrator's ahd1/ahd2, asc1/asc2 and ahal fields.
function nativeArrowOptions(item) {
    var input = item.arrowheads || {};
    return {
        start: input.start === undefined ? 0 : input.start,
        end: input.end === undefined ? 7 : input.end,
        startScale: input.start_scale === undefined ? 100 : input.start_scale,
        endScale: input.end_scale === undefined ? 100 : input.end_scale,
        align: input.align === undefined ? 0 : input.align
    };
}

function nativeArrowKey(item) {
    var o = nativeArrowOptions(item);
    return [o.start, o.end, o.startScale, o.endScale, o.align].join('_');
}

function installNativeArrowTemplates(scene, state, sessionKey) {
    var doc = app.activeDocument, styles = [], indices = {}, templates = {};
    var layer = null;
    state.arrowTemplates = templates;
    state.releaseArrows = function () {
        if (layer) { layer.visible = true; layer.remove(); layer = null; }
        state.arrowTemplates = {};
    };
    for (var i = 0; i < scene.items.length; i++) {
        var item = scene.items[i];
        if (item.kind !== 'arrow') continue;
        var key = nativeArrowKey(item);
        if (indices[key] === undefined) {
            indices[key] = styles.length;
            styles.push({key: key, options: nativeArrowOptions(item)});
        }
    }
    if (!styles.length) return;
    var locale = String(app.locale || $.locale);
    var prefixes = {en: 'Arrow ', ja: '\u77e2\u5370 ', zh: '\u7bad\u5934 '};
    var prefix = scene.arrowhead_prefix || prefixes[locale.substr(0, 2)];
    if (locale.indexOf('zh_TW') === 0 && !scene.arrowhead_prefix) prefix = '\u7bad\u982d ';
    if (!prefix) throw new Error('Set scene.arrowhead_prefix for Illustrator locale ' + locale);

    function encoded(text) {
        var bytes = unescape(encodeURIComponent(text)), hex = '';
        for (var c = 0; c < bytes.length; c++) hex += ('0' + bytes.charCodeAt(c).toString(16)).slice(-2);
        return '[ ' + bytes.length + ' ' + hex + ' ]';
    }
    function parameter(number, key, type, value) {
        return '/parameter-' + number + ' { /key ' + key +
            ' /showInPalette 4294967295 /type (' + type + ') ' + value + ' }\n';
    }
    var setName = 'SCI_ARROWS_' + sessionKey;
    var source = '/version 3\n/name ' + encoded(setName) + '\n/isOpen 0\n/actionCount ' + styles.length + '\n';
    for (i = 0; i < styles.length; i++) {
        var options = styles[i].options, params = '', count = 0;
        if (options.start) {
            params += parameter(++count, 1634231345, 'ustring', '/value ' + encoded(prefix + options.start));
            params += parameter(++count, 1634951985, 'real', '/value ' + options.startScale.toFixed(4));
        }
        if (options.end) {
            params += parameter(++count, 1634231346, 'ustring', '/value ' + encoded(prefix + options.end));
            params += parameter(++count, 1634951986, 'real', '/value ' + options.endScale.toFixed(4));
        }
        params += parameter(++count, 1634230636, 'enumerated', '/name [ 0 ] /value ' + options.align);
        source += '/action-' + (i + 1) + ' {\n/name ' + encoded('Arrow_' + i) +
            '\n/keyIndex 0\n/colorIndex 0\n/isOpen 0\n/eventCount 1\n/event-1 {\n' +
            '/useRulersIn1stQuadrant 0\n/internalName (ai_plugin_setStroke)\n' +
            '/localizedName [ 0 ]\n/isOpen 0\n/isOn 1\n/hasDialog 0\n' +
            '/parameterCount ' + count + '\n' + params + '}\n}\n';
    }
    var file = new File(Folder.temp.fsName + '/' + setName + '.aia'), loaded = false;
    try {
        file.encoding = 'ASCII';
        if (!file.open('w')) throw new Error('Cannot write temporary arrow action');
        file.write(source); file.close();
        app.loadAction(file); loaded = true;
        layer = doc.layers.add(); layer.name = '__' + setName;
        for (i = 0; i < styles.length; i++) {
            var path = layer.pathItems.add();
            path.setEntirePath([[0, 1000], [100, 1000]]);
            path.closed = false; path.filled = false; path.stroked = true; path.strokeWidth = 1;
            doc.selection = null; path.selected = true; app.redraw();
            app.doScript('Arrow_' + i, setName, false);
            var bounds = path.visibleBounds;
            if (bounds[1] - bounds[3] <= 1.01) throw new Error('Native arrow preset unavailable: ' + styles[i].key);
            templates[styles[i].key] = path;
        }
        doc.selection = null;
        doc.activeLayer = doc.layers.getByName(scene.items[0].layer);
        layer.visible = false;
        app.executeMenuCommand('fitin'); app.redraw();
    } catch (error) {
        state.releaseArrows(); throw error;
    } finally {
        doc.selection = null;
        if (loaded) app.unloadAction(setName, '');
        if (file.exists) file.remove();
    }
}
