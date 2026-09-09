/* Shared screen-gesture state. Source-space authority stays in the resolver. */
(function(root) {
    "use strict";
    class DrawingTool {
        constructor() { this.state = "IDLE"; this.vertices = []; this.error = ""; this.generation = 0; }
        arm(tool, mode = "REPLACE") {
            if (!["Polygon", "Rectangle"].includes(tool) || !["REPLACE", "ADD", "SUBTRACT"].includes(mode))
                throw Error("Unsupported drawing tool or selection mode.");
            this.generation++; this.tool = tool; this.mode = mode;
            this.vertices = []; this.error = ""; this.state = "ARMED";
        }
        vertex(x, y) {
            if (!["ARMED", "DRAWING"].includes(this.state)) return false;
            if (![x, y].every(Number.isFinite)) return false;
            const prior = this.vertices[this.vertices.length - 1];
            if (prior && Math.hypot(x - prior[0], y - prior[1]) < 2) return false;
            if (this.vertices.length >= 2048) { this.fail("Too many vertices; draw a simpler boundary."); return false; }
            this.vertices.push([x, y]); this.state = "DRAWING"; return true;
        }
        close() {
            if (this.state !== "DRAWING") { this.fail("Place at least three polygon vertices."); return null; }
            this.state = "CLOSING";
            const ring = this.vertices.map(p => p.slice());
            if (ring.length > 3 && Math.hypot(ring[0][0] - ring.at(-1)[0], ring[0][1] - ring.at(-1)[1]) < 2)
                ring.pop();
            const cross = (a,b,c) => (b[0]-a[0])*(c[1]-a[1]) - (b[1]-a[1])*(c[0]-a[0]);
            const on = (a,b,c) => Math.abs(cross(a,b,c)) < 1e-8 &&
                c[0] >= Math.min(a[0],b[0]) && c[0] <= Math.max(a[0],b[0]) &&
                c[1] >= Math.min(a[1],b[1]) && c[1] <= Math.max(a[1],b[1]);
            const intersects = (a,b,c,d) => cross(a,b,c)*cross(a,b,d) < 0 && cross(c,d,a)*cross(c,d,b) < 0 ||
                on(a,b,c) || on(a,b,d) || on(c,d,a) || on(c,d,b);
            if (ring.length < 3) { this.fail("Place at least three distinct vertices."); return null; }
            for (let i=0; i<ring.length; i++) for (let j=i+1; j<ring.length; j++) {
                if (j===i+1 || i===0 && j===ring.length-1) continue;
                if (intersects(ring[i],ring[(i+1)%ring.length],ring[j],ring[(j+1)%ring.length])) {
                    this.fail("Polygon edges intersect. Draw a simple boundary."); return null;
                }
            }
            const area = Math.abs(ring.reduce((sum,p,i) => {
                const q=ring[(i+1)%ring.length]; return sum+p[0]*q[1]-q[0]*p[1];
            },0))/2;
            if (area < 4) { this.fail("Selection is too small. Zoom in and draw a larger boundary."); return null; }
            ring.push(ring[0].slice()); this.state = "PREVIEW"; return ring;
        }
        resolving() { if (this.state === "PREVIEW") this.state = "RESOLVING"; }
        resolved() { if (this.state === "RESOLVING") this.state = "RESOLVED"; }
        fail(message) { this.error = message; this.state = "FAILED"; }
        cancel() { this.vertices = []; this.state = "CANCELLED"; this.generation++; }
    }
    root.DrawingTool = DrawingTool;
    if (typeof module !== "undefined") module.exports = {DrawingTool};
})(globalThis);
