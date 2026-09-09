"""Isolated read-only linked-view worker. Never creates an editor journal."""
from __future__ import annotations
import argparse
from contextlib import ExitStack
import json
import os
from pathlib import Path
import queue
import sys
import threading
import time
from uuid import uuid4

sys.path.insert(0,str(Path(__file__).resolve().parents[2]))


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--folder",type=Path,required=True)
    args=parser.parse_args()
    dll=Path(sys.executable).parent/"Library/bin"
    dll_handle=os.add_dll_directory(str(dll)) if os.name=="nt" and dll.is_dir() else None
    from pyforestscan_qgis.core.point_cloud.session import SourceIdentity
    from pyforestscan_qgis.core.point_cloud.linked_query import extract_view
    from pyforestscan_qgis.core.point_cloud.runtime import ViewerRuntimeService
    from pyforestscan_qgis.core.atomic_state import atomic_write_json
    commands=queue.Queue(maxsize=4)
    cancelled=threading.Event()
    closed=threading.Event()
    generation=[0]
    def emit(value):
        print(json.dumps(value,allow_nan=False),flush=True)
    def listen():
        for line in iter(lambda:sys.stdin.readline(2*1024*1024+1),""):
            try:
                if len(line)>2*1024*1024:
                    raise ValueError("Excessive query request.")
                value=json.loads(line)
                if value.get("action") in ("cancel","close"):
                    generation[0]+=1
                    cancelled.set()
                    if value["action"]=="close":
                        closed.set()
                    continue
                value["_generation"]=generation[0]
                commands.put_nowait(value)
            except (ValueError,queue.Full):
                emit({"error":"Invalid or excessive linked query requests."})
        closed.set()
        cancelled.set()
    threading.Thread(target=listen,daemon=True).start()
    identity=None
    stamp=None
    cached_paths = {}
    verified_view_cache = {}
    last_progress=[0]
    def progress(stage,count):
        if time.monotonic()-last_progress[0]>.2:
            emit({"progress":stage,"count":count})
            last_progress[0]=time.monotonic()
    while not closed.is_set():
        try:
            command=commands.get(timeout=.1)
        except queue.Empty:
            continue
        request=command.get("request_id")
        try:
            if command.pop("_generation")!=generation[0]:
                raise InterruptedError("Superseded linked view query.")
            cancelled.clear()
            descriptor = command["source_identity"]
            if descriptor.get("source_type") == "EPT":
                from pyforestscan_qgis.core.point_cloud.linked_query import EPTViewIdentity
                source = EPTViewIdentity(**descriptor)
            else:
                source=SourceIdentity(**descriptor)
            stat=Path(source.path).stat()
            current=(stat.st_size,stat.st_mtime_ns,stat.st_ctime_ns)
            if source!=identity or current!=stamp:
                progress("Verifying original source",0)
                source.verify(cancelled=cancelled.is_set)
                identity,stamp=source,current
            cached = command.get("cached") or {}
            cached_path = Path(cached.get("path",""))
            if (cached.get("source_fingerprint") == source.sha256 and
                    cached.get("geometry") == command["view"]["geometry"] and
                    cached.get("view_type") == command["view"]["view_type"] and
                    cached_path.is_file() and cached_path.resolve().is_relative_to(args.folder.resolve())):
                result = dict(cached, view_id=command["view"]["view_id"])
            else:
                with ExitStack() as leases:
                    display_path = None
                    key = command.get("view_cache_key")
                    if key and source.source_type in ("LAS","LAZ"):
                        from pyforestscan_qgis.core.point_cloud.view_cache import ViewCache
                        cache = ViewCache(ViewerRuntimeService().root/"source-cache")
                        entry = cache._owned(cache.root/key)
                        record_path = entry/"cache.json"
                        if record_path.is_file() and not record_path.is_symlink() and record_path.stat().st_size <= 128*1024:
                            record = json.loads(record_path.read_text(encoding="utf-8"))
                            cache_identity = record.get("identity",{})
                            if cache_identity.get("source_sha256") == source.sha256 and cache.entry(cache_identity)==entry:
                                output = entry/"view.copc.laz"
                                cache_stamp = (output.stat().st_size,output.stat().st_mtime_ns,output.stat().st_ctime_ns)
                                if verified_view_cache.get(key) == cache_stamp:
                                    display_path = output
                                else:
                                    display_path = cache.reusable(cache_identity,lambda _path,identity:
                                        identity.get("source_sha256")==source.sha256)
                                    if display_path:
                                        verified_view_cache[key] = cache_stamp
                                if display_path:
                                    leases.enter_context(cache.lease(key))
                    result=extract_view(source,command["view"],args.folder/uuid4().hex,
                        index_root=ViewerRuntimeService().root/"source-range-index",
                        point_budget=command["point_budget"],cancelled=cancelled.is_set,progress=progress,
                        display_path=display_path)
            stat=Path(source.path).stat()
            if (stat.st_size,stat.st_mtime_ns,stat.st_ctime_ns)!=stamp:
                raise ValueError("Original source changed during linked query.")
            if cancelled.is_set() or closed.is_set():
                raise InterruptedError("Superseded linked view query.")
            atomic_write_json(Path(result["path"]).with_name("query.json"),result)
            cached_paths[result["path"]] = time.monotonic()
            # Only this worker's generated display files are eligible for eviction.
            # Keep the most recent views, including the previous active renderer.
            while len(cached_paths) > 32:
                oldest = min(cached_paths, key=cached_paths.get)
                candidate = Path(oldest)
                if candidate.resolve().is_relative_to(args.folder.resolve()):
                    try:
                        candidate.unlink(missing_ok=True)
                        candidate.with_name("query.json").unlink(missing_ok=True)
                        candidate.parent.rmdir()
                    except OSError:
                        pass
                del cached_paths[oldest]
            emit({"linked_ready":result,"request_id":request})
        except Exception as error:
            emit({"error":str(error),"request_id":request})
    return 0


if __name__=="__main__":
    raise SystemExit(main())
