"""Source-aware bounded work planning for polygon LiDAR products."""
from __future__ import annotations
import hashlib, json, math, os
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Iterable

class WorkUnitType(str, Enum):
    SINGLE_SOURCE_FILE="single_source_file"
    GROUPED_SOURCE_FILES="grouped_source_files"
    SUBDIVIDED_LARGE_SOURCE="subdivided_large_source"
    EPT_WINDOW="ept_window"
    COPC_WINDOW="copc_window"

@dataclass(frozen=True)
class SpatialExtent:
    xmin: float; ymin: float; xmax: float; ymax: float
    @property
    def width(self): return max(0.0,self.xmax-self.xmin)
    @property
    def height(self): return max(0.0,self.ymax-self.ymin)
    def intersects(self,other): return not (self.xmax<=other.xmin or self.xmin>=other.xmax or self.ymax<=other.ymin or self.ymin>=other.ymax)
    def buffered(self,d): return SpatialExtent(self.xmin-d,self.ymin-d,self.xmax+d,self.ymax+d)

@dataclass(frozen=True)
class AlignedRasterGrid:
    crs: str; resolution: float; origin_x: float; origin_y: float; total_extent: SpatialExtent; rows: int; columns: int; nodata: float=-9999.0; data_type: str="float32"
    @classmethod
    def from_extent(cls,extent,resolution,crs,nodata=-9999.0):
        if not math.isfinite(resolution) or resolution<=0: raise ValueError("Raster resolution must be finite and positive.")
        cols=math.ceil(extent.width/resolution);rows=math.ceil(extent.height/resolution)
        aligned=SpatialExtent(extent.xmin,extent.ymin,extent.xmin+cols*resolution,extent.ymin+rows*resolution)
        return cls(crs,resolution,extent.xmin,extent.ymin,aligned,rows,cols,nodata)
    @property
    def grid_signature(self):
        payload={"crs":self.crs,"resolution":self.resolution,"origin_x":self.origin_x,"origin_y":self.origin_y,"extent":asdict(self.total_extent),"rows":self.rows,"columns":self.columns,"nodata":self.nodata,"data_type":self.data_type}
        return hashlib.sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest()
    def cell_extent(self,row0,row1,col0,col1):
        return SpatialExtent(self.origin_x+col0*self.resolution,self.origin_y+row0*self.resolution,self.origin_x+col1*self.resolution,self.origin_y+row1*self.resolution)

@dataclass(frozen=True)
class NativeSource:
    path: Path; bounds: SpatialExtent; size_bytes: int=0; point_count: int|None=None; source_type: str="las"

@dataclass(frozen=True)
class WorkUnitSizingPolicy:
    target_width: float; target_height: float; buffer_distance: float; maximum_estimated_points: int; maximum_expected_memory: int; maximum_concurrent_units: int; rationale: str; confidence: str; strategy:str="adaptive";estimated_point_range:tuple[int,int]=(0,0);expected_memory_range:tuple[int,int]=(0,0);pilot_required:bool=False

@dataclass(frozen=True)
class ProductPartitionPolicy:
    product: str; partitionable: bool; required_buffer: float; core_output_rule: str; merge_rule: str; scientific_caveats: tuple[str,...]; resume_support: bool; equivalence_status: str; default_enabled: bool

PRODUCT_POLICIES={
 "chm":ProductPartitionPolicy("chm",True,50.0,"discard buffered pixels; retain globally aligned core","deterministic first-valid core cells","Tiled/reference equivalence requires live measurement.",True,"provisional",True),
 "rumple":ProductPartitionPolicy("rumple",True,1.0,"retain patch-centered aligned core after one-cell CHM halo","deterministic first-valid patch cells",("Array-level equivalence is validated; coordinator execution is not enabled.",),True,"synthetic-equivalence",False),
 **{p:ProductPartitionPolicy(p,False,0.0,"monolithic","not reviewed",("Partition merge behavior is not validated.",),False,"not reviewed",False) for p in ("pad","pai","fhd","canopy_cover","dtm","point_density","voxel_stat")}
}

@dataclass(frozen=True)
class WorkUnit:
    work_unit_id: str; unit_type: WorkUnitType; source_paths: tuple[Path,...]; core_extent: SpatialExtent; read_extent: SpatialExtent; row_start: int; row_end: int; column_start: int; column_end: int; execution_order: int; estimated_memory: int; status: str="Pending"; polygon_intersection_area:float=0.0;polygon_coverage_percent:float=0.0;required_for_output:bool=True;planning_reason:str="core intersects polygon";buffered_polygon_intersects:bool=False;source_coverage_expectation:str="unknown"

@dataclass(frozen=True)
class SourceAwareWorkPlan:
    repository_kind: str; product: str; grid: AlignedRasterGrid; work_units: tuple[WorkUnit,...]; concurrency_limit: int; workload_category: str; memory_category: str; merge_strategy: str; retry_policy: str; checkpoint_policy: str; scientific_assumptions: tuple[str,...]; source_location: str; physical_retiling: bool=False;candidate_work_units:tuple[WorkUnit,...]=();skipped_work_units:tuple[WorkUnit,...]=();exact_polygon_signature:str="";buffer_policy:str="";hag_method_signature:str="";adaptive_strategy:str="adaptive";target_work_unit_width:float=0.0;target_work_unit_height:float=0.0;estimated_point_range:tuple[int,int]=(0,0);expected_memory_range:tuple[int,int]=(0,0);pilot_required:bool=False;native_partitions_reused:int=0;logical_subdivisions_added:int=0
    @property
    def candidate_count(self):return len(self.candidate_work_units or self.work_units)
    @property
    def required_count(self):return len(self.work_units)
    @property
    def skipped_count(self):return len(self.skipped_work_units)
    @property
    def core_area(self):return sum(unit.core_extent.width*unit.core_extent.height for unit in self.work_units)
    @property
    def buffered_read_area(self):return sum(unit.read_extent.width*unit.read_extent.height for unit in self.work_units)
    @property
    def read_amplification(self):return self.buffered_read_area/self.core_area if self.core_area else 1.0
    @property
    def estimated_peak_memory(self):return max((unit.estimated_memory for unit in self.work_units),default=0)*max(1,self.concurrency_limit)
    @property
    def plan_signature(self):
        payload={"grid_signature":self.grid.grid_signature,"repository_kind":self.repository_kind,"product":self.product,"exact_polygon_signature":self.exact_polygon_signature,"buffer_policy":self.buffer_policy,"hag_method_signature":self.hag_method_signature,"required_ids":[unit.work_unit_id for unit in self.work_units],"skipped_ids":[unit.work_unit_id for unit in self.skipped_work_units],"source_identity":sorted({str(path) for unit in self.candidate_work_units for path in unit.source_paths})}
        return hashlib.sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest()
    def to_dict(self):
        def conv(v):
            if isinstance(v,Path): return str(v)
            if isinstance(v,Enum): return v.value
            if hasattr(v,'__dataclass_fields__'): return {k:conv(x) for k,x in asdict(v).items()}
            if isinstance(v,(tuple,list)): return [conv(x) for x in v]
            if isinstance(v,dict): return {k:conv(x) for k,x in v.items()}
            return v
        return conv(self)

def source_location(path: Path|str) -> str:
    text=str(path)
    if text.startswith(('http://','https://','s3://')): return 'remote_url'
    if text.startswith(('\\','//')): return 'network'
    if os.name=='nt' and len(text)>1 and text[1]==':': return 'mapped_or_local_drive'
    return 'local'

def sizing_policy(*,repository_kind,product,resolution,available_memory_bytes,cpu_count,network=False,point_density=None,profile='recommended',extent=None,polygon_area=None,native_partition_count=0,hag_method='existing_normalized_height'):
    from .adaptive_processing import AdaptivePlannerInputs,derive_adaptive_plan
    width=getattr(extent,'width',1000.0);height=getattr(extent,'height',1000.0);area=max(0.0,width*height)
    adaptive=derive_adaptive_plan(AdaptivePlannerInputs(width,height,polygon_area if polygon_area is not None else area,resolution,repository_kind,point_density,available_memory_bytes,cpu_count,network,product,hag_method,native_partition_count))
    concurrency=adaptive.concurrency
    if profile=='conservative':concurrency=1
    elif profile=='performance' and not network and (repository_kind!='ept' or os.environ.get('PYFORESTSCAN_DEV_EPT_PARALLEL')=='1'):concurrency=min(max(1,cpu_count),4,max(1,concurrency+1))
    rationale=' '.join(adaptive.rationale)
    return WorkUnitSizingPolicy(adaptive.target_width,adaptive.target_height,adaptive.buffer_distance,adaptive.estimated_points_per_unit[1],adaptive.expected_memory_per_unit[1],concurrency,rationale,adaptive.confidence,adaptive.strategy,adaptive.estimated_points_per_unit,adaptive.expected_memory_per_unit,adaptive.pilot_required)


class SourceAwareWorkPlanner:
    def plan(self,*,repository_kind,sources,polygon_envelope,processing_crs,product,resolution,available_memory_bytes=8*1024**3,cpu_count=2,profile='recommended',polygon_wkt=None):
        policy=PRODUCT_POLICIES.get(product)
        if policy is None or not policy.partitionable: raise ValueError(f"{product} does not have a validated partition policy.")
        grid=AlignedRasterGrid.from_extent(polygon_envelope,resolution,processing_crs)
        paths=tuple(sources); location=source_location(paths[0].path) if paths else 'local'; network=location in {'network','remote_url'}
        exact_area=None
        if polygon_wkt:
            from .work_unit_geometry import measure_core_polygon_intersection
            exact_area=measure_core_polygon_intersection(grid.total_extent,polygon_wkt).intersection_area
        sizing=sizing_policy(repository_kind=repository_kind,product=product,resolution=resolution,available_memory_bytes=available_memory_bytes,cpu_count=cpu_count,network=network,profile=profile,extent=grid.total_extent,polygon_area=exact_area,native_partition_count=len(paths),point_density=next((source.point_count/source.bounds.width/source.bounds.height for source in paths if source.point_count and source.bounds.width and source.bounds.height),None))
        if repository_kind=='ept': units=self._windows(grid,paths,WorkUnitType.EPT_WINDOW,sizing)
        elif repository_kind=='copc': units=self._copc(grid,paths,sizing)
        else: units=self._native(grid,paths,sizing)
        candidates=tuple(units);skipped=()
        if polygon_wkt:
            from dataclasses import replace
            from .work_unit_geometry import measure_core_polygon_intersection
            measured=[]
            for unit in candidates:
                intersection=measure_core_polygon_intersection(unit.core_extent,polygon_wkt);buffered=measure_core_polygon_intersection(unit.read_extent,polygon_wkt)
                measured.append(replace(unit,polygon_intersection_area=intersection.intersection_area,polygon_coverage_percent=intersection.coverage_percent,required_for_output=intersection.intersects,status="Pending" if intersection.intersects else "SkippedOutsidePolygon",planning_reason="positive core/polygon area" if intersection.intersects else "zero exact core/polygon area",buffered_polygon_intersects=buffered.intersects,source_coverage_expectation="expected"))
            candidates=tuple(measured);units=[unit for unit in candidates if unit.required_for_output];skipped=tuple(unit for unit in candidates if not unit.required_for_output)
        cells=grid.rows*grid.columns; workload='Small' if cells<5_000_000 else 'Moderate' if cells<25_000_000 else 'Large' if cells<100_000_000 else 'Very Large'
        peak=max((unit.estimated_memory for unit in units),default=cells*4)
        memory='Low' if peak<256*1024**2 else 'Moderate' if peak<1024**3 else 'High' if peak<3*1024**3 else 'Very High'
        assumptions=[f"Global {resolution:g}-unit grid.",f"{sizing.buffer_distance:g}-unit CHM read buffer.",f"Adaptive strategy: {sizing.strategy}.",sizing.rationale,"Exact polygon mask is applied after mosaic."]
        if repository_kind=='ept' and product=='chm' and sizing.maximum_concurrent_units==1:assumptions.extend(("Safe processing mode is active for this EPT job.","Parallel EPT HAG workers are temporarily limited while native-worker stability is being validated."))
        polygon_signature=hashlib.sha256((polygon_wkt or "").strip().encode()).hexdigest() if polygon_wkt else ""
        hag_signature=hashlib.sha256(b"existing_normalized_height:HeightAboveGround").hexdigest()
        native_reused=len(paths) if repository_kind in {'folder','las','laz'} else 0
        subdivisions=max(0,len(units)-native_reused)
        effective_concurrency=min(sizing.maximum_concurrent_units,max(1,len(units)))
        return SourceAwareWorkPlan(repository_kind,product,grid,tuple(units),effective_concurrency,workload,memory,policy.merge_rule,'transient failures: 2; deterministic input/HAG failures: 0','verify and persist every completed core tile',tuple(assumptions),location,False,candidates,skipped,polygon_signature,f"buffer={sizing.buffer_distance:g}",hag_signature,sizing.strategy,sizing.target_width,sizing.target_height,sizing.estimated_point_range,sizing.expected_memory_range,sizing.pilot_required,native_reused,subdivisions)
    def _windows(self,grid,sources,kind,sizing):
        cols=max(1,round(sizing.target_width/grid.resolution));rows=max(1,round(sizing.target_height/grid.resolution));out=[];n=0
        for r0 in range(0,grid.rows,rows):
            for c0 in range(0,grid.columns,cols):
                core=grid.cell_extent(r0,min(grid.rows,r0+rows),c0,min(grid.columns,c0+cols));n+=1
                read=core.buffered(sizing.buffer_distance)
                density=20.0 if kind is WorkUnitType.EPT_WINDOW else 8.0
                from .resource_estimation import estimate_work_unit_resources
                estimate=estimate_work_unit_resources(int(read.width*read.height*density),hag_method="existing_normalized_height",raster_cells=int(read.width*read.height/grid.resolution**2),core_width=sizing.target_width)
                out.append(WorkUnit(f"wu-{n:04d}",kind,tuple(x.path for x in sources),core,read,r0,min(grid.rows,r0+rows),c0,min(grid.columns,c0+cols),n,estimate.estimated_memory))
        return out
    def _copc(self,grid,sources,sizing):
        if len(sources)==1 and (sources[0].size_bytes>2*1024**3 or grid.rows*grid.columns>5_000_000): return self._windows(grid,sources,WorkUnitType.COPC_WINDOW,sizing)
        return self._native(grid,sources,sizing)
    def _native(self,grid,sources,sizing):
        selected=[x for x in sources if x.bounds.intersects(grid.total_extent)];out=[];group=[];size=0
        def flush():
            nonlocal group,size
            if not group:return
            xmin=max(grid.total_extent.xmin,min(x.bounds.xmin for x in group));ymin=max(grid.total_extent.ymin,min(x.bounds.ymin for x in group));xmax=min(grid.total_extent.xmax,max(x.bounds.xmax for x in group));ymax=min(grid.total_extent.ymax,max(x.bounds.ymax for x in group));core=SpatialExtent(xmin,ymin,xmax,ymax)
            typ=WorkUnitType.SINGLE_SOURCE_FILE if len(group)==1 else WorkUnitType.GROUPED_SOURCE_FILES
            out.append(WorkUnit(f"wu-{len(out)+1:04d}",typ,tuple(x.path for x in group),core,core.buffered(sizing.buffer_distance),0,grid.rows,0,grid.columns,len(out)+1,max(size*3,1)));group=[];size=0
        for src in sorted(selected,key=lambda x:(x.bounds.ymin,x.bounds.xmin)):
            overlap=SpatialExtent(max(src.bounds.xmin,grid.total_extent.xmin),max(src.bounds.ymin,grid.total_extent.ymin),min(src.bounds.xmax,grid.total_extent.xmax),min(src.bounds.ymax,grid.total_extent.ymax))
            density=src.point_count/(src.bounds.width*src.bounds.height) if src.point_count and src.bounds.width and src.bounds.height else 8.0
            estimated_points=int(overlap.width*overlap.height*density)
            from .resource_estimation import estimate_work_unit_resources
            source_estimate=estimate_work_unit_resources(estimated_points,raster_cells=int(overlap.width*overlap.height/grid.resolution**2),core_width=sizing.target_width)
            subdivision_limit=sizing.maximum_expected_memory+256*1024**2
            if src.size_bytes>2*1024**3 or source_estimate.estimated_memory>subdivision_limit:
                flush();subgrid=AlignedRasterGrid.from_extent(overlap,grid.resolution,grid.crs);out.extend(self._windows(subgrid,(src,),WorkUnitType.SUBDIVIDED_LARGE_SOURCE,sizing));continue
            if group:
                union=SpatialExtent(min(x.bounds.xmin for x in group),min(x.bounds.ymin for x in group),max(x.bounds.xmax for x in group),max(x.bounds.ymax for x in group))
                adjacent=union.buffered(max(sizing.buffer_distance, sizing.target_width * 0.1)).intersects(src.bounds)
                if size+src.size_bytes>1024**3 or not adjacent: flush()
            group.append(src);size+=src.size_bytes
        flush();return out
