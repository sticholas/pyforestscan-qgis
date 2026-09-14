"""Low-overhead, QGIS-free profiling for polygon prerun planning."""
from __future__ import annotations

import json
import os
import threading
import time
import tracemalloc
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class _Metric:
    count: int = 0
    total: float = 0.0
    maximum: float = 0.0


@dataclass
class PrerunProfiler:
    metrics: dict[str, _Metric] = field(default_factory=dict)
    started: float = field(default_factory=time.perf_counter)
    counters: dict[str, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        tracemalloc.start()

    @contextmanager
    def measure(self, function: str):
        started = time.perf_counter()
        try:
            yield
        finally:
            elapsed = time.perf_counter() - started
            metric = self.metrics.setdefault(function, _Metric())
            metric.count += 1; metric.total += elapsed; metric.maximum = max(metric.maximum, elapsed)

    def count(self, name: str, amount: int = 1) -> None:
        self.counters[name] = self.counters.get(name, 0) + amount

    def write(self, path: Path | str, *, stage: str, extra: dict[str, object] | None = None) -> Path:
        _, peak = tracemalloc.get_traced_memory()
        payload = {
            "schema": "pyforestscan-prerun-profile-v1",
            "stage": stage,
            "elapsed_seconds": time.perf_counter() - self.started,
            "peak_memory_bytes": peak,
            "process_id": os.getpid(),
            "thread_id": threading.get_ident(),
            "functions": [
                {"function": name, "call_count": metric.count, "total_seconds": metric.total, "mean_seconds": metric.total / metric.count, "max_seconds": metric.maximum}
                for name, metric in sorted(self.metrics.items())
            ],
            "counters": dict(sorted(self.counters.items())),
            **(extra or {}),
        }
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return destination
