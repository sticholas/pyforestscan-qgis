"""Pipeline execution context."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping


class PipelineContextError(ValueError):
    """Raised when a pipeline context cannot be created."""


@dataclass(frozen=True)
class PipelineContext:
    """Immutable context shared by pipeline steps."""

    product: str
    product_label: str
    product_plan_path: Path
    output_folder: Path
    product_plan: Mapping[str, Any]
    product_entry: Mapping[str, Any]
    dataset_report: Mapping[str, Any] | None = None

    @property
    def source_dataset(self) -> str | None:
        """Return the source dataset recorded by Product Planner."""
        value = self.product_plan.get("source_dataset")
        return str(value) if value else None

    @property
    def source_report_path(self) -> Path | None:
        """Return the Dataset Explorer JSON path recorded by Product Planner."""
        value = self.product_plan.get("source_report")
        return Path(str(value)) if value else None

    @property
    def grid_resolution(self) -> float:
        """Return the planned grid resolution."""
        parameters = self.product_plan.get("parameters")
        if isinstance(parameters, Mapping):
            value = parameters.get("grid_resolution", 1.0)
        else:
            value = 1.0
        return float(value)


    @property
    def chm_interpolation(self) -> str:
        """Return the planned CHM interpolation method."""
        return str(self._parameter("chm_interpolation", "linear"))

    @property
    def chm_interpolate_valid_region(self) -> bool:
        """Return whether CHM valid-region interpolation is enabled."""
        return bool(self._parameter("chm_interpolate_valid_region", False))

    @property
    def chm_clean_edges(self) -> bool:
        """Return whether CHM edge cleanup is enabled."""
        return bool(self._parameter("chm_clean_edges", False))

    @property
    def chm_output_filename(self) -> str:
        """Return the planned CHM output filename."""
        value = str(self._parameter("chm_output_filename", "chm.tif"))
        return value or "chm.tif"



    @property
    def voxel_height(self) -> float:
        """Return the planned voxel height / height bin size."""
        value = self._parameter("height_bin_size", 1.0)
        return float(value) if value is not None else 1.0

    @property
    def pad_output_filename(self) -> str:
        """Return the planned PAD output filename."""
        value = str(self._parameter("pad_output_filename", "pad.tif"))
        return value or "pad.tif"

    @property
    def pai_output_filename(self) -> str:
        """Return the planned PAI output filename."""
        value = str(self._parameter("pai_output_filename", "pai.tif"))
        return value or "pai.tif"


    @property
    def fhd_output_filename(self) -> str:
        """Return the planned FHD output filename."""
        value = str(self._parameter("fhd_output_filename", "fhd.tif"))
        return value or "fhd.tif"

    @property
    def rumple_output_filename(self) -> str:
        """Return the planned rumple output filename."""
        value = str(self._parameter("rumple_output_filename", "rumple.tif"))
        return value or "rumple.tif"

    @property
    def canopy_cover_height_threshold(self) -> float:
        """Return the planned canopy cover height threshold."""
        return float(self._parameter("canopy_cover_height_threshold", 2.0))

    @property
    def canopy_cover_output_filename(self) -> str:
        """Return the planned canopy cover output filename."""
        value = str(self._parameter("canopy_cover_output_filename", "canopy_cover.tif"))
        return value or "canopy_cover.tif"

    @property
    def parameters(self) -> dict[str, object]:
        """Return user-selected execution parameters for summary output."""
        raw = self.product_plan.get("parameters")
        return dict(raw) if isinstance(raw, Mapping) else {}

    def _parameter(self, name: str, default: object) -> object:
        parameters = self.product_plan.get("parameters")
        if isinstance(parameters, Mapping):
            return parameters.get(name, default)
        return default

    @property
    def crs(self) -> str | None:
        """Return the dataset CRS from Dataset Explorer JSON when available."""
        if self.dataset_report is None:
            return None
        geometry = self.dataset_report.get("geometry")
        if not isinstance(geometry, Mapping):
            return None
        value = geometry.get("crs")
        return str(value) if value else None

    @property
    def hag_method(self) -> str:
        """Prefer an existing normalized-height dimension when reported."""
        if self.dataset_report is None:
            return "classified_ground_delaunay"
        raw = self.dataset_report.get("dimensions", ())
        names: set[str] = set()
        if isinstance(raw, (list, tuple)):
            for item in raw:
                if isinstance(item, str):
                    names.add(item.casefold())
                elif isinstance(item, Mapping):
                    names.add(str(item.get("name", "")).casefold())
        return "existing_normalized_height" if "heightaboveground" in names else "classified_ground_delaunay"


def load_pipeline_contexts(product_plan_path: Path | str, output_folder: Path | str) -> tuple[PipelineContext, ...]:
    """Load one pipeline context per requested product from Product Planner JSON."""
    plan_path = Path(product_plan_path)
    try:
        payload = json.loads(plan_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise PipelineContextError(f"Could not read Product Planner JSON: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise PipelineContextError(f"Product Planner JSON is not valid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise PipelineContextError("Product Planner JSON must contain an object at the top level.")
    dataset_report = _load_dataset_report(payload)
    products = payload.get("products")
    if not isinstance(products, list) or not products:
        raise PipelineContextError("Product plan must contain requested products.")
    contexts = []
    for entry in products:
        if not isinstance(entry, dict) or entry.get("requested") is not True:
            continue
        product = entry.get("product")
        if not isinstance(product, str) or not product:
            raise PipelineContextError("Each requested product must include a product identifier.")
        contexts.append(
            PipelineContext(
                product=product,
                product_label=str(entry.get("label") or product),
                product_plan_path=plan_path,
                output_folder=_planned_output_folder(payload, output_folder),
                product_plan=payload,
                product_entry=entry,
                dataset_report=dataset_report,
            )
        )
    if not contexts:
        raise PipelineContextError("Product plan does not contain any requested products.")
    return tuple(contexts)


def _load_dataset_report(product_plan: Mapping[str, Any]) -> Mapping[str, Any] | None:
    value = product_plan.get("source_report")
    if not value:
        return None
    path = Path(str(value))
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _planned_output_folder(product_plan: Mapping[str, Any], fallback: Path | str) -> Path:
    value = product_plan.get("output_folder")
    return Path(str(value)) if value else Path(fallback)
