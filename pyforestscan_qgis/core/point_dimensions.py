"""Authoritative point-dimension capability discovery."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


HAG_ALIASES = (
    "HeightAboveGround",
    "height_above_ground",
    "HAG",
    "NormalizedHeight",
)


@dataclass(frozen=True)
class PointDimensionCapabilities:
    """Dimensions observed at one inspection or execution boundary."""

    names: tuple[str, ...]
    hag_dimension_name: str | None = None

    @classmethod
    def from_names(cls, names: Iterable[object] | None) -> "PointDimensionCapabilities":
        values = tuple(dict.fromkeys(str(name) for name in (names or ()) if str(name)))
        lookup = {name.casefold().replace("_", ""): name for name in values}
        hag = next((lookup.get(alias.casefold().replace("_", "")) for alias in HAG_ALIASES if lookup.get(alias.casefold().replace("_", ""))), None)
        return cls(values, hag)

    @property
    def has_existing_hag(self) -> bool:
        return self.hag_dimension_name is not None

    def to_dict(self) -> dict[str, object]:
        return {"names": list(self.names), "has_existing_hag": self.has_existing_hag, "hag_dimension_name": self.hag_dimension_name}


class SourceDimensionMismatch(RuntimeError):
    """Raised when inspection and execution dimensions disagree."""

    code = "SOURCE_DIMENSION_MISMATCH"

    def __init__(self, expected: str, observed: Iterable[object]) -> None:
        names = tuple(str(name) for name in observed)
        super().__init__(f"SOURCE_DIMENSION_MISMATCH: expected {expected}; observed [{', '.join(names) or 'none'}]. Metadata inspection and execution read disagree.")
        self.expected = expected
        self.observed = names

