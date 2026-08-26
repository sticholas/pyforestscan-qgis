"""Resolve raw LiDAR metadata into the spatial profile used for selection."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .crs_alignment import compare_crs
from .lidar_source_metadata import LidarSourceMetadata
from .processing_spatial_context import (
    CoordinateSpaceCompatibility,
    EffectiveSpatialContext,
    EffectiveSpatialMode,
    SourceLocalFallbackPolicy,
    resolve_effective_spatial_context,
)
from .spatial_assignment import LinearUnit
from .spatial_selection import Bounds2D
from .spatial_reference_resolver import (
    SpatialReferenceAssignmentStore,
    SpatialReferenceResolver,
    SpatialReferenceStatus,
    default_spatial_assignment_store,
    normalize_crs,
)


@dataclass(frozen=True)
class EffectiveSourceSpatialProfile:
    """Raw and resolved spatial truth for one repository member."""

    source_path: Path
    repository_path: Path
    raw_crs: str
    effective_crs: str
    assignment_source: str
    status: SpatialReferenceStatus
    safe_for_spatial_alignment: bool
    mode: EffectiveSpatialMode = EffectiveSpatialMode.UNRESOLVED
    effective_units: LinearUnit | None = None
    compatibility: CoordinateSpaceCompatibility | None = None
    context: EffectiveSpatialContext | None = None
    warnings: tuple[str, ...] = ()

    @property
    def conflict(self) -> bool:
        return self.status is SpatialReferenceStatus.CONFLICT


def resolve_effective_source_spatial_profile(
    metadata: LidarSourceMetadata,
    repository_path: Path | str,
    *,
    assignment_store: SpatialReferenceAssignmentStore | None = None,
    repository_crs_override: str | None = None,
    polygon_crs: str | None = None,
    polygon_bounds: Bounds2D | None = None,
    policy: SourceLocalFallbackPolicy | None = None,
    allow_polygon_fallback: bool = True,
) -> EffectiveSourceSpatialProfile:
    """Resolve effective CRS before any polygon overlap comparison.

    ``repository_crs_override`` is retained as a compatibility input for old
    catalogs and request manifests. New user assignments live in the shared
    spatial-assignment store.
    """

    repository = Path(repository_path)
    store = assignment_store or default_spatial_assignment_store()
    resolution = SpatialReferenceResolver(store).resolve(
        metadata.path,
        embedded_crs=metadata.embedded_crs,
        polygon_crs=polygon_crs,
        spatial_alignment_required=True,
        source_local_allowed=False,
    )
    raw_crs = normalize_crs(metadata.embedded_crs)
    explicit_assignment = store.spatial_assignment_for(metadata.path, repository)
    assigned_crs = normalize_crs(explicit_assignment.horizontal_crs) if explicit_assignment is not None else ""
    if assigned_crs:
        if raw_crs and not compare_crs(raw_crs, assigned_crs).horizontally_equivalent:
            context = resolve_effective_spatial_context(raw_crs=raw_crs, contradictory_evidence=True, polygon_crs=polygon_crs or "", source_bounds=metadata.bounds, polygon_bounds=polygon_bounds, polygon_alignment_required=True, policy=policy)
            return EffectiveSourceSpatialProfile(
                metadata.path,
                repository,
                raw_crs,
                "",
                explicit_assignment.assignment_type.value,
                SpatialReferenceStatus.CONFLICT,
                False,
                context.mode, context.units, context.compatibility, context,
                (f"Embedded CRS {raw_crs} conflicts with trusted assignment {assigned_crs}.",),
            )
        effective = raw_crs or assigned_crs
        context = resolve_effective_spatial_context(raw_crs=raw_crs, resolved_crs=effective, resolution_source="embedded_metadata" if raw_crs else explicit_assignment.assignment_type.value, assignment_scope=explicit_assignment.scope.value, polygon_crs=polygon_crs or "", source_bounds=metadata.bounds, polygon_bounds=polygon_bounds, polygon_alignment_required=True, policy=policy)
        return EffectiveSourceSpatialProfile(
            metadata.path,
            repository,
            raw_crs,
            raw_crs or assigned_crs,
            "embedded_metadata" if raw_crs else explicit_assignment.assignment_type.value,
            SpatialReferenceStatus.RESOLVED_AUTHORITATIVE if raw_crs else SpatialReferenceStatus.RESOLVED_USER_ASSIGNMENT,
            True,
            context.mode, context.units, context.compatibility, context,
        )
    legacy_crs = normalize_crs(repository_crs_override)
    if legacy_crs:
        if raw_crs and not compare_crs(raw_crs, legacy_crs).horizontally_equivalent:
            context = resolve_effective_spatial_context(raw_crs=raw_crs, contradictory_evidence=True, polygon_crs=polygon_crs or "", source_bounds=metadata.bounds, polygon_bounds=polygon_bounds, polygon_alignment_required=True, policy=policy)
            return EffectiveSourceSpatialProfile(
                metadata.path,
                repository,
                raw_crs,
                "",
                "legacy_repository_override_conflict",
                SpatialReferenceStatus.CONFLICT,
                False,
                context.mode, context.units, context.compatibility, context,
                (f"Embedded CRS {raw_crs} conflicts with repository assignment {legacy_crs}.",),
            )
        if not resolution.resolved:
            context = resolve_effective_spatial_context(raw_crs=raw_crs, resolved_crs=legacy_crs, resolution_source="legacy_repository_override", assignment_scope="REPOSITORY", polygon_crs=polygon_crs or "", source_bounds=metadata.bounds, polygon_bounds=polygon_bounds, polygon_alignment_required=True, policy=policy)
            return EffectiveSourceSpatialProfile(
                metadata.path,
                repository,
                raw_crs,
                legacy_crs,
                "legacy_repository_override",
                SpatialReferenceStatus.RESOLVED_USER_ASSIGNMENT,
                True,
                context.mode, context.units, context.compatibility, context,
            )
    context = resolve_effective_spatial_context(
        raw_crs=raw_crs,
        resolved_crs=resolution.resolved_crs,
        resolution_source=resolution.source,
        polygon_crs=polygon_crs or "",
        source_bounds=metadata.bounds,
        polygon_bounds=polygon_bounds,
        polygon_alignment_required=True,
        policy=policy,
    )
    effective_crs = context.effective_crs if allow_polygon_fallback else resolution.resolved_crs
    status = resolution.status
    if context.mode is EffectiveSpatialMode.ASSUMED_MATCHING_COORDINATE_SPACE:
        status = SpatialReferenceStatus.RESOLVED_USER_ASSIGNMENT
    return EffectiveSourceSpatialProfile(
        metadata.path,
        repository,
        raw_crs,
        effective_crs,
        context.provenance or resolution.source,
        status,
        context.alignment_allowed if allow_polygon_fallback else resolution.safe_for_spatial_alignment,
        context.mode, context.units, context.compatibility, context,
        tuple(dict.fromkeys((*resolution.warnings, *context.warnings))),
    )


def shared_repository_crs(
    repository_path: Path | str,
    *,
    assignment_store: SpatialReferenceAssignmentStore | None = None,
) -> tuple[str, str]:
    """Return a valid shared repository assignment and its provenance."""

    repository = Path(repository_path)
    store = assignment_store or default_spatial_assignment_store()
    assignment = store.spatial_assignment_for(repository, repository)
    if assignment is None or not assignment.horizontal_crs:
        return "", ""
    return normalize_crs(assignment.horizontal_crs), assignment.assignment_type.value
