# PBM Installer Safety

Phase 22C introduces controlled installer mechanics behind a hard developer-only guard.

## Developer Guard

Real installer actions may run only when this environment variable is set:

```text
PYFORESTSCAN_QGIS_ENABLE_BACKEND_INSTALL=1
```

If the flag is absent:

- Mission Control shows preview and compatibility information only.
- Install Backend remains disabled and labeled planned.
- `BackendService.install_backend()` refuses to run and reports a clear message.
- No directories are created and no downloads occur.

If the flag is present, Mission Control labels the button `Install Backend Experimental` and warns that it is for development testing only.

## Safety Boundaries

The installer must:

- Use only the user-local PBM backend root.
- Avoid administrator privileges.
- Avoid QGIS Python, QGIS install folders, system Python, and global user site-packages.
- Avoid global environment-variable changes.
- Keep existing Guided Mission Control, Advanced Toolbox, and Batch behavior unchanged.
- Keep External Worker mode disabled.

## Developer Prototype Scope

The Phase 22C prototype includes download, checksum, extraction, environment creation, verification, config writing, staging, and rollback mechanics. Exact production checksums, final version locks, and broad user enablement remain future work.
