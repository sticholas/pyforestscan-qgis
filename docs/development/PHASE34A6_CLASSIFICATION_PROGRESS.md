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

## IN PROGRESS

The catalog and first classify-while-selecting policy are foundations.
Visibility/isolation, richer counts, presets, data-health summaries, target
warnings, and human interaction acceptance are not yet complete.

## NEXT

1. Build compact class visibility/isolation using the shared catalog.
2. Surface selection and effective-class counts without permanent large panels.
3. Add target warnings and presets without bypassing journal confirmation.

## BLOCKED

Human classification-workbench acceptance requires a fresh viewer session; old
user-owned viewer hosts currently occupy the configured runtime slots and are
not terminated automatically.
