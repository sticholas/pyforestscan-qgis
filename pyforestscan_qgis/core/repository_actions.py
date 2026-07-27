"""Typed state and result helpers for visible repository actions."""

from __future__ import annotations

from dataclasses import dataclass

from .lidar_catalog_integrity import CatalogIntegrityReport
from .lidar_catalog_jobs import CatalogJobProgress, CatalogJobStatus
from .lidar_repository_discovery import RepositoryDiscoveryReport


@dataclass(frozen=True)
class RepositoryActionState:
    visible: bool
    enabled: bool
    running: bool = False
    progress: int | None = None
    status_text: str = ""
    disabled_reason: str = ""
    last_result: str = ""
    last_error: str = ""


@dataclass(frozen=True)
class RepositoryActionStates:
    inspect_repository: RepositoryActionState
    scan_file_headers: RepositoryActionState
    build_complete_catalog: RepositoryActionState
    update_catalog: RepositoryActionState
    resume_catalog_build: RepositoryActionState
    pause_after_current_chunk: RepositoryActionState
    move_catalog_local: RepositoryActionState
    open_catalog_folder: RepositoryActionState
    add_coverage_to_map: RepositoryActionState
    repair_catalog: RepositoryActionState
    refresh_repository: RepositoryActionState


def repository_action_states(
    *,
    has_repository: bool,
    repository_readable: bool,
    catalog_exists: bool,
    integrity: CatalogIntegrityReport | None = None,
    latest_job: CatalogJobProgress | None = None,
    running: bool = False,
) -> RepositoryActionStates:
    reason_no_repo = "" if has_repository else "Choose a LiDAR repository first."
    reason_unreadable = "" if repository_readable else "Selected repository cannot be read."
    base_enabled = has_repository and repository_readable and not running
    paused = latest_job is not None and latest_job.status in {CatalogJobStatus.PAUSED, CatalogJobStatus.INTERRUPTED}
    repair_needed = integrity is not None and integrity.status in {"Repair Recommended", "Unusable"} and catalog_exists
    coverage_available = integrity is not None and integrity.rtree_row_count > 0
    disabled = reason_no_repo or reason_unreadable or ("Action is disabled while a catalog job is running." if running else "")
    return RepositoryActionStates(
        inspect_repository=RepositoryActionState(True, base_enabled, running, status_text="Inspect selected folder", disabled_reason=disabled),
        scan_file_headers=RepositoryActionState(True, base_enabled, running, status_text="Scan headers and build catalog", disabled_reason=disabled),
        build_complete_catalog=RepositoryActionState(True, base_enabled, running, status_text="Build complete catalog", disabled_reason=disabled),
        update_catalog=RepositoryActionState(True, base_enabled and catalog_exists, running, status_text="Refresh changed files", disabled_reason=disabled or ("Build a catalog first." if not catalog_exists else "")),
        resume_catalog_build=RepositoryActionState(True, base_enabled and paused, running, status_text="Resume paused job", disabled_reason=disabled or ("No paused or incomplete catalog build exists for this repository." if not paused else "")),
        pause_after_current_chunk=RepositoryActionState(True, running, running, status_text="Pause after current chunk", disabled_reason="" if running else "Only available during an active catalog job."),
        move_catalog_local=RepositoryActionState(True, base_enabled and catalog_exists, running, status_text="Copy active catalog to local storage", disabled_reason=disabled or ("No active catalog exists." if not catalog_exists else "")),
        open_catalog_folder=RepositoryActionState(True, catalog_exists and not running, running, status_text="Open active catalog folder", disabled_reason=("No active catalog exists." if not catalog_exists else disabled)),
        add_coverage_to_map=RepositoryActionState(True, base_enabled and coverage_available, running, status_text="Show repository coverage", disabled_reason=disabled or ("No usable spatial records are available." if not coverage_available else "")),
        repair_catalog=RepositoryActionState(True, base_enabled and repair_needed, running, status_text="Repair catalog integrity", disabled_reason=disabled or ("Catalog repair is not currently needed." if not repair_needed else "")),
        refresh_repository=RepositoryActionState(True, base_enabled, running, status_text="Refresh repository status", disabled_reason=disabled),
    )


def repository_setup_recommendation(discovery: RepositoryDiscoveryReport, integrity: CatalogIntegrityReport | None) -> tuple[str, str]:
    if not discovery.exists:
        return ("Repository folder was not found.", "Choose Folder")
    if not discovery.readable:
        return ("The selected folder cannot be read.", "Choose Folder")
    if discovery.supported_files_found == 0:
        return ("No supported LAS, LAZ, COPC, or EPT data was found in this folder.", "Choose Folder")
    if integrity is None or integrity.status == "Empty":
        return (f"{discovery.supported_files_found:,} LiDAR file(s) found. No usable catalog exists.", "Build Catalog")
    if integrity.status == "Healthy":
        return (f"Repository ready. {integrity.rtree_row_count:,} spatial source(s) available.", "Continue")
    if integrity.source_row_count and integrity.rtree_row_count == 0:
        return (f"{discovery.supported_files_found:,} LiDAR file(s) found. Catalog has {integrity.source_row_count:,} source(s) but no valid spatial index.", "Repair Catalog")
    return (f"Catalog status: {integrity.status}. Review problems before processing.", "Repair Catalog")
