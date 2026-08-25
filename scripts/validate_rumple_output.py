#!/usr/bin/env python3
"""Validate Rumple structure, statistics, grid alignment, and optional mask support."""
from __future__ import annotations
import argparse
import csv
import json
from pathlib import Path


def inspect_raster(path: Path) -> dict[str, object]:
    import numpy as np
    import rasterio
    with rasterio.open(path) as dataset:
        values = dataset.read(1, masked=True)
        valid = values.compressed()
        return {
            "path": str(path), "driver": dataset.driver, "bands": dataset.count,
            "dtype": dataset.dtypes[0], "crs": str(dataset.crs), "transform": tuple(dataset.transform),
            "bounds": tuple(dataset.bounds), "resolution": dataset.res, "width": dataset.width, "height": dataset.height,
            "nodata": dataset.nodata, "description": dataset.descriptions[0], "tags": dataset.tags(),
            "valid_count": int(valid.size), "nodata_count": int(values.size-valid.size),
            "minimum": float(valid.min()) if valid.size else None, "maximum": float(valid.max()) if valid.size else None,
            "mean": float(valid.mean()) if valid.size else None, "median": float(np.median(valid)) if valid.size else None,
            "percentiles": [float(x) for x in np.percentile(valid,[1,5,25,75,95,99])] if valid.size else [],
            "below_one": int(np.count_nonzero(valid < 1-1e-6)), "approximately_one": int(np.count_nonzero(np.isclose(valid,1,atol=1e-6))),
        }


def read_scalar(path: Path | None) -> float | None:
    if path is None or not path.is_file(): return None
    with path.open(encoding="utf-8", newline="") as stream:
        rows = {row[0]: row[1] for row in csv.reader(stream) if len(row)>=2}
    try: return float(rows["rumple_index"])
    except (KeyError,ValueError): return None


def main() -> int:
    parser=argparse.ArgumentParser();parser.add_argument("rumple",type=Path);parser.add_argument("--chm",type=Path);parser.add_argument("--summary",type=Path);parser.add_argument("--json",action="store_true");args=parser.parse_args()
    report={"rumple":inspect_raster(args.rumple)}
    if args.chm:
        report["chm"]=inspect_raster(args.chm)
        rb=report["rumple"]["bounds"];cb=report["chm"]["bounds"];rx=report["rumple"]["resolution"][0];ry=report["rumple"]["resolution"][1]
        report["grid_relationship"]={"half_cell_inset":[rb[0]-cb[0],rb[1]-cb[1],cb[2]-rb[2],cb[3]-rb[3]],"expected":[rx/2,ry/2,rx/2,ry/2],"shape_delta":[report["chm"]["height"]-report["rumple"]["height"],report["chm"]["width"]-report["rumple"]["width"]]}
    scalar=read_scalar(args.summary);mean=report["rumple"]["mean"]
    report["scalar_comparison"]={"scalar":scalar,"raster_aggregate":mean,"absolute_difference":None if scalar is None or mean is None else abs(scalar-mean),"relative_difference":None if scalar is None or mean in (None,0) else abs(scalar-mean)/abs(mean)}
    print(json.dumps(report,indent=2,default=str))
    return 1 if report["rumple"]["below_one"] or report["rumple"]["bands"]!=1 else 0


if __name__=="__main__": raise SystemExit(main())
