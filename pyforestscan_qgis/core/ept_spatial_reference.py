"""EPT spatial-reference parsing and validation helpers."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Callable

EPT_CRS_PARSER_VERSION = "phase27s-ept-crs-v1"
INCOMPLETE_CRS_AUTHORITY = "INCOMPLETE_CRS_AUTHORITY"
_AUTHORITY_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_+-]*$")
_AUTHID_RE = re.compile(r"^([A-Za-z][A-Za-z0-9_+-]*):(\d+)$")


@dataclass(frozen=True)
class ResolvedSpatialReference:
    """Typed EPT CRS resolution result."""

    authid: str = ""
    authority: str = ""
    horizontal_code: str = ""
    vertical_code: str = ""
    wkt: str = ""
    projjson: dict[str, Any] | str | None = None
    source: str = "unknown"
    valid: bool = False
    geographic: bool | None = None
    projected: bool | None = None
    units: str = ""
    warnings: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()
    raw_srs: dict[str, Any] = field(default_factory=dict)

    @property
    def crs_text(self) -> str:
        return self.authid or self.wkt or (_projjson_text(self.projjson) if self.projjson else "")

    def to_dict(self) -> dict[str, Any]:
        return {
            "authid": self.authid,
            "authority": self.authority,
            "horizontal_code": self.horizontal_code,
            "vertical_code": self.vertical_code,
            "wkt": self.wkt,
            "projjson": self.projjson,
            "source": self.source,
            "valid": self.valid,
            "geographic": self.geographic,
            "projected": self.projected,
            "units": self.units,
            "warnings": list(self.warnings),
            "errors": list(self.errors),
            "raw_srs": self.raw_srs,
            "parser_version": EPT_CRS_PARSER_VERSION,
        }


Validator = Callable[[str], bool]


def resolve_ept_spatial_reference(
    payload: dict[str, Any] | None,
    *,
    user_override: str | None = None,
    pdal_probe: dict[str, Any] | None = None,
    validator: Validator | None = None,
) -> ResolvedSpatialReference:
    """Resolve an EPT CRS without letting incomplete authority strings through."""
    warnings: list[str] = []
    errors: list[str] = []
    raw_srs = _raw_srs(payload)
    candidates: list[ResolvedSpatialReference] = []

    for key in ("wkt2", "wkt"):
        wkt = _text(raw_srs.get(key))
        if wkt:
            candidates.append(_candidate(wkt=wkt, source="ept_wkt", raw_srs=raw_srs, validator=validator))

    projjson = raw_srs.get("projjson") or raw_srs.get("proj_json")
    if projjson:
        candidates.append(_candidate(projjson=projjson, source="ept_projjson", raw_srs=raw_srs, validator=validator))

    authority = _text(raw_srs.get("authority"))
    horizontal = _text(raw_srs.get("horizontal") or raw_srs.get("code") or raw_srs.get("epsg"))
    vertical = _text(raw_srs.get("vertical"))
    authority_authid = authority.upper() if _AUTHID_RE.match(authority) else ""
    authid = authority_authid or normalize_authority_code(authority, horizontal)
    if authid:
        match = _AUTHID_RE.match(authid)
        candidates.append(
            _candidate(
                authid=authid,
                authority=(match.group(1).upper() if match else authority.upper()),
                horizontal_code=horizontal or (match.group(2) if match else ""),
                vertical_code=vertical,
                source="ept_authority_code",
                raw_srs=raw_srs,
                validator=validator,
            )
        )
    elif authority and not horizontal:
        errors.append(INCOMPLETE_CRS_AUTHORITY)
        warnings.append(f"EPT metadata supplied authority {authority} but no usable horizontal code was parsed.")
    elif horizontal and not authority:
        errors.append("INCOMPLETE_CRS_AUTHORITY_CODE")
        warnings.append("EPT metadata supplied a horizontal CRS code without an authority.")

    if pdal_probe:
        for key in ("authid", "detected_crs", "horizontal_crs", "spatialreference", "srs", "wkt"):
            value = _text(pdal_probe.get(key))
            if value and not is_incomplete_crs_identifier(value):
                candidates.append(_candidate(authid=value if _AUTHID_RE.match(value) else "", wkt=value if not _AUTHID_RE.match(value) else "", source="pdal_metadata", raw_srs=raw_srs, validator=validator))

    override = _text(user_override)
    if override:
        candidates.append(_candidate(authid=override if _AUTHID_RE.match(override) else "", wkt=override if not _AUTHID_RE.match(override) else "", source="user_override", raw_srs=raw_srs, validator=validator))

    for candidate in candidates:
        if candidate.valid and candidate.crs_text and not is_incomplete_crs_identifier(candidate.crs_text):
            if warnings:
                return _replace_messages(candidate, warnings=tuple(warnings))
            return candidate

    if candidates:
        errors.extend(error for candidate in candidates for error in candidate.errors)
    if not raw_srs:
        errors.append("EPT_SRS_MISSING")
    return ResolvedSpatialReference(source="unknown", valid=False, warnings=tuple(dict.fromkeys(warnings)), errors=tuple(dict.fromkeys(errors)), raw_srs=raw_srs)


def normalize_authority_code(authority: Any, horizontal_code: Any) -> str:
    authority_text = _text(authority).upper()
    code_text = _text(horizontal_code)
    if not authority_text or not code_text:
        return ""
    if not _AUTHORITY_RE.match(authority_text):
        return ""
    if not code_text.isdigit():
        return ""
    return f"{authority_text}:{code_text}"


def is_incomplete_crs_identifier(value: Any) -> bool:
    text = _text(value).upper()
    if not text:
        return True
    if text in {"EPSG", "ESRI", "AUTHORITY", "UNKNOWN"}:
        return True
    if text.endswith(":") or text.startswith(":"):
        return True
    if _AUTHORITY_RE.match(text) and ":" not in text and not _looks_like_wkt(text):
        return True
    return False


def ept_spatial_metadata_summary(path: str, payload: dict[str, Any] | None, resolved: ResolvedSpatialReference, pdal_probe: dict[str, Any] | None = None) -> dict[str, Any]:
    """Return support-friendly EPT CRS diagnostics without reading point data."""
    root_bounds = payload.get("bounds") if isinstance(payload, dict) else None
    return {
        "path": path,
        "raw_srs": _raw_srs(payload),
        "resolved_crs": resolved.to_dict(),
        "root_bounds": root_bounds,
        "point_count": payload.get("points") if isinstance(payload, dict) else None,
        "schema": payload.get("schema") if isinstance(payload, dict) else None,
        "pdal_probe": pdal_probe or {},
        "parser_version": EPT_CRS_PARSER_VERSION,
    }


def _candidate(
    *,
    authid: str = "",
    authority: str = "",
    horizontal_code: str = "",
    vertical_code: str = "",
    wkt: str = "",
    projjson: dict[str, Any] | str | None = None,
    source: str,
    raw_srs: dict[str, Any],
    validator: Validator | None,
) -> ResolvedSpatialReference:
    text = authid or wkt or (_projjson_text(projjson) if projjson else "")
    errors: list[str] = []
    if is_incomplete_crs_identifier(text):
        errors.append(INCOMPLETE_CRS_AUTHORITY)
    valid = not errors and _validate_crs_text(text, validator)
    if not valid and not errors:
        errors.append("CRS_VALIDATION_FAILED")
    return ResolvedSpatialReference(
        authid=authid,
        authority=authority or (_AUTHID_RE.match(authid).group(1).upper() if _AUTHID_RE.match(authid) else ""),
        horizontal_code=horizontal_code or (_AUTHID_RE.match(authid).group(2) if _AUTHID_RE.match(authid) else ""),
        vertical_code=vertical_code,
        wkt=wkt,
        projjson=projjson,
        source=source,
        valid=valid,
        geographic=_guess_geographic(text),
        projected=_guess_projected(text),
        units=_guess_units(text),
        errors=tuple(errors),
        raw_srs=raw_srs,
    )


def _validate_crs_text(text: str, validator: Validator | None) -> bool:
    if validator is not None:
        try:
            return bool(validator(text))
        except Exception:
            return False
    try:
        from pyproj import CRS  # type: ignore

        CRS.from_user_input(text)
        return True
    except Exception:
        pass
    return bool(_AUTHID_RE.match(text) or _looks_like_wkt(text) or _looks_like_projjson(text))


def _raw_srs(payload: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {}
    srs = payload.get("srs")
    if isinstance(srs, dict):
        return dict(srs)
    for key in ("spatialreference", "spatial_reference", "spatial-reference", "crs"):
        value = payload.get(key)
        if isinstance(value, dict):
            return dict(value)
        if isinstance(value, str) and value.strip():
            return {"wkt": value}
    return {}


def _replace_messages(resolved: ResolvedSpatialReference, *, warnings: tuple[str, ...] = (), errors: tuple[str, ...] = ()) -> ResolvedSpatialReference:
    return ResolvedSpatialReference(
        authid=resolved.authid,
        authority=resolved.authority,
        horizontal_code=resolved.horizontal_code,
        vertical_code=resolved.vertical_code,
        wkt=resolved.wkt,
        projjson=resolved.projjson,
        source=resolved.source,
        valid=resolved.valid,
        geographic=resolved.geographic,
        projected=resolved.projected,
        units=resolved.units,
        warnings=tuple(dict.fromkeys((*resolved.warnings, *warnings))),
        errors=tuple(dict.fromkeys((*resolved.errors, *errors))),
        raw_srs=resolved.raw_srs,
    )


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if float(value).is_integer():
            return str(int(value))
    if isinstance(value, dict):
        return ""
    return str(value).strip()


def _projjson_text(value: dict[str, Any] | str | None) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict):
        return json.dumps(value, sort_keys=True)
    return ""


def _looks_like_wkt(text: str) -> bool:
    upper = text.upper()
    return any(token in upper for token in ("PROJCRS[", "GEOGCRS[", "GEODCRS[", "PROJCS[", "GEOGCS[", "BOUNDCRS[", "COMPD_CS["))


def _looks_like_projjson(text: str) -> bool:
    stripped = text.strip()
    if not stripped.startswith("{"):
        return False
    try:
        payload = json.loads(stripped)
    except json.JSONDecodeError:
        return False
    return isinstance(payload, dict) and bool(payload.get("type") or payload.get("$schema") or payload.get("name"))


def _guess_geographic(text: str) -> bool | None:
    upper = text.upper()
    if "GEOGCRS" in upper or "GEOGCS" in upper:
        return True
    if "PROJCRS" in upper or "PROJCS" in upper:
        return False
    return None


def _guess_projected(text: str) -> bool | None:
    geographic = _guess_geographic(text)
    return None if geographic is None else not geographic


def _guess_units(text: str) -> str:
    upper = text.upper()
    if "UNIT[\"METRE\"" in upper or "LENGTHUNIT[\"METRE\"" in upper:
        return "metre"
    if "UNIT[\"DEGREE\"" in upper or "ANGLEUNIT[\"DEGREE\"" in upper:
        return "degree"
    return ""


__all__ = [
    "EPT_CRS_PARSER_VERSION",
    "INCOMPLETE_CRS_AUTHORITY",
    "ResolvedSpatialReference",
    "ept_spatial_metadata_summary",
    "is_incomplete_crs_identifier",
    "normalize_authority_code",
    "resolve_ept_spatial_reference",
]
