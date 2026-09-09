/* Local renderer commands contain values only, never executable user scripts. */
"use strict";
const message = document.getElementById("message");
const state = {ready: false, js_ready: false, source_requested: false, errors: [], mode: "Classification", classes: null, height_filter: null};
let viewer, cloud, heightVolume, previousCamera = "", lastFrame = performance.now(), frameMs = 16;
const observedClasses = new Set(), scannedClasses = new WeakMap();
window.editorSelectionFilters = () => ({classes: state.classes, height_filter: state.height_filter});
window.editorClassificationColor = code => (viewer.classifications[code] || viewer.classifications.DEFAULT).color;
function inspectVisibleClasses() {
    // Inspect only resident buffers, with bounded work per telemetry tick.
    let remaining = 50000;
    for (const node of cloud.visibleNodes || []) {
        const geometry = node.geometryNode && node.geometryNode.geometry;
        const attribute = geometry && geometry.getAttribute("classification");
        if (!attribute) continue;
        const values = window.pointCloudEditor ? window.pointCloudEditor.originalClasses(attribute) : attribute.array;
        let offset = scannedClasses.get(values) || 0;
        const end = Math.min(values.length, offset + remaining);
        for (; offset < end; offset++) observedClasses.add(values[offset]);
        remaining -= end - (scannedClasses.get(values) || 0);
        scannedClasses.set(values, end);
        if (remaining <= 0) break;
    }
    state.observed_classes = Array.from(observedClasses).sort((a, b) => a - b);
}
function fail(error) {
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
        if (window.pointCloudEditor) window.pointCloudEditor.command(command);
        if (action === "snapshot") state.request_id = command.request_id;
        if (action === "orbit") { viewer.orbitControls.yawDelta += .25; viewer.orbitControls.pitchDelta += .1; }
        if (action === "pan") { viewer.orbitControls.panDelta.x += .05; }
        if (action === "zoom") { viewer.orbitControls.radiusDelta -= viewer.scene.view.radius * .2; }
        if (action === "navigation") viewer.setControls(command.mode === "Pan" ? viewer.earthControls : viewer.orbitControls);
        if (action === "fit") viewer.fitToScreen(0);
        if (action === "top") { viewer.setTopView(); viewer.fitToScreen(0); }
        if (action === "front") { viewer.setFrontView(); viewer.fitToScreen(0); }
        if (action === "budget") {
            viewer.setPointBudget(Math.max(1000, Math.min(2000000, command.points)));
            cloud.minimumNodePixelSize = command.screen_error;
        }
        if (action === "mode") {
            const names = {Classification: "classification", Elevation: "elevation", RGB: "rgba", Intensity: "intensity"};
            if (!names[command.mode]) throw Error("Unsupported render mode.");
            cloud.material.activeAttributeName = names[command.mode];
            state.mode = command.mode;
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
    const moving = previousCamera !== "" && previousCamera !== key;
    previousCamera = key;
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
    state.js_ready = true;
    const gl = viewer.renderer.getContext();
    viewer.renderer.domElement.addEventListener("webglcontextlost", () => fail(Error("The viewer graphics context was lost. Reload Viewer.")));
    state.webgl_information = {vendor: gl.getParameter(gl.VENDOR), renderer: gl.getParameter(gl.RENDERER), version: gl.getParameter(gl.VERSION)};
    const source = new URLSearchParams(location.search).get("source");
    if (!["source/cloud.copc.laz", "source/ept.json"].includes(source)) throw Error("Invalid source route.");
    state.source_requested = true;
    Potree.loadPointCloud(source, "Point cloud", event => {
        cloud = event.pointcloud;
        viewer.scene.addPointCloud(cloud);
        cloud.material.activeAttributeName = "classification";
        cloud.updateMatrixWorld(true);
        const bounds = cloud.boundingBox.clone().applyMatrix4(cloud.matrixWorld);
        state.z_range = [bounds.min.z, bounds.max.z];
        viewer.fitToScreen(0);
        state.ready = true;
        message.textContent = "";
    });
} catch (error) { fail(error); }
