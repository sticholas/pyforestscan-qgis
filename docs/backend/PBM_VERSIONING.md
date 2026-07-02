# PBM Versioning

`BackendVersionManager` compares plugin versions and backend manifest versions before activation.

It checks:

- plugin version is at least the manifest minimum
- plugin version is not newer than a manifest maximum, when one is declared
- installed backend version is older than the manifest and needs migration
- downgrade requests remain blocked until an explicit downgrade policy exists
- future migration boundaries are reported as warnings

Version checks are intentionally conservative. A mismatch should produce a clear compatibility message rather than attempting to run a backend built for another plugin generation.
