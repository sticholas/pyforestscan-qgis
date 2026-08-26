# Repository Spatial Reference Profile

`RepositorySpatialReferenceProfile` samples at most 200 metadata records by default. It records the repository fingerprint, sample count, agreement, disagreement, unknown count, distribution, confidence, and conflicts.

A single known CRS with at least two agreeing authoritative records and no conflicting known records is `HIGH` confidence. Unknown members may inherit it. Any distinct known CRS values produce `CONFLICT`, even when one is the majority. Embedded metadata on an individual file always wins and may expose a repository conflict.

Explicit repository assignments are stored with canonical path, content fingerprint, CRS, source, and timestamp. Material repository changes invalidate the cached assignment. Assigning metadata does not rewrite LAS/LAZ headers.
