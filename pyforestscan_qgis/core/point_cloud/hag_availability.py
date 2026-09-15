"""Explicit, cacheable HAG availability decisions for viewer and selection contracts."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import json


class HagAvailability(str, Enum):
    NATIVE_HAG = "NATIVE_HAG"
    DERIVED_HAG_CACHED = "DERIVED_HAG_CACHED"
    DERIVED_HAG_AVAILABLE = "DERIVED_HAG_AVAILABLE"
    HAG_REQUIRES_TERRAIN_PREPARATION = "HAG_REQUIRES_TERRAIN_PREPARATION"
    HAG_UNAVAILABLE = "HAG_UNAVAILABLE"


@dataclass(frozen=True)
class HagCacheKey:
    source_fingerprint: str
    method_signature: str
    scope: str = "source"
    parameters: tuple[tuple[str, str], ...] = ()

    def token(self) -> str:
        payload = {
            "source_fingerprint": self.source_fingerprint.lower(),
            "method_signature": self.method_signature,
            "scope": self.scope,
            "parameters": list(self.parameters),
        }
        return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class HagAvailabilityContract:
    status: HagAvailability
    source_dimension: str | None = None
    cache_key: HagCacheKey | None = None
    explanation: str = ""

    @property
    def usable_for_viewing(self) -> bool:
        return self.status in {
            HagAvailability.NATIVE_HAG,
            HagAvailability.DERIVED_HAG_CACHED,
            HagAvailability.DERIVED_HAG_AVAILABLE,
        }

    @property
    def requires_managed_preparation(self) -> bool:
        return self.status is HagAvailability.HAG_REQUIRES_TERRAIN_PREPARATION


def resolve_hag_availability(
    *,
    native_dimension: str | None = None,
    cached_key: HagCacheKey | None = None,
    cache_is_compatible: bool = False,
    dtm_available: bool = False,
    ground_preparation_available: bool = False,
    source_fingerprint: str = "",
    method_signature: str = "",
    scope: str = "source",
) -> HagAvailabilityContract:
    """Resolve HAG state without performing terrain science in QGIS."""
    if native_dimension:
        return HagAvailabilityContract(
            HagAvailability.NATIVE_HAG,
            source_dimension=str(native_dimension),
            explanation="The source provides a native HeightAboveGround dimension.",
        )
    if cached_key is not None and cache_is_compatible:
        return HagAvailabilityContract(
            HagAvailability.DERIVED_HAG_CACHED,
            cache_key=cached_key,
            explanation="A compatible managed HAG result is cached for this source and scope.",
        )
    if dtm_available:
        key = HagCacheKey(source_fingerprint, method_signature or "provided_dtm", scope)
        return HagAvailabilityContract(
            HagAvailability.DERIVED_HAG_AVAILABLE,
            cache_key=key,
            explanation="A compatible DTM-backed HAG derivation is available through the managed engine.",
        )
    if ground_preparation_available:
        key = HagCacheKey(source_fingerprint, method_signature or "classified_ground_delaunay", scope)
        return HagAvailabilityContract(
            HagAvailability.HAG_REQUIRES_TERRAIN_PREPARATION,
            cache_key=key,
            explanation="HAG can be prepared by the managed terrain workflow before viewing or selection.",
        )
    return HagAvailabilityContract(
        HagAvailability.HAG_UNAVAILABLE,
        explanation="No native, cached, DTM-backed, or validated terrain preparation path is available.",
    )


def has_hag_dimension(dimensions: object) -> bool:
    """Return true only when the loaded view exposes a real HAG attribute."""
    for value in dimensions or ():
        normalized = str(value).lower().replace("_", "").replace("-", "")
        if normalized in {"heightaboveground", "hag", "pfshag"}:
            return True
    return False
