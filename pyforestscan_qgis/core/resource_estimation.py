"""Empirical resource estimates for bounded LiDAR work units."""
from dataclasses import dataclass

@dataclass(frozen=True)
class WorkUnitResourceEstimate:
    point_count:int;point_item_size:int;array_copies:int;hag_method:str;raster_bytes:int;estimated_memory:int;confidence:str;workload_category:str;recommended_concurrency:int;recommended_core_width:float;rationale:str

def estimated_point_memory_bytes(*, point_item_size=48, array_copies=3, hag_method="existing_normalized_height"):
    """Return the shared point-memory model used by planning and execution."""
    triangulation = 3.0 if hag_method == "classified_ground_delaunay" else 0.35
    native_multiplier = 1.75
    return float(point_item_size * (array_copies + native_multiplier + triangulation))

def estimate_work_unit_resources(point_count,*,point_item_size=48,array_copies=3,hag_method="existing_normalized_height",raster_cells=0,available_memory=8*1024**3,core_width=750.0):
    points=max(0,int(point_count));point_bytes=int(points*estimated_point_memory_bytes(point_item_size=point_item_size,array_copies=array_copies,hag_method=hag_method));raster_bytes=int(raster_cells*4*3);total=point_bytes+raster_bytes+128*1024**2
    category="Low" if total<256*1024**2 else "Moderate" if total<1024**3 else "High" if total<3*1024**3 else "Very High"
    concurrency=max(1,min(4,int((available_memory*.55)/max(total,1))))
    width=core_width
    if total>available_memory*.4:width=max(250.0,core_width*.67)
    return WorkUnitResourceEstimate(points,point_item_size,array_copies,hag_method,raster_bytes,total,"medium" if points else "low",category,concurrency,width,f"Estimate includes {array_copies} point-array copies, native PDAL overhead, raster working arrays, and {'triangulation' if hag_method == 'classified_ground_delaunay' else 'existing-HAG'} overhead.")
