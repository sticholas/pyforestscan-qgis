const assert=require("node:assert/strict");
const {DrawingTool,simplifySourcePath}=require("../../pyforestscan_qgis/viewer/drawing.js");
const {RGBStats}=require("../../pyforestscan_qgis/viewer/rgb.js");
for (const mode of ["REPLACE","ADD","SUBTRACT"]) {
    const d=new DrawingTool();
    d.arm("Polygon",mode); assert.equal(d.state,"ARMED");
    [[0,0],[30,0],[30,30],[0,30]].forEach(p=>d.vertex(...p));
    assert.equal(d.state,"DRAWING");
    assert.equal(d.close().length,5); assert.equal(d.state,"PREVIEW");
    d.resolving(); assert.equal(d.state,"RESOLVING");
    d.resolved(); assert.equal(d.state,"RESOLVED");
    assert.equal(d.vertex(3,4),false);
    d.arm("Polygon",mode); d.cancel(); assert.equal(d.state,"CANCELLED");
}
for (const points of [[[0,0],[10,10],[0,10],[10,0]], [[0,0],[1,0],[1,1]], [[0,0],[10,0]]]) {
    const d=new DrawingTool(); d.arm("Polygon"); points.forEach(p=>d.vertex(...p));
    assert.equal(d.close(),null); assert.equal(d.state,"FAILED"); assert.ok(d.error);
}
for(let i=0;i<1000;i++) {
    const d=new DrawingTool(); d.arm("Rectangle");
    [[0,0],[20,0],[20,20],[0,20]].forEach(p=>d.vertex(...p));
    assert.ok(d.close()); d.cancel();
}
const short=simplifySourcePath([[0,0],[1,2],[3,4]],2);
assert.deepEqual(short.path,[[0,0],[1,2],[3,4]]); assert.equal(short.tolerance,0);
const straight=Array.from({length:1200},(_,index)=>[index/10,0]);
const reduced=simplifySourcePath(straight,4);
assert.deepEqual(reduced.path,[[0,0],[119.9,0]]);
assert.ok(reduced.tolerance>0 && reduced.tolerance<=1);
assert.equal(reduced.original_count,1200);
const corner=Array.from({length:600},(_,index)=>index<300?[index/10,0]:[29.9,(index-299)/10]);
const cornerResult=simplifySourcePath(corner,4);
assert.deepEqual(cornerResult.path,[[0,0],[29.9,0],[29.9,30]]);
const detailed=Array.from({length:700},(_,index)=>[index,index%2?10:0]);
const rejected=simplifySourcePath(detailed,1);
assert.equal(rejected.path,null); assert.match(rejected.error,/Increase Radius/);
assert.ok(rejected.tolerance<=.25);
const rgb=(points,present=true,error="")=>{
    const s=new RGBStats(present); points.forEach(p=>s.add(...p)); return s.report(error);
};
assert.equal(rgb([[0,0,0],[0,0,0]]).status,"RGB_AVAILABLE_ALL_ZERO");
assert.equal(rgb([[80,50,10],[80,50,10]]).status,"RGB_AVAILABLE_CONSTANT");
assert.equal(rgb([[100,100,100],[101,101,101]]).status,"RGB_AVAILABLE_LOW_RANGE");
assert.equal(rgb([],false).status,"RGB_MISSING");
assert.equal(rgb([[NaN,10,20],[10,30,200]]).status,"RGB_PARTIAL");
assert.equal(rgb([[null,10,20]]).status,"RGB_PARTIAL");
for (const maximum of [255,65535,4095]) {
    const result=rgb([[0,maximum,0],[maximum,0,maximum]]);
    assert.equal(result.status,"RGB_AVAILABLE_VALID");
    assert.equal(result.display_transform.divisor,maximum>255?256:1);
    assert.equal(result.display_transform.source_modified,false);
}
const failed=rgb([[0,255,0],[255,0,255]],true,"Injected shader failure");
assert.equal(failed.status,"RGB_RENDER_FAILED");
assert.equal(failed.data_status,"RGB_AVAILABLE_VALID");
assert.match(failed.message,/data appears valid/);
console.log("Drawing, source-space Brush simplification, and RGB contracts passed.");
