"""QGIS-free visualization contracts for point-cloud attributes and scale."""

from __future__ import annotations

from dataclasses import dataclass
import math

ATTRIBUTE_MODES = (
    "RGB", "Classification", "Elevation", "Height Above Ground", "Intensity",
    "Return Number", "Number of Returns", "Scan Angle", "Point Source ID",
    "GPS Time", "User Data",
)
ATTRIBUTE_DIMENSIONS = {
    "RGB": ("Red", "Green", "Blue"),
    "Classification": ("Classification",),
    "Elevation": ("Z",),
    "Height Above Ground": ("HeightAboveGround",),
    "Intensity": ("Intensity",),
    "Return Number": ("ReturnNumber",),
    "Number of Returns": ("NumberOfReturns",),
    "Scan Angle": ("ScanAngleRank", "ScanAngle"),
    "Point Source ID": ("PointSourceId", "PointSourceID"),
    "GPS Time": ("GpsTime", "GPSTime"),
    "User Data": ("UserData",),
}

@dataclass(frozen=True)
class RenderState:
    """Presentation state shared by overview, detail and profile views."""
    color_mode: str = "Classification"
    display_range: DisplayRange | None = None
    visible_classes: tuple[int, ...] | None = None
    point_style: str = "Circular"
    point_size: int = 0
    quality: str = "Automatic"
    vertical_slice: tuple[float, float] | None = None
    display_filters: tuple[tuple[str, object], ...] = ()

    def identity(self):
        return (self.color_mode, self.display_range, self.visible_classes,
                self.point_style, self.point_size, self.quality,
                self.vertical_slice, self.display_filters)

def attribute_aliases(mode):
    """Return canonical source dimensions for one display mode."""
    return ATTRIBUTE_DIMENSIONS.get(mode, ())

def resolve_attribute(mode, dimensions):
    """Resolve a display mode to the first matching source dimension."""
    names = {str(value) for value in dimensions}
    aliases = attribute_aliases(mode)
    if mode == "RGB" and not all(name in names for name in aliases):
        return None
    return next((name for name in aliases if name in names), None)

def histogram(values, *, bins=16, minimum=None, maximum=None):
    """Create a bounded display-sample histogram with explicit endpoints."""
    numbers = [float(value) for value in values if math.isfinite(float(value))]
    if not numbers:
        return {"minimum": None, "maximum": None, "bins": ()}
    bins = max(1, min(128, int(bins)))
    low = min(numbers) if minimum is None else float(minimum)
    high = max(numbers) if maximum is None else float(maximum)
    if not math.isfinite(low) or not math.isfinite(high) or low > high:
        raise ValueError("Histogram extent must be finite and ascending.")
    if low == high:
        return {"minimum": low, "maximum": high, "bins": (len(numbers),)}
    counts = [0] * bins
    width = (high - low) / bins
    for value in numbers:
        index = int((value - low) / width)
        counts[max(0, min(bins - 1, index))] += 1
    return {"minimum": low, "maximum": high, "bins": tuple(counts)}

def numeric_summary(values):
    """Return cheap, sample-labelled descriptive values for analytics."""
    numbers = sorted(float(value) for value in values if math.isfinite(float(value)))
    if not numbers:
        return {"count": 0, "minimum": None, "maximum": None, "p25": None, "median": None, "p75": None, "p95": None}
    def percentile(percent):
        position = (len(numbers) - 1) * percent / 100.0
        lower, upper = math.floor(position), math.ceil(position)
        return numbers[lower] if lower == upper else numbers[lower] + (numbers[upper] - numbers[lower]) * (position - lower)
    return {"count": len(numbers), "minimum": numbers[0], "maximum": numbers[-1], "p25": percentile(25), "median": percentile(50), "p75": percentile(75), "p95": percentile(95)}

@dataclass(frozen=True)
class DisplayRange:
    minimum: float
    maximum: float
    mode: str = "AUTO"

    def __post_init__(self):
        if not all(math.isfinite(float(value)) for value in (self.minimum, self.maximum)):
            raise ValueError("Display range values must be finite.")
        if float(self.minimum) > float(self.maximum):
            raise ValueError("Display range minimum exceeds maximum.")
        if self.mode not in {"AUTO", "ROBUST", "MANUAL"}:
            raise ValueError("Display range mode is unsupported.")

    def clamp(self, value):
        return min(float(self.maximum), max(float(self.minimum), float(value)))

def available_attribute_modes(dimensions):
    """Return display modes supported by the supplied source dimensions."""
    names = {str(value) for value in dimensions}
    return tuple(mode for mode in ATTRIBUTE_MODES
                 if (all(name in names for name in ATTRIBUTE_DIMENSIONS[mode])
                     if mode == "RGB" else
                     any(name in names for name in ATTRIBUTE_DIMENSIONS[mode])))
def nice_tick_step(span, target_ticks=6):
    """Choose a 1/2/5 * 10^n interval for readable axis labels."""
    span = float(span)
    if not math.isfinite(span) or span <= 0:
        raise ValueError("Axis span must be finite and positive.")
    target = max(2, int(target_ticks))
    raw = span / target
    exponent = math.floor(math.log10(raw))
    scale = 10.0 ** exponent
    normalized = raw / scale
    factor = 1.0 if normalized <= 1.0 else 2.0 if normalized <= 2.0 else 5.0 if normalized <= 5.0 else 10.0
    return factor * scale

def nice_ticks(minimum, maximum, target_ticks=6):
    """Return stable, human-readable ticks covering an axis extent."""
    minimum, maximum = float(minimum), float(maximum)
    if not all(math.isfinite(value) for value in (minimum, maximum)) or minimum > maximum:
        raise ValueError("Axis extent must be finite and ascending.")
    if minimum == maximum:
        return (minimum,)
    step = nice_tick_step(maximum - minimum, target_ticks)
    start = math.ceil(minimum / step - 1e-12) * step
    end = math.floor(maximum / step + 1e-12) * step
    count = max(0, int(round((end - start) / step)))
    ticks = tuple(round(start + index * step, 12) for index in range(count + 1))
    return ticks or (minimum, maximum)

def display_range(values, *, mode="AUTO", lower_percentile=2.0, upper_percentile=98.0):
    """Calculate an explicit range without requiring NumPy or a renderer."""
    numbers = sorted(float(value) for value in values if math.isfinite(float(value)))
    if not numbers:
        raise ValueError("At least one finite value is required for a display range.")
    if mode == "MANUAL":
        raise ValueError("Manual display ranges must be constructed as DisplayRange.")
    if mode == "ROBUST":
        if not 0 <= lower_percentile <= upper_percentile <= 100:
            raise ValueError("Percentiles must be ordered between 0 and 100.")
        def percentile(percent):
            position = (len(numbers) - 1) * percent / 100.0
            lower = math.floor(position)
            upper = math.ceil(position)
            if lower == upper:
                return numbers[lower]
            fraction = position - lower
            return numbers[lower] + (numbers[upper] - numbers[lower]) * fraction
        low, high = percentile(lower_percentile), percentile(upper_percentile)
    else:
        low, high = numbers[0], numbers[-1]
    if low == high:
        padding = max(abs(low) * 0.01, 1.0)
        low, high = low - padding, high + padding
    return DisplayRange(low, high, mode)

@dataclass(frozen=True)
class LegendModel:
    title: str
    units: str = ""
    display_range: DisplayRange | None = None
    categories: tuple[tuple[str, str], ...] = ()

    @property
    def label(self):
        return f"{self.title} ({self.units})" if self.units else self.title
