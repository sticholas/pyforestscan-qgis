"""QGIS-free presentation contracts for the linked profile workbench."""
from __future__ import annotations

from .las_classification import classification_counts_summary
from .workspace import SliceGeometry


def profile_workbench_summary(geometry, query_result=None):
    """Return compact, honest labels for one source-resolved profile query."""
    profile = SliceGeometry(**geometry)
    result = query_result if isinstance(query_result, dict) else {}
    axis = "height above ground" if profile.vertical_axis == "HeightAboveGround" else "elevation"
    count = result.get("source_points")
    displayed = result.get("display_points")
    counts = result.get("classification_counts") or ()
    if type(count) is not int or count < 0:
        count = None
    if type(displayed) is not int or displayed < 0:
        displayed = None
    count_text = f"{count:,} points" if count is not None else "Loading points"
    axis_text = "HAG" if profile.vertical_axis == "HeightAboveGround" else "elevation"
    text = (f"{count_text} | X distance | Y {axis_text} | "
            f"{profile.thickness:g} XY wide")
    details = [
        f"Profile length: {profile.length:g} source XY units.",
        f"Corridor width: {profile.thickness:g} source XY units.",
        f"Vertical axis: {axis}.",
    ]
    if count is not None:
        details.append(f"Authoritative source points in corridor: {count:,}.")
    if displayed is not None:
        details.append(f"Display points: {displayed:,}; displayed samples are not edit authority.")
    if counts:
        details.append("Source classification distribution: " +
                       classification_counts_summary(counts, limit=6) + ".")
    return {"text": text, "details": "\n".join(details), "axis": axis,
            "source_points": count, "display_points": displayed}
