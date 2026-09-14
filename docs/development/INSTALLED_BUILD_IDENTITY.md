# Installed Build Identity

Packaged PyForestScan ZIPs contain `pyforestscan_qgis/build_info.json`. It records the plugin version, Git commit, package build ID, package-content identity, build timestamp, Processing Engine plugin-build hash, and SHA-256 hashes for critical launch modules. Installed QGIS runtime code reads this file directly and never depends on `.git` metadata.

At plugin load, PyForestScan writes `plugin_session_identity.json` below the user-local backend diagnostics directory. The trace records QGIS and Python versions, profile path, process ID, plugin root, loaded module paths, critical hashes, and immutable session build identity.

## Installation States

- `PLUGIN_VALID`: every critical file matches `build_info.json`.
- `PLUGIN_MIXED_INSTALL`: one or more critical files differ or are missing. Reinstall the plugin ZIP; do not repair the Processing Engine.
- `PLUGIN_CORRUPT`: build metadata cannot be read.
- `PLUGIN_UNKNOWN`: a development/source copy has no packaged metadata.

Processing checks compare files on disk with the identity captured at session start. If files change while QGIS remains open, processing stops with a restart instruction. Production code does not mutate `sys.modules` to compensate for an unsafe live overlay.

The package build ID identifies the complete shipped plugin content contract. `processing_engine_plugin_build_id` remains the narrower Phase 32D launch-surface hash verified by the managed engine. Diagnostics show both identities rather than treating plugin corruption as engine corruption.
