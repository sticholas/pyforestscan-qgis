# PBM Download Manager

The Phase 22D download manager provides a production-oriented artifact download layer for backend installation.

Capabilities:

- provider abstraction for future mirrors
- resumable partial downloads
- progress callbacks
- retry handling
- timeout handling
- cancellation token support
- cache reuse when checksums match
- temporary `.part` downloads
- partial cleanup on failure or cancellation
- streaming in bounded chunks
- checksum verification before artifact activation

The download manager is QGIS-free and testable without network access. Tests use mocked openers and never fetch real artifacts.

Public backend installation still requires signed release metadata and pinned checksums before users can rely on this manager for real downloads.
