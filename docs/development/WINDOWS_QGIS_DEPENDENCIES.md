# Windows QGIS Dependencies

This guide documents the safest known dependency path for PyForestScan QGIS on
Windows with QGIS 3.44.x installed through the standalone OSGeo4W-based QGIS
installer.

It is based on a read-only investigation of this machine on the `develop`
branch. It does not install packages and does not modify the QGIS Python
environment.

## Observed Environment

The live QGIS Environment Check reported:

- QGIS version: `3.44.9-Solothurn`
- Python version: `3.12.13`
- GDAL version: `3.12.3`
- PDAL command-line version: `2.10.0`
- rasterio version: `1.5.0` in the live report
- numpy version: `2.4.3`
- `pyforestscan` import: missing
- `pdal` Python import: missing

A later verification showed the plugin was being run from QGIS 3.44.10, not
3.44.9. That mismatch is important: command-line installation and verification
must always use the same QGIS root shown by the plugin Environment Check.

Local read-only command probing found the matching QGIS 3.44.9 install at:

```text
C:\Program Files\QGIS 3.44.9
```

The initialized QGIS Python executable is:

```text
C:\Program Files\QGIS 3.44.9\bin\python3.exe
```

`pip` is available inside that environment:

```text
C:\Program Files\QGIS 3.44.9\apps\Python312\Scripts\pip.exe
```

The QGIS 3.44.9 OSGeo4W package database showed installed OSGeo4W packages for
`pdal`, `pdal-libs`, `python3-numpy`, `python3-geopandas`, `python3-pyproj`,
`python3-shapely`, `python3-pandas`, `python3-matplotlib`, `python3-scipy`, and
`python3-requests`. The Python `pdal` module was not installed.

A local import probe of QGIS 3.44.9 found `rasterio 1.4.3`, while the live QGIS
report supplied for this task reported `rasterio 1.5.0`. This discrepancy means
users must always verify the exact QGIS executable/profile they are launching,
especially when multiple QGIS versions are installed side by side.

## Matching the Plugin's QGIS Install

Command-line verification must use the same QGIS install path reported by the
plugin `Environment Check` algorithm. This matters when multiple QGIS versions
are installed side by side. Installing `python3-pdal` into QGIS 3.44.9 does not
make it available to QGIS 3.44.10, and the reverse is also true.

In the observed mismatch, manual commands were first run against:

```text
C:\Program Files\QGIS 3.44.9
```

But the plugin was later found to run from:

```text
C:\Program Files\QGIS 3.44.10
```

For command-line checks, copy the exact QGIS root from the Environment Check
report and initialize that root's OSGeo4W environment. For QGIS 3.44.10 this is:

```cmd
call "C:\Program Files\QGIS 3.44.10\OSGeo4W.bat"
where python3
python3 -c "import sys; print(sys.executable); print('\n'.join(sys.path))"
python3 -c "import pdal; print(pdal.__file__); print(getattr(pdal, '__version__', 'UNKNOWN'))"
```

If those commands are run through WSL or another shell that struggles with spaces
in Windows paths, first inspect short names with:

```cmd
dir /x "C:\Program Files"
```

Then use the matching short path for the same QGIS version, for example:

```cmd
call C:\PROGRA~1\QGIS34~1.10\OSGeo4W.bat
```

Do not assume that `QGIS34~1.9` and `QGIS34~1.10` are interchangeable. They are
different install roots with different Python `site-packages` directories and
different OSGeo4W package databases.

## Python Environment Boundaries

Windows development may involve several Python environments at once:

- System Python: a normal Windows Python from python.org, Microsoft Store, or an
  application installer. Packages installed here are not automatically visible to
  QGIS.
- WSL Python: Linux Python inside WSL. Packages installed here are not visible to
  Windows QGIS.
- QGIS Python: the Python interpreter launched by QGIS after OSGeo4W environment
  variables are initialized.
- OSGeo4W/QGIS Python: the QGIS Python environment plus OSGeo4W package-managed
  geospatial libraries, DLL paths, and Python packages.

PyForestScan QGIS must use the QGIS Python environment. Installing into system
Python or WSL Python will not fix imports inside QGIS.

## Inspect the Active QGIS Python

Open `cmd.exe`, not WSL, and run:

```cmd
call "C:\Program Files\QGIS 3.44.9\OSGeo4W.bat"
where python3
where pip
where pdal
python3 -c "import sys, platform; print(sys.executable); print(sys.version); print(platform.platform())"
python3 -m pip --version
pdal --version
```

If quoting paths through WSL, use the short path discovered with `dir /x`:

```cmd
call C:\PROGRA~1\QGIS34~1.9\OSGeo4W.bat
```

To check imports without installing anything:

```cmd
python3 -c "import importlib.util; mods=['pyforestscan','pdal','osgeo.gdal','rasterio','numpy']; [print(m, 'FOUND' if importlib.util.find_spec(m) else 'MISSING') for m in mods]"
```

To print versions for packages that import:

```cmd
python3 -c "import numpy, rasterio; from osgeo import gdal; print(gdal.VersionInfo('--version')); print(rasterio.__version__); print(numpy.__version__)"
```

## OSGeo4W Package Availability

The current OSGeo4W package index includes `python3-pdal`:

```text
@ python3-pdal
requires: python3-core python3-numpy pdal
version: 3.5.3-1
```

It also includes `python3-rasterio 1.5.0-2`. The installed QGIS 3.44.9 database
on this machine did not list `python3-pdal`, which explains why `pdal.exe` works
but `import pdal` fails.

## Recommended Installation Route

Recommended order:

1. Use OSGeo4W/QGIS package management for compiled geospatial and scientific
   dependencies whenever available.
2. Install `python3-pdal` through the QGIS/OSGeo4W setup tool for the same QGIS
   root that launches the plugin.
3. Verify `import pdal` from QGIS Python.
4. Install PyForestScan into QGIS Python only after the OSGeo4W-managed compiled
   dependencies are present.
5. Prefer avoiding dependency upgrades from pip that would replace OSGeo4W GDAL,
   numpy, rasterio, pyproj, shapely, pandas, scipy, or PDAL components.

The safest PyForestScan pip pattern, after OSGeo4W dependencies are installed and
verified, is:

```cmd
call "C:\Program Files\QGIS 3.44.9\OSGeo4W.bat"
python3 -m pip install --no-deps pyforestscan
```

`--no-deps` is intentional. PyForestScan currently declares dependencies such as
`pdal`, `rasterio`, `geopandas`, `pyproj`, `shapely`, `pandas`, `numpy`,
`matplotlib`, and `scipy`. Many of these are compiled packages that QGIS already
gets from OSGeo4W. Letting pip resolve them may upgrade or replace packages in a
way that no longer matches the QGIS GDAL/PROJ/PDAL runtime.

After installing, verify from the same initialized QGIS shell:

```cmd
python3 -c "import pyforestscan, pdal; print('pyforestscan ok'); print('pdal ok')"
```

Then run the plugin `Environment Check` algorithm inside QGIS.

## Installing python3-pdal with OSGeo4W

Preferred manual route:

1. Close QGIS.
2. Run the OSGeo4W/QGIS setup tool for the same install root, for example:
   `C:\Program Files\QGIS 3.44.9\bin\osgeo4w-setup.exe`.
3. Choose the advanced package selection workflow.
4. Search for `python3-pdal`.
5. Select `python3-pdal` for installation.
6. Complete the setup process.
7. Reopen an OSGeo4W shell for QGIS 3.44.9 and verify:

```cmd
call "C:\Program Files\QGIS 3.44.9\OSGeo4W.bat"
python3 -c "import pdal; print(pdal.__version__)"
```

Do not install `pdal` from pip as the first attempt on Windows QGIS. The pip
package is a Python binding that must match native PDAL libraries. OSGeo4W
already provides the native PDAL runtime used by QGIS.

## Fallback Options

If OSGeo4W cannot install `python3-pdal` into the standalone QGIS directory:

- Prefer installing a fresh QGIS/OSGeo4W environment where `python3-pdal` is
  selectable from the setup tool.
- Consider a separate conda/mamba environment for command-line PyForestScan
  experiments, but do not assume QGIS can use that environment.
- Use pip only for pure-Python or project-level packages after confirming that
  compiled dependencies are already satisfied by OSGeo4W.
- Avoid mixing conda DLLs, system Python wheels, and QGIS OSGeo4W DLLs in the
  same QGIS process.

## Troubleshooting

### pyforestscan missing

Symptom:

```text
[FAIL] pyforestscan: Could not import pyforestscan
```

Check that pip points to QGIS Python:

```cmd
call "C:\Program Files\QGIS 3.44.9\OSGeo4W.bat"
python3 -m pip --version
python3 -c "import sys; print(sys.executable)"
```

If compiled dependencies are already present, install PyForestScan into QGIS
Python with:

```cmd
python3 -m pip install --no-deps pyforestscan
```

### QGIS install mismatch

Symptom:

```text
python3-pdal is installed in one QGIS root, but the plugin still reports pdal missing.
```

Check the QGIS install path from the plugin Environment Check report. Then run
all command-line verification from that same root:

```cmd
call "C:\Program Files\QGIS 3.44.10\OSGeo4W.bat"
where python3
python3 -c "import sys; print(sys.executable); print('\n'.join(sys.path))"
python3 -c "import pdal; print(pdal.__file__); print(getattr(pdal, '__version__', 'UNKNOWN'))"
```

Confirm that `sys.executable`, `sys.path`, and `pdal.__file__` all point under
the same QGIS root. Also check the OSGeo4W package database for that root:

```cmd
findstr /I python3-pdal "C:\Program Files\QGIS 3.44.10\etc\setup\installed.db"
```

If `python3-pdal` appears under QGIS 3.44.9 but the plugin runs under QGIS
3.44.10, install `python3-pdal` into QGIS 3.44.10 as well. After QGIS or OSGeo4W
updates, rerun the plugin Environment Check because GDAL, numpy, rasterio, and
PDAL package versions may change.

### pdal Python bindings missing

Symptom:

```text
pdal.exe works, but import pdal fails
```

This means the PDAL command-line/runtime package is installed, but the Python
binding package is not. Install `python3-pdal` through OSGeo4W setup for the same
QGIS install root.

### GDAL version conflicts

Symptoms may include import errors, DLL load failures, rasterio errors, or QGIS
crashes after pip upgrades.

Avoid:

```cmd
python3 -m pip install --upgrade gdal rasterio numpy pyproj shapely
```

Those packages are tightly coupled to QGIS/OSGeo4W native libraries. Restore the
QGIS environment with OSGeo4W setup or reinstall QGIS if pip has replaced core
compiled packages.

### pip installed into the wrong Python

Always run pip as a module of the target interpreter:

```cmd
python3 -m pip --version
python3 -m pip install --no-deps pyforestscan
```

Do not rely on bare `pip` from PowerShell, WSL, Git Bash, or system Python.

### QGIS sees packages but system Python does not

This is expected. QGIS Python and system Python are separate environments. Test
plugin dependencies from QGIS or from a shell initialized with `OSGeo4W.bat`.

### System Python sees packages but QGIS does not

This is also expected. Re-run the install command from the initialized QGIS
Python environment, not from system Python or WSL.

## Investigation Commands Used

The following read-only commands were useful on this machine:

```cmd
cmd.exe /c dir /x "C:\Program Files"
cmd.exe /c "call C:/PROGRA~1/QGIS34~1.9/OSGeo4W.bat && python3 -m pip --version"
cmd.exe /c "call C:/PROGRA~1/QGIS34~1.9/OSGeo4W.bat && where python3 && where pip && where pdal && pdal --version"
```

The OSGeo4W package index was inspected from:

```text
https://download.osgeo.org/osgeo4w/v2/x86_64/setup.ini
```

PyForestScan and PDAL Python package metadata were inspected from PyPI without
installing packages:

```text
https://pypi.org/pypi/pyforestscan/json
https://pypi.org/pypi/pdal/json
```
