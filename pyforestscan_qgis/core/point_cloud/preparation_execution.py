"""Managed-worker preparation of full-resolution arrays, never display samples.

This layer does not load or publish files. Its caller must verify source identity,
preflight memory before loading arrays, and validate a staged LAS/LAZ before
publishing through preparation_publication.
"""
from dataclasses import dataclass

from ..lidar_preparation import HeightNormalizationPlanMode
from ..lidar_preparation_execution import execute_preparation
from ..scientific_boundary import assert_scientific_import_allowed
from .preparation import PreparationOptions


ORIGINAL_Z = "PFSOriginalZ"


@dataclass(frozen=True)
class PreparedArrays:
    arrays: tuple
    input_points: int
    output_points: int
    height_provenance: str | None


def prepare_arrays(arrays, options: PreparationOptions, *, filters_module,
                   assessment=None, plan=None, run_folder=None, job_identity="",
                   cancelled=lambda: False, progress=None):
    """Reuse official filters, preserving caller arrays and explicit height intent."""
    assert_scientific_import_allowed("pyforestscan.filters")
    if not isinstance(options, PreparationOptions):
        raise ValueError("Validated preparation options are required.")
    arrays = tuple(arrays)
    count = sum(len(array) for array in arrays)
    if not count:
        raise ValueError("Preparation requires nonempty full-resolution input.")
    _check_cancelled(cancelled)
    for array in arrays:
        names = array.dtype.names or ()
        if not all(name in names for name in ("X", "Y", "Z")):
            raise ValueError("Preparation requires structured XYZ point records.")
        if options.height_action == "normalize_z" and ORIGINAL_Z in names:
            raise ValueError("PFSOriginalZ already exists; refusing to overwrite height provenance.")
    if options.height_action != "preserve":
        if assessment is None or plan is None or run_folder is None or not job_identity:
            raise ValueError("Height preparation requires a source assessment, plan, and job provenance.")
        allowed = {
            HeightNormalizationPlanMode.USE_EXISTING_HAG,
            HeightNormalizationPlanMode.DTM_EXISTING,
            HeightNormalizationPlanMode.DELAUNAY_FROM_EXISTING_GROUND,
            HeightNormalizationPlanMode.AUTO_CLASSIFY_GROUND_THEN_DELAUNAY,
        }
        if plan.height_mode not in allowed or not plan.can_execute:
            raise ValueError("The height plan is not executable by workspace preparation.")
        if (plan.height_mode is HeightNormalizationPlanMode.AUTO_CLASSIFY_GROUND_THEN_DELAUNAY
                and not options.allow_ground_classification):
            raise ValueError("Automatic ground classification requires explicit consent.")
    prepared = tuple(array.copy() for array in arrays)
    provenance = None
    if options.height_action != "preserve":
        result = execute_preparation(
            prepared, assessment, plan, run_folder=run_folder,
            job_identity=job_identity, filters_module=filters_module, progress=progress)
        prepared = result.arrays
        provenance = str(result.provenance_path)
        if sum(len(array) for array in prepared) != count:
            raise ValueError("Height preparation unexpectedly changed the point count.")
        _check_cancelled(cancelled)
        if options.height_action == "normalize_z":
            import numpy as np
            from numpy.lib.recfunctions import append_fields
            normalized = []
            for array in prepared:
                if ORIGINAL_Z in array.dtype.names:
                    raise ValueError("Height preparation introduced conflicting original-Z provenance.")
                heights = array["HeightAboveGround"]
                if not np.all(np.isfinite(heights)):
                    raise ValueError("Normalized Z requires finite HAG for every point.")
                if array.dtype["Z"].kind != "f":
                    raise ValueError("Normalized Z requires floating-point XYZ records.")
                output = append_fields(array, ORIGINAL_Z, array["Z"].copy(), usemask=False)
                output["Z"] = heights
                normalized.append(output)
            prepared = tuple(normalized)
    _check_cancelled(cancelled)
    if options.thinning != "none":
        if progress:
            progress("Thinning prepared points")
        if options.thinning == "poisson":
            prepared = tuple(filters_module.downsample_poisson(prepared, options.spacing))
        else:
            prepared = tuple(filters_module.downsample_voxel(prepared, options.spacing, "first"))
    _check_cancelled(cancelled)
    output_count = sum(len(array) for array in prepared)
    if not 0 < output_count <= count:
        raise ValueError("Preparation returned an invalid point count.")
    return PreparedArrays(prepared, count, output_count, provenance)


def _check_cancelled(cancelled):
    if cancelled():
        raise InterruptedError("Point-cloud preparation cancelled before publication.")
