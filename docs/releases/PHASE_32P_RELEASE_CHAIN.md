# Phase 32P Release Chain

## Required Chain

The only accepted deployment chain is:

1. Start from a clean `develop` worktree.
2. Run `python3 scripts/package_plugin.py`.
3. Validate the versioned ZIP and `dist/pyforestscan_qgis.zip`.
4. Review `dist/package_source_verification.json`.
5. Stop QGIS and managed jobs only after active processing reaches a durable terminal state.
6. Install the exact generated ZIP with `scripts/install_qgis_plugin.py` into the default QGIS profile.
7. Review `dist/installed_package_verification.json` and require no missing, extra, or differing files.
8. Start QGIS and verify plugin load, build identity, Processing Engine readiness, and one bounded EPT canary.

## Packaging Guarantees

- Release CLI packaging rejects a dirty Git worktree unless the explicit developer-only `--allow-dirty` override is supplied.
- Every build uses a brand-new temporary staging directory.
- The ZIP is recursively compared with all included source modules, backend specifications, and the backend manifest.
- `build_info.json` records the Git commit, clean/dirty state, complete package-manifest hash, package identity, and expanded critical-module hashes.
- Reinstallation deletes the old plugin directory before extracting the ZIP, so retired modules cannot survive.

## Evidence Status

Source-to-ZIP verification is automated and release validation consumes it. ZIP-to-installed-profile comparison is also automated, but must be performed only after active QGIS/PBM work is safely terminal. A Phase 32P release is not deployment-proven until both reports pass and the live canary is recorded.

## Backend Versioning Decision

The current Processing Engine generation and runtime token remain the compatibility authority. Immutable side-by-side backend version directories are deferred because introducing a second activation model during throughput stabilization would expand the release surface. This decision must be revisited before concurrent installed-plugin versions are supported.
