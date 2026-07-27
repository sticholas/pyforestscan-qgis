"""Header reread and stored-vs-actual verification helpers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .lidar_catalog_builder import inspect_lidar_header
from .lidar_catalog_models import LidarCatalogRecord
from .spatial_selection import Bounds2D


@dataclass(frozen=True)
class HeaderVerificationResult:
    source_path: Path
    stored_bounds: Bounds2D | None
    actual_bounds: Bounds2D | None
    bounds_match: bool
    stored_crs: str | None
    actual_crs: str | None
    crs_match: bool
    point_count_match: bool
    reader: str
    warnings: tuple[str, ...]
    recommended_action: str


def verify_header_record(stored: LidarCatalogRecord, root: Path | str, *, reader=None) -> HeaderVerificationResult:
    root_path = Path(root)
    read = reader or inspect_lidar_header
    warnings: list[str] = []
    try:
        actual = read(stored.source_path, root_path, stored.root_id)
        actual_bounds = actual.bounds
        actual_crs = actual.source_crs
        reader_name = "pdm/laspy-unavailable:fallback-las-public-header"
    except Exception as exc:  # noqa: BLE001 - diagnostics must report header failures.
        actual_bounds = None
        actual_crs = None
        reader_name = "header-reread-failed"
        warnings.append(str(exc))
    bounds_match = _bounds_close(stored.bounds, actual_bounds)
    crs_match = (stored.source_crs or "") == (actual_crs or "")
    point_count_match = stored.point_count is None or actual_bounds is not None
    if not actual_crs:
        warnings.append("No embedded CRS was found by the available header reader.")
    if not bounds_match:
        action = "Refresh File Metadata"
    elif not actual_crs:
        action = "Assign Coordinate System"
    else:
        action = "No action needed"
    return HeaderVerificationResult(stored.source_path, stored.bounds, actual_bounds, bounds_match, stored.source_crs, actual_crs, crs_match, point_count_match, reader_name, tuple(warnings), action)


def _bounds_close(left: Bounds2D | None, right: Bounds2D | None, tolerance: float = 1e-6) -> bool:
    if left is None or right is None:
        return left is right
    return all(abs(a - b) <= tolerance for a, b in ((left.xmin, right.xmin), (left.xmax, right.xmax), (left.ymin, right.ymin), (left.ymax, right.ymax)))
