"""Bounded point-budget controller independent of renderer and QGIS."""
from dataclasses import dataclass
import math


@dataclass(frozen=True)
class ViewBudget:
    points: int
    screen_error: float
    prefetch: bool


def next_view_budget(previous: int, *, viewport_pixels: int, moving: bool,
                     frame_ms: float | None = None, memory_pressure: float = 0.0,
                     available_bytes: int | None = None, source_points: int | None = None) -> ViewBudget:
    """Conservative draw budget; a backend must enforce residency separately.

    Unknown RAM/GPU is not invented. Limits are guardrails, not measured
    capacities. A point's estimated renderer allocation is 128 bytes.
    """
    if previous < 0 or viewport_pixels <= 0:
        raise ValueError("Invalid previous budget or viewport.")
    if not math.isfinite(memory_pressure) or not 0 <= memory_pressure <= 1:
        raise ValueError("Memory pressure must be a fraction between zero and one.")
    if frame_ms is not None and (not math.isfinite(frame_ms) or frame_ms <= 0):
        raise ValueError("Frame duration must be positive and finite.")
    if available_bytes is not None and available_bytes < 0:
        raise ValueError("Available memory cannot be negative.")
    if source_points is not None and source_points < 0:
        raise ValueError("Source point count cannot be negative.")
    ceiling = min(2_000_000, max(10_000, viewport_pixels * 2))
    if available_bytes is not None:
        ceiling = min(ceiling, available_bytes // (128 * 4))
    if source_points is not None:
        ceiling = min(ceiling, source_points)
    if memory_pressure >= 0.85:
        target = int(previous * 0.5)
    elif moving or (frame_ms is not None and frame_ms > 33.3):
        target = int(previous * 0.75)
    elif frame_ms is not None and frame_ms < 22:
        target = max(previous + 1, int(previous * 1.10))
    else:
        target = previous
    # First view starts small; telemetry subsequently determines refinement.
    if previous == 0 and ceiling:
        target = min(100_000, ceiling)
    points = max(0, min(target, ceiling))
    return ViewBudget(points, 6.0 if moving or memory_pressure >= 0.85 else 2.0,
                      not moving and memory_pressure < 0.7 and points > 0)
