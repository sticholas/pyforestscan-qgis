"""Explicit unassigned semantics and safe IDs for future object journal edits."""
from __future__ import annotations

from contextlib import closing
from dataclasses import asdict, dataclass
from pathlib import Path
import re
import sqlite3

from .object_catalog import object_catalog_report


INTEGER_DTYPE_LIMITS = {
    "int8": (-(2**7), 2**7-1), "uint8": (0, 2**8-1),
    "int16": (-(2**15), 2**15-1), "uint16": (0, 2**16-1),
    "int32": (-(2**31), 2**31-1), "uint32": (0, 2**32-1),
    "int64": (-(2**63), 2**63-1),
    # Exact catalog keys use SQLite INTEGER; uint64 values above this remain read-only.
    "uint64": (0, 2**63-1),
}


@dataclass(frozen=True)
class ObjectIdPolicy:
    source_sha256: str
    field: str
    field_dtype: str
    storage_minimum: int
    storage_maximum: int
    unassigned_id: int
    semantics: str = "USER_CONFIRMED_UNASSIGNED_VALUE"

    def __post_init__(self):
        if (not re.fullmatch(r"[0-9a-f]{64}", self.source_sha256)
                or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", self.field)
                or not isinstance(self.field_dtype, str)
                or type(self.storage_minimum) is not int or type(self.storage_maximum) is not int
                or self.storage_minimum > self.storage_maximum):
            raise ValueError("Invalid object ID policy identity or storage range.")
        if self.semantics != "USER_CONFIRMED_UNASSIGNED_VALUE":
            raise ValueError("Object unassigned semantics require explicit user confirmation.")
        if (type(self.unassigned_id) is not int or
                not self.storage_minimum <= self.unassigned_id <= self.storage_maximum):
            raise ValueError("Unassigned object ID is outside the field storage range.")

    def to_dict(self):
        return asdict(self)


def create_object_id_policy(catalog_report, unassigned_id):
    """Create policy only for integer storage; floating IDs remain safely read-only."""
    if not isinstance(catalog_report, dict) or catalog_report.get("status") != "READY":
        raise ValueError("Build an exact object catalog before defining ID semantics.")
    dtype = catalog_report["field_dtype"]
    if dtype not in INTEGER_DTYPE_LIMITS:
        raise ValueError("Object editing requires an integer source dimension; this field remains read-only.")
    low, high = INTEGER_DTYPE_LIMITS[dtype]
    if type(unassigned_id) is not int:
        raise ValueError("Unassigned object ID must be an integer.")
    return ObjectIdPolicy(catalog_report["source_sha256"], catalog_report["field"],
        dtype, low, high, unassigned_id)


def next_available_object_id(catalog_path, policy, *, preferred_start=1):
    """Find the first unused ID in constant memory without assuming zero is unassigned."""
    if not isinstance(policy, ObjectIdPolicy):
        raise ValueError("A confirmed object ID policy is required.")
    if type(preferred_start) is not int:
        raise ValueError("Preferred object ID must be an integer.")
    report = object_catalog_report(catalog_path)
    if ((report["source_sha256"], report["field"], report["field_dtype"])
            != (policy.source_sha256, policy.field, policy.field_dtype)):
        raise ValueError("Object ID policy does not belong to this exact catalog field.")
    expected_limits = INTEGER_DTYPE_LIMITS.get(report["field_dtype"])
    if expected_limits is None or (policy.storage_minimum, policy.storage_maximum) != expected_limits:
        raise ValueError("Object ID policy storage range does not match the catalog field.")
    candidate = max(preferred_start, policy.storage_minimum)
    if candidate == policy.unassigned_id:
        candidate += 1
    if candidate > policy.storage_maximum:
        raise OverflowError("No object ID remains inside the field storage range.")
    with closing(sqlite3.connect(Path(catalog_path))) as connection:
        rows = connection.execute(
            "SELECT object_id FROM objects WHERE object_id>=? ORDER BY object_id", (candidate,))
        for (identifier,) in rows:
            identifier = int(identifier)
            if identifier < candidate:
                continue
            if identifier > candidate:
                break
            candidate += 1
            if candidate == policy.unassigned_id:
                candidate += 1
            if candidate > policy.storage_maximum:
                raise OverflowError("No object ID remains inside the field storage range.")
    return candidate


def object_id_policy_summary(policy, next_id):
    if not isinstance(policy, ObjectIdPolicy) or type(next_id) is not int:
        raise ValueError("Invalid object ID policy summary.")
    return (f"Object IDs: {policy.field} | Unassigned = {policy.unassigned_id} | "
            f"Next safe ID = {next_id}")
