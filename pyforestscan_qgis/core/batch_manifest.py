"""Durable batch manifest and resume helpers."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .batch import BatchItemResult, BatchRequest, batch_run_context
from .types import ProductType

MANIFEST_NAME = "batch_manifest.json"


@dataclass(frozen=True)
class BatchManifestItem:
    """Durable status for one dataset in a batch."""

    dataset_path: Path
    run_folder: Path
    status: str
    job_id: str
    message: str = ""
    outputs: tuple[Path, ...] = ()


@dataclass(frozen=True)
class BatchManifest:
    """Durable manifest for a resumable batch."""

    batch_id: str
    batch_folder: Path
    created_at: str
    updated_at: str
    execution_mode: str
    max_workers: int
    products: tuple[ProductType, ...]
    items: tuple[BatchManifestItem, ...]

    @property
    def path(self) -> Path:
        """Return the manifest path."""
        return self.batch_folder / MANIFEST_NAME


def create_manifest(request: BatchRequest, batch_folder: Path) -> BatchManifest:
    """Create a manifest for the requested batch datasets."""
    now = _now()
    return BatchManifest(
        batch_id=f"pfs-batch-{uuid.uuid4().hex[:10]}",
        batch_folder=batch_folder,
        created_at=now,
        updated_at=now,
        execution_mode=request.settings.execution_mode,
        max_workers=request.settings.max_workers,
        products=request.settings.products,
        items=tuple(
            BatchManifestItem(
                dataset_path=Path(dataset),
                run_folder=batch_run_context(dataset, batch_folder, reuse_existing=True).run_folder,
                status="pending",
                job_id=f"pfs-file-{uuid.uuid4().hex[:10]}",
            )
            for dataset in request.datasets
        ),
    )


def load_manifest(path: Path | str) -> BatchManifest:
    """Load a batch manifest from JSON."""
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    items = tuple(
        BatchManifestItem(
            dataset_path=Path(item["dataset_path"]),
            run_folder=Path(item["run_folder"]),
            status=str(item.get("status", "pending")),
            job_id=str(item.get("job_id", "")),
            message=str(item.get("message", "")),
            outputs=tuple(Path(value) for value in item.get("outputs", [])),
        )
        for item in payload.get("items", [])
    )
    return BatchManifest(
        batch_id=str(payload["batch_id"]),
        batch_folder=Path(payload["batch_folder"]),
        created_at=str(payload.get("created_at", "")),
        updated_at=str(payload.get("updated_at", "")),
        execution_mode=str(payload.get("execution_mode", "sequential")),
        max_workers=int(payload.get("max_workers", 1)),
        products=tuple(ProductType(value) for value in payload.get("products", [])),
        items=items,
    )


def write_manifest(manifest: BatchManifest, path: Path | str | None = None) -> Path:
    """Write a batch manifest as stable JSON."""
    output = Path(path) if path is not None else manifest.path
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(manifest_to_dict(manifest), indent=2), encoding="utf-8")
    return output


def update_manifest_item(manifest: BatchManifest, result: BatchItemResult) -> BatchManifest:
    """Return a manifest with one item updated from a batch result."""
    updated: list[BatchManifestItem] = []
    found = False
    for item in manifest.items:
        if item.dataset_path == result.dataset_path:
            updated.append(
                BatchManifestItem(
                    dataset_path=item.dataset_path,
                    run_folder=result.run_context.run_folder,
                    status=result.status,
                    job_id=item.job_id,
                    message=result.message,
                    outputs=result.outputs,
                )
            )
            found = True
        else:
            updated.append(item)
    if not found:
        updated.append(
            BatchManifestItem(
                dataset_path=result.dataset_path,
                run_folder=result.run_context.run_folder,
                status=result.status,
                job_id=f"pfs-file-{uuid.uuid4().hex[:10]}",
                message=result.message,
                outputs=result.outputs,
            )
        )
    return BatchManifest(
        batch_id=manifest.batch_id,
        batch_folder=manifest.batch_folder,
        created_at=manifest.created_at,
        updated_at=_now(),
        execution_mode=manifest.execution_mode,
        max_workers=manifest.max_workers,
        products=manifest.products,
        items=tuple(updated),
    )


def completed_dataset_paths(manifest: BatchManifest) -> tuple[Path, ...]:
    """Return datasets completed in a prior run."""
    return tuple(item.dataset_path for item in manifest.items if item.status == "completed")


def failed_dataset_paths(manifest: BatchManifest) -> tuple[Path, ...]:
    """Return datasets failed in a prior run."""
    return tuple(item.dataset_path for item in manifest.items if item.status == "failed")


def manifest_to_dict(manifest: BatchManifest) -> dict[str, Any]:
    """Convert manifest to JSON-serializable data."""
    return {
        "batch_id": manifest.batch_id,
        "batch_folder": str(manifest.batch_folder),
        "created_at": manifest.created_at,
        "updated_at": manifest.updated_at,
        "execution_mode": manifest.execution_mode,
        "max_workers": manifest.max_workers,
        "products": [product.value for product in manifest.products],
        "items": [
            {
                "dataset_path": str(item.dataset_path),
                "run_folder": str(item.run_folder),
                "status": item.status,
                "job_id": item.job_id,
                "message": item.message,
                "outputs": [str(path) for path in item.outputs],
            }
            for item in manifest.items
        ],
    }


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
