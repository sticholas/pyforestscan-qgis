"""Validated presentation-only focus policy for authoritative object selections."""
from __future__ import annotations

from enum import Enum


MAX_EXACT_RENDER_ID = (1 << 53) - 1


class ObjectFocusMode(str, Enum):
    SHOW_ALL = "SHOW_ALL"
    FADE_OTHERS = "FADE_OTHERS"
    ISOLATE = "ISOLATE"


def normalize_object_focus_mode(value: object) -> str:
    """Return a known renderer mode or reject untrusted workspace state."""
    try:
        return ObjectFocusMode(value).value
    except (TypeError, ValueError) as exc:
        raise ValueError("Unknown object focus mode.") from exc


def object_focus_command(mode: object, active_object: dict | None = None,
                         selection: dict | None = None) -> dict:
    """Build a display command without transferring selection authority."""
    value = normalize_object_focus_mode(mode)
    command = {"action": "object_focus", "mode": value,
               "scope": "AUTHORITATIVE_ACTIVE_OBJECT_SELECTION"}
    if value == ObjectFocusMode.SHOW_ALL.value:
        return command
    active_object = active_object or {}
    selection = selection or {}
    field = active_object.get("field")
    object_id = active_object.get("object_id")
    if not isinstance(field, str) or not field or not selection.get("resolved_point_count"):
        raise ValueError("Select an exact catalog object before changing object focus.")
    try:
        exact_id = int(object_id)
    except (TypeError, ValueError) as exc:
        raise ValueError("Active object ID is not an exact renderer integer.") from exc
    if exact_id != object_id or abs(exact_id) > MAX_EXACT_RENDER_ID:
        raise ValueError("Object focus requires an ID within the renderer's exact integer range.")
    command.update(field=field, object_id=str(exact_id))
    return command


def object_focus_summary(mode: object, active_object: dict | None = None) -> str:
    value = normalize_object_focus_mode(mode)
    labels = {
        ObjectFocusMode.SHOW_ALL.value: "Showing all points",
        ObjectFocusMode.FADE_OTHERS.value: "Other points faded",
        ObjectFocusMode.ISOLATE.value: "Selected object isolated",
    }
    active_object = active_object or {}
    if value == ObjectFocusMode.SHOW_ALL.value or "object_id" not in active_object:
        return labels[value]
    return f"{labels[value]} | {active_object.get('field')} = {active_object['object_id']}"
