"""Polygon-driven LiDAR folder processing plan models."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .lidar_inventory import LidarInventory, LidarSourceRecord
from .spatial_selection import Bounds2D, PolygonSelection

DEFAULT_LARGE_POINT_WARNING = 25_000_000
DEFAULT_LARGE_SOURCE_WARNING = 25


@dataclass(frozen=True)
class LidarIntersectionRecord:
    """Intersection decision for one source and the selected polygon."""

    source: LidarSourceRecord
    intersects: bool
    reason: str
    ept_bounds: tuple[tuple[float, float], tuple[float, float]] | None = None


@dataclass(frozen=True)
class PolygonProcessingPlan:
    """Preflight plan for polygon-driven folder processing."""

    inventory: LidarInventory
    polygon: PolygonSelection
    output_folder: Path
    products: tuple[str, ...]
    intersections: tuple[LidarIntersectionRecord, ...]
    processing_crs: str
    warnings: tuple[str, ...]

    @property
    def selected_sources(self) -> tuple[LidarSourceRecord, ...]:
        return tuple(item.source for item in self.intersections if item.intersects)

    @property
    def estimated_point_count(self) -> int | None:
        counts = [item.point_count for item in self.selected_sources]
        if not counts or any(count is None for count in counts):
            return None
        return int(sum(count for count in counts if count is not None))


@dataclass(frozen=True)
class PolygonProcessingResult:
    """Result placeholder for a polygon-folder processing run."""

    plan: PolygonProcessingPlan
    output_paths: tuple[Path, ...]
    status: str
    message: str


def build_polygon_processing_plan(
    inventory: LidarInventory,
    polygon: PolygonSelection,
    output_folder: Path,
    products: tuple[str, ...],
    *,
    processing_crs: str | None = None,
    large_point_threshold: int = DEFAULT_LARGE_POINT_WARNING,
    large_source_threshold: int = DEFAULT_LARGE_SOURCE_WARNING,
) -> PolygonProcessingPlan:
    """Build an intersection/preflight plan without reading full point clouds."""
    if not products:
        raise ValueError("Select at least one product for polygon processing.")
    crs = (processing_crs or polygon.crs).strip()
    if not crs:
        raise ValueError("Processing CRS is required.")
    intersections = tuple(_intersect_source(source, polygon.bounds) for source in inventory.sources)
    selected = tuple(item.source for item in intersections if item.intersects)
    warnings: list[str] = []
    if not selected:
        warnings.append("No discovered LiDAR sources intersect the selected polygon bounds.")
    known_crs = {source.crs for source in selected if source.crs}
    if len(known_crs) > 1 and processing_crs is None:
        warnings.append("Intersecting sources report multiple CRS values; choose a processing CRS before running.")
    elif known_crs and any(source.crs and source.crs != crs for source in selected):
        warnings.append("At least one intersecting source CRS differs from the processing CRS; reprojection is required.")
    known_counts = [source.point_count for source in selected if source.point_count is not None]
    if len(selected) > large_source_threshold:
        warnings.append(f"Large source selection: {len(selected)} intersecting files. Use PBM/chunked processing.")
    if known_counts and sum(known_counts) > large_point_threshold:
        warnings.append(f"Large point estimate: {sum(known_counts):,} points. Use PBM/chunked processing.")
    if any(source.bounds is None for source in inventory.sources):
        warnings.append("Some source bounds are unknown; run metadata inventory before processing to avoid unnecessary reads.")
    return PolygonProcessingPlan(inventory, polygon, Path(output_folder), tuple(products), intersections, crs, tuple(warnings))


def polygon_preflight_summary(plan: PolygonProcessingPlan) -> tuple[str, ...]:
    """Return concise guided UI summary lines for a polygon plan."""
    count = len(plan.selected_sources)
    points = plan.estimated_point_count
    point_text = "unknown point count" if points is None else f"{points:,} estimated points"
    return (
        f"Polygon area: {plan.polygon.bounds.area:g} square map units",
        f"Intersecting sources: {count} of {len(plan.inventory.sources)}",
        f"Estimated workload: {point_text}",
        f"Products: {', '.join(plan.products)}",
        f"Output folder: {plan.output_folder}",
        *(f"Warning: {warning}" for warning in plan.warnings),
    )


def _intersect_source(source: LidarSourceRecord, polygon_bounds: Bounds2D) -> LidarIntersectionRecord:
    if source.bounds is None:
        return LidarIntersectionRecord(source, False, "bounds unavailable")
    if not source.bounds.intersects(polygon_bounds):
        return LidarIntersectionRecord(source, False, "outside polygon bounds")
    ept_bounds = polygon_bounds.to_ept_bounds() if source.source_type == "ept" else None
    return LidarIntersectionRecord(source, True, "intersects polygon bounds", ept_bounds=ept_bounds)
