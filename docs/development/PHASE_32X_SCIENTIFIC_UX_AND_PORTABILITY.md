# Phase 32X Scientific UX and Portability Audit

## Advanced layout root cause

The shared disclosure component was content-sized, but Process replaced its
vertical `Maximum` policy with `Minimum`. Expansion then set the body maximum
to Qt's unbounded value. Inside the resizable page scroll area, that combination
allowed the body to absorb surplus height after hidden form rows changed.

The Process override is removed. The tested QGIS/PyQt 5.15 binding does not
expose `QFormLayout.setRowVisible`; hiding only the two widgets leaves every
row spacing in the form hint. Process therefore reconstructs the form from the
currently active field list on that binding, while newer Qt bindings can use
native row visibility. Expanded bodies are capped to the current child layout
`sizeHint()` after complete rows are updated. Collapsed
bodies remain zero height. This makes CHM compact and adds height only for rows
made visible by FHD, PAD, or other selected products. The exact DPI/theme height
matrix is recorded by installed-QGIS QA rather than encoded as constants.

The footer uses natural-width Calculation Reference and Restore Defaults
actions. The reference opens the official PyForestScan calculate API page.

## Semantic help

Stable keys in `ui/help_topics.py` now define Process discovery, polygon,
product, scientific parameter, reference, and Fallback CRS semantics. The old
label-generated interactive fallback was removed because it produced complete
but meaningless coverage. Scientific controls describe interpretation and
tradeoffs; Clear explicitly states that source files are untouched.

## Fallback CRS

Fallback CRS extends the existing user-local `spatial_policy.json`. Selection
uses QGIS's native CRS dialog; clearing it affects only the preference.
Resolution precedence is authoritative source/assignment, repository and
existing safe coordinate-space rules, then user fallback. Polygon alignment
requires strong numeric compatibility before fallback can apply. Provenance is
`CRS ASSUMED FROM USER FALLBACK`, no transformation is implied, and Prerun gets
an explicit warning. Incompatible bounds remain blocked.

## Portability findings

- Portable: `pathlib` storage layout, guarded QGIS API wrappers, `qgis.PyQt`
  imports, sanitized engine environment, backend-owned Python.
- Windows-specific by design: hidden-console flags, task-tree termination,
  LocalAppData, `.exe`, `Scripts`, and `Library/bin` discovery.
- POSIX-specific by design: process sessions/groups, signals, `bin/python`, and
  XDG/macOS user storage.
- Must remain gated: platform lock files, ARM artifact selection in the active
  installer, macOS signing/quarantine, Flatpak subprocess access, and QGIS 4
  Qt 6 live behavior.

The available QGIS 4.0.0 spike exposed Qt 6 scoped dock-area and dock-feature
enums. These are now resolved through `compat/qt.py`; the current QGIS 4.2.1
release is not installed on the test host and remains unqualified.

See [Compatibility](../COMPATIBILITY.md) for the support matrix and runtime
inventory.
