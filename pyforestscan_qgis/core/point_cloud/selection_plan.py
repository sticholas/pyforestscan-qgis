"""Review-only scoped Product Plan materialization."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from .selection_product_request import SelectionProductRequest


def _normalize_requests(
    request: SelectionProductRequest | Sequence[SelectionProductRequest],
) -> tuple[SelectionProductRequest, ...]:
    """Return one or more requests sharing the same authoritative selection."""
    requests = (request,) if isinstance(request, SelectionProductRequest) else tuple(request)
    if not requests:
        raise ValueError("At least one selected product request is required.")
    first = requests[0]
    if any(
        item.source_path != first.source_path
        or item.selection_id != first.selection_id
        or item.geometry != first.geometry
        for item in requests
    ):
        raise ValueError("Selected products must share one authoritative selection scope.")
    return requests


def build_scoped_product_plan(
    base_plan: Mapping[str, Any],
    request: SelectionProductRequest | Sequence[SelectionProductRequest],
) -> dict[str, Any]:
    """Create a bounded plan for one or more products sharing a viewer scope."""
    requests = _normalize_requests(request)
    first = requests[0]
    if not isinstance(base_plan, Mapping):
        raise ValueError("The base Product Plan must be an object.")
    source = base_plan.get("source_dataset")
    if source and Path(str(source)) != first.source_path:
        raise ValueError("Selection source does not match the active Product Plan source.")
    products = base_plan.get("products")
    if not isinstance(products, list):
        raise ValueError("The base Product Plan has no product entries.")
    entries = {
        str(entry.get("product", "")): dict(entry)
        for entry in products if isinstance(entry, Mapping)
    }
    selected = []
    for item in requests:
        entry = entries.get(item.product.value)
        if entry is None:
            raise ValueError(f"Product {item.product.value} is not present in the active Product Plan.")
        entry["requested"] = True
        selected.append(entry)
    scoped = dict(base_plan)
    scoped["products"] = selected
    scoped["output_folder"] = str(first.output_folder)
    scoped["processing_executed"] = False
    scoped["selection_scope"] = first.to_dict()
    scoped["selection_products"] = [item.to_dict() for item in requests]
    scoped["selection_execution"] = {
        "mode": "VIEWER_SCOPE",
        "status": "REVIEW_ONLY",
        "message": "This scoped plan is prepared for review; execution is not wired yet.",
    }
    return scoped


def promote_scoped_product_plan(
    base_plan: Mapping[str, Any],
    request: SelectionProductRequest | Sequence[SelectionProductRequest],
    preflight: Any,
) -> dict[str, Any]:
    """Promote a scoped plan only when its explicit preflight report is ready."""
    if not bool(getattr(preflight, "ready", False)):
        blockers = getattr(preflight, "blockers", ()) or ("Preflight did not pass.",)
        raise ValueError("Cannot promote scoped Product Plan: " + "; ".join(str(item) for item in blockers))
    scoped = build_scoped_product_plan(base_plan, request)
    scoped["selection_execution"] = {
        "mode": "VIEWER_SCOPE",
        "status": str(getattr(preflight, "execution_status", "READY_FOR_EXECUTION")),
        "source_format": str(getattr(preflight, "source_format", "")),
        "warnings": list(getattr(preflight, "warnings", ()) or ()),
    }
    return scoped

def write_scoped_product_plan(
    base_plan_path: Path | str,
    request: SelectionProductRequest | Sequence[SelectionProductRequest],
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
