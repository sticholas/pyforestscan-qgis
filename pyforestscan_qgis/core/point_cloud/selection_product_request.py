"""QGIS-free product requests prepared from authoritative viewer selections."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping

from .selection_processing import SelectionProcessingScope, selection_product_options
from ..product_registry import product_definition
from ..polygon_transport import PolygonExecutionInput
from ..types import ProductType


@dataclass(frozen=True)
class SelectionProductRequest:
    """Immutable, reviewable product request for one source selection."""

    selection_id: str
    source_path: Path
    source_fingerprint: str
    product: ProductType
    scope_kind: str
    geometry: tuple[tuple[float, float], ...]
    geometry_crs: str
    bounds: tuple[float, float, float, float]
    vertical_axis: str
    z_range: tuple[float, float] | None
    hag_range: tuple[float, float] | None
    point_count: int | None
    output_folder: Path
    review_required: bool
    review_reason: str
    authority: str = "FULL_RESOLUTION_ORIGINAL_SOURCE_QUERY"

    @property
    def summary(self) -> str:
        definition = product_definition(self.product)
        scope = self.scope_kind.title()
        count = f"{self.point_count:,} source points" if self.point_count is not None else "source points"
        return f"{definition.display_name} | {scope} | {count}"

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["source_path"] = str(self.source_path)
        payload["product"] = self.product.value
        payload["geometry"] = [list(point) for point in self.geometry]
        payload["bounds"] = list(self.bounds)
        payload["z_range"] = list(self.z_range) if self.z_range is not None else None
        payload["hag_range"] = list(self.hag_range) if self.hag_range is not None else None
        payload["output_folder"] = str(self.output_folder)
        payload["original_unchanged"] = True
        return payload


def selection_scope_from_context(context: Mapping[str, Any]) -> SelectionProcessingScope:
    """Rehydrate the validated scope sent from the viewer."""
    return SelectionProcessingScope(
        selection_id=str(context.get("selection_id", "")),
        source_path=Path(str(context.get("source_path", ""))),
        source_fingerprint=str(context.get("source_fingerprint", "")),
        geometry=tuple(tuple(point) for point in context.get("geometry", ())),
        geometry_crs=str(context.get("geometry_crs", "")),
        scope_kind=str(context.get("scope_kind", "")),
        view_title=str(context.get("view_title", "")),
        point_count=context.get("point_count"),
        z_range=context.get("z_range"),
        hag_range=context.get("hag_range"),
        vertical_axis=str(context.get("vertical_axis", "Z")),
    )


def selection_scope_to_polygon_input(scope: SelectionProcessingScope) -> PolygonExecutionInput:
    """Translate a closed source-space scope into the existing polygon transport model."""
    coordinates = [list(point) for point in scope.geometry]
    wkt_coordinates = ", ".join(f"{point[0]:.15g} {point[1]:.15g}" for point in scope.geometry)
    area = abs(sum(
        scope.geometry[index][0] * scope.geometry[index + 1][1]
        - scope.geometry[index + 1][0] * scope.geometry[index][1]
        for index in range(len(scope.geometry) - 1)
    )) / 2.0
    return PolygonExecutionInput(
        source_kind="viewer_selection",
        geometry_wkt=f"POLYGON (({wkt_coordinates}))",
        geometry_geojson={"type": "Polygon", "coordinates": [coordinates]},
        source_crs_authid=scope.geometry_crs,
        processing_crs_authid=scope.geometry_crs,
        envelope=scope.bounds,
        area=area,
        feature_count=1,
        layer_name="viewer_selection",
    )

def build_selection_product_request(
    scope: SelectionProcessingScope,
    product: ProductType | str,
    *,
    output_folder: Path | str,
) -> SelectionProductRequest:
    """Build a product request without starting processing or touching source data."""
    selected = ProductType(product)
    options = {option.product: option for option in selection_product_options(scope)}
    try:
        option = options[selected]
    except KeyError as exc:
        raise ValueError(f"Product is not registered for Mission Control: {selected.value}") from exc
    return SelectionProductRequest(
        selection_id=scope.selection_id,
        source_path=scope.source_path,
        source_fingerprint=scope.source_fingerprint,
        product=selected,
        scope_kind=scope.scope_kind,
        geometry=scope.geometry,
        geometry_crs=scope.geometry_crs,
        bounds=scope.bounds,
        vertical_axis=scope.vertical_axis,
        z_range=scope.z_range,
        hag_range=scope.hag_range,
        point_count=scope.point_count,
        output_folder=Path(output_folder),
        review_required=option.status == "REVIEW",
        review_reason=option.reason,
    )
