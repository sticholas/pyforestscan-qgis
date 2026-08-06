"""Validation-first raster mosaic contracts for aligned work-unit outputs."""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from .source_aware_processing import AlignedRasterGrid,WorkUnit

@dataclass(frozen=True)
class MosaicInput:
 work_unit: WorkUnit; path: Path; verified: bool; crs: str; resolution: float; nodata: float; final_output: bool=False
@dataclass(frozen=True)
class MosaicPlan:
 inputs: tuple[MosaicInput,...]; output_path: Path; grid: AlignedRasterGrid; merge_rule: str='first valid core cell'; transactional: bool=True
def validate_mosaic_plan(plan):
 errors=[];ids=set()
 for item in plan.inputs:
  if item.work_unit.work_unit_id in ids:errors.append(f'duplicate work unit {item.work_unit.work_unit_id}')
  ids.add(item.work_unit.work_unit_id)
  if not item.verified or not item.path.is_file():errors.append(f'unverified input {item.work_unit.work_unit_id}')
  if item.crs!=plan.grid.crs:errors.append(f'CRS mismatch {item.work_unit.work_unit_id}')
  if abs(item.resolution-plan.grid.resolution)>1e-9:errors.append(f'resolution mismatch {item.work_unit.work_unit_id}')
 if not plan.inputs:errors.append('no verified core rasters')
 return tuple(errors)
