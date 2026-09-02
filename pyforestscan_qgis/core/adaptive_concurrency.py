"""Conservative job-level concurrency policy for isolated LiDAR workers."""
from __future__ import annotations

import math
import os
import statistics
from dataclasses import dataclass, field

from .adaptive_processing import available_memory_bytes


@dataclass(frozen=True)
class ConcurrencySnapshot:
    requested: int
    target: int
    ceiling: int
    active: int
    successful: int
    failed: int
    health: str
    reason: str
    median_worker_rss: int = 0
    p90_worker_rss: int = 0
    maximum_worker_rss: int = 0


@dataclass
class AdaptiveConcurrencyController:
    """Ramp isolated workers from one toward a resource-derived ceiling."""

    requested: int
    source_location: str
    estimated_worker_memory: int
    available_memory_provider: object = available_memory_bytes
    cpu_count: int = field(default_factory=lambda: max(1, os.cpu_count() or 1))
    hard_maximum: int = 5
    reserve_bytes: int = 2 * 1024**3
    target: int = 1
    successful: int = 0
    failed: int = 0
    health: str = "WORKING"
    reason: str = "Starting conservatively with one isolated worker."
    worker_rss: list[int] = field(default_factory=list)
    ept_seconds: list[float] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.requested = max(1, min(int(self.requested), self.hard_maximum))
        self.target = 1

    @property
    def ceiling(self) -> int:
        available = max(0, int(self.available_memory_provider()))
        conservative = max(int(self.p90_worker_rss * 1.35), 512 * 1024**2) if self.p90_worker_rss else max(self.estimated_worker_memory, 512 * 1024**2)
        memory_capacity = max(1, int(max(0, available - self.reserve_bytes) / max(conservative * 1.25, 1)))
        cpu_capacity = max(1, min(self.hard_maximum, self.cpu_count // 2 or 1))
        network_capacity = 2 if self.source_location in {"network", "remote_url"} else self.hard_maximum
        return max(1, min(self.requested, memory_capacity, cpu_capacity, network_capacity, self.hard_maximum))

    @property
    def median_worker_rss(self) -> int:
        return int(statistics.median(self.worker_rss)) if self.worker_rss else 0

    @property
    def p90_worker_rss(self) -> int:
        if not self.worker_rss:
            return 0
        values = sorted(self.worker_rss)
        return int(values[min(len(values) - 1, int((len(values) - 1) * 0.9))])

    @property
    def maximum_worker_rss(self) -> int:
        return max(self.worker_rss, default=0)

    def observe(self, result) -> None:
        metrics = getattr(result, "metrics", {}) or {}
        rss = int(metrics.get("worker_peak_rss", 0) or 0)
        if rss > 0:
            self.worker_rss.append(rss)
            del self.worker_rss[:-32]
        ept = float(metrics.get("ept_read_and_point_decode_seconds", 0) or 0)
        if ept > 0:
            self.ept_seconds.append(ept)
            del self.ept_seconds[:-32]
        if getattr(result, "status", "") == "Failed":
            self.failed += 1
            self.target = max(1, self.target - 1)
            self.health = "RESOURCE_LIMITED" if getattr(result, "error_code", "") != "NATIVE_BACKEND_CRASH" else "POSSIBLE_STALL"
            self.reason = "Worker failure reduced automatic processing capacity."
            return
        self.successful += 1
        if self._memory_pressure():
            self.target = max(1, self.target - 1)
            self.health = "RESOURCE_LIMITED"
            self.reason = "Available memory reduced automatic processing capacity."
            return
        if self._network_degraded():
            self.target = max(1, self.target - 1)
            self.health = "WAITING_FOR_DATA"
            self.reason = "LiDAR read latency increased under concurrency."
            return
        if self.successful >= self.target and self.target < self.ceiling:
            self.target += 1
            self.reason = f"Stable completed regions allowed ramp-up to {self.target} workers."
        else:
            self.health = "WORKING"
            self.reason = "Automatic capacity is stable."

    def dispatch_capacity(self, active: int) -> int:
        if self._memory_pressure() and self.target > 1:
            self.target -= 1
            self.health = "RESOURCE_LIMITED"
            self.reason = "New workers are paused while memory pressure recovers."
        return max(0, min(self.target, self.ceiling) - max(0, active))

    def snapshot(self, active: int = 0) -> ConcurrencySnapshot:
        return ConcurrencySnapshot(
            self.requested, self.target, self.ceiling, active, self.successful, self.failed,
            self.health, self.reason, self.median_worker_rss, self.p90_worker_rss, self.maximum_worker_rss,
        )

    def _memory_pressure(self) -> bool:
        available = int(self.available_memory_provider())
        conservative = max(int(self.p90_worker_rss * 1.35), 512 * 1024**2) if self.p90_worker_rss else max(self.estimated_worker_memory, 512 * 1024**2)
        return available < self.reserve_bytes + conservative * max(1, self.target)

    def _network_degraded(self) -> bool:
        if self.source_location not in {"network", "remote_url"} or len(self.ept_seconds) < 6:
            return False
        baseline = statistics.median(self.ept_seconds[:3])
        recent = statistics.median(self.ept_seconds[-3:])
        return baseline > 0 and recent > baseline * 2.25


def weighted_progress(completed_weight: float, active_weight: float, total_weight: float) -> int:
    """Return conservative integer progress with active work half credited."""
    if total_weight <= 0:
        return 0
    return max(0, min(100, int(((completed_weight + active_weight * 0.5) / total_weight) * 100)))


def robust_eta_seconds(completed_durations: list[float], pending: int, active: int, concurrency: int) -> tuple[float | None, str]:
    """Estimate remaining time from a rolling robust duration distribution."""
    values = [float(value) for value in completed_durations[-24:] if value > 0]
    if len(values) < 3:
        return None, "CALCULATING"
    duration = statistics.median(values)
    waves = math.ceil(max(0, pending + active) / max(1, concurrency))
    confidence = "STABLE" if len(values) >= 8 else "LOW_CONFIDENCE"
    return duration * waves, confidence
