"""QGIS-free presentation contracts for the linked profile workbench."""
from __future__ import annotations

from .las_classification import classification_counts_summary
from .workspace import SliceGeometry


def profile_coordinates(profile, x, y, np):
    """Vectorized closest-segment distance/cross-track projection."""
    geometry = profile if isinstance(profile, SliceGeometry) else SliceGeometry(**profile)
    x = np.asarray(x, dtype="f8")
    y = np.asarray(y, dtype="f8")
    best_distance = np.full(len(x), np.inf, dtype="f8")
    best_along = np.zeros(len(x), dtype="f8")
    best_cross = np.zeros(len(x), dtype="f8")
    cumulative = 0.0
    for first, second in zip(geometry.points, geometry.points[1:]):
        dx, dy = second[0]-first[0], second[1]-first[1]
        length = (dx*dx+dy*dy)**.5
        fraction = np.clip(((x-first[0])*dx+(y-first[1])*dy)/(length*length), 0, 1)
        px, py = first[0]+fraction*dx, first[1]+fraction*dy
        distance = (x-px)**2+(y-py)**2
        replace = distance < best_distance
        best_distance[replace] = distance[replace]
        best_along[replace] = cumulative+fraction[replace]*length
        cross = (-(x-first[0])*dy+(y-first[1])*dx)/length
        best_cross[replace] = cross[replace]
        cumulative += length
    return best_along, best_cross, best_distance


def profile_membership(profile, x, y, np):
    """Exact flat-ended, round-joined corridor membership without Shapely."""
    geometry = profile if isinstance(profile, SliceGeometry) else SliceGeometry(**profile)
    x = np.asarray(x, dtype="f8")
    y = np.asarray(y, dtype="f8")
    inside = np.zeros(len(x), dtype=bool)
    radius2 = (geometry.thickness/2)**2
    for first, second in zip(geometry.points, geometry.points[1:]):
        dx, dy = second[0]-first[0], second[1]-first[1]
        length2 = dx*dx+dy*dy
        fraction = ((x-first[0])*dx+(y-first[1])*dy)/length2
        px, py = first[0]+fraction*dx, first[1]+fraction*dy
        inside |= ((fraction >= 0) & (fraction <= 1) &
                   ((x-px)**2+(y-py)**2 <= radius2))
    for vertex in geometry.points[1:-1]:
        inside |= (x-vertex[0])**2+(y-vertex[1])**2 <= radius2
    return inside


def profile_corridor_shape(profile, shapely):
    """Exact flat-ended corridor shared by bounded queries and tests."""
    geometry = profile if isinstance(profile, SliceGeometry) else SliceGeometry(**profile)
    return shapely.LineString(geometry.points).buffer(
        geometry.thickness/2, cap_style="flat", join_style="round")


def profile_query_envelopes(profile):
    geometry = profile if isinstance(profile, SliceGeometry) else SliceGeometry(**profile)
    margin = geometry.thickness/2
    return tuple((min(a[0],b[0])-margin,min(a[1],b[1])-margin,
                  max(a[0],b[0])+margin,max(a[1],b[1])+margin)
                 for a,b in zip(geometry.points,geometry.points[1:]))


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
        f"Path segments: {len(profile.points)-1}.",
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


def profile_footprint_command(views, *, active_view_id="", limit=100):
    """Serialize bounded profile footprints without exposing workspace authority."""
    if type(limit) is not int or not 1 <= limit <= 100:
        raise ValueError("Profile footprint limit must be between 1 and 100.")
    values = views.values() if isinstance(views, dict) else views
    footprints = []
    for raw in values:
        view_type = getattr(raw, "view_type", None)
        view_type = getattr(view_type, "value", view_type)
        if view_type != "VERTICAL_SLICE":
            continue
        geometry = getattr(raw, "geometry", None)
        profile = SliceGeometry(**geometry)
        view_id = getattr(raw, "view_id", "")
        title = getattr(raw, "title", "")
        if not isinstance(view_id, str) or not view_id or not isinstance(title, str):
            raise ValueError("Profile footprint requires a linked-view identity and title.")
        footprints.append({"view_id": view_id, "title": title,
                           "active": view_id == active_view_id,
                           "corridor": profile.corridor(),
                           "path": profile.points,
                           "segment_corridors": profile.segment_corridors()})
        if len(footprints) == limit:
            break
    return {"action": "workspace_views", "profiles": footprints}
