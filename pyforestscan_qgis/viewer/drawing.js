/* Shared screen-gesture state. Source-space authority stays in the resolver. */
(function(root) {
    "use strict";
    function distanceSquared(point, a, b) {
        const vx=b[0]-a[0], vy=b[1]-a[1], length=vx*vx+vy*vy;
        const t=length ? Math.max(0,Math.min(1,((point[0]-a[0])*vx+(point[1]-a[1])*vy)/length)) : 0;
        const dx=point[0]-(a[0]+t*vx), dy=point[1]-(a[1]+t*vy);
        return dx*dx+dy*dy;
    }
    function rdp(points, tolerance) {
        if (points.length <= 2) return points.map(point => point.slice());
        const keep=new Uint8Array(points.length); keep[0]=keep[points.length-1]=1;
        const stack=[[0,points.length-1]], threshold=tolerance*tolerance;
        while (stack.length) {
            const [start,end]=stack.pop();
            let farthest=-1, distance=-1;
            for (let i=start+1;i<end;i++) {
                const candidate=distanceSquared(points[i],points[start],points[end]);
                if (candidate > distance) { distance=candidate; farthest=i; }
            }
            if (distance > threshold) {
                keep[farthest]=1; stack.push([start,farthest],[farthest,end]);
            }
        }
        return points.filter((_point,index)=>keep[index]).map(point=>point.slice());
    }
    function simplifySourcePath(points, radius, maxVertices=512) {
        if (!Array.isArray(points) || points.length < 2 || !Number.isInteger(maxVertices) || maxVertices < 2 ||
                !Number.isFinite(radius) || radius <= 0 || points.some(point =>
                    !Array.isArray(point) || point.length !== 2 || !point.every(Number.isFinite)))
            throw Error("Brush simplification requires finite source XY points, radius and limit.");
        const unique=points.filter((point,index)=>!index || point[0]!==points[index-1][0] || point[1]!==points[index-1][1]);
        if (unique.length < 2) throw Error("Drag a longer brush stroke.");
        if (unique.length <= maxVertices)
            return {path:unique.map(point=>point.slice()),tolerance:0,original_count:unique.length};
        let low=radius/32, high=radius/4;
        let result=rdp(unique,high);
        if (result.length > maxVertices)
            return {path:null,tolerance:high,original_count:unique.length,
                error:"Brush stroke has too much detail for its radius. Increase Radius or draw a shorter stroke."};
        for (let iteration=0;iteration<20;iteration++) {
            const middle=(low+high)/2, candidate=rdp(unique,middle);
            if (candidate.length <= maxVertices) { high=middle; result=candidate; }
            else low=middle;
        }
        return {path:result,tolerance:high,original_count:unique.length};
    }
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
        finishPath(maxVertices = 512) {
            if (this.state === "FAILED") return null;
            if (this.state !== "DRAWING" || this.vertices.length < 2) {
                this.fail("Drag a longer brush stroke."); return null;
            }
            if (this.vertices.length > maxVertices) {
                this.fail("Brush stroke is too detailed. Draw a shorter stroke."); return null;
            }
            this.state = "PREVIEW";
            return this.vertices.map(point => point.slice());
        }
        resolving() { if (this.state === "PREVIEW") this.state = "RESOLVING"; }
        resolved() { if (this.state === "RESOLVING") this.state = "RESOLVED"; }
        fail(message) { this.error = message; this.state = "FAILED"; }
        cancel() { this.vertices = []; this.state = "CANCELLED"; this.generation++; }
    }
    root.DrawingTool = DrawingTool;
    root.simplifySourcePath = simplifySourcePath;
    if (typeof module !== "undefined") module.exports = {DrawingTool,simplifySourcePath};
})(globalThis);
