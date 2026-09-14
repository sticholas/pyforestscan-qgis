"""Typed empty spatial-read semantics for required polygon cores."""
from dataclasses import dataclass
from enum import Enum

class EmptySpatialReadStatus(str,Enum):
    SKIPPED_OUTSIDE_POLYGON="SkippedOutsidePolygon"
    COMPLETE_NODATA="CompleteNoData"
    FAILED_EMPTY_READ="FailedEmptyRead"
    NEEDS_COVERAGE_REVIEW="NeedsCoverageReview"

@dataclass(frozen=True)
class EmptySpatialReadDecision:
    status:str;reason_code:str;message:str;counts_as_failure:bool;output_required:bool

def classify_empty_spatial_read(*,core_intersection_area,source_coverage_expected=None,read_completed=True,previous_success=False,network_failure=False):
    if core_intersection_area<=0:return EmptySpatialReadDecision(EmptySpatialReadStatus.SKIPPED_OUTSIDE_POLYGON.value,"OUTSIDE_EXACT_POLYGON","Core has zero exact-polygon intersection.",False,False)
    if network_failure or previous_success:return EmptySpatialReadDecision(EmptySpatialReadStatus.FAILED_EMPTY_READ.value,"UNEXPECTED_EMPTY_READ","LiDAR data was expected in this required area, but the source returned no points.",True,True)
    if read_completed and source_coverage_expected is not False:return EmptySpatialReadDecision(EmptySpatialReadStatus.COMPLETE_NODATA.value,"VALID_SOURCE_NODATA","The required area contains no LiDAR returns and will remain NoData.",False,False)
    if source_coverage_expected is False:return EmptySpatialReadDecision(EmptySpatialReadStatus.COMPLETE_NODATA.value,"OUTSIDE_SOURCE_COVERAGE","The polygon extends outside authoritative LiDAR coverage; this area will remain NoData.",False,False)
    return EmptySpatialReadDecision(EmptySpatialReadStatus.NEEDS_COVERAGE_REVIEW.value,"COVERAGE_UNKNOWN","Source coverage could not be determined for an empty required area.",True,True)
