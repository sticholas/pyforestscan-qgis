"""Documented algorithm runner interfaces for future implementation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


@dataclass(frozen=True)
class AlgorithmRunRequest:
    """Normalized request for a future PyForestScan-backed workflow."""

    algorithm_id: str
    inputs: Mapping[str, object]
    output_directory: Path | None = None


def run_algorithm(request: AlgorithmRunRequest) -> dict[str, object]:
    """Run a future PyForestScan-backed workflow.

    Phase 1 deliberately performs no computation. Future phases will implement
    adapters from validated requests to PyForestScan public APIs.
    """
    return {
        "algorithm_id": request.algorithm_id,
        "message": "Not yet implemented.",
    }

