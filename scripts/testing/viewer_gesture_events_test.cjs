/* Exercise editor.js event handlers, not the selection_test shortcut. */
const fs=require("node:fs"), vm=require("node:vm"), assert=require("node:assert/strict");
const path=require("node:path");
const {DrawingTool}=require("../../pyforestscan_qgis/viewer/drawing.js");
function surface() {
    const listeners={};
    return {listeners,style:{},clientWidth:500,clientHeight:500,
        addEventListener(name,callback){(listeners[name] ||= []).push(callback);},
        emit(name,props={}) {
            const event={button:0,offsetX:0,offsetY:0,pointerId:1,
                preventDefault(){},stopPropagation(){},stopImmediatePropagation(){},...props};
            for(const fn of listeners[name]||[]) fn(event);
        },
        appendChild(){},setAttribute(){},remove(){},
        setPointerCapture(){},hasPointerCapture(){return false;},releasePointerCapture(){}};
}
const canvas=surface(); canvas.parentElement=surface();
const document=surface(); document.createElement=surface; document.createElementNS=surface;
const queue=[];
class Vector3 {
    constructor(x=0,y=0,z=0){Object.assign(this,{x,y,z});}
    unproject(){ this.x=1000+this.x*100;this.y=2000+this.y*100;return this; }
    clone(){return new Vector3(this.x,this.y,this.z);}
    copy(value){Object.assign(this,value);return this;}
}
const THREE={Vector3,Vector2:class {constructor(x,y){Object.assign(this,{x,y});}},
    Color:class{}, ShapeUtils:{triangulateShape(){return [];}}};
const viewer={renderer:{domElement:canvas},inputHandler:{enabled:true},
    scene:{view:{position:new Vector3(20,30,40),yaw:.4,pitch:-.3,radius:12},cameraMode:1,
        getActiveCamera(){return {clone(){return {};}};}},
    setCameraMode(mode){this.scene.cameraMode=mode;},
    setTopView(){this.scene.view.yaw=0;this.scene.view.pitch=-Math.PI/2;}};
const cloud={visibleNodes:[],material:{activeAttributeName:"classification"}};
const context={THREE,DrawingTool,document,Potree:{CameraMode:{PERSPECTIVE:1,ORTHOGRAPHIC:2}},
    requestAnimationFrame:fn=>queue.push(fn),performance:{now:()=>0}};
context.window=context; context.editorSelectionFilters=()=>({classes:null,height_filter:null});
vm.createContext(context);
const source=fs.readFileSync(path.join(__dirname,"../../pyforestscan_qgis/viewer/editor.js"),"utf8").replace(/^import[^\n]+\n/,"");
vm.runInContext(source,context);
const editor=context.pointCloudEditor;
const tick=()=>editor.tick({viewer,cloud});
tick();
function arm(tool="Polygon",mode="REPLACE") {
    editor.command({action:"selection_tool",tool,mode});
    for(let i=0;i<2;i++){ const callbacks=queue.splice(0);callbacks.forEach(fn=>fn()); }
}
function click(x,y,extra={}) {
    canvas.emit("pointerdown",{offsetX:x,offsetY:y,...extra});
    canvas.emit("pointerup",{offsetX:x,offsetY:y,...extra});
}
let id=0;
for(const ending of ["dblclick","Enter","contextmenu","first"]) {
    arm();
    click(50,50);click(200,50);click(200,200);
    if(ending==="Enter")document.emit("keydown",{key:"Enter"});
    else if(ending==="first")click(50,50);
    else canvas.emit(ending,{button:ending==="contextmenu"?2:0});
    const state=tick();
    assert.equal(state.tool,"Pointer");
    assert.equal(state.drawing_state,"RESOLVING");
    assert.ok(state.event.id>id); id=state.event.id;
    assert.equal(state.event.geometry.length,4);
    assert.deepEqual(Array.from(state.event.geometry[0]),[920,2080]);
    assert.equal(viewer.inputHandler.enabled,true);
    assert.equal(viewer.scene.view.yaw,.4);
    assert.equal(viewer.scene.view.pitch,-.3);
    assert.equal(viewer.scene.view.radius,12);
    editor.command({action:"selection_resolution"});
    assert.equal(tick().drawing_state,"RESOLVED");
}
arm();click(30,30); document.emit("keydown",{key:"Escape"});
assert.equal(tick().drawing_state,"CANCELLED");
assert.equal(tick().event.action,"pointer");
arm();click(20,20);click(200,200);click(20,200);click(200,20);
document.emit("keydown",{key:"Enter"});
assert.equal(tick().drawing_state,"FAILED");assert.match(tick().event.error,/intersect/);
for(const [props,mode]of [[{shiftKey:true},"ADD"],[{altKey:true},"SUBTRACT"]]) {
    arm();click(50,50,props);click(200,50);click(200,200);
    document.emit("keydown",{key:"Enter"});assert.equal(tick().event.mode,mode);
}
arm("Rectangle");
canvas.emit("pointerdown",{offsetX:50,offsetY:50});
canvas.emit("pointermove",{offsetX:200,offsetY:200});
canvas.emit("pointerup",{offsetX:200,offsetY:200});
assert.equal(tick().event.geometry.length,5);
assert.equal(tick().drawing_state,"RESOLVING");
arm();editor.command({action:"selection_tool",tool:"Pointer"});
for(let i=0;i<2;i++){ const callbacks=queue.splice(0);callbacks.forEach(fn=>fn()); }
assert.equal(tick().tool,"Pointer");
console.log("Production editor gesture handlers passed all completion/cancel paths.");
