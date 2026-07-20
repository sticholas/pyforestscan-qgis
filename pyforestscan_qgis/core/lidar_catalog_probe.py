"""Instant and bounded probes for LiDAR repository selection."""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from pathlib import Path

from .lidar_catalog import catalog_summary
from .lidar_catalog_models import LidarCatalogSummary, default_lidar_catalog_path
from .lidar_inventory import lidar_source_type

DEFAULT_PROBE_ENTRY_LIMIT = 500
DEFAULT_PROBE_SECONDS = 2.0


@dataclass(frozen=True)
class RepositorySelectionStatus:
    """Immediate repository-path status that never enumerates children."""

    path: Path
    normalized_path: Path
    valid: bool
    readable: bool
    catalog_path: Path
    catalog_exists: bool
    message: str


@dataclass(frozen=True)
class QuickProbeResult:
    """Bounded top-level repository probe."""

    selection: RepositorySelectionStatus
    inspected_entries: int
    stopped_by_limit: bool
    elapsed_seconds: float
    top_level_directory_examples: tuple[str, ...]
    source_type_examples: tuple[str, ...]
    filesystem_note: str
    recommendation: str
    catalog_summary: LidarCatalogSummary


def select_lidar_repository_path(path: str | Path) -> RepositorySelectionStatus:
    """Normalize and validate a repository path without deep scanning."""
    raw = Path(path).expanduser()
    normalized = raw.resolve() if raw.exists() else raw.absolute()
    catalog = default_lidar_catalog_path(normalized)
    valid = normalized.is_dir()
    readable = False
    if valid:
        try:
            os.stat(normalized)
            readable = os.access(normalized, os.R_OK)
        except OSError:
            readable = False
    if not valid:
        message = f"Path is not a directory: {normalized}"
    elif not readable:
        message = f"Directory is not readable: {normalized}"
    elif catalog.exists():
        message = "Catalog found. Refresh status or analyze polygon."
    else:
        message = "No Catalog - Build Catalog when ready."
    return RepositorySelectionStatus(normalized, normalized, valid, readable, catalog, catalog.exists(), message)


def quick_probe_lidar_repository(path: str | Path, *, max_entries: int = DEFAULT_PROBE_ENTRY_LIMIT, max_seconds: float = DEFAULT_PROBE_SECONDS) -> QuickProbeResult:
    """Inspect only bounded top-level examples and catalog presence."""
    selection = select_lidar_repository_path(path)
    start = time.monotonic()
    inspected = 0
    stopped = False
    dirs: list[str] = []
    source_types: list[str] = []
    if selection.valid and selection.readable:
        try:
            with os.scandir(selection.normalized_path) as entries:
                for entry in entries:
                    elapsed = time.monotonic() - start
                    if inspected >= max_entries or elapsed >= max_seconds:
                        stopped = True
                        break
                    inspected += 1
                    try:
                        if entry.is_dir(follow_symlinks=False) and len(dirs) < 8:
                            dirs.append(entry.name)
                        elif entry.is_file(follow_symlinks=False):
                            source_type = lidar_source_type(Path(entry.name), include_ept=True)
                            if source_type and source_type not in source_types:
                                source_types.append(source_type)
                    except OSError:
                        continue
        except OSError:
            stopped = False
    elapsed = time.monotonic() - start
    summary = catalog_summary(selection.catalog_path, selection.normalized_path) if selection.catalog_exists else catalog_summary(selection.catalog_path, selection.normalized_path)
    note = _filesystem_note(selection.normalized_path)
    if not selection.valid or not selection.readable:
        recommendation = selection.message
    elif not selection.catalog_exists:
        recommendation = "Build Catalog explicitly before polygon preflight. This probe did not scan recursively."
    elif summary.error_count:
        recommendation = "Catalog is present with metadata errors. Review or update before critical processing."
    else:
        recommendation = "Catalog is present. Analyze Polygon can query the indexed catalog."
    return QuickProbeResult(selection, inspected, stopped, elapsed, tuple(dirs), tuple(source_types), note, recommendation, summary)


def _filesystem_note(path: Path) -> str:
    text = str(path).replace("\\", "/").lower()
    if text.startswith("//") or text.startswith("\\\\"):
        return "Network or UNC path detected; use conservative metadata workers."
    if "/mnt/" in text or text.startswith("/mnt/"):
        return "Mounted filesystem detected; performance may depend on host storage."
    if text.startswith("/home/") or ":/" in text:
        return "Local filesystem profile."
    return "Unknown filesystem profile; use conservative catalog settings."
