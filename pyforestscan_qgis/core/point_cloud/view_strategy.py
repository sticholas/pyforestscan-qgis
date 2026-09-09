"""Pure intake policy. Cache/LOD identity never replaces the original source."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import hashlib
import json
import math
import re


class ViewStrategy(str, Enum):
    DIRECT = "DIRECT"
    DIRECT_STREAMED = "DIRECT_STREAMED"
    COPC_NATIVE = "COPC_NATIVE"
    EPT_NATIVE = "EPT_NATIVE"
    BUILD_VIEW_CACHE = "BUILD_VIEW_CACHE"
    REUSE_VIEW_CACHE = "REUSE_VIEW_CACHE"


class CacheState(str, Enum):
    VALID = "VALID"
    BUILDING = "BUILDING"
    STALE = "STALE"
    FAILED = "FAILED"
    PURGEABLE = "PURGEABLE"


class StorageCategory(str, Enum):
    SESSION = "SESSION"
    VIEW_CACHE = "VIEW_CACHE"
    TEMP = "TEMP"
    DIAGNOSTICS = "DIAGNOSTICS"
    EXPORT = "EXPORT"


CACHE_FORMAT_VERSION = 1
CONVERSION_POLICY = "original-authority-copc-v2-scan-flags"
# Provisional bounds, not claims of empirically qualified hardware capacity.
DIRECT_POINT_CEILING = 100_000
DIRECT_FILE_BYTE_CEILING = 16 * 1024 * 1024
DIRECT_DECODED_BYTE_CEILING = 64 * 1024 * 1024


@dataclass(frozen=True)
class SourceViewFacts:
    source_format: str
    file_bytes: int
    point_count: int
    dimensions: tuple[str, ...] = ()
    crs: str = ""
    point_record_bytes: int = 38
    storage_type: str = "unknown"
    network: bool = False
    hierarchical: bool = False
    fingerprint: str = ""
    modified_ns: int = 0
    available_ram_bytes: int | None = None
    bounds: tuple[float, ...] = ()
    performance_profile: dict = field(default_factory=dict)

    def __post_init__(self):
        for name in ("file_bytes", "point_count", "modified_ns"):
            value = getattr(self, name)
            if type(value) is not int or value < 0:
                raise ValueError(f"{name} must be a nonnegative integer.")
        if type(self.point_record_bytes) is not int or self.point_record_bytes <= 0:
            raise ValueError("point_record_bytes must be positive.")
        if self.available_ram_bytes is not None and (
                type(self.available_ram_bytes) is not int or self.available_ram_bytes < 0):
            raise ValueError("Available RAM must be nonnegative or unknown.")
        if self.fingerprint and not re.fullmatch(r"[0-9a-f]{64}", self.fingerprint):
            raise ValueError("Invalid source SHA256.")
        if self.bounds and (len(self.bounds) != 6 or
                any(not math.isfinite(v) for v in self.bounds) or
                any(self.bounds[i] > self.bounds[i + 3] for i in range(3))):
            raise ValueError("Invalid source extent.")

    @property
    def estimated_direct_bytes(self):
        # Full-file compressed copy, WASM input, decoded records, worker attribute
        # buffers and GPU/CPU residency. This is an estimate, not measured RSS.
        return self.file_bytes * 2 + self.point_count * (self.point_record_bytes * 2 + 160)


def cache_identity(facts: SourceViewFacts, tool_version: str) -> dict:
    if not facts.fingerprint or not tool_version.strip():
        raise ValueError("Cache identity requires source SHA256 and indexer version.")
    return {
        "source_sha256": facts.fingerprint,
        "source_size": facts.file_bytes,
        "source_mtime_ns": facts.modified_ns,
        "point_count": facts.point_count,
        "dimensions": sorted(facts.dimensions),
        "crs": facts.crs,
        "cache_format_version": CACHE_FORMAT_VERSION,
        "conversion_policy": CONVERSION_POLICY,
        "tool_version": tool_version,
    }


def cache_key(identity: dict) -> str:
    return hashlib.sha256(json.dumps(identity, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode("utf-8")).hexdigest()


def session_cache_hint(info, source_sha256):
    """Optional source-bound metadata; no derivative paths or edit addresses."""
    if not isinstance(info, dict) or info.get("sha256") != source_sha256:
        return {}
    try:
        strategy = ViewStrategy(info["strategy"]).value
    except (KeyError, ValueError, TypeError):
        return {}
    key = info.get("cache_fingerprint")
    if key is not None and (not isinstance(key, str) or not re.fullmatch(r"[0-9a-f]{64}", key)):
        return {}
    return {"strategy": strategy, "cache_fingerprint": key, "source_sha256": source_sha256}


@dataclass(frozen=True)
class ViewPlan:
    strategy: ViewStrategy
    reason: str
    estimated_direct_bytes: int
    original_is_authority: bool = True
    threshold_qualified: bool = False


class PointCloudViewStrategyPlanner:
    """Select only implemented, explicitly enabled paths.

    DIRECT_STREAMED is reserved until a bounded raw streaming adapter is
    qualified. A profile may lower direct admission, never lift safety ceilings.
    Native hierarchical sources do not need a full repository fingerprint.
    """

    def __init__(self, *, direct_available=False):
        self.direct_available = direct_available

    def plan(self, facts: SourceViewFacts, *, cache_state=None,
             cache_identity_matches=False, cache_file_verified=False) -> ViewPlan:
        fmt = facts.source_format.upper()
        estimated = facts.estimated_direct_bytes
        if fmt == "EPT":
            return ViewPlan(ViewStrategy.EPT_NATIVE, "Stream requested hierarchy and nodes.", estimated)
        if fmt == "COPC":
            return ViewPlan(ViewStrategy.COPC_NATIVE, "Use the native indexed source.", estimated)
        if fmt not in ("LAS", "LAZ"):
            raise ValueError("Select LAS, LAZ, COPC or EPT.")
        if facts.point_count <= 0:
            raise ValueError("A verified nonempty point count is required.")
        if facts.hierarchical:
            raise ValueError("Identify the indexed source format before planning.")
        # Metadata alone cannot authorize a cache; callers must verify its file.
        if (cache_state == CacheState.VALID and cache_identity_matches and
                cache_file_verified and facts.fingerprint):
            return ViewPlan(ViewStrategy.REUSE_VIEW_CACHE, "Reuse verified read-only view cache.", estimated)
        point_limit = DIRECT_POINT_CEILING
        profile_limit = facts.performance_profile.get("direct_point_ceiling")
        if type(profile_limit) is int and profile_limit > 0:
            point_limit = min(point_limit, profile_limit)
        memory_limit = DIRECT_DECODED_BYTE_CEILING
        if facts.available_ram_bytes is not None:
            memory_limit = min(memory_limit, facts.available_ram_bytes // 8)
        if (self.direct_available and facts.point_count <= point_limit and
                facts.file_bytes <= DIRECT_FILE_BYTE_CEILING and estimated <= memory_limit):
            return ViewPlan(ViewStrategy.DIRECT, "Bounded full-file direct view.", estimated)
        return ViewPlan(ViewStrategy.BUILD_VIEW_CACHE,
                        "Prepare an optimized interactive view in managed storage.", estimated)
