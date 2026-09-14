"""Inspect PBM native-library resolution without importing QGIS."""
from __future__ import annotations
import json,os,platform,sys
from pathlib import Path
from .process_env import native_environment_diagnostics

LIBRARY_PATTERNS={"pdalcpp":("pdalcpp.dll","libpdal_base.so","libpdalcpp.dylib"),"gdal":("gdal*.dll","libgdal.so*","libgdal*.dylib"),"proj":("proj*.dll","libproj.so*","libproj*.dylib"),"geos":("geos*.dll","libgeos.so*","libgeos*.dylib"),"sqlite":("sqlite*.dll","libsqlite3.so*","libsqlite3*.dylib")}

def inspect_native_runtime(environment_path=None):
    env_root=Path(environment_path or sys.prefix);search=(env_root/'Library'/'bin',env_root/'Scripts',env_root/'bin',env_root)
    imports={};versions={}
    for name in ('pdal','osgeo.gdal','rasterio'):
        try:
            module=__import__(name,fromlist=['*']);imports[name]={"ok":True,"module":str(getattr(module,'__file__',''))};versions[name]=str(getattr(module,'__version__',getattr(module,'VersionInfo',lambda:'unknown')()))
        except Exception as exc:imports[name]={"ok":False,"error":f"{type(exc).__name__}: {exc}"}
    candidates={name:sorted({str(path) for folder in search if folder.exists() for pattern in patterns for path in folder.glob(pattern)}) for name,patterns in LIBRARY_PATTERNS.items()}
    qgis=[path for values in candidates.values() for path in values if 'qgis' in path.lower() or 'osgeo4w' in path.lower()]
    return {"python_executable":sys.executable,"python_version":sys.version,"platform":platform.platform(),"environment_root":str(env_root),"environment":native_environment_diagnostics(os.environ),"imports":imports,"versions":versions,"dll_candidates":candidates,"qgis_dll_candidates":qgis,"release_blocker":bool(qgis)}

def print_native_runtime(environment_path=None):
    payload=inspect_native_runtime(environment_path);print(json.dumps(payload,indent=2,sort_keys=True));return 2 if payload['release_blocker'] else 0
