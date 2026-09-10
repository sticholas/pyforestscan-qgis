"""Validated transient cursor projection across source-linked point-cloud views."""
from __future__ import annotations

from dataclasses import asdict, is_dataclass
import math
import re

from .workspace import AreaGeometry, SliceGeometry, ViewType


CURSOR_AUTHORITY = (
    "ORIGINAL_SOURCE_RECORD_COORDINATES",
    "DISPLAYED_SOURCE_RECORD_COORDINATES",
)


def _point(value, label):
    values = tuple(value) if isinstance(value, (list, tuple)) else ()
    if (len(values) != 3 or any(type(item) not in (int, float)
                                or not math.isfinite(item) for item in values)):
        raise ValueError(f"{label} requires three finite coordinates.")
    return tuple(float(item) for item in values)


def validate_linked_cursor(payload, source_sha256, origin_view_id):
    """Normalize one renderer hover without granting it edit authority."""
    if (not re.fullmatch(r"[0-9a-f]{64}", source_sha256 or "")
            or not isinstance(origin_view_id, str) or not origin_view_id):
        raise ValueError("Linked cursor requires verified source and view identities.")
    if not isinstance(payload, dict) or type(payload.get("sequence")) is not int:
        raise ValueError("Linked cursor telemetry is invalid.")
    if not 0 <= payload["sequence"] <= 2**53-1 or type(payload.get("active")) is not bool:
        raise ValueError("Linked cursor sequence or state is invalid.")
    result = {
        "sequence": payload["sequence"],
        "active": payload["active"],
        "source_sha256": source_sha256,
        "origin_view_id": origin_view_id,
    }
    if not payload["active"]:
        return result
    result["source_xyz"] = _point(payload.get("source_xyz"), "Linked cursor source point")
    result["display_xyz"] = _point(payload.get("display_xyz"), "Linked cursor display point")
    authority = payload.get("authority")
    if authority not in CURSOR_AUTHORITY:
        raise ValueError("Linked cursor coordinate authority is invalid.")
    result["authority"] = authority
    for key in ("height_above_ground", "distance_along", "cross_track"):
        value = payload.get(key)
        if value is not None:
            if type(value) not in (int, float) or not math.isfinite(value):
                raise ValueError(f"Linked cursor {key.replace('_', ' ')} is invalid.")
            result[key] = float(value)
    classification = payload.get("classification")
    if classification is not None:
        if type(classification) is not int or not 0 <= classification <= 255:
            raise ValueError("Linked cursor classification is invalid.")
        result["classification"] = classification
    return result


def _view_payload(view):
    if is_dataclass(view):
        return asdict(view)
    if not isinstance(view, dict):
        raise ValueError("Linked cursor target view is invalid.")
    return view


def _inside_ring(x, y, ring):
    inside = False
    for first, second in zip(ring, (*ring[1:], ring[0])):
        if ((first[1] > y) != (second[1] > y)
                and x < (second[0]-first[0])*(y-first[1])
                /(second[1]-first[1])+first[0]):
            inside = not inside
    return inside


def _area_contains(geometry, x, y):
    area = AreaGeometry(**geometry)
    if area.shape == "CIRCLE":
        return math.hypot(x-area.center[0], y-area.center[1]) <= area.radius
    if area.shape == "POLYGON":
        return _inside_ring(x, y, area.vertices[:-1])
    return (abs(x-area.center[0]) <= area.width/2
            and abs(y-area.center[1]) <= area.height/2)


def linked_cursor_command(cursor, view):
    """Project one validated source record into a linked target view."""
    target = _view_payload(view)
    view_id = target.get("view_id")
    try:
        kind = ViewType(target.get("view_type"))
    except (TypeError, ValueError) as error:
        raise ValueError("Linked cursor target view type is invalid.") from error
    if not isinstance(view_id, str) or not view_id:
        raise ValueError("Linked cursor target view identity is invalid.")
    base = {"action": "linked_cursor", "view_id": view_id,
            "source_sha256": cursor["source_sha256"],
            "origin_view_id": cursor["origin_view_id"],
            "sequence": cursor["sequence"], "visible": False}
    if not cursor["active"]:
        return base
    x, y, z = cursor["source_xyz"]
    if kind == ViewType.AREA_DETAIL and not _area_contains(target.get("geometry") or {}, x, y):
        return base
    if kind != ViewType.VERTICAL_SLICE:
        return {**base, "visible": True, "display_xyz": (x, y, z),
                "source_xyz": (x, y, z),
                "height_above_ground": cursor.get("height_above_ground"),
                "classification": cursor.get("classification"),
                "authority": cursor["authority"]}
    profile = SliceGeometry(**(target.get("geometry") or {}))
    hag = cursor.get("height_above_ground")
    if profile.vertical_axis == "HeightAboveGround" and hag is None:
        return base
    along, vertical, cross = profile.local(x, y, z, hag=hag)
    if abs(cross) > profile.thickness/2:
        return base
    if (profile.vertical_limits is not None
            and not profile.vertical_limits[0] <= vertical <= profile.vertical_limits[1]):
        return base
    display = ((along, cross, vertical)
               if profile.display_projection == "PROFILE_DISTANCE" else (x, y, vertical))
    return {**base, "visible": True, "display_xyz": display,
            "source_xyz": (x, y, z), "distance_along": along,
            "cross_track": cross, "vertical_axis": profile.vertical_axis,
            "vertical_value": vertical, "height_above_ground": hag,
            "classification": cursor.get("classification"),
            "authority": cursor["authority"]}


def linked_cursor_summary(command):
    """Compact profile readout plus complete source-coordinate hover help."""
    if not command.get("visible") or "distance_along" not in command:
        return {"text": "", "details": ""}
    axis = "HAG" if command["vertical_axis"] == "HeightAboveGround" else "Elevation"
    x, y, z = command["source_xyz"]
    details = [
        f"Source X: {x:,.3f}", f"Source Y: {y:,.3f}", f"Source Z: {z:,.3f}",
        f"Distance along profile: {command['distance_along']:,.3f}",
        f"Cross-track distance: {command['cross_track']:+,.3f}",
        f"{axis}: {command['vertical_value']:,.3f}",
    ]
    if command.get("height_above_ground") is not None and axis != "HAG":
        details.append(f"HAG: {command['height_above_ground']:,.3f}")
    if command.get("classification") is not None:
        details.append(f"Classification: {command['classification']}")
    scope = ("Original source-record coordinates carried by the profile cache."
             if command["authority"] == "ORIGINAL_SOURCE_RECORD_COORDINATES" else
             "Coordinates of the displayed source record; hover does not create an edit.")
    details.append(scope)
    return {"text": (f"Distance {command['distance_along']:,.3f} | "
                     f"{axis} {command['vertical_value']:,.3f}"),
            "details": "\n".join(details)}
