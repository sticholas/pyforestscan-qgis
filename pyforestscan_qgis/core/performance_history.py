"""Advisory, invalidatable processing performance history."""
from __future__ import annotations
from dataclasses import asdict,dataclass
from datetime import datetime,timezone
import hashlib,json
from pathlib import Path

@dataclass(frozen=True)
class PerformanceProfileKey:
    repository_identity:str;source_type:str;product:str;resolution:float;hag_method:str;density_band:str;backend_version:str;algorithm_version:str='adaptive-v1'
    @property
    def cache_key(self):return hashlib.sha256(json.dumps(asdict(self),sort_keys=True).encode()).hexdigest()

@dataclass(frozen=True)
class PerformanceMeasurement:
    points_per_square_metre:float;points_per_second:float;seconds_per_million_points:float;memory_per_million_points:float;raster_cells_per_second:float;stable_concurrency:int;recorded_at:str=''

class PerformanceHistoryCache:
    def __init__(self,path):self.path=Path(path)
    def get(self,key):
        data=self._read().get(key.cache_key)
        if not data or data.get('key')!=asdict(key):return None
        try:return PerformanceMeasurement(**data['measurement'])
        except (KeyError,TypeError):return None
    def put(self,key,measurement):
        data=self._read();payload=asdict(measurement)
        if not payload.get('recorded_at'):payload['recorded_at']=datetime.now(timezone.utc).isoformat()
        data[key.cache_key]={'key':asdict(key),'measurement':payload};self.path.parent.mkdir(parents=True,exist_ok=True)
        temporary=self.path.with_suffix('.tmp');temporary.write_text(json.dumps(data,indent=2,sort_keys=True),encoding='utf-8');temporary.replace(self.path)
    def invalidate_repository(self,repository_identity):
        data=self._read();kept={name:value for name,value in data.items() if value.get('key',{}).get('repository_identity')!=repository_identity}
        if kept!=data:self.path.write_text(json.dumps(kept,indent=2,sort_keys=True),encoding='utf-8')
    def _read(self):
        try:return json.loads(self.path.read_text(encoding='utf-8'))
        except (OSError,ValueError):return {}
