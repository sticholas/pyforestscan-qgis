"""Timeout, heartbeat, and workload models for long PBM jobs."""
from __future__ import annotations
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Mapping
import math

class TimeoutMode(str, Enum):
    AUTOMATIC = "automatic"
    NO_FIXED_WALL_TIME = "no_fixed_wall_time"
    CUSTOM = "custom"
    CONSERVATIVE_TESTING = "conservative_testing"

@dataclass(frozen=True)
class ProcessingTimeoutPolicy:
    mode: TimeoutMode = TimeoutMode.AUTOMATIC
    startup_timeout: float = 60.0
    heartbeat_timeout: float = 1800.0
    no_progress_timeout: float = 3600.0
    maximum_wall_time: float | None = None
    graceful_shutdown_timeout: float = 15.0
    product_overrides: Mapping[str, float] = field(default_factory=dict)
    repository_overrides: Mapping[str, float] = field(default_factory=dict)

    @classmethod
    def automatic(cls) -> "ProcessingTimeoutPolicy":
        return cls()

    def wall_time_for(self, product: str, repository_kind: str = "") -> float | None:
        value = self.product_overrides.get(product, self.repository_overrides.get(repository_kind, self.maximum_wall_time))
        return normalized_wall_time(value)

@dataclass(frozen=True)
class JobHeartbeat:
    job_id: str
    attempt_id: str
    timestamp: str
    process_id: int
    current_stage: str
    current_product: str
    latest_activity: str
    elapsed_seconds: float
    current_work_unit_id: str = ""
    latest_completed_unit: str = ""
    completed_count: int = 0
    total_count: int = 1
    retry_count: int = 0
    points_processed: int | None = None
    bytes_processed: int | None = None
    process_alive: bool = True

    @classmethod
    def read(cls, path: Path) -> "JobHeartbeat":
        return cls(**json.loads(path.read_text(encoding="utf-8")))

def heartbeat_path(run_folder: Path) -> Path:
    return Path(run_folder) / "progress" / "heartbeat.json"

STAGES = ("Validating Inputs", "Reading LiDAR", "Preparing Heights", "Generating Product", "Writing Raster", "Clipping to Polygon", "Finalizing Output")

@dataclass(frozen=True)
class WorkloadEstimate:
    classification: str
    rows: int
    columns: int
    cells: int
    raster_memory_bytes: int
    approximate_disk_bytes: int
    warning: str = ""

def classify_raster_workload(envelope: tuple[float,float,float,float], resolution: float, product: str="chm", repository_kind: str="") -> WorkloadEstimate:
    if resolution <= 0: raise ValueError("resolution must be positive")
    xmin,ymin,xmax,ymax=envelope
    columns=max(1, int((xmax-xmin)/resolution + .999999))
    rows=max(1, int((ymax-ymin)/resolution + .999999))
    cells=rows*columns
    level="Small" if cells < 5_000_000 else "Moderate" if cells < 25_000_000 else "Large" if cells < 100_000_000 else "Very Large"
    warning="Very large raster request; memory-safe tiling has not been scientifically validated for every product." if level=="Very Large" else ""
    return WorkloadEstimate(level,rows,columns,cells,cells*4,int(cells*2.5),warning)


@dataclass(frozen=True)
class LivenessDecision:
    status: str
    reason: str

def evaluate_liveness(policy: ProcessingTimeoutPolicy, *, elapsed: float, heartbeat_age: float | None, progress_age: float | None, started: bool=True, product: str="", repository_kind: str="") -> LivenessDecision:
    if not started and elapsed > policy.startup_timeout:
        return LivenessDecision("stalled", "Process did not start within the startup limit.")
    wall = policy.wall_time_for(product, repository_kind)
    if wall is not None and elapsed > wall:
        return LivenessDecision("timed_out", "Configured custom maximum wall time was reached.")
    if heartbeat_age is not None and heartbeat_age > policy.heartbeat_timeout:
        return LivenessDecision("stalled", f"No heartbeat for {heartbeat_age:.0f} seconds.")
    if progress_age is not None and progress_age > policy.no_progress_timeout and heartbeat_age is None:
        return LivenessDecision("stalled", f"No progress for {progress_age:.0f} seconds and heartbeat is unavailable.")
    return LivenessDecision("running", "Job is running and responsive.")


def normalized_wall_time(value) -> float | None:
    """Normalize legacy/config wall times; malformed and nonpositive values mean unlimited."""
    if value is None or isinstance(value,bool): return None
    try: number=float(value)
    except (TypeError,ValueError): return None
    return number if math.isfinite(number) and number>0 else None

def has_wall_time_limit(policy: ProcessingTimeoutPolicy) -> bool:
    return normalized_wall_time(policy.maximum_wall_time) is not None or any(normalized_wall_time(x) is not None for x in (*policy.product_overrides.values(),*policy.repository_overrides.values()))
