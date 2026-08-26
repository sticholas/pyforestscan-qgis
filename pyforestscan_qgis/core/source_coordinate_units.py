"""Evidence-based coordinate-unit assessment for preparation algorithms."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import re

from .spatial_assignment import LinearUnit


class SourceCoordinateUnits(str, Enum):
    METERS = "METERS"
    INTERNATIONAL_FEET = "INTERNATIONAL_FEET"
    US_SURVEY_FEET = "US_SURVEY_FEET"
    FEET = "INTERNATIONAL_FEET"  # Compatibility alias.
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class SourceCoordinateUnitAssessment:
    units: SourceCoordinateUnits
    evidence: str
    confidence: str
    distance_operations_safe: bool
    warnings: tuple[str, ...] = ()

    @property
    def linear_unit(self) -> LinearUnit | None:
        return LinearUnit.parse(self.units.value)

    @property
    def meters_per_source_unit(self) -> float | None:
        return self.linear_unit.meters_per_unit if self.linear_unit else None

    def from_meters(self, value: float) -> float:
        if not self.linear_unit:
            raise ValueError("Trusted linear units are required for distance conversion.")
        return self.linear_unit.source_units(value)


def assess_source_coordinate_units(crs: object = None, explicit_units: object = None) -> SourceCoordinateUnitAssessment:
    """Resolve linear units without guessing from coordinate magnitude or LAS scale."""
    explicit = LinearUnit.parse(explicit_units)
    if explicit is not None:
        return SourceCoordinateUnitAssessment(SourceCoordinateUnits(explicit.value), "trusted explicit/repository assignment", "HIGH", True)
    text = str(crs or "").strip()
    if text:
        try:
            from pyproj import CRS
            parsed = CRS.from_user_input(text)
            axis = parsed.axis_info[0] if parsed.axis_info else None
            unit = str(getattr(axis, "unit_name", "") or "").casefold()
            if "metre" in unit or "meter" in unit:
                return SourceCoordinateUnitAssessment(SourceCoordinateUnits.METERS, "resolved CRS axis units", "AUTHORITATIVE", True)
            if "us survey" in unit:
                return SourceCoordinateUnitAssessment(SourceCoordinateUnits.US_SURVEY_FEET, "resolved CRS axis units", "AUTHORITATIVE", True)
            if "foot" in unit or "feet" in unit:
                return SourceCoordinateUnitAssessment(SourceCoordinateUnits.INTERNATIONAL_FEET, "resolved CRS axis units", "AUTHORITATIVE", True)
        except Exception:
            pass
        # QGIS Python may not include pyproj. These EPSG definitions have
        # authoritative metre axes and are safe to recognize without guessing.
        match = re.fullmatch(r"EPSG:(\d+)", text.upper())
        code = int(match.group(1)) if match else 0
        if 32601 <= code <= 32660 or 32701 <= code <= 32760 or code == 6635:
            return SourceCoordinateUnitAssessment(SourceCoordinateUnits.METERS, "authoritative EPSG linear-unit registry", "AUTHORITATIVE", True)
    return SourceCoordinateUnitAssessment(
        SourceCoordinateUnits.UNKNOWN,
        "no authoritative unit evidence",
        "NONE",
        False,
        ("Coordinate magnitude and LAS scale/offset do not establish linear units.",),
    )
