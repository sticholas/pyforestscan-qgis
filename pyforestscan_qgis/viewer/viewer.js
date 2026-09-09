/* Local renderer commands contain values only, never executable user scripts. */
"use strict";
const message = document.getElementById("message");
const state = {ready: false, js_ready: false, source_requested: false, errors: [], mode: "Classification", classes: null, height_filter: null, quality: "Automatic"};
let viewer, cloud, heightVolume, previousCamera = "", lastFrame = performance.now(), frameMs = 16;
let linkedContext = null, profileDragInstalled = false;
function fitProfile() {
    const geometry = linkedContext.geometry;
    viewer.setCameraMode(Potree.CameraMode.ORTHOGRAPHIC);
    viewer.scene.view.yaw = Math.atan2(geometry.b[1]-geometry.a[1], geometry.b[0]-geometry.a[0]);
    viewer.scene.view.pitch = 0;
    viewer.fitToScreen(0);
}
let priorView = null, cameraVelocity = 0, lastMotion = 0, evictions = 0;
const recentNodes = new WeakMap();
state.point_style = "Circular";
state.point_size = 0;
function pointDisplay(style, manual) {
    const display = viewerRenderPolicy.appearance(style, manual);
    cloud.material.shape = style === "Circular" ? Potree.PointShape.CIRCLE : Potree.PointShape.SQUARE;
    cloud.material.pointSizeType = manual === 0 ? Potree.PointSizeType.ADAPTIVE : Potree.PointSizeType.FIXED;
    cloud.material.size = display.material.scale;
    cloud.material.minSize = display.material.minimum;
    cloud.material.maxSize = display.material.maximum;
    state.point_style = style;
    state.point_size = manual;
}
let residentLimit = 2000000;
const observedClasses = new Set(), scannedClasses = new WeakMap();
let rgbChecked = 0, rgbNonzero = false;
const rawRGB = new RGBStats(), decodedRGB = new RGBStats(), rgbNodes = new WeakSet();
let rgbRenderError = "";
window.editorSelectionFilters = () => ({classes: state.classes, height_filter: state.height_filter});
window.editorClassificationColor = code => (viewer.classifications[code] || viewer.classifications.DEFAULT).color;
function inspectVisibleClasses() {
    // Inspect only resident buffers, with bounded work per telemetry tick.
    let remaining = 50000;
    for (const node of cloud.visibleNodes || []) {
        const raw = node.geometryNode && node.geometryNode.gpsTime && node.geometryNode.gpsTime.rgbDiagnostic;
        if (raw && !rgbNodes.has(node.geometryNode)) {
            rawRGB.merge(raw); rgbNodes.add(node.geometryNode);
        }
        const geometry = node.geometryNode && node.geometryNode.geometry;
        const attribute = geometry && geometry.getAttribute("classification");
        if (!attribute) continue;
        const values = window.pointCloudEditor ? window.pointCloudEditor.originalClasses(attribute) : attribute.array;
        let offset = scannedClasses.get(values) || 0;
        const end = Math.min(values.length, offset + remaining);
        const colors = geometry.getAttribute("rgba");
        for (; offset < end; offset++) {
            observedClasses.add(values[offset]);
            if (colors && offset < colors.count) {
                const i = offset * colors.itemSize;
                rgbNonzero = rgbNonzero || colors.array[i] > 0 || colors.array[i + 1] > 0 || colors.array[i + 2] > 0;
                rgbChecked++;
                decodedRGB.add(colors.array[i], colors.array[i+1], colors.array[i+2]);
            }
        }
        remaining -= end - (scannedClasses.get(values) || 0);
        scannedClasses.set(values, end);
        if (remaining <= 0) break;
    }
    state.observed_classes = Array.from(observedClasses).sort((a, b) => a - b);
    state.rgb_observation = rgbNonzero ? "NONZERO_OBSERVED" : rgbChecked ? "ZERO_SO_FAR" : "UNCHECKED";
    const owner = cloud.pcoGeometry;
    const header = owner.copc && owner.copc.header;
    const schema = owner.ept && owner.ept.schema;
    const present = rawRGB.count > 0 || (header ? [2,3,5,7,8,10].includes(Number(header.pointDataRecordFormat) & 63) :
        schema ? ["Red","Green","Blue"].every(name=>schema.some(a=>a.name===name)) : true);
    const stats = rawRGB.count || rawRGB.invalid ? rawRGB : decodedRGB;
    stats.present = present;
    state.rgb_diagnostic = stats.report(rgbRenderError, stats===rawRGB?"ORIGINAL_RGB":"DECODED_RGB");
}
function fail(error) {
    if (state.mode === "RGB") rgbRenderError = String(error.message || error);
    if (rgbRenderError) state.rgb_diagnostic = (rawRGB.count ? rawRGB : decodedRGB).report(
        rgbRenderError, rawRGB.count ? "ORIGINAL_RGB" : "DECODED_RGB");
    state.ready = false;
    const text = String(error.message || error).slice(0, 1000);
    state.errors = state.errors.slice(-7).concat(text);
    state.error_details = (state.error_details || []).slice(-7).concat(String(error.stack || error).slice(0, 4000));
    console.error(error.stack || text);
    message.textContent = text;
}
window.addEventListener("error", event => fail(event.error || event.message));
window.addEventListener("unhandledrejection", event => fail(event.reason));
function frame(now) {
    const elapsed = now - lastFrame;
    if (elapsed > 0 && elapsed < 1000) frameMs = frameMs * .9 + elapsed * .1;
    lastFrame = now;
    if (viewer && cloud) {
        const v = viewer.scene.view;
        const current = [...v.position.toArray(), v.yaw, v.pitch, v.radius];
        if (priorView && elapsed > 0 && elapsed < 1000) {
            const motion = viewerRenderPolicy.motion(priorView, current, elapsed, cameraVelocity, lastMotion, now);
            cameraVelocity = motion.velocity;
            lastMotion = motion.lastMotion;
        }
        priorView = current;
        for (const n of cloud.visibleNodes || []) recentNodes.set(n.geometryNode, now);
    }
    requestAnimationFrame(frame);
}
requestAnimationFrame(frame);
function clearHeight() {
    if (heightVolume) viewer.scene.removeVolume(heightVolume);
    heightVolume = null;
    state.height_filter = null;
    viewer.setClipTask(Potree.ClipTask.NONE);
}
function setClassVisibility(code, visible) {
    // Potree's setter creates unknown classes without a color. Its material
    // later indexes color[0], so supply a full style before using that setter.
    if (!viewer.classifications[code] || !viewer.classifications[code].color) {
        const fallback = viewer.classifications.DEFAULT;
        viewer.classifications[code] = {visible: !visible, name: "Class " + code, color: fallback.color.slice()};
    }
    viewer.setClassificationVisibility(code, visible);
}
window.command = function(command) {
    if (!cloud) return;
    try {
        const action = command.action;
        if (action === "point_display") pointDisplay(command.style, command.size);
        if (action === "linked_view") {
            linkedContext = command.view || null;
            if (linkedContext && linkedContext.view_type === "VERTICAL_SLICE") {
                viewer.setControls(viewer.orbitControls);
                viewer.orbitControls.rotationSpeed = 0;
                viewer.orbitControls.yawDelta = viewer.orbitControls.pitchDelta = 0;
                viewer.orbitControls.doubleClockZoomEnabled = false;
                if (!profileDragInstalled) {
                    viewer.orbitControls.addEventListener("drag", event => {
                        if (!linkedContext || linkedContext.view_type !== "VERTICAL_SLICE" ||
                            event.drag.object !== null || event.drag.mouse !== 1) return;
                        viewer.orbitControls.panDelta.x += event.drag.lastDrag.x/viewer.renderer.domElement.clientWidth;
                        viewer.orbitControls.panDelta.y += event.drag.lastDrag.y/viewer.renderer.domElement.clientHeight;
                    });
                    profileDragInstalled = true;
                }
                fitProfile();
            }
        }
        if (action === "quality") {
            if (!["Automatic", "Performance", "Balanced", "High Detail"].includes(command.quality)) throw Error("Invalid quality preset.");
            state.quality = command.quality;
        }
        if (window.pointCloudEditor) window.pointCloudEditor.command(command);
        if (action === "snapshot") state.request_id = command.request_id;
        if (action === "orbit") { viewer.orbitControls.yawDelta += .25; viewer.orbitControls.pitchDelta += .1; }
        if (action === "pan") { viewer.orbitControls.panDelta.x += .05; }
        if (action === "zoom") { viewer.orbitControls.radiusDelta -= viewer.scene.view.radius * .2; }
        if (action === "navigation") viewer.setControls(linkedContext && linkedContext.view_type === "VERTICAL_SLICE" ?
            viewer.orbitControls : command.mode === "Pan" ? viewer.earthControls : viewer.orbitControls);
        if (action === "fit") {
            if (linkedContext && linkedContext.view_type === "VERTICAL_SLICE") fitProfile();
            else viewer.fitToScreen(0);
        }
        if (action === "top") { viewer.setTopView(); viewer.fitToScreen(0); }
        if (action === "front") { viewer.setFrontView(); viewer.fitToScreen(0); }
        if (action === "budget") {
            viewer.setPointBudget(Math.max(1000, Math.min(2000000, command.points)));
            // Viewer.update owns this property; assigning it on the cloud is overwritten.
            viewer.minNodeSize = viewerRenderPolicy.threshold(viewer.minNodeSize, command.screen_error);
            residentLimit = Math.max(command.ceiling, command.points) * (command.pressure >= .85 ? 1.25 : 2);
            Potree.maxNodesLoading = command.pressure >= .85 ? 2 : 4;
            state.quality_floor = command.floor;
            state.source_class = command.source_class;
        }
        if (action === "mode") {
            const names = {Classification: "classification", Elevation: "elevation", RGB: "rgba", Intensity: "intensity"};
            if (!names[command.mode]) throw Error("Unsupported render mode.");
            cloud.material.activeAttributeName = names[command.mode];
            state.mode = command.mode;
            if (command.mode === "RGB") rgbRenderError = "";
        }
        if (action === "classes") {
            state.classes = command.classes.slice();
            for (let i = 0; i < 256; i++) setClassVisibility(i, command.classes.includes(i));
        }
        if (action === "height") {
            const low = Number(command.minimum), high = Number(command.maximum);
            if (!Number.isFinite(low) || !Number.isFinite(high) || low >= high) throw Error("Height minimum must be below maximum.");
            clearHeight();
            cloud.updateMatrixWorld(true);
            const bounds = cloud.boundingBox.clone().applyMatrix4(cloud.matrixWorld);
            const size = bounds.getSize(cloud.position.clone());
            const center = bounds.getCenter(cloud.position.clone());
            heightVolume = new Potree.BoxVolume({clip: true});
            heightVolume.position.copy(center);
            heightVolume.position.z = (low + high) / 2;
            heightVolume.scale.set(Math.max(size.x * 1.01, .01), Math.max(size.y * 1.01, .01), high - low);
            heightVolume.visible = false;
            heightVolume.updateMatrixWorld(true);
            viewer.scene.addVolume(heightVolume);
            viewer.setClipTask(Potree.ClipTask.SHOW_INSIDE);
            state.height_filter = [low, high];
        }
        if (action === "clear_height") clearHeight();
        if (action === "clear_filters") {
            state.classes = null;
            clearHeight();
            for (let i = 0; i < 256; i++) setClassVisibility(i, true);
        }
        if (action === "camera") {
            const camera = command.camera;
            if (camera.position.length !== 3 || !camera.position.every(Number.isFinite) ||
                ![camera.yaw, camera.pitch, camera.radius].every(Number.isFinite) || camera.radius <= 0) throw Error("Invalid camera.");
            viewer.scene.view.position.fromArray(camera.position);
            viewer.scene.view.yaw = camera.yaw;
            viewer.scene.view.pitch = camera.pitch;
            viewer.scene.view.radius = camera.radius;
        }
    } catch (error) { fail(error); }
};
window.snapshot = function() {
    if (!state.ready) return state;
    if (window.pointCloudEditor) state.editor = window.pointCloudEditor.tick({viewer, cloud});
    inspectVisibleClasses();
    const view = viewer.scene.view;
    const camera = {position: view.position.toArray(), yaw: view.yaw, pitch: view.pitch, radius: view.radius};
    const key = JSON.stringify(camera);
    const moving = viewerRenderPolicy.moving(cameraVelocity, lastMotion, performance.now());
    previousCamera = key;
    const nodes = cloud.visibleNodes || [];
    const levels = nodes.map(n => n.geometryNode.level);
    const root = cloud.pcoGeometry.root;
    state.render_diagnostics = {
        visible_nodes: nodes.length, loaded_nodes: Potree.lru ? Potree.lru.elements : null,
        resident_points: Potree.lru ? Potree.lru.numPoints : null,
        pending_nodes: Potree.numNodesLoading, node_pixel_threshold: cloud.minimumNodePixelSize,
        viewer_node_threshold: viewer.minNodeSize, point_size: cloud.material.size,
        point_size_type: cloud.material.pointSizeType, point_shape: cloud.material.shape,
        root_points: root ? root.numPoints : null,
        lod_min: levels.length ? Math.min(...levels) : null, lod_max: levels.length ? Math.max(...levels) : null,
        fps: 1000 / frameMs, viewport_pixels: viewer.renderer.domElement.width * viewer.renderer.domElement.height,
        near: viewer.scene.getActiveCamera().near, far: viewer.scene.getActiveCamera().far,
        scale: cloud.scale.toArray(), cache_limit_points: Potree.pointLoadLimit,
        js_heap_bytes: performance.memory ? performance.memory.usedJSHeapSize : null
    };
    state.render_diagnostics.cache_evictions = evictions;
    state.render_diagnostics.resident_limit_points = residentLimit;
    state.render_diagnostics.rendered_points = nodes.reduce((sum, n) => sum + n.geometryNode.numPoints, 0);
    state.render_diagnostics.points_per_megapixel = state.render_diagnostics.rendered_points * 1000000 / Math.max(1, state.render_diagnostics.viewport_pixels);
    state.render_diagnostics.gpu_upload_nodes_per_frame = 2;
    state.render_diagnostics.decode_queue = Potree.numNodesLoading;
    state.render_diagnostics.gpu_upload_queue = null;
    state.source_points = cloud.pcoGeometry.copc ? cloud.pcoGeometry.copc.header.pointCount : cloud.pcoGeometry.ept.points;
    state.camera_velocity = cameraVelocity;
    state.memory_pressure = performance.memory ? Math.min(1, performance.memory.usedJSHeapSize / performance.memory.jsHeapSizeLimit) : 0;
    state.memory_pressure_source = "JS_HEAP_RATIO; host also samples system RAM";
    state.detail = moving ? "Interactive" : performance.now() - lastMotion < 1500 ? "Refining" : "Available detail";
    return Object.assign({}, state, {displayed: cloud.numVisiblePoints, budget: viewer.getPointBudget(),
                                    frame_ms: frameMs, moving, camera, webgl: !!viewer.renderer.getContext()});
};
window.captureFrame = function() {
    if (!state.ready || viewer.renderer.getContext().isContextLost()) return "";
    const canvas = viewer.renderer.domElement;
    if (canvas.width * canvas.height > 8000000) return "";
    viewer.render();
    return canvas.toDataURL("image/png");
};
try {
    viewer = new Potree.Viewer(document.getElementById("view"), {noDragAndDrop: true});
    viewer.setBackground("black");
    viewer.setEDLEnabled(false);
    viewer.setPointBudget(100000);
    // Keep a stable cache ceiling during motion; never evict visible ancestors.
    const lru = Potree.lru;
    if (lru) {
        const remove = lru.remove.bind(lru);
        lru.remove = node => { if (lru.items[node.id]) evictions++; return remove(node); };
        lru.freeMemory = () => {
            const visible = cloud ? (cloud.visibleNodes || []).map(n => n.geometryNode.name) : [];
            const candidates = [];
            for (let item = lru.first; item; item = item.next) candidates.push(item.node);
            for (const node of candidates) {
                if (lru.numPoints <= residentLimit) break;
                if (!lru.items[node.id] || viewerRenderPolicy.retain(node.name, visible,
                    recentNodes.get(node) || 0, performance.now(), lru.numPoints, residentLimit)) continue;
                lru.disposeDescendants(node);
            }
        };
    }
    state.js_ready = true;
    const gl = viewer.renderer.getContext();
    viewer.renderer.domElement.addEventListener("webglcontextlost", event => {
        event.preventDefault(); state.context_lost = true;
        message.textContent = "Viewer graphics context was reset. Restoring view...";
    });
    viewer.renderer.domElement.addEventListener("webglcontextrestored", () => {
        state.context_lost = false; state.context_restores = (state.context_restores || 0) + 1;
        message.textContent = "";
    });
    state.webgl_information = {vendor: gl.getParameter(gl.VENDOR), renderer: gl.getParameter(gl.RENDERER), version: gl.getParameter(gl.VERSION)};
    const gpu = gl.getExtension('WEBGL_debug_renderer_info');
    if (gpu) state.webgl_information.graphics_device = gl.getParameter(gpu.UNMASKED_RENDERER_WEBGL);
    const source = new URLSearchParams(location.search).get("source");
    if (!["source/cloud.copc.laz", "source/ept.json"].includes(source)) throw Error("Invalid source route.");
    state.source_requested = true;
    Potree.loadPointCloud(source, "Point cloud", event => {
        cloud = event.pointcloud;
        viewer.scene.addPointCloud(cloud);
        cloud.material.activeAttributeName = "classification";
        pointDisplay(state.point_style, state.point_size);
        cloud.updateMatrixWorld(true);
        const bounds = cloud.boundingBox.clone().applyMatrix4(cloud.matrixWorld);
        state.z_range = [bounds.min.z, bounds.max.z];
        viewer.fitToScreen(0);
        state.ready = true;
        message.textContent = "";
    });
} catch (error) { fail(error); }
