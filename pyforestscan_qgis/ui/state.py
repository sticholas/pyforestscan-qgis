"""Plain-Python Mission Control state models."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Iterable

from ..core.jobs import JobRecord
from ..core.workspace import RunContext


SESSION_PRODUCT_LABELS: tuple[tuple[str, str], ...] = (
    ("dtm", "DTM"),
    ("chm", "CHM"),
    ("canopy_cover", "Canopy Cover"),
    ("pad", "PAD"),
    ("pai", "PAI"),
    ("fhd", "FHD"),
    ("rumple", "Rumple"),
    ("point_density", "Point Density"),
    ("voxel_stat", "Voxel Statistic"),
)

RESULT_TYPE_TO_PRODUCT: dict[str, str] = {
    "dtm_geotiff": "dtm",
    "chm_geotiff": "chm",
    "canopy_cover_geotiff": "canopy_cover",
    "pad_geotiff": "pad",
    "pai_geotiff": "pai",
    "fhd_geotiff": "fhd",
    "rumple_csv": "rumple",
    "point_density_geotiff": "point_density",
    "voxel_stat_geotiff": "voxel_stat",
}

SUMMARY_RESULT_TYPES = frozenset({"job_summary_json", "job_summary_html"})


@dataclass(frozen=True)
class MissionActivity:
    """One Mission Control activity entry."""

    label: str
    detail: str = ""


@dataclass(frozen=True)
class ProductSessionStatus:
    """Generated/loaded state for one product in the active Mission Control session."""

    product: str
    label: str
    generated_paths: tuple[Path, ...] = ()
    loaded_paths: tuple[Path, ...] = ()
    requested: bool = False

    @property
    def generated(self) -> bool:
        """Return whether the session has generated this product."""
        return bool(self.generated_paths)

    @property
    def loaded(self) -> bool:
        """Return whether at least one generated output is loaded into QGIS."""
        return bool(self.loaded_paths)

    @property
    def load_state(self) -> str:
        """Return the compact user-facing load state."""
        if self.loaded:
            return "Loaded"
        if self.generated:
            return "Generated"
        if self.requested:
            return "Missing"
        return "Unavailable"

    def summary_line(self) -> str:
        """Return a compact status line for Results and Processing pages."""
        if self.loaded:
            return f"{self.label}: Generated, Loaded"
        if self.generated:
            return f"{self.label}: Generated, Not Loaded"
        if self.requested:
            return f"{self.label}: Missing"
        return f"{self.label}: Unavailable"


@dataclass(frozen=True)
class ProjectSummary:
    """Shared current-session summary used by Mission Control pages."""

    dataset_path: str | None = None
    dataset_type: str = "Unknown"
    workspace: str | None = None
    output_folder: Path | None = None
    product_statuses: tuple[ProductSessionStatus, ...] = ()
    processing_state: str = "Not started"
    backend_state: str = "Unknown"
    environment_state: str = "Unknown"
    last_processing_time: str | None = None
    project_crs: str | None = None

    @property
    def dataset_name(self) -> str:
        """Return the current dataset file name or a neutral fallback."""
        return Path(self.dataset_path).name if self.dataset_path else "Not selected"

    @property
    def generated_products(self) -> tuple[ProductSessionStatus, ...]:
        """Return products generated during the active session."""
        return tuple(item for item in self.product_statuses if item.generated)

    @property
    def loaded_products(self) -> tuple[ProductSessionStatus, ...]:
        """Return generated products already loaded into QGIS."""
        return tuple(item for item in self.product_statuses if item.loaded)

    @property
    def available_products(self) -> tuple[ProductSessionStatus, ...]:
        """Return generated products not yet loaded into QGIS."""
        return tuple(item for item in self.product_statuses if item.generated and not item.loaded)

    @property
    def missing_products(self) -> tuple[ProductSessionStatus, ...]:
        """Return requested products that do not currently have generated outputs."""
        return tuple(item for item in self.product_statuses if item.load_state == "Missing")

    def generated_summary(self) -> str:
        """Return a compact generated-products summary."""
        if not self.generated_products:
            return "Products generated: None"
        return "Products generated: " + ", ".join(item.label for item in self.generated_products)

    def loaded_summary(self) -> str:
        """Return a compact loaded-products summary."""
        if not self.loaded_products:
            return "Products loaded: None"
        return "Products loaded: " + ", ".join(item.label for item in self.loaded_products)

    def product_status_lines(self) -> tuple[str, ...]:
        """Return stable product/load status lines."""
        return tuple(item.summary_line() for item in self.product_statuses)

    def compact_status(self) -> str:
        """Return the compact session status shown on Workspace."""
        if self.processing_state not in {"Not started", "completed"}:
            return f"Processing: {self.processing_state}"
        if self.generated_products:
            return "Session: outputs generated"
        if self.dataset_path:
            return "Session: dataset selected"
        return "Session: not started"

    @classmethod
    def from_state(
        cls,
        state: "MissionControlState",
        jobs: Iterable[JobRecord] = (),
        loaded_paths: Iterable[Path] = (),
        workspace: str | None = None,
        project_crs: str | None = None,
    ) -> "ProjectSummary":
        """Build a shared project summary from current in-memory Mission Control state."""
        jobs_tuple = tuple(jobs)
        generated: dict[str, list[Path]] = {key: [] for key, _label in SESSION_PRODUCT_LABELS}
        requested: set[str] = set()
        for job in jobs_tuple:
            requested.update(_normalize_product_key(product) for product in job.requested_products)
            for result in job.results:
                product = product_key_from_result_type(result.result_type)
                if product and result.result_type not in SUMMARY_RESULT_TYPES:
                    generated.setdefault(product, []).append(result.path)
        loaded = {_normalize_path(path) for path in loaded_paths}
        statuses: list[ProductSessionStatus] = []
        for product, label in SESSION_PRODUCT_LABELS:
            paths = tuple(_dedupe_paths(generated.get(product, ())))
            loaded_for_product = tuple(path for path in paths if _normalize_path(path) in loaded)
            statuses.append(
                ProductSessionStatus(
                    product=product,
                    label=label,
                    generated_paths=paths,
                    loaded_paths=loaded_for_product,
                    requested=product in requested,
                )
            )
        latest_job = jobs_tuple[0] if jobs_tuple else None
        last_processing_time = None
        if latest_job is not None and latest_job.status.value in {"completed", "failed", "cancelled"}:
            last_processing_time = latest_job.updated_at
        output_folder = state.active_run.outputs_dir if state.active_run is not None else state.default_output_folder
        return cls(
            dataset_path=state.latest_dataset,
            dataset_type=dataset_type_label(state.latest_dataset),
            workspace=workspace,
            output_folder=output_folder,
            product_statuses=tuple(statuses),
            processing_state=latest_job.status.value if latest_job is not None else "Not started",
            backend_state=state.backend_status,
            environment_state=state.environment_status,
            last_processing_time=last_processing_time,
            project_crs=project_crs,
        )


@dataclass(frozen=True)
class MissionControlState:
    """Snapshot of Mission Control workflow state independent of QGIS widgets."""

    environment_status: str = "Unknown"
    backend_status: str = "Unknown"
    latest_dataset: str | None = None
    latest_project: str | None = None
    latest_report_paths: tuple[Path, ...] = ()
    planning_status: str = "Not started"
    default_output_folder: Path | None = None
    active_run: RunContext | None = None
    activities: tuple[MissionActivity, ...] = field(default_factory=tuple)

    def with_activity(self, label: str, detail: str = "", limit: int = 8) -> "MissionControlState":
        """Return a new state with a recent activity prepended."""
        next_activities = (MissionActivity(label, detail),) + self.activities
        return replace(self, activities=next_activities[:limit])

    def with_environment(self, status: str) -> "MissionControlState":
        """Return a new state with environment status changed."""
        return replace(self, environment_status=status)

    def with_backend(self, status: str) -> "MissionControlState":
        """Return a new state with backend status changed."""
        return replace(self, backend_status=status)

    def with_dataset(self, dataset: str) -> "MissionControlState":
        """Return a new state with latest dataset changed."""
        return replace(self, latest_dataset=dataset)

    def with_dataset_pending(self, dataset: str) -> "MissionControlState":
        """Return a state for a newly selected dataset before analysis completes."""
        return replace(
            self,
            latest_dataset=dataset,
            latest_project=None,
            latest_report_paths=(),
            planning_status="Not started",
            active_run=None,
        )

    def without_active_run(self) -> "MissionControlState":
        """Return a state with downstream run outputs cleared."""
        return replace(
            self,
            latest_project=None,
            latest_report_paths=(),
            planning_status="Not started",
            active_run=None,
        )

    def with_planning(self, status: str) -> "MissionControlState":
        """Return a new state with planning status changed."""
        return replace(self, planning_status=status)

    def with_report_path(self, path: Path) -> "MissionControlState":
        """Return a new state with a report path recorded."""
        paths = (path,) + tuple(existing for existing in self.latest_report_paths if existing != path)
        return replace(self, latest_report_paths=paths[:10])

    def with_default_output_folder(self, folder: Path | None) -> "MissionControlState":
        """Return a new state with the default output folder changed."""
        return replace(self, default_output_folder=folder)

    def with_active_run(self, context: RunContext) -> "MissionControlState":
        """Return a new state with the active run context changed."""
        return replace(
            self,
            latest_dataset=str(context.lidar_path),
            latest_project=str(context.run_folder),
            active_run=context,
        )


def build_project_summary(
    state: MissionControlState,
    jobs: Iterable[JobRecord] = (),
    loaded_paths: Iterable[Path] = (),
    workspace: str | None = None,
    project_crs: str | None = None,
) -> ProjectSummary:
    """Return the shared Mission Control project summary."""
    return ProjectSummary.from_state(state, jobs, loaded_paths, workspace, project_crs)


def product_key_from_result_type(result_type: str) -> str | None:
    """Map a job result type to a session product key."""
    return RESULT_TYPE_TO_PRODUCT.get(result_type)


def dataset_type_label(dataset_path: str | None) -> str:
    """Infer a compact dataset type label from the current dataset path."""
    if not dataset_path:
        return "Unknown"
    path = Path(dataset_path)
    lower_name = path.name.lower()
    suffix = path.suffix.lower()
    if lower_name == "ept.json":
        return "EPT"
    if lower_name.endswith(".copc.laz") or suffix == ".copc":
        return "COPC"
    if suffix == ".las":
        return "LAS"
    if suffix == ".laz":
        return "LAZ"
    return suffix.lstrip(".").upper() or "Unknown"


def _normalize_product_key(value: object) -> str:
    text = getattr(value, "value", value)
    return str(text).strip().lower()


def _normalize_path(path: Path | str) -> str:
    text = str(path).split("|", 1)[0]
    try:
        return str(Path(text).expanduser().resolve()).casefold()
    except OSError:
        return str(Path(text).expanduser()).casefold()


def _dedupe_paths(paths: Iterable[Path]) -> tuple[Path, ...]:
    seen: set[str] = set()
    output: list[Path] = []
    for raw_path in paths:
        path = Path(raw_path)
        key = _normalize_path(path)
        if key not in seen:
            seen.add(key)
            output.append(path)
    return tuple(output)
