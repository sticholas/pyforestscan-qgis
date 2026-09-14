# PBM Backend Manifest

`backend_manifest.json` is the single source of truth for the managed backend release.

The manifest declares:

- schema version
- backend version
- environment version
- Micromamba version policy
- Python version policy
- package list and version specifications
- package channels
- artifact hashes
- supported plugin versions
- minimum and maximum plugin versions
- future migration version

PBM should not infer production package versions from scattered code, docs, or UI strings. Planning and environment previews read from the manifest first and only fall back to the dependency registry defensively if the manifest is unavailable.

The Phase 22D manifest intentionally leaves platform Micromamba SHA-256 values empty. That keeps public installation disabled until release-owned hashes are pinned and tested.
