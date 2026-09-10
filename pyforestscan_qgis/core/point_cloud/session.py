"""Immutable source-space selections and reversible, non-destructive sessions.

These contracts do not execute edits. Selection membership refers to ORIGINAL
attributes, never renderer order or attributes changed by earlier operations.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from ..atomic_state import atomic_write_json


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class SourceIdentity:
    path: str
    sha256: str
    size: int
    source_type: str

    def __post_init__(self):
        if self.source_type not in ("LAS", "LAZ", "COPC"):
            raise ValueError("File identity supports LAS/LAZ/COPC only; EPT needs a tree identity.")
        if not re.fullmatch(r"[0-9a-f]{64}", self.sha256) or self.size < 0:
            raise ValueError("Invalid source fingerprint.")

    @classmethod
    def capture(cls, path: str | Path, *, cancelled=lambda: False) -> "SourceIdentity":
        source = Path(path).resolve(strict=True)
        kind = "COPC" if source.name.lower().endswith(".copc.laz") else source.suffix[1:].upper()
        if kind not in ("LAS", "LAZ", "COPC"):
            raise ValueError("Only local LAS/LAZ/COPC file fingerprints are implemented.")
        before = source.stat()
        digest = hashlib.sha256()
        with source.open("rb") as stream:
            while True:
                if cancelled():
                    raise InterruptedError("Source fingerprint cancelled.")
                block = stream.read(1024 * 1024)
                if not block:
                    break
                digest.update(block)
        after = source.stat()
        if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
            raise ValueError("Source changed while fingerprinting; retry on a stable source.")
        return cls(str(source), digest.hexdigest(), after.st_size, kind)

    def verify(self, *, cancelled=lambda: False) -> None:
        if self.capture(self.path, cancelled=cancelled) != self:
            raise ValueError("Source fingerprint changed; session edits cannot be replayed.")


@dataclass(frozen=True)
class SpatialSelection:
    """Inclusive XYZ box and original-class filter in source coordinates.

    A deliberately limited first contract: polygon/frustum selections must use
    separately validated geometry contracts, not pretend a box is a lasso.
    """
    selection_id: str
    source_sha256: str
    bounds: tuple[float, float, float, float, float, float]
    source_crs: str
    original_classes: tuple[int, ...] = ()
    addressing: str = "FULL_RESOLUTION_ORIGINAL_SOURCE_QUERY"

    def __post_init__(self):
        object.__setattr__(self, "bounds", tuple(self.bounds))
        object.__setattr__(self, "original_classes", tuple(self.original_classes))
        if not self.selection_id or not self.source_crs.strip():
            raise ValueError("Selection identity and source CRS are required.")
        if not re.fullmatch(r"[0-9a-f]{64}", self.source_sha256):
            raise ValueError("Selection requires a content fingerprint.")
        if self.addressing != "FULL_RESOLUTION_ORIGINAL_SOURCE_QUERY":
            raise ValueError("Rendered sample indices are not valid source edit addresses.")
        if len(self.bounds) != 6 or not all(math.isfinite(v) for v in self.bounds):
            raise ValueError("Selection needs six finite XYZ bounds.")
        if any(self.bounds[i] > self.bounds[i + 3] for i in range(3)):
            raise ValueError("Selection minimum exceeds maximum.")
        if any(type(c) is not int or not 0 <= c <= 255 for c in self.original_classes):
            raise ValueError("Invalid LAS classification filter.")


@dataclass(frozen=True)
class EditOperation:
    operation_id: str
    timestamp: str
    selection: SpatialSelection
    classification: int
    kind: str = "SET_CLASSIFICATION"
    note: str = ""

    def __post_init__(self):
        if not self.operation_id or not self.timestamp:
            raise ValueError("Operation identity and timestamp are required.")
        if self.kind not in ("SET_CLASSIFICATION", "MARK_NOISE"):
            raise ValueError("Unsupported journal operation.")
        if type(self.classification) is not int or not 0 <= self.classification <= 255:
            raise ValueError("Classification must be an integer from 0 to 255.")
        if self.kind == "MARK_NOISE" and self.classification not in (7, 18):
            raise ValueError("Noise classification must be 7 or 18.")


@dataclass
class PointCloudEditSession:
    source: SourceIdentity
    source_crs: str
    dimensions: tuple[str, ...] = ()
    session_id: str = field(default_factory=lambda: uuid4().hex)
    created: str = field(default_factory=_now)
    modified: str = field(default_factory=_now)
    camera: dict = field(default_factory=dict)
    visibility: dict = field(default_factory=dict)
    filters: dict = field(default_factory=dict)
    review_notes: list[str] = field(default_factory=list)
    export_history: list[dict] = field(default_factory=list)
    _journal: list[EditOperation | AttributeEditOperation | ObjectIdEditOperation] = field(default_factory=list, repr=False)
    _cursor: int = field(default=0, repr=False)

    @property
    def operations(self) -> tuple[EditOperation | AttributeEditOperation | ObjectIdEditOperation, ...]:
        return tuple(self._journal[:self._cursor])

    @property
    def can_undo(self) -> bool:
        return self._cursor > 0

    @property
    def can_redo(self) -> bool:
        return self._cursor < len(self._journal)

    def stage(self, selection: SpatialSelection, classification: int, *, noise=False, note=""):
        if selection.source_sha256 != self.source.sha256 or selection.source_crs != self.source_crs:
            raise ValueError("Selection does not belong to this source and CRS.")
        operation = EditOperation(uuid4().hex, _now(), selection, classification,
                                  "MARK_NOISE" if noise else "SET_CLASSIFICATION", note)
        self._journal[self._cursor:] = [operation]
        self._cursor += 1
        self.modified = _now()
        return operation

    def stage_resolved(self, definitions, result, attribute, value, *, note=""):
        from .selection import validate_sequence
        items = validate_sequence(definitions)
        first = items[0]
        if (first.session_id != self.session_id or first.source_fingerprint != self.source.sha256
                or first.geometry_crs != self.source_crs or first.source_type != self.source.source_type):
            raise ValueError("Selection does not belong to this session/source.")
        if result.resolution_status != "RESOLVED" or result.selection_id != items[-1].selection_id:
            raise ValueError("Resolve the current selection before staging edits.")
        if result.resolved_point_count <= 0:
            raise ValueError("No source points are selected.")
        operation = AttributeEditOperation(uuid4().hex, _now(), items, attribute, value,
                                           result.resolved_point_count, note=note)
        self._journal[self._cursor:] = [operation]
        self._cursor += 1
        self.modified = _now()
        return operation

    def stage_object_id(self, definitions, result, policy, value, *, note=""):
        from .object_id_policy import ObjectIdPolicy
        from .selection import validate_sequence
        if not isinstance(policy, ObjectIdPolicy):
            raise ValueError("A confirmed object ID policy is required.")
        if policy.source_sha256 != self.source.sha256 or policy.field not in self.dimensions:
            raise ValueError("Object ID policy does not belong to this source field.")
        items = validate_sequence(definitions)
        first = items[0]
        if (first.session_id != self.session_id or first.source_fingerprint != self.source.sha256
                or first.geometry_crs != self.source_crs or first.source_type != self.source.source_type):
            raise ValueError("Selection does not belong to this session/source.")
        if result.resolution_status != "RESOLVED" or result.selection_id != items[-1].selection_id:
            raise ValueError("Resolve the current selection before staging object edits.")
        if result.resolved_point_count <= 0:
            raise ValueError("No source points are selected.")
        operation = ObjectIdEditOperation(uuid4().hex, _now(), items, policy.field, value,
            result.resolved_point_count, policy.field_dtype, policy.storage_minimum,
            policy.storage_maximum, policy.unassigned_id, note=note)
        self._journal[self._cursor:] = [operation]
        self._cursor += 1
        self.modified = _now()
        return operation

    def undo(self) -> bool:
        if not self.can_undo:
            return False
        self._cursor -= 1
        self.modified = _now()
        return True

    def redo(self) -> bool:
        if not self.can_redo:
            return False
        self._cursor += 1
        self.modified = _now()
        return True

    def save(self, path: str | Path) -> Path:
        destination = Path(path).resolve()
        source = Path(self.source.path).resolve()
        if destination == source or (destination.exists() and destination.samefile(source)):
            raise ValueError("A session must never overwrite its source.")
        if destination.suffix.lower() != ".json":
            raise ValueError("Session files must use the .json extension.")
        payload = asdict(self)
        payload["schema_version"] = 3
        return atomic_write_json(destination, payload)

    @classmethod
    def load(cls, path: str | Path, *, verify_source=True, cancelled=lambda: False):
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(payload, dict) or payload.pop("schema_version", None) not in (1, 2, 3):
            raise ValueError("Unsupported point cloud session schema.")
        source = SourceIdentity(**payload.pop("source"))
        entries = payload.pop("_journal")
        cursor = payload.pop("_cursor")
        if type(cursor) is not int or not 0 <= cursor <= len(entries):
            raise ValueError("Invalid journal cursor.")
        operations = []
        ids = set()
        for entry in entries:
            entry = dict(entry)
            if entry.get("kind") in ("SET_ATTRIBUTE", "SET_OBJECT_ID"):
                from .selection import SelectionDefinition
                definitions = tuple(SelectionDefinition(**item) for item in entry.pop("definitions"))
                operation_type = (ObjectIdEditOperation if entry.get("kind") == "SET_OBJECT_ID"
                                  else AttributeEditOperation)
                operation = operation_type(definitions=definitions, **entry)
                if isinstance(operation, ObjectIdEditOperation) and operation.attribute not in payload["dimensions"]:
                    raise ValueError("Object journal field is not present in the saved source dimensions.")
                first = definitions[0]
                if (first.session_id != payload["session_id"] or first.source_fingerprint != source.sha256
                        or first.geometry_crs != payload["source_crs"] or first.source_type != source.source_type):
                    raise ValueError("Journal contains a selection for another source/session.")
                if operation.operation_id in ids:
                    raise ValueError("Duplicate journal operation identity.")
                ids.add(operation.operation_id)
                operations.append(operation)
                continue
            selection = SpatialSelection(**entry.pop("selection"))
            operation = EditOperation(selection=selection, **entry)
            if selection.source_sha256 != source.sha256 or selection.source_crs != payload["source_crs"]:
                raise ValueError("Journal contains a selection for another source or CRS.")
            if operation.operation_id in ids:
                raise ValueError("Duplicate journal operation identity.")
            ids.add(operation.operation_id)
            operations.append(operation)
        payload["dimensions"] = tuple(payload["dimensions"])
        result = cls(source=source, _journal=operations, _cursor=cursor, **payload)
        if verify_source:
            source.verify(cancelled=cancelled)
        return result


@dataclass(frozen=True)
class AttributeEditOperation:
    """Ordered diff; membership always refers to original source attributes."""
    operation_id: str
    timestamp: str
    definitions: tuple
    attribute: str
    value: int
    point_count: int
    kind: str = "SET_ATTRIBUTE"
    previous_value_contract: str = "REPLAY_ORIGINAL_THEN_ORDERED_JOURNAL"
    status: str = "STAGED"
    note: str = ""

    def __post_init__(self):
        from .selection import validate_sequence
        object.__setattr__(self, "definitions", validate_sequence(self.definitions))
        if not self.operation_id or not self.timestamp or self.kind != "SET_ATTRIBUTE" or self.status != "STAGED":
            raise ValueError("Invalid staged edit identity/state.")
        if self.previous_value_contract != "REPLAY_ORIGINAL_THEN_ORDERED_JOURNAL":
            raise ValueError("Unsupported previous-value contract.")
        limits = {"Classification": 255, "Withheld": 1, "DELETE_ON_EXPORT": 1}
        if self.attribute not in limits or type(self.value) is not int or not 0 <= self.value <= limits[self.attribute]:
            raise ValueError("Unsupported attribute or value; coordinate edits are prohibited.")
        if type(self.point_count) is not int or self.point_count <= 0:
            raise ValueError("Staged edits require a positive resolved source count.")


@dataclass(frozen=True)
class ObjectIdEditOperation:
    """One validated categorical-ID diff in the shared ordered edit journal."""
    operation_id: str
    timestamp: str
    definitions: tuple
    attribute: str
    value: int
    point_count: int
    field_dtype: str
    storage_minimum: int
    storage_maximum: int
    unassigned_id: int
    kind: str = "SET_OBJECT_ID"
    previous_value_contract: str = "REPLAY_ORIGINAL_THEN_ORDERED_JOURNAL"
    status: str = "STAGED"
    note: str = ""

    def __post_init__(self):
        from .object_id_policy import INTEGER_DTYPE_LIMITS
        from .selection import validate_sequence
        object.__setattr__(self, "definitions", validate_sequence(self.definitions))
        if (not self.operation_id or not self.timestamp or self.kind != "SET_OBJECT_ID"
                or self.status != "STAGED"):
            raise ValueError("Invalid object edit identity/state.")
        if self.previous_value_contract != "REPLAY_ORIGINAL_THEN_ORDERED_JOURNAL":
            raise ValueError("Unsupported previous-value contract.")
        if (not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", self.attribute)
                or self.attribute in ("X", "Y", "Z", "Classification", "HeightAboveGround")):
            raise ValueError("Invalid object ID source dimension.")
        expected = INTEGER_DTYPE_LIMITS.get(self.field_dtype)
        if expected != (self.storage_minimum, self.storage_maximum):
            raise ValueError("Object edit storage contract does not match its integer dtype.")
        if (type(self.value) is not int or not self.storage_minimum <= self.value <= self.storage_maximum
                or type(self.unassigned_id) is not int
                or not self.storage_minimum <= self.unassigned_id <= self.storage_maximum):
            raise ValueError("Object edit value is outside the source field storage range.")
        if type(self.point_count) is not int or self.point_count <= 0:
            raise ValueError("Object edits require a positive resolved source count.")
