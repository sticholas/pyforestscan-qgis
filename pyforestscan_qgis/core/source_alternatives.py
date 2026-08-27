"""Conservative detection of duplicate-like LiDAR source representations."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from .lidar_inventory import LidarSourceRecord


class SourceRelationship(str, Enum):
    INDEPENDENT = "INDEPENDENT"
    POTENTIAL_ALTERNATIVE_REPRESENTATION = "POTENTIAL_ALTERNATIVE_REPRESENTATION"
    DUPLICATE = "DUPLICATE"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class PotentialDuplicateSourceDetection:
    first: LidarSourceRecord
    second: LidarSourceRecord
    relationship: SourceRelationship
    recommended: LidarSourceRecord | None
    evidence: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "first": str(self.first.path),
            "second": str(self.second.path),
            "relationship": self.relationship.value,
            "recommended": None if self.recommended is None else str(self.recommended.path),
            "evidence": list(self.evidence),
        }


def detect_source_alternatives(sources: tuple[LidarSourceRecord, ...]) -> tuple[PotentialDuplicateSourceDetection, ...]:
    detections: list[PotentialDuplicateSourceDetection] = []
    for index, first in enumerate(sources):
        for second in sources[index + 1 :]:
            detections.append(_compare(first, second))
    return tuple(detections)


def canonicalize_source_alternatives(sources: tuple[LidarSourceRecord, ...]) -> tuple[tuple[LidarSourceRecord, ...], tuple[PotentialDuplicateSourceDetection, ...]]:
    detections = detect_source_alternatives(sources)
    excluded: set[Path] = set()
    for item in detections:
        if item.relationship is SourceRelationship.POTENTIAL_ALTERNATIVE_REPRESENTATION and item.recommended is not None:
            excluded.add(item.first.path if item.recommended.path == item.second.path else item.second.path)
        elif item.relationship is SourceRelationship.DUPLICATE:
            excluded.add(item.second.path)
    return tuple(item for item in sources if item.path not in excluded), detections


def _compare(first: LidarSourceRecord, second: LidarSourceRecord) -> PotentialDuplicateSourceDetection:
    evidence: list[str] = []
    same_count = first.point_count is not None and first.point_count == second.point_count
    if same_count:
        evidence.append("same point count")
    same_bounds = _matching_bounds(first, second)
    if same_bounds:
        evidence.append("near-identical bounds")
    size_ratio = abs(first.size_bytes - second.size_bytes) / max(1, first.size_bytes, second.size_bytes)
    similar_size = size_ratio <= 0.01
    if similar_size:
        evidence.append("file sizes within one percent")
    prepared = _prepared_candidate(first, second)
    if prepared is not None:
        evidence.append("filename and vertical ranges indicate a prepared representation")
    if same_count and same_bounds and first.size_bytes == second.size_bytes:
        relationship = SourceRelationship.DUPLICATE
        recommended = first
    elif same_count and same_bounds and similar_size and prepared is not None:
        relationship = SourceRelationship.POTENTIAL_ALTERNATIVE_REPRESENTATION
        recommended = prepared
    elif same_bounds and (same_count or similar_size):
        relationship = SourceRelationship.UNKNOWN
        recommended = None
    else:
        relationship = SourceRelationship.INDEPENDENT
        recommended = None
    return PotentialDuplicateSourceDetection(first, second, relationship, recommended, tuple(evidence))


def _matching_bounds(first: LidarSourceRecord, second: LidarSourceRecord) -> bool:
    if first.bounds is None or second.bounds is None:
        return False
    values = ("xmin", "ymin", "xmax", "ymax")
    scale = max(1.0, *(abs(getattr(first.bounds, name)) for name in values), *(abs(getattr(second.bounds, name)) for name in values))
    tolerance = max(1e-6, scale * 1e-9)
    return all(abs(getattr(first.bounds, name) - getattr(second.bounds, name)) <= tolerance for name in values)


def _prepared_candidate(first: LidarSourceRecord, second: LidarSourceRecord) -> LidarSourceRecord | None:
    markers = ("_norm", "_normalized", "_hag", "_prepared")
    first_marked = any(marker in first.path.stem.lower() for marker in markers)
    second_marked = any(marker in second.path.stem.lower() for marker in markers)
    if first_marked == second_marked:
        return None
    prepared, raw = (first, second) if first_marked else (second, first)
    if None in (prepared.zmin, prepared.zmax, raw.zmin, raw.zmax):
        return None
    prepared_near_ground = abs(float(prepared.zmin)) <= 100 and abs(float(prepared.zmax)) <= 150
    vertical_offset = abs(float(raw.zmin) - float(prepared.zmin)) >= 100
    return prepared if prepared_near_ground and vertical_offset else None
