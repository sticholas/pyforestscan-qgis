#!/usr/bin/env python3
"""Non-destructive planning benchmark for source-aware processing."""
import argparse,json,time,sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pyforestscan_qgis.core.source_aware_processing import NativeSource,SourceAwareWorkPlanner,SpatialExtent
def main():
 p=argparse.ArgumentParser();p.add_argument('--mode',choices=('planning',),default='planning');p.add_argument('--kind',choices=('ept','copc','folder'),default='ept');p.add_argument('--width',type=float,default=1000);p.add_argument('--height',type=float,default=1000);p.add_argument('--resolution',type=float,default=1);a=p.parse_args();start=time.perf_counter();src=NativeSource(Path('ept.json' if a.kind=='ept' else 'source.laz'),SpatialExtent(0,0,a.width,a.height),source_type=a.kind);plan=SourceAwareWorkPlanner().plan(repository_kind=a.kind,sources=(src,),polygon_envelope=src.bounds,processing_crs='EPSG:32605',product='chm',resolution=a.resolution);print(json.dumps({'mode':a.mode,'source_type':a.kind,'work_units':len(plan.work_units),'concurrency':plan.concurrency_limit,'planning_seconds':time.perf_counter()-start,'physical_retiling':plan.physical_retiling},indent=2));return 0
if __name__=='__main__':raise SystemExit(main())
