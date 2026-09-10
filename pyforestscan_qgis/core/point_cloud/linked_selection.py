"""Value-only selection adapters: local display state is never implicit authority."""
import math
from .linked_query import area_ring
from .workspace import AreaGeometry, SliceGeometry


def box_selection_error(view_type, depth):
    """Return why an explicit box volume cannot be armed, or an empty string."""
    if view_type == "VERTICAL_SLICE":
        return ""
    if view_type not in ("OVERVIEW_3D", "AREA_DETAIL"):
        return "Box Select is unavailable in this view."
    if not isinstance(depth, dict) or not any(depth.get(key) is not None
                                               for key in ("z_filter", "hag_filter")):
        return "Box Select requires Elevation or HAG selection limits before drawing its XY footprint."
    return ""


def profile_line_selection_error(view_type):
    """Return why Above/Below Line cannot be armed, or an empty string."""
    return "" if view_type == "VERTICAL_SLICE" else (
        "Select Above/Below Line is available only in a Vertical Slice.")


def selection_limit_values(values):
    """Validate saved UI limits, retaining inverted bounds for visible correction."""
    if not isinstance(values, dict) or set(values) - {"z_filter", "hag_filter"}:
        raise ValueError("Invalid saved selection limits.")
    result = {}
    for key, limits in values.items():
        if (not isinstance(limits, (tuple, list)) or len(limits) != 2 or
                any(isinstance(v, bool) or not isinstance(v, (int, float)) or
                    not math.isfinite(v) for v in limits)):
            raise ValueError("Selection heights must be two finite numbers.")
        result[key] = list(limits)
    return result


def linked_constraints(view, *, profile_geometry=None, select_filtered=False,
                       display=None, z_filter=None, hag_filter=None):
    kind = view["view_type"]
    values = {"view_id": view["view_id"], "view_name": view["title"],
              "z_filter": z_filter, "hag_filter": hag_filter,
              "depth_mode": "CUSTOM_DEPTH_RANGE" if z_filter is not None or hag_filter is not None else "FULL_COLUMN"}
    if select_filtered:
        display = display or {}
        values["classification_filter"] = display.get("classes")
        # Intersect, never replace a stricter explicit editing depth constraint.
        limits = display.get("height_filter")
        if limits is not None:
            key = "hag_filter" if kind == "VERTICAL_SLICE" and view["geometry"].get("vertical_axis") == "HeightAboveGround" else "z_filter"
            previous = values[key]
            values[key] = limits if previous is None else (
                max(limits[0], previous[0]), min(limits[1], previous[1]))
    if kind == "AREA_DETAIL":
        AreaGeometry(**view["geometry"])
        values["clip_geometry"] = area_ring(view["geometry"])
    elif kind == "VERTICAL_SLICE":
        profile = SliceGeometry(**view["geometry"])
        values.update(profile_a=profile.a, profile_b=profile.b,
                      profile_path=profile.points if profile.path else None,
                      profile_thickness=profile.thickness, profile_axis=profile.vertical_axis,
                      profile_geometry=profile_geometry, depth_mode="SLICE_CORRIDOR")
        if profile.vertical_limits is not None:
            key = "hag_filter" if profile.vertical_axis == "HeightAboveGround" else "z_filter"
            previous = values[key]
            values[key] = profile.vertical_limits if previous is None else (
                max(previous[0], profile.vertical_limits[0]),
                min(previous[1], profile.vertical_limits[1]))
    elif kind != "OVERVIEW_3D":
        raise ValueError("Unknown linked view type.")
    return values
