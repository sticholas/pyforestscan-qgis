"""Evidence-based coordinate-unit assessment for preparation algorithms."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class SourceCoordinateUnits(str, Enum):
    METERS = "METERS"
    FEET = "FEET"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class SourceCoordinateUnitAssessment:
    units: SourceCoordinateUnits
    evidence: str
    confidence: str
    distance_operations_safe: bool
    warnings: tuple[str, ...] = ()


def assess_source_coordinate_units(crs: object = None, explicit_units: object = None) -> SourceCoordinateUnitAssessment:
    """Resolve linear units without guessing from coordinate magnitude or LAS scale."""
    explicit = str(explicit_units or "").strip().upper()
    if explicit in {"M", "METER", "METERS", "METRE", "METRES"}:
        return SourceCoordinateUnitAssessment(SourceCoordinateUnits.METERS, "trusted explicit/repository assignment", "HIGH", True)
    if explicit in {"FT", "FOOT", "FEET", "US_SURVEY_FOOT"}:
        return SourceCoordinateUnitAssessment(SourceCoordinateUnits.FEET, "trusted explicit/repository assignment", "HIGH", True)
    text = str(crs or "").strip()
    if text:
        try:
            from pyproj import CRS
            parsed = CRS.from_user_input(text)
            axis = parsed.axis_info[0] if parsed.axis_info else None
            unit = str(getattr(axis, "unit_name", "") or "").casefold()
            if "metre" in unit or "meter" in unit:
                return SourceCoordinateUnitAssessment(SourceCoordinateUnits.METERS, "resolved CRS axis units", "AUTHORITATIVE", True)
            if "foot" in unit or "feet" in unit:
                return SourceCoordinateUnitAssessment(SourceCoordinateUnits.FEET, "resolved CRS axis units", "AUTHORITATIVE", True)
        except Exception:
            pass
    return SourceCoordinateUnitAssessment(
        SourceCoordinateUnits.UNKNOWN,
        "no authoritative unit evidence",
        "NONE",
        False,
        ("Coordinate magnitude and LAS scale/offset do not establish linear units.",),
    )

