"""Evidence-driven spatial-reference resolution for LiDAR sources."""

from __future__ import annotations

import hashlib
import json
import re
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Iterable, Mapping

from .crs_alignment import compare_crs
from .ept_spatial_reference import resolve_ept_spatial_reference


class SpatialReferenceStatus(str, Enum):
    RESOLVED_AUTHORITATIVE = "RESOLVED_AUTHORITATIVE"
    RESOLVED_REPOSITORY_INHERITANCE = "RESOLVED_REPOSITORY_INHERITANCE"
    RESOLVED_USER_ASSIGNMENT = "RESOLVED_USER_ASSIGNMENT"
    SOURCE_LOCAL_ONLY = "SOURCE_LOCAL_ONLY"
    AMBIGUOUS = "AMBIGUOUS"
    CONFLICT = "CONFLICT"
    INVALID = "INVALID"


class SpatialReferenceConfidence(str, Enum):
    AUTHORITATIVE = "AUTHORITATIVE"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    NONE = "NONE"


@dataclass(frozen=True)
class SpatialReferenceEvidence:
    source: str
    crs: str
    confidence: SpatialReferenceConfidence
    detail: str = ""


@dataclass(frozen=True)
class SpatialReferenceResolution:
    status: SpatialReferenceStatus
    resolved_crs: str = ""
    horizontal_crs: str = ""
    vertical_crs: str = ""
    authority: str = ""
    source: str = "unknown"
    confidence: SpatialReferenceConfidence = SpatialReferenceConfidence.NONE
    evidence: tuple[SpatialReferenceEvidence, ...] = ()
    transformation_required: bool = False
    safe_for_source_local_processing: bool = False
    safe_for_spatial_alignment: bool = False
    user_action_required: bool = False
    warnings: tuple[str, ...] = ()

    @property
    def resolved(self) -> bool:
        return bool(self.resolved_crs) and self.status not in {SpatialReferenceStatus.CONFLICT, SpatialReferenceStatus.INVALID}

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["status"] = self.status.value
        payload["confidence"] = self.confidence.value
        payload["evidence"] = [{**asdict(item), "confidence": item.confidence.value} for item in self.evidence]
        return payload


@dataclass(frozen=True)
class RepositorySpatialReferenceProfile:
    repository_path: Path
    repository_fingerprint: str
    resolved_crs: str
    confidence: SpatialReferenceConfidence
    sampled_count: int
    agreement_count: int
    disagreement_count: int
    unknown_count: int
    crs_distribution: tuple[tuple[str, int], ...]
    status: str
    warnings: tuple[str, ...] = ()

    @property
    def can_inherit(self) -> bool:
        return self.status == "resolved" and self.confidence in {SpatialReferenceConfidence.AUTHORITATIVE, SpatialReferenceConfidence.HIGH}


class SpatialReferenceAssignmentStore:
    """Small JSON store for explicit file/repository assignments."""

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)

    def assignment_for(self, source: Path, repository: Path | None = None) -> SpatialReferenceEvidence | None:
        data = self._read()
        file_key = _path_key(source)
        record = data.get("files", {}).get(file_key)
        if isinstance(record, dict) and record.get("signature") == _file_signature(source):
            return SpatialReferenceEvidence("persisted_file_assignment", str(record.get("crs", "")), SpatialReferenceConfidence.HIGH, "Explicit file assignment")
        if repository is not None:
            record = data.get("repositories", {}).get(_path_key(repository))
            if isinstance(record, dict) and record.get("fingerprint") == repository_fingerprint(repository):
                return SpatialReferenceEvidence("persisted_repository_assignment", str(record.get("crs", "")), SpatialReferenceConfidence.HIGH, "Explicit repository assignment")
        return None

    def assign_file(self, source: Path, crs: str) -> None:
        self._write_assignment("files", _path_key(source), crs, "signature", _file_signature(source))

    def assign_repository(self, repository: Path, crs: str) -> None:
        self._write_assignment("repositories", _path_key(repository), crs, "fingerprint", repository_fingerprint(repository))

    def clear_repository(self, repository: Path) -> None:
        data = self._read()
        data.setdefault("repositories", {}).pop(_path_key(repository), None)
        self._write(data)

    def _write_assignment(self, group: str, key: str, crs: str, signature_key: str, signature: str) -> None:
        normalized = normalize_crs(crs)
        if not normalized:
            raise ValueError("A valid CRS is required for assignment.")
        data = self._read()
        data.setdefault(group, {})[key] = {"crs": normalized, signature_key: signature, "assigned_at": datetime.now(timezone.utc).isoformat(), "source": "user"}
        self._write(data)

    def _read(self) -> dict[str, object]:
        if not self.path.exists():
            return {"version": 1, "files": {}, "repositories": {}}
        try:
            value = json.loads(self.path.read_text(encoding="utf-8"))
            return value if isinstance(value, dict) else {"version": 1, "files": {}, "repositories": {}}
        except (OSError, json.JSONDecodeError):
            return {"version": 1, "files": {}, "repositories": {}}

    def _write(self, data: dict[str, object]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        temporary.replace(self.path)


class SpatialReferenceResolver:
    """Resolve CRS from authoritative evidence without coordinate guessing."""

    def __init__(self, assignment_store: SpatialReferenceAssignmentStore | None = None) -> None:
        self.assignment_store = assignment_store

    def resolve(
        self,
        source: Path | str,
        *,
        embedded_crs: str | None = None,
        ept_payload: Mapping[str, object] | None = None,
        repository_context: RepositorySpatialReferenceProfile | None = None,
        qgis_context: Mapping[str, str] | None = None,
        polygon_crs: str | None = None,
        project_crs: str | None = None,
        spatial_alignment_required: bool = False,
        source_local_allowed: bool = False,
    ) -> SpatialReferenceResolution:
        path = Path(source)
        evidence: list[SpatialReferenceEvidence] = []
        embedded = normalize_crs(embedded_crs)
        if not embedded:
            embedded = _discover_embedded_crs(path, ept_payload)
        if not embedded and ept_payload:
            resolved_ept = resolve_ept_spatial_reference(dict(ept_payload))
            embedded = normalize_crs(resolved_ept.crs_text) if resolved_ept.valid else ""
        if embedded:
            evidence.append(SpatialReferenceEvidence("embedded_metadata", embedded, SpatialReferenceConfidence.AUTHORITATIVE, "Dataset CRS metadata"))
        evidence.extend(_sidecar_evidence(path))
        repository = path if path.is_dir() else path.parent
        if self.assignment_store is not None:
            assignment = self.assignment_store.assignment_for(path, repository)
            if assignment is not None and normalize_crs(assignment.crs):
                evidence.append(assignment)
        if repository_context and repository_context.can_inherit and repository_context.resolved_crs:
            evidence.append(SpatialReferenceEvidence("repository_consensus", repository_context.resolved_crs, SpatialReferenceConfidence.HIGH, f"{repository_context.agreement_count}/{repository_context.sampled_count} sampled sources agree"))
        matched_qgis = _matched_qgis_crs(path, qgis_context or {})
        if matched_qgis:
            evidence.append(SpatialReferenceEvidence("qgis_layer_assignment", matched_qgis, SpatialReferenceConfidence.HIGH, "Exact datasource path match"))

        conflict = _conflicting_high_confidence(evidence)
        if conflict:
            return SpatialReferenceResolution(SpatialReferenceStatus.CONFLICT, evidence=tuple(evidence), user_action_required=True, warnings=("Conflicting coordinate-system evidence was found: " + ", ".join(conflict),))
        selected = _select_evidence(evidence)
        if selected:
            status = SpatialReferenceStatus.RESOLVED_AUTHORITATIVE
            if selected.source == "repository_consensus":
                status = SpatialReferenceStatus.RESOLVED_REPOSITORY_INHERITANCE
            elif "assignment" in selected.source:
                status = SpatialReferenceStatus.RESOLVED_USER_ASSIGNMENT
            target = normalize_crs(polygon_crs or project_crs) if spatial_alignment_required else selected.crs
            transform = bool(target and not compare_crs(selected.crs, target).horizontally_equivalent)
            horizontal, vertical, authority = _components(selected.crs)
            return SpatialReferenceResolution(status, selected.crs, horizontal, vertical, authority, selected.source, selected.confidence, tuple(evidence), transform, True, True, False)

        suggestion = normalize_crs(project_crs) if project_crs and polygon_crs and compare_crs(project_crs, polygon_crs).horizontally_equivalent else ""
        if spatial_alignment_required:
            warning = "LiDAR coordinate system is unknown; spatial alignment requires an assignment."
            if suggestion:
                warning += f" Project and polygon context suggest {suggestion}, but confirmation is required."
            return SpatialReferenceResolution(SpatialReferenceStatus.AMBIGUOUS, source="context_suggestion" if suggestion else "unknown", confidence=SpatialReferenceConfidence.MEDIUM if suggestion else SpatialReferenceConfidence.NONE, evidence=tuple(evidence), user_action_required=True, warnings=(warning,))
        if source_local_allowed:
            return SpatialReferenceResolution(SpatialReferenceStatus.SOURCE_LOCAL_ONLY, source="source_local", confidence=SpatialReferenceConfidence.NONE, evidence=tuple(evidence), safe_for_source_local_processing=True, warnings=("No authoritative CRS was found; processing will retain source coordinates with undefined CRS.",))
        return SpatialReferenceResolution(SpatialReferenceStatus.INVALID, evidence=tuple(evidence), user_action_required=True, warnings=("No valid coordinate system was found.",))


def profile_repository(repository: Path | str, sources: Iterable[object], *, sample_limit: int = 200) -> RepositorySpatialReferenceProfile:
    """Build a bounded consensus profile from source metadata records."""
    root = Path(repository)
    distribution: dict[str, int] = {}
    unknown = 0
    sampled = 0
    for item in sources:
        if sampled >= max(1, sample_limit):
            break
        sampled += 1
        raw = getattr(item, "embedded_crs", None) or getattr(item, "source_crs", None)
        crs = normalize_crs(raw)
        if crs:
            distribution[crs] = distribution.get(crs, 0) + 1
        else:
            unknown += 1
    ordered = tuple(sorted(distribution.items(), key=lambda value: (-value[1], value[0])))
    known = sum(distribution.values())
    winner, agreement = ordered[0] if ordered else ("", 0)
    disagreement = known - agreement
    confidence = SpatialReferenceConfidence.NONE
    status = "unresolved"
    warnings: tuple[str, ...] = ()
    if len(distribution) > 1:
        status = "conflict"
        warnings = ("Multiple authoritative coordinate systems were detected in this repository.",)
    elif winner and disagreement == 0 and agreement >= 2 and agreement / max(1, known) >= 0.9:
        status = "resolved"
        confidence = SpatialReferenceConfidence.HIGH
    return RepositorySpatialReferenceProfile(root, repository_fingerprint(root), winner if status == "resolved" else "", confidence, sampled, agreement, disagreement, unknown, ordered, status, warnings)


def normalize_crs(value: object) -> str:
    """Return a canonical horizontal authority where possible."""
    text = str(value or "").strip()
    if not text or text.upper() in {"UNKNOWN", "NONE"}:
        return ""
    try:
        from pyproj import CRS  # type: ignore

        crs = CRS.from_user_input(text)
        horizontal = crs.sub_crs_list[0] if crs.is_compound and crs.sub_crs_list else crs
        authority = horizontal.to_authority()
        return f"{authority[0].upper()}:{authority[1]}" if authority else horizontal.to_wkt()
    except Exception:
        pass
    match = re.search(r'(?:AUTHORITY|ID)\s*\[\s*["\']([A-Za-z0-9_+-]+)["\']\s*,\s*["\']?(\d+)["\']?\s*\]', text, re.IGNORECASE)
    if match:
        return f"{match.group(1).upper()}:{match.group(2)}"
    match = re.fullmatch(r"([A-Za-z][A-Za-z0-9_+-]*):(\d+)", text)
    return f"{match.group(1).upper()}:{match.group(2)}" if match else ""


def repository_fingerprint(repository: Path | str) -> str:
    root = Path(repository)
    parts = [_path_key(root)]
    try:
        for path in sorted(root.iterdir(), key=lambda item: item.name.casefold())[:64]:
            try:
                stat = path.stat()
                parts.append(f"{path.name}|{stat.st_size}|{stat.st_mtime_ns}")
            except OSError:
                continue
    except OSError:
        pass
    return hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()


def _sidecar_evidence(path: Path) -> tuple[SpatialReferenceEvidence, ...]:
    candidates = (path.with_suffix(".prj"), path.with_suffix(".wkt"), path.with_suffix(".metadata.json"), path.parent / "metadata.json", path.parent / "metadata.xml", path.parent / "repository.prj")
    found: list[SpatialReferenceEvidence] = []
    for candidate in candidates:
        if not candidate.is_file():
            continue
        try:
            text = candidate.read_text(encoding="utf-8", errors="replace")[:100000]
            crs = _crs_from_supported_sidecar(candidate, text)
        except OSError:
            continue
        if crs:
            source = "file_sidecar" if candidate.stem == path.stem else "repository_sidecar"
            confidence = SpatialReferenceConfidence.AUTHORITATIVE if source == "file_sidecar" else SpatialReferenceConfidence.HIGH
            found.append(SpatialReferenceEvidence(source, crs, confidence, str(candidate)))
    return tuple(found)


def _discover_embedded_crs(path: Path, ept_payload: Mapping[str, object] | None) -> str:
    """Read bounded source metadata when the caller did not already provide it."""
    if path.name.lower() == "ept.json":
        payload = dict(ept_payload or {})
        if not payload and path.is_file():
            try:
                value = json.loads(path.read_text(encoding="utf-8"))
                payload = value if isinstance(value, dict) else {}
            except (OSError, json.JSONDecodeError):
                payload = {}
        resolved = resolve_ept_spatial_reference(payload)
        return normalize_crs(resolved.crs_text) if resolved.valid else ""
    if not path.is_file():
        return ""
    try:
        from .lidar_catalog_builder import inspect_lidar_header
        from .lidar_catalog_models import stable_root_id

        record = inspect_lidar_header(path, path.parent, stable_root_id(path.parent))
        return normalize_crs(record.source_crs)
    except Exception:
        return ""


def _crs_from_supported_sidecar(path: Path, text: str) -> str:
    suffixes = "".join(path.suffixes).lower()
    if suffixes.endswith(".json"):
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            return ""
        if not isinstance(payload, dict):
            return ""
        for key in ("crs", "srs", "spatialreference", "spatial_reference", "epsg"):
            value = payload.get(key)
            if isinstance(value, dict):
                candidate = value.get("authid") or value.get("wkt") or value.get("authority")
            else:
                candidate = f"EPSG:{value}" if key == "epsg" and str(value).isdigit() else value
            normalized = normalize_crs(candidate)
            if normalized:
                return normalized
        return ""
    if path.suffix.lower() == ".xml":
        try:
            root = ET.fromstring(text)
        except ET.ParseError:
            return ""
        for element in root.iter():
            if element.tag.split("}")[-1].casefold() in {"crs", "srs", "spatialreference", "spatial_reference", "epsg"}:
                candidate = f"EPSG:{element.text}" if element.tag.split("}")[-1].casefold() == "epsg" and str(element.text or "").strip().isdigit() else element.text
                normalized = normalize_crs(candidate)
                if normalized:
                    return normalized
        return ""
    return normalize_crs(text)


def _conflicting_high_confidence(evidence: Iterable[SpatialReferenceEvidence]) -> tuple[str, ...]:
    high = [item for item in evidence if item.confidence in {SpatialReferenceConfidence.AUTHORITATIVE, SpatialReferenceConfidence.HIGH}]
    values: list[str] = []
    for item in high:
        if not any(compare_crs(item.crs, existing).horizontally_equivalent for existing in values):
            values.append(item.crs)
    return tuple(values) if len(values) > 1 else ()


def _select_evidence(evidence: Iterable[SpatialReferenceEvidence]) -> SpatialReferenceEvidence | None:
    precedence = {"embedded_metadata": 0, "file_sidecar": 1, "persisted_file_assignment": 2, "persisted_repository_assignment": 3, "repository_consensus": 4, "repository_sidecar": 5, "qgis_layer_assignment": 6}
    valid = [item for item in evidence if normalize_crs(item.crs)]
    return min(valid, key=lambda item: precedence.get(item.source, 99)) if valid else None


def _matched_qgis_crs(path: Path, context: Mapping[str, str]) -> str:
    target = _path_key(path)
    for source, crs in context.items():
        if _path_key(Path(str(source).split("|", 1)[0])) == target:
            return normalize_crs(crs)
    return ""


def _components(crs: str) -> tuple[str, str, str]:
    try:
        from pyproj import CRS  # type: ignore

        value = CRS.from_user_input(crs)
        horizontal = value.sub_crs_list[0] if value.is_compound and value.sub_crs_list else value
        vertical = value.sub_crs_list[1].to_string() if value.is_compound and len(value.sub_crs_list) > 1 else ""
        authority = horizontal.to_authority()
        canonical = f"{authority[0].upper()}:{authority[1]}" if authority else horizontal.to_string()
        return canonical, vertical, authority[0].upper() if authority else ""
    except Exception:
        authority = crs.split(":", 1)[0] if ":" in crs else ""
        return crs, "", authority


def _path_key(path: Path) -> str:
    try:
        return str(path.expanduser().resolve()).casefold()
    except OSError:
        return str(path.expanduser().absolute()).casefold()


def _file_signature(path: Path) -> str:
    try:
        stat = path.stat()
        value = f"{_path_key(path)}|{stat.st_size}|{stat.st_mtime_ns}"
    except OSError:
        value = _path_key(path)
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


__all__ = [
    "RepositorySpatialReferenceProfile", "SpatialReferenceAssignmentStore", "SpatialReferenceConfidence",
    "SpatialReferenceEvidence", "SpatialReferenceResolution", "SpatialReferenceResolver", "SpatialReferenceStatus",
    "normalize_crs", "profile_repository", "repository_fingerprint",
]
