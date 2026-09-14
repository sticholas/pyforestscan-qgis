"""QGIS-free guided workflow model for Polygon Area Processing."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GuidedPolygonStep:
    key: str
    number: int
    label: str
    primary_action: str
    prerequisite: str = ""


GUIDED_POLYGON_STEPS: tuple[GuidedPolygonStep, ...] = (
    GuidedPolygonStep("data", 1, "Data", "Continue", "Choose LiDAR data."),
    GuidedPolygonStep("area", 2, "Area", "Use This Area", "Choose a polygon area."),
    GuidedPolygonStep("outputs", 3, "Outputs", "Continue", "Select products."),
    GuidedPolygonStep("settings", 4, "Settings", "Continue", "Choose output folder and quality settings."),
    GuidedPolygonStep("review", 5, "Review", "Validate", "Refresh the execution plan."),
    GuidedPolygonStep("results", 6, "Results", "Run", "Plan is current and ready."),
)


@dataclass(frozen=True)
class ProcessingProfile:
    key: str
    label: str
    description: str
    recommended_workers: int


PROCESSING_PROFILES: tuple[ProcessingProfile, ...] = (
    ProcessingProfile("conservative", "Conservative", "Lower concurrency for network storage and memory-sensitive jobs.", 1),
    ProcessingProfile("recommended", "Recommended", "Balanced default for internal beta testing.", 2),
    ProcessingProfile("performance", "Performance", "Higher concurrency for tested local or high-performance storage.", 4),
    ProcessingProfile("custom", "Custom", "Use detailed worker controls.", 2),
)


def guided_step_indicator(current_key: str = "data") -> str:
    """Return compact step text for Mission Control."""
    current = {step.key: step.number for step in GUIDED_POLYGON_STEPS}.get(current_key, 1)
    parts = []
    for step in GUIDED_POLYGON_STEPS:
        marker = "*" if step.number == current else ""
        parts.append(f"{marker}{step.number} {step.label}{marker}")
    return " / ".join(parts)


def profile_by_key(key: str) -> ProcessingProfile:
    """Return a processing profile, defaulting to Recommended."""
    for profile in PROCESSING_PROFILES:
        if profile.key == key:
            return profile
    return PROCESSING_PROFILES[1]


def guided_review_summary(plan) -> tuple[str, ...]:
    """Return concise review rows from a PolygonExecutionPlan-like object."""
    if plan is None:
        return ("Plan status: Needs refresh", "Run Validate to build a current polygon execution plan.")
    repository = getattr(plan, "repository", None)
    selection = getattr(plan, "source_selection", None)
    return (
        f"Plan status: Current",
        f"LiDAR data: {getattr(repository, 'repository_kind', 'unknown')}",
        f"Spatial selection: {len(getattr(selection, 'selected_sources', ())) if selection else 0} logical input(s)",
        f"Processing capacity: requested {getattr(plan, 'requested_concurrency', 1)}; effective {getattr(plan, 'effective_concurrency', 1)}",
        f"Final polygon clipping: {'on' if getattr(getattr(plan, 'polygon_batch_options', None), 'exact_raster_mask', True) else 'off'}",
    )
