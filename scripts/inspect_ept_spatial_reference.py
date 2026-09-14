#!/usr/bin/env python3
"""Inspect EPT spatial-reference metadata without reading point data."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from pyforestscan_qgis.core.ept_spatial_reference import ept_spatial_metadata_summary, resolve_ept_spatial_reference


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect EPT CRS metadata from an ept.json file.")
    parser.add_argument("ept_json", type=Path)
    args = parser.parse_args()
    payload = json.loads(args.ept_json.read_text(encoding="utf-8"))
    resolved = resolve_ept_spatial_reference(payload)
    print(json.dumps(ept_spatial_metadata_summary(str(args.ept_json), payload, resolved), indent=2, sort_keys=True))
    return 0 if resolved.valid else 2


if __name__ == "__main__":
    raise SystemExit(main())
