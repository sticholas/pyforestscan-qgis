#!/usr/bin/env python3
"""Manual helper for real Windows/QGIS EPT polygon validation.

This script intentionally does not run QGIS or PBM automatically. It records the
explicit paths and prints the checklist a tester should execute in QGIS.
"""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ept", required=True, type=Path, help="Path to ept.json, EPT root, or ept-data selected in QGIS.")
    parser.add_argument("--polygon-layer", required=True, help="Name/path of polygon layer used in QGIS.")
    parser.add_argument("--polygon-crs", required=True, help="Polygon source CRS, for example EPSG:6635.")
    parser.add_argument("--output", required=True, type=Path, help="Output folder used for the CHM run.")
    parser.add_argument("--zip", type=Path, default=Path("dist/pyforestscan_qgis.zip"), help="Plugin ZIP artifact to record.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    print("Real EPT polygon validation inputs")
    print(f"EPT selection: {args.ept}")
    print(f"Polygon layer: {args.polygon_layer}")
    print(f"Polygon CRS: {args.polygon_crs}")
    print(f"Output folder: {args.output}")
    if args.zip.exists():
        print(f"ZIP SHA256: {sha256(args.zip)}")
    else:
        print(f"ZIP SHA256: unavailable; file not found: {args.zip}")
    print("\nManual QGIS steps are documented in docs/testing/REAL_EPT_POLYGON_VALIDATION.md")
    print("Do not mark the real workflow passed unless QGIS/PBM execution completes and output is inspected.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
