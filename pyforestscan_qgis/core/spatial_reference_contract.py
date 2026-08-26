"""Explicit spatial-reference state carried across PBM boundaries."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping

from .spatial_reference_resolver import normalize_crs


class SpatialReferenceMode(str, Enum):
    """Whether coordinates have a named reference system."""

    RESOLVED = "resolved"
    SOURCE_LOCAL = "source_local"


@dataclass(frozen=True)
class SpatialReferenceContract:
    """Serializable source/output coordinate policy for one job."""

    mode: SpatialReferenceMode
    crs: str | None = None
    resolution_source: str = "none"
    confidence: str = "none"
    transformation_required: bool = False
    coordinate_units: str = "unknown"

    @classmethod
    def from_crs(cls, crs: object, *, source: str = "request") -> "SpatialReferenceContract":
        normalized = normalize_crs(crs)
        if normalized:
            return cls(SpatialReferenceMode.RESOLVED, normalized, source, "authoritative")
        return cls(SpatialReferenceMode.SOURCE_LOCAL)

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any] | None) -> "SpatialReferenceContract":
        data = dict(payload or {})
        raw_crs = normalize_crs(data.get("crs")) or None
        raw_mode = str(data.get("mode") or ("resolved" if raw_crs else "source_local")).lower()
        mode = SpatialReferenceMode(raw_mode)
        if mode is SpatialReferenceMode.SOURCE_LOCAL:
            raw_crs = None
        if mode is SpatialReferenceMode.RESOLVED and not raw_crs:
            raise ValueError("Resolved spatial-reference contract requires a valid CRS.")
        return cls(
            mode,
            raw_crs,
            str(data.get("resolution_source") or "none"),
            str(data.get("confidence") or "none"),
            bool(data.get("transformation_required", False)),
            str(data.get("coordinate_units") or "unknown"),
        )

    @property
    def source_local(self) -> bool:
        return self.mode is SpatialReferenceMode.SOURCE_LOCAL

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode.value,
            "crs": self.crs,
            "resolution_source": self.resolution_source,
            "confidence": self.confidence,
            "transformation_required": self.transformation_required,
            "coordinate_units": self.coordinate_units,
        }

