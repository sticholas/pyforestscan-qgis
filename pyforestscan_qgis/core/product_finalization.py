"""Product output roles and terminal finalization semantics."""
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum


class OutputRole(str, Enum):
    PRIMARY = "primary"
    SECONDARY = "secondary"
    SUPPORTING = "supporting"
    INTERMEDIATE = "intermediate"
    DIAGNOSTIC = "diagnostic"


class ProductCompletion(str, Enum):
    SUCCESS = "success"
    SUCCESS_WITH_WARNING = "success_with_warning"
    FAILED = "failed"
    RECOVERABLE = "recoverable"


@dataclass(frozen=True)
class ProductOutputContract:
    product: str
    outputs: tuple[tuple[str, OutputRole], ...]


RUMPLE_OUTPUT_CONTRACT = ProductOutputContract("rumple", (
    ("rumple.tif", OutputRole.PRIMARY),
    ("rumple_summary.csv", OutputRole.SECONDARY),
    ("chm.tif", OutputRole.SUPPORTING),
))


def rumple_completion(*, raster_valid: bool, mask_valid: bool, registry_valid: bool, summary_valid: bool, autoload_valid: bool = True) -> ProductCompletion:
    if not raster_valid or not mask_valid:
        return ProductCompletion.FAILED
    if not registry_valid:
        return ProductCompletion.RECOVERABLE
    if not summary_valid or not autoload_valid:
        return ProductCompletion.SUCCESS_WITH_WARNING
    return ProductCompletion.SUCCESS


__all__ = ["OutputRole", "ProductCompletion", "ProductOutputContract", "RUMPLE_OUTPUT_CONTRACT", "rumple_completion"]
