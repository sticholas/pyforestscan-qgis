# Windows Native Crash Dump Analysis

Observed dumps:

- `qgis-ltr-bin.exe.24048.dmp`: QGIS `0xC0000005`, `ntdll.dll`, 10:22:01.
- `python.exe.27908.dmp`: PBM Python `0xC0000005`, `pdalcpp.dll`, 10:39:08.
- `qgis-ltr-bin.exe.2832.dmp`: QGIS `0xC0000005`, `ntdll.dll`, 10:40:58.

In WinDbg, capture `!analyze -v`, the exception-thread stack, loaded module paths, and versions for PDAL/GDAL/PROJ/GEOS/Qt/QGIS. Redact user and network paths before committing output. Compare loaded native modules against the PBM environment. Dump analysis is evidence gathering, not a prerequisite for deterministic circuit breaking.
