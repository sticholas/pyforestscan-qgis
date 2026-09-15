"""Bounded, provenance-carrying payloads for viewer scientific overlays."""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Mapping, Sequence

MAX_CELLS = 128 * 128

@dataclass(frozen=True)
class ScientificOverlayPayload:
    product_id: str
    label: str
    kind: str
    units: str
    crs: str
    extent: tuple[float, float, float, float]
    rows: int
    columns: int
    values: tuple[float | None, ...]
    value_range: tuple[float, float] | None
    nodata: float | None
    palette: str
    provenance: Mapping[str, str]
    vertical_semantics: str = ""
    surface_mode: str = "flat"

    def __post_init__(self) -> None:
        xmin, ymin, xmax, ymax = self.extent
        if not self.product_id or not self.label or not self.kind:
            raise ValueError("Scientific overlay identity is incomplete.")
        if not all(math.isfinite(float(value)) for value in self.extent) or not (xmin < xmax and ymin < ymax):
            raise ValueError("Scientific overlay extent must be finite and ascending.")
        if not (1 <= self.rows <= 128 and 1 <= self.columns <= 128):
            raise ValueError("Scientific overlay grid must be between 1 and 128 cells per side.")
        if self.rows * self.columns > MAX_CELLS or len(self.values) != self.rows * self.columns:
            raise ValueError("Scientific overlay grid payload has an invalid size.")
        if self.surface_mode not in {"flat", "values"}:
            raise ValueError("Scientific overlay surface mode is unsupported.")
        if self.value_range is not None and (len(self.value_range) != 2 or not all(math.isfinite(float(value)) for value in self.value_range)):
            raise ValueError("Scientific overlay value range is invalid.")
        if not self.provenance.get("source_fingerprint"):
            raise ValueError("Scientific overlay provenance requires a source fingerprint.")

    @property
    def valid_value_count(self) -> int:
        return sum(value is not None and math.isfinite(float(value)) for value in self.values)

    def as_command(self) -> dict[str, Any]:
        return {"action": "scientific_overlay", "overlay": {
            "product_id": self.product_id, "label": self.label, "kind": self.kind,
            "units": self.units, "crs": self.crs, "extent": list(self.extent),
            "rows": self.rows, "columns": self.columns, "values": list(self.values),
            "value_range": list(self.value_range) if self.value_range else None,
            "nodata": self.nodata, "palette": self.palette,
            "vertical_semantics": self.vertical_semantics, "surface_mode": self.surface_mode,
            "provenance": dict(self.provenance)}}

def overlay_value_range(values: Sequence[float | None]) -> tuple[float, float] | None:
    valid = [float(value) for value in values if value is not None and math.isfinite(float(value))]
    return (min(valid), max(valid)) if valid else None
