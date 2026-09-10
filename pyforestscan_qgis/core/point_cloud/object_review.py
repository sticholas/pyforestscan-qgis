"""Session-owned object review metadata; never implicit source attributes."""
from __future__ import annotations

from datetime import datetime, timezone
import re


MAX_REVIEW_RECORDS = 10_000
MAX_NOTE_CHARACTERS = 2_000
_FIELD = re.compile(r"[A-Za-z][A-Za-z0-9_]*")


def _identity(source_sha256, field, object_id):
    if not re.fullmatch(r"[0-9a-f]{64}", source_sha256):
        raise ValueError("Object review requires the original source fingerprint.")
    if not isinstance(field, str) or not _FIELD.fullmatch(field):
        raise ValueError("Object review requires a valid source object field.")
    if type(object_id) is not int or not -(2**63) <= object_id <= 2**63-1:
        raise ValueError("Object review requires a signed 64-bit integer object ID.")
    return source_sha256, field, object_id


def validate_object_reviews(payload, source_sha256):
    if payload in (None, {}):
        return {"schema_version":1, "source_sha256":source_sha256, "records":[]}
    if (not isinstance(payload, dict) or payload.get("schema_version") != 1
            or payload.get("source_sha256") != source_sha256
            or not isinstance(payload.get("records"), list)
            or len(payload["records"]) > MAX_REVIEW_RECORDS):
        raise ValueError("Saved object review metadata is invalid or belongs to another source.")
    seen = set()
    records = []
    for raw in payload["records"]:
        if not isinstance(raw, dict):
            raise ValueError("Saved object review record is invalid.")
        field = raw.get("field")
        object_id = raw.get("object_id")
        _identity(source_sha256, field, object_id)
        key = field, object_id
        if key in seen or type(raw.get("reviewed")) is not bool:
            raise ValueError("Saved object review records contain duplicate or invalid state.")
        note = raw.get("note")
        if (not isinstance(note, str) or len(note) > MAX_NOTE_CHARACTERS
                or "\x00" in note or not isinstance(raw.get("updated_at"), str)):
            raise ValueError("Saved object review note or timestamp is invalid.")
        seen.add(key)
        records.append({"field":field, "object_id":object_id,
                        "reviewed":raw["reviewed"], "note":note,
                        "updated_at":raw["updated_at"]})
    records.sort(key=lambda item: (item["field"], item["object_id"]))
    return {"schema_version":1, "source_sha256":source_sha256, "records":records}


def object_review_record(payload, source_sha256, field, object_id):
    _identity(source_sha256, field, object_id)
    ledger = validate_object_reviews(payload, source_sha256)
    record = next((item for item in ledger["records"]
                   if item["field"] == field and item["object_id"] == object_id), None)
    if record is None:
        return {"field":field, "object_id":object_id, "reviewed":False,
                "note":"", "updated_at":"", "recorded":False}
    return {**record, "recorded":True}


def update_object_review(payload, source_sha256, field, object_id, *,
                         reviewed=None, note=None, updated_at=None):
    """Return a validated immutable-style ledger update for one source object."""
    _identity(source_sha256, field, object_id)
    if reviewed is None and note is None:
        raise ValueError("Object review update requires status or note content.")
    if reviewed is not None and type(reviewed) is not bool:
        raise ValueError("Object reviewed state must be explicit true or false.")
    if note is not None:
        if not isinstance(note, str) or len(note) > MAX_NOTE_CHARACTERS or "\x00" in note:
            raise ValueError(f"Object notes must contain at most {MAX_NOTE_CHARACTERS:,} characters.")
        note = note.strip()
    ledger = validate_object_reviews(payload, source_sha256)
    records = {(item["field"], item["object_id"]):dict(item)
               for item in ledger["records"]}
    key = field, object_id
    current = records.get(key, {"field":field, "object_id":object_id,
                                "reviewed":False, "note":""})
    if reviewed is not None:
        current["reviewed"] = reviewed
    if note is not None:
        current["note"] = note
    current["updated_at"] = updated_at or datetime.now(timezone.utc).isoformat()
    records[key] = current
    if len(records) > MAX_REVIEW_RECORDS:
        raise ValueError(f"One session supports at most {MAX_REVIEW_RECORDS:,} reviewed objects.")
    return validate_object_reviews({"schema_version":1, "source_sha256":source_sha256,
        "records":list(records.values())}, source_sha256)


def object_review_summary(record):
    if not isinstance(record, dict) or type(record.get("reviewed")) is not bool:
        raise ValueError("Invalid object review record.")
    state = "Reviewed" if record["reviewed"] else "Not reviewed"
    return state + (" | Note saved" if record.get("note") else " | No note")
