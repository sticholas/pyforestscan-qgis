"""Evidence-based coordinate-unit assessment for preparation algorithms."""

from __future__ import annotations

from dataclasses import dataclass, replace
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
    unit_basis: str = "UNRESOLVED"
    authoritative: bool = False

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
        return SourceCoordinateUnitAssessment(SourceCoordinateUnits(explicit.value), "trusted explicit/repository assignment", "HIGH", True, unit_basis="USER_ASSIGNED", authoritative=True)
    text = str(crs or "").strip()
    if text:
        try:
            from pyproj import CRS
            parsed = CRS.from_user_input(text)
            axis = parsed.axis_info[0] if parsed.axis_info else None
            unit = str(getattr(axis, "unit_name", "") or "").casefold()
            if "metre" in unit or "meter" in unit:
                return SourceCoordinateUnitAssessment(SourceCoordinateUnits.METERS, "resolved CRS axis units", "AUTHORITATIVE", True, unit_basis="CRS_DERIVED", authoritative=True)
            if "us survey" in unit:
                return SourceCoordinateUnitAssessment(SourceCoordinateUnits.US_SURVEY_FEET, "resolved CRS axis units", "AUTHORITATIVE", True, unit_basis="CRS_DERIVED", authoritative=True)
            if "foot" in unit or "feet" in unit:
                return SourceCoordinateUnitAssessment(SourceCoordinateUnits.INTERNATIONAL_FEET, "resolved CRS axis units", "AUTHORITATIVE", True, unit_basis="CRS_DERIVED", authoritative=True)
        except Exception:
            pass
        # QGIS Python may not include pyproj. These EPSG definitions have
        # authoritative metre axes and are safe to recognize without guessing.
        match = re.fullmatch(r"EPSG:(\d+)", text.upper())
        code = int(match.group(1)) if match else 0
        if 32601 <= code <= 32660 or 32701 <= code <= 32760 or code == 6635:
            return SourceCoordinateUnitAssessment(SourceCoordinateUnits.METERS, "authoritative EPSG linear-unit registry", "AUTHORITATIVE", True, unit_basis="CRS_DERIVED", authoritative=True)
    return SourceCoordinateUnitAssessment(
        SourceCoordinateUnits.UNKNOWN,
        "no authoritative unit evidence",
        "NONE",
        False,
        ("Coordinate magnitude and LAS scale/offset do not establish linear units.",),
    )


def assess_processing_coordinate_units(crs: object = None, explicit_units: object = None, unit_basis: object = None) -> SourceCoordinateUnitAssessment:
    """Rehydrate the immutable prerun unit decision without changing its trust state."""
    assessment = assess_source_coordinate_units(crs, explicit_units)
    basis = str(getattr(unit_basis, "value", unit_basis) or assessment.unit_basis).upper()
    if basis == "ASSUMED_SOURCE_LOCAL" and assessment.linear_unit:
        return replace(assessment, evidence="configured source-local processing fallback", confidence="ASSUMED", distance_operations_safe=True, unit_basis=basis, authoritative=False, warnings=("Distance-sensitive parameters depend on assumed source units.",))
    return replace(assessment, unit_basis=basis, authoritative=basis not in {"ASSUMED_SOURCE_LOCAL", "UNRESOLVED"})
