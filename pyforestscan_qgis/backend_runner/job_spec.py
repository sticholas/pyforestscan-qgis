"""Serializable PBM processing job specifications."""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, fields, is_dataclass
from pathlib import Path
from typing import Any

from pyforestscan_qgis.core.ept_bounds import EptBounds, EptBoundsError

try:
    from pyforestscan_qgis import __version__
except Exception:  # pragma: no cover - backend runner may be imported from source checkouts.
    __version__ = None  # type: ignore[assignment]


@dataclass(frozen=True)
class BackendJobSpec:
    """One managed backend processing job."""

    job_id: str
    input_lidar_path: Path
    crs: str
    run_folder: Path
    product: str
    product_parameters: dict[str, Any]
    output_paths: dict[str, Path]
    result_path: Path
    hag_options: dict[str, Any] | None = None
    dtm_path: Path | None = None
    plugin_version: str = "unknown"
    protocol_version: str = "1"

    def to_dict(self) -> dict[str, Any]:
        """Serialize to JSON-compatible values."""
        return {
            "job_id": self.job_id,
            "input_lidar_path": str(self.input_lidar_path),
            "crs": self.crs,
            "run_folder": str(self.run_folder),
            "product": self.product,
            "product_parameters": _json_ready(self.product_parameters),
            "output_paths": {key: str(value) for key, value in self.output_paths.items()},
            "result_path": str(self.result_path),
            "hag_options": _json_ready(self.hag_options or {}),
            "dtm_path": str(self.dtm_path) if self.dtm_path is not None else None,
            "plugin_version": self.plugin_version,
            "protocol_version": self.protocol_version,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BackendJobSpec":
        """Deserialize from JSON-compatible values."""
        return cls(
            job_id=str(data["job_id"]),
            input_lidar_path=Path(data["input_lidar_path"]),
            crs=str(data.get("crs", "")),
            run_folder=Path(data["run_folder"]),
            product=str(data["product"]),
            product_parameters=dict(data.get("product_parameters", {})),
            output_paths={str(key): Path(value) for key, value in dict(data.get("output_paths", {})).items()},
            result_path=Path(data["result_path"]),
            hag_options=dict(data.get("hag_options", {})) or None,
            dtm_path=Path(data["dtm_path"]) if data.get("dtm_path") else None,
            plugin_version=str(data.get("plugin_version", "unknown")),
            protocol_version=str(data.get("protocol_version", "1")),
        )

    def write(self, path: Path | None = None) -> Path:
        """Write the spec JSON and return the path."""
        target = path or self.run_folder / ".pbm_jobs" / f"{self.job_id}.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(self.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return target

    @classmethod
    def read(cls, path: Path) -> "BackendJobSpec":
        """Read a spec JSON file."""
        return cls.from_dict(json.loads(path.read_text(encoding="utf-8")))


def build_job_spec_from_request(product: str, request: Any, run_folder: Path | None = None, job_id: str | None = None) -> BackendJobSpec:
    """Build a backend job spec from an adapter request dataclass."""
    if not is_dataclass(request):
        raise TypeError("PBM backend jobs require dataclass adapter requests.")
    params = _json_ready(asdict(request))
    _normalize_ept_bounds_parameters(params)
    input_path = Path(str(params.get("input_path", "")))
    output_path = Path(str(params.get("output_path", "")))
    crs = str(params.get("crs", ""))
    folder = Path(run_folder) if run_folder is not None else _default_run_folder_for_request(params, output_path)
    identifier = job_id or f"pbm-{product}-{uuid.uuid4().hex[:12]}"
    result_path = folder / ".pbm_jobs" / f"{identifier}.result.json"
    output_paths = {"primary": output_path}
    if params.get("dtm_path"):
        dtm_path = Path(str(params["dtm_path"]))
    else:
        dtm_path = None
    request_fields = {field.name for field in fields(request)}
    hag_options = {
        key: params[key]
        for key in ("use_dtm", "hag", "hag_dtm", "dtm_path", "reproject", "bounds", "thin_radius", "crop_polygon", "crop_polygon_path", "polygon_execution_input", "crop_poly", "poly")
        if key in request_fields
    }
    version = getattr(__version__, "full_version", lambda: "unknown")() if __version__ is not None else "unknown"
    return BackendJobSpec(
        job_id=identifier,
        input_lidar_path=input_path,
        crs=crs,
        run_folder=folder,
        product=product,
        product_parameters=params,
        output_paths=output_paths,
        result_path=result_path,
        hag_options=hag_options or None,
        dtm_path=dtm_path,
        plugin_version=version,
    )


def _normalize_ept_bounds_parameters(params: dict[str, Any]) -> None:
    """Store EPT bounds as a typed manifest object across the PBM boundary."""
    bounds = params.get("bounds")
    crs = str(params.get("crs") or "")
    if bounds is None or not crs:
        return
    try:
        model = EptBounds.from_value(bounds, crs=crs, source="polygon_envelope", transformed=True)
    except EptBoundsError:
        return
    params["ept_bounds"] = model.to_json()
    params["pdal_bounds_expression"] = model.to_pdal_range_string()


def _default_run_folder_for_request(params: dict[str, Any], output_path: Path) -> Path:
    """Return the durable PBM job workspace for a request."""
    parent = output_path.parent
    if params.get("polygon_execution_input") and parent.name == "outputs":
        return parent.parent
    return parent


def _json_ready(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, tuple):
        return [_json_ready(item) for item in value]
    if isinstance(value, list):
        return [_json_ready(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _json_ready(item) for key, item in value.items()}
    return value
