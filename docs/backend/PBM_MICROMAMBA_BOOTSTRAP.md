# PBM Micromamba Bootstrap

Phase 22C defines a controlled Micromamba bootstrap policy for the PyForestScan Backend Manager (PBM). The policy supports a developer-only installer prototype, but normal users still see installation as disabled.

## Source URL Strategy

PBM uses the official Micromamba API URL pattern:

```text
https://micro.mamba.pm/api/micromamba/<platform-subdir>/latest
```

Initial platform mapping:

| PBM platform | Micromamba subdir | Local archive name |
| --- | --- | --- |
| Windows | `win-64` | `micromamba-win-64.tar.bz2` |
| Linux | `linux-64` | `micromamba-linux-64.tar.bz2` |
| macOS | `osx-64` | `micromamba-osx-64.tar.bz2` |

Apple Silicon-specific policy remains to be validated before production installer enablement.

## Local Paths

Downloads are stored under the user-local PBM backend root:

```text
<backend_root>/downloads/<archive_name>
```

The extracted executable is promoted only after verification:

```text
<backend_root>/micromamba/micromamba(.exe)
```

During installation, extraction happens below:

```text
<backend_root>/staging/
```

## Checksum Strategy

Phase 22C includes SHA-256 verification helpers. Production activation must provide pinned SHA-256 values before extraction and environment creation. If no checksum is available, verification fails for required Micromamba artifacts.

This is intentional: the controlled installer mechanics exist, but production installation must not trust an unpinned bootstrap artifact.

## Failure And Retry Behavior

- Downloads use a small retry count.
- Failed downloads return a structured failure result instead of crashing Mission Control.
- Checksum mismatch fails the install.
- Any failed install step triggers rollback of staging files.
- Existing QGIS Python, QGIS folders, system Python, and user environment variables are not modified.

## Offline Placeholder

Offline install remains future work. A later phase may accept a pre-downloaded Micromamba archive, package cache, and locked environment spec, but those artifacts must still pass checksum and version verification before activation.
