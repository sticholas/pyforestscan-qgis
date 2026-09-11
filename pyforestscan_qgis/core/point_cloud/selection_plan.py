"""Review-only scoped Product Plan materialization."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from .selection_product_request import SelectionProductRequest


def build_scoped_product_plan(
    base_plan: Mapping[str, Any],
    request: SelectionProductRequest,
) -> dict[str, Any]:
    """Create a one-product plan carrying an authoritative viewer scope."""
    if not isinstance(base_plan, Mapping):
        raise ValueError("The base Product Plan must be an object.")
    source = base_plan.get("source_dataset")
    if source and Path(str(source)) != request.source_path:
        raise ValueError("Selection source does not match the active Product Plan source.")
    products = base_plan.get("products")
    if not isinstance(products, list):
        raise ValueError("The base Product Plan has no product entries.")
    selected = None
    for entry in products:
        if isinstance(entry, Mapping) and str(entry.get("product", "")) == request.product.value:
            selected = dict(entry)
            break
    if selected is None:
        raise ValueError(f"Product {request.product.value} is not present in the active Product Plan.")
    selected["requested"] = True
    scoped = dict(base_plan)
    scoped["products"] = [selected]
    scoped["output_folder"] = str(request.output_folder)
    scoped["processing_executed"] = False
    scoped["selection_scope"] = request.to_dict()
    scoped["selection_execution"] = {
        "mode": "VIEWER_SCOPE",
        "status": "REVIEW_ONLY",
        "message": "This scoped plan is prepared for review; execution is not wired yet.",
    }
    return scoped


def write_scoped_product_plan(
    base_plan_path: Path | str,
    request: SelectionProductRequest,
    output_path: Path | str,
) -> Path:
    """Write a derived review artifact without changing the base Product Plan."""
    base_path = Path(base_plan_path)
    try:
        payload = json.loads(base_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError(f"Could not read the base Product Plan: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"The base Product Plan is not valid JSON: {exc}") from exc
    scoped = build_scoped_product_plan(payload, request)
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(scoped, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return destination
