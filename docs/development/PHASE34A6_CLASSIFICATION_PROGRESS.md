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

## IN PROGRESS

The catalog is a presentation/policy foundation. Fast classify-while-selecting,
visibility/isolation, richer counts, presets, data-health summaries, and target
warnings are not yet complete.

## NEXT

1. Add guarded classify-while-selecting through the existing worker journal.
2. Build compact class visibility/isolation using the shared catalog.
3. Surface selection and effective-class counts without permanent large panels.

## BLOCKED

Human classification-workbench acceptance requires a fresh viewer session; old
user-owned viewer hosts currently occupy the configured runtime slots and are
not terminated automatically.
