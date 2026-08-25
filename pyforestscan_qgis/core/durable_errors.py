"""Durable user-visible processing error records."""
from __future__ import annotations
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
from pathlib import Path


@dataclass(frozen=True)
class DurableErrorRecord:
    code: str
    category: str
    user_message: str
    technical_message: str
    stage: str
    job_id: str = ""
    attempt_id: str = ""
    product: str = ""
    timestamp: str = ""
    recommended_action: str = "Review job diagnostics and retry when appropriate."

    def to_dict(self):
        data = asdict(self)
        if not data["timestamp"]:
            data["timestamp"] = datetime.now(timezone.utc).isoformat()
        return data


def write_recent_error(job_folder: Path | str, record: DurableErrorRecord) -> Path:
    path = Path(job_folder) / "diagnostics" / "recent_error.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".partial")
    temporary.write_text(json.dumps(record.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)
    return path


def read_recent_error(job_folder: Path | str) -> DurableErrorRecord | None:
    path = Path(job_folder) / "diagnostics" / "recent_error.json"
    try:
        return DurableErrorRecord(**json.loads(path.read_text(encoding="utf-8")))
    except (OSError, ValueError, TypeError):
        return None


__all__ = ["DurableErrorRecord", "read_recent_error", "write_recent_error"]
