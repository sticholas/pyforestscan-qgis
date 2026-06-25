"""Dry-run job execution manager.

The manager owns lifecycle transitions for PyForestScan jobs. Phase 8A performs
validation and dry-run simulation only. It never calls PyForestScan scientific
processing functions and never creates rasters or product outputs.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any, Callable, Mapping

from .job_results import write_job_summary_json
from .jobs import JobMode, JobRecord, JobRequest, JobResultRecord, JobStatus, utc_now

JobEventSink = Callable[[JobRecord], None]


class JobExecutionError(ValueError):
    """Raised when a job request or product plan is invalid."""


class JobManager:
    """Create, validate, run, cancel, and retain dry-run job records."""

    def __init__(self, event_sink: JobEventSink | None = None) -> None:
        """Create a manager with an optional event sink for progress bridges."""
        self._event_sink = event_sink
        self._jobs: dict[str, JobRecord] = {}
        self._cancel_requested: set[str] = set()

    @property
    def jobs(self) -> tuple[JobRecord, ...]:
        """Return known jobs ordered by most recent update."""
        return tuple(sorted(self._jobs.values(), key=lambda job: job.updated_at, reverse=True))

    def get_job(self, job_id: str) -> JobRecord | None:
        """Return a job by identifier if known."""
        return self._jobs.get(job_id)

    def request_cancel(self, job_id: str) -> JobRecord | None:
        """Request cancellation for a known job."""
        job = self._jobs.get(job_id)
        if job is None:
            return None
        if job.status in {JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED}:
            return job
        self._cancel_requested.add(job_id)
        job = job.with_status(JobStatus.CANCELLING, "Cancellation requested.")
        return self._store(job)

    def create_dry_run_job(self, request: JobRequest) -> JobRecord:
        """Create a pending dry-run job after validating the product plan."""
        if request.mode is not JobMode.DRY_RUN:
            raise JobExecutionError("Only dry-run jobs are supported in this phase.")
        plan = self._load_product_plan(request.product_plan_path)
        requested_products = self._requested_products(plan)
        created_at = utc_now()
        job = JobRecord(
            job_id=f"pfs-{uuid.uuid4().hex[:12]}",
            title=request.title or "PyForestScan Dry-Run Job",
            status=JobStatus.PENDING,
            mode=JobMode.DRY_RUN,
            product_plan_path=Path(request.product_plan_path),
            output_folder=Path(request.output_folder),
            summary_path=Path(request.summary_path) if request.summary_path else None,
            created_at=created_at,
            updated_at=created_at,
            requested_products=tuple(requested_products),
        ).with_log("INFO", "Dry-run job created.")
        return self._store(job)

    def run_dry_run(
        self,
        product_plan_path: Path | str,
        output_folder: Path | str,
        title: str = "PyForestScan Dry-Run Job",
        summary_path: Path | str | None = None,
    ) -> JobRecord:
        """Run a cancellable dry-run job and write a JSON summary."""
        request = JobRequest(
            product_plan_path=Path(product_plan_path),
            output_folder=Path(output_folder),
            title=title,
            summary_path=Path(summary_path) if summary_path else None,
        )
        job = self.create_dry_run_job(request)
        try:
            plan = self._load_product_plan(request.product_plan_path)
            self._validate_plan_for_execution(plan)
            job = self._transition(job, JobStatus.VALIDATING, "Product plan validated for dry-run execution.")
            job = self._progress(job, 10, "Validation complete.")
            if self._is_cancelled(job):
                return self._finalize_cancelled(job)

            job = self._transition(job, JobStatus.RUNNING, "Dry-run simulation started.")
            for percent, message in (
                (25, "Checking requested products."),
                (45, "Estimating future outputs."),
                (65, "Verifying no scientific processing will run."),
                (85, "Preparing dry-run summary."),
            ):
                job = self._progress(job, percent, message)
                if self._is_cancelled(job):
                    return self._finalize_cancelled(job)

            job = self._progress(job, 100, "Dry-run completed.")
            job = self._transition(job, JobStatus.COMPLETED, "Dry-run job completed without scientific processing.")
            return self._write_summary(job)
        except Exception as exc:
            if isinstance(exc, JobExecutionError):
                message = str(exc)
            else:
                message = f"Unexpected dry-run job failure: {exc}"
            failed = job.with_error(message)
            failed = self._store(failed)
            return self._write_summary(failed)

    def _load_product_plan(self, product_plan_path: Path) -> Mapping[str, Any]:
        try:
            payload = json.loads(Path(product_plan_path).read_text(encoding="utf-8"))
        except OSError as exc:
            raise JobExecutionError(f"Could not read Product Planner JSON: {exc}") from exc
        except json.JSONDecodeError as exc:
            raise JobExecutionError(f"Product Planner JSON is not valid JSON: {exc}") from exc
        if not isinstance(payload, dict):
            raise JobExecutionError("Product Planner JSON must contain an object at the top level.")
        return payload

    def _validate_plan_for_execution(self, plan: Mapping[str, Any]) -> None:
        if plan.get("processing_executed") is not False:
            raise JobExecutionError("Product plan must have processing_executed=false.")
        products = plan.get("products")
        if not isinstance(products, list) or not products:
            raise JobExecutionError("Product plan must contain at least one requested product.")
        for product in products:
            if not isinstance(product, dict):
                raise JobExecutionError("Each product entry must be an object.")
            if product.get("requested") is not True:
                raise JobExecutionError("Dry-run execution requires requested product entries.")
            if not product.get("product"):
                raise JobExecutionError("Each requested product must include a product identifier.")
            if product.get("plan_status") == "Blocked":
                raise JobExecutionError(f"Product {product.get('product')} is blocked in the plan.")

    def _requested_products(self, plan: Mapping[str, Any]) -> list[str]:
        products = plan.get("products")
        if not isinstance(products, list) or not products:
            raise JobExecutionError("Product plan must contain at least one product.")
        requested: list[str] = []
        for product in products:
            if isinstance(product, dict) and product.get("requested") is True:
                name = product.get("product")
                if isinstance(name, str) and name:
                    requested.append(name)
        if not requested:
            raise JobExecutionError("Product plan does not contain any requested products.")
        return requested

    def _transition(self, job: JobRecord, status: JobStatus, message: str) -> JobRecord:
        return self._store(job.with_status(status, message))

    def _progress(self, job: JobRecord, percent: float, message: str) -> JobRecord:
        return self._store(job.with_progress(percent, message).with_log("INFO", message))

    def _is_cancelled(self, job: JobRecord) -> bool:
        return job.job_id in self._cancel_requested

    def _finalize_cancelled(self, job: JobRecord) -> JobRecord:
        self._cancel_requested.discard(job.job_id)
        job = self._progress(job, job.progress.percent, "Dry-run cancelled.")
        job = self._transition(job, JobStatus.CANCELLED, "Dry-run job cancelled before completion.")
        return self._write_summary(job)

    def _write_summary(self, job: JobRecord) -> JobRecord:
        summary_path = job.summary_path or (job.output_folder / f"{job.job_id}_job_summary.json")
        result = JobResultRecord(
            path=summary_path,
            result_type="job_summary_json",
            description="Dry-run job summary JSON. No scientific outputs were created.",
        )
        job_with_result = self._store(job.with_result(result))
        write_job_summary_json(job_with_result, summary_path)
        return job_with_result

    def _store(self, job: JobRecord) -> JobRecord:
        self._jobs[job.job_id] = job
        if self._event_sink is not None:
            self._event_sink(job)
        return job
