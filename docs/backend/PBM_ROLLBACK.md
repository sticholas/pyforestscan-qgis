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

Installer steps write to `staging/` first. Staged verification checks `staging/micromamba` and `staging/env` before any final backend paths are replaced. Active backend paths are promoted only after staged verification succeeds.

## Rollback Behavior

`rollback_failed_install()` removes the staging directory, including empty or partial environment prefixes created by failed Micromamba runs. This prevents an empty `staging/env` folder from poisoning a retry. It does not remove QGIS files, QGIS Python packages, system Python packages, global user site-packages, or environment variables.

During promotion, any existing active backend `micromamba/`, `env/`, and `backend.json` are preserved in `staging/promotion_backup`. If promotion or final verification fails, rollback restores that backup before removing staging. On success, staging and promotion backup are removed without restoring the previous backend.

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

The backend config is written only after staged verification and promotion pass. Final verification then checks the final config and final executable/environment paths before the backend is marked `Ready`.
