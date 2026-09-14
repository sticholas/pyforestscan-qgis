# Repository Spatial Assignments

Mission Control writes polygon repository assignments to the shared user-local assignment store. Direct scans and catalog queries consume that assignment immediately; the historical catalog override is compatibility metadata, not a second writable source of truth.

A repository assignment is appropriate only for one coherent survey or collection. It records canonical root identity, repository fingerprint, bounded inventory signature, assignment, timestamp, and provenance. Compatible files inherit it without repeated prompts.

Adding/removing/changing repository members invalidates the exact fingerprint and requires revalidation. Mixed authoritative CRS evidence remains a conflict. Numeric bounds are useful for detecting structural incompatibility but are never used to infer metres, feet, or EPSG codes.

Mission Control offers file and repository scope. **Use Project CRS** requires explicit confirmation that source coordinates are already in the project CRS; it does not transform them. Repository units-only assignments help standalone preparation but do not make polygon selection spatially valid.
