"""Scientific suitability checks and explicit HAG strategy selection."""
from __future__ import annotations
import math
from dataclasses import dataclass

@dataclass(frozen=True)
class HagSuitabilityReport:
 status: str; total_points: int; finite_points: int; unique_xy: int; x_range: float; y_range: float; xy_rank: int; ground_points: int; ground_density: float|None; existing_hag: bool; dtm_available: bool; reasons: tuple[str,...]

@dataclass(frozen=True)
class HagStrategy:
 method: str; reason: str; assumptions: tuple[str,...]=(); ground_classes: tuple[int,...]=(2,); dtm_path: str=''; warnings: tuple[str,...]=(); method_version: str='1'

def assess_hag_suitability(x,y,classifications=(),dimensions=(),area=None,dtm_available=False):
 total=min(len(x),len(y));finite=[(float(a),float(b)) for a,b in zip(x,y) if math.isfinite(float(a)) and math.isfinite(float(b))];unique=set(finite);reasons=[]
 xr=(max((a for a,_ in finite),default=0)-min((a for a,_ in finite),default=0));yr=(max((b for _,b in finite),default=0)-min((b for _,b in finite),default=0))
 rank=0 if not finite else (1 if xr==0 or yr==0 else _rank(unique))
 ground=sum(1 for c in classifications if c==2);density=(ground/area if area and area>0 else None);existing=any(str(d).lower() in {'heightaboveground','normalizedz','height'} for d in dimensions)
 if total<3:reasons.append('too few points')
 if len(unique)<3:reasons.append('too few unique XY coordinates')
 if rank<2:reasons.append('XY coordinates rank-deficient')
 if not existing and not dtm_available and ground<3:reasons.append('no usable ground points')
 status='Suitable' if not reasons else ('Alternative recommended' if existing or dtm_available else 'Unsuitable')
 return HagSuitabilityReport(status,total,len(finite),len(unique),xr,yr,rank,ground,density,existing,dtm_available,tuple(reasons))

def _rank(points):
 pts=list(points);mx=sum(x for x,_ in pts)/len(pts);my=sum(y for _,y in pts)/len(pts);xx=sum((x-mx)**2 for x,y in pts);yy=sum((y-my)**2 for x,y in pts);xy=sum((x-mx)*(y-my) for x,y in pts);scale=max(xx*yy,1.0);return 1 if abs(xx*yy-xy*xy)<=scale*1e-12 else 2

class HagStrategyPlanner:
 def select(self,report,provided_dtm=''):
  if report.existing_hag:return HagStrategy('existing_normalized_height','Existing normalized-height dimension is available.',ground_classes=())
  if provided_dtm and report.dtm_available:return HagStrategy('provided_dtm','A compatible supplied DTM is available.',ground_classes=(),dtm_path=provided_dtm)
  if report.xy_rank==2 and report.ground_points>=3:return HagStrategy('classified_ground_delaunay','Ground XY geometry passed bounded Delaunay suitability checks.',assumptions=('Ground class 2 represents terrain.',))
  return HagStrategy('unavailable','Ground normalization could not construct a surface for part of the selected area.',warnings=report.reasons)

def classify_hag_exception(exc,work_unit_id,report=None):
 text=str(exc)
 if 'all points collinear' in text.lower():
  return {'code':'HAG_COLLINEAR','work_unit_id':work_unit_id,'original_exception':text,'user_message':'Ground normalization could not construct a surface for part of the selected area.','retry_identical':False,'statistics':None if report is None else report.__dict__}
 return {'code':'HAG_FAILED','work_unit_id':work_unit_id,'original_exception':text,'user_message':'Height normalization failed for part of the selected area.','retry_identical':False}
