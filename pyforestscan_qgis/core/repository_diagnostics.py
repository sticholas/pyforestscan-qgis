"""Repository diagnostic report export."""

from __future__ import annotations

import json
from pathlib import Path

from .lidar_catalog_integrity import inspect_catalog_integrity, source_view_rows
from .lidar_repository_discovery import discover_lidar_repository


def repository_diagnostic_payload(root_path: Path | str, catalog_path: Path | str, *, sample_limit: int = 10) -> dict[str, object]:
    discovery = discover_lidar_repository(root_path)
    integrity = inspect_catalog_integrity(catalog_path, root_path)
    return {
        "repository_path": str(root_path),
        "discovery": {
            "exists": discovery.exists,
            "readable": discovery.readable,
            "directories_scanned": discovery.directories_scanned,
            "files_examined": discovery.files_examined,
            "supported_files_found": discovery.supported_files_found,
            "source_type_counts": discovery.source_type_counts,
            "warnings": list(discovery.warnings),
            "errors": list(discovery.errors),
        },
        "catalog": {
            "path": str(catalog_path),
            "status": integrity.status,
            "source_count": integrity.source_row_count,
            "usable_source_count": integrity.rtree_row_count,
            "rtree_count": integrity.rtree_row_count,
            "skip_reason_counts": integrity.skip_reason_counts,
            "crs_distribution": integrity.crs_distribution,
            "extent_union": None if integrity.extent_union is None else integrity.extent_union.__dict__,
            "messages": list(integrity.messages),
        },
        "sample_sources": [row.__dict__ for row in source_view_rows(catalog_path, root_path, limit=sample_limit)],
    }


def export_repository_diagnostic_report(root_path: Path | str, catalog_path: Path | str, output_path: Path | str) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(repository_diagnostic_payload(root_path, catalog_path), indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    return path
