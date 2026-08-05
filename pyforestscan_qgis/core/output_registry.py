"""Shared generated-output registry for Mission Control workflows."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

REGISTRY_NAME = "generated_outputs.json"
RASTER_SUFFIXES = {".tif", ".tiff"}
TABLE_SUFFIXES = {".csv"}


@dataclass(frozen=True)
class GeneratedOutput:
    output_id: str
    job_id: str
    attempt_id: str
    product_key: str
    product_name: str
    output_kind: str
    path: Path
    canonical_path: str
    exists: bool
    valid: bool
    complete: bool
    masked: bool = False
    mask_geometry_id: str = ""
    source_mode: str = ""
    crs: str = ""
    bounds: str = ""
    nodata: str = ""
    raster_band_count: int | None = None
    display_role: str = ""
    recommended_renderer: str = ""
    metadata_path: Path | None = None
    checksum: str = ""
    generated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    loaded_into_qgis: bool = False
    qgis_layer_id: str = ""
    load_error: str = ""
    group_name: str = "PyForestScan"
    project_identity: str = ""
    plan_signature: str = ""
    repository_path_hash: str = ""
    polygon_geometry_hash: str = ""
    final_output: bool = True

    def to_dict(self) -> dict[str, Any]:
        payload = dict(self.__dict__)
        payload["path"] = str(self.path)
        payload["metadata_path"] = str(self.metadata_path) if self.metadata_path is not None else None
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "GeneratedOutput":
        data = dict(payload)
        data["path"] = Path(data["path"])
        data["metadata_path"] = Path(data["metadata_path"]) if data.get("metadata_path") else None
        return cls(**data)


def generated_output_for_path(
    path: Path | str,
    *,
    job_id: str,
    product_key: str | None = None,
    source_mode: str = "",
    masked: bool = False,
    mask_geometry_id: str = "",
    group_name: str = "PyForestScan",
    attempt_id: str = "attempt-1",
    project_identity: str = "",
    plan_signature: str = "",
    repository_path_hash: str = "",
    polygon_geometry_hash: str = "",
) -> GeneratedOutput:
    output_path = Path(path)
    canonical = _canonical_path(output_path)
    inferred = product_key or _infer_product_key(output_path)
    suffix = output_path.suffix.lower()
    kind = "raster" if suffix in RASTER_SUFFIXES else ("table" if suffix in TABLE_SUFFIXES else "file")
    return GeneratedOutput(
        output_id=hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16],
        job_id=job_id,
        attempt_id=attempt_id,
        product_key=inferred,
        product_name=_product_name(inferred),
        output_kind=kind,
        path=output_path,
        canonical_path=canonical,
        exists=output_path.exists(),
        valid=output_path.exists() and output_path.is_file(),
        complete=output_path.exists() and output_path.is_file(),
        masked=masked,
        mask_geometry_id=mask_geometry_id,
        source_mode=source_mode,
        display_role=_display_role(inferred, kind),
        recommended_renderer=_renderer(inferred, kind),
        group_name=group_name,
        project_identity=project_identity,
        plan_signature=plan_signature,
        repository_path_hash=repository_path_hash,
        polygon_geometry_hash=polygon_geometry_hash,
    )


def write_output_registry(outputs: Iterable[GeneratedOutput], folder: Path | str) -> Path:
    path = Path(folder) / REGISTRY_NAME
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"schema": "phase27m-generated-output-v1", "outputs": [item.to_dict() for item in outputs]}
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def read_output_registry(path: Path | str) -> tuple[GeneratedOutput, ...]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return tuple(GeneratedOutput.from_dict(item) for item in payload.get("outputs", ()))


def registry_paths(folder: Path | str) -> tuple[Path, ...]:
    root = Path(folder)
    if not root.exists():
        return ()
    return tuple(sorted(root.rglob(REGISTRY_NAME)))


def _canonical_path(path: Path) -> str:
    try:
        return str(path.expanduser().resolve()).casefold()
    except OSError:
        return str(path.expanduser()).casefold()


def _infer_product_key(path: Path) -> str:
    stem = path.stem.lower()
    if "canopy_cover" in stem:
        return "canopy_cover"
    if "point_density" in stem:
        return "point_density"
    if "voxel" in stem:
        return "voxel_stat"
    for key in ("chm", "dtm", "pad", "pai", "fhd", "rumple"):
        if stem == key or key in stem:
            return key
    return "output"


def _product_name(key: str) -> str:
    return {
        "chm": "Canopy Height Model",
        "dtm": "DTM",
        "pad": "PAD",
        "pai": "PAI",
        "fhd": "FHD",
        "canopy_cover": "Canopy Cover",
        "rumple": "Rumple",
        "point_density": "Point Density",
        "voxel_stat": "Voxel Statistic",
    }.get(key, key.replace("_", " ").title())


def _display_role(key: str, kind: str) -> str:
    if kind == "table":
        return "table"
    return "multiband_raster" if key == "pad" else "raster"


def _renderer(key: str, kind: str) -> str:
    if kind == "table":
        return "table"
    if key == "pad":
        return "pad_rgb_5_3_2"
    return "grayscale"


def outputs_for_current_attempt(outputs: Iterable[GeneratedOutput], *, job_id: str, attempt_id: str, project_identity: str = "", plan_signature: str = "", polygon_geometry_hash: str = "") -> tuple[GeneratedOutput, ...]:
    """Return only valid final records emitted for the active attempt."""
    selected=[]
    for item in outputs:
        if item.job_id != job_id or item.attempt_id != attempt_id or not item.final_output or not item.valid or not item.complete:
            continue
        if project_identity and item.project_identity != project_identity: continue
        if plan_signature and item.plan_signature != plan_signature: continue
        if polygon_geometry_hash and item.polygon_geometry_hash != polygon_geometry_hash: continue
        selected.append(item)
    return tuple(selected)

def automatic_load_paths(outputs: Iterable[GeneratedOutput], **identity) -> tuple[Path, ...]:
    """Never scan folders; load only current-attempt registry records."""
    return tuple(item.path for item in outputs_for_current_attempt(outputs, **identity))
