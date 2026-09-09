"""Managed-runtime linked query evidence; no QGIS imports or source modifications."""
import argparse
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--source",type=Path,required=True)
    parser.add_argument("--output-dir",type=Path,required=True)
    parser.add_argument("--center",nargs=2,type=float)
    parser.add_argument("--width",type=float,default=30)
    parser.add_argument("--hag",action="store_true")
    args=parser.parse_args()
    args.output_dir.mkdir(parents=True,exist_ok=False)
    dll=Path(sys.executable).parent/"Library/bin"
    handle=os.add_dll_directory(str(dll)) if os.name=="nt" and dll.is_dir() else None
    import pdal
    from pyforestscan_qgis.core.point_cloud.session import SourceIdentity
    from pyforestscan_qgis.core.point_cloud.linked_query import extract_view, EPTViewIdentity
    from pyforestscan_qgis.core.point_cloud.selection import SelectionDefinition,SelectionResolver
    from pyforestscan_qgis.core.point_cloud.runtime import ViewerRuntimeService
    started=time.monotonic()
    if args.source.name=="ept.json":
        source=EPTViewIdentity(str(args.source),hashlib.sha256(args.source.read_bytes()).hexdigest())
        kind="readers.ept"
    else:
        source=SourceIdentity.capture(args.source)
        kind="readers.copc" if source.source_type=="COPC" else "readers.las"
    metadata=next(iter(pdal.Pipeline(json.dumps([{"type":kind,"filename":str(args.source)}])).quickinfo.values()))
    srs=metadata.get("srs",{})
    crs=srs.get("compoundwkt") or srs.get("wkt") or "SOURCE_LOCAL:"+source.sha256
    bounds=metadata["bounds"]
    x,y=args.center or ((bounds["minx"]+bounds["maxx"])/2,(bounds["miny"]+bounds["maxy"])/2)
    area={"view_id":"area","view_type":"AREA_DETAIL","geometry":{
        "shape":"RECTANGLE","center":[x,y],"width":args.width,"height":args.width,"crs":crs}}
    profile={"view_id":"slice","view_type":"VERTICAL_SLICE","geometry":{
        "a":[x-args.width/2,y],"b":[x+args.width/2,y],"thickness":5,"crs":crs,
        "vertical_axis":"HeightAboveGround" if args.hag else "Z"}}
    report={"source":asdict(source),"source_points":metadata["num_points"],
            "identity_scope":"EPT_METADATA_ONLY" if source.source_type=="EPT" else "FULL_ORIGINAL_FILE",
            "checks":[],"passed":False}
    try:
        index_root=ViewerRuntimeService().root/"source-range-index"
        for view in (area,profile):
            result=extract_view(source,view,args.output_dir/view["view_id"],index_root=index_root,point_budget=200000,
                progress=lambda stage,count:print(json.dumps({"stage":stage,"count":count}),flush=True))
            report["checks"].append(result)
        source.verify()
        report["passed"]=True
    except Exception as error:
        report["error"]=str(error)
        raise
    finally:
        report["elapsed_seconds"]=time.monotonic()-started
        (args.output_dir/"query-evidence.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
        print(json.dumps(report),flush=True)
    return 0


if __name__=="__main__":
    raise SystemExit(main())
