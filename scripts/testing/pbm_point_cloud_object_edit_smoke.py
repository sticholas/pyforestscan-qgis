#!/usr/bin/env python3
"""Managed-engine object journal/export canary with a real LAS Extra Bytes field."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=False)
    dll = Path(sys.executable).parent / "Library/bin"
    handle = os.add_dll_directory(str(dll)) if os.name == "nt" and dll.is_dir() else None
    import numpy as np
    import pdal
    from pyforestscan_qgis.core.point_cloud.export import export_edited
    from pyforestscan_qgis.core.point_cloud.object_id_policy import ObjectIdPolicy
    from pyforestscan_qgis.core.point_cloud.selection import SelectionDefinition, SelectionResult
    from pyforestscan_qgis.core.point_cloud.session import PointCloudEditSession, SourceIdentity

    source = args.output_dir/"object-source.las"
    output = args.output_dir/"object-edited.laz"
    points = np.zeros(5, dtype=[("X","f8"),("Y","f8"),("Z","f8"),
        ("Classification","u1"),("Tree_ID","i4")])
    points["X"] = [1,2,8,9,10]
    points["Y"] = [1,2,8,9,10]
    points["Z"] = [2,3,8,9,10]
    points["Classification"] = 5
    points["Tree_ID"] = [1,1,2,2,2]
    writer = {"type":"writers.las", "filename":str(source), "minor_version":4,
              "dataformat_id":6, "extra_dims":"Tree_ID=int32"}
    written = pdal.Pipeline(json.dumps([writer]), arrays=[points]).execute()
    if written != len(points):
        raise RuntimeError("Synthetic object source write count differs.")
    identity = SourceIdentity.capture(source)
    before = identity.sha256
    session = PointCloudEditSession(identity, "SOURCE_LOCAL:"+identity.sha256,
        ("X","Y","Z","Classification","Tree_ID"))
    definition = SelectionDefinition("object-selection", session.session_id, identity.sha256,
        "LAS", ((0,0),(4,0),(4,4),(0,4),(0,0)), session.source_crs,
        attribute_filters=(("Tree_ID",1,1),))
    result = SelectionResult("object-selection", "RESOLVED", 2, (1,1,2,2,2,3),
        ((5,2),),2,3,None,None,(identity.path,),0.0,2)
    policy = ObjectIdPolicy(identity.sha256, "Tree_ID", "int32", -(2**31), 2**31-1, 0)
    session.stage_object_id((definition,), result, policy, 8, note="Managed export canary")
    report = export_edited(session, output)
    readback = pdal.Pipeline(json.dumps([{"type":"readers.las", "filename":str(output)}]))
    readback.execute()
    actual = readback.arrays[0]
    if actual["Tree_ID"].tolist() != [8,8,2,2,2]:
        raise RuntimeError("Exported object IDs do not match the staged journal.")
    after = sha256(source)
    if before != after or report["attribute_changes"]["object_id_changed"] != {"Tree_ID":2}:
        raise RuntimeError("Object export immutability or change accounting failed.")
    evidence = {"status":"PASS", "source":str(source), "output":str(output),
        "source_sha256":before, "original_unchanged":True, "point_count":len(actual),
        "tree_ids":actual["Tree_ID"].tolist(), "report":report}
    print(json.dumps(evidence, sort_keys=True))
    if handle is not None:
        handle.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
