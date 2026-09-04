"""Small registry-backed processing history; never inferred by scanning outputs."""

from __future__ import annotations

import json
import os
import platform
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

from .atomic_state import atomic_write_json


@dataclass(frozen=True)
class ProcessingHistoryEntry:
    job_id: str
    attempt_id: str
    date: str
    source: str
    source_mode: str
    products: tuple[str, ...]
    status: str
    elapsed_seconds: float
    outputs: tuple[str, ...]
    output_folder: str = ""
    report_path: str = ""
    error_report_path: str = ""
    plan_signature: str = ""
    area_hectares: float | None = None
    crs: str = ""

    def to_dict(self) -> dict[str, object]:
        data = asdict(self)
        data["products"] = list(self.products)
        data["outputs"] = list(self.outputs)
        return data


def append_processing_history(path: Path | str, entry: ProcessingHistoryEntry, *, limit: int = 100) -> Path:
    """Append one new attempt identity and retain a compact local history."""
    target = Path(path)
    existing = list(read_processing_history(target))
    existing = [item for item in existing if (item.job_id, item.attempt_id) != (entry.job_id, entry.attempt_id)]
    existing.insert(0, entry)
    atomic_write_json(target, {"schema": "pyforestscan-processing-history-v1", "runs": [item.to_dict() for item in existing[: max(1, limit)]]})
    return target


def read_processing_history(path: Path | str) -> tuple[ProcessingHistoryEntry, ...]:
    target = Path(path)
    if not target.is_file():
        return ()
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ()
    entries = []
    for item in payload.get("runs", ()):
        fields = ProcessingHistoryEntry.__dataclass_fields__
        values = {key: value for key, value in item.items() if key in fields}
        entries.append(ProcessingHistoryEntry(**{**values, "products": tuple(item.get("products", ())), "outputs": tuple(item.get("outputs", ())) }))
    return tuple(entries)


def default_processing_history_path(environ: dict[str, str] | None = None, home: Path | None = None) -> Path:
    """Return the cross-platform user-local history index without creating it."""
    env = environ if environ is not None else os.environ
    base_home = home or Path.home()
    system = platform.system().lower()
    if system.startswith("win"):
        base = Path(env.get("LOCALAPPDATA") or base_home / "AppData" / "Local") / "PyForestScan"
    elif system == "darwin":
        base = base_home / "Library" / "Application Support" / "PyForestScan"
    else:
        base = Path(env.get("XDG_DATA_HOME") or base_home / ".local" / "share") / "PyForestScan"
    return base / "jobs" / "processing_history.json"


def format_recent_result(entry: ProcessingHistoryEntry) -> str:
    """Return a compact product-oriented result summary."""
    status = {
        "SUCCEEDED": "Complete",
        "complete": "Complete",
        "PARTIAL_SUCCESS": "Completed with issues",
        "partial_success": "Completed with issues",
        "FAILED": "Failed",
        "failed": "Failed",
        "CANCELLED": "Cancelled",
        "cancelled": "Cancelled",
    }.get(entry.status, entry.status.replace("_", " ").title())
    labels = {
        "chm": "CHM", "dtm": "DTM", "pad": "PAD", "pai": "PAI", "fhd": "FHD",
        "canopy_cover": "Canopy Cover", "rumple": "Rumple", "point_density": "Point Density",
    }
    products = " · ".join(labels.get(item, item.replace("_", " ").title()) for item in entry.products) or "No completed products"
    area = f" · {entry.area_hectares:.1f} ha" if entry.area_hectares is not None else ""
    source = Path(entry.source).parent.name if Path(entry.source).name.lower() == "ept.json" else Path(entry.source).name
    return f"{status} · {len(entry.outputs)} outputs{area} · {entry.date}\n{source or 'Processing job'}\n{products}"


__all__ = ["ProcessingHistoryEntry", "append_processing_history", "read_processing_history", "default_processing_history_path", "format_recent_result"]
