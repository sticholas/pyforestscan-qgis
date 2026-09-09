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
        size() { return {minimum: 2, maximum: 5, scale: 1}; }
    };
    root.viewerRenderPolicy = policy;
    if (typeof module !== 'undefined') module.exports = policy;
})(typeof window === 'undefined' ? globalThis : window);
