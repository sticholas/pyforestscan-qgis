# Phase 32R Release Blocker Audit

## Blocking Categories

Release is blocked by a reproducible plugin crash, incorrect science, lost or
corrupted output, source/ZIP/installed identity mismatch, broken Processing
Engine setup, broken primary UI action, unsafe cancellation, or a claimed core
product that cannot complete its release smoke.

## Current Blockers Before RC1

1. Complete the final clean-package core QA matrix for Folder and Polygon modes,
   supported products, cancel, pause/resume, results/autoload, history, and setup.
2. Record a final packaged medium/large Polygon smoke with progress, checkpoint,
   exact finalization, and no orphaned worker process.
3. Pin and verify a tested Micromamba artifact digest before public distribution.
4. Resolve or explicitly downgrade any product that fails final-package smoke.

## Non-Blocking / Deferred

- A point-cloud viewer/editor.
- AI or heuristic candidate classifications.
- N=5 network concurrency proof; the release baseline remains 2.
- Automatic LAS/LAZ-to-COPC conversion.
- Richer history/re-run controls and additional convenience surfaces.
- Visual polish beyond core readability once width/height and action QA pass.

No RC1 recommendation should be made until the blocking clean-package QA evidence
is complete. `0.1.0-beta.3` therefore remains unchanged in Phase 32R.

