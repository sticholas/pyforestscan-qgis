#!/usr/bin/env python3
"""Summarize durable polygon-job timing and read amplification."""
from __future__ import annotations
import argparse, json, statistics
from datetime import datetime
from pathlib import Path

def analyze(root):
    records=[];core_area=0.0;read_area=0.0
    for path in sorted(Path(root).glob("work_units/*/status.json")):
        try:data=json.loads(path.read_text(encoding="utf-8"))
        except (OSError,ValueError):continue
        records.append(data)
        unit=data.get("work_unit",{});core=unit.get("core_extent",{});read=unit.get("read_extent",{})
        core_area += _area(core);read_area += _area(read)
    runtimes=[float(item.get("runtime_seconds") or 0) for item in records if item.get("status")=="Complete" and float(item.get("runtime_seconds") or 0)>0]
    updates=[]
    for item in records:
        try:updates.append(datetime.fromisoformat(item["updated_at"]))
        except (KeyError,TypeError,ValueError):pass
    statuses={status:sum(item.get("status")==status for item in records) for status in sorted({str(item.get("status")) for item in records})}
    return {"job_folder":str(Path(root)),"records":len(records),"statuses":statuses,"completed_runtime_count":len(runtimes),
        "completed_runtime_seconds":sum(runtimes),"median_unit_seconds":statistics.median(runtimes) if runtimes else 0.0,
        "mean_unit_seconds":statistics.mean(runtimes) if runtimes else 0.0,"minimum_unit_seconds":min(runtimes) if runtimes else 0.0,
        "maximum_unit_seconds":max(runtimes) if runtimes else 0.0,"status_update_span_seconds":(max(updates)-min(updates)).total_seconds() if updates else 0.0,
        "read_amplification":read_area/core_area if core_area else 1.0}

def _area(bounds):
    return max(0.0,float(bounds.get("xmax",0))-float(bounds.get("xmin",0)))*max(0.0,float(bounds.get("ymax",0))-float(bounds.get("ymin",0)))

def main():
    parser=argparse.ArgumentParser();parser.add_argument("job_folder",type=Path);args=parser.parse_args()
    print(json.dumps(analyze(args.job_folder),indent=2,sort_keys=True));return 0

if __name__=="__main__":raise SystemExit(main())
