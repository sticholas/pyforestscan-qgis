#!/usr/bin/env python3
"""Managed real-LAS canary for authoritative object split and merge."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
from uuid import uuid4

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
    dll = Path(sys.executable).parent/"Library/bin"
    handle = os.add_dll_directory(str(dll)) if os.name == "nt" and dll.is_dir() else None

    import numpy as np
    import pdal
    from pyforestscan_qgis.core.point_cloud.export import export_edited
    from pyforestscan_qgis.core.point_cloud.object_audit import audit_source_objects
    from pyforestscan_qgis.core.point_cloud.object_catalog import (
        build_source_object_catalog, catalog_object, object_selection_definition)
    from pyforestscan_qgis.core.point_cloud.object_id_policy import (
        ObjectIdPolicy, next_available_object_id)
    from pyforestscan_qgis.core.point_cloud.object_operations import (
        begin_object_split, restrict_selection_to_object, validate_merge_target,
        validate_split_count)
    from pyforestscan_qgis.core.point_cloud.selection import SelectionDefinition, SelectionResolver
    from pyforestscan_qgis.core.point_cloud.session import PointCloudEditSession, SourceIdentity

    source = args.output_dir/"split-merge-source.las"
    output = args.output_dir/"split-merge-edited.laz"
    points = np.zeros(8, dtype=[("X","f8"),("Y","f8"),("Z","f8"),
        ("Classification","u1"),("Tree_ID","i4")])
    points["X"] = [1,2,3,4,6,7,8,9]
    points["Y"] = points["X"]
    points["Z"] = [5,6,7,8,9,10,11,12]
    points["Classification"] = 5
    points["Tree_ID"] = [1,1,1,1,2,2,3,3]
    writer = {"type":"writers.las", "filename":str(source), "minor_version":4,
              "dataformat_id":6, "extra_dims":"Tree_ID=int32"}
    if pdal.Pipeline(json.dumps([writer]), arrays=[points]).execute() != len(points):
        raise RuntimeError("Synthetic segmented source write count differs.")

    identity = SourceIdentity.capture(source)
    before = identity.sha256
    session = PointCloudEditSession(identity, "SOURCE_LOCAL:"+identity.sha256,
        ("X","Y","Z","Classification","Tree_ID"))
    resolver = SelectionResolver(identity)
    catalog = build_source_object_catalog(identity, len(points), "Tree_ID",
        args.output_dir/"objects.sqlite")
    policy = ObjectIdPolicy(identity.sha256, "Tree_ID", "int32", -(2**31), 2**31-1, 0)

    parent_row = catalog_object(catalog["catalog_path"], 1,
        source_sha256=identity.sha256, field="Tree_ID")
    parent_definition = object_selection_definition(session, "Tree_ID", parent_row)
    parent_result = resolver.resolve((parent_definition,))
    split = begin_object_split(identity.sha256, catalog,
        {"field":"Tree_ID", **parent_row, "selection_id":parent_result.selection_id},
        parent_result)
    portion = SelectionDefinition("portion", session.session_id, identity.sha256, "LAS",
        ((.5,.5),(2.5,.5),(2.5,2.5),(.5,2.5),(.5,.5)), session.source_crs)
    restricted = restrict_selection_to_object((portion,), split, selection_id=uuid4().hex)
    split_result = resolver.resolve(restricted)
    validate_split_count(split, split_result.resolved_point_count)
    new_id = next_available_object_id(catalog["catalog_path"], policy)
    session.stage_object_id(restricted, split_result, policy, new_id,
        note="Authoritative split canary")

    source_row = catalog_object(catalog["catalog_path"], 2,
        source_sha256=identity.sha256, field="Tree_ID")
    merge_definition = object_selection_definition(session, "Tree_ID", source_row)
    merge_result = resolver.resolve((merge_definition,))
    target_row = catalog_object(catalog["catalog_path"], 3,
        source_sha256=identity.sha256, field="Tree_ID")
    target_id = validate_merge_target(catalog,
        {"field":"Tree_ID", **source_row, "selection_id":merge_result.selection_id}, target_row)
    session.stage_object_id((merge_definition,), merge_result, policy, target_id,
        note="Authoritative merge canary")

    audit = audit_source_objects(identity, session.operations, len(points), "Tree_ID",
        args.output_dir/"effective-objects.sqlite", policy.unassigned_id)
    if (audit["effective_object_count"] != 3 or audit["object_id_changed"] != 4
            or audit["largest_effective_objects"] != [[3,4],[1,2],[4,2]]):
        raise RuntimeError("Effective object audit does not match staged split/merge truth.")

    report = export_edited(session, output)
    reader = pdal.Pipeline(json.dumps([{"type":"readers.las", "filename":str(output)}]))
    reader.execute()
    actual = reader.arrays[0]["Tree_ID"].tolist()
    expected = [4,4,1,1,3,3,3,3]
    if actual != expected:
        raise RuntimeError(f"Split/merge output mismatch: {actual!r} != {expected!r}")
    if sha256(source) != before:
        raise RuntimeError("Object split/merge changed the original source.")
    if report["attribute_changes"]["object_id_changed"] != {"Tree_ID":4}:
        raise RuntimeError("Object split/merge change accounting differs.")
    evidence = {
        "status":"PASS", "source":str(source), "output":str(output),
        "source_sha256":before, "source_unchanged":True,
        "parent_object_id":1, "split_point_count":split_result.resolved_point_count,
        "allocated_object_id":new_id, "merged_source_object_id":2,
        "merged_target_object_id":target_id, "tree_ids":actual, "report":report,
        "effective_object_audit":audit,
    }
    print(json.dumps(evidence, sort_keys=True))
    if handle is not None:
        handle.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
