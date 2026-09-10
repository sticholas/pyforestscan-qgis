/* Exercise editor.js event handlers, not the selection_test shortcut. */
const fs=require("node:fs"), vm=require("node:vm"), assert=require("node:assert/strict");
const path=require("node:path");
const {DrawingTool,simplifySourcePath}=require("../../pyforestscan_qgis/viewer/drawing.js");
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
class BufferGeometry {
    constructor(){this.attributes={};}
    setAttribute(name,value){this.attributes[name]=value;return this;}
    clone(){const value=new BufferGeometry();value.attributes={...this.attributes};return value;}
    dispose(){}
}
class Group {constructor(){this.children=[];}add(value){this.children.push(value);}}
class SceneObject {
    constructor(geometry,material){
        this.geometry=geometry;this.material=material;
        this.position={set:(x,y,z)=>{this.origin=[x,y,z];}};
    }
}
class Vector3 {
    constructor(x=0,y=0,z=0){Object.assign(this,{x,y,z});}
    unproject(){ this.x=1000+this.x*100;this.y=2000+this.y*100;return this; }
    clone(){return new Vector3(this.x,this.y,this.z);}
    copy(value){Object.assign(this,value);return this;}
}
const THREE={Vector3,Vector2:class {constructor(x,y){Object.assign(this,{x,y});}},
    Color:class{},Group,BufferGeometry,
    Float32BufferAttribute:class {constructor(values,size){this.values=values;this.itemSize=size;}},
    Line:SceneObject,Points:SceneObject,LineBasicMaterial:class {dispose(){}},
    PointsMaterial:class {dispose(){}},ShapeUtils:{triangulateShape(){return [];}}};
const viewer={renderer:{domElement:canvas},inputHandler:{enabled:true},
    scene:{view:{position:new Vector3(20,30,40),yaw:.4,pitch:-.3,radius:12},cameraMode:1,
        scene:{items:[],add(value){this.items.push(value);}},
        getActiveCamera(){return {clone(){return {};}};}},
    setCameraMode(mode){this.scene.cameraMode=mode;},
    setTopView(){this.scene.view.yaw=0;this.scene.view.pitch=-Math.PI/2;}};
const cloud={visibleNodes:[],material:{activeAttributeName:"classification"}};
const context={THREE,DrawingTool,simplifySourcePath,document,Potree:{CameraMode:{PERSPECTIVE:1,ORTHOGRAPHIC:2},
    Utils:{getMousePointCloudIntersection(mouse){return {location:new Vector3(mouse.x,mouse.y,mouse.x+mouse.y)};}}},
    requestAnimationFrame:fn=>queue.push(fn),performance:{now:()=>0}};
context.window=context; context.editorSelectionFilters=()=>({classes:null,height_filter:null});
context.viewerRenderPolicy={objectFocus(mode){return {requested:mode,effective:mode,opacity:1};}};
vm.createContext(context);
const source=fs.readFileSync(path.join(__dirname,"../../pyforestscan_qgis/viewer/editor.js"),"utf8").replace(/^import[^\n]+\n/,"");
vm.runInContext(source,context);
const editor=context.pointCloudEditor;
const tick=()=>editor.tick({viewer,cloud});
tick();
function arm(tool="Polygon",mode="REPLACE") {
    editor.command({action:"selection_tool",tool,mode,...(tool==="Brush"?{brush_radius:1}:{})});
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
editor.command({action:"selection_resolution"});
arm("Box");
canvas.emit("pointerdown",{offsetX:75,offsetY:100});
canvas.emit("pointermove",{offsetX:225,offsetY:250});
canvas.emit("pointerup",{offsetX:225,offsetY:250});
const box=tick().event;
assert.equal(box.geometry.length,5);
assert.deepEqual(Array.from(box.geometry[0]),[930,2060]);
assert.deepEqual(Array.from(box.geometry[2]),[990,2000]);
assert.equal(tick().drawing_state,"RESOLVING");
editor.command({action:"selection_resolution"});
editor.command({action:"selection_tool",tool:"Sphere",mode:"REPLACE",sphere_axis:"HeightAboveGround",sphere_height:12});
for(let i=0;i<2;i++){ const callbacks=queue.splice(0);callbacks.forEach(fn=>fn()); }
canvas.emit("pointerdown",{offsetX:250,offsetY:250});
canvas.emit("pointermove",{offsetX:300,offsetY:250});
canvas.emit("pointerup",{offsetX:300,offsetY:250});
const sphereGesture=tick().event;
assert.deepEqual(Array.from(sphereGesture.sphere_center),[1000,2000,12]);
assert.equal(sphereGesture.sphere_radius,20);
assert.equal(sphereGesture.sphere_axis,"HeightAboveGround");
editor.command({action:"selection_resolution"});
arm("Circle");
canvas.emit("pointerdown",{offsetX:250,offsetY:250});
canvas.emit("pointermove",{offsetX:300,offsetY:250});
canvas.emit("pointerup",{offsetX:300,offsetY:250});
const circle=tick().event;
assert.deepEqual(Array.from(circle.circle_center),[1000,2000]);
assert.equal(circle.circle_radius,20);
assert.deepEqual(Array.from(circle.geometry[0]),[980,1980]);
assert.deepEqual(Array.from(circle.geometry[2]),[1020,2020]);
assert.equal(tick().drawing_state,"RESOLVING");
assert.equal(viewer.inputHandler.enabled,true);
assert.equal(viewer.scene.view.yaw,.4);
assert.equal(viewer.scene.view.pitch,-.3);
editor.command({action:"selection_resolution"});
editor.command({action:"linked_view",view:{view_id:"slice",view_type:"VERTICAL_SLICE"}});
arm("Circle");
canvas.emit("pointerdown",{offsetX:250,offsetY:250});
assert.match(tick().event.error,/Overview and Area Detail/);
assert.equal(tick().tool,"Pointer");
editor.command({action:"linked_view",view:null});
arm("Brush");
// Invalid brush commands are ignored and retain the currently armed tool.
editor.command({action:"selection_tool",tool:"Brush",mode:"REPLACE",brush_radius:0});
assert.equal(tick().tool,"Brush");
canvas.emit("pointerdown",{offsetX:100,offsetY:100});
canvas.emit("pointermove",{offsetX:150,offsetY:100});
canvas.emit("pointermove",{offsetX:150,offsetY:150});
canvas.emit("pointerup",{offsetX:150,offsetY:180});
const brush=tick().event;
assert.equal(brush.brush_radius,1);
assert.equal(brush.brush_tolerance,0);
assert.equal(brush.brush_path.length,4);
assert.deepEqual(Array.from(brush.brush_path[0]),[940,2060]);
assert.deepEqual(Array.from(brush.brush_path.at(-1)),[960,2028]);
assert.equal(brush.geometry.length,5);
assert.equal(tick().drawing_state,"RESOLVING");
editor.command({action:"selection_resolution"});
editor.command({action:"linked_view",view:{view_id:"slice",view_type:"VERTICAL_SLICE"}});
arm("Brush");
canvas.emit("pointerdown",{offsetX:100,offsetY:100});
assert.match(tick().event.error,/Overview and Area Detail/);
assert.equal(tick().tool,"Pointer");
editor.command({action:"linked_view",view:null});
editor.command({action:"selection_test",
    geometry:[[8,18],[12,18],[12,22],[8,22],[8,18]],
    sphere_center:[10,20,30],sphere_radius:2,sphere_axis:"Z"});
const sphere=tick().event;
assert.deepEqual(Array.from(sphere.sphere_center),[10,20,30]);
assert.equal(sphere.sphere_radius,2);
assert.equal(sphere.sphere_axis,"Z");
editor.command({action:"linked_view",view:{view_id:"slice",view_type:"VERTICAL_SLICE",
    geometry:{a:[900,2000],b:[1100,2000]},
    corridor:[[900,1995],[1100,1995],[1100,2005],[900,2005],[900,1995]]}});
arm("AboveLine"); click(125,250); click(375,200);
const aboveLine=tick().event;
assert.equal(aboveLine.profile_line_side,"ABOVE");
assert.deepEqual(Array.from(aboveLine.profile_line[0]),[50,0]);
assert.deepEqual(Array.from(aboveLine.profile_line[1]),[150,0]);
assert.equal(aboveLine.mode,"REPLACE");
assert.equal(tick().drawing_state,"RESOLVING");
editor.command({action:"selection_resolution"});
editor.command({action:"linked_view",view:null});
arm("BelowLine"); click(125,250); click(375,200);
assert.match(tick().event.error,/only in Vertical Slice/);
arm();editor.command({action:"selection_tool",tool:"Pointer"});
for(let i=0;i<2;i++){ const callbacks=queue.splice(0);callbacks.forEach(fn=>fn()); }
assert.equal(tick().tool,"Pointer");
const cameraBefore=[viewer.scene.view.yaw,viewer.scene.view.pitch,viewer.scene.cameraMode];
editor.command({action:"measurement_tool"});
assert.equal(tick().tool,"MeasureDistance");
click(10,20);
assert.equal(tick().event.action,"measurement_anchor");
assert.equal(tick().tool,"MeasureDistance");
click(30,50);
const measurement=tick().event;
assert.equal(measurement.action,"measure_points");
assert.deepEqual(Array.from(measurement.points[0]),[10,20,30]);
assert.deepEqual(Array.from(measurement.points[1]),[30,50,80]);
assert.equal(tick().tool,"Pointer");
assert.deepEqual([viewer.scene.view.yaw,viewer.scene.view.pitch,viewer.scene.cameraMode],cameraBefore);
editor.command({action:"measurements",measurements:[{
    start:{source_xyz:[10,20,30]},end:{source_xyz:[30,50,80]}}]});
assert.equal(tick().measurement_count,1);
const measurementGroup=viewer.scene.scene.items.find(item=>item.name==="PyForestScan measurements");
assert.ok(measurementGroup);
assert.deepEqual(Array.from(measurementGroup.children[0].geometry.attributes.position.values),
    [0,0,0,20,30,50]);
assert.deepEqual(measurementGroup.children[0].origin,[10,20,30]);
editor.command({action:"selection_tool",tool:"Polygon",purpose:"MEASURE_AREA"});
for(let i=0;i<2;i++){ const callbacks=queue.splice(0);callbacks.forEach(fn=>fn()); }
click(50,50);click(200,50);click(200,200);document.emit("keydown",{key:"Enter"});
const area=tick().event;
assert.equal(area.action,"MEASURE_AREA");
assert.equal(area.geometry.length,4);
assert.equal(area.display_elevation,0);
editor.command({action:"measurements",measurements:[
    {start:{source_xyz:[10,20,30]},end:{source_xyz:[30,50,80]}},
    {kind:"PLANAR_AREA",vertices:[[920,2080],[980,2080],[980,2020],[920,2080]],
        display_elevation:0}
]});
assert.equal(tick().measurement_count,2);
assert.equal(measurementGroup.children.length,3);
assert.deepEqual(Array.from(measurementGroup.children[2].geometry.attributes.position.values),
    [0,0,0,60,0,0,60,-60,0,0,0,0]);
editor.command({action:"linked_view",view:{view_id:"slice",view_type:"VERTICAL_SLICE",
    geometry:{a:[0,0],b:[100,0],thickness:4}}});
editor.command({action:"measurement_tool",kind:"PROFILE_DISTANCE"});
click(5,8);click(9,20);
const profileMeasurement=tick().event;
assert.equal(profileMeasurement.action,"measure_profile_points");
assert.equal(profileMeasurement.view_id,"slice");
editor.command({action:"measurements",measurements:[{kind:"PROFILE_DISTANCE",view_id:"slice",
    start:{display_xyz:[5,8,13]},end:{display_xyz:[9,20,29]}}]});
assert.equal(tick().measurement_count,1);
assert.deepEqual(Array.from(measurementGroup.children[0].geometry.attributes.position.values),
    [0,0,0,4,12,16]);
editor.command({action:"linked_view",view:{view_id:"overview",view_type:"OVERVIEW_3D"}});
assert.equal(tick().measurement_count,0);
editor.command({action:"linked_view",view:{view_id:"slice",view_type:"VERTICAL_SLICE",
    geometry:{a:[0,0],b:[100,0],thickness:4}}});
assert.equal(tick().measurement_count,1);
console.log("Production editor gesture handlers passed all completion/cancel paths.");
