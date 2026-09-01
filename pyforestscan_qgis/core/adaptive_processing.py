"""Workload-derived processing scale selection without preferred tile counts."""
from __future__ import annotations
from dataclasses import dataclass,replace
import math,os

@dataclass(frozen=True)
class AdaptivePlannerInputs:
    envelope_width:float;envelope_height:float;polygon_area:float;output_resolution:float
    source_type:str="ept";point_density:float|None=None;available_memory_bytes:int=8*1024**3
    cpu_count:int=2;network:bool=False;product:str="chm";hag_method:str="existing_normalized_height"
    native_partition_count:int=0;historical_memory_per_million:float|None=None;historical_points_per_second:float|None=None

@dataclass(frozen=True)
class AdaptiveProcessingPlan:
    strategy:str;target_width:float;target_height:float;buffer_distance:float
    estimated_points_per_unit:tuple[int,int];expected_memory_per_unit:tuple[int,int]
    concurrency:int;native_partitions_reused:int;logical_subdivisions_added:int
    estimated_work_units:int;rationale:tuple[str,...];confidence:str;pilot_required:bool

@dataclass(frozen=True)
class PilotMeasurement:
    area:float;point_count:int;read_seconds:float;calculation_seconds:float;write_seconds:float
    peak_memory_bytes:int;stable_concurrency:int=1

def available_memory_bytes(default=8*1024**3):
    try:
        if os.name=='nt':
            import ctypes
            class Status(ctypes.Structure):_fields_=[('length',ctypes.c_ulong),('memory_load',ctypes.c_ulong),('total_physical',ctypes.c_ulonglong),('available_physical',ctypes.c_ulonglong),('total_page',ctypes.c_ulonglong),('available_page',ctypes.c_ulonglong),('total_virtual',ctypes.c_ulonglong),('available_virtual',ctypes.c_ulonglong),('available_extended',ctypes.c_ulonglong)]
            status=Status();status.length=ctypes.sizeof(Status)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):return int(status.available_physical)
        pages=os.sysconf('SC_AVPHYS_PAGES');size=os.sysconf('SC_PAGE_SIZE');return int(pages*size)
    except (AttributeError,KeyError,OSError,ValueError):return int(default)
    return int(default)

def derive_adaptive_plan(inputs:AdaptivePlannerInputs)->AdaptiveProcessingPlan:
    if inputs.output_resolution<=0:raise ValueError('Output resolution must be positive.')
    envelope_area=max(0.0,inputs.envelope_width*inputs.envelope_height);polygon_area=max(0.0,min(inputs.polygon_area or envelope_area,envelope_area))
    compactness=polygon_area/envelope_area if envelope_area else 1.0
    density=max(0.01,float(inputs.point_density if inputs.point_density is not None else _default_density(inputs.source_type)))
    from .resource_estimation import estimated_point_memory_bytes
    bytes_per_point=estimated_point_memory_bytes(hag_method=inputs.hag_method)
    if inputs.historical_memory_per_million and inputs.historical_memory_per_million>0:bytes_per_point=max(bytes_per_point,inputs.historical_memory_per_million/1_000_000.0)
    memory_budget=max(256*1024**2,min(int(inputs.available_memory_bytes*.22),3*1024**3))
    point_limit=max(500_000,min(30_000_000,int(memory_budget/(bytes_per_point*1.6))))
    raster_working_bytes=48.0 if inputs.product=='rumple' else 32.0
    raster_cell_limit=max(1_000_000,min(36_000_000,int(memory_budget/(raster_working_bytes*1.25))))
    safe_area=min(point_limit/density,raster_cell_limit*inputs.output_resolution**2)
    safe_width=math.sqrt(max(1.0,safe_area))
    lower=250.0 if inputs.network else 300.0;upper=2200.0 if inputs.network else 4000.0
    shape_scale=min(1.75,1.0/math.sqrt(max(compactness,.25)))
    width=max(lower,min(upper,safe_width*shape_scale));height=width
    estimated_points=int(polygon_area*density);output_cells=int(envelope_area/(inputs.output_resolution**2))
    fast_safe=(
        estimated_points<=point_limit
        and output_cells<=raster_cell_limit
        and estimated_points*bytes_per_point<=memory_budget
    )
    if fast_safe:
        width=max(inputs.envelope_width,1.0);height=max(inputs.envelope_height,1.0);strategy='small_safe_request';estimated_units=1
    else:
        cols=max(1,math.ceil(inputs.envelope_width/width));rows=max(1,math.ceil(inputs.envelope_height/height));estimated_units=max(1,math.ceil(cols*rows*max(compactness,.05)))
        strategy='medium_bounded' if estimated_units<=8 else 'large_bounded' if estimated_units<=128 else 'very_large_bounded'
    estimated_unit_area=min(envelope_area,max(1.0,width*height));central=int(estimated_unit_area*density)
    point_range=(max(0,int(central*.55)),max(1,int(central*1.6)))
    memory_range=(int(point_range[0]*bytes_per_point),int(point_range[1]*bytes_per_point))
    memory_concurrency=max(1,int((inputs.available_memory_bytes*.55)/max(memory_range[1],1)))
    concurrency=max(1,min(int(inputs.cpu_count or 1),4,memory_concurrency))
    if inputs.network:concurrency=min(concurrency,2)
    if inputs.source_type=='ept' and os.environ.get('PYFORESTSCAN_DEV_EPT_PARALLEL')!='1':concurrency=1
    native_reused=inputs.native_partition_count if inputs.source_type in {'las','laz','folder'} else 0
    shared_note='Rumple memory includes simultaneous buffered CHM, patch raster, and mosaic buffers.' if inputs.product=='rumple' else 'CHM memory includes buffered raster and output buffers.'
    rationale=(f'Unit scale derives from {density:g} points/m2, {memory_budget/1024**2:.0f} MiB per-unit budget, and {inputs.output_resolution:g}-unit output cells.',shared_note,f'Polygon occupies {compactness:.0%} of its envelope; no preferred work-unit count is used.',f'{"Network-aware" if inputs.network else "Local"} concurrency is bounded by memory and CPU.')
    return AdaptiveProcessingPlan(strategy,width,height,50.0 if inputs.product in {'chm','rumple'} else 0.0,point_range,memory_range,concurrency,native_reused,max(0,estimated_units-native_reused),estimated_units,rationale,'high' if inputs.point_density is not None else 'medium',not fast_safe and inputs.point_density is None)

def calibrate_from_pilot(plan:AdaptiveProcessingPlan,measurement:PilotMeasurement,available_memory_bytes:int,cpu_count:int,network:bool=False)->AdaptiveProcessingPlan:
    if measurement.area<=0 or measurement.point_count<=0:return replace(plan,confidence='low',rationale=plan.rationale+('Pilot contained no representative points; initial safety plan retained.',))
    target_memory=max(256*1024**2,min(int(available_memory_bytes*.22),3*1024**3));memory_ratio=target_memory/max(measurement.peak_memory_bytes,1)
    duration=measurement.read_seconds+measurement.calculation_seconds+measurement.write_seconds;duration_ratio=180.0/max(duration,1.0)
    area_scale=max(.35,min(2.25,min(memory_ratio,duration_ratio)));linear_scale=math.sqrt(area_scale)
    width=max(250.0,min(5000.0,plan.target_width*linear_scale));height=max(250.0,min(5000.0,plan.target_height*linear_scale))
    concurrency=max(1,min(cpu_count,4,measurement.stable_concurrency,max(1,int((available_memory_bytes*.55)/max(measurement.peak_memory_bytes,1)))))
    if network:concurrency=min(concurrency,2)
    direction='decreased' if linear_scale<.9 else 'increased' if linear_scale>1.1 else 'retained'
    return replace(plan,target_width=width,target_height=height,concurrency=concurrency,confidence='high',pilot_required=False,rationale=plan.rationale+(f'Pilot {direction} unit width using measured duration and peak memory.',))

def _default_density(source_type):return {'ept':20.0,'copc':12.0,'las':8.0,'laz':8.0,'folder':8.0}.get(str(source_type).lower(),10.0)
