"""Authoritative retained-interface state and lightweight read models."""
from __future__ import annotations
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from hashlib import sha256
import json
from typing import Any

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()

@dataclass(frozen=True)
class MissionControlSessionState:
    input_signature: str = ""
    current_mode: str = "folder"
    repository_path: str = ""
    repository_kind: str = ""
    repository_status: str = "not configured"
    selected_polygon_source: str = ""
    selected_polygon_feature_count: int = 0
    polygon_geometry_signature: str = ""
    polygon_area: float | None = None
    polygon_crs: str = ""
    selected_products: tuple[str, ...] = ()
    output_resolution: float | None = None
    output_folder: str = ""
    current_execution_plan: Any = None
    plan_signature: str = ""
    plan_status: str = "needs refresh"
    backend_status: str = "unknown"
    environment_status: str = "unknown"
    processing_status: str = "idle"
    generated_outputs: tuple[str, ...] = ()
    loaded_outputs: tuple[str, ...] = ()
    last_error: str = ""
    last_updated: str = field(default_factory=_now)

    def with_updates(self, **changes: Any) -> "MissionControlSessionState":
        changes.setdefault("last_updated", _now())
        return replace(self, **changes)

    def invalidate_plan(self) -> "MissionControlSessionState":
        return self.with_updates(current_execution_plan=None, plan_signature="", plan_status="needs refresh")

    def advisor_signature(self) -> str:
        payload = {"mode": self.current_mode, "repository": self.repository_path,
                   "kind": self.repository_kind, "polygon": self.polygon_geometry_signature,
                   "area": self.polygon_area, "crs": self.polygon_crs,
                   "products": self.selected_products, "resolution": self.output_resolution,
                   "output": self.output_folder, "plan": self.plan_signature,
                   "backend": self.backend_status, "outputs": self.generated_outputs}
        return sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()

def workflow_input_signature(payload: dict[str, Any]) -> str:
    """Return a deterministic identity for every workflow-defining control."""
    normalized = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return sha256(normalized.encode("utf-8")).hexdigest()

@dataclass(frozen=True)
class ScientificAdvisorSummary:
    executive_summary: str
    key_recommendations: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    recommended_products: tuple[str, ...] = ()
    parameter_recommendations: tuple[str, ...] = ()
    assumptions: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()
    source_signature: str = ""
    generated_at: str = field(default_factory=_now)
    stale: bool = False

def build_scientific_advisor_summary(state: MissionControlSessionState) -> ScientificAdvisorSummary:
    signature = state.advisor_signature()
    products = tuple(state.selected_products)
    product_text = ", ".join(products) if products else "No products are selected"
    output_text = state.output_folder or "an output folder not yet selected"
    warnings: list[str] = []
    recommendations: list[str] = []
    if not state.repository_path:
        summary = "Choose LiDAR data to begin."
    elif state.current_mode == "polygon" and not state.polygon_geometry_signature:
        summary = "Choose a polygon layer or vector file to receive area-specific guidance."
    elif state.current_mode == "polygon":
        area = f"{state.polygon_area / 10000:.3g} ha" if state.polygon_area is not None else "an area of unknown size"
        kind = state.repository_kind or "LiDAR repository"
        summary = f"A {area} polygon is selected within the {kind}. {product_text} will be written to {output_text}."
        recommendations.append("Run Prerun Check after changing the polygon or product selection.")
    else:
        kind = state.repository_kind or "LiDAR repository"
        summary = f"{kind} is available for folder processing. {product_text} will be written to {output_text}."
        recommendations.append("Run Prerun Check before processing to confirm workload and output settings.")
    if state.plan_status == "needs refresh" and state.repository_path:
        warnings.append("Prerun Check needs refresh for the current inputs.")
    if not products and state.repository_path:
        warnings.append("Select at least one scientific product.")
    if not state.output_folder and state.repository_path:
        warnings.append("Choose an output folder before processing.")
    parameters = ((f"Output resolution: {state.output_resolution:g} map units.",)
                  if state.output_resolution is not None else ())
    return ScientificAdvisorSummary(summary, tuple(recommendations), tuple(warnings), products,
                                    parameters, ("Guidance reflects the current Mission Control selections.",),
                                    ("Scientific Advisor is optional and does not block processing.",), signature)
