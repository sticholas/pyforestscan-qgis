"""Guarded object split/merge contracts built on authoritative selections."""
from __future__ import annotations

from dataclasses import dataclass, replace
import re

from .selection import validate_sequence


_FIELD = re.compile(r"[A-Za-z][A-Za-z0-9_]*")


@dataclass(frozen=True)
class ObjectSplitSource:
    source_sha256: str
    field: str
    object_id: int
    original_point_count: int

    def __post_init__(self):
        if not re.fullmatch(r"[0-9a-f]{64}", self.source_sha256):
            raise ValueError("Object split requires the original source fingerprint.")
        if not isinstance(self.field, str) or not _FIELD.fullmatch(self.field):
            raise ValueError("Object split requires a valid source object field.")
        if type(self.object_id) is not int:
            raise ValueError("Object split requires an integer parent object ID.")
        if type(self.original_point_count) is not int or self.original_point_count <= 0:
            raise ValueError("Object split requires a positive exact parent-object count.")

    def to_dict(self):
        return {
            "source_sha256": self.source_sha256,
            "field": self.field,
            "object_id": self.object_id,
            "original_point_count": self.original_point_count,
        }


def begin_object_split(source_sha256, catalog, active_object, selection_result):
    """Freeze an exact selected catalog object as the parent of a later split."""
    if not isinstance(catalog, dict) or catalog.get("source_sha256") != source_sha256:
        raise ValueError("Build a current exact object catalog before splitting an object.")
    if not isinstance(active_object, dict) or active_object.get("field") != catalog.get("field"):
        raise ValueError("Select an exact catalog object before beginning a split.")
    if (selection_result is None
            or active_object.get("selection_id") != selection_result.selection_id
            or active_object.get("point_count") != selection_result.resolved_point_count):
        raise ValueError("The active object selection changed; select the object again before splitting it.")
    return ObjectSplitSource(source_sha256, active_object["field"],
                             active_object["object_id"], active_object["point_count"])


def restrict_selection_to_object(definitions, split_source, *, selection_id):
    """Intersect an arbitrary selection sequence with one original object ID."""
    if not isinstance(split_source, ObjectSplitSource):
        split_source = ObjectSplitSource(**split_source)
    items = validate_sequence(definitions)
    if items[0].source_fingerprint != split_source.source_sha256:
        raise ValueError("Split selection and parent object belong to different sources.")
    if not isinstance(selection_id, str) or not selection_id:
        raise ValueError("Split selection requires a new authoritative identity.")
    result = []
    exact_filter = (split_source.field, split_source.object_id, split_source.object_id)
    for index, item in enumerate(items):
        result.append(replace(item,
            selection_id=selection_id if index == len(items)-1 else item.selection_id,
            attribute_filters=(*item.attribute_filters, exact_filter)))
    return validate_sequence(result)


def validate_split_count(split_source, selected_point_count):
    """Reject empty and whole-object assignments that are not true splits."""
    if not isinstance(split_source, ObjectSplitSource):
        split_source = ObjectSplitSource(**split_source)
    if type(selected_point_count) is not int or selected_point_count <= 0:
        raise ValueError("The selected portion contains no points from the parent object.")
    if selected_point_count >= split_source.original_point_count:
        raise ValueError("A split must leave at least one point in the parent object.")
    return selected_point_count


def validate_merge_target(catalog, active_object, target_object):
    """Require two distinct exact objects from the same original catalog."""
    if not isinstance(catalog, dict) or not isinstance(active_object, dict):
        raise ValueError("Select an exact catalog object before merging.")
    if active_object.get("field") != catalog.get("field"):
        raise ValueError("Active object and catalog fields differ; rebuild the catalog.")
    if not isinstance(target_object, dict) or target_object.get("object_id") is None:
        raise ValueError("Merge target is not present in the exact object catalog.")
    if target_object["object_id"] == active_object.get("object_id"):
        raise ValueError("Choose a different target object for the merge.")
    return int(target_object["object_id"])
