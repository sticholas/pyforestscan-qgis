# Phase 34A6: LiDAR Classification Workbench

State: IN PROGRESS. The Point Cloud Editor remains EDITOR_EXPERIMENTAL.

## DONE

- Added one QGIS-free LAS 1.4 classification catalog for codes 0-22, common
  forestry/editor targets, reserved codes, user-defined codes 64-255, compact
  warnings, and theme-independent palette colors.
- Replaced the editor's partial hardcoded target list with the complete shared
  catalog. The existing compact target control now shows a color swatch and
  precise class name for every standard code while retaining custom uint8 entry.
- Classification still stages through the existing authoritative selection and
  edit journal. Source files, export rules, viewer LOD, PBM and scientific
  processing behavior are unchanged.
- Added an explicit opt-in `Classify each selection` mode. It stages the chosen
  target only after a newly drawn, non-empty authoritative Replace selection
  resolves. Add/Subtract composites are skipped with clear status text; restore,
  invert, resize, undo/redo, errors and telemetry cannot trigger automatic
  edits. The managed editor remains the only journal writer, so large-selection
  confirmation, autosave, undo/redo and immutable export rules remain active.
- Upgraded view-local class visibility to the shared LAS catalog. Docked and
  detached views can show, hide, isolate or restore classes without sending an
  edit command. Rows use class names and swatches and may show explicitly
  approximate resident-view counts after staged edits; they are not presented
  as authoritative full-source totals. Each linked view retains its own filter.
- Replaced numeric-only selection summaries with compact catalog names and
  authoritative full-resolution counts from the selection resolver. The
  expanded Selection Details view uses the same catalog. Classification targets
  now show a stable one-line LAS/scientific impact message for ground,
  vegetation, noise, building, water, unclassified, reserved and user-defined
  targets without expanding the viewer layout.
- Added a compact `Quick target` palette for Ground, Low/Medium/High
  Vegetation, Building, Water, Low Noise and High Noise. Choosing a preset only
  updates the proposed LAS class and its guidance; it cannot bypass Apply,
  classify-while-selecting guards, large-edit confirmation or the journal.
  Noise, Withheld and Remove-on-Export remain explicit actions under Cleanup.
- Added an explicit source-wide classification audit under Editing Details. It
  streams the verified original in fixed 65,536-point chunks, replays only the
  active journal, counts original/effective classes, reclassified/withheld/
  remove-on-export points, and records factual ground/unclassified/noise review
  prompts. It is cancellable, source-immutable, never automatic on open, and is
  invalidated by stage/undo/redo so stale totals are not presented as current.

## IN PROGRESS

The catalog, guarded classify-while-selecting policy and view-local class
visibility, authoritative selected-class counts, target guidance and the
forestry quick-target palette and explicit bounded source-wide audit are
foundations. Broader data-health analysis and human interaction acceptance are
not yet complete.

## NEXT

1. Qualify the classification workflow and full-source audit in a fresh human
   viewer session.
2. Expand factual data-health summaries without silent edit suggestions.
3. Begin Phase 34A7 categorical object-field discovery without hardcoding one
   segmentation schema.

## BLOCKED

Human classification-workbench acceptance requires a fresh viewer session; old
user-owned viewer hosts currently occupy the configured runtime slots and are
not terminated automatically.

## MEASURED EVIDENCE

The managed-engine smoke audited
`215000_2114500_g_h_c_h_unbuf_hag.laz` at source SHA-256
`0c688c22d42b0240c6cba19973087ee59606721289872a3f8237253548db34bb`.
It streamed all 2,287,408 records in 0.469 seconds with a 65,536-point chunk
contract, reconciled exact class totals, reported 16,081 unclassified points
(0.7%), and verified the original identity unchanged before publication.
