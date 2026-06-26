"""Job result serialization helpers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .jobs import JobRecord
from .pipeline_results import pipeline_result_to_dict


def job_to_dict(job: JobRecord) -> dict[str, Any]:
    """Convert a job record to a JSON-serializable dictionary."""
    return {
        "job_id": job.job_id,
        "title": job.title,
        "status": job.status.value,
        "mode": job.mode.value,
        "product_plan_path": str(job.product_plan_path),
        "output_folder": str(job.output_folder),
        "summary_path": str(job.summary_path) if job.summary_path else None,
        "created_at": job.created_at,
        "updated_at": job.updated_at,
        "progress": {
            "percent": job.progress.percent,
            "message": job.progress.message,
        },
        "requested_products": list(job.requested_products),
        "pipelines": [pipeline_result_to_dict(result) for result in job.pipeline_results],
        "logs": [
            {"timestamp": entry.timestamp, "level": entry.level, "message": entry.message}
            for entry in job.logs
        ],
        "results": [
            {
                "path": str(result.path),
                "type": result.result_type,
                "description": result.description,
            }
            for result in job.results
        ],
        "error_message": job.error_message,
        "processing_executed": False,
        "scientific_outputs_created": False,
    }


def render_job_summary_json(job: JobRecord) -> str:
    """Render a job summary as formatted JSON."""
    return json.dumps(job_to_dict(job), indent=2, sort_keys=True)


def write_job_summary_json(job: JobRecord, output_path: Path | str) -> Path:
    """Write a dry-run job summary JSON file."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_job_summary_json(job) + "\n", encoding="utf-8")
    return path
