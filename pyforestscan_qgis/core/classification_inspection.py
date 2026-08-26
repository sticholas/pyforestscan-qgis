"""Bounded classification sampling that never loads an entire large source."""

from __future__ import annotations

import json
import math
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Callable


@dataclass(frozen=True)
class ClassificationAssessment:
    classification_present: bool
    sampled_points: int
    ground_class_2_observed: bool
    ground_fraction_estimate: float | None
    vegetation_classes_observed: tuple[int, ...]
    confidence: str
    sampling_method: str
    warnings: tuple[str, ...] = ()
    class_counts: tuple[tuple[int, int], ...] = ()
    observed_dimensions: tuple[str, ...] = ()
    strata_sampled: int = 0
    strata_with_ground: int = 0
    ground_coverage_ratio: float | None = None
    ground_coverage_confidence: str = "UNKNOWN"

    def to_dict(self) -> dict[str, object]:
        return {
            "classification_present": self.classification_present,
            "sampled_points": self.sampled_points,
            "ground_class_2_observed": self.ground_class_2_observed,
            "ground_fraction_estimate": self.ground_fraction_estimate,
            "vegetation_classes_observed": list(self.vegetation_classes_observed),
            "confidence": self.confidence,
            "sampling_method": self.sampling_method,
            "warnings": list(self.warnings),
            "class_counts": [{"classification": key, "count": value} for key, value in self.class_counts],
            "observed_dimensions": list(self.observed_dimensions),
            "strata_sampled": self.strata_sampled,
            "strata_with_ground": self.strata_with_ground,
            "ground_coverage_ratio": self.ground_coverage_ratio,
            "ground_coverage_confidence": self.ground_coverage_confidence,
        }


class ClassificationInspectionService:
    """Inspect storage-stratified point windows using backend PDAL."""

    def __init__(self, pipeline_factory: Callable[[str], object] | None = None) -> None:
        self.pipeline_factory = pipeline_factory

    def inspect(self, source: Path | str, *, point_count: int | None = None, sample_target: int = 50_000, strata: int = 5) -> ClassificationAssessment:
        path = Path(source)
        count = max(1, int(point_count or sample_target))
        window = max(1, min(sample_target // max(1, strata), count))
        starts = _sample_starts(count, window, strata) if point_count else (0,)
        classes: Counter[int] = Counter()
        sampled = 0
        dimension_seen = False
        observed_dimensions: list[str] = []
        strata_sampled = 0
        strata_with_ground = 0
        factory = self.pipeline_factory or _default_pipeline_factory
        for start in starts:
            stratum_ground = 0
            reader_type = _reader_type(path)
            reader = {"type": reader_type, "filename": str(path)}
            stages = [reader]
            if reader_type == "readers.las":
                reader.update(start=int(start), count=int(window))
            else:
                stages.append({"type": "filters.head", "count": int(window)})
            pipeline = factory(json.dumps({"pipeline": stages}))
            pipeline.execute()
            for array in tuple(getattr(pipeline, "arrays", ()) or ()):
                names = tuple(getattr(getattr(array, "dtype", None), "names", ()) or ())
                observed_dimensions.extend(name for name in names if name not in observed_dimensions)
                if "Classification" not in names:
                    sampled += len(array)
                    continue
                dimension_seen = True
                values = array["Classification"]
                sampled += len(values)
                classes.update(int(value) for value in values)
                stratum_ground += sum(1 for value in values if int(value) == 2)
            strata_sampled += 1
            if stratum_ground:
                strata_with_ground += 1
        ground = classes.get(2, 0)
        warnings: list[str] = []
        if not dimension_seen:
            warnings.append("Classification dimension was not observed in sampled execution arrays.")
        elif not ground:
            warnings.append("Ground class 2 was not observed in the bounded sample; absence is not proof for unsampled points.")
        coverage = strata_with_ground / strata_sampled if strata_sampled else None
        if ground and strata_sampled >= 3 and coverage is not None and coverage < 0.5:
            warnings.append("Ground returns occurred in fewer than half of sampled storage strata; review spatial support before Delaunay HAG.")
        return ClassificationAssessment(
            dimension_seen,
            sampled,
            ground > 0,
            (ground / sampled) if sampled else None,
            tuple(code for code in (3, 4, 5) if classes.get(code, 0)),
            "HIGH" if sampled >= min(count, sample_target) else "MEDIUM",
            "storage-stratified bounded PDAL sample",
            tuple(warnings),
            tuple(sorted(classes.items())),
            tuple(observed_dimensions),
            strata_sampled,
            strata_with_ground,
            coverage,
            "HIGH" if strata_sampled >= 5 else ("MEDIUM" if strata_sampled >= 3 else "LOW"),
        )


def assessment_from_array(array: object) -> ClassificationAssessment:
    names = tuple(getattr(getattr(array, "dtype", None), "names", ()) or ())
    if "Classification" not in names:
        return ClassificationAssessment(False, len(array), False, None, (), "HIGH", "execution array", ("Classification dimension is missing.",), observed_dimensions=names)
    counts = Counter(int(value) for value in array["Classification"])
    total = len(array)
    has_ground = counts.get(2, 0) > 0
    return ClassificationAssessment(True, total, has_ground, counts.get(2, 0) / total if total else None, tuple(code for code in (3, 4, 5) if counts.get(code, 0)), "HIGH", "complete execution array", class_counts=tuple(sorted(counts.items())), observed_dimensions=names, strata_sampled=1, strata_with_ground=1 if has_ground else 0, ground_coverage_ratio=1.0 if has_ground else 0.0, ground_coverage_confidence="HIGH")


def _sample_starts(point_count: int, window: int, strata: int) -> tuple[int, ...]:
    if point_count <= window:
        return (0,)
    maximum = max(0, point_count - window)
    return tuple(dict.fromkeys(int(round(maximum * index / max(1, strata - 1))) for index in range(max(1, strata))))


def _reader_type(path: Path) -> str:
    lowered = str(path).lower()
    if lowered.endswith("ept.json"):
        return "readers.ept"
    if lowered.endswith((".copc.laz", ".copc")):
        return "readers.copc"
    return "readers.las"


def _default_pipeline_factory(spec: str) -> object:
    import pdal
    return pdal.Pipeline(spec)
