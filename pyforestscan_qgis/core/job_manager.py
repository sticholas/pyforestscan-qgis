"""Job execution manager for dry-run and implemented pipeline work.

The manager owns lifecycle transitions for PyForestScan jobs. Dry-run mode still
performs validation only. Processing mode executes only pipeline stages that are
implemented behind the adapter boundary.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any, Callable, Mapping

from .adapter import PyForestScanAdapter
from .job_results import write_job_summary_json
from .jobs import JobMode, JobRecord, JobRequest, JobResultRecord, JobStatus, utc_now
from .pipeline import PipelineRegistry, build_default_pipeline_registry
from .pipeline_context import PipelineContextError, load_pipeline_contexts

JobEventSink = Callable[[JobRecord], None]


class JobExecutionError(ValueError):
    """Raised when a job request or product plan is invalid."""


class JobManager:
    """Create, validate, run, cancel, and retain job records."""

    def __init__(
        self,
        event_sink: JobEventSink | None = None,
        pipeline_registry: PipelineRegistry | None = None,
        adapter: PyForestScanAdapter | None = None,
    ) -> None:
        """Create a manager with optional event, registry, and adapter hooks."""
        self._event_sink = event_sink
        self._pipeline_registry = pipeline_registry or build_default_pipeline_registry()
        self._adapter = adapter or PyForestScanAdapter()
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
        """Create a pending job after validating the product plan."""
        if request.mode not in {JobMode.DRY_RUN, JobMode.PROCESSING}:
            raise JobExecutionError("Unsupported job execution mode.")
        plan = self._load_product_plan(request.product_plan_path)
        requested_products = self._requested_products(plan)
        created_at = utc_now()
        job = JobRecord(
            job_id=f"pfs-{uuid.uuid4().hex[:12]}",
            title=request.title or ("PyForestScan Processing Job" if request.mode is JobMode.PROCESSING else "PyForestScan Dry-Run Job"),
            status=JobStatus.PENDING,
            mode=request.mode,
            product_plan_path=Path(request.product_plan_path),
            output_folder=Path(request.output_folder),
            summary_path=Path(request.summary_path) if request.summary_path else None,
            created_at=created_at,
            updated_at=created_at,
            requested_products=tuple(requested_products),
        ).with_log("INFO", f"{request.mode.value} job created.")
        return self._store(job)

    def run_dry_run(
        self,
        product_plan_path: Path | str,
        output_folder: Path | str,
        title: str = "PyForestScan Dry-Run Job",
        summary_path: Path | str | None = None,
    ) -> JobRecord:
        """Run validation-only pipelines and write a JSON summary."""
        return self._run_pipeline_job(product_plan_path, output_folder, title, summary_path, execute_products=False)

    def run_pipeline(
        self,
        product_plan_path: Path | str,
        output_folder: Path | str,
        title: str = "PyForestScan Processing Job",
        summary_path: Path | str | None = None,
    ) -> JobRecord:
        """Run implemented product pipelines and write a JSON summary."""
        return self._run_pipeline_job(product_plan_path, output_folder, title, summary_path, execute_products=True)

    def _run_pipeline_job(
        self,
        product_plan_path: Path | str,
        output_folder: Path | str,
        title: str,
        summary_path: Path | str | None,
        execute_products: bool,
    ) -> JobRecord:
        request = JobRequest(
            product_plan_path=Path(product_plan_path),
            output_folder=Path(output_folder),
            title=title,
            mode=JobMode.PROCESSING if execute_products else JobMode.DRY_RUN,
            summary_path=Path(summary_path) if summary_path else None,
        )
        job = self.create_dry_run_job(request)
        try:
            plan = self._load_product_plan(request.product_plan_path)
            self._validate_plan_for_execution(plan)
            job = self._transition(job, JobStatus.VALIDATING, "Product plan validated for pipeline execution.")
            contexts = load_pipeline_contexts(request.product_plan_path, request.output_folder)
            job = self._progress(job, 10, "Pipeline contexts loaded.")
            if self._is_cancelled(job):
                return self._finalize_cancelled(job)

            start_message = "Processing pipeline started." if execute_products else "Pipeline dry-run validation started."
            job = self._transition(job, JobStatus.RUNNING, start_message)
            pipeline_results = []
            total = max(1, len(contexts))
            for index, pipeline_context in enumerate(contexts, start=1):
                pipeline = self._pipeline_registry.get(pipeline_context.product)
                pipeline_result = pipeline.run(pipeline_context, adapter=self._adapter, execute_products=execute_products)
                pipeline_results.append(pipeline_result)
                job = self._store(job.with_pipeline_results(tuple(pipeline_results)))
                for output_path in pipeline_result.output_paths:
                    if output_path not in tuple(result.path for result in job.results):
                        job = self._store(job.with_result(JobResultRecord(output_path, f"{pipeline_result.product}_geotiff", f"{pipeline_result.label} GeoTIFF output.")))
                percent = 10 + (index / total) * 80
                job = self._progress(job, percent, f"Validated pipeline: {pipeline.label}.")
                if self._is_cancelled(job):
                    return self._finalize_cancelled(job)
            if any(not result.passed for result in pipeline_results):
                raise JobExecutionError("One or more pipeline validation stages failed.")

            finish_progress = "Processing pipeline completed." if execute_products else "Pipeline dry-run completed."
            job = self._progress(job, 100, finish_progress)
            complete_message = "Processing pipeline completed." if execute_products else "Dry-run pipeline completed without scientific processing."
            job = self._transition(job, JobStatus.COMPLETED, complete_message)
            return self._write_summary(job)
        except Exception as exc:
            if isinstance(exc, (JobExecutionError, PipelineContextError, KeyError)):
                message = str(exc)
            else:
                message = f"Unexpected job failure: {exc}"
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
        job = self._progress(job, job.progress.percent, "Job cancelled.")
        job = self._transition(job, JobStatus.CANCELLED, "Job cancelled before completion.")
        return self._write_summary(job)

    def _write_summary(self, job: JobRecord) -> JobRecord:
        summary_path = job.summary_path or (job.output_folder / f"{job.job_id}_job_summary.json")
        result = JobResultRecord(
            path=summary_path,
            result_type="job_summary_json",
            description="Job summary JSON.",
        )
        job_with_result = self._store(job.with_result(result))
        write_job_summary_json(job_with_result, summary_path)
        return job_with_result

    def _store(self, job: JobRecord) -> JobRecord:
        self._jobs[job.job_id] = job
        if self._event_sink is not None:
            self._event_sink(job)
        return job
