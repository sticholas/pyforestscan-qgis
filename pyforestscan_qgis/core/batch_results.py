"""Batch summary writers."""

from __future__ import annotations

import csv
import json
from html import escape
from pathlib import Path
from typing import Any

from .batch import BatchResult


def batch_result_to_dict(result: BatchResult) -> dict[str, Any]:
    """Convert a batch result to JSON-serializable data."""
    return {
        "batch_id": result.batch_id,
        "title": result.title,
        "started_at": result.started_at,
        "finished_at": result.finished_at,
        "batch_folder": str(result.batch_folder),
        "success_count": result.success_count,
        "failure_count": result.failure_count,
        "items": [
            {
                "dataset_path": str(item.dataset_path),
                "run_folder": str(item.run_context.run_folder),
                "status": item.status,
                "message": item.message,
                "bounds_summary": item.bounds_summary,
                "outputs": [str(path) for path in item.outputs],
            }
            for item in result.items
        ],
        "summary_json": str(result.summary_json),
        "summary_csv": str(result.summary_csv),
        "summary_html": str(result.summary_html),
    }


def write_batch_summary_json(result: BatchResult, path: Path | str | None = None) -> Path:
    """Write batch summary JSON."""
    output = Path(path) if path is not None else result.summary_json
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(batch_result_to_dict(result), indent=2), encoding="utf-8")
    return output


def write_batch_summary_csv(result: BatchResult, path: Path | str | None = None) -> Path:
    """Write batch summary CSV."""
    output = Path(path) if path is not None else result.summary_csv
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(("dataset", "status", "message", "bounds", "run_folder", "outputs"))
        for item in result.items:
            writer.writerow((
                str(item.dataset_path),
                item.status,
                item.message,
                item.bounds_summary,
                str(item.run_context.run_folder),
                "; ".join(str(path) for path in item.outputs),
            ))
    return output


def write_batch_summary_html(result: BatchResult, path: Path | str | None = None) -> Path:
    """Write browser-friendly batch summary HTML."""
    output = Path(path) if path is not None else result.summary_html
    output.parent.mkdir(parents=True, exist_ok=True)
    rows = "".join(
        "<tr>"
        f"<td>{escape(item.dataset_path.name)}</td>"
        f"<td>{escape(item.status)}</td>"
        f"<td>{escape(item.message)}</td>"
        f"<td>{escape(item.bounds_summary)}</td>"
        f"<td>{escape(str(item.run_context.run_folder))}</td>"
        f"<td>{escape(str(len(item.outputs)))}</td>"
        "</tr>"
        for item in result.items
    ) or '<tr><td colspan="6">No datasets processed.</td></tr>'
    html = f"""<!doctype html>
<html><head><meta charset=\"utf-8\"><title>{escape(result.title)}</title>
<style>body{{font-family:Arial,sans-serif;margin:24px;color:#23313a}}table{{border-collapse:collapse;width:100%}}td,th{{border:1px solid #dfe6e9;padding:8px;text-align:left}}th{{background:#eef3f4}}</style>
</head><body>
<h1>{escape(result.title)}</h1>
<p>Started: {escape(result.started_at)}<br>Finished: {escape(result.finished_at)}<br>Batch folder: {escape(str(result.batch_folder))}</p>
<p>Completed: {result.success_count} &nbsp; Failed: {result.failure_count}</p>
<table><tr><th>Dataset</th><th>Status</th><th>Message</th><th>Bounds</th><th>Run folder</th><th>Outputs</th></tr>{rows}</table>
</body></html>"""
    output.write_text(html, encoding="utf-8")
    return output


def write_batch_summaries(result: BatchResult) -> BatchResult:
    """Write all batch summary formats and return the result."""
    write_batch_summary_json(result)
    write_batch_summary_csv(result)
    write_batch_summary_html(result)
    return result
