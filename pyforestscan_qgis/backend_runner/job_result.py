"""Serializable PBM processing job results."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class BackendJobResult:
    """Result produced by one managed backend processing job."""

    job_id: str
    product: str
    status: str
    outputs: dict[str, Path] = field(default_factory=dict)
    warnings: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()
    started_at: str = ""
    finished_at: str = ""
    product_metrics: dict[str, Any] = field(default_factory=dict)
    stdout: str = ""
    stderr: str = ""
    traceback: str | None = None
    error_code: str = ""
    retryable: bool | None = None
    root_exception_type: str = ""
    root_exception_message: str = ""
    root_errno: int | None = None
    root_winerror: int | None = None
    root_filename: str | None = None
    root_filename2: str | None = None
    root_module: str = ""
    root_function: str = ""
    root_line: int | None = None
    wrapper_chain: tuple[str, ...] = ()

    @property
    def success(self) -> bool:
        """Return whether the backend job succeeded."""
        return self.status == "success"

    def to_dict(self, include_traceback: bool = True) -> dict[str, Any]:
        """Serialize to JSON-compatible values."""
        payload = {
            "job_id": self.job_id,
            "product": self.product,
            "status": self.status,
            "outputs": {key: str(value) for key, value in self.outputs.items()},
            "warnings": list(self.warnings),
            "errors": list(self.errors),
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "product_metrics": _json_ready(self.product_metrics),
            "stdout": self.stdout,
            "stderr": self.stderr,
            "error_code": self.error_code,
            "retryable": self.retryable,
            "root_exception_type": self.root_exception_type,
            "root_exception_message": self.root_exception_message,
            "root_errno": self.root_errno,
            "root_winerror": self.root_winerror,
            "root_filename": self.root_filename,
            "root_filename2": self.root_filename2,
            "root_module": self.root_module,
            "root_function": self.root_function,
            "root_line": self.root_line,
            "wrapper_chain": list(self.wrapper_chain),
        }
        if include_traceback and self.traceback:
            payload["traceback"] = self.traceback
        return payload

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BackendJobResult":
        """Deserialize from JSON-compatible values."""
        return cls(
            job_id=str(data.get("job_id", "")),
            product=str(data.get("product", "")),
            status=str(data.get("status", "failed")),
            outputs={str(key): Path(value) for key, value in dict(data.get("outputs", {})).items()},
            warnings=tuple(str(item) for item in data.get("warnings", ())),
            errors=tuple(str(item) for item in data.get("errors", ())),
            started_at=str(data.get("started_at", "")),
            finished_at=str(data.get("finished_at", "")),
            product_metrics=dict(data.get("product_metrics", {})),
            stdout=str(data.get("stdout", "")),
            stderr=str(data.get("stderr", "")),
            traceback=data.get("traceback"),
            error_code=str(data.get("error_code", "")),
            retryable=data.get("retryable"),
            root_exception_type=str(data.get("root_exception_type", "")),
            root_exception_message=str(data.get("root_exception_message", "")),
            root_errno=data.get("root_errno"), root_winerror=data.get("root_winerror"),
            root_filename=data.get("root_filename"), root_filename2=data.get("root_filename2"),
            root_module=str(data.get("root_module", "")), root_function=str(data.get("root_function", "")),
            root_line=data.get("root_line"), wrapper_chain=tuple(str(item) for item in data.get("wrapper_chain", ())),
        )

    def write(self, path: Path) -> Path:
        """Write result JSON and return the path."""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return path

    @classmethod
    def read(cls, path: Path) -> "BackendJobResult":
        """Read result JSON."""
        return cls.from_dict(json.loads(path.read_text(encoding="utf-8")))


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
