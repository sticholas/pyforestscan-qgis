"""Scientific suitability checks and explicit HAG strategy selection."""
from __future__ import annotations
import hashlib
import json
import math
from collections import Counter
from dataclasses import asdict, dataclass
from enum import Enum

class HagReasonCode(str, Enum):
    EMPTY_POINT_ARRAY="EMPTY_POINT_ARRAY"; TOO_FEW_POINTS="TOO_FEW_POINTS"; TOO_FEW_UNIQUE_XY="TOO_FEW_UNIQUE_XY"; ALL_POINTS_COLLINEAR="ALL_POINTS_COLLINEAR"; TOO_FEW_GROUND_POINTS="TOO_FEW_GROUND_POINTS"; GROUND_POINTS_COLLINEAR="GROUND_POINTS_COLLINEAR"; INSUFFICIENT_GROUND_COVERAGE="INSUFFICIENT_GROUND_COVERAGE"; NONFINITE_COORDINATES="NONFINITE_COORDINATES"; VALID_EXISTING_HAG="VALID_EXISTING_HAG"; SUITABLE_FOR_DELAUNAY="SUITABLE_FOR_DELAUNAY"; UNKNOWN="UNKNOWN"

@dataclass(frozen=True)
class HagWindowSuitability:
    work_unit_id:str; suitable:bool; total_points:int; finite_points:int; unique_xy:int; xy_rank:int; ground_points:int; unique_ground_xy:int; ground_xy_rank:int; x_range:float; y_range:float; ground_x_range:float; ground_y_range:float; classifications:dict[int,int]; existing_hag_available:bool; recommended_method:str; reason_code:str; user_message:str; technical_message:str; ground_coverage:float|None=None; z_range:float=0.; empty_array:bool=False; nonfinite_points:int=0; dtm_available:bool=False
    @property
    def status(self): return "Suitable" if self.suitable else ("Alternative recommended" if self.existing_hag_available or self.dtm_available else "Unsuitable")
    @property
    def existing_hag(self): return self.existing_hag_available
    @property
    def ground_density(self): return self.ground_coverage
    @property
    def reasons(self):
        labels={HagReasonCode.EMPTY_POINT_ARRAY.value:"empty point array",HagReasonCode.TOO_FEW_POINTS.value:"too few points",HagReasonCode.TOO_FEW_UNIQUE_XY.value:"too few unique XY coordinates",HagReasonCode.ALL_POINTS_COLLINEAR.value:"XY coordinates rank-deficient",HagReasonCode.TOO_FEW_GROUND_POINTS.value:"no usable ground points",HagReasonCode.GROUND_POINTS_COLLINEAR.value:"ground XY coordinates rank-deficient",HagReasonCode.NONFINITE_COORDINATES.value:"nonfinite coordinates"}
        return () if self.suitable else (labels.get(self.reason_code,self.technical_message),)
    def to_dict(self): return asdict(self)

HagSuitabilityReport=HagWindowSuitability

@dataclass(frozen=True)
class HagStrategy:
    method:str; reason:str; assumptions:tuple[str,...]=(); ground_classes:tuple[int,...]=(2,); dtm_path:str=""; warnings:tuple[str,...]=(); method_version:str="2"

def hag_method_signature(method,source_dimension=""):
    basis={"method":method,"dimension":source_dimension if method=="existing_normalized_height" else "","implementation_version":"3"}
    return hashlib.sha256(json.dumps(basis,sort_keys=True).encode()).hexdigest()

@dataclass(frozen=True)
class HagExecutionDecision:
    """Authoritative immutable HAG planning and execution contract."""
    selected_method:str;source_dimension:str;suitability_status:str;suitability_evidence:dict;method_signature:str;fallback_allowed:bool=False;fallback_method:str="unsupported";scientific_reason:str="";validation_timestamp:str="";implementation_version:str="3"
    @classmethod
    def from_report(cls,report,source_dimension="HeightAboveGround"):
        from datetime import datetime,timezone
        method=report.recommended_method if report.suitable else "unsupported"
        dimension=source_dimension if method=="existing_normalized_height" else ""
        evidence=report.to_dict()
        signature=hag_method_signature(method,dimension)
        return cls(method,dimension,report.status,evidence,signature,False,"unsupported",report.technical_message,datetime.now(timezone.utc).isoformat())
    def assert_executed(self,method):
        if method!=self.selected_method:raise RuntimeError(f"HAG_METHOD_MISMATCH: planned {self.selected_method}, execution requested {method}.")

def assess_hag_suitability(x,y,classifications=(),dimensions=(),area=None,dtm_available=False,*,z=(),hag_values=(),work_unit_id=""):
    total=min(len(x),len(y)); finite=[]; nonfinite=0
    for a,b in zip(x,y):
        try: point=(float(a),float(b))
        except (TypeError,ValueError): nonfinite+=1; continue
        if all(math.isfinite(v) for v in point): finite.append(point)
        else: nonfinite+=1
    unique=set(finite); xr,yr=_ranges(finite); rank=_rank(unique); classes=Counter(); ground=[]
    for value in classifications:
        try: classes[int(value)]+=1
        except (TypeError,ValueError): pass
    for point,value in zip(finite,classifications):
        try: is_ground=int(value)==2
        except (TypeError,ValueError): is_ground=False
        if is_ground: ground.append(point)
    unique_ground=set(ground); gxr,gyr=_ranges(ground); grank=_rank(unique_ground); existing=any(str(d).lower()=="heightaboveground" for d in dimensions); coverage=len(ground)/area if area and area>0 else None
    finite_hag=[float(v) for v in hag_values if _finite(v)];existing_valid=bool(existing and finite_hag and any(abs(v)>1e-9 for v in finite_hag) and max(finite_hag)-min(finite_hag)>1e-9)
    if existing_valid: reason=HagReasonCode.VALID_EXISTING_HAG; suitable=True; method="existing_normalized_height"
    elif existing: reason=HagReasonCode.UNKNOWN; suitable=False; method="unavailable"
    elif total==0: reason=HagReasonCode.EMPTY_POINT_ARRAY; suitable=False; method="unavailable"
    elif total<3: reason=HagReasonCode.TOO_FEW_POINTS; suitable=False; method="unavailable"
    elif nonfinite and len(finite)<3: reason=HagReasonCode.NONFINITE_COORDINATES; suitable=False; method="unavailable"
    elif len(unique)<3: reason=HagReasonCode.TOO_FEW_UNIQUE_XY; suitable=False; method="unavailable"
    elif rank<2: reason=HagReasonCode.ALL_POINTS_COLLINEAR; suitable=False; method="unavailable"
    elif len(ground)<3 or len(unique_ground)<3: reason=HagReasonCode.TOO_FEW_GROUND_POINTS; suitable=False; method="provided_dtm" if dtm_available else "unavailable"
    elif grank<2 or gxr<=0 or gyr<=0: reason=HagReasonCode.GROUND_POINTS_COLLINEAR; suitable=False; method="provided_dtm" if dtm_available else "unavailable"
    else: reason=HagReasonCode.SUITABLE_FOR_DELAUNAY; suitable=True; method="classified_ground_delaunay"
    messages={HagReasonCode.EMPTY_POINT_ARRAY:"No LiDAR points were returned for this processing area.",HagReasonCode.ALL_POINTS_COLLINEAR:"Ground normalization cannot form a two-dimensional surface in this area.",HagReasonCode.TOO_FEW_GROUND_POINTS:"This area does not contain enough classified ground points for normalization.",HagReasonCode.GROUND_POINTS_COLLINEAR:"Classified ground points cannot form a two-dimensional terrain surface."}
    technical=f"reason={reason.value}; total={total}; finite={len(finite)}; unique_xy={len(unique)}; xy_rank={rank}; ground={len(ground)}; unique_ground_xy={len(unique_ground)}; ground_rank={grank}"
    zv=[float(v) for v in z if _finite(v)]; zr=max(zv)-min(zv) if zv else 0.
    return HagWindowSuitability(work_unit_id,suitable,total,len(finite),len(unique),rank,len(ground),len(unique_ground),grank,xr,yr,gxr,gyr,dict(sorted(classes.items())),existing,method,reason.value,messages.get(reason,"The bounded LiDAR area passed height-normalization suitability checks." if suitable else "This area is unsuitable for the selected height-normalization method."),technical,coverage,zr,total==0,nonfinite,dtm_available)

def _rank(points):
    pts=list(points)
    if not pts:return 0
    if len(pts)<3:return 1
    mx=sum(x for x,_ in pts)/len(pts); my=sum(y for _,y in pts)/len(pts); xx=sum((x-mx)**2 for x,y in pts); yy=sum((y-my)**2 for x,y in pts); xy=sum((x-mx)*(y-my) for x,y in pts); scale=max(xx*yy,1.)
    return 1 if abs(xx*yy-xy*xy)<=scale*1e-12 else 2

def _ranges(points):
    pts=list(points)
    return (0.,0.) if not pts else (max(x for x,_ in pts)-min(x for x,_ in pts),max(y for _,y in pts)-min(y for _,y in pts))

def _finite(value):
    try:return math.isfinite(float(value))
    except (TypeError,ValueError):return False

class HagStrategyPlanner:
    def select(self,report,provided_dtm=""):
        if report.suitable and report.recommended_method=="existing_normalized_height":return HagStrategy("existing_normalized_height","Existing normalized-height dimension is validated.",ground_classes=())
        if provided_dtm and report.dtm_available:return HagStrategy("provided_dtm","A compatible supplied DTM is available.",ground_classes=(),dtm_path=provided_dtm)
        if report.suitable and report.ground_xy_rank==2 and report.ground_points>=3:return HagStrategy("classified_ground_delaunay","Ground XY geometry passed bounded Delaunay suitability checks.",assumptions=("Ground class 2 represents terrain.",))
        return HagStrategy("unavailable","Ground normalization could not construct a surface for part of the selected area.",warnings=report.reasons)

def classify_hag_exception(exc,work_unit_id="",report=None):
    text=str(exc); lower=text.lower()
    if "collinear" in lower:code="HAG_COLLINEAR_INPUT";message="Ground-normalization points cannot form a two-dimensional surface."
    elif "empty point" in lower or "no point data" in lower or "no points" in lower:code="EMPTY_SPATIAL_READ";message="No usable LiDAR points were returned for this processing area."
    elif "ground" in lower and ("too few" in lower or "insufficient" in lower):code="HAG_INSUFFICIENT_GROUND";message="There are not enough usable ground points for height normalization."
    else:code="HAG_FAILED";message="Height normalization failed for part of the selected area."
    return {"code":code,"work_unit_id":work_unit_id,"original_exception":text,"user_message":message,"retry_identical":False,"statistics":None if report is None else report.to_dict()}
