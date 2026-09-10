"""Source-bound scene annotations for linked point-cloud views."""
from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
import math
import re
from uuid import uuid4

from .measurement import MeasurementAnchor, resolve_source_anchors


MAX_ANNOTATIONS = 500
MAX_ANNOTATION_TITLE = 80
MAX_ANNOTATION_NOTE = 2000


def _text(value, label, maximum, *, required=False):
    if not isinstance(value, str):
        raise ValueError(f"Annotation {label} must be text.")
    result = value.strip()
    if required and not result:
        raise ValueError(f"Annotation {label} is required.")
    if len(result) > maximum or any(ord(char) < 32 and char not in "\n\t" for char in result):
        raise ValueError(f"Annotation {label} is invalid or exceeds {maximum:,} characters.")
    return result


def _timestamp(value, label):
    if not isinstance(value, str) or not value:
        raise ValueError(f"Annotation {label} is invalid.")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError(f"Annotation {label} is invalid.") from error
    if parsed.tzinfo is None:
        raise ValueError(f"Annotation {label} must include a timezone.")
    return value


@dataclass(frozen=True)
class SceneAnnotation:
    annotation_id: str
    source_sha256: str
    source_crs: str
    title: str
    note: str
    anchor: MeasurementAnchor
    resolution_seconds: float
    source_point_count: int
    created_at: str
    updated_at: str
    addressing: str = "FULL_RESOLUTION_ORIGINAL_SOURCE_POINT_RESOLUTION"
    kind: str = "SOURCE_POINT_ANNOTATION"

    def __post_init__(self):
        if (not isinstance(self.annotation_id, str) or not self.annotation_id
                or len(self.annotation_id) > 128
                or not re.fullmatch(r"[0-9a-f]{64}", self.source_sha256)
                or not isinstance(self.source_crs, str) or not self.source_crs
                or self.addressing != "FULL_RESOLUTION_ORIGINAL_SOURCE_POINT_RESOLUTION"
                or self.kind != "SOURCE_POINT_ANNOTATION"):
            raise ValueError("Annotation source identity is invalid.")
        object.__setattr__(self, "title",
                           _text(self.title, "title", MAX_ANNOTATION_TITLE, required=True))
        object.__setattr__(self, "note", _text(self.note, "note", MAX_ANNOTATION_NOTE))
        if not isinstance(self.anchor, MeasurementAnchor):
            raise ValueError("Annotation requires one resolved source anchor.")
        if (type(self.resolution_seconds) not in (int, float)
                or not math.isfinite(self.resolution_seconds) or self.resolution_seconds < 0
                or type(self.source_point_count) is not int or self.source_point_count <= 0):
            raise ValueError("Annotation resolution evidence is invalid.")
        _timestamp(self.created_at, "creation time")
        _timestamp(self.updated_at, "update time")

    def to_dict(self):
        return asdict(self)


def create_annotation(source_sha256, source_crs, anchor, title, note="", *,
                      resolution_seconds=0, source_point_count=1,
                      annotation_id=None, created_at=None):
    now = created_at or datetime.now(timezone.utc).isoformat()
    return SceneAnnotation(annotation_id or uuid4().hex, source_sha256, source_crs,
        title, note, anchor, resolution_seconds, source_point_count, now, now)


def resolve_source_annotation(source, expected_points, requested_point, source_crs,
                              title, note="", *, pdal_module=None,
                              cancelled=lambda: False, progress=lambda count: None):
    """Resolve one displayed point and create immutable source-bound metadata."""
    anchors, duration = resolve_source_anchors(source, expected_points,
        (requested_point,), pdal_module=pdal_module, cancelled=cancelled,
        progress=progress)
    return create_annotation(source.sha256, source_crs, anchors[0], title, note,
        resolution_seconds=duration, source_point_count=expected_points)


def update_annotation(annotation, *, title=None, note=None, updated_at=None):
    item = annotation if isinstance(annotation, SceneAnnotation) else annotation_from_dict(annotation)
    return replace(item,
        title=item.title if title is None else title,
        note=item.note if note is None else note,
        updated_at=updated_at or datetime.now(timezone.utc).isoformat())


def annotation_from_dict(payload):
    if not isinstance(payload, dict):
        raise ValueError("Saved annotation is invalid.")
    values = dict(payload)
    try:
        values["anchor"] = MeasurementAnchor(**values["anchor"])
        return SceneAnnotation(**values)
    except (KeyError, TypeError) as error:
        raise ValueError("Saved annotation is incomplete.") from error


def validate_annotations(payload, source_sha256):
    if payload in (None, []):
        return []
    if not isinstance(payload, list) or len(payload) > MAX_ANNOTATIONS:
        raise ValueError(f"One session supports at most {MAX_ANNOTATIONS:,} annotations.")
    result = []
    identities = set()
    for raw in payload:
        item = annotation_from_dict(raw)
        if item.source_sha256 != source_sha256:
            raise ValueError("Saved annotation belongs to another source.")
        if item.annotation_id in identities:
            raise ValueError("Saved annotations contain duplicate identities.")
        identities.add(item.annotation_id)
        result.append(item.to_dict())
    return result


def replace_annotation(payload, source_sha256, annotation_id, *, title=None, note=None,
                       updated_at=None):
    items = validate_annotations(payload, source_sha256)
    found = False
    result = []
    for raw in items:
        item = annotation_from_dict(raw)
        if item.annotation_id == annotation_id:
            item = update_annotation(item, title=title, note=note, updated_at=updated_at)
            found = True
        result.append(item.to_dict())
    if not found:
        raise ValueError("Annotation no longer exists in this session.")
    return result


def remove_annotation(payload, source_sha256, annotation_id):
    items = validate_annotations(payload, source_sha256)
    result = [item for item in items if item["annotation_id"] != annotation_id]
    if len(result) == len(items):
        raise ValueError("Annotation no longer exists in this session.")
    return result


def annotation_summary(annotation):
    item = annotation if isinstance(annotation, SceneAnnotation) else annotation_from_dict(annotation)
    x, y, z = item.anchor.source_xyz
    return f"{item.title} | X {x:,.3f}, Y {y:,.3f}, Z {z:,.3f}"
