"""Authoritative LiDAR repository discovery service.

The discovery pass intentionally reads directory entries only. Header metadata
belongs to the catalog builder; this module answers whether a selected folder
contains supported logical LiDAR sources before expensive work starts.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from pathlib import Path

from .ept_repository import is_ept_internal_path, prune_ept_traversal, resolve_ept_selection
from .lidar_catalog_models import CatalogBuildOptions
from .lidar_inventory import lidar_source_type


@dataclass(frozen=True)
class RepositoryDiscoveryReport:
    selected_root: Path
    normalized_root: Path
    exists: bool
    readable: bool
    recursive: bool
    directories_scanned: int = 0
    files_examined: int = 0
    supported_files_found: int = 0
    las_count: int = 0
    laz_count: int = 0
    copc_count: int = 0
    ept_count: int = 0
    unsupported_files: tuple[Path, ...] = ()
    ignored_files: tuple[Path, ...] = ()
    inaccessible_files: tuple[Path, ...] = ()
    duplicate_files: tuple[Path, ...] = ()
    discovered_paths: tuple[Path, ...] = ()
    elapsed_seconds: float = 0.0
    warnings: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()

    @property
    def usable(self) -> bool:
        return self.exists and self.readable and self.supported_files_found > 0

    @property
    def source_type_counts(self) -> dict[str, int]:
        return {"las": self.las_count, "laz": self.laz_count, "copc": self.copc_count, "ept": self.ept_count}

    def summary_lines(self) -> tuple[str, ...]:
        status = "usable sources found" if self.usable else "no usable logical sources found"
        return (
            f"Repository: {self.normalized_root}",
            f"Status: {status}",
            f"Folders scanned: {self.directories_scanned:,}",
            f"Files examined: {self.files_examined:,}",
            f"Supported LiDAR files: {self.supported_files_found:,}",
            f"LAS: {self.las_count:,}; LAZ: {self.laz_count:,}; COPC: {self.copc_count:,}; EPT: {self.ept_count:,}",
        )


class LidarRepositoryDiscoveryService:
    """Discover supported logical LiDAR sources under a selected root."""

    def inspect(self, root_path: Path | str, *, options: CatalogBuildOptions | None = None) -> RepositoryDiscoveryReport:
        options = options or CatalogBuildOptions()
        selected = Path(root_path).expanduser()
        normalized = selected.resolve() if selected.exists() else selected.absolute()
        start = time.perf_counter()
        if not normalized.exists():
            return RepositoryDiscoveryReport(selected, normalized, False, False, options.recursive, elapsed_seconds=time.perf_counter() - start, errors=(f"Repository folder does not exist: {normalized}",))
        if not normalized.is_dir():
            return RepositoryDiscoveryReport(selected, normalized, True, False, options.recursive, elapsed_seconds=time.perf_counter() - start, errors=(f"Repository path is not a folder: {normalized}",))
        try:
            readable = os.access(normalized, os.R_OK)
        except OSError:
            readable = False
        if not readable:
            return RepositoryDiscoveryReport(selected, normalized, True, False, options.recursive, elapsed_seconds=time.perf_counter() - start, errors=(f"Repository folder cannot be read: {normalized}",))

        # One ept.json represents the complete logical source. Never enumerate
        # its data, hierarchy, or source storage during normal discovery.
        ept = resolve_ept_selection(normalized)
        if ept is not None:
            allowed = not options.source_types or "ept" in options.source_types
            discovered = (ept.ept_json,) if allowed else ()
            return RepositoryDiscoveryReport(
                selected, ept.normalized_repository, True, True, options.recursive,
                directories_scanned=1, files_examined=1,
                supported_files_found=len(discovered), ept_count=len(discovered),
                discovered_paths=discovered, elapsed_seconds=time.perf_counter() - start,
                warnings=() if discovered else ("EPT sources are excluded by the selected source-type filter.",),
            )

        directories = 0
        files_examined = 0
        counts = {"las": 0, "laz": 0, "copc": 0, "ept": 0}
        unsupported: list[Path] = []
        ignored: list[Path] = []
        inaccessible: list[Path] = []
        duplicates: list[Path] = []
        discovered: list[Path] = []
        seen: set[str] = set()
        root_depth = len(normalized.parts)
        try:
            walker = os.walk(normalized, followlinks=False)
            for dirpath, dirnames, filenames in walker:
                current = Path(dirpath)
                directories += 1
                depth = len(current.parts) - root_depth
                if options.max_depth is not None and depth >= options.max_depth:
                    dirnames[:] = []
                if options.ignore_hidden:
                    hidden_dirs = [current / item for item in dirnames if item.startswith(".")]
                    hidden_files = [current / item for item in filenames if item.startswith(".")]
                    ignored.extend(hidden_dirs[:20])
                    ignored.extend(hidden_files[:20])
                    dirnames[:] = [item for item in dirnames if not item.startswith(".")]
                    filenames = [item for item in filenames if not item.startswith(".")]
                if options.ignore_names:
                    ignored_names = set(options.ignore_names)
                    ignored.extend((current / item for item in dirnames if item in ignored_names))
                    dirnames[:] = [item for item in dirnames if item not in ignored_names]
                for ept_source in prune_ept_traversal(current, dirnames, filenames):
                    _append_source(ept_source, "ept", counts, discovered, seen, duplicates)
                if is_ept_internal_path(current):
                    ignored.extend((current / item for item in filenames[:20]))
                    dirnames[:] = []
                    continue
                for name in filenames:
                    path = current / name
                    files_examined += 1
                    if is_ept_internal_path(path) or name.lower() in {"ept.json", "ept-build.json", "ept-sources.json"}:
                        ignored.append(path)
                        continue
                    try:
                        source_type = lidar_source_type(path, include_ept=True)
                    except OSError:
                        inaccessible.append(path)
                        continue
                    if source_type is None:
                        if len(unsupported) < 200:
                            unsupported.append(path)
                        continue
                    if options.source_types and source_type not in options.source_types:
                        ignored.append(path)
                        continue
                    _append_source(path, source_type, counts, discovered, seen, duplicates)
                if not options.recursive:
                    dirnames[:] = []
        except OSError as exc:
            return RepositoryDiscoveryReport(selected, normalized, True, False, options.recursive, directories, files_examined, sum(counts.values()), counts["las"], counts["laz"], counts["copc"], counts["ept"], tuple(unsupported), tuple(ignored), tuple(inaccessible), tuple(duplicates), tuple(discovered), time.perf_counter() - start, errors=(str(exc),))
        warnings: list[str] = []
        if not discovered:
            warnings.append("No supported LAS, LAZ, COPC, or EPT logical sources were found.")
        if duplicates:
            warnings.append(f"{len(duplicates):,} duplicate source path(s) were ignored.")
        return RepositoryDiscoveryReport(selected, normalized, True, True, options.recursive, directories, files_examined, sum(counts.values()), counts["las"], counts["laz"], counts["copc"], counts["ept"], tuple(unsupported), tuple(ignored), tuple(inaccessible), tuple(duplicates), tuple(discovered), time.perf_counter() - start, tuple(warnings), ())


def discover_lidar_repository(root_path: Path | str, *, options: CatalogBuildOptions | None = None) -> RepositoryDiscoveryReport:
    return LidarRepositoryDiscoveryService().inspect(root_path, options=options)


def _append_source(path: Path, source_type: str, counts: dict[str, int], discovered: list[Path], seen: set[str], duplicates: list[Path]) -> None:
    key = str(path.resolve() if path.exists() else path.absolute()).replace("\\", "/").lower()
    if key in seen:
        duplicates.append(path)
        return
    seen.add(key)
    counts[source_type] = counts.get(source_type, 0) + 1
    discovered.append(path)
