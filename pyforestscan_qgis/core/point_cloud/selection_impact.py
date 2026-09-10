"""One selection-impact policy shared by the managed worker and compact UI."""
from dataclasses import dataclass
import math


@dataclass(frozen=True)
class SelectionImpact:
    level: str
    selected_points: int
    source_points: int
    fraction: float
    message: str
    requires_confirmation: bool


def selection_impact(selected_points, source_points):
    if (type(selected_points) is not int or type(source_points) is not int
            or selected_points < 0 or source_points < 0
            or selected_points > source_points):
        raise ValueError("Selection impact requires valid source-point counts.")
    fraction = selected_points / source_points if source_points else 0.0
    if not math.isfinite(fraction):
        raise ValueError("Selection impact fraction must be finite.")
    if selected_points > 10_000_000 or fraction > .25:
        return SelectionImpact("CONFIRM", selected_points, source_points, fraction,
            "Very large selection: confirmation required before applying an edit", True)
    if selected_points > 1_000_000 or fraction > .10:
        return SelectionImpact("REVIEW", selected_points, source_points, fraction,
            "Large selection: review before applying an edit", False)
    return SelectionImpact("ROUTINE" if selected_points else "EMPTY",
                           selected_points, source_points, fraction, "", False)


def selection_impact_suffix(selected_points, source_points):
    message = selection_impact(selected_points, source_points).message
    return f" | {message}" if message else ""
