"""QGIS-free repository coverage overlay models."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path

from .lidar_catalog_integrity import inspect_catalog_integrity
from .lidar_catalog_models import stable_root_id
from .spatial_selection import Bounds2D


@dataclass(frozen=True)
class RepositoryCoverageFeature:
    name: str
    source_id: str
    source_type: str
    metadata_status: str
    bounds: Bounds2D
    problem: str = ""


@dataclass(frozen=True)
class RepositoryCoverageModel:
    group_name: str
    mode: str
    crs: str
    union_extent: Bounds2D | None
    features: tuple[RepositoryCoverageFeature, ...]
    message: str


def build_repository_coverage_model(catalog_path: Path | str, root_path: Path | str, *, mode: str = "outline", limit: int = 1000) -> RepositoryCoverageModel:
    report = inspect_catalog_integrity(catalog_path, root_path)
    if report.extent_union is None:
        return RepositoryCoverageModel("PyForestScan - Repository Coverage", mode, _dominant_crs(report.crs_distribution), None, (), "Coverage extent is unavailable because no valid spatial records exist.")
    if mode == "outline":
        return RepositoryCoverageModel("PyForestScan - Repository Coverage", mode, _dominant_crs(report.crs_distribution), report.extent_union, (RepositoryCoverageFeature("Coverage outline", "union", "outline", report.status, report.extent_union),), "Repository coverage outline is ready to add to the map.")
    connection = sqlite3.connect(str(catalog_path))
    connection.row_factory = sqlite3.Row
    root_id = stable_root_id(root_path)
    try:
        rows = connection.execute(
            "SELECT s.source_id, s.relative_path, s.source_type, s.inventory_status, s.metadata_error, b.xmin, b.xmax, b.ymin, b.ymax FROM lidar_source_bounds b JOIN lidar_sources s ON s.id=b.id WHERE s.root_id=? ORDER BY s.relative_path LIMIT ?",
            (root_id, int(limit)),
        ).fetchall()
    finally:
        connection.close()
    features = tuple(
        RepositoryCoverageFeature(
            Path(str(row["relative_path"])).name,
            str(row["source_id"]),
            str(row["source_type"]),
            str(row["inventory_status"]),
            Bounds2D(float(row["xmin"]), float(row["ymin"]), float(row["xmax"]), float(row["ymax"])),
            str(row["metadata_error"] or ""),
        )
        for row in rows
    )
    return RepositoryCoverageModel("PyForestScan - Repository Coverage", mode, _dominant_crs(report.crs_distribution), report.extent_union, features, f"{len(features):,} source footprint(s) are ready to add to the map.")


def _dominant_crs(distribution: dict[str, int]) -> str:
    if not distribution:
        return "unknown"
    return max(distribution, key=distribution.get)
