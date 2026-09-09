"""Full large-source edited LAZ qualification, with independent PDAL selection."""
from __future__ import annotations
import argparse
from dataclasses import asdict
import json
import os
from pathlib import Path
import sys
import threading
from time import monotonic
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=False)
    dll = Path(sys.executable).parent / "Library/bin"
    handle = os.add_dll_directory(str(dll)) if os.name == "nt" and dll.is_dir() else None
    import pdal
    from pyforestscan_qgis.core.point_cloud.session import SourceIdentity, PointCloudEditSession
    from pyforestscan_qgis.core.point_cloud.selection import SelectionDefinition, SelectionResolver, reader_spec
    from pyforestscan_qgis.core.point_cloud.export import export_edited
    from pyforestscan_qgis.core.atomic_state import atomic_write_json
    from windows_viewer_memory import tree_memory
    started = monotonic()
    report = {"passed": False, "memory_peak": {}, "progress": []}
    stopped = threading.Event()
    def sample():
        while not stopped.wait(1):
            value = tree_memory(os.getpid()) or {}
            for key in ("private_bytes", "working_set_bytes"):
                report["memory_peak"][key] = max(report["memory_peak"].get(key, 0), value.get(key, 0))
    sampler = threading.Thread(target=sample, daemon=True)
    sampler.start()
    last = [0]
    def progress(stage, count):
        if monotonic() - last[0] < 5 and report["progress"] and stage == report["progress"][-1]["stage"]:
            return
        last[0] = monotonic()
        item = {"stage": stage, "points": count, "seconds": round(monotonic() - started, 3)}
        report["progress"].append(item)
        atomic_write_json(args.output_dir / "large_edit_acceptance.json", report)
        print(json.dumps(item), flush=True)
    try:
        progress("Fingerprinting indexed source", 0)
        source = SourceIdentity.capture(args.source)
        assert source.source_type == "COPC", "Reuse the qualified index; do not scan unindexed large LAS for selection."
        meta = next(iter(pdal.Pipeline(json.dumps([{"type": "readers.copc", "filename": source.path}])).quickinfo.values()))
        bounds = meta["bounds"]
        x = (bounds["minx"] + bounds["maxx"]) / 2
        y = (bounds["miny"] + bounds["maxy"]) / 2
        ring = ((x,y), (x+10,y), (x,y+10), (x,y))
        srs = meta.get("srs", {})
        crs = srs.get("compoundwkt") or srs.get("wkt") or "SOURCE_LOCAL:" + source.sha256
        session = PointCloudEditSession(source, crs, tuple(d.strip() for d in meta["dimensions"].split(",")))
        definition = SelectionDefinition("olaa-triangle", session.session_id, source.sha256, source.source_type, ring, crs)
        result = SelectionResolver(source).resolve([definition])
        wkt = "POLYGON ((" + ", ".join(f"{px} {py}" for px, py in ring) + "))"
        expected = pdal.Pipeline(json.dumps([reader_spec(source, [definition]), {"type": "filters.crop", "polygon": wkt}])).execute_streaming(65536)
        assert result.resolved_point_count == expected == 20405
        report["selection"] = asdict(result)
        report["independent_pdal_count"] = expected
        stage_started = monotonic()
        session.stage_resolved([definition], result, "Classification", 2)
        report["staging_seconds"] = monotonic() - stage_started
        session.undo()
        session.redo()
        saved = session.save(args.output_dir / "session.json")
        report["journal_bytes"] = saved.stat().st_size
        loaded = PointCloudEditSession.load(saved)
        report["export"] = export_edited(loaded, args.output_dir / "olaa_edited.laz", progress=progress)
        assert report["export"]["source_point_count"] == 104819538
        source.verify()
        report["source"] = asdict(source)
        report["passed"] = True
    except Exception as error:
        import traceback
        report["error"] = str(error)
        report["traceback"] = traceback.format_exc()
    finally:
        stopped.set()
        sampler.join()
        report["duration_seconds"] = monotonic() - started
        atomic_write_json(args.output_dir / "large_edit_acceptance.json", report)
    print(json.dumps({"passed": report["passed"], "error": report.get("error"), "duration": report["duration_seconds"]}), flush=True)
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
