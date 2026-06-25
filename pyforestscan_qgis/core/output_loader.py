"""Documented output-loading interfaces for future implementation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class OutputLoadRequest:
    """Description of an output that may be loaded into a QGIS project later."""

    path: Path
    layer_name: str
    style_path: Path | None = None


def prepare_output_for_loading(request: OutputLoadRequest) -> OutputLoadRequest:
    """Return a validated output load request.

    Phase 1 does not load layers or apply styles. Future phases will use this
    boundary to keep QGIS project mutation separate from computation.
    """
    return request

