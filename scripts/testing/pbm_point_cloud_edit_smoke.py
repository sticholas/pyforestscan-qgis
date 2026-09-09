"""Real managed-runtime edit/save/export canary; never writes its input."""
import argparse
from dataclasses import asdict, replace
import json
import os
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=False)
    dll = Path(sys.executable).parent / "Library/bin"
    handle = os.add_dll_directory(str(dll)) if os.name == "nt" and dll.is_dir() else None
    import numpy as np
    import pdal
    from pyforestscan_qgis.core.point_cloud.session import SourceIdentity, PointCloudEditSession
    from pyforestscan_qgis.core.point_cloud.selection import SelectionDefinition, SelectionResolver
    from pyforestscan_qgis.core.point_cloud.export import export_edited
    from pyforestscan_qgis.core.atomic_state import atomic_write_json

    source = SourceIdentity.capture(args.source)
    reader = pdal.Pipeline(json.dumps([{"type": "readers.las", "filename": source.path}]))
    meta = next(iter(reader.quickinfo.values()))
    if meta["num_points"] > 2_000_000:
        raise ValueError("This independent full-array reference is restricted to small QA fixtures.")
    reader.execute()
    original = reader.arrays[0]
    expected = original.copy()
    remove = np.zeros(len(original), dtype=bool)
    srs = meta.get("srs", {})
    crs = srs.get("compoundwkt") or srs.get("wkt") or "SOURCE_LOCAL:" + source.sha256
    session = PointCloudEditSession(source, crs, tuple(original.dtype.names))
    resolver = SelectionResolver(source)
    report = {"source": asdict(source), "passed": False, "operations": []}
    for index in range(20):
        x = float(original["X"].min()) + index * .2
        y = float(original["Y"].min()) + index * .1
        size = 8 - index * .1
        geometry = ((x, y), (x + size, y), (x + size, y + size), (x, y + size), (x, y))
        definition = SelectionDefinition(str(index), session.session_id, source.sha256, source.source_type, geometry, crs)
        result = resolver.resolve([definition])
        attribute, value = (("Classification", (2, 5, 7, 18)[index % 4]) if index < 16
                            else ("Withheld", 1) if index < 19 else ("DELETE_ON_EXPORT", 1))
        session.stage_resolved([definition], result, attribute, value)
        # Independent rectangle predicate: no shared geometry/replay implementation.
        mask = ((original["X"] >= x) & (original["X"] <= x + size) &
                (original["Y"] >= y) & (original["Y"] <= y + size))
        if int(mask.sum()) != result.resolved_point_count:
            raise AssertionError("Authoritative count differs from independent original-point mask.")
        if attribute == "DELETE_ON_EXPORT":
            remove[mask] = True
        else:
            expected[attribute][mask] = value
        report["operations"].append({"attribute": attribute, "value": value, "points": result.resolved_point_count})
    session.undo()
    session.undo()
    saved = session.save(args.output_dir / "editing-session.json")
    loaded = PointCloudEditSession.load(saved)
    assert loaded.can_redo
    loaded.redo()
    loaded.redo()
    loaded.save(saved)
    report["session_bytes"] = saved.stat().st_size
    report["exports"] = []
    for suffix in ("las", "laz"):
        destination = args.output_dir / ("edited." + suffix)
        result = export_edited(loaded, destination)
        assert result["source_points_modified"] == 0
        assert result["attribute_changes"]["classification_changed"] == int(((expected["Classification"] != original["Classification"]) & ~remove).sum())
        assert result["attribute_changes"]["withheld_set"] == int(((expected["Withheld"] != 0) & (original["Withheld"] == 0) & ~remove).sum())
        actual_reader = pdal.Pipeline(json.dumps([{"type": "readers.las", "filename": str(destination)}]))
        actual_reader.execute()
        actual = actual_reader.arrays[0]
        wanted = expected[~remove]
        assert len(actual) == len(wanted)
        for name in original.dtype.names:
            assert np.array_equal(actual[name], wanted[name], equal_nan=True), name
        report["exports"].append(result)
    source.verify()
    from unittest.mock import patch
    from types import SimpleNamespace
    report["failure_safety"] = []
    baseline = {item.name for item in args.output_dir.iterdir()}
    def rejected(name, call, expected_error):
        try:
            call()
        except expected_error:
            pass
        else:
            raise AssertionError(name + " was not rejected")
        assert {item.name for item in args.output_dir.iterdir()} == baseline, name
        assert len(loaded.operations) == 20
        source.verify()
        report["failure_safety"].append(name)
    rejected("source overwrite", lambda: export_edited(loaded, source.path), ValueError)
    rejected("existing destination", lambda: export_edited(loaded, args.output_dir / "edited.laz"), FileExistsError)
    rejected("missing destination folder", lambda: export_edited(loaded, args.output_dir / "absent/out.laz"), ValueError)
    rejected("cancel before export", lambda: export_edited(loaded, args.output_dir / "cancel.laz", cancelled=lambda: True), InterruptedError)
    with patch("pyforestscan_qgis.core.point_cloud.export.shutil.disk_usage", return_value=SimpleNamespace(free=0)):
        rejected("disk full", lambda: export_edited(loaded, args.output_dir / "disk-full.laz"), ValueError)
    def fail_during_write(stage, _count):
        if stage == "Writing edited cloud":
            raise OSError("Injected writer boundary failure")
    rejected("writer boundary failure", lambda: export_edited(loaded, args.output_dir / "write-failed.laz", progress=fail_during_write), OSError)
    cancellation = [False]
    def cancel_during_staging(stage, _count):
        if stage == "Staging edits on disk":
            cancellation[0] = True
    rejected("cancel after disk staging", lambda: export_edited(loaded, args.output_dir / "cancel-staged.laz",
        cancelled=lambda: cancellation[0], progress=cancel_during_staging), InterruptedError)
    report["original_unchanged"] = True
    from pyforestscan_qgis.core.backend.service import BackendService
    from pyforestscan_qgis.core.types import ChmRequest
    science = args.output_dir / "process-canary"
    science.mkdir()
    process_result = BackendService().execution_service().run_product("chm", ChmRequest(
        input_path=args.output_dir / "edited.laz", output_path=science / "edited_chm.tif",
        grid_resolution=1.0, crs=crs))
    report["process_canary"] = process_result.to_dict()
    assert process_result.success, str(process_result.errors)
    assert (science / "edited_chm.tif").is_file()
    report["passed"] = True
    atomic_write_json(args.output_dir / "editing_acceptance.json", report)
    print(json.dumps(report), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
