"""Job result serialization helpers."""

from __future__ import annotations

import json
from html import escape
from pathlib import Path
from typing import Any, Mapping

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
        "parameters": _job_parameters(job),
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
        "processing_executed": any(_is_scientific_result(result.result_type) for result in job.results),
        "scientific_outputs_created": any(_is_scientific_result(result.result_type) for result in job.results),
    }


def _job_parameters(job: JobRecord) -> dict[str, Any]:
    """Return Product Planner parameters for reproducible job summaries."""
    try:
        payload = json.loads(job.product_plan_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(payload, Mapping):
        return {}
    parameters = payload.get("parameters")
    return dict(parameters) if isinstance(parameters, Mapping) else {}


def render_job_summary_html(job: JobRecord) -> str:
    """Render a browser-friendly final run summary."""
    payload = job_to_dict(job)
    result_rows = "".join(
        "<tr>"
        f"<td>{escape(result['type'])}</td>"
        f"<td>{escape(result['description'])}</td>"
        f"<td>{escape(result['path'])}</td>"
        "</tr>"
        for result in payload["results"]
    ) or '<tr><td colspan="3">No result files recorded.</td></tr>'
    pipeline_rows = "".join(
        "<tr>"
        f"<td>{escape(pipeline['label'])}</td>"
        f"<td>{escape('passed' if pipeline['passed'] else 'failed')}</td>"
        f"<td>{escape(str(len(pipeline['steps'])))}</td>"
        "</tr>"
        for pipeline in payload["pipelines"]
    ) or '<tr><td colspan="3">No pipeline results recorded.</td></tr>'
    parameter_rows = "".join(
        f"<tr><td>{escape(str(key))}</td><td>{escape(str(value))}</td></tr>"
        for key, value in payload["parameters"].items()
    ) or '<tr><td colspan="2">No parameters available.</td></tr>'
    logs = "".join(
        f"<li><strong>{escape(entry['level'])}</strong> {escape(entry['message'])}</li>"
        for entry in payload["logs"][-12:]
    ) or "<li>No log entries.</li>"
    error = payload.get("error_message") or "None"
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>{escape(payload['title'])}</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 0; background: #f7f8f9; color: #24313a; }}
    header {{ background: #eef3f4; border-bottom: 1px solid #d8e0e3; padding: 24px 32px; }}
    main {{ max-width: 1120px; margin: 0 auto; padding: 24px; }}
    section {{ background: #fff; border: 1px solid #dfe5e8; border-radius: 6px; padding: 16px; margin-bottom: 16px; }}
    table {{ width: 100%; border-collapse: collapse; }}
    th, td {{ border-bottom: 1px solid #e4eaed; padding: 8px; text-align: left; vertical-align: top; }}
    th {{ background: #f0f4f5; }}
    .status {{ font-weight: 700; text-transform: uppercase; }}
  </style>
</head>
<body>
  <header>
    <h1>{escape(payload['title'])}</h1>
    <p class="status">Status: {escape(payload['status'])}</p>
    <p>Created: {escape(payload['created_at'])} | Updated: {escape(payload['updated_at'])}</p>
  </header>
  <main>
    <section>
      <h2>Run Summary</h2>
      <p>Requested products: {escape(', '.join(payload['requested_products']))}</p>
      <p>Processing executed: {str(payload['processing_executed'])}</p>
      <p>Scientific outputs created: {str(payload['scientific_outputs_created'])}</p>
      <p>Error: {escape(str(error))}</p>
    </section>
    <section>
      <h2>Results</h2>
      <table><tr><th>Type</th><th>Description</th><th>Path</th></tr>{result_rows}</table>
    </section>
    <section>
      <h2>Parameters</h2>
      <table><tr><th>Name</th><th>Value</th></tr>{parameter_rows}</table>
    </section>
    <section>
      <h2>Pipelines</h2>
      <table><tr><th>Product</th><th>Status</th><th>Steps</th></tr>{pipeline_rows}</table>
    </section>
    <section>
      <h2>Recent Log</h2>
      <ul>{logs}</ul>
    </section>
  </main>
</body>
</html>
"""


def write_job_summary_html(job: JobRecord, output_path: Path | str) -> Path:
    """Write a final run summary HTML file."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_job_summary_html(job), encoding="utf-8")
    return path


def _is_scientific_result(result_type: str) -> bool:
    return result_type not in {"job_summary_json", "job_summary_html"}


def render_job_summary_json(job: JobRecord) -> str:
    """Render a job summary as formatted JSON."""
    return json.dumps(job_to_dict(job), indent=2, sort_keys=True)


def write_job_summary_json(job: JobRecord, output_path: Path | str) -> Path:
    """Write a job summary JSON file."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_job_summary_json(job) + "\n", encoding="utf-8")
    return path
