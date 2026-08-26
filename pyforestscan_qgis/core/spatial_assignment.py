"""Typed, persistent spatial meaning assigned without changing coordinates."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Iterable


class LinearUnit(str, Enum):
    METERS = "METERS"
    INTERNATIONAL_FEET = "INTERNATIONAL_FEET"
    US_SURVEY_FEET = "US_SURVEY_FEET"

    @property
    def meters_per_unit(self) -> float:
        return {
            LinearUnit.METERS: 1.0,
            LinearUnit.INTERNATIONAL_FEET: 0.3048,
            LinearUnit.US_SURVEY_FEET: 1200.0 / 3937.0,
        }[self]

    def source_units(self, meters: float) -> float:
        """Convert a canonical distance in metres to source-coordinate units."""
        return float(meters) / self.meters_per_unit

    @classmethod
    def parse(cls, value: object) -> "LinearUnit | None":
        text = str(getattr(value, "value", value) or "").strip().upper().replace(" ", "_")
        aliases = {
            "M": cls.METERS, "METER": cls.METERS, "METERS": cls.METERS,
            "METRE": cls.METERS, "METRES": cls.METERS,
            "FT": cls.INTERNATIONAL_FEET, "FOOT": cls.INTERNATIONAL_FEET,
            "FEET": cls.INTERNATIONAL_FEET, "INTERNATIONAL_FEET": cls.INTERNATIONAL_FEET,
            "US_SURVEY_FOOT": cls.US_SURVEY_FEET, "US_SURVEY_FEET": cls.US_SURVEY_FEET,
        }
        return aliases.get(text)


class AssignmentScope(str, Enum):
    FILE = "FILE"
    REPOSITORY = "REPOSITORY"


class SpatialAssignmentType(str, Enum):
    EMBEDDED = "EMBEDDED"
    SIDECAR = "SIDECAR"
    REPOSITORY_CONSENSUS = "REPOSITORY_CONSENSUS"
    QGIS_LAYER = "QGIS_LAYER"
    USER_FILE_ASSIGNMENT = "USER_FILE_ASSIGNMENT"
    USER_REPOSITORY_ASSIGNMENT = "USER_REPOSITORY_ASSIGNMENT"
    USER_UNITS_ONLY = "USER_UNITS_ONLY"
    SOURCE_LOCAL = "SOURCE_LOCAL"


@dataclass(frozen=True)
class SpatialAssignment:
    scope: AssignmentScope
    identity: str
    assignment_type: SpatialAssignmentType
    horizontal_crs: str = ""
    vertical_crs: str = ""
    linear_units: LinearUnit | None = None
    provenance: str = "user"
    confidence: str = "HIGH"
    user_confirmed: bool = False
    created_at: str = ""
    source_fingerprint: str = ""
    repository_fingerprint: str = ""
    inventory_signature: str = ""
    notes: str = ""

    @property
    def crs_assigned(self) -> bool:
        return bool(self.horizontal_crs)

    @property
    def trusted_linear_units(self) -> bool:
        return self.linear_units is not None and (self.user_confirmed or self.confidence in {"HIGH", "AUTHORITATIVE"})

    def to_dict(self) -> dict[str, object]:
        value = asdict(self)
        value["scope"] = self.scope.value
        value["assignment_type"] = self.assignment_type.value
        value["linear_units"] = self.linear_units.value if self.linear_units else ""
        return value

    @classmethod
    def from_dict(cls, value: dict[str, object]) -> "SpatialAssignment":
        return cls(
            scope=AssignmentScope(str(value.get("scope", "FILE"))),
            identity=str(value.get("identity", "")),
            assignment_type=SpatialAssignmentType(str(value.get("assignment_type", "USER_FILE_ASSIGNMENT"))),
            horizontal_crs=str(value.get("horizontal_crs", value.get("crs", "")) or ""),
            vertical_crs=str(value.get("vertical_crs", "") or ""),
            linear_units=LinearUnit.parse(value.get("linear_units")),
            provenance=str(value.get("provenance", value.get("source", "user"))),
            confidence=str(value.get("confidence", "HIGH")),
            user_confirmed=bool(value.get("user_confirmed", True)),
            created_at=str(value.get("created_at", value.get("assigned_at", ""))),
            source_fingerprint=str(value.get("source_fingerprint", value.get("signature", ""))),
            repository_fingerprint=str(value.get("repository_fingerprint", value.get("fingerprint", ""))),
            inventory_signature=str(value.get("inventory_signature", "")),
            notes=str(value.get("notes", "")),
        )


@dataclass(frozen=True)
class LidarSpatialProfile:
    source: Path
    repository: Path
    embedded_crs: str = ""
    assigned_crs: str = ""
    linear_units: LinearUnit | None = None
    assignment_scope: str = ""
    evidence: str = "source-local"
    preparation_safe: bool = False
    polygon_alignment_safe: bool = False
    conflict: str = ""

    @property
    def effective_crs(self) -> str:
        return self.embedded_crs or self.assigned_crs


def assignment_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def source_inventory_signature(paths: Iterable[Path]) -> str:
    parts: list[str] = []
    for path in sorted((Path(item) for item in paths), key=lambda item: str(item).casefold()):
        try:
            stat = path.stat()
            parts.append(f"{path.name}|{stat.st_size}|{stat.st_mtime_ns}")
        except OSError:
            parts.append(path.name)
    return hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()


def assignment_summary(assignment: SpatialAssignment | None) -> str:
    if assignment is None:
        return "No trusted spatial assignment"
    units = assignment.linear_units.value.replace("_", " ").title() if assignment.linear_units else "units derived from CRS"
    crs = assignment.horizontal_crs or "source-local coordinates"
    return f"{crs}; {units}; {assignment.scope.value.lower()} assignment"


__all__ = [
    "AssignmentScope", "LidarSpatialProfile", "LinearUnit", "SpatialAssignment",
    "SpatialAssignmentType", "assignment_summary", "assignment_timestamp", "source_inventory_signature",
]
