"use strict";
const assert=require("node:assert/strict");
const {performance}=require("node:perf_hooks");
const {simplifySourcePath}=require("../../pyforestscan_qgis/viewer/drawing.js");

function distance(point,a,b) {
    const vx=b[0]-a[0],vy=b[1]-a[1],length=vx*vx+vy*vy;
    const t=length?Math.max(0,Math.min(1,((point[0]-a[0])*vx+(point[1]-a[1])*vy)/length)):0;
    return Math.hypot(point[0]-(a[0]+t*vx),point[1]-(a[1]+t*vy));
}
function deviation(source,reduced) {
    return Math.max(...source.map(point=>Math.min(...reduced.slice(1).map(
        (end,index)=>distance(point,reduced[index],end)))));
}

const radius=4;
const source=Array.from({length:2048},(_value,index)=>[
    index*.025,Math.sin(index/18)*.8+Math.sin(index/71)*.25]);
for(let i=0;i<5;i++) simplifySourcePath(source,radius);
const durations=[];
let result;
for(let i=0;i<50;i++) {
    const started=performance.now();
    result=simplifySourcePath(source,radius);
    durations.push(performance.now()-started);
}
durations.sort((a,b)=>a-b);
const maximumDeviation=deviation(source,result.path);
assert.ok(result.path.length<=512);
assert.ok(maximumDeviation<=result.tolerance+1e-9);
assert.ok(result.tolerance<=radius/4);
console.log(JSON.stringify({input_points:source.length,output_points:result.path.length,
    radius,tolerance:result.tolerance,max_observed_deviation:maximumDeviation,
    median_milliseconds:durations[Math.floor(durations.length/2)],iterations:durations.length}));
