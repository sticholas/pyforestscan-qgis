#!/usr/bin/env python3
"""Validate Phase 27M polygon output registration and optional raster masking.

This utility is intentionally conservative. It can inspect an existing output
registry and can mask an existing raster supplied by a tester. It does not run
network EPT processing automatically.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pyforestscan_qgis.core.output_registry import registry_paths, read_output_registry
from pyforestscan_qgis.core.raster_mask import BackendRasterMaskService, RasterMaskOptions


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-folder", type=Path, help="Job or batch folder containing generated_outputs.json.")
    parser.add_argument("--print-output-registry", action="store_true", help="Print generated output registry entries.")
    parser.add_argument("--mask-existing-raster", action="store_true", help="Apply exact mask to an existing raster supplied with --raster.")
    parser.add_argument("--raster", type=Path, help="Existing raster to mask in place.")
    parser.add_argument("--polygon-wkt", help="Polygon or MultiPolygon WKT.")
    parser.add_argument("--polygon-crs", default="EPSG:4326", help="Polygon CRS authid.")
    parser.add_argument("--processing-crs", help="Processing/raster CRS authid. Defaults to --polygon-crs.")
    parser.add_argument("--all-touched", action="store_true", help="Include cells touched by polygon boundary.")
    parser.add_argument("--crop-to-extent", action="store_true", help="Crop output raster to polygon envelope.")
    parser.add_argument("--retain-unmasked-intermediate", action="store_true", help="Keep the unmasked intermediate beside the raster.")
    parser.add_argument("--mask-nodata", type=float, help="Explicit mask NoData value.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload: dict[str, object] = {
        "mode": [],
        "qgis_loading_tested": False,
        "live_ept_processing_tested": False,
    }
    if args.print_output_registry:
        if args.output_folder is None:
            print("--print-output-registry requires --output-folder.", file=sys.stderr)
            return 2
        payload["mode"].append("print-output-registry")
        payload["registries"] = [_registry_payload(path) for path in registry_paths(args.output_folder)]
    if args.mask_existing_raster:
        if args.raster is None or not args.polygon_wkt:
            print("--mask-existing-raster requires --raster and --polygon-wkt.", file=sys.stderr)
            return 2
        payload["mode"].append("mask-existing-raster")
        result = BackendRasterMaskService().mask(
            args.raster,
            args.polygon_wkt,
            polygon_crs=args.polygon_crs,
            processing_crs=args.processing_crs or args.polygon_crs,
            options=RasterMaskOptions(
                all_touched=args.all_touched,
                crop_to_polygon_extent=args.crop_to_extent,
                retain_unmasked_intermediate=args.retain_unmasked_intermediate,
                nodata=args.mask_nodata,
            ),
        )
        payload["mask_result"] = result.to_dict()
    if not payload["mode"]:
        print("Choose --print-output-registry and/or --mask-existing-raster.", file=sys.stderr)
        return 2
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


def _registry_payload(path: Path) -> dict[str, object]:
    outputs = read_output_registry(path)
    return {
        "registry": str(path),
        "output_count": len(outputs),
        "outputs": [output.to_dict() for output in outputs],
    }


if __name__ == "__main__":
    raise SystemExit(main())
