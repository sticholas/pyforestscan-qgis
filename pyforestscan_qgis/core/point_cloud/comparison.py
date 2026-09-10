"""Source-isolated contracts for read-only point-cloud comparison views."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import re
from uuid import uuid4


COMPARISON_DISPLAY_ACTIONS = frozenset({
    "resize", "visible", "resource_limit", "fit", "top", "front", "mode",
    "quality", "point_display", "camera", "navigation", "orbit", "pan",
    "zoom", "classes", "height", "clear_height", "clear_filters",
})
MAX_COMPARISON_VIEWS = 2


def comparison_display_command(command):
    """Return a copied display command or reject any editing authority."""
    if not isinstance(command, dict) or command.get("action") not in COMPARISON_DISPLAY_ACTIONS:
        raise ValueError("Comparison views accept display commands only; editing remains source-isolated.")
    return deepcopy(command)


@dataclass(frozen=True)
class ComparisonSourceRecord:
    comparison_id: str
    path: str
    source_fingerprint: str
    source_type: str
    point_count: int | None = None
    source_crs: str = ""
    authority: str = "READ_ONLY_INDEPENDENT_SOURCE"

    def __post_init__(self):
        if (not re.fullmatch(r"[0-9a-f]{32}", self.comparison_id)
                or not self.path.strip()
                or not re.fullmatch(r"[0-9a-f]{64}", self.source_fingerprint)
                or self.source_type not in ("LAS", "LAZ", "COPC", "EPT")
                or (self.point_count is not None
                    and (type(self.point_count) is not int or self.point_count < 0))
                or self.authority != "READ_ONLY_INDEPENDENT_SOURCE"):
            raise ValueError("Comparison source identity is incomplete or unsafe.")

    @classmethod
    def from_viewer_info(cls, path, info, *, comparison_id=None):
        identity = info.get("source_identity") if isinstance(info, dict) else None
        if not isinstance(identity, dict):
            raise ValueError("Comparison source requires verified viewer identity.")
        metadata = info.get("metadata") or {}
        srs = metadata.get("srs") or {}
        crs = srs.get("wkt") or (f"{srs.get('authority')}:{srs.get('horizontal')}"
            if srs.get("authority") and srs.get("horizontal") else "")
        return cls(comparison_id or uuid4().hex, str(identity.get("path") or path),
            identity.get("sha256", ""), identity.get("source_type", ""),
            info.get("point_count"), crs)

    def relationship(self, primary_fingerprint):
        if primary_fingerprint and not re.fullmatch(r"[0-9a-f]{64}", primary_fingerprint):
            raise ValueError("Primary source fingerprint is invalid.")
        return "SAME_SOURCE_REFERENCE" if self.source_fingerprint == primary_fingerprint else "INDEPENDENT_SOURCE"
