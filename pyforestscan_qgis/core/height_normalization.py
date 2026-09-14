"""Serializable scientific decision for height normalization."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping

from .hag_strategy import hag_method_signature
from .point_dimensions import PointDimensionCapabilities


class HeightNormalizationMode(str, Enum):
    EXISTING_HAG = "EXISTING_HAG"
    DELAUNAY_HAG = "DELAUNAY_HAG"
    DTM_HAG = "DTM_HAG"
    NO_HAG_REQUIRED = "NO_HAG_REQUIRED"
    UNAVAILABLE = "UNAVAILABLE"


@dataclass(frozen=True)
class HeightNormalizationDecision:
    """One immutable HAG method selected before PBM execution."""

    mode: HeightNormalizationMode
    source_dimension: str | None = None
    method_signature: str = ""
    fallback_allowed: bool = False

    @classmethod
    def from_dimensions(cls, dimensions: PointDimensionCapabilities, requested_method: str = "") -> "HeightNormalizationDecision":
        if dimensions.has_existing_hag:
            dimension = dimensions.hag_dimension_name
            return cls(HeightNormalizationMode.EXISTING_HAG, dimension, hag_method_signature("existing_normalized_height", dimension or ""))
        if requested_method == "existing_normalized_height":
            return cls(HeightNormalizationMode.EXISTING_HAG, "HeightAboveGround", hag_method_signature("existing_normalized_height", "HeightAboveGround"))
        if requested_method in {"provided_dtm", "dtm"}:
            return cls(HeightNormalizationMode.DTM_HAG, method_signature=hag_method_signature("provided_dtm"))
        if requested_method in {"classified_ground_delaunay", "delaunay", "automatic", "auto"}:
            return cls(HeightNormalizationMode.DELAUNAY_HAG, method_signature=hag_method_signature("classified_ground_delaunay"))
        return cls(HeightNormalizationMode.UNAVAILABLE)

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any] | None) -> "HeightNormalizationDecision":
        data = dict(payload or {})
        return cls(
            HeightNormalizationMode(str(data.get("mode") or "UNAVAILABLE")),
            str(data["source_dimension"]) if data.get("source_dimension") else None,
            str(data.get("method_signature") or ""),
            bool(data.get("fallback_allowed", False)),
        )

    @property
    def adapter_method(self) -> str:
        return {
            HeightNormalizationMode.EXISTING_HAG: "existing_normalized_height",
            HeightNormalizationMode.DELAUNAY_HAG: "classified_ground_delaunay",
            HeightNormalizationMode.DTM_HAG: "provided_dtm",
        }.get(self.mode, "unavailable")

    def to_dict(self) -> dict[str, object]:
        return {"mode": self.mode.value, "source_dimension": self.source_dimension, "method_signature": self.method_signature, "fallback_allowed": self.fallback_allowed}
