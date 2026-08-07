"""QGIS-free exact polygon/core intersection measurements."""
from __future__ import annotations
from dataclasses import dataclass
from .polygon_transport import wkt_to_geojson_geometry

@dataclass(frozen=True)
class CorePolygonIntersection:
    intersects:bool;intersection_area:float;coverage_percent:float;boundary_touch_only:bool

def measure_core_polygon_intersection(extent,polygon_wkt):
    geometry=wkt_to_geojson_geometry(polygon_wkt);polygons=geometry["coordinates"] if geometry["type"]=="MultiPolygon" else [geometry["coordinates"]]
    area=0.0;touch=False
    for polygon in polygons:
        if not polygon:continue
        exterior=_clipped_ring_area(polygon[0],extent);holes=sum(_clipped_ring_area(ring,extent) for ring in polygon[1:])
        area+=max(0.0,exterior-holes)
        touch=touch or _boundary_touches(polygon,extent)
    core_area=max(0.0,extent.width*extent.height);area=min(core_area,max(0.0,area))
    return CorePolygonIntersection(area>1e-9,area,(area/core_area*100.0) if core_area else 0.0,touch and area<=1e-9)

def _clipped_ring_area(ring,extent):
    points=[(float(p[0]),float(p[1])) for p in ring]
    for axis,value,keep_greater in ((0,extent.xmin,True),(0,extent.xmax,False),(1,extent.ymin,True),(1,extent.ymax,False)):
        points=_clip(points,axis,value,keep_greater)
        if not points:return 0.0
    return abs(sum(points[i][0]*points[(i+1)%len(points)][1]-points[(i+1)%len(points)][0]*points[i][1] for i in range(len(points)))/2.0)

def _clip(points,axis,value,keep_greater):
    if not points:return []
    result=[]
    def inside(p):return p[axis]>=value if keep_greater else p[axis]<=value
    def intersect(a,b):
        delta=b[axis]-a[axis]
        if abs(delta)<1e-15:return a
        t=(value-a[axis])/delta
        return (value,a[1]+t*(b[1]-a[1])) if axis==0 else (a[0]+t*(b[0]-a[0]),value)
    previous=points[-1];previous_inside=inside(previous)
    for current in points:
        current_inside=inside(current)
        if current_inside:
            if not previous_inside:result.append(intersect(previous,current))
            result.append(current)
        elif previous_inside:result.append(intersect(previous,current))
        previous,previous_inside=current,current_inside
    return result

def _boundary_touches(polygons,extent):
    for ring in polygons:
        for point in ring:
            x,y=float(point[0]),float(point[1])
            if extent.xmin<=x<=extent.xmax and extent.ymin<=y<=extent.ymax:return True
    return False
