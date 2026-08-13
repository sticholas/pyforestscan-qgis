"""Numeric raster-equivalence summaries without QGIS dependencies."""
from __future__ import annotations
from dataclasses import dataclass
from math import sqrt

@dataclass(frozen=True)
class RasterEquivalenceSummary:
    equivalent: bool
    compared_cells: int
    valid_cells: int
    nodata_mismatches: int
    maximum_absolute_difference: float
    rmse: float
    mean_difference: float
    tolerance: float

def compare_raster_values(reference, candidate, *, nodata=-9999.0, tolerance=0.0):
    """Compare aligned flattened raster values with an explicit tolerance."""
    left = tuple(reference); right = tuple(candidate)
    if len(left) != len(right):
        raise ValueError("Aligned raster comparisons require equal cell counts.")
    differences=[];nodata_mismatches=0
    for expected, actual in zip(left, right):
        expected_nodata=expected==nodata;actual_nodata=actual==nodata
        if expected_nodata or actual_nodata:
            nodata_mismatches += int(expected_nodata != actual_nodata)
            continue
        differences.append(float(actual)-float(expected))
    maximum=max((abs(value) for value in differences),default=0.0)
    rmse=sqrt(sum(value*value for value in differences)/len(differences)) if differences else 0.0
    mean=sum(differences)/len(differences) if differences else 0.0
    return RasterEquivalenceSummary(nodata_mismatches==0 and maximum<=tolerance,len(left),len(differences),nodata_mismatches,maximum,rmse,mean,float(tolerance))
