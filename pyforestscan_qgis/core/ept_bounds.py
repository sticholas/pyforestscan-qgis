"""Canonical EPT bounds contract for PyForestScan/PDAL requests."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Any

DEFAULT_BOUNDS_SOURCE = "polygon_envelope"
ADAPTER_CONTRACT_VERSION = "ept-bounds-v1"
_SAFE_COORDINATE_ABS_MAX = 1.0e15
_NUMBER_RE = re.compile(r"[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?")


class EptBoundsError(ValueError):
    """Raised when EPT bounds cannot be represented safely."""


@dataclass(frozen=True)
class PdalBoundsValidation:
    """Grammar validation result for a derived PDAL bounds expression."""

    valid: bool
    reason: str = ""
    ranges: tuple[tuple[float, float], ...] = ()


@dataclass(frozen=True)
class EptBounds:
    """Validated EPT bounds with explicit CRS and conversion methods."""

    xmin: float
    xmax: float
    ymin: float
    ymax: float
    zmin: float | None = None
    zmax: float | None = None
    crs: str = ""
    source: str = DEFAULT_BOUNDS_SOURCE
    transformed: bool = False

    def __post_init__(self) -> None:
        values = {
            "xmin": self.xmin,
            "xmax": self.xmax,
            "ymin": self.ymin,
            "ymax": self.ymax,
        }
        if (self.zmin is None) ^ (self.zmax is None):
            raise EptBoundsError("Both zmin and zmax must be supplied for 3D EPT bounds.")
        if self.zmin is not None and self.zmax is not None:
            values["zmin"] = self.zmin
            values["zmax"] = self.zmax
        normalized = {name: _coerce_float(name, value) for name, value in values.items()}
        if not str(self.crs or "").strip():
            raise EptBoundsError("EPT bounds require a CRS.")
        if normalized["xmin"] >= normalized["xmax"]:
            raise EptBoundsError("EPT bounds require xmin < xmax.")
        if normalized["ymin"] >= normalized["ymax"]:
            raise EptBoundsError("EPT bounds require ymin < ymax.")
        if "zmin" in normalized and normalized["zmin"] >= normalized["zmax"]:
            raise EptBoundsError("EPT bounds require zmin < zmax.")
        object.__setattr__(self, "xmin", normalized["xmin"])
        object.__setattr__(self, "xmax", normalized["xmax"])
        object.__setattr__(self, "ymin", normalized["ymin"])
        object.__setattr__(self, "ymax", normalized["ymax"])
        object.__setattr__(self, "zmin", normalized.get("zmin"))
        object.__setattr__(self, "zmax", normalized.get("zmax"))
        object.__setattr__(self, "crs", str(self.crs).strip())
        object.__setattr__(self, "source", str(self.source or DEFAULT_BOUNDS_SOURCE).strip() or DEFAULT_BOUNDS_SOURCE)
        object.__setattr__(self, "transformed", bool(self.transformed))

    @classmethod
    def from_value(
        cls,
        value: Any,
        *,
        crs: str | None = None,
        source: str = DEFAULT_BOUNDS_SOURCE,
        transformed: bool = False,
    ) -> "EptBounds":
        """Build validated bounds from an object, dict, or nested ranges."""
        if isinstance(value, cls):
            if crs and value.crs != crs:
                return cls(value.xmin, value.xmax, value.ymin, value.ymax, value.zmin, value.zmax, crs=crs, source=value.source, transformed=value.transformed)
            return value
        if isinstance(value, dict):
            data = dict(value)
            return cls(
                data.get("xmin"),
                data.get("xmax"),
                data.get("ymin"),
                data.get("ymax"),
                data.get("zmin"),
                data.get("zmax"),
                crs=str(data.get("crs") or crs or ""),
                source=str(data.get("source") or source),
                transformed=bool(data.get("transformed", transformed)),
            )
        if isinstance(value, str):
            raise EptBoundsError("EPT bounds must be structured values; string parsing is not implicit.")
        if isinstance(value, (list, tuple)):
            if len(value) not in {2, 3}:
                raise EptBoundsError("EPT bounds must contain two or three coordinate ranges.")
            ranges = []
            for index, item in enumerate(value):
                if not isinstance(item, (list, tuple)) or isinstance(item, (str, bytes)):
                    raise EptBoundsError("Each EPT coordinate range must be a list or tuple of two numbers.")
                if len(item) != 2:
                    raise EptBoundsError("Each EPT coordinate range must contain exactly two numbers.")
                ranges.append((_coerce_float(f"range{index}_min", item[0]), _coerce_float(f"range{index}_max", item[1])))
            zmin = ranges[2][0] if len(ranges) == 3 else None
            zmax = ranges[2][1] if len(ranges) == 3 else None
            return cls(ranges[0][0], ranges[0][1], ranges[1][0], ranges[1][1], zmin, zmax, crs=str(crs or ""), source=source, transformed=transformed)
        raise EptBoundsError(f"Unsupported EPT bounds value type: {type(value).__name__}.")

    def to_json(self) -> dict[str, Any]:
        """Return the manifest-safe source-of-truth representation."""
        payload: dict[str, Any] = {
            "xmin": self.xmin,
            "xmax": self.xmax,
            "ymin": self.ymin,
            "ymax": self.ymax,
            "crs": self.crs,
            "source": self.source,
            "transformed": self.transformed,
        }
        if self.zmin is not None and self.zmax is not None:
            payload["zmin"] = self.zmin
            payload["zmax"] = self.zmax
        return payload

    def to_pyforestscan_value(self) -> tuple[list[float], list[float]] | tuple[list[float], list[float], list[float]]:
        """Return the exact value shape expected by PyForestScan read_lidar."""
        xy = ([self.xmin, self.xmax], [self.ymin, self.ymax])
        if self.zmin is None or self.zmax is None:
            return xy
        return xy + ([self.zmin, self.zmax],)

    def to_pdal_range_string(self) -> str:
        """Return a deterministic PDAL readers.ept bounds expression."""
        pieces = [f"[{_format_number(lo)}, {_format_number(hi)}]" for lo, hi in self.to_pyforestscan_value()]
        return "(" + ", ".join(pieces) + ")"


def validate_pyforestscan_bounds_value(value: Any) -> None:
    """Assert that the final PyForestScan value has list coordinate ranges."""
    if not isinstance(value, (list, tuple)) or len(value) not in {2, 3}:
        raise EptBoundsError("PyForestScan bounds must be a sequence with two or three coordinate ranges.")
    for item in value:
        if not isinstance(item, list):
            raise EptBoundsError("Each PyForestScan coordinate range must be a list so PDAL receives square brackets.")
        if len(item) != 2:
            raise EptBoundsError("Each PyForestScan coordinate range must contain exactly two numbers.")
        lower = _coerce_float("range_min", item[0])
        upper = _coerce_float("range_max", item[1])
        if lower >= upper:
            raise EptBoundsError("Each PyForestScan coordinate range must be ordered from lower to upper.")
    expression = _expression_from_final_value(value)
    grammar = validate_pdal_bounds_expression(expression)
    if not grammar.valid:
        raise EptBoundsError(grammar.reason)


def validate_pdal_bounds_expression(expression: str) -> PdalBoundsValidation:
    """Validate the derived PDAL range grammar used by readers.ept."""
    if not isinstance(expression, str):
        return PdalBoundsValidation(False, "PDAL bounds expression must be a string.")
    text = expression.strip()
    if not text.startswith("(") or not text.endswith(")"):
        return PdalBoundsValidation(False, "PDAL bounds expression must be wrapped in parentheses.")
    if "'" in text or '"' in text:
        return PdalBoundsValidation(False, "PDAL bounds expression must not contain quoted numeric ranges.")
    inner = text[1:-1].strip()
    ranges: list[tuple[float, float]] = []
    position = 0
    while position < len(inner):
        while position < len(inner) and inner[position].isspace():
            position += 1
        if position >= len(inner):
            break
        if inner[position] != "[":
            return PdalBoundsValidation(False, "Each PDAL coordinate range must use square brackets.")
        close = inner.find("]", position + 1)
        if close < 0:
            return PdalBoundsValidation(False, "Each PDAL coordinate range must close with a square bracket.")
        range_text = inner[position + 1:close].strip()
        parts = [part.strip() for part in range_text.split(",")]
        if len(parts) != 2:
            return PdalBoundsValidation(False, "Each PDAL coordinate range must contain exactly two numeric values.")
        if any(_looks_like_locale_number(part) for part in parts):
            return PdalBoundsValidation(False, "PDAL bounds expression must not use locale thousands separators.")
        try:
            lower = _parse_expression_number(parts[0])
            upper = _parse_expression_number(parts[1])
        except ValueError as exc:
            return PdalBoundsValidation(False, str(exc))
        if lower >= upper:
            return PdalBoundsValidation(False, "Each PDAL coordinate range lower value must be less than upper value.")
        ranges.append((lower, upper))
        position = close + 1
        while position < len(inner) and inner[position].isspace():
            position += 1
        if position < len(inner):
            if inner[position] != ",":
                return PdalBoundsValidation(False, "PDAL coordinate ranges must be comma separated.")
            position += 1
    if len(ranges) not in {2, 3}:
        return PdalBoundsValidation(False, "PDAL bounds expression must contain two or three coordinate ranges.")
    return PdalBoundsValidation(True, ranges=tuple(ranges))


def _coerce_float(name: str, value: Any) -> float:
    if isinstance(value, bool):
        raise EptBoundsError(f"{name} must be a number, not a boolean.")
    if isinstance(value, str):
        raise EptBoundsError(f"{name} must be numeric; strings are not accepted implicitly.")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise EptBoundsError(f"{name} must be numeric.") from exc
    if not math.isfinite(number):
        raise EptBoundsError(f"{name} must be finite.")
    if abs(number) > _SAFE_COORDINATE_ABS_MAX:
        raise EptBoundsError(f"{name} is outside the safe numeric range for EPT bounds.")
    return number


def _parse_expression_number(text: str) -> float:
    if not _NUMBER_RE.fullmatch(text):
        raise ValueError("PDAL bounds expression values must be plain numeric values.")
    number = float(text)
    if not math.isfinite(number):
        raise ValueError("PDAL bounds expression values must be finite.")
    if abs(number) > _SAFE_COORDINATE_ABS_MAX:
        raise ValueError("PDAL bounds expression values are outside the safe numeric range.")
    return number


def _looks_like_locale_number(text: str) -> bool:
    return bool(re.search(r"\d,\d{3}(?:\D|$)", text))


def _format_number(value: float) -> str:
    number = float(value)
    if number == 0:
        return "0"
    if number.is_integer():
        return str(int(number))
    text = str(number)
    if "e" in text.lower():
        text = f"{number:.15f}".rstrip("0").rstrip(".")
    return text


def _expression_from_final_value(value: Any) -> str:
    return "(" + ", ".join(f"[{_format_number(float(item[0]))}, {_format_number(float(item[1]))}]" for item in value) + ")"
