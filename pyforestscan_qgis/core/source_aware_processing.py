"""Source-aware bounded work planning for polygon LiDAR products."""
from __future__ import annotations
import math, os
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
    def cell_extent(self,row0,row1,col0,col1):
        return SpatialExtent(self.origin_x+col0*self.resolution,self.origin_y+row0*self.resolution,self.origin_x+col1*self.resolution,self.origin_y+row1*self.resolution)

@dataclass(frozen=True)
class NativeSource:
    path: Path; bounds: SpatialExtent; size_bytes: int=0; point_count: int|None=None; source_type: str="las"

@dataclass(frozen=True)
class WorkUnitSizingPolicy:
    target_width: float; target_height: float; buffer_distance: float; maximum_estimated_points: int; maximum_expected_memory: int; maximum_concurrent_units: int; rationale: str; confidence: str

@dataclass(frozen=True)
class ProductPartitionPolicy:
    product: str; partitionable: bool; required_buffer: float; core_output_rule: str; merge_rule: str; scientific_caveats: tuple[str,...]; resume_support: bool; equivalence_status: str; default_enabled: bool

PRODUCT_POLICIES={
 "chm":ProductPartitionPolicy("chm",True,50.0,"discard buffered pixels; retain globally aligned core","deterministic first-valid core cells","Tiled/reference equivalence requires live measurement.",True,"provisional",True),
 **{p:ProductPartitionPolicy(p,False,0.0,"monolithic","not reviewed",("Partition merge behavior is not validated.",),False,"not reviewed",False) for p in ("pad","pai","fhd","rumple","canopy_cover","dtm","point_density","voxel_stat")}
}

@dataclass(frozen=True)
class WorkUnit:
    work_unit_id: str; unit_type: WorkUnitType; source_paths: tuple[Path,...]; core_extent: SpatialExtent; read_extent: SpatialExtent; row_start: int; row_end: int; column_start: int; column_end: int; execution_order: int; estimated_memory: int; status: str="Pending"

@dataclass(frozen=True)
class SourceAwareWorkPlan:
    repository_kind: str; product: str; grid: AlignedRasterGrid; work_units: tuple[WorkUnit,...]; concurrency_limit: int; workload_category: str; memory_category: str; merge_strategy: str; retry_policy: str; checkpoint_policy: str; scientific_assumptions: tuple[str,...]; source_location: str; physical_retiling: bool=False
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

def sizing_policy(*,repository_kind,product,resolution,available_memory_bytes,cpu_count,network=False,point_density=None,profile='recommended'):
    width=1000.0
    if network or profile=='conservative': width=750.0
    if point_density and point_density>30: width=min(width,500.0)
    if profile=='performance' and not network and available_memory_bytes>=16*1024**3: width=1500.0
    per_unit=min(int(available_memory_bytes*.25),2*1024**3)
    requested={'conservative':1,'recommended':2,'performance':4,'custom':max(1,cpu_count)}.get(profile,2)
    concurrency=max(1,min(requested,cpu_count,max(1,int(available_memory_bytes/max(per_unit,1)))))
    if network: concurrency=min(concurrency,2)
    if repository_kind=='ept' and product=='chm' and os.environ.get('PYFORESTSCAN_DEV_EPT_PARALLEL')!='1':concurrency=1
    buffer=50.0 if product=='chm' else 0.0
    return WorkUnitSizingPolicy(width,width,buffer,25_000_000,per_unit,concurrency,'Adaptive size reflects storage, memory, product, and profile.','medium' if point_density is None else 'high')

class SourceAwareWorkPlanner:
    def plan(self,*,repository_kind,sources,polygon_envelope,processing_crs,product,resolution,available_memory_bytes=8*1024**3,cpu_count=2,profile='recommended'):
        policy=PRODUCT_POLICIES.get(product)
        if policy is None or not policy.partitionable: raise ValueError(f"{product} does not have a validated partition policy.")
        grid=AlignedRasterGrid.from_extent(polygon_envelope,resolution,processing_crs)
        paths=tuple(sources); location=source_location(paths[0].path) if paths else 'local'; network=location in {'network','remote_url'}
        sizing=sizing_policy(repository_kind=repository_kind,product=product,resolution=resolution,available_memory_bytes=available_memory_bytes,cpu_count=cpu_count,network=network,profile=profile)
        if repository_kind=='ept': units=self._windows(grid,paths,WorkUnitType.EPT_WINDOW,sizing)
        elif repository_kind=='copc': units=self._copc(grid,paths,sizing)
        else: units=self._native(grid,paths,sizing)
        cells=grid.rows*grid.columns; workload='Small' if cells<5_000_000 else 'Moderate' if cells<25_000_000 else 'Large' if cells<100_000_000 else 'Very Large'
        memory='Low' if cells*4<256*1024**2 else 'Moderate' if cells*4<1024**3 else 'High'
        assumptions=[f"Global {resolution:g}-unit grid.",f"{sizing.buffer_distance:g}-unit CHM read buffer.","Exact polygon mask is applied after mosaic."]
        if repository_kind=='ept' and product=='chm' and sizing.maximum_concurrent_units==1:assumptions.extend(("Safe processing mode is active for this EPT job.","Parallel EPT HAG workers are temporarily limited while native-worker stability is being validated."))
        return SourceAwareWorkPlan(repository_kind,product,grid,tuple(units),sizing.maximum_concurrent_units,workload,memory,policy.merge_rule,'transient failures: 2; deterministic input/HAG failures: 0','verify and persist every completed core tile',tuple(assumptions),location)
    def _windows(self,grid,sources,kind,sizing):
        cols=max(1,round(sizing.target_width/grid.resolution));rows=max(1,round(sizing.target_height/grid.resolution));out=[];n=0
        for r0 in range(0,grid.rows,rows):
            for c0 in range(0,grid.columns,cols):
                core=grid.cell_extent(r0,min(grid.rows,r0+rows),c0,min(grid.columns,c0+cols));n+=1
                out.append(WorkUnit(f"wu-{n:04d}",kind,tuple(x.path for x in sources),core,core.buffered(sizing.buffer_distance),r0,min(grid.rows,r0+rows),c0,min(grid.columns,c0+cols),n,int(core.width*core.height/grid.resolution**2*16)))
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
            if src.size_bytes>2*1024**3:
                flush();subgrid=AlignedRasterGrid.from_extent(src.bounds,grid.resolution,grid.crs);out.extend(self._windows(subgrid,(src,),WorkUnitType.SUBDIVIDED_LARGE_SOURCE,sizing));continue
            if group:
                union=SpatialExtent(min(x.bounds.xmin for x in group),min(x.bounds.ymin for x in group),max(x.bounds.xmax for x in group),max(x.bounds.ymax for x in group))
                adjacent=union.buffered(max(sizing.buffer_distance, sizing.target_width * 0.1)).intersects(src.bounds)
                if size+src.size_bytes>1024**3 or not adjacent: flush()
            group.append(src);size+=src.size_bytes
        flush();return out
