# PBM Rollback

Phase 22C uses staging to keep backend installation rollback-safe.

## Staging Layout

```text
<backend_root>/
  downloads/
  staging/
    micromamba/
    env/
  env/
  logs/
```

Installer steps write to `staging/` first. Active backend paths are promoted only after verification succeeds.

## Rollback Behavior

`rollback_failed_install()` removes the staging directory, including empty or partial environment prefixes created by failed Micromamba runs. This prevents an empty `staging/env` folder from poisoning a retry. It does not remove QGIS files, QGIS Python packages, system Python packages, global user site-packages, or environment variables.

Rollback runs when:

- download fails,
- checksum verification fails,
- extraction fails,
- environment creation fails,
- staged backend verification fails,
- promotion or config writing fails.

If an install fails after user-local files were written, the backend reports `Failed` or `Repair Required` and keeps logs for diagnosis.

## Promotion

A successful future install promotes staged Micromamba and environment files into:

```text
<backend_root>/micromamba/
<backend_root>/env/
```

The backend config is written only after verification passes.
