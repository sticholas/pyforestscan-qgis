/* Renderer-only policy: never changes scientific data or selection identity. */
(function(root) {
    "use strict";
    const policy = {
        motion(previous, current, elapsed, velocity, lastMotion, now) {
            if (!previous || elapsed <= 0 || elapsed >= 1000) return {velocity, lastMotion};
            const radius = Math.max(current[5], .01);
            const translation = Math.hypot(...current.slice(0, 3).map((x, i) => x - previous[i])) / radius;
            const yaw = Math.atan2(Math.sin(current[3] - previous[3]), Math.cos(current[3] - previous[3]));
            const delta = translation + Math.abs(yaw) + Math.abs(current[4] - previous[4]) + Math.abs(current[5] - previous[5]) / radius;
            return {velocity: .8 * velocity + .2 * delta * 1000 / elapsed,
                    lastMotion: delta > .00005 ? now : lastMotion};
        },
        moving(velocity, lastMotion, now) { return now - lastMotion < 180 && velocity > .0001; },
        threshold(previous, target) {
            // Global LOD deadband prevents jitter; no change to octree ownership.
            return Math.abs(target - previous) < .15 ? previous : previous + (target - previous) * .2;
        },
        retain(name, visible, lastSeen, now, residentPoints, limit) {
            if (visible.some(child => child.startsWith(name))) return true;
            return now - lastSeen < 1000 && residentPoints < limit * 1.25;
        },
        size(manual = 0) {
            if (!Number.isInteger(manual) || manual < 0 || manual > 16) throw new RangeError("Point size must be Automatic or 1-16 pixels.");
            return manual === 0 ? {minimum: 2, maximum: 5, scale: 1} :
                {minimum: manual, maximum: manual, scale: manual};
        },
        appearance(style, size) {
            if (!["Circular", "Square"].includes(style)) throw new RangeError("Unknown point style.");
            return {style, size, material: this.size(size)};
        },
        framing(bounds, yaw, pitch, fov = 60) {
            const values = [...bounds.min, ...bounds.max, yaw, pitch, fov];
            if (values.some(value => !Number.isFinite(value)) || fov <= 0 || fov >= 180)
                throw new RangeError("Source framing values must be finite.");
            const extent = bounds.max.map((value, index) => value - bounds.min[index]);
            if (extent.some(value => value < 0) || Math.hypot(...extent) <= 0)
                throw new RangeError("Source bounds must have a positive extent.");
            const center = bounds.min.map((value, index) => (value + bounds.max[index]) / 2);
            const sourceRadius = Math.hypot(...extent) / 2;
            const distance = sourceRadius / Math.sin(fov * Math.PI / 360);
            const cosPitch = Math.cos(pitch);
            const backward = [Math.sin(yaw) * cosPitch, -Math.cos(yaw) * cosPitch, -Math.sin(pitch)];
            return {center, source_radius: sourceRadius, radius: distance,
                    position: center.map((value, index) => value + backward[index] * distance)};
        },
        framed(camera, framing) {
            const values = [...camera.position, camera.radius, ...framing.center,
                framing.source_radius, framing.radius];
            if (values.some(value => !Number.isFinite(value)) || camera.radius <= 0) return false;
            const distance = Math.hypot(...camera.position.map((value, index) => value - framing.center[index]));
            return camera.radius >= framing.source_radius * .5 && camera.radius <= framing.radius * 10 &&
                distance >= framing.source_radius * .5 && distance <= framing.radius * 10;
        },
        objectFocus(mode, hasSelection) {
            if (!["SHOW_ALL", "FADE_OTHERS", "ISOLATE"].includes(mode))
                throw new RangeError("Unknown object focus mode.");
            if (typeof hasSelection !== "boolean") throw new TypeError("Object focus selection state must be boolean.");
            const effective = hasSelection ? mode : "SHOW_ALL";
            return {requested: mode, effective,
                    opacity: effective === "FADE_OTHERS" ? 0.12 : effective === "ISOLATE" ? 0 : 1};
        }
    };
    root.viewerRenderPolicy = policy;
    if (typeof module !== 'undefined') module.exports = policy;
})(typeof window === 'undefined' ? globalThis : window);
