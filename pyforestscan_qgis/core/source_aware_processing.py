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
    target_width: float; target_height: float; buffer_distance: float; maximum_estimated_points: int; maximum_expected_memory: int; maximum_concurrent_units: int; rationale: str; confidence: str; strategy:str="adaptive";estimated_point_range:tuple[int,int]=(0,0);expected_memory_range:tuple[int,int]=(0,0);pilot_required:bool=False;product:str="chm"

@dataclass(frozen=True)
class ProductPartitionPolicy:
    product: str; partitionable: bool; required_buffer: float; core_output_rule: str; merge_rule: str; scientific_caveats: tuple[str,...]; resume_support: bool; equivalence_status: str; default_enabled: bool

PRODUCT_POLICIES={
 "chm":ProductPartitionPolicy("chm",True,50.0,"discard buffered pixels; retain globally aligned core","deterministic first-valid core cells","Tiled/reference equivalence requires live measurement.",True,"provisional",True),
 "rumple":ProductPartitionPolicy("rumple",True,1.0,"retain globally aligned patch core after one-cell CHM halo","deterministic non-overlapping patch ownership",("Every Rumple patch uses a 2x2 CHM neighborhood; core ownership excludes duplicate halo patches.",),True,"synthetic-and-coordinator-equivalence",True),
 **{p:ProductPartitionPolicy(p,False,0.0,"monolithic","not reviewed",("Partition merge behavior is not validated.",),False,"not reviewed",False) for p in ("pad","pai","fhd","canopy_cover","dtm","point_density","voxel_stat")}
}

@dataclass(frozen=True)
class WorkUnit:
    work_unit_id: str; unit_type: WorkUnitType; source_paths: tuple[Path,...]; core_extent: SpatialExtent; read_extent: SpatialExtent; row_start: int; row_end: int; column_start: int; column_end: int; execution_order: int; estimated_memory: int; status: str="Pending"; polygon_intersection_area:float=0.0;polygon_coverage_percent:float=0.0;required_for_output:bool=True;planning_reason:str="core intersects polygon";buffered_polygon_intersects:bool=False;source_coverage_expectation:str="unknown";component_ids:tuple[str,...]=();transport_cluster_id:str="";read_block_id:str="";science_block_id:str="";checkpoint_tile_id:str="";morton_code:int=0

@dataclass(frozen=True)
class SourceAwareWorkPlan:
    repository_kind: str; product: str; grid: AlignedRasterGrid; work_units: tuple[WorkUnit,...]; concurrency_limit: int; workload_category: str; memory_category: str; merge_strategy: str; retry_policy: str; checkpoint_policy: str; scientific_assumptions: tuple[str,...]; source_location: str; physical_retiling: bool=False;candidate_work_units:tuple[WorkUnit,...]=();skipped_work_units:tuple[WorkUnit,...]=();exact_polygon_signature:str="";buffer_policy:str="";hag_method_signature:str="";adaptive_strategy:str="adaptive";target_work_unit_width:float=0.0;target_work_unit_height:float=0.0;estimated_point_range:tuple[int,int]=(0,0);expected_memory_range:tuple[int,int]=(0,0);pilot_required:bool=False;native_partitions_reused:int=0;logical_subdivisions_added:int=0;component_count:int=0;cluster_count:int=0;read_block_count:int=0;science_block_count:int=0;checkpoint_tile_count:int=0;pruned_by_geometry:int=0;pruned_by_hierarchy:int=0;outside_polygon_count_estimate:int=0
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
    return WorkUnitSizingPolicy(adaptive.target_width,adaptive.target_height,adaptive.buffer_distance,adaptive.estimated_points_per_unit[1],adaptive.expected_memory_per_unit[1],concurrency,rationale,adaptive.confidence,adaptive.strategy,adaptive.estimated_points_per_unit,adaptive.expected_memory_per_unit,adaptive.pilot_required,product)


class PlanningCancelled(RuntimeError):
    """Raised at pure-Python safe points when a prerun cancellation is requested."""


class SourceAwareWorkPlanner:
    def plan(self,*,repository_kind,sources,polygon_envelope,processing_crs,product,resolution,available_memory_bytes=8*1024**3,cpu_count=2,profile='recommended',polygon_wkt=None,normalized_polygon=None,cancel_callback=None,progress_callback=None):
        policy=PRODUCT_POLICIES.get(product)
        if policy is None or not policy.partitionable: raise ValueError(f"{product} does not have a validated partition policy.")
        grid=AlignedRasterGrid.from_extent(polygon_envelope,resolution,processing_crs)
        paths=tuple(sources); location=source_location(paths[0].path) if paths else 'local'; network=location in {'network','remote_url'}
        polygon = normalized_polygon
        if polygon is None and polygon_wkt:
            from .work_unit_geometry import normalize_polygon_geometry
            polygon=normalize_polygon_geometry(polygon_wkt,processing_crs=processing_crs)
        exact_area=None
        if polygon is not None:
            from .work_unit_geometry import measure_core_polygon_intersection
            exact_area=measure_core_polygon_intersection(grid.total_extent,polygon).intersection_area
        point_density=next((source.point_count/source.bounds.width/source.bounds.height for source in paths if source.point_count and source.bounds.width and source.bounds.height),None)
        sizing=sizing_policy(repository_kind=repository_kind,product=product,resolution=resolution,available_memory_bytes=available_memory_bytes,cpu_count=cpu_count,network=network,profile=profile,extent=grid.total_extent,polygon_area=exact_area,native_partition_count=len(paths),point_density=point_density)
        sparse_polygon=polygon is not None and repository_kind in {'ept','copc'}
        planning={}
        if repository_kind=='ept' and sparse_polygon: units,planning=self._component_windows(grid,paths,WorkUnitType.EPT_WINDOW,sizing,polygon,cancel_callback,progress_callback)
        elif repository_kind=='ept': units=self._windows(grid,paths,WorkUnitType.EPT_WINDOW,sizing)
        elif repository_kind=='copc' and sparse_polygon: units,planning=self._component_windows(grid,paths,WorkUnitType.COPC_WINDOW,sizing,polygon,cancel_callback,progress_callback)
        elif repository_kind=='copc': units=self._copc(grid,paths,sizing)
        else: units=self._native(grid,paths,sizing)
        candidates=tuple(units);skipped=()
        if polygon is not None and not sparse_polygon:
            from dataclasses import replace
            from .work_unit_geometry import measure_core_polygon_intersection
            measured=[]
            total=max(1,len(candidates))
            for index,unit in enumerate(candidates,1):
                if cancel_callback is not None and cancel_callback(): raise PlanningCancelled("Polygon Prerun cancelled.")
                intersection=measure_core_polygon_intersection(unit.core_extent,polygon);buffered=measure_core_polygon_intersection(unit.read_extent,polygon)
                measured.append(replace(unit,polygon_intersection_area=intersection.intersection_area,polygon_coverage_percent=intersection.coverage_percent,required_for_output=intersection.intersects,status="Pending" if intersection.intersects else "SkippedOutsidePolygon",planning_reason="positive core/polygon area" if intersection.intersects else "zero exact core/polygon area",buffered_polygon_intersects=buffered.intersects,source_coverage_expectation="expected"))
                if progress_callback is not None and (index == total or index % 10 == 0): progress_callback("Checking polygon coverage",index,total)
            candidates=tuple(measured);units=[unit for unit in candidates if unit.required_for_output];skipped=tuple(unit for unit in candidates if not unit.required_for_output)
        cells=max(1,math.ceil((exact_area if exact_area is not None else grid.rows*grid.columns*resolution**2)/resolution**2));workload='Small' if cells<5_000_000 else 'Moderate' if cells<25_000_000 else 'Large' if cells<100_000_000 else 'Very Large'
        peak=max((unit.estimated_memory for unit in units),default=cells*4)
        memory='Low' if peak<256*1024**2 else 'Moderate' if peak<1024**3 else 'High' if peak<3*1024**3 else 'Very High'
        assumptions=[f"Global {resolution:g}-unit grid.",f"{sizing.buffer_distance:g}-unit CHM read buffer.",f"Adaptive strategy: {sizing.strategy}.",sizing.rationale,"Exact polygon mask is applied after mosaic."]
        if repository_kind=='ept' and product=='chm' and sizing.maximum_concurrent_units==1:assumptions.extend(("Safe processing mode is active for this EPT job.","Parallel EPT HAG workers are temporarily limited while native-worker stability is being validated."))
        polygon_signature=getattr(polygon,"polygon_signature","")
        hag_signature=hashlib.sha256(b"existing_normalized_height:HeightAboveGround").hexdigest()
        native_reused=len(paths) if repository_kind in {'folder','las','laz'} else 0
        subdivisions=max(0,len(units)-native_reused)
        effective_concurrency=min(sizing.maximum_concurrent_units,max(1,len(units)))
        component_count=len(getattr(polygon,'parts',()))
        total_point_range=sizing.estimated_point_range
        if sparse_polygon and exact_area:
            density=point_density if point_density is not None else 20.0;central=max(1,int(exact_area*density));total_point_range=(int(central*.6),int(central*1.4))
        return SourceAwareWorkPlan(repository_kind,product,grid,tuple(units),effective_concurrency,workload,memory,policy.merge_rule,'transient failures: 2; deterministic input/HAG failures: 0','verify and persist every completed core tile',tuple(assumptions),location,False,candidates,skipped,polygon_signature,f"buffer={sizing.buffer_distance:g}",hag_signature,sizing.strategy,sizing.target_width,sizing.target_height,total_point_range,sizing.expected_memory_range,sizing.pilot_required,native_reused,subdivisions,component_count,planning.get('cluster_count',component_count),planning.get('read_block_count',len(units)),len(units),len(units),planning.get('pruned_by_geometry',0),planning.get('pruned_by_hierarchy',0),planning.get('outside_polygon_count_estimate',0))

    def _component_windows(self,grid,sources,kind,sizing,polygon,cancel_callback=None,progress_callback=None):
        """Create only exact-polygon regions while retaining the global output grid."""
        from .work_unit_geometry import measure_core_polygon_intersection
        source_id=hashlib.sha256("\n".join(sorted(str(item.path) for item in sources)).encode()).hexdigest()[:10]
        paths=tuple(item.path for item in sources);provisional=[];local_candidates=0;hierarchy_pruned=0
        cluster_map=self._component_cluster_map(polygon,sizing.buffer_distance)
        occupancy=None
        if kind is WorkUnitType.EPT_WINDOW and paths:
            from .ept_occupancy import load_ept_occupancy
            occupancy=load_ept_occupancy(paths[0])
        for component_index in range(len(polygon.parts)):
            if cancel_callback is not None and cancel_callback():raise PlanningCancelled("Polygon Prerun cancelled.")
            component=polygon.component(component_index);bounds=SpatialExtent(*component.bounds);area=polygon.component_areas[component_index]
            local=sizing_policy(repository_kind='ept' if kind is WorkUnitType.EPT_WINDOW else 'copc',product=sizing.product,resolution=grid.resolution,available_memory_bytes=max(sizing.maximum_expected_memory*4,1024**3),cpu_count=sizing.maximum_concurrent_units,network=True,extent=bounds,polygon_area=area)
            c0=max(0,int(math.floor((bounds.xmin-grid.origin_x)/grid.resolution)));c1=min(grid.columns,int(math.ceil((bounds.xmax-grid.origin_x)/grid.resolution)))
            r0=max(0,int(math.floor((bounds.ymin-grid.origin_y)/grid.resolution)));r1=min(grid.rows,int(math.ceil((bounds.ymax-grid.origin_y)/grid.resolution)))
            step_c=max(1,round(local.target_width/grid.resolution));step_r=max(1,round(local.target_height/grid.resolution))
            component_id=f"pc-{component.polygon_signature[:12]}"
            cluster_id=cluster_map[component_index]
            for row in range(r0,r1,step_r):
                for col in range(c0,c1,step_c):
                    if cancel_callback is not None and cancel_callback():raise PlanningCancelled("Polygon Prerun cancelled.")
                    local_candidates+=1;core=grid.cell_extent(row,min(r1,row+step_r),col,min(c1,col+step_c));intersection=measure_core_polygon_intersection(core,component)
                    if not intersection.intersects:continue
                    if occupancy is not None and not occupancy.intersects(core):
                        hierarchy_pruned+=1;continue
                    read=core.buffered(sizing.buffer_distance)
                    from .resource_estimation import estimate_work_unit_resources
                    estimate=estimate_work_unit_resources(int(read.width*read.height*20.0),hag_method='existing_normalized_height',raster_cells=int(read.width*read.height/grid.resolution**2),core_width=local.target_width,product=sizing.product)
                    center=((core.xmin+core.xmax)/2,(core.ymin+core.ymax)/2)
                    provisional.append((cluster_id,self._morton(center,grid.total_extent),component_id,core,read,row,min(r1,row+step_r),col,min(c1,col+step_c),intersection,estimate.estimated_memory))
            if progress_callback is not None:progress_callback("Planning selected areas",component_index+1,len(polygon.parts))
        ordered=[]
        for order,item in enumerate(sorted(provisional,key=lambda value:(value[1],value[0],value[2])),1):
            cluster_id,morton,component_id,core,read,r0,r1,c0,c1,intersection,memory=item
            block=hashlib.sha256(f"{polygon.polygon_signature}:{component_id}:{r0}:{r1}:{c0}:{c1}".encode()).hexdigest()[:12]
            ordered.append(WorkUnit(f"wu-{source_id}-{block}",kind,paths,core,read,r0,r1,c0,c1,order,memory,polygon_intersection_area=intersection.intersection_area,polygon_coverage_percent=intersection.coverage_percent,planning_reason='component-first exact polygon region',buffered_polygon_intersects=True,source_coverage_expectation='expected',component_ids=(component_id,),transport_cluster_id=cluster_id,read_block_id=f"rb-{block}",science_block_id=f"sb-{block}",checkpoint_tile_id=f"ct-{block}",morton_code=morton))
        dense_columns=math.ceil(grid.columns/max(1,round(sizing.target_width/grid.resolution)))
        dense_rows=math.ceil(grid.rows/max(1,round(sizing.target_height/grid.resolution)))
        global_dense=max(1,dense_columns*dense_rows)
        geometry_pruned=max(0,local_candidates-len(ordered)-hierarchy_pruned)
        return ordered,{'cluster_count':len(set(cluster_map.values())),'read_block_count':len(ordered),'pruned_by_geometry':geometry_pruned,'pruned_by_hierarchy':hierarchy_pruned,'outside_polygon_count_estimate':max(0,global_dense-len(ordered))}

    @staticmethod
    def _component_cluster_map(polygon,buffer_distance):
        clusters=[];mapping={}
        for index,bounds in enumerate(polygon.part_bounds):
            extent=SpatialExtent(*bounds);selected=None
            for cluster_index,cluster_extent in enumerate(clusters):
                if cluster_extent.buffered(buffer_distance*2).intersects(extent):selected=cluster_index;break
            if selected is None:clusters.append(extent);selected=len(clusters)-1
            else:
                current=clusters[selected];clusters[selected]=SpatialExtent(min(current.xmin,extent.xmin),min(current.ymin,extent.ymin),max(current.xmax,extent.xmax),max(current.ymax,extent.ymax))
            mapping[index]=f"tc-{selected+1:04d}"
        return mapping

    @staticmethod
    def _morton(point,extent):
        width=max(extent.width,1.0);height=max(extent.height,1.0)
        x=max(0,min(65535,int((point[0]-extent.xmin)/width*65535)));y=max(0,min(65535,int((point[1]-extent.ymin)/height*65535)));value=0
        for bit in range(16):value|=((x>>bit)&1)<<(2*bit);value|=((y>>bit)&1)<<(2*bit+1)
        return value
    def _windows(self,grid,sources,kind,sizing):
        cols=max(1,round(sizing.target_width/grid.resolution));rows=max(1,round(sizing.target_height/grid.resolution));out=[];n=0
        source_id=hashlib.sha256("\n".join(sorted(str(item.path) for item in sources)).encode()).hexdigest()[:10]
        for r0 in range(0,grid.rows,rows):
            for c0 in range(0,grid.columns,cols):
                core=grid.cell_extent(r0,min(grid.rows,r0+rows),c0,min(grid.columns,c0+cols));n+=1
                read=core.buffered(sizing.buffer_distance)
                density=20.0 if kind is WorkUnitType.EPT_WINDOW else 8.0
                from .resource_estimation import estimate_work_unit_resources
                estimate=estimate_work_unit_resources(int(read.width*read.height*density),hag_method="existing_normalized_height",raster_cells=int(read.width*read.height/grid.resolution**2),core_width=sizing.target_width,product=sizing.product)
                out.append(WorkUnit(f"wu-{source_id}-{n:04d}",kind,tuple(x.path for x in sources),core,read,r0,min(grid.rows,r0+rows),c0,min(grid.columns,c0+cols),n,estimate.estimated_memory))
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
            source_estimate=estimate_work_unit_resources(estimated_points,raster_cells=int(overlap.width*overlap.height/grid.resolution**2),core_width=sizing.target_width,product=sizing.product)
            subdivision_limit=sizing.maximum_expected_memory+256*1024**2
            if src.size_bytes>2*1024**3 or source_estimate.estimated_memory>subdivision_limit:
                flush();subgrid=AlignedRasterGrid.from_extent(overlap,grid.resolution,grid.crs);out.extend(self._windows(subgrid,(src,),WorkUnitType.SUBDIVIDED_LARGE_SOURCE,sizing));continue
            if group:
                union=SpatialExtent(min(x.bounds.xmin for x in group),min(x.bounds.ymin for x in group),max(x.bounds.xmax for x in group),max(x.bounds.ymax for x in group))
                adjacent=union.buffered(max(sizing.buffer_distance, sizing.target_width * 0.1)).intersects(src.bounds)
                if size+src.size_bytes>1024**3 or not adjacent: flush()
            group.append(src);size+=src.size_bytes
        flush();return out
