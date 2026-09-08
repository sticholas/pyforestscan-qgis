"""Persist real viewer state using the Phase 34A1 non-destructive session."""
from __future__ import annotations
import copy
import math
from pathlib import Path
from .session import PointCloudEditSession, SourceIdentity


class ViewerSourceChanged(ValueError):
    def __init__(self, source):
        super().__init__("The source has changed since this editing session was saved.")
        self.source = source


def validate_view_state(state):
    camera = copy.deepcopy(state.get("camera", {}))
    position = camera.get("position", ())
    scalars = [*position, camera.get("yaw"), camera.get("pitch"), camera.get("radius")]
    if len(position) != 3 or any(type(v) not in (int, float) or not math.isfinite(v) for v in scalars):
        raise ValueError("Session camera must contain finite position, yaw, pitch and radius.")
    if camera["radius"] <= 0:
        raise ValueError("Session camera radius must be positive.")
    mode = state.get("mode", "Classification")
    if mode not in ("Classification", "Elevation", "RGB", "Intensity"):
        raise ValueError("Unsupported session render mode.")
    classes = state.get("classes")
    if classes is not None and (not isinstance(classes, (list, tuple)) or
            any(type(c) is not int or not 0 <= c <= 255 for c in classes)):
        raise ValueError("Session class visibility must use LAS class values 0-255.")
    height = state.get("height_filter")
    if height is not None and (not isinstance(height, (list, tuple)) or len(height) != 2 or
            any(type(v) not in (int, float) or not math.isfinite(v) for v in height) or height[0] >= height[1]):
        raise ValueError("Invalid session height filter.")
    return {"camera": camera, "mode": mode, "classes": list(classes) if classes is not None else None,
            "height_filter": list(height) if height is not None else None}


def view_state_matches(actual, expected):
    """Only acknowledge restoration after the renderer reports matching values."""
    try:
        actual, expected = validate_view_state(actual), validate_view_state(expected)
    except (ValueError, TypeError, AttributeError):
        return False
    if any(actual[key] != expected[key] for key in ("mode", "classes", "height_filter")):
        return False
    a, b = actual["camera"], expected["camera"]
    return (all(math.isclose(x, y, rel_tol=0, abs_tol=1e-5) for x, y in zip(a["position"], b["position"])) and
            all(math.isclose(a[key], b[key], rel_tol=0, abs_tol=1e-5) for key in ("yaw", "pitch", "radius")))


def save_view_session(path, source, state, *, existing=None, source_crs="", dimensions=(),
                      cache_identity=None, cancelled=lambda: False):
    values = validate_view_state(state)
    identity = SourceIdentity.capture(source, cancelled=cancelled)
    if existing is not None and existing.source != identity:
        raise ViewerSourceChanged(existing.source.path)
    session = copy.deepcopy(existing) if existing is not None else PointCloudEditSession(
        identity, source_crs, tuple(dimensions))
    session.camera = values["camera"]
    session.visibility.update(render_mode=values["mode"], quality="AUTOMATIC",
                              viewer_backend="ISOLATED_WEBENGINE_POTREE",
                              cache_identity=copy.deepcopy(cache_identity or {}))
    session.filters.update(classes=values["classes"], z=values["height_filter"])
    if cancelled():
        raise InterruptedError("Session save cancelled.")
    session.save(path)
    return session


def load_view_session(path, *, cancelled=lambda: False):
    session = PointCloudEditSession.load(path, verify_source=False)
    try:
        session.source.verify(cancelled=cancelled)
    except (ValueError, OSError) as error:
        raise ViewerSourceChanged(session.source.path) from error
    validate_view_state(session_view_state(session))
    return session


def session_view_state(session):
    return {"camera": copy.deepcopy(session.camera),
            "mode": session.visibility.get("render_mode", "Classification"),
            "classes": copy.deepcopy(session.filters.get("classes")),
            "height_filter": copy.deepcopy(session.filters.get("z"))}
