"""Durable, chunked LiDAR catalog jobs."""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Callable

from .lidar_catalog_builder import build_lidar_catalog
from .lidar_catalog_models import CatalogBuildOptions, LidarCatalogBuildResult, default_lidar_catalog_path, stable_root_id, utc_now_iso


class CatalogJobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    PAUSING = "pausing"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    INTERRUPTED = "interrupted"


class CatalogJobStage(str, Enum):
    PREPARING = "Preparing"
    DISCOVERING = "Discovering Sources"
    READING_METADATA = "Reading Metadata"
    WRITING_INDEX = "Writing Spatial Index"
    DETECTING_DELETED = "Detecting Deleted Sources"
    VERIFYING = "Verifying Catalog"
    FINALIZING = "Finalizing"
    READY = "Ready"


@dataclass(frozen=True)
class CatalogJobSpec:
    """Durable catalog job request."""

    job_id: str
    job_type: str
    root_path: Path
    catalog_path: Path
    options: CatalogBuildOptions = CatalogBuildOptions()
    created_at: str = field(default_factory=utc_now_iso)

    @staticmethod
    def create(job_type: str, root_path: Path | str, catalog_path: Path | str | None = None, *, options: CatalogBuildOptions | None = None) -> "CatalogJobSpec":
        root = Path(root_path).expanduser().resolve()
        return CatalogJobSpec(
            job_id=f"lidar-catalog-{uuid.uuid4().hex[:12]}",
            job_type=job_type,
            root_path=root,
            catalog_path=Path(catalog_path) if catalog_path is not None else default_lidar_catalog_path(root),
            options=options or CatalogBuildOptions(),
        )

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["root_path"] = str(self.root_path)
        payload["catalog_path"] = str(self.catalog_path)
        payload["options"] = _options_to_dict(self.options)
        return payload

    @staticmethod
    def from_dict(payload: dict[str, object]) -> "CatalogJobSpec":
        return CatalogJobSpec(
            job_id=str(payload["job_id"]),
            job_type=str(payload["job_type"]),
            root_path=Path(str(payload["root_path"])),
            catalog_path=Path(str(payload["catalog_path"])),
            options=_options_from_dict(dict(payload.get("options", {}) or {})),
            created_at=str(payload.get("created_at") or utc_now_iso()),
        )


@dataclass(frozen=True)
class CatalogJobProgress:
    """User-facing progress snapshot."""

    job_id: str
    status: CatalogJobStatus
    stage: CatalogJobStage
    discovered: int = 0
    indexed: int = 0
    unchanged: int = 0
    errors: int = 0
    deleted: int = 0
    elapsed_seconds: float = 0.0
    rate_per_second: float | None = None
    latest_source: str = ""
    queue_depth: int | None = None
    percent: int | None = None
    eta_text: str | None = None
    updated_at: str = field(default_factory=utc_now_iso)
    message: str = ""

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["status"] = self.status.value
        payload["stage"] = self.stage.value
        return payload

    @staticmethod
    def from_dict(payload: dict[str, object]) -> "CatalogJobProgress":
        return CatalogJobProgress(
            job_id=str(payload.get("job_id", "")),
            status=CatalogJobStatus(str(payload.get("status", CatalogJobStatus.QUEUED.value))),
            stage=CatalogJobStage(str(payload.get("stage", CatalogJobStage.PREPARING.value))),
            discovered=int(payload.get("discovered", 0) or 0),
            indexed=int(payload.get("indexed", 0) or 0),
            unchanged=int(payload.get("unchanged", 0) or 0),
            errors=int(payload.get("errors", 0) or 0),
            deleted=int(payload.get("deleted", 0) or 0),
            elapsed_seconds=float(payload.get("elapsed_seconds", 0.0) or 0.0),
            rate_per_second=None if payload.get("rate_per_second") is None else float(payload.get("rate_per_second")),
            latest_source=str(payload.get("latest_source", "") or ""),
            queue_depth=None if payload.get("queue_depth") is None else int(payload.get("queue_depth")),
            percent=None if payload.get("percent") is None else int(payload.get("percent")),
            eta_text=payload.get("eta_text"),
            updated_at=str(payload.get("updated_at") or utc_now_iso()),
            message=str(payload.get("message", "") or ""),
        )


def catalog_job_dir(catalog_path: Path | str) -> Path:
    return Path(catalog_path).parent / "catalog_jobs"


def catalog_job_state_path(catalog_path: Path | str, job_id: str) -> Path:
    return catalog_job_dir(catalog_path) / f"{job_id}.json"


def catalog_job_lock_path(catalog_path: Path | str) -> Path:
    return Path(catalog_path).with_suffix(Path(catalog_path).suffix + ".lock")


def latest_catalog_job_state(catalog_path: Path | str) -> CatalogJobProgress | None:
    directory = catalog_job_dir(catalog_path)
    if not directory.exists():
        return None
    latest: tuple[float, Path] | None = None
    for path in directory.glob("*.json"):
        try:
            stamp = path.stat().st_mtime
        except OSError:
            continue
        if latest is None or stamp > latest[0]:
            latest = (stamp, path)
    if latest is None:
        return None
    try:
        payload = json.loads(latest[1].read_text(encoding="utf-8"))
        progress = payload.get("progress", payload)
        return CatalogJobProgress.from_dict(dict(progress))
    except (OSError, json.JSONDecodeError, ValueError):
        return None


class CatalogJobRunner:
    """Run one catalog build/update/resume job with checkpointed progress and a writer lock."""

    def __init__(self, spec: CatalogJobSpec, *, progress_callback: Callable[[CatalogJobProgress], None] | None = None, pause_callback: Callable[[], bool] | None = None) -> None:
        self.spec = spec
        self.progress_callback = progress_callback
        self.pause_callback = pause_callback
        self.started = time.monotonic()
        self.state_path = catalog_job_state_path(spec.catalog_path, spec.job_id)
        self.lock_path = catalog_job_lock_path(spec.catalog_path)
        self._last_progress: CatalogJobProgress | None = None

    def run(self) -> LidarCatalogBuildResult:
        self._acquire_lock()
        try:
            self._emit(CatalogJobStatus.RUNNING, CatalogJobStage.PREPARING, message="Preparing catalog job.", percent=5)
            result = build_lidar_catalog(
                self.spec.root_path,
                self.spec.catalog_path,
                options=self.spec.options,
                progress_callback=self._on_builder_progress,
                cancel_callback=self._pause_requested,
            )
            if result.cancelled:
                self._emit(CatalogJobStatus.INTERRUPTED, CatalogJobStage.FINALIZING, discovered=result.discovered_count, indexed=result.indexed_count, unchanged=result.unchanged_count, errors=result.error_count, deleted=result.deleted_count, message="Catalog job paused after current chunk.", percent=None)
            else:
                self._emit(CatalogJobStatus.COMPLETED, CatalogJobStage.READY, discovered=result.discovered_count, indexed=result.indexed_count, unchanged=result.unchanged_count, errors=result.error_count, deleted=result.deleted_count, message="Catalog ready.", percent=100)
            return result
        except Exception as exc:  # noqa: BLE001 - durable state should record failures.
            self._emit(CatalogJobStatus.FAILED, CatalogJobStage.FINALIZING, message=str(exc), percent=None)
            raise
        finally:
            self._release_lock()

    def _on_builder_progress(self, payload: dict[str, int | str]) -> None:
        status = CatalogJobStatus.RUNNING
        stage = CatalogJobStage(str(payload.get("stage", CatalogJobStage.READING_METADATA.value)))
        discovered = int(payload.get("discovered", 0) or 0)
        elapsed = max(0.001, time.monotonic() - self.started)
        rate = discovered / elapsed if discovered else None
        eta = None
        if rate is not None and discovered >= 10_000:
            eta = "Estimated time remaining: pending total repository size."
        self._emit(
            status,
            stage,
            discovered=discovered,
            indexed=int(payload.get("indexed", 0) or 0),
            unchanged=int(payload.get("unchanged", 0) or 0),
            errors=int(payload.get("errors", 0) or 0),
            deleted=int(payload.get("deleted", 0) or 0),
            latest_source=str(payload.get("latest_source", "") or "")[-160:],
            rate_per_second=rate,
            eta_text=eta,
            percent=stage_percent(stage, total_known=False),
            message="Catalog discovery/indexing in progress.",
        )

    def _pause_requested(self) -> bool:
        return bool(self.pause_callback and self.pause_callback())

    def _emit(self, status: CatalogJobStatus, stage: CatalogJobStage, *, discovered: int = 0, indexed: int = 0, unchanged: int = 0, errors: int = 0, deleted: int = 0, latest_source: str = "", rate_per_second: float | None = None, eta_text: str | None = None, percent: int | None = None, message: str = "") -> CatalogJobProgress:
        if self._last_progress is not None:
            discovered = discovered or self._last_progress.discovered
            indexed = indexed or self._last_progress.indexed
            unchanged = unchanged or self._last_progress.unchanged
            errors = errors or self._last_progress.errors
            deleted = deleted or self._last_progress.deleted
            latest_source = latest_source or self._last_progress.latest_source
            rate_per_second = rate_per_second if rate_per_second is not None else self._last_progress.rate_per_second
        progress = CatalogJobProgress(
            job_id=self.spec.job_id,
            status=status,
            stage=stage,
            discovered=discovered,
            indexed=indexed,
            unchanged=unchanged,
            errors=errors,
            deleted=deleted,
            elapsed_seconds=time.monotonic() - self.started,
            rate_per_second=rate_per_second,
            latest_source=latest_source,
            queue_depth=None,
            percent=percent,
            eta_text=eta_text,
            message=message,
        )
        self._last_progress = progress
        self._write_state(progress)
        if self.progress_callback is not None:
            self.progress_callback(progress)
        return progress

    def _write_state(self, progress: CatalogJobProgress) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"spec": self.spec.to_dict(), "progress": progress.to_dict()}
        self.state_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    def _acquire_lock(self) -> None:
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            handle = self.lock_path.open("x", encoding="utf-8")
        except FileExistsError as exc:
            raise RuntimeError(f"Another catalog write job is already active for {self.spec.catalog_path}.") from exc
        with handle:
            handle.write(json.dumps({"job_id": self.spec.job_id, "created_at": utc_now_iso()}) + "\n")

    def _release_lock(self) -> None:
        try:
            self.lock_path.unlink()
        except FileNotFoundError:
            pass


def stage_percent(stage: CatalogJobStage, *, total_known: bool = False) -> int | None:
    if stage is CatalogJobStage.PREPARING:
        return 5
    if stage in {CatalogJobStage.DISCOVERING, CatalogJobStage.READING_METADATA, CatalogJobStage.WRITING_INDEX}:
        return None if not total_known else 50
    if stage is CatalogJobStage.DETECTING_DELETED:
        return 88
    if stage is CatalogJobStage.VERIFYING:
        return 94
    if stage is CatalogJobStage.FINALIZING:
        return 98
    if stage is CatalogJobStage.READY:
        return 100
    return None


def _options_to_dict(options: CatalogBuildOptions) -> dict[str, object]:
    return {
        "recursive": options.recursive,
        "include_globs": list(options.include_globs),
        "exclude_globs": list(options.exclude_globs),
        "max_depth": options.max_depth,
        "max_source_files": options.max_source_files,
        "source_types": list(options.source_types),
        "ignore_hidden": options.ignore_hidden,
        "ignore_names": list(options.ignore_names),
        "thresholds": asdict(options.thresholds),
    }


def _options_from_dict(payload: dict[str, object]) -> CatalogBuildOptions:
    from .lidar_catalog_models import CatalogThresholds

    thresholds_payload = dict(payload.get("thresholds", {}) or {})
    thresholds = CatalogThresholds(**{key: value for key, value in thresholds_payload.items() if key in CatalogThresholds.__dataclass_fields__})
    return CatalogBuildOptions(
        recursive=bool(payload.get("recursive", True)),
        include_globs=tuple(str(item) for item in payload.get("include_globs", ()) or ()),
        exclude_globs=tuple(str(item) for item in payload.get("exclude_globs", ()) or ()),
        max_depth=None if payload.get("max_depth") is None else int(payload["max_depth"]),
        max_source_files=None if payload.get("max_source_files") is None else int(payload["max_source_files"]),
        source_types=tuple(str(item) for item in payload.get("source_types", ()) or ()),
        ignore_hidden=bool(payload.get("ignore_hidden", True)),
        ignore_names=tuple(str(item) for item in payload.get("ignore_names", ()) or ()),
        thresholds=thresholds,
    )
