"""Bounded point-budget controller independent of renderer and QGIS."""
from dataclasses import dataclass
import math


def system_memory_pressure():
    """Read system pressure, not invented GPU availability; unavailable is None."""
    import os
    if os.name != 'nt':
        return None
    import ctypes
    from ctypes import wintypes
    class Status(ctypes.Structure):
        _fields_ = [('length', wintypes.DWORD), ('load', wintypes.DWORD),
                    *[(name, ctypes.c_ulonglong) for name in ('total', 'available', 'page_total',
                       'page_available', 'virtual_total', 'virtual_available', 'extended')]]
    status = Status()
    status.length = ctypes.sizeof(status)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
        return None
    return {'pressure': status.load / 100, 'available_bytes': status.available}


@dataclass(frozen=True)
class ViewBudget:
    points: int
    screen_error: float
    prefetch: bool
    floor: int = 0
    ceiling: int = 0
    source_class: str = "UNKNOWN"


def next_view_budget(previous: int, *, viewport_pixels: int, moving: bool,
                     frame_ms: float | None = None, memory_pressure: float = 0.0,
                     available_bytes: int | None = None, source_points: int | None = None,
                     root_points: int = 0, velocity: float = 0.0,
                     quality: str = "Automatic") -> ViewBudget:
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
    if root_points < 0 or not math.isfinite(velocity) or velocity < 0:
        raise ValueError("Invalid root point count or camera velocity.")
    if quality not in ("Automatic", "Performance", "Balanced", "High Detail"):
        raise ValueError("Unknown viewer quality preset.")
    multiplier = {"Performance": 1.5, "High Detail": 3}.get(quality, 2)
    ceiling = int(min(2_000_000, max(10_000, viewport_pixels * multiplier)))
    if available_bytes is not None:
        ceiling = min(ceiling, available_bytes // (128 * 4))
    if source_points is not None:
        ceiling = min(ceiling, source_points)
    source_class = ("UNKNOWN" if source_points is None else "TINY" if source_points <= 100_000
                    else "SMALL" if source_points <= 3_000_000 else "MEDIUM" if source_points <= 20_000_000
                    else "LARGE" if source_points <= 200_000_000 else "MASSIVE_INDEXED")
    # Admission is whole-node in Potree. A budget below the root renders nothing.
    floor = min(ceiling, max(root_points, min(500_000, max(100_000, viewport_pixels))))
    fits = source_points is not None and source_points <= ceiling
    if fits:
        floor = ceiling
    speed = min(1.0, velocity) if moving else 0.0
    target = int(ceiling * (1 - .25 * speed))
    if memory_pressure >= .85 or (frame_ms is not None and frame_ms > 40):
        target = int(previous * .9)
    # Smooth changes, with a non-negotiable structural floor after root discovery.
    step = max(1, int(max(previous, 100_000) * .08))
    points = min(ceiling, max(floor, min(previous + step, max(previous - step, target))))
    return ViewBudget(points, 12.0 + 6.0 * speed, False, floor, ceiling, source_class)
