#!/usr/bin/env python3
"""Real-data classification audit smoke using the managed Processing Engine."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    args = parser.parse_args()
    dll = Path(sys.executable).parent / "Library/bin"
    handle = os.add_dll_directory(str(dll)) if os.name == "nt" and dll.is_dir() else None
    import pdal
    from pyforestscan_qgis.core.point_cloud.classification_audit import audit_source_classifications
    from pyforestscan_qgis.core.point_cloud.session import SourceIdentity

    before = SourceIdentity.capture(args.source)
    reader = "readers.copc" if before.source_type == "COPC" else "readers.las"
    quickinfo = next(iter(pdal.Pipeline(json.dumps([
        {"type": reader, "filename": before.path}])).quickinfo.values()))
    report = audit_source_classifications(before, (), int(quickinfo["num_points"]),
                                          pdal_module=pdal)
    after = SourceIdentity.capture(args.source)
    if before != after:
        raise RuntimeError("Classification audit changed the original source identity.")
    print(json.dumps({"source": before.path, "source_sha256": before.sha256,
                      "original_unchanged": True, "report": report}, sort_keys=True))
    if handle is not None:
        handle.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
