import * as THREE from "./assets/libs/three.js/three.module.js";

let context, tool = "Pointer", rectangleStart = null, rectangleBox = null;
const drawing = new DrawingTool();
let drawingCamera = null, polygonOverlay = null, polygonLine = null;
let savedNavigation = null;
let mode = "REPLACE", eventNumber = 0, latestEvent = null, revision = 0, edits = [], selection = [];
const originals = new WeakMap(), records = new Map();
const point = new THREE.Vector3(), flat = new THREE.Vector3();
let pending = [], requestedRevision = 0;
let gestureMode = null;
let toolEpoch = 0, insertionPending = false;
let displaySignature = "";
let selectionColor = new THREE.Color("#5be4eb");

function publish(geometry) {
    const effectiveMode = gestureMode || mode;
    latestEvent = {id: ++eventNumber, geometry, mode: effectiveMode};
    const filters = window.editorSelectionFilters();
    const preview = compile({geometry, selection_mode: effectiveMode, classification_filter: filters.classes,
        z_filter: filters.height_filter, hag_filter: null, attribute_filters: []});
    selection = effectiveMode === "REPLACE" ? [preview] : [...selection, preview];
    revision++;
    for (const record of records.values()) record.revision = -1;
}
function compile(definition) {
    const ring = definition.geometry.slice(0, -1).map(p => new THREE.Vector2(p[0], p[1]));
    const triangles = THREE.ShapeUtils.triangulateShape(ring, []).map(face =>
        new THREE.Triangle(...face.map(i => new THREE.Vector3(ring[i].x, ring[i].y, 0))));
    return {...definition, triangles, bounds: [Math.min(...ring.map(p => p.x)),
        Math.min(...ring.map(p => p.y)), Math.max(...ring.map(p => p.x)), Math.max(...ring.map(p => p.y))]};
}
function matches(definitions, xyz, classification, geometry, index) {
    let selected = false;
    for (const item of definitions) {
        flat.set(xyz.x, xyz.y, 0);
        let hit = item.triangles.some(triangle => triangle.containsPoint(flat));
        if (item.legacy_bounds) {
            const b = item.legacy_bounds;
            hit = xyz.x >= b[0] && xyz.y >= b[1] && xyz.z >= b[2] &&
                  xyz.x <= b[3] && xyz.y <= b[4] && xyz.z <= b[5];
        }
        if (hit && item.z_filter) hit = xyz.z >= item.z_filter[0] && xyz.z <= item.z_filter[1];
        if (hit && item.classification_filter !== null) hit = item.classification_filter.includes(classification);
        const ranges = [...(item.attribute_filters || [])];
        if (item.hag_filter) ranges.push(["HeightAboveGround", ...item.hag_filter]);
        for (const [name, low, high] of ranges) {
            const attribute = geometry.getAttribute(name) || geometry.getAttribute(name.toLowerCase());
            if (!attribute || attribute.array[index] < low || attribute.array[index] > high) hit = false;
        }
        if (item.selection_mode === "REPLACE") selected = hit;
        else if (item.selection_mode === "ADD") selected = selected || hit;
        else selected = selected && !hit;
    }
    return selected;
}
function removeHighlight(record) {
    if (record.highlight) {
        context.viewer.scene.scene.remove(record.highlight);
        record.highlight.geometry.dispose();
        record.highlight.material.dispose();
        record.highlight = null;
    }
}
function leaveTool() {
    toolEpoch++;
    insertionPending = false;
    const viewer = context.viewer;
    if (polygonOverlay) polygonOverlay.remove();
    polygonOverlay = null; polygonLine = null; drawingCamera = null;
    if (rectangleBox) rectangleBox.remove();
    rectangleBox = null;
    rectangleStart = null;
    viewer.inputHandler.enabled = true;
    if (savedNavigation) {
        const view = viewer.scene.view;
        view.position.copy(savedNavigation.position);
        view.yaw = savedNavigation.yaw; view.pitch = savedNavigation.pitch;
        view.radius = savedNavigation.radius;
        viewer.setCameraMode(savedNavigation.cameraMode);
        savedNavigation = null;
    }
    gestureMode = null;
    tool = "Pointer";
}
function sourceXY(x, y, camera) {
    const canvas = context.viewer.renderer.domElement;
    return new THREE.Vector3(x / canvas.clientWidth * 2 - 1, 1 - y / canvas.clientHeight * 2, 0)
        .unproject(camera);
}
function drawPolygon(cursor) {
    if (!polygonLine) return;
    const points = cursor ? [...drawing.vertices, cursor] : drawing.vertices;
    polygonLine.setAttribute("points", points.map(p => p.join(",")).join(" "));
}
function completeDrawing() {
    const ring = drawing.close();
    if (ring) {
        publish(ring.map(p => {
            const xyz = sourceXY(p[0], p[1], drawingCamera);
            return [xyz.x, xyz.y];
        }));
        drawing.resolving();
    } else latestEvent = {id: ++eventNumber, error: drawing.error};
    leaveTool();
}
function initialize(value) {
    context = value;
    const canvas = context.viewer.renderer.domElement;
    canvas.addEventListener("pointerdown", event => {
        if (tool !== "Pointer" && gestureMode === null)
            gestureMode = event.altKey ? "SUBTRACT" : event.shiftKey ? "ADD" : mode;
        if (tool !== "Rectangle" || event.button !== 0) return;
        rectangleStart = [event.offsetX, event.offsetY];
        rectangleBox = document.createElement("div");
        rectangleBox.style.cssText = "position:absolute;border:2px dashed #5be4eb;pointer-events:none;box-sizing:border-box";
        canvas.parentElement.appendChild(rectangleBox);
        canvas.setPointerCapture(event.pointerId);
        event.preventDefault();
        event.stopPropagation();
    }, true);
    canvas.addEventListener("pointermove", event => {
        if (tool === "Polygon") drawPolygon([event.offsetX, event.offsetY]);
        if (!rectangleStart || !rectangleBox) return;
        const [x, y] = rectangleStart;
        Object.assign(rectangleBox.style, {left: Math.min(x, event.offsetX) + "px",
            top: Math.min(y, event.offsetY) + "px", width: Math.abs(event.offsetX - x) + "px",
            height: Math.abs(event.offsetY - y) + "px"});
    }, true);
    canvas.addEventListener("pointerup", event => {
        if (tool === "Polygon") {
            event.preventDefault();
            event.stopImmediatePropagation();
            if (event.button === 0) {
                const first = drawing.vertices[0];
                if (drawing.vertices.length >= 3 && first &&
                    Math.hypot(first[0]-event.offsetX, first[1]-event.offsetY) <= 6) completeDrawing();
                else { drawing.vertex(event.offsetX, event.offsetY); drawPolygon(); }
            }
            return;
        }
        if (!rectangleStart || tool !== "Rectangle") return;
        const [x, y] = rectangleStart, xx = event.offsetX, yy = event.offsetY;
        if (canvas.hasPointerCapture(event.pointerId)) canvas.releasePointerCapture(event.pointerId);
        if (Math.abs(x - xx) > 2 && Math.abs(y - yy) > 2) {
            for (const p of [[x,y], [xx,y], [xx,yy], [x,yy]]) drawing.vertex(...p);
            completeDrawing();
        } else { drawing.cancel(); leaveTool(); latestEvent = {id: ++eventNumber, action: "pointer"}; }
    }, true);
    canvas.addEventListener("dblclick", event => {
        if (tool !== "Polygon") return;
        event.preventDefault(); event.stopImmediatePropagation(); completeDrawing();
    }, true);
    canvas.addEventListener("contextmenu", event => {
        if (tool !== "Polygon") return;
        event.preventDefault(); event.stopImmediatePropagation(); completeDrawing();
    }, true);
    canvas.addEventListener("pointercancel", () => {
        if (tool === "Pointer") return;
        drawing.cancel(); leaveTool(); latestEvent = {id: ++eventNumber, action: "pointer"};
    }, true);
    document.addEventListener("keydown", event => {
        if (event.key === "Enter" && tool === "Polygon") {
            event.preventDefault(); completeDrawing();
        } else if (event.key === "Escape" && (tool !== "Pointer" || insertionPending)) {
            drawing.cancel();
            leaveTool();
            latestEvent = {id: ++eventNumber, action: "pointer"};
            event.preventDefault();
        } else if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "z") {
            latestEvent = {id: ++eventNumber, action: event.shiftKey ? "redo" : "undo"};
            event.preventDefault();
        }
    });
    requestAnimationFrame(paint);
}
function paint() {
    const start = performance.now();
    while (pending.length && performance.now() - start < 6) {
        const record = pending[0], {geometry, node, original} = record;
        const positions = geometry.getAttribute("position"), classes = geometry.getAttribute("classification");
        if (!classes || !positions) { pending.shift(); continue; }
        if (record.revision !== revision) {
            record.offset = 0;
            record.selected = [];
            record.colors = [];
            record.effectiveClasses = {};
            record.sourceUnchanged = true;
            record.revision = revision;
            removeHighlight(record);
            // Potree metadata bounds are cloud-relative, not node-buffer-relative.
            const box = node.geometryNode.boundingBox.clone().applyMatrix4(context.cloud.matrixWorld);
            record.edits = edits.filter(edit => edit.definitions.some(definition =>
                definition.selection_mode !== "SUBTRACT" && definition.bounds[0] <= box.max.x &&
                definition.bounds[2] >= box.min.x && definition.bounds[1] <= box.max.y && definition.bounds[3] >= box.min.y));
        }
        for (let n = 0; n < 64 && record.offset < original.length; n++, record.offset++) {
            const i = record.offset;
            if (classes.array[i] !== original[i]) record.sourceUnchanged = false;
            point.fromBufferAttribute(positions, i).applyMatrix4(node.sceneNode.matrixWorld);
            let classification = original[i], classified = false, withheld = false, removed = false;
            for (const edit of record.edits) {
                if (!matches(edit.definitions, point, original[i], geometry, i)) continue;
                if (edit.attribute === "Classification") { classification = edit.value; classified = true; }
                else if (edit.attribute === "Withheld") withheld = Boolean(edit.value);
                else if (edit.attribute === "DELETE_ON_EXPORT") removed = Boolean(edit.value);
            }
            record.effectiveClasses[classification] = (record.effectiveClasses[classification] || 0) + 1;
            const filters = window.editorSelectionFilters();
            const visible = (filters.classes === null || filters.classes.includes(original[i])) &&
                (!filters.height_filter || point.z >= filters.height_filter[0] && point.z <= filters.height_filter[1]);
            const selected = matches(selection, point, original[i], geometry, i);
            let color = null;
            if (selected) color = selectionColor.toArray();
            else if (removed) color = [1, .25, .65];
            else if (withheld) color = [1, .8, .2];
            else if (classified && context.cloud.material.activeAttributeName === "classification")
                color = window.editorClassificationColor(classification);
            if (visible && color) {
                record.selected.push(positions.getX(i), positions.getY(i), positions.getZ(i));
                record.colors.push(color[0], color[1], color[2]);
            }
        }
        if (record.offset >= original.length) {
            if (record.selected.length) {
                const highlighted = new THREE.BufferGeometry();
                highlighted.setAttribute("position", new THREE.Float32BufferAttribute(record.selected, 3));
                highlighted.setAttribute("color", new THREE.Float32BufferAttribute(record.colors, 3));
                record.highlight = new THREE.Points(highlighted,
                    new THREE.PointsMaterial({vertexColors: true, size: 3, sizeAttenuation: false, depthTest: false}));
                record.highlight.renderOrder = 1000;
                record.highlight.matrixAutoUpdate = false;
                record.highlight.matrix.copy(node.sceneNode.matrixWorld);
                context.viewer.scene.scene.add(record.highlight);
            }
            record.selected = [];
            record.colors = [];
            pending.shift();
        }
    }
    requestAnimationFrame(paint);
}
window.pointCloudEditor = {
    originalClasses(attribute) { return originals.get(attribute) || attribute.array; },
    tick(value) {
        if (!context) initialize(value);
        const signature = JSON.stringify(window.editorSelectionFilters()) + context.cloud.material.activeAttributeName;
        if (signature !== displaySignature) {
            displaySignature = signature;
            for (const record of records.values()) record.revision = -1;
        }
        const visible = new Set(context.cloud.visibleNodes || []);
        for (const [node, record] of records) if (!visible.has(node)) {
            removeHighlight(record);
            records.delete(node);
        }
        for (const node of visible) {
            const geometry = node.geometryNode && node.geometryNode.geometry;
            const classes = geometry && geometry.getAttribute("classification");
            if (!classes || !node.sceneNode) continue;
            if (!originals.has(classes)) originals.set(classes, classes.array.slice());
            if (!records.has(node)) records.set(node, {node, geometry, original: originals.get(classes), revision: -1, offset: 0});
        }
        pending = Array.from(records.values()).filter(r => r.revision !== revision || r.offset < r.original.length);
        const effectiveClasses = {};
        let highlighted = 0;
        for (const record of records.values()) {
            if (record.highlight) highlighted += record.highlight.geometry.getAttribute("position").count;
            for (const [code, count] of Object.entries(record.effectiveClasses || {}))
                effectiveClasses[code] = (effectiveClasses[code] || 0) + count;
        }
        return {event: latestEvent, tool, drawing_state: drawing.state, revision, pending_nodes: pending.length, ready: true,
            highlighted_points: highlighted, effective_classes: effectiveClasses,
            source_buffers_unchanged: Array.from(records.values()).every(r => r.sourceUnchanged !== false),
            overlay_diagnostics: Array.from(records.values()).slice(0, 3).map(r => ({
                node: r.node.name, edits: (r.edits || []).length,
                local_bounds: r.geometry.boundingBox && [r.geometry.boundingBox.min.toArray(), r.geometry.boundingBox.max.toArray()],
                translation: r.node.sceneNode.matrixWorld.elements.slice(12, 15)
            }))};
    },
    command(command) {
        if (!context) return;
        if (command.action === "selection_tool") {
            if (!["Pointer", "Polygon", "Rectangle"].includes(command.tool)) return;
            if (command.mode && !["REPLACE", "ADD", "SUBTRACT"].includes(command.mode)) return;
            leaveTool();
            drawing.cancel();
            mode = command.mode || "REPLACE";
            if (command.tool === "Pointer") {
                return;
            }
            const view = context.viewer.scene.view;
            if (view) savedNavigation = {position: view.position.clone(), yaw: view.yaw,
                pitch: view.pitch, radius: view.radius,
                cameraMode: context.viewer.scene.cameraMode || Potree.CameraMode.PERSPECTIVE};
            context.viewer.setCameraMode(Potree.CameraMode.ORTHOGRAPHIC);
            context.viewer.setTopView();
            const epoch = toolEpoch;
            insertionPending = true;
            requestAnimationFrame(() => requestAnimationFrame(() => {
                if (epoch !== toolEpoch) return;
                insertionPending = false;
                tool = command.tool;
                drawing.arm(tool, mode);
                drawingCamera = context.viewer.scene.getActiveCamera().clone();
                context.viewer.inputHandler.enabled = false;
                if (tool === "Polygon") {
                    polygonOverlay = document.createElementNS("http://www.w3.org/2000/svg", "svg");
                    polygonOverlay.style.cssText = "position:absolute;inset:0;width:100%;height:100%;pointer-events:none";
                    polygonLine = document.createElementNS("http://www.w3.org/2000/svg", "polyline");
                    polygonLine.setAttribute("fill", "none");
                    polygonLine.setAttribute("stroke", "#5be4eb");
                    polygonLine.setAttribute("stroke-width", "2");
                    polygonOverlay.appendChild(polygonLine);
                    context.viewer.renderer.domElement.parentElement.appendChild(polygonOverlay);
                }
            }));
        }
        if (command.action === "selection_resolution") {
            if (command.error) drawing.fail(command.error);
            else drawing.resolved();
        }
        if (command.action === "selection_test") publish(command.geometry);
        if (command.action === "editor_overlay") {
            if (/^#[0-9a-f]{6}$/i.test(command.selection_color || "")) selectionColor.set(command.selection_color);
            const request = ++requestedRevision;
            fetch("editor-overlay.json").then(response => {
                if (!response.ok) throw Error("Overlay state unavailable.");
                return response.json();
            }).then(data => {
                if (request !== requestedRevision) return;
                edits = data.edits.map(edit => ({...edit, definitions: edit.definitions.map(compile)}));
                selection = data.selection.map(compile);
                revision = data.revision;
                for (const record of records.values()) record.revision = -1;
            }).catch(error => { latestEvent = {id: ++eventNumber, error: String(error)}; });
        }
    }
};
