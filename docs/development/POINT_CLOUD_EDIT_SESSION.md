# Point cloud edit session

Schema 1 stores source identity, CRS, dimensions, session UUID/timestamps,
camera, visibility, filters, review notes, export history and ordered edit
operations with an active cursor. Undo/redo persist across reopen; staging
after undo drops the redo branch. Operations and selections are immutable.

`PointCloudEditSession.save()` uses existing atomic JSON persistence.
It rejects source destinations, source aliases and non-JSON session paths.
`load()` validates schema, cursor, duplicate operation IDs, classifications,
selection source and CRS. It verifies source content by default.

Fingerprinting is chunked and cancellation-aware but synchronous at the
contract level: the future UI MUST call it in a background worker.
The internal `verify_source=False` option permits inspection only; it is not
authorization to export stale edits.

No cloud copy is made. Rendering representation, classification schema
discovery, thumbnails, managed session directory selection and autosave UI
are next-milestone integration work.
