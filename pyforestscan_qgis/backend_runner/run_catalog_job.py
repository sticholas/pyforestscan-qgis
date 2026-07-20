"""Command-line entrypoint for PBM managed LiDAR catalog jobs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from pyforestscan_qgis.core.lidar_catalog_jobs import CatalogJobRunner, CatalogJobSpec


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run a PBM LiDAR catalog job.")
    parser.add_argument("--spec", required=True, type=Path, help="Path to a catalog job spec JSON file.")
    args = parser.parse_args(argv)
    payload = json.loads(args.spec.read_text(encoding="utf-8"))
    spec = CatalogJobSpec.from_dict(dict(payload))
    result = CatalogJobRunner(spec).run()
    print(json.dumps({"job_id": spec.job_id, "cancelled": result.cancelled, "indexed": result.indexed_count, "errors": result.error_count}))
    return 2 if result.cancelled else 0


if __name__ == "__main__":
    raise SystemExit(main())
