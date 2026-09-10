"""Bounded, explicit source-wide classification audit through the edit journal."""
from __future__ import annotations

import json
from time import monotonic
from uuid import uuid4

from .edit_plan import EditExecutionPlan

CHUNK_SIZE = 65_536


def _add_counts(target, values, np):
    codes, counts = np.unique(values, return_counts=True)
    for code, count in zip(codes, counts):
        target[int(code)] = target.get(int(code), 0) + int(count)


def classification_findings(effective_counts, effective_points, *, removed_points=0,
                            withheld_points=0):
    """Return factual review prompts, not automatic classification decisions."""
    if type(effective_points) is not int or effective_points < 0:
        raise ValueError("Effective point count must be a non-negative integer.")
    findings = []
    if effective_points and not effective_counts.get(2, 0):
        findings.append("No effective Ground (2) points were found; DTM and HAG workflows may need ground preparation.")
    unclassified = effective_counts.get(0, 0) + effective_counts.get(1, 0)
    if effective_points and unclassified:
        fraction = unclassified / effective_points
        findings.append(f"{unclassified:,} effective points ({fraction:.1%}) are unclassified; review class-filtered processing coverage.")
    noise = effective_counts.get(7, 0) + effective_counts.get(18, 0)
    if noise:
        findings.append(f"{noise:,} effective points use Low/High Noise classes; confirm downstream filtering intent.")
    if withheld_points:
        findings.append(f"{withheld_points:,} effective points are marked Withheld.")
    if removed_points:
        findings.append(f"{removed_points:,} source points are staged for omission from a new export.")
    return tuple(findings)


def audit_classification_chunks(chunks, operations, expected_points, *,
                                cancelled=lambda: False, progress=lambda count: None):
    """Audit an iterable of source chunks using bounded copies from journal replay."""
    if type(expected_points) is not int or expected_points < 0:
        raise ValueError("Expected source point count must be a non-negative integer.")
    import numpy as np

    started = monotonic()
    operations = tuple(operations)
    plan = EditExecutionPlan(operations) if operations else None
    source_counts, effective_counts = {}, {}
    scanned = changed = removed = withheld = 0
    for original in chunks:
        if cancelled():
            raise InterruptedError("Classification audit cancelled; source and staged edits are unchanged.")
        names = original.dtype.names or ()
        if "Classification" not in names:
            raise ValueError("Source does not contain a Classification dimension.")
        if plan is None:
            edited = original.copy()
            removed_mask = np.zeros(len(original), dtype=bool)
        else:
            edited, removed_mask = plan.apply(original)
        kept = ~removed_mask
        _add_counts(source_counts, original["Classification"], np)
        _add_counts(effective_counts, edited["Classification"][kept], np)
        changed += int(((edited["Classification"] != original["Classification"]) & kept).sum())
        removed += int(removed_mask.sum())
        if "Withheld" in names:
            withheld += int((edited["Withheld"][kept] != 0).sum())
        scanned += len(original)
        progress(scanned)
    if scanned != expected_points:
        raise ValueError("Classification audit source count differs from the verified header.")
    effective_points = scanned - removed
    findings = classification_findings(effective_counts, effective_points,
                                       removed_points=removed, withheld_points=withheld)
    return {
        "audit_id": uuid4().hex,
        "status": "REVIEW" if findings else "NO_FLAGS",
        "addressing": "FULL_RESOLUTION_ORIGINAL_SOURCE_SEQUENTIAL_AUDIT",
        "bounded_memory": True,
        "chunk_size": CHUNK_SIZE,
        "source_point_count": scanned,
        "effective_point_count": effective_points,
        "source_classification_counts": dict(sorted(source_counts.items())),
        "effective_classification_counts": dict(sorted(effective_counts.items())),
        "classification_changed": changed,
        "removed_on_export": removed,
        "withheld": withheld,
        "staged_operations": len(operations),
        "findings": list(findings),
        "duration_seconds": monotonic() - started,
    }


def audit_source_classifications(source, operations, expected_points, *, pdal_module=None,
                                 cancelled=lambda: False, progress=lambda count: None):
    """Verify and stream one local LAS/LAZ/COPC source without materializing it."""
    pdal = pdal_module
    if pdal is None:
        import pdal as pdal_module
        pdal = pdal_module
    source.verify(cancelled=cancelled)
    reader = {"type": "readers.copc" if source.source_type == "COPC" else "readers.las",
              "filename": source.path}
    pipeline = pdal.Pipeline(json.dumps([reader]))
    chunks = pipeline.iterator(chunk_size=CHUNK_SIZE, prefetch=0)
    report = audit_classification_chunks(chunks, operations, expected_points,
                                         cancelled=cancelled, progress=progress)
    source.verify(cancelled=cancelled)
    return report


def classification_audit_summary(report):
    if not isinstance(report, dict) or report.get("status") not in ("NO_FLAGS", "REVIEW"):
        raise ValueError("Invalid classification audit report.")
    return (f"Classification audit: {report['status'].replace('_', ' ').title()} | "
            f"{report['source_point_count']:,} source points | "
            f"{report['classification_changed']:,} reclassified | "
            f"{report['removed_on_export']:,} removed on export")
