/* Local renderer commands contain values only, never executable user scripts. */
"use strict";
const message = document.getElementById("message");
const profileAxes = document.getElementById("profile-axes");
const state = {ready: false, js_ready: false, source_requested: false, errors: [], mode: "Classification", classes: null, height_filter: null, quality: "Automatic", script_revision: "visualization-analytics-1", available_modes: [], dimensions: [], display_range: null, legend: null, analytics: null, analytics_generation: 0, analytics_updates: 0, analytics_sample_limit: 30000};
let viewer, cloud, heightVolume, previousCamera = "", lastFrame = performance.now(), frameMs = 16;
let linkedContext = null, profileDragInstalled = false;
let cameraSyncFallbacks = 0;
const ATTRIBUTE_MODES = ["RGB", "Classification", "Elevation", "Height Above Ground", "Intensity", "Return Number", "Number of Returns", "Scan Angle", "Point Source ID", "GPS Time", "User Data"];
const ATTRIBUTE_ALIASES = {
    "RGB": ["Red", "Green", "Blue"], "Classification": ["Classification"],
    "Elevation": ["Z"], "Height Above Ground": ["HeightAboveGround", "_pfsHag"],
    "Intensity": ["Intensity"], "Return Number": ["ReturnNumber"],
    "Number of Returns": ["NumberOfReturns"], "Scan Angle": ["ScanAngleRank", "ScanAngle"],
    "Point Source ID": ["PointSourceId", "PointSourceID"], "GPS Time": ["GpsTime", "GPSTime"],
    "User Data": ["UserData"]
};
function sourceDimensions() {
    const attrs = cloud && cloud.pcoGeometry && cloud.pcoGeometry.pointAttributes && cloud.pcoGeometry.pointAttributes.attributes;
    return (attrs || []).map(attribute => attribute.name || attribute).filter(Boolean);
}
function modeAttribute(mode) {
    const names = new Set(sourceDimensions().map(value => String(value).toLowerCase()));
    const aliases = ATTRIBUTE_ALIASES[mode] || [];
    if (mode === "RGB") {
        if (names.has("rgba") || aliases.every(name => names.has(name.toLowerCase()))) return "rgba";
        return null;
    }
    const candidate = aliases.find(name => names.has(name.toLowerCase()));
    if (candidate) return candidate;
    if (mode === "Elevation" && (names.has("z") || names.has("position_cartesian") || names.has("position"))) return "elevation";
    const builtins = {"Classification":"classification", "Intensity":"intensity"};
    return builtins[mode] && names.has(builtins[mode]) ? builtins[mode] : null;
}
function updateVisualizationMetadata() {
    state.dimensions = sourceDimensions();
    state.available_modes = ATTRIBUTE_MODES.filter(mode => !!modeAttribute(mode));
    if (!state.available_modes.includes(state.mode)) state.mode = state.available_modes[0] || "Classification";
    updateLegend();
    updateScales();
}
function niceStep(span, target=5) {
    if (!(span > 0)) return 1;
    const raw = span / target, exponent = Math.floor(Math.log10(raw)), scale = 10 ** exponent;
    const normalized = raw / scale;
    return (normalized <= 1 ? 1 : normalized <= 2 ? 2 : normalized <= 5 ? 5 : 10) * scale;
}
function niceTicks(minimum, maximum, target=5) {
    if (!Number.isFinite(minimum) || !Number.isFinite(maximum) || minimum >= maximum) return [minimum, maximum];
    const step = niceStep(maximum - minimum, target), start = Math.ceil(minimum / step - 1e-9) * step;
    const ticks = [];
    for (let value = start; value <= maximum + step * 1e-9 && ticks.length < 12; value += step) ticks.push(Number(value.toPrecision(12)));
    return ticks.length ? ticks : [minimum, maximum];
}
function updateScales() {
    if (!viewer || !cloud) return;
    const radius = viewer.scene.view.radius;
    const groundStep = niceStep(Math.max(radius * .22, .001), 4);
    const vertical = state.display_range || state.z_range;
    const verticalStep = vertical ? niceStep(Math.max(Number(vertical[1]) - Number(vertical[0]), .001), 5) : null;
    const scaleText = `Ground scale: ${groundStep < 1 ? groundStep.toFixed(2) : groundStep.toFixed(0)} source units`;
    const verticalText = verticalStep ? `Vertical scale: ${verticalStep < 1 ? verticalStep.toFixed(2) : verticalStep.toFixed(0)} ${state.mode === "Height Above Ground" ? "HAG" : "elevation"} units` : "Vertical scale unavailable";
    if (state.scales && state.scales.ground === scaleText && state.scales.vertical === verticalText) return;
    state.scales = {ground: scaleText, vertical: verticalText};
    const ground = document.getElementById("spatial-scale"), verticalNode = document.getElementById("vertical-scale");
    if (ground) ground.textContent = scaleText;
    if (verticalNode) verticalNode.textContent = verticalText;
}

function classificationColorHex(code) {
    const entry = viewer && viewer.classifications &&
        (viewer.classifications[code] || viewer.classifications.DEFAULT);
    const color = entry && entry.color;
    if (!color) return "#aab4bb";
    const values = Array.isArray(color) ? color : [color.r, color.g, color.b];
    const scale = values.some(value => Number(value) > 1) ? 1 : 255;
    return "#" + values.slice(0, 3).map(value =>
        Math.max(0, Math.min(255, Math.round(Number(value || 0) * scale))).toString(16).padStart(2, "0")).join("");
}
function updateLegend() {
    if (!cloud) return;
    const range = state.display_range || state.z_range;
    const units = state.mode === "Height Above Ground" || state.mode === "Elevation" ? "source height units" : "display values";
    const labels = {2:"Ground", 3:"Low vegetation", 4:"Medium vegetation", 5:"High vegetation", 6:"Building", 7:"Low noise", 18:"High noise"};
    const categories = state.mode === "Classification" ? (state.observed_classes || []).slice(0, 12).map(code => ({
        code, label: labels[code] || (viewer.classifications[code] && viewer.classifications[code].name) || `Class ${code}`,
        color: classificationColorHex(code), visible: !state.classes || state.classes.includes(code)
    })) : [];
    state.legend = {title: state.mode, units, range: range || null, ticks: range ? niceTicks(Number(range[0]), Number(range[1])) : [], categories, available: state.available_modes};
    const node = document.getElementById("visual-legend");
    if (!node) return;
    if (state.mode === "Classification" && categories.length) {
        node.replaceChildren();
        const title = document.createElement("strong");
        title.textContent = "Classification | ";
        node.appendChild(title);
        categories.forEach((item, index) => {
            if (index) node.appendChild(document.createTextNode(" · "));
            const swatch = document.createElement("span");
            swatch.style.cssText = `display:inline-block;width:9px;height:9px;margin-right:3px;background:${item.color};border:1px solid rgba(255,255,255,.65);opacity:${item.visible ? 1 : .35}`;
            swatch.setAttribute("aria-label", `${item.label} color`);
            node.appendChild(swatch);
            node.appendChild(document.createTextNode(`${item.label} ${item.visible ? "shown" : "hidden"}`));
        });
        return;
    }
    node.textContent = state.legend.range ? `${state.mode} | ${state.legend.range[0].toFixed(2)}–${state.legend.range[1].toFixed(2)} ${units}` : state.mode;
}
function updateAnalytics() {
    if (!cloud || !state.ready) return;
    const values = [], classes = {}, limit = 30000;
    for (const node of cloud.visibleNodes || []) {
        const geometry = node.geometryNode && node.geometryNode.geometry;
        if (!geometry) continue;
        const attributeName = modeAttribute(state.mode);
        const attribute = geometry.getAttribute(attributeName === "elevation" ? "position" : attributeName) ||
            geometry.getAttribute(attributeName ? attributeName.toLowerCase() : "");
        const classification = geometry.getAttribute("classification");
        const count = Math.min(attribute ? attribute.count : 0, limit - values.length);
        for (let index = 0; index < count; index++) {
            const value = attribute.itemSize === 1 ? attribute.array[index] : attribute.array[index * attribute.itemSize + 2];
            if (Number.isFinite(value)) values.push(value);
            if (classification && index < classification.count) {
                const code = classification.array[index]; classes[code] = (classes[code] || 0) + 1;
            }
        }
        if (values.length >= limit) break;
    }
    values.sort((a, b) => a - b);
    const minimum = values.length ? values[0] : null, maximum = values.length ? values[values.length - 1] : null;
    const percentile = p => values.length ? values[Math.min(values.length - 1, Math.floor((values.length - 1) * p))] : null;
    state.analytics = {scope: "VISIBLE VIEW", sample_points: values.length, minimum, maximum, robust_range: [percentile(.02), percentile(.98)], classes, bounded: true, mode: state.mode, generation: state.analytics_generation};
    state.analytics_updates++;
    const node = document.getElementById("visual-analytics");
    if (node) node.textContent = values.length ? `VISIBLE VIEW | ${values.length.toLocaleString()} sampled points | ${state.mode}: ${minimum.toFixed(2)}–${maximum.toFixed(2)}` : "VISIBLE VIEW | Waiting for display sample";
}

function renderProfileHistogram(stats) {
    const node = document.getElementById("profile-histogram");
    if (!node) return;
    node.replaceChildren();
    const bins = stats && Array.isArray(stats.histogram) ? stats.histogram : [];
    if (!bins.length) { node.style.display = "none"; return; }
    node.style.display = "flex";
    const peak = Math.max(...bins.map(bin => Number(bin.count) || 0), 1);
    bins.forEach(bin => {
        const bar = document.createElement("span");
        bar.style.height = `${Math.max(2, 100 * (Number(bin.count) || 0) / peak)}%`;
        bar.title = `${bin.minimum}–${bin.maximum}: ${bin.count.toLocaleString()} points`;
        node.appendChild(bar);
    });
}
function updateProfileAxes() {
    const profile = linkedContext && linkedContext.view_type === "VERTICAL_SLICE" &&
        linkedContext.display_projection === "PROFILE_DISTANCE";
    profileAxes.style.display = profile ? "block" : "none";
    if (!profile || !cloud) {
        state.profile_axes = null;
        renderProfileHistogram(null);
        return;
    }
    const geometry = linkedContext.geometry || {};
    const path = Array.isArray(geometry.path) && geometry.path.length > 1 ?
        geometry.path : [geometry.a, geometry.b];
    const length = path.slice(1).reduce((sum, point, index) =>
        sum + Math.hypot(point[0]-path[index][0],point[1]-path[index][1]),0);
    cloud.updateMatrixWorld(true);
    const bounds = cloud.boundingBox.clone().applyMatrix4(cloud.matrixWorld);
    const vertical = geometry.vertical_limits || [bounds.min.z,bounds.max.z];
    const unit = linkedContext.horizontal_unit || "source units";
    const verticalUnit = linkedContext.vertical_unit || "source height units";
    const axis = geometry.vertical_axis === "HeightAboveGround" ? "Height above ground" : "Elevation";
    const distanceTicks = niceTicks(0, length);
    document.getElementById("profile-x-min").textContent = distanceTicks[0] ?? "0";
    document.getElementById("profile-x-max").textContent = distanceTicks[distanceTicks.length - 1] ?? length.toFixed(1);
    document.getElementById("profile-x-title").textContent = `Distance along profile (${unit})`;
    const verticalTicks = niceTicks(Number(vertical[0]), Number(vertical[1]));
    document.getElementById("profile-y-min").textContent = Number(verticalTicks[0]).toFixed(1);
    document.getElementById("profile-y-max").textContent = Number(verticalTicks[verticalTicks.length - 1]).toFixed(1);
    document.getElementById("profile-y-title").textContent = `${axis} (${verticalUnit})`;
    state.profile_axes = {distance:[0,length],vertical:[Number(vertical[0]),Number(vertical[1])],
        horizontal_unit:unit,vertical_unit:verticalUnit,vertical_axis:axis,
        analytics_scope: linkedContext.profile_analytics ? "AUTHORITATIVE PROFILE CORRIDOR" : "UNAVAILABLE"};
    renderProfileHistogram(linkedContext.profile_analytics);
}
function syncRenderCameras() {
    const view = viewer.scene.view;
    const active = viewer.scene.getActiveCamera();
    if (active.position.distanceToSquared(view.position) < 1e-12) return;
    for (const camera of [viewer.scene.cameraP, viewer.scene.cameraO]) {
        camera.position.copy(view.position);
        camera.rotation.order = "ZXY";
        camera.rotation.x = Math.PI / 2 + view.pitch;
        camera.rotation.z = view.yaw;
        camera.updateMatrix();
        camera.updateMatrixWorld();
        camera.matrixWorldInverse.copy(camera.matrixWorld).invert();
    }
    cameraSyncFallbacks++;
}
function cameraSnapshot() {
    const view = viewer.scene.view;
    return {position: view.position.toArray(), yaw: view.yaw, pitch: view.pitch, radius: view.radius};
}
function fitSource(reason) {
    cloud.updateMatrixWorld(true);
    const bounds = cloud.boundingBox.clone().applyMatrix4(cloud.matrixWorld);
    const sourceBounds = {min: bounds.min.toArray(), max: bounds.max.toArray()};
    const view = viewer.scene.view;
    const framing = viewerRenderPolicy.framing(sourceBounds, view.yaw, view.pitch, viewer.scene.cameraP.fov);
    const before = cameraSnapshot();
    state.framing = {reason, bounds: sourceBounds, before, checks: [], fallback_used: false};
    viewer.fitToScreen(0);
    const ensureFramed = checkpoint => {
        const fitted = cameraSnapshot();
        let fallback = false;
        if (!viewerRenderPolicy.framed(fitted, framing)) {
            view.position.set(...framing.position);
            view.lookAt(...framing.center);
            fallback = true;
        }
        state.framing.checks.push({checkpoint, fitted, fallback_used: fallback});
        state.framing.fallback_used = state.framing.fallback_used || fallback;
        state.framing.final = cameraSnapshot();
    };
    setTimeout(() => ensureFramed("event_loop"), 0);
    requestAnimationFrame(() => ensureFramed("animation_frame"));
    setTimeout(() => ensureFramed("settled"), 250);
}
function fitProfile() {
    const geometry = linkedContext.geometry;
    viewer.setCameraMode(Potree.CameraMode.ORTHOGRAPHIC);
    viewer.scene.view.yaw = linkedContext.display_projection === "PROFILE_DISTANCE" ? 0 :
        Math.atan2(geometry.b[1]-geometry.a[1], geometry.b[0]-geometry.a[0]);
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
let rgbChecked = 0, rgbNonzero = false, lastAnalytics = 0;
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
    updateLegend();
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
function frame() {
    const now = performance.now();
    const elapsed = now - lastFrame;
    if (elapsed > 0 && elapsed < 1000) frameMs = frameMs * .9 + elapsed * .1;
    lastFrame = now;
    if (viewer) {
        viewer.update(Math.min(viewer.clock.getDelta(), .1), now);
        syncRenderCameras();
        viewer.render();
    }
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
}
const renderTimer = setInterval(() => {
    try { frame(); }
    catch (error) {
        clearInterval(renderTimer);
        fail(error);
    }
}, 16);
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
            updateProfileAxes();
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
                updateProfileAxes();
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
            else fitSource("command_fit");
        }
        if (action === "top") { viewer.setTopView(); fitSource("command_top"); }
        if (action === "front") { viewer.setFrontView(); fitSource("command_front"); }
        if (action === "budget") {
            viewer.setPointBudget(Math.max(1000, Math.min(2000000, command.points)));
            const threshold = viewerRenderPolicy.threshold(viewer.minNodeSize, command.screen_error);
            viewer.minNodeSize = threshold;
            // Keep the cloud usable even when an embedded/occluded render loop has
            // not yet propagated the Viewer setting during source startup.
            cloud.minimumNodePixelSize = threshold;
            residentLimit = Math.max(command.ceiling, command.points) * (command.pressure >= .85 ? 1.25 : 2);
            Potree.maxNodesLoading = command.pressure >= .85 ? 2 : 4;
            state.quality_floor = command.floor;
            state.source_class = command.source_class;
        }
        if (action === "mode") {
            const attribute = modeAttribute(command.mode);
            if (!attribute || !state.available_modes.includes(command.mode)) throw Error(`Display mode unavailable: ${command.mode}.`);
            cloud.material.activeAttributeName = attribute;
            state.mode = command.mode;
            state.analytics_generation++;
            updateLegend();
            if (command.mode === "RGB") rgbRenderError = "";
        }
        if (action === "classes") {
            state.classes = command.classes.slice();
            for (let i = 0; i < 256; i++) setClassVisibility(i, command.classes.includes(i));
        }
        if (action === "display_range_mode") {
            const mode = String(command.mode || "AUTO").toUpperCase();
            if (!["AUTO", "ROBUST"].includes(mode)) throw Error("Unsupported display range mode.");
            state.display_range_mode = mode;
            state.analytics_generation++;
            const range = mode === "ROBUST" && state.analytics && state.analytics.robust_range && state.analytics.robust_range[0] !== null ?
                state.analytics.robust_range : state.z_range;
            state.display_range = mode === "AUTO" ? null : range;
            if (state.mode === "Elevation" && range) cloud.material.elevationRange = range;
            if (state.mode === "Intensity" && range) cloud.material.intensityRange = range;
            updateLegend();
        }
        if (action === "display_range") {
            const low = Number(command.minimum), high = Number(command.maximum);
            if (!Number.isFinite(low) || !Number.isFinite(high) || low >= high) throw Error("Display range minimum must be below maximum.");
            state.display_range = [low, high];
            state.display_range_mode = String(command.mode || "MANUAL").toUpperCase();
            state.analytics_generation++;
            if (state.mode === "Elevation") cloud.material.elevationRange = [low, high];
            if (state.mode === "Intensity") cloud.material.intensityRange = [low, high];
            updateLegend();
        }
        if (action === "display_range_clear") {
            state.display_range = null;
            state.display_range_mode = "AUTO";
            state.analytics_generation++;
            if (state.mode === "Elevation" && state.z_range) cloud.material.elevationRange = state.z_range;
            updateLegend();
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
    if (performance.now() - lastAnalytics > 350) { lastAnalytics = performance.now(); updateAnalytics(); updateScales(); }
    const view = viewer.scene.view;
    const camera = {position: view.position.toArray(), yaw: view.yaw, pitch: view.pitch, radius: view.radius};
    const key = JSON.stringify(camera);
    const moving = viewerRenderPolicy.moving(cameraVelocity, lastMotion, performance.now());
    previousCamera = key;
    const nodes = cloud.visibleNodes || [];
    const levels = nodes.map(n => n.geometryNode.level);
    const root = cloud.pcoGeometry.root;
    const activeCamera = viewer.scene.getActiveCamera();
    state.render_diagnostics = {
        visible_nodes: nodes.length, loaded_nodes: Potree.lru ? Potree.lru.elements : null,
        resident_points: Potree.lru ? Potree.lru.numPoints : null,
        pending_nodes: Potree.numNodesLoading, node_pixel_threshold: cloud.minimumNodePixelSize,
        viewer_node_threshold: viewer.minNodeSize, point_size: cloud.material.size,
        point_size_type: cloud.material.pointSizeType, point_shape: cloud.material.shape,
        root_points: root ? root.numPoints : null,
        lod_min: levels.length ? Math.min(...levels) : null, lod_max: levels.length ? Math.max(...levels) : null,
        fps: 1000 / frameMs, viewport_pixels: viewer.renderer.domElement.width * viewer.renderer.domElement.height,
        near: activeCamera.near, far: activeCamera.far,
        active_camera_position: activeCamera.position.toArray(),
        active_camera_rotation: activeCamera.rotation.toArray().slice(0, 3),
        camera_sync_fallbacks: cameraSyncFallbacks,
        cloud_visible: cloud.visible, cloud_position: cloud.position.toArray(),
        root_bounds: root ? {min: root.boundingBox.min.toArray(), max: root.boundingBox.max.toArray(),
            loaded: root.loaded, loading: root.loading} : null,
        scale: cloud.scale.toArray(), cache_limit_points: Potree.pointLoadLimit,
        js_heap_bytes: performance.memory ? performance.memory.usedJSHeapSize : null
    };
    state.render_diagnostics.cache_evictions = evictions;
    state.render_diagnostics.source_type = state.source_type || "UNKNOWN";
    state.render_diagnostics.dimensions = state.dimensions.slice();
    state.render_diagnostics.active_mode = state.mode;
    state.render_diagnostics.display_range = state.display_range;
    state.render_diagnostics.analytics_generation = state.analytics_generation;
    state.render_diagnostics.analytics_updates = state.analytics_updates;
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
    // QWebEngine can suspend animation callbacks after its native child is
    // embedded while timers and the command bridge remain active. This non-VR
    // viewer therefore owns one explicit Potree update/render timer above.
    viewer.renderer.setAnimationLoop(null);
    state.render_loop = "INTERVAL_16_MS";
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
    state.source_type = source.endsWith("ept.json") ? "EPT" : source.endsWith("cloud.copc.laz") ? "COPC" : "LAS/LAZ";
    Potree.loadPointCloud(source, "Point cloud", event => {
        cloud = event.pointcloud;
        viewer.scene.addPointCloud(cloud);
        cloud.minimumNodePixelSize = viewer.minNodeSize;
        cloud.material.activeAttributeName = "classification";
        updateVisualizationMetadata();
        pointDisplay(state.point_style, state.point_size);
        cloud.updateMatrixWorld(true);
        const bounds = cloud.boundingBox.clone().applyMatrix4(cloud.matrixWorld);
        state.z_range = [bounds.min.z, bounds.max.z];
        updateProfileAxes();
        fitSource("source_open");
        state.ready = true;
        message.textContent = "";
    });
} catch (error) { fail(error); }
