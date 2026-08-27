"""Small registry-backed processing history; never inferred by scanning outputs."""

from __future__ import annotations

import json
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
        entries.append(ProcessingHistoryEntry(**{**item, "products": tuple(item.get("products", ())), "outputs": tuple(item.get("outputs", ())) }))
    return tuple(entries)


__all__ = ["ProcessingHistoryEntry", "append_processing_history", "read_processing_history"]
