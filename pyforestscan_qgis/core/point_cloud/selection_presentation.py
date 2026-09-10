"""QGIS-free labels and defaults for authoritative selection controls."""
from __future__ import annotations

import math


SELECTION_COMBINE_OPTIONS = (
    ("Start new selection", "REPLACE"),
    ("Add to selection", "ADD"),
    ("Remove from selection", "SUBTRACT"),
)


def selection_combine_summary(mode):
    labels = {value: label for label, value in SELECTION_COMBINE_OPTIONS}
    try:
        return labels[str(mode).upper()]
    except KeyError as error:
        raise ValueError("Unsupported selection combination mode.") from error


def _finite_range(value):
    if (not isinstance(value, (list, tuple)) or len(value) != 2
            or any(type(item) not in (int, float) or not math.isfinite(item)
                   for item in value)
            or value[0] >= value[1]):
        return None
    return float(value[0]), float(value[1])


def recommended_height_range(kind, *, source_bounds=None, profile_geometry=None,
                             display_range=None):
    """Choose a useful initial range without inventing source measurements."""
    if kind not in ("z_filter", "hag_filter"):
        raise ValueError("Height range kind must be elevation or HAG.")
    geometry = profile_geometry if isinstance(profile_geometry, dict) else {}
    axis = geometry.get("vertical_axis", "Z")
    profile_limits = _finite_range(geometry.get("vertical_limits"))
    if profile_limits and ((kind == "z_filter" and axis == "Z")
                           or (kind == "hag_filter" and axis == "HeightAboveGround")):
        return profile_limits
    if kind == "z_filter" and isinstance(source_bounds, dict):
        bounds = _finite_range((source_bounds.get("minz"), source_bounds.get("maxz")))
        if bounds:
            return bounds
        lower, upper = source_bounds.get("min"), source_bounds.get("max")
        if (isinstance(lower, (list, tuple)) and isinstance(upper, (list, tuple))
                and len(lower) >= 3 and len(upper) >= 3):
            bounds = _finite_range((lower[2], upper[2]))
            if bounds:
                return bounds
    if ((kind == "hag_filter" and axis == "HeightAboveGround")
            or (kind == "z_filter" and axis == "Z")):
        visible = _finite_range(display_range)
        if visible:
            return visible
    return (0.0, 50.0)


def selection_height_summary(kind, limits, *, view_name="active view"):
    interval = _finite_range(limits)
    if not interval:
        return f"{view_name} | All heights included"
    axis = "Elevation Z" if kind == "z_filter" else "Height above ground"
    return (f"{view_name} | {axis}: {interval[0]:g} to {interval[1]:g} "
            "source height units | Applies to the next selection")
