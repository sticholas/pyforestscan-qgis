"""Authoritative execution and output contracts for scientific products."""
from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class ProductExecutionCapability:
    key:str;label:str;required_dimensions:tuple[str,...];hag_requirement:str;partition_support:bool;fast_path_support:bool;mosaic_semantics:str;mask_semantics:str;output_kind:str;display_role:str;renderer:str;load_to_qgis:bool;validation_status:str;limitations:str="";depends_on:tuple[str,...]=();secondary_output:str="";units:str="";halo_cells:int=0

_RASTER=dict(required_dimensions=("X","Y","Z"),partition_support=True,fast_path_support=True,mosaic_semantics="aligned_core_tiles",mask_semantics="exact_polygon_nodata_mask",output_kind="raster",display_role="raster",renderer="grayscale",load_to_qgis=True,validation_status="regression_tested")
PRODUCT_CAPABILITIES={
 "chm":ProductExecutionCapability("chm","Canopy Height Model",hag_requirement="required",**_RASTER),
 "canopy_cover":ProductExecutionCapability("canopy_cover","Canopy Cover",hag_requirement="required",**_RASTER),
 "dtm":ProductExecutionCapability("dtm","DTM",hag_requirement="classified_ground",**_RASTER),
 "fhd":ProductExecutionCapability("fhd","FHD",hag_requirement="required",**_RASTER),
 "pai":ProductExecutionCapability("pai","PAI",hag_requirement="required",**_RASTER),
 "point_density":ProductExecutionCapability("point_density","Point Density",hag_requirement="not_required",**_RASTER),
 "voxel_stat":ProductExecutionCapability("voxel_stat","Voxel Statistic",hag_requirement="required",**_RASTER),
 "pad":ProductExecutionCapability("pad","PAD",("X","Y","Z"),"required",True,True,"aligned_multiband_core_tiles","exact_polygon_nodata_mask","raster","multiband_raster","pad_rgb_5_3_2",True,"regression_tested"),
 "rumple":ProductExecutionCapability("rumple","Rumple Index",("X","Y","Z"),"required",False,True,"aligned_patch_core_tiles","exact_polygon_nodata_mask","raster","raster","grayscale",True,"core_equivalence_tested","Patch-centered spatial extension; durable work-unit execution remains pending.",( "chm",),"scalar_summary","dimensionless",1),
 "rumple_summary":ProductExecutionCapability("rumple_summary","Area Rumple Summary",("X","Y","Z"),"required",True,True,"planar_area_weighted","area_summary","table","table","table",True,"scientific_equivalence_tested","Supporting scalar compatibility output.",( "chm",),"","dimensionless",1),
}

def product_capability(key):return PRODUCT_CAPABILITIES.get(str(key).strip().lower())
