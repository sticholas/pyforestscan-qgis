"""Indexed LiDAR catalog query and automatic polygon-envelope helpers."""

from __future__ import annotations

import math
import re
import time
from pathlib import Path
from typing import Callable

from .lidar_catalog import connect_catalog, query_intersecting_records
from .lidar_catalog_models import CatalogThresholds, LidarCatalogQuery, LidarCatalogQueryResult, PolygonQueryGeometry, WorkloadEstimate, stable_root_id
from .polygon_source import NormalizedPolygonSelection
from .spatial_selection import Bounds2D, polygon_selection_from_wkt

CoordinateTransformer = Callable[[float, float], tuple[float, float]]
MAX_PLAUSIBLE_POINT_ESTIMATE = 10_000_000_000_000


def derive_polygon_query_geometry(
    polygon: NormalizedPolygonSelection,
    *,
    catalog_crs: str | None = None,
    transformer: CoordinateTransformer | None = None,
) -> PolygonQueryGeometry:
    """Derive broad catalog/EPT bounds while retaining exact polygon WKT."""
    target_crs = (catalog_crs or polygon.processing_crs or polygon.source_crs).strip()
    source_crs = (polygon.processing_crs or polygon.source_crs).strip()
    warnings: list[str] = []
    wkt = polygon.geometry_wkt
    if target_crs and source_crs and target_crs != source_crs:
        if transformer is not None:
            wkt = transform_wkt_coordinates(wkt, transformer)
        else:
            warnings.append("Polygon CRS differs from catalog CRS; using normalized polygon coordinates because no transformer was available.")
    selection = polygon_selection_from_wkt(wkt, target_crs or source_crs, source_label=polygon.source_description)
    return PolygonQueryGeometry(
        envelope=selection.bounds,
        exact_polygon_wkt=wkt,
        source_crs=source_crs,
        catalog_crs=target_crs or source_crs,
        ept_bounds=selection.bounds.to_ept_bounds(),
        warnings=tuple(warnings),
    )


def transform_wkt_coordinates(wkt: str, transformer: CoordinateTransformer) -> str:
    """Transform numeric XY pairs in simple Polygon/MultiPolygon WKT."""
    numbers = list(re.finditer(r"[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?", wkt))
    if len(numbers) % 2 != 0:
        raise ValueError("Polygon WKT must contain XY coordinate pairs for CRS transformation.")
    replacements: list[tuple[int, int, str]] = []
    for x_match, y_match in zip(numbers[0::2], numbers[1::2]):
        x, y = transformer(float(x_match.group(0)), float(y_match.group(0)))
        replacements.append((x_match.start(), x_match.end(), f"{x:.12g}"))
        replacements.append((y_match.start(), y_match.end(), f"{y:.12g}"))
    out = wkt
    for start, end, value in sorted(replacements, reverse=True):
        out = out[:start] + value + out[end:]
    return out


def query_catalog_for_polygon(
    catalog_path: Path | str,
    root_path: Path | str,
    polygon: NormalizedPolygonSelection,
    *,
    catalog_crs: str | None = None,
    thresholds: CatalogThresholds | None = None,
) -> LidarCatalogQueryResult:
    """Query catalog candidates whose indexed bounds intersect the polygon envelope."""
    thresholds = thresholds or CatalogThresholds()
    geometry = derive_polygon_query_geometry(polygon, catalog_crs=catalog_crs)
    query = LidarCatalogQuery(Path(catalog_path), Path(root_path), geometry.envelope, geometry.exact_polygon_wkt, geometry.catalog_crs, thresholds)
    start = time.perf_counter()
    connection = connect_catalog(catalog_path)
    try:
        root_id = stable_root_id(root_path)
        rtree_start = time.perf_counter()
        records = query_intersecting_records(
            connection,
            root_id,
            geometry.envelope.xmin,
            geometry.envelope.xmax,
            geometry.envelope.ymin,
            geometry.envelope.ymax,
            limit=thresholds.max_candidates_per_run + 1,
        )
        rtree_elapsed = time.perf_counter() - rtree_start
        row_start = time.perf_counter()
        error_row = connection.execute(
            "SELECT COUNT(*) AS count FROM lidar_sources WHERE root_id = ? AND inventory_status = 'error'",
            (root_id,),
        ).fetchone()
        indexed_row = connection.execute(
            "SELECT COUNT(*) AS count FROM lidar_sources WHERE root_id = ? AND inventory_status = 'indexed'",
            (root_id,),
        ).fetchone()
        row_elapsed = time.perf_counter() - row_start
    finally:
        connection.close()
    warnings = list(geometry.warnings)
    candidate_count = len(records)
    limited = False
    if candidate_count > thresholds.max_candidates_per_run:
        limited = True
        records = records[: thresholds.max_candidates_per_run]
        warnings.append(f"Catalog query exceeded the maximum candidate threshold of {thresholds.max_candidates_per_run:,}; refine the polygon or thresholds before running.")
    estimate_start = time.perf_counter()
    workload_estimate = _estimated_points(records, polygon_area=polygon.area)
    estimated_points = workload_estimate.point_estimate
    estimate_confidence = workload_estimate.confidence
    estimate_warning = workload_estimate.warning
    estimate_elapsed = time.perf_counter() - estimate_start
    estimated_bytes = sum(record.file_size for record in records)
    elapsed = time.perf_counter() - start
    if estimate_warning:
        warnings.append(estimate_warning)
    if estimated_points is not None and estimated_points > thresholds.max_estimated_points:
        warnings.append(f"Estimated point count {estimated_points:,} exceeds the configured threshold.")
    if estimated_bytes > thresholds.max_estimated_input_bytes:
        warnings.append(f"Estimated input size {estimated_bytes:,} bytes exceeds the configured threshold.")
    metadata_errors = int(error_row["count"] or 0) if error_row is not None else 0
    indexed_count = int(indexed_row["count"] or 0) if indexed_row is not None else 0
    if metadata_errors:
        warnings.append(f"{metadata_errors:,} source(s) could not be indexed. Polygon source selection may be incomplete.")
    if indexed_count == 0:
        warnings.append("Catalog has no indexed sources for this LiDAR repository.")
    return LidarCatalogQueryResult(
        query=query,
        records=records,
        candidate_count=candidate_count,
        exact_intersecting_count=len(records),
        skipped_count=max(0, indexed_count - len(records)),
        metadata_error_count=metadata_errors,
        estimated_point_count=estimated_points,
        estimated_bytes=estimated_bytes,
        query_seconds=elapsed,
        warnings=tuple(dict.fromkeys(warnings)),
        timing_seconds={
            "rtree_lookup": rtree_elapsed,
            "row_loading": row_elapsed,
            "workload_estimation": estimate_elapsed,
            "total_preflight_query": elapsed,
        },
        point_estimate_confidence=estimate_confidence,
        workload_estimate=workload_estimate,
    )


def _estimated_points(records, *, polygon_area: float | None = None) -> WorkloadEstimate:
    if not records:
        return WorkloadEstimate(None, polygon_area=polygon_area)
    source_types = {str(getattr(record, "source_type", "")).lower() for record in records}
    if source_types & {"ept", "copc"}:
        return WorkloadEstimate(
            None,
            confidence="Unavailable",
            method="Unavailable",
            polygon_area=polygon_area,
            unit_basis="source metadata only",
            assumptions=("EPT/COPC root point counts describe the source, not the requested polygon subset.",),
            warning="Estimated point count is unavailable because EPT/COPC metadata does not provide a reliable polygon-subset estimate.",
            is_plausible=False,
        )
    if any(record.point_count is None for record in records):
        return WorkloadEstimate(None, polygon_area=polygon_area)
    total = 0
    for record in records:
        value = record.point_count
        if value is None:
            return WorkloadEstimate(None, polygon_area=polygon_area)
        if not isinstance(value, int) or value < 0:
            return WorkloadEstimate(None, polygon_area=polygon_area, warning="Estimated point count is unavailable because catalog point metadata is malformed.")
        total += value
        if total > MAX_PLAUSIBLE_POINT_ESTIMATE:
            return WorkloadEstimate(None, polygon_area=polygon_area, warning="Estimated point count is unavailable because catalog point metadata is implausibly large.")
    if not math.isfinite(float(total)) or total < 0:
        return WorkloadEstimate(None, polygon_area=polygon_area, warning="Estimated point count is unavailable because catalog point metadata is invalid.")
    return WorkloadEstimate(
        int(total),
        lower_bound=int(total),
        upper_bound=int(total),
        confidence="High",
        method="Catalog source-point sum for independent nonoverlapping tiles",
        polygon_area=polygon_area,
        unit_basis="catalog source metadata",
        assumptions=("Selected source files are independent catalog records.",),
        is_plausible=True,
    )
