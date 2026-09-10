import * as THREE from "./assets/libs/three.js/three.module.js";

let context, tool = "Pointer", rectangleStart = null, rectangleBox = null;
const drawing = new DrawingTool();
let drawingCamera = null, polygonOverlay = null, polygonLine = null;
let savedNavigation = null;
let linkedView = null, drawingPurpose = "EDIT";
let mode = "REPLACE", eventNumber = 0, latestEvent = null, revision = 0, edits = [], selection = [];
const originals = new WeakMap(), records = new Map();
const point = new THREE.Vector3(), sourcePointValue = new THREE.Vector3(), flat = new THREE.Vector3();
let pending = [], requestedRevision = 0;
let gestureMode = null;
let toolEpoch = 0, insertionPending = false;
let brushPointer = null, brushRadius = 1;
let sphereAxis = "Z", sphereHeight = 0;
let displaySignature = "";
let selectionColor = new THREE.Color("#5be4eb");
let objectFocusMode = "SHOW_ALL";
let measurementDraft = [], measurementGroup = null, measurementCount = 0;
let measurementKind = "POINT_DISTANCE", measurementPurpose = "CROSS_SECTION", measurementItems = [];
let annotationGroup = null, annotationCount = 0, annotationItems = [];
let workspaceGroup = null, workspaceViewCount = 0, workspaceItems = [];
let cursorGroup = null, linkedCursor = null, hoverCursor = {sequence:0,active:false};
let cursorTimer = null;
let sceneVisibility = {selection:true, measurements:true, annotations:true, profiles:true};
function sourceAttribute(geometry, name) {
    const extra = geometry._pfsOriginalDimensions && geometry._pfsOriginalDimensions[name];
    return extra ? {array:extra} : geometry.getAttribute(name) || geometry.getAttribute(name.toLowerCase());
}
function profileLocal(geometry, x, y) {
    const path=Array.isArray(geometry.path)&&geometry.path.length>2 ? geometry.path :
        [geometry.a,geometry.b];
    let best=null,cumulative=0;
    for (let i=0;i<path.length-1;i++) {
        const a=path[i],b=path[i+1],dx=b[0]-a[0],dy=b[1]-a[1],length=Math.hypot(dx,dy);
        if (!(length>0)) continue;
        const fraction=Math.max(0,Math.min(1,((x-a[0])*dx+(y-a[1])*dy)/(length*length)));
        const px=a[0]+fraction*dx,py=a[1]+fraction*dy,distance=(x-px)**2+(y-py)**2;
        const candidate={distance,along:cumulative+fraction*length,
            cross:(-(x-a[0])*dy+(y-a[1])*dx)/length};
        if (!best || candidate.distance<best.distance) best=candidate;
        cumulative+=length;
    }
    return best ? {...best,length:cumulative} : null;
}
function profileProjected() {
    return linkedView && linkedView.view_type === "VERTICAL_SLICE" &&
        linkedView.display_projection === "PROFILE_DISTANCE";
}
function profileContains(geometry,x,y) {
    const path=Array.isArray(geometry.path)&&geometry.path.length>2 ? geometry.path :
        [geometry.a,geometry.b];
    const radius=(geometry.thickness||0)/2,radius2=radius*radius;
    for (let i=0;i<path.length-1;i++) {
        const a=path[i],b=path[i+1],dx=b[0]-a[0],dy=b[1]-a[1],length2=dx*dx+dy*dy;
        const fraction=((x-a[0])*dx+(y-a[1])*dy)/length2;
        const px=a[0]+fraction*dx,py=a[1]+fraction*dy;
        if (fraction>=0&&fraction<=1&&(x-px)**2+(y-py)**2<=radius2) return true;
    }
    return path.slice(1,-1).some(vertex =>
        (x-vertex[0])**2+(y-vertex[1])**2<=radius2);
}
function profileSource(along,cross) {
    if (!linkedView || !linkedView.geometry) return null;
    const geometry=linkedView.geometry;
    const path=Array.isArray(geometry.path)&&geometry.path.length>2 ? geometry.path :
        [geometry.a,geometry.b];
    let cumulative=0;
    for (let i=0;i<path.length-1;i++) {
        const a=path[i],b=path[i+1],dx=b[0]-a[0],dy=b[1]-a[1],length=Math.hypot(dx,dy);
        if (!(length>0)) continue;
        if (along<=cumulative+length || i===path.length-2) {
            const distance=Math.max(0,Math.min(length,along-cumulative));
            return [a[0]+distance*dx/length-cross*dy/length,
                    a[1]+distance*dy/length+cross*dx/length];
        }
        cumulative+=length;
    }
    return null;
}
function scalar(value) {
    if (Number.isFinite(value)) return Number(value);
    if (value && Number.isFinite(value[0])) return Number(value[0]);
    return null;
}
function pickWithSourceProvenance(x,y) {
    const hit=Potree.Utils&&Potree.Utils.getMousePointCloudIntersection(
        {x,y},context.viewer.scene.getActiveCamera(),context.viewer,[context.cloud],
        {pickWindowSize:17});
    const picked=hit&&hit.point&&hit.point._pfsPick;
    if (!picked||!picked.geometry||!Number.isInteger(picked.index)) return hit;
    const aliases={HeightAboveGround:"_pfsHag",PFSOriginalX:"_pfsOriginalX",
        PFSOriginalY:"_pfsOriginalY",PFSOriginalZ:"_pfsOriginalZ"};
    for (const [name,alias] of Object.entries(aliases)) {
        const values=picked.sourceDimensions&&picked.sourceDimensions[name];
        const attribute=values ? {array:values} : sourceAttribute(picked.geometry,name);
        if (attribute&&picked.index>=0&&picked.index<attribute.array.length)
            hit.point[alias]=attribute.array[picked.index];
    }
    return hit;
}
function clearHoverCursor() {
    if (cursorTimer) clearTimeout(cursorTimer);
    cursorTimer=null;
    if (hoverCursor.active) hoverCursor={sequence:hoverCursor.sequence+1,active:false};
}
function inspectHoverCursor(x,y) {
    cursorTimer=null;
    if (!context||tool!=="Pointer") return;
    const hit=pickWithSourceProvenance(x,y);
    if (!hit||!hit.location||!hit.point) {
        clearHoverCursor();
        return;
    }
    const display=[hit.location.x,hit.location.y,hit.location.z];
    const ox=scalar(hit.point._pfsOriginalX),oy=scalar(hit.point._pfsOriginalY);
    const oz=scalar(hit.point._pfsOriginalZ),hag=scalar(hit.point._pfsHag);
    const inverse=profileProjected()?profileSource(display[0],display[1]):null;
    const source=[ox??(inverse?inverse[0]:display[0]),
                  oy??(inverse?inverse[1]:display[1]),
                  oz??display[2]];
    if (source.some(value=>!Number.isFinite(value))) {
        clearHoverCursor();
        return;
    }
    const local=linkedView&&linkedView.view_type==="VERTICAL_SLICE" ?
        profileLocal(linkedView.geometry,source[0],source[1]):null;
    hoverCursor={sequence:hoverCursor.sequence+1,active:true,source_xyz:source,
        display_xyz:display,height_above_ground:hag,
        classification:scalar(hit.point.classification),
        distance_along:local&&local.along,cross_track:local&&local.cross,
        authority:ox!==null&&oy!==null&&oz!==null ?
            "ORIGINAL_SOURCE_RECORD_COORDINATES":"DISPLAYED_SOURCE_RECORD_COORDINATES"};
}
function scheduleHoverCursor(event) {
    if (cursorTimer) clearTimeout(cursorTimer);
    const x=event.offsetX,y=event.offsetY;
    cursorTimer=setTimeout(()=>{
        try {
            inspectHoverCursor(x,y);
        } catch (error) {
            clearHoverCursor();
            console.warn("Linked cursor inspection was skipped.",error);
        }
    },90);
}

function publish(geometry, primitive = {}) {
    const effectiveMode = gestureMode || mode;
    if (drawingPurpose !== "EDIT") {
        latestEvent = {id: ++eventNumber, action: drawingPurpose, geometry, ...primitive};
        return;
    }
    latestEvent = {id: ++eventNumber, geometry, mode: effectiveMode, ...primitive};
    if (linkedView && linkedView.view_type === "VERTICAL_SLICE") {
        if (!primitive.profile_brush_path) latestEvent.profile_geometry = geometry;
        latestEvent.geometry = linkedView.corridor;
        return; // Only the authoritative worker publishes a profile selection overlay.
    }
    const filters = window.editorSelectionFilters();
    const preview = compile({geometry, selection_mode: effectiveMode, classification_filter: filters.classes,
        z_filter: filters.height_filter, hag_filter: null, attribute_filters: [], ...primitive});
    selection = effectiveMode === "REPLACE" ? [preview] : [...selection, preview];
    revision++;
    for (const record of records.values()) record.revision = -1;
}
function compile(definition) {
    const ring = definition.geometry.slice(0, -1).map(p => new THREE.Vector2(p[0], p[1]));
    const triangles = THREE.ShapeUtils.triangulateShape(ring, []).map(face =>
        new THREE.Triangle(...face.map(i => new THREE.Vector3(ring[i].x, ring[i].y, 0))));
    const extra = {};
    for (const key of ["clip_geometry", "profile_geometry"]) {
        if (definition[key]) extra[key + "_triangles"] = compile({geometry:definition[key]}).triangles;
    }
    return {...definition, ...extra, triangles, bounds: [Math.min(...ring.map(p => p.x)),
        Math.min(...ring.map(p => p.y)), Math.max(...ring.map(p => p.x)), Math.max(...ring.map(p => p.y))]};
}
function insideBrush(item, xyz) {
    const path = item.brush_path, radius = item.brush_radius;
    if (!path || !radius) return true;
    if (path.length === 1) return Math.hypot(xyz.x-path[0][0], xyz.y-path[0][1]) <= radius;
    for (let i=0; i<path.length-1; i++) {
        const a=path[i], b=path[i+1], vx=b[0]-a[0], vy=b[1]-a[1];
        const t=Math.max(0,Math.min(1,((xyz.x-a[0])*vx+(xyz.y-a[1])*vy)/(vx*vx+vy*vy)));
        if (Math.hypot(xyz.x-(a[0]+t*vx),xyz.y-(a[1]+t*vy)) <= radius) return true;
    }
    return false;
}
function insideSphere(item, xyz, geometry, index) {
    if (!item.sphere_center || !item.sphere_radius) return true;
    const attribute = item.sphere_axis === "HeightAboveGround" ?
        sourceAttribute(geometry, "HeightAboveGround") : null;
    const height = item.sphere_axis === "HeightAboveGround" ?
        (attribute ? attribute.array[index] : NaN) : xyz.z;
    const [x,y,z] = item.sphere_center, radius = item.sphere_radius;
    return Number.isFinite(height) &&
        ((xyz.x-x)/radius)**2 + ((xyz.y-y)/radius)**2 + ((height-z)/radius)**2 <= 1;
}
function matches(definitions, xyz, classification, geometry, index) {
    let selected = false;
    for (const item of definitions) {
        flat.set(xyz.x, xyz.y, 0);
        let hit = item.triangles.some(triangle => triangle.containsPoint(flat));
        if (hit && item.circle_center && item.circle_radius)
            hit = Math.hypot(xyz.x-item.circle_center[0], xyz.y-item.circle_center[1]) <= item.circle_radius;
        if (hit && item.brush_path && item.brush_radius) hit = insideBrush(item, xyz);
        if (hit && item.sphere_center && item.sphere_radius)
            hit = insideSphere(item, xyz, geometry, index);
        if (hit && item.clip_geometry_triangles)
            hit = item.clip_geometry_triangles.some(triangle => triangle.containsPoint(flat));
        if (hit && item.profile_a) {
            const local=profileLocal({a:item.profile_a,b:item.profile_b,path:item.profile_path},xyz.x,xyz.y);
            const along=local.along,depth=local.cross,length=local.length;
            hit = along >= 0 && along <= length && profileContains(
                {a:item.profile_a,b:item.profile_b,path:item.profile_path,
                 thickness:item.profile_thickness},xyz.x,xyz.y);
            if (hit && item.profile_geometry_triangles) {
                const attribute = sourceAttribute(geometry, "HeightAboveGround");
                const height = item.profile_axis === "HeightAboveGround" ?
                    (attribute ? attribute.array[index] : NaN) : xyz.z;
                flat.set(along, height, 0);
                hit = Number.isFinite(height) && item.profile_geometry_triangles.some(triangle => triangle.containsPoint(flat));
            }
            if (hit && item.profile_line) {
                const attribute = sourceAttribute(geometry, "HeightAboveGround");
                const height = item.profile_axis === "HeightAboveGround" ?
                    (attribute ? attribute.array[index] : NaN) : xyz.z;
                const [[x1,h1],[x2,h2]]=item.profile_line;
                const low=Math.min(x1,x2), high=Math.max(x1,x2);
                const lineHeight=h1+(along-x1)*(h2-h1)/(x2-x1);
                hit = Number.isFinite(height) && along >= low && along <= high &&
                    (item.profile_line_side === "ABOVE" ? height >= lineHeight : height <= lineHeight);
            }
            if (hit && item.profile_brush_path && item.profile_brush_radius) {
                const attribute = sourceAttribute(geometry, "HeightAboveGround");
                const height = item.profile_axis === "HeightAboveGround" ?
                    (attribute ? attribute.array[index] : NaN) : xyz.z;
                hit = Number.isFinite(height) && insideBrush(
                    {brush_path:item.profile_brush_path,
                     brush_radius:item.profile_brush_radius},
                    {x:along,y:height});
            }
        }
        if (item.legacy_bounds) {
            const b = item.legacy_bounds;
            hit = xyz.x >= b[0] && xyz.y >= b[1] && xyz.z >= b[2] &&
                  xyz.x <= b[3] && xyz.y <= b[4] && xyz.z <= b[5];
        }
        if (hit && item.z_filter) hit = xyz.z >= item.z_filter[0] && xyz.z <= item.z_filter[1];
        if (hit && item.classification_filter != null) hit = item.classification_filter.includes(classification);
        const ranges = [...(item.attribute_filters || [])];
        if (item.hag_filter) ranges.push(["HeightAboveGround", ...item.hag_filter]);
        for (const [name, low, high] of ranges) {
            const attribute = sourceAttribute(geometry, name);
            if (!attribute || attribute.array[index] < low || attribute.array[index] > high) hit = false;
        }
        if (item.selection_mode === "REPLACE") selected = hit;
        else if (item.selection_mode === "ADD") selected = selected || hit;
        else selected = selected && !hit;
        if (item.invert_result) selected = !selected;
    }
    return selected;
}
function removeHighlight(record) {
    if (record.highlight) {
        context.viewer.scene.scene.remove(record.highlight);
        record.highlight.geometry.dispose();
        record.highlight.material.dispose();
        record.highlight = null;
    }
}
function setSceneVisibility(value) {
    if (!value || typeof value !== "object") return false;
    for (const key of ["selection", "measurements", "annotations", "profiles"])
        if (key in value && typeof value[key] !== "boolean") return false;
    sceneVisibility = {...sceneVisibility, ...value};
    if (measurementGroup) measurementGroup.visible = sceneVisibility.measurements;
    if (annotationGroup) annotationGroup.visible = sceneVisibility.annotations;
    if (workspaceGroup) workspaceGroup.visible = sceneVisibility.profiles &&
        (!linkedView || linkedView.view_type !== "VERTICAL_SLICE");
    for (const record of records.values()) record.revision = -1;
    return true;
}
function renderWorkspaceViews(items) {
    workspaceItems=Array.isArray(items)?items:[];
    if (!workspaceGroup) {
        workspaceGroup=new THREE.Group();
        workspaceGroup.name="PyForestScan profile corridors";
        context.viewer.scene.scene.add(workspaceGroup);
    }
    while (workspaceGroup.children.length) {
        const child=workspaceGroup.children.pop();
        if (child.geometry) child.geometry.dispose();
        if (child.material) child.material.dispose();
    }
    workspaceViewCount=0;
    context.cloud.updateMatrixWorld(true);
    const bounds=context.cloud.boundingBox.clone().applyMatrix4(context.cloud.matrixWorld);
    const z=bounds.min.z + Math.max(.01,(bounds.max.z-bounds.min.z)*.01);
    for (const item of workspaceItems.slice(0,100)) {
        const rings=Array.isArray(item&&item.segment_corridors)&&item.segment_corridors.length ?
            item.segment_corridors : [item&&item.corridor];
        let accepted=false;
        for (const ring of rings) {
            if (!Array.isArray(ring) || ring.length<4 || ring.length>16 ||
                    ring.some(value=>!Array.isArray(value)||value.length!==2||!value.every(Number.isFinite))) continue;
            const origin=ring[0];
            const values=ring.flatMap(value=>[value[0]-origin[0],value[1]-origin[1],0]);
            const geometry=new THREE.BufferGeometry();
            geometry.setAttribute("position",new THREE.Float32BufferAttribute(values,3));
            const line=new THREE.Line(geometry,new THREE.LineBasicMaterial({
                color:item.active?0xffd166:0x5be4eb,depthTest:false,transparent:true,opacity:.9}));
            line.position.set(origin[0],origin[1],z);
            line.renderOrder=1090;
            line.name=typeof item.title==="string"?item.title:"Profile corridor";
            line.userData={view_id:item.view_id||"",authority:"DISPLAY_CONTEXT_ONLY"};
            workspaceGroup.add(line);
            accepted=true;
        }
        const path=item&&item.path;
        if (Array.isArray(path)&&path.length>=2&&path.length<=256&&
                path.every(value=>Array.isArray(value)&&value.length===2&&value.every(Number.isFinite))) {
            const origin=path[0],geometry=new THREE.BufferGeometry();
            geometry.setAttribute("position",new THREE.Float32BufferAttribute(
                path.flatMap(value=>[value[0]-origin[0],value[1]-origin[1],.01]),3));
            const centerline=new THREE.Line(geometry,new THREE.LineBasicMaterial({
                color:item.active?0xffd166:0x5be4eb,depthTest:false}));
            centerline.position.set(origin[0],origin[1],z);
            centerline.renderOrder=1091;
            centerline.name=(item.title||"Profile corridor")+" centerline";
            centerline.userData={view_id:item.view_id||"",authority:"DISPLAY_CONTEXT_ONLY"};
            workspaceGroup.add(centerline);
            accepted=true;
        }
        if (!accepted) continue;
        workspaceViewCount++;
    }
    workspaceGroup.visible=sceneVisibility.profiles &&
        (!linkedView || linkedView.view_type !== "VERTICAL_SLICE");
}
function applyObjectFocus() {
    const focus = window.viewerRenderPolicy.objectFocus(objectFocusMode, selection.length > 0);
    if (context && context.cloud.material.opacity !== focus.opacity)
        context.cloud.material.opacity = focus.opacity;
    return focus;
}
function leaveTool() {
    toolEpoch++;
    insertionPending = false;
    const viewer = context.viewer;
    if (polygonOverlay) polygonOverlay.remove();
    polygonOverlay = null; polygonLine = null; drawingCamera = null;
    if (rectangleBox) rectangleBox.remove();
    rectangleBox = null;
    rectangleStart = null;
    brushPointer = null;
    measurementDraft = [];
    if (context && context.viewer && context.viewer.renderer)
        context.viewer.renderer.domElement.style.cursor = "";
    viewer.inputHandler.enabled = true;
    if (savedNavigation) {
        const view = viewer.scene.view;
        view.position.copy(savedNavigation.position);
        view.yaw = savedNavigation.yaw; view.pitch = savedNavigation.pitch;
        view.radius = savedNavigation.radius;
        viewer.setCameraMode(savedNavigation.cameraMode);
        savedNavigation = null;
    }
    gestureMode = null;
    tool = "Pointer";
}
function renderMeasurements(items) {
    measurementItems = Array.isArray(items) ? items : [];
    if (!measurementGroup) {
        measurementGroup = new THREE.Group();
        measurementGroup.name = "PyForestScan measurements";
        context.viewer.scene.scene.add(measurementGroup);
    }
    measurementGroup.visible = sceneVisibility.measurements;
    while (measurementGroup.children.length) {
        const child = measurementGroup.children.pop();
        if (child.geometry) child.geometry.dispose();
        if (child.material) child.material.dispose();
    }
    measurementCount = 0;
    for (const item of measurementItems) {
        if (item.kind === "PROFILE_DISTANCE") {
            if (!linkedView || linkedView.view_id !== item.view_id ||
                    !item.start || !item.end) continue;
            const absolute=[...item.start.display_xyz,...item.end.display_xyz];
            if (absolute.length !== 6 || absolute.some(value=>!Number.isFinite(value))) continue;
            const values=[0,0,0,absolute[3]-absolute[0],
                absolute[4]-absolute[1],absolute[5]-absolute[2]];
            const geometry=new THREE.BufferGeometry();
            geometry.setAttribute("position",new THREE.Float32BufferAttribute(values,3));
            const line=new THREE.Line(geometry,new THREE.LineBasicMaterial(
                {color:0xffd166,depthTest:false,transparent:true,opacity:.95}));
            line.position.set(absolute[0],absolute[1],absolute[2]);
            line.renderOrder=1100;measurementGroup.add(line);
            const markers=new THREE.Points(geometry.clone(),new THREE.PointsMaterial(
                {color:0xffd166,size:8,sizeAttenuation:false,depthTest:false}));
            markers.position.set(absolute[0],absolute[1],absolute[2]);
            markers.renderOrder=1101;measurementGroup.add(markers);
            measurementCount++;
            continue;
        }
        if (item.kind === "PLANAR_AREA") {
            if (linkedView && linkedView.view_type === "VERTICAL_SLICE") continue;
            const vertices=item.vertices || [], z=item.display_elevation;
            if (vertices.length < 4 || !Number.isFinite(z) ||
                    vertices.some(value=>value.length !== 2 || value.some(x=>!Number.isFinite(x)))) continue;
            const origin=[vertices[0][0],vertices[0][1],z];
            const values=vertices.flatMap(value=>[value[0]-origin[0],value[1]-origin[1],0]);
            const geometry=new THREE.BufferGeometry();
            geometry.setAttribute("position",new THREE.Float32BufferAttribute(values,3));
            const line=new THREE.Line(geometry,new THREE.LineBasicMaterial(
                {color:0xffd166,depthTest:false,transparent:true,opacity:.95}));
            line.position.set(...origin);line.renderOrder=1100;measurementGroup.add(line);
            measurementCount++;
            continue;
        }
        if (!item.start || !item.end) continue;
        const absolute = [...item.start.source_xyz, ...item.end.source_xyz];
        if (absolute.length !== 6 || absolute.some(value => !Number.isFinite(value))) continue;
        // Keep Float32 geometry local so large projected coordinates do not erase
        // sub-metre differences; Object3D carries the source-coordinate origin.
        const values = [0, 0, 0, absolute[3]-absolute[0],
            absolute[4]-absolute[1], absolute[5]-absolute[2]];
        const geometry = new THREE.BufferGeometry();
        geometry.setAttribute("position", new THREE.Float32BufferAttribute(values, 3));
        const line = new THREE.Line(geometry,
            new THREE.LineBasicMaterial({color:0xffd166, depthTest:false, transparent:true, opacity:.95}));
        line.position.set(absolute[0], absolute[1], absolute[2]);
        line.renderOrder = 1100;
        measurementGroup.add(line);
        const markers = new THREE.Points(geometry.clone(),
            new THREE.PointsMaterial({color:0xffd166, size:8, sizeAttenuation:false, depthTest:false}));
        markers.position.set(absolute[0], absolute[1], absolute[2]);
        markers.renderOrder = 1101;
        measurementGroup.add(markers);
        measurementCount++;
    }
}
function pointInRing(x, y, ring) {
    if (!Array.isArray(ring) || ring.length < 4) return true;
    let inside = false;
    for (let i=0,j=ring.length-1;i<ring.length;j=i++) {
        const a=ring[i],b=ring[j];
        if (!Array.isArray(a)||!Array.isArray(b)) continue;
        if ((a[1]>y)!==(b[1]>y) && x<(b[0]-a[0])*(y-a[1])/(b[1]-a[1])+a[0])
            inside=!inside;
    }
    return inside;
}
function annotationDisplayPoint(item) {
    const anchor=item&&item.anchor;
    if (!anchor || !Array.isArray(anchor.source_xyz) || anchor.source_xyz.length!==3 ||
            anchor.source_xyz.some(value=>!Number.isFinite(value))) return null;
    const value=anchor.source_xyz.slice();
    if (!linkedView || linkedView.view_type === "OVERVIEW_3D") return value;
    if (linkedView.view_type === "AREA_DETAIL")
        return pointInRing(value[0],value[1],linkedView.corridor) ? value : null;
    if (linkedView.view_type !== "VERTICAL_SLICE" || !linkedView.geometry) return null;
    const geometry=linkedView.geometry,local=profileLocal(geometry,value[0],value[1]);
    if (!local || local.along<0 || local.along>local.length ||
            !profileContains(geometry,value[0],value[1])) return null;
    if (geometry.vertical_axis === "HeightAboveGround") {
        if (!Number.isFinite(anchor.height_above_ground)) return null;
        value[2]=anchor.height_above_ground;
    }
    if (Array.isArray(geometry.vertical_limits) &&
            (value[2]<geometry.vertical_limits[0] || value[2]>geometry.vertical_limits[1])) return null;
    return profileProjected() ? [local.along,local.cross,value[2]] : value;
}
function renderAnnotations(items) {
    annotationItems=Array.isArray(items)?items:[];
    if (!annotationGroup) {
        annotationGroup=new THREE.Group();
        annotationGroup.name="PyForestScan annotations";
        context.viewer.scene.scene.add(annotationGroup);
    }
    annotationGroup.visible=sceneVisibility.annotations;
    while (annotationGroup.children.length) {
        const child=annotationGroup.children.pop();
        if (child.geometry) child.geometry.dispose();
        if (child.material) child.material.dispose();
    }
    annotationCount=0;
    for (const item of annotationItems) {
        const value=annotationDisplayPoint(item);
        if (!value) continue;
        const geometry=new THREE.BufferGeometry();
        geometry.setAttribute("position",new THREE.Float32BufferAttribute([0,0,0],3));
        const marker=new THREE.Points(geometry,new THREE.PointsMaterial(
            {color:0x39d98a,size:12,sizeAttenuation:false,depthTest:false}));
        marker.position.set(...value);
        marker.renderOrder=1110;
        marker.name=item.title||"Linked marker";
        marker.userData={annotation_id:item.annotation_id,title:item.title||""};
        annotationGroup.add(marker);
        annotationCount++;
    }
}
function renderLinkedCursor(command) {
    linkedCursor=command&&typeof command==="object"?command:null;
    if (!cursorGroup) {
        cursorGroup=new THREE.Group();
        cursorGroup.name="PyForestScan linked cursor";
        context.viewer.scene.scene.add(cursorGroup);
    }
    while (cursorGroup.children.length) {
        const child=cursorGroup.children.pop();
        if (child.geometry) child.geometry.dispose();
        if (child.material) child.material.dispose();
    }
    if (!linkedCursor||!linkedCursor.visible||!Array.isArray(linkedCursor.display_xyz)||
            linkedCursor.display_xyz.length!==3||linkedCursor.display_xyz.some(v=>!Number.isFinite(v))||
            !linkedView||linkedCursor.view_id!==linkedView.view_id) return;
    for (const [size,color,order] of [[14,0x5be4eb,1120],[5,0xffffff,1121]]) {
        const geometry=new THREE.BufferGeometry();
        geometry.setAttribute("position",new THREE.Float32BufferAttribute([0,0,0],3));
        const marker=new THREE.Points(geometry,new THREE.PointsMaterial(
            {color,size,sizeAttenuation:false,depthTest:false,transparent:true,opacity:.95}));
        marker.position.set(...linkedCursor.display_xyz);
        marker.renderOrder=order;
        marker.userData={authority:"TRANSIENT_LINKED_CURSOR",source_xyz:linkedCursor.source_xyz};
        cursorGroup.add(marker);
    }
}
function sourceXY(x, y, camera) {
    const canvas = context.viewer.renderer.domElement;
    return new THREE.Vector3(x / canvas.clientWidth * 2 - 1, 1 - y / canvas.clientHeight * 2, 0)
        .unproject(camera);
}
function drawPolygon(cursor) {
    if (!polygonLine) return;
    const points = cursor ? [...drawing.vertices, cursor] : drawing.vertices;
    polygonLine.setAttribute("points", points.map(p => p.join(",")).join(" "));
}
function completeDrawing() {
    const ring = drawing.close();
    if (ring) {
        const projected = ring.map(p => {
            const xyz = sourceXY(p[0], p[1], drawingCamera);
            if (drawingPurpose === "EDIT" && linkedView && linkedView.view_type === "VERTICAL_SLICE") {
                if (profileProjected()) return [xyz.x, xyz.z];
                const {a, b} = linkedView.geometry;
                const length = Math.hypot(b[0]-a[0], b[1]-a[1]);
                return [((xyz.x-a[0])*(b[0]-a[0])+(xyz.y-a[1])*(b[1]-a[1]))/length, xyz.z];
            }
            return xyz;
        });
        const geometry = projected.map(xyz => Array.isArray(xyz) ? xyz : [xyz.x, xyz.y]);
        const primitive = drawingPurpose === "MEASURE_AREA" ?
            {display_elevation:projected.reduce((total, xyz) => total + xyz.z, 0)/projected.length} : {};
        publish(geometry, primitive);
        drawing.resolving();
    } else latestEvent = {id: ++eventNumber, error: drawing.error};
    leaveTool();
}
function completeProfilePath() {
    const screenPath=drawing.finishPath(256);
    if (!screenPath) {
        latestEvent={id:++eventNumber,error:drawing.error};
        leaveTool();
        return;
    }
    const geometry=screenPath.map(p => {
        const xyz=sourceXY(p[0],p[1],drawingCamera);
        return [xyz.x,xyz.y];
    });
    publish(geometry);
    drawing.resolving();
    leaveTool();
}
function initialize(value) {
    context = value;
    const canvas = context.viewer.renderer.domElement;
    canvas.addEventListener("pointerdown", event => {
        if (tool === "Pointer") clearHoverCursor();
        if (tool !== "Pointer" && gestureMode === null)
            gestureMode = event.altKey ? "SUBTRACT" : event.shiftKey ? "ADD" : mode;
        if (tool === "Brush" && event.button === 0) {
            brushPointer = event.pointerId;
            drawing.vertex(event.offsetX,event.offsetY);
            canvas.setPointerCapture(event.pointerId);
            event.preventDefault(); event.stopPropagation();
            return;
        }
        if (!["Rectangle", "Box", "Circle", "Sphere"].includes(tool) || event.button !== 0) return;
        if (["Circle", "Sphere"].includes(tool) && linkedView && linkedView.view_type === "VERTICAL_SLICE") {
            latestEvent = {id: ++eventNumber, error: tool + " Select currently works in Overview and Area Detail. Use Polygon Select in Vertical Slice."};
            leaveTool();
            return;
        }
        rectangleStart = [event.offsetX, event.offsetY];
        rectangleBox = document.createElement("div");
        rectangleBox.style.cssText = "position:absolute;border:2px dashed #5be4eb;pointer-events:none;box-sizing:border-box";
        if (["Circle", "Sphere"].includes(tool)) rectangleBox.style.borderRadius = "50%";
        canvas.parentElement.appendChild(rectangleBox);
        canvas.setPointerCapture(event.pointerId);
        event.preventDefault();
        event.stopPropagation();
    }, true);
    canvas.addEventListener("pointermove", event => {
        if (tool === "Pointer" && event.buttons === 0) scheduleHoverCursor(event);
        else if (hoverCursor.active) clearHoverCursor();
        if (tool === "Brush" && brushPointer === event.pointerId) {
            const previous=drawing.vertices.at(-1);
            if (!previous || Math.hypot(previous[0]-event.offsetX,previous[1]-event.offsetY)>=3)
                drawing.vertex(event.offsetX,event.offsetY);
            drawPolygon([event.offsetX,event.offsetY]);
            event.preventDefault(); event.stopPropagation();
            return;
        }
        if (["Polygon", "ProfilePath", "Line", "AboveLine", "BelowLine"].includes(tool))
            drawPolygon([event.offsetX, event.offsetY]);
        if (!rectangleStart || !rectangleBox) return;
        const [x, y] = rectangleStart;
        if (tool === "Circle") {
            const radius = Math.hypot(event.offsetX-x, event.offsetY-y);
            Object.assign(rectangleBox.style, {left:(x-radius)+"px", top:(y-radius)+"px",
                width:(2*radius)+"px", height:(2*radius)+"px"});
        } else Object.assign(rectangleBox.style, {left: Math.min(x, event.offsetX) + "px",
            top: Math.min(y, event.offsetY) + "px", width: Math.abs(event.offsetX - x) + "px",
            height: Math.abs(event.offsetY - y) + "px"});
    }, true);
    canvas.addEventListener("pointerleave", clearHoverCursor, true);
    canvas.addEventListener("pointerup", event => {
        if (tool === "MeasureDistance" || tool === "AddAnnotation") {
            event.preventDefault(); event.stopImmediatePropagation();
            if (event.button !== 0) return;
            const hit = Potree.Utils && Potree.Utils.getMousePointCloudIntersection(
                {x:event.offsetX,y:event.offsetY}, context.viewer.scene.getActiveCamera(),
                context.viewer, [context.cloud]);
            if (!hit || !hit.location) {
                latestEvent={id:++eventNumber,error:"No displayed source point was found at that location. Try a visible point."};
                return;
            }
            const picked=[hit.location.x,hit.location.y,hit.location.z];
            if (tool === "AddAnnotation") {
                latestEvent={id:++eventNumber,action:"annotation_point",point:picked,
                    view_id:linkedView&&linkedView.view_id,
                    profile_display:profileProjected()};
                leaveTool();
                return;
            }
            measurementDraft.push(picked);
            if (measurementDraft.length === 1) {
                latestEvent={id:++eventNumber,action:"measurement_anchor",count:1};
            } else {
                latestEvent={id:++eventNumber,
                    action:measurementKind === "PROFILE_DISTANCE" ?
                        "measure_profile_points" : "measure_points",
                    points:measurementDraft.map(value=>value.slice()),
                    view_id:linkedView&&linkedView.view_id,
                    purpose:measurementPurpose};
                leaveTool();
            }
            return;
        }
        if (tool === "Brush" && brushPointer === event.pointerId) {
            if (canvas.hasPointerCapture(event.pointerId)) canvas.releasePointerCapture(event.pointerId);
            drawing.vertex(event.offsetX,event.offsetY);
            const screenPath=drawing.finishPath(2048);
            if (!screenPath) latestEvent={id:++eventNumber,error:drawing.error};
            else {
                const profile = linkedView && linkedView.view_type === "VERTICAL_SLICE";
                const path=screenPath.map(p => {
                    const xyz=sourceXY(p[0],p[1],drawingCamera);
                    if (!profile) return [xyz.x,xyz.y];
                    if (profileProjected()) return [xyz.x,xyz.z];
                    return [profileLocal(linkedView.geometry,xyz.x,xyz.y).along,xyz.z];
                });
                const simplified=simplifySourcePath(path,brushRadius,512);
                if (!simplified.path) latestEvent={id:++eventNumber,error:simplified.error};
                else {
                    const path=simplified.path, xs=path.map(p=>p[0]), ys=path.map(p=>p[1]);
                    if (profile) publish(linkedView.corridor,
                        {profile_brush_path:path,profile_brush_radius:brushRadius,
                         profile_brush_tolerance:simplified.tolerance});
                    else {
                        const geometry=[[Math.min(...xs)-brushRadius,Math.min(...ys)-brushRadius],
                            [Math.max(...xs)+brushRadius,Math.min(...ys)-brushRadius],
                            [Math.max(...xs)+brushRadius,Math.max(...ys)+brushRadius],
                            [Math.min(...xs)-brushRadius,Math.max(...ys)+brushRadius],
                            [Math.min(...xs)-brushRadius,Math.min(...ys)-brushRadius]];
                        publish(geometry,{brush_path:path,brush_radius:brushRadius,
                            brush_tolerance:simplified.tolerance});
                    }
                    drawing.resolving();
                }
            }
            leaveTool();
            event.preventDefault(); event.stopImmediatePropagation();
            return;
        }
        if (["Line", "AboveLine", "BelowLine"].includes(tool)) {
            event.preventDefault(); event.stopImmediatePropagation();
            if (event.button === 0) {
                drawing.vertex(event.offsetX, event.offsetY); drawPolygon();
                if (drawing.vertices.length === 2) {
                    const points=drawing.vertices.map(p => sourceXY(p[0],p[1],drawingCamera));
                    if (tool === "Line") {
                        publish(points.map(xyz => [xyz.x,xyz.y]));
                        drawing.cancel(); leaveTool();
                    } else if (!linkedView || linkedView.view_type !== "VERTICAL_SLICE") {
                        latestEvent={id:++eventNumber,error:"Above/Below Line is available only in Vertical Slice."};
                        drawing.cancel(); leaveTool();
                    } else {
                        const profileLine=points.map(xyz => {
                            if (profileProjected()) return [xyz.x,xyz.z];
                            const local=profileLocal(linkedView.geometry,xyz.x,xyz.y);
                            return [local.along,xyz.z];
                        });
                        if (!drawing.finishPath(2)) {
                            latestEvent={id:++eventNumber,error:drawing.error};
                            leaveTool();
                            return;
                        }
                        latestEvent={id:++eventNumber,geometry:linkedView.corridor,
                            mode:gestureMode||mode,profile_line:profileLine,
                            profile_line_side:tool === "AboveLine" ? "ABOVE" : "BELOW"};
                        drawing.resolving(); leaveTool();
                    }
                }
            }
            return;
        }
        if (tool === "Polygon") {
            event.preventDefault();
            event.stopImmediatePropagation();
            if (event.button === 0) {
                const first = drawing.vertices[0];
                if (drawing.vertices.length >= 3 && first &&
                    Math.hypot(first[0]-event.offsetX, first[1]-event.offsetY) <= 6) completeDrawing();
                else { drawing.vertex(event.offsetX, event.offsetY); drawPolygon(); }
            }
            return;
        }
        if (tool === "ProfilePath") {
            event.preventDefault();
            event.stopImmediatePropagation();
            if (event.button === 0) {
                drawing.vertex(event.offsetX,event.offsetY);
                drawPolygon();
            }
            return;
        }
        if (!rectangleStart || !["Rectangle", "Box", "Circle", "Sphere"].includes(tool)) return;
        const [x, y] = rectangleStart, xx = event.offsetX, yy = event.offsetY;
        if (canvas.hasPointerCapture(event.pointerId)) canvas.releasePointerCapture(event.pointerId);
        if (["Circle", "Sphere"].includes(tool) && Math.hypot(x-xx, y-yy) > 2) {
            const screenRadius = Math.hypot(x-xx, y-yy);
            for (const p of [[x-screenRadius,y-screenRadius], [x+screenRadius,y-screenRadius],
                    [x+screenRadius,y+screenRadius], [x-screenRadius,y+screenRadius]])
                drawing.vertex(...p);
            if (!drawing.close()) {
                latestEvent = {id: ++eventNumber, error: drawing.error};
                leaveTool();
                return;
            }
            const center = sourceXY(x, y, drawingCamera), edge = sourceXY(xx, yy, drawingCamera);
            const radius = Math.hypot(edge.x-center.x, edge.y-center.y);
            const geometry = [[center.x-radius,center.y-radius], [center.x+radius,center.y-radius],
                [center.x+radius,center.y+radius], [center.x-radius,center.y+radius],
                [center.x-radius,center.y-radius]];
            publish(geometry, tool === "Sphere" ?
                {sphere_center:[center.x,center.y,sphereHeight],sphere_radius:radius,sphere_axis:sphereAxis} :
                {circle_center:[center.x,center.y], circle_radius:radius});
            drawing.resolving(); leaveTool();
        } else if (["Rectangle", "Box"].includes(tool) && Math.abs(x - xx) > 2 && Math.abs(y - yy) > 2) {
            for (const p of [[x,y], [xx,y], [xx,yy], [x,yy]]) drawing.vertex(...p);
            completeDrawing();
        } else { drawing.cancel(); leaveTool(); latestEvent = {id: ++eventNumber, action: "pointer"}; }
    }, true);
    canvas.addEventListener("dblclick", event => {
        if (!["Polygon","ProfilePath"].includes(tool)) return;
        event.preventDefault(); event.stopImmediatePropagation();
        if (tool === "ProfilePath") completeProfilePath(); else completeDrawing();
    }, true);
    canvas.addEventListener("contextmenu", event => {
        if (!["Polygon","ProfilePath"].includes(tool)) return;
        event.preventDefault(); event.stopImmediatePropagation();
        if (tool === "ProfilePath") completeProfilePath(); else completeDrawing();
    }, true);
    canvas.addEventListener("pointercancel", () => {
        if (tool === "Pointer") return;
        drawing.cancel(); leaveTool(); latestEvent = {id: ++eventNumber, action: "pointer"};
    }, true);
    document.addEventListener("keydown", event => {
        if (event.key === "Enter" && ["Polygon","ProfilePath"].includes(tool)) {
            event.preventDefault();
            if (tool === "ProfilePath") completeProfilePath(); else completeDrawing();
        } else if (event.key === "Escape" && (tool !== "Pointer" || insertionPending)) {
            drawing.cancel();
            leaveTool();
            latestEvent = {id: ++eventNumber, action: "pointer"};
            event.preventDefault();
        } else if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "z") {
            latestEvent = {id: ++eventNumber, action: event.shiftKey ? "redo" : "undo"};
            event.preventDefault();
        }
    });
    requestAnimationFrame(paint);
}
function paint() {
    const start = performance.now();
    while (pending.length && performance.now() - start < 6) {
        const record = pending[0], {geometry, node, original} = record;
        const positions = geometry.getAttribute("position"), classes = geometry.getAttribute("classification");
        if (!classes || !positions) { pending.shift(); continue; }
        if (record.revision !== revision) {
            record.offset = 0;
            record.selected = [];
            record.colors = [];
            record.effectiveClasses = {};
            record.sourceUnchanged = true;
            record.revision = revision;
            removeHighlight(record);
            // Potree metadata bounds are cloud-relative, not node-buffer-relative.
            const box = node.geometryNode.boundingBox.clone().applyMatrix4(context.cloud.matrixWorld);
            record.edits = profileProjected() ? edits : edits.filter(edit => edit.definitions.some(definition =>
                definition.selection_mode !== "SUBTRACT" && definition.bounds[0] <= box.max.x &&
                definition.bounds[2] >= box.min.x && definition.bounds[1] <= box.max.y && definition.bounds[3] >= box.min.y));
        }
        for (let n = 0; n < 64 && record.offset < original.length; n++, record.offset++) {
            const i = record.offset;
            if (classes.array[i] !== original[i]) record.sourceUnchanged = false;
            point.fromBufferAttribute(positions, i).applyMatrix4(node.sceneNode.matrixWorld);
            const displayZ = point.z;
            sourcePointValue.copy(point);
            const originalX = sourceAttribute(geometry, "PFSOriginalX");
            const originalY = sourceAttribute(geometry, "PFSOriginalY");
            const originalZ = sourceAttribute(geometry, "PFSOriginalZ");
            if (originalX) sourcePointValue.x = originalX.array[i];
            if (originalY) sourcePointValue.y = originalY.array[i];
            if (originalZ) sourcePointValue.z = originalZ.array[i];
            let classification = original[i], classified = false, withheld = false, removed = false, objectEdited = false;
            for (const edit of record.edits) {
                if (!matches(edit.definitions, sourcePointValue, original[i], geometry, i)) continue;
                if (edit.attribute === "Classification") { classification = edit.value; classified = true; }
                else if (edit.attribute === "Withheld") withheld = Boolean(edit.value);
                else if (edit.attribute === "DELETE_ON_EXPORT") removed = Boolean(edit.value);
                else objectEdited = true;
            }
            record.effectiveClasses[classification] = (record.effectiveClasses[classification] || 0) + 1;
            const filters = window.editorSelectionFilters();
            const visible = (filters.classes === null || filters.classes.includes(original[i])) &&
                (!filters.height_filter || displayZ >= filters.height_filter[0] && displayZ <= filters.height_filter[1]);
            const selected = matches(selection, sourcePointValue, original[i], geometry, i);
            let color = null;
            if (selected && sceneVisibility.selection) color = selectionColor.toArray();
            else if (removed) color = [1, .25, .65];
            else if (withheld) color = [1, .8, .2];
            else if (objectEdited) color = [.25, .85, .55];
            else if (classified && context.cloud.material.activeAttributeName === "classification")
                color = window.editorClassificationColor(classification);
            if (visible && color) {
                record.selected.push(positions.getX(i), positions.getY(i), positions.getZ(i));
                record.colors.push(color[0], color[1], color[2]);
            }
        }
        if (record.offset >= original.length) {
            if (record.selected.length) {
                const highlighted = new THREE.BufferGeometry();
                highlighted.setAttribute("position", new THREE.Float32BufferAttribute(record.selected, 3));
                highlighted.setAttribute("color", new THREE.Float32BufferAttribute(record.colors, 3));
                record.highlight = new THREE.Points(highlighted,
                    new THREE.PointsMaterial({vertexColors: true, size: 3, sizeAttenuation: false, depthTest: false}));
                record.highlight.renderOrder = 1000;
                record.highlight.matrixAutoUpdate = false;
                record.highlight.matrix.copy(node.sceneNode.matrixWorld);
                context.viewer.scene.scene.add(record.highlight);
            }
            record.selected = [];
            record.colors = [];
            pending.shift();
        }
    }
    requestAnimationFrame(paint);
}
window.pointCloudEditor = {
    originalClasses(attribute) { return originals.get(attribute) || attribute.array; },
    tick(value) {
        if (!context) initialize(value);
        const signature = JSON.stringify(window.editorSelectionFilters()) + context.cloud.material.activeAttributeName;
        if (signature !== displaySignature) {
            displaySignature = signature;
            for (const record of records.values()) record.revision = -1;
        }
        const visible = new Set(context.cloud.visibleNodes || []);
        for (const [node, record] of records) if (!visible.has(node)) {
            removeHighlight(record);
            records.delete(node);
        }
        for (const node of visible) {
            const geometry = node.geometryNode && node.geometryNode.geometry;
            const extra = node.geometryNode && node.geometryNode.gpsTime && node.geometryNode.gpsTime.originalDimensions;
            // CPU membership metadata must not change Potree's registered GPU attribute layout.
            if (geometry && extra) geometry._pfsOriginalDimensions = extra;
            const classes = geometry && geometry.getAttribute("classification");
            if (!classes || !node.sceneNode) continue;
            if (!originals.has(classes)) originals.set(classes, classes.array.slice());
            if (!records.has(node)) records.set(node, {node, geometry, original: originals.get(classes), revision: -1, offset: 0});
        }
        pending = Array.from(records.values()).filter(r => r.revision !== revision || r.offset < r.original.length);
        const effectiveClasses = {};
        let highlighted = 0;
        for (const record of records.values()) {
            if (record.highlight) highlighted += record.highlight.geometry.getAttribute("position").count;
            for (const [code, count] of Object.entries(record.effectiveClasses || {}))
                effectiveClasses[code] = (effectiveClasses[code] || 0) + count;
        }
        const objectFocus = applyObjectFocus();
        return {event: latestEvent, tool, drawing_state: drawing.state, revision, pending_nodes: pending.length, ready: true,
            view_id: linkedView && linkedView.view_id,
            cursor: {...hoverCursor},
            linked_cursor_markers: cursorGroup ? cursorGroup.children.length : 0,
            highlighted_points: highlighted, effective_classes: effectiveClasses,
            object_focus_mode: objectFocus.requested, object_focus_effective: objectFocus.effective,
            measurement_count: measurementCount,
            annotation_count: annotationCount,
            workspace_profile_count: workspaceViewCount,
            scene_visibility: {...sceneVisibility},
            source_buffers_unchanged: Array.from(records.values()).every(r => r.sourceUnchanged !== false),
            overlay_diagnostics: Array.from(records.values()).slice(0, 3).map(r => ({
                node: r.node.name, edits: (r.edits || []).length,
                local_bounds: r.geometry.boundingBox && [r.geometry.boundingBox.min.toArray(), r.geometry.boundingBox.max.toArray()],
                translation: r.node.sceneNode.matrixWorld.elements.slice(12, 15)
            }))};
    },
    command(command) {
        if (command.action === "linked_view") {
            linkedView = command.view || null;
            if (context && measurementGroup) renderMeasurements(measurementItems);
            if (context && annotationGroup) renderAnnotations(annotationItems);
            if (context && workspaceGroup) renderWorkspaceViews(workspaceItems);
            if (context && cursorGroup) renderLinkedCursor(linkedCursor);
        }
        if (!context) return;
        if (command.action === "scene_visibility") {
            setSceneVisibility(command.visibility);
            return;
        }
        if (command.action === "measurement_tool") {
            if (command.kind && !["POINT_DISTANCE","PROFILE_DISTANCE"].includes(command.kind)) return;
            if (command.kind === "PROFILE_DISTANCE" &&
                    (!linkedView || linkedView.view_type !== "VERTICAL_SLICE")) {
                latestEvent={id:++eventNumber,error:"Cross-section measurement is available only in Vertical Slice."};
                return;
            }
            leaveTool();
            drawing.cancel();
            tool = "MeasureDistance";
            measurementKind = command.kind || "POINT_DISTANCE";
            measurementPurpose = command.purpose || "CROSS_SECTION";
            measurementDraft = [];
            context.viewer.inputHandler.enabled = false;
            context.viewer.renderer.domElement.style.cursor = "crosshair";
            return;
        }
        if (command.action === "measurements") {
            renderMeasurements(command.measurements || []);
            return;
        }
        if (command.action === "annotation_tool") {
            leaveTool();
            drawing.cancel();
            tool="AddAnnotation";
            context.viewer.inputHandler.enabled=false;
            context.viewer.renderer.domElement.style.cursor="crosshair";
            return;
        }
        if (command.action === "annotations") {
            renderAnnotations(command.annotations || []);
            return;
        }
        if (command.action === "workspace_views") {
            renderWorkspaceViews(command.profiles || []);
            return;
        }
        if (command.action === "linked_cursor") {
            renderLinkedCursor(command);
            return;
        }
        if (command.action === "selection_tool") {
            if (!["Pointer", "Polygon", "ProfilePath", "Rectangle", "Box", "Circle", "Sphere", "Brush", "Line", "AboveLine", "BelowLine"].includes(command.tool)) return;
            if (command.mode && !["REPLACE", "ADD", "SUBTRACT"].includes(command.mode)) return;
            if (command.tool === "Brush" &&
                    (!Number.isFinite(command.brush_radius) || command.brush_radius <= 0)) return;
            if (command.tool === "Sphere" &&
                    (!Number.isFinite(command.sphere_height) || !["Z", "HeightAboveGround"].includes(command.sphere_axis))) return;
            clearHoverCursor();
            leaveTool();
            drawing.cancel();
            mode = command.mode || "REPLACE";
            drawingPurpose = command.purpose || "EDIT";
            if (command.tool === "Brush") brushRadius=command.brush_radius;
            if (command.tool === "Sphere") { sphereAxis=command.sphere_axis; sphereHeight=command.sphere_height; }
            if (command.tool === "Pointer") {
                return;
            }
            const view = context.viewer.scene.view;
            if (view) savedNavigation = {position: view.position.clone(), yaw: view.yaw,
                pitch: view.pitch, radius: view.radius,
                cameraMode: context.viewer.scene.cameraMode || Potree.CameraMode.PERSPECTIVE};
            context.viewer.setCameraMode(Potree.CameraMode.ORTHOGRAPHIC);
            if (!linkedView || linkedView.view_type !== "VERTICAL_SLICE") context.viewer.setTopView();
            const epoch = toolEpoch;
            insertionPending = true;
            requestAnimationFrame(() => requestAnimationFrame(() => {
                if (epoch !== toolEpoch) return;
                insertionPending = false;
                tool = command.tool;
                drawing.arm(["ProfilePath", "Line", "Brush", "AboveLine", "BelowLine"].includes(tool) ? "Polygon" :
                    tool === "Circle" || tool === "Sphere" || tool === "Box" ? "Rectangle" : tool, mode);
                drawingCamera = context.viewer.scene.getActiveCamera().clone();
                context.viewer.inputHandler.enabled = false;
                if (["Polygon", "ProfilePath", "Line", "Brush", "AboveLine", "BelowLine"].includes(tool)) {
                    polygonOverlay = document.createElementNS("http://www.w3.org/2000/svg", "svg");
                    polygonOverlay.style.cssText = "position:absolute;inset:0;width:100%;height:100%;pointer-events:none";
                    polygonLine = document.createElementNS("http://www.w3.org/2000/svg", "polyline");
                    polygonLine.setAttribute("fill", "none");
                    polygonLine.setAttribute("stroke", "#5be4eb");
                    polygonLine.setAttribute("stroke-width", "2");
                    if (tool === "Brush") {
                        const a=sourceXY(0,0,drawingCamera), b=sourceXY(1,0,drawingCamera);
                        const unitsPerPixel=linkedView&&linkedView.view_type==="VERTICAL_SLICE" ?
                            Math.hypot(b.x-a.x,b.z-a.z) : Math.hypot(b.x-a.x,b.y-a.y);
                        const width=Number.isFinite(unitsPerPixel) && unitsPerPixel > 0
                            ? Math.max(.25,2*brushRadius/unitsPerPixel) : 2;
                        polygonLine.setAttribute("stroke-width", String(width));
                        polygonLine.setAttribute("stroke-linecap","round");
                        polygonLine.setAttribute("stroke-linejoin","round");
                        polygonLine.setAttribute("stroke-opacity",".6");
                    }
                    polygonOverlay.appendChild(polygonLine);
                    context.viewer.renderer.domElement.parentElement.appendChild(polygonOverlay);
                }
            }));
        }
        if (command.action === "selection_resolution") {
            if (command.error) drawing.fail(command.error);
            else drawing.resolved();
        }
        if (command.action === "object_focus") {
            window.viewerRenderPolicy.objectFocus(command.mode, selection.length > 0);
            objectFocusMode = command.mode;
            applyObjectFocus();
        }
        if (command.action === "selection_test") publish(command.geometry,
            Object.fromEntries(["circle_center", "circle_radius", "brush_path", "brush_radius", "brush_tolerance",
                "profile_brush_path", "profile_brush_radius", "profile_brush_tolerance",
                "sphere_center", "sphere_radius", "sphere_axis", "invert_result", "profile_line",
                "profile_line_side"].filter(key => key in command)
                .map(key => [key, command[key]])));
        if (command.action === "editor_overlay") {
            if (/^#[0-9a-f]{6}$/i.test(command.selection_color || "")) selectionColor.set(command.selection_color);
            const request = ++requestedRevision;
            fetch("editor-overlay.json").then(response => {
                if (!response.ok) throw Error("Overlay state unavailable.");
                return response.json();
            }).then(data => {
                if (request !== requestedRevision) return;
                edits = data.edits.map(edit => ({...edit, definitions: edit.definitions.map(compile)}));
                selection = data.selection.map(compile);
                revision = data.revision;
                applyObjectFocus();
                for (const record of records.values()) record.revision = -1;
            }).catch(error => { latestEvent = {id: ++eventNumber, error: String(error)}; });
        }
    }
};
