"""Pure validation and promotion gate for bounded CHM requests."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .selection_product_request import SelectionProductRequest

_SUPPORTED_SUFFIXES = (".las", ".laz", ".copc", ".copc.laz")


@dataclass(frozen=True)
class SelectionChmPreflightReport:
    """Deterministic validation result for one bounded CHM request."""

    ready: bool
    source_format: str
    blockers: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    execution_status: str = "REVIEW_ONLY"

    @property
    def summary(self) -> str:
        if self.ready:
            return "CHM scoped request is ready for bounded execution."
        return "CHM scoped request needs review: " + "; ".join(self.blockers)


def detect_selection_source_format(source_path: Path | str) -> str:
    """Identify supported local LAS/LAZ/COPC or EPT source forms."""
    path = Path(source_path)
    lowered = str(path).lower()
    if path.name.lower() == "ept.json" or (path.is_dir() and (path / "ept.json").exists()):
        return "EPT"
    if lowered.endswith(".copc.laz"):
        return "COPC"
    if lowered.endswith((".las", ".laz", ".copc")):
        return "LAS/LAZ"
    return "UNSUPPORTED"


def preflight_selection_chm(
    request: SelectionProductRequest,
    *,
    backend_ready: bool,
    source_exists: bool | None = None,
) -> SelectionChmPreflightReport:
    """Validate a bounded CHM request without reading point data."""
    blockers: list[str] = []
    warnings: list[str] = []
    source_format = detect_selection_source_format(request.source_path)
    if not backend_ready:
        blockers.append("PBM backend is not READY.")
    if source_exists is False:
        blockers.append("The selected source does not exist.")
    if source_format == "UNSUPPORTED":
        blockers.append("The selected source format is not supported for bounded CHM.")
    if not request.geometry_crs.strip():
        blockers.append("Selection geometry CRS is required.")
    if len(request.geometry) < 4 or request.geometry[0] != request.geometry[-1]:
        blockers.append("Selection geometry must be a closed polygon.")
    if request.point_count is not None and request.point_count <= 0:
        blockers.append("The authoritative selection contains no source points.")
    if request.review_required:
        blockers.append("Scientific review is required before this scoped CHM can run.")
    if request.z_range is not None and request.hag_range is not None:
        warnings.append("Both elevation and HAG ranges are present; the selected vertical axis controls execution.")
    ready = not blockers
    return SelectionChmPreflightReport(
        ready=ready,
        source_format=source_format,
        blockers=tuple(blockers),
        warnings=tuple(warnings),
        execution_status="READY_FOR_EXECUTION" if ready else "REVIEW_ONLY",
    )
