# Phase 33C Results Workspace

Phase 33C makes the Process terminal state content-sized and introduces a bounded,
registry-backed Recent Results view.

## Ownership

processing_history.json is the authoritative lightweight result index. It records
job and attempt identity, plan signature, source, products, terminal state, time,
area, registered outputs, output folder, and human report paths. Mission Control
reads at most 15 entries and never discovers history by scanning output folders.

Opening or loading a historical result does not alter the active polygon, plan,
runtime token, output identity, or current job.

## Layout

The Process workspace no longer includes a vertical stretch that consumes the
remaining viewport. Hidden progress and worker controls are state-driven, and
terminal states collapse to the status summary before Recent Results.

Prerun Details recalculates its text document height, invalidates the enclosing
layout, and performs a deferred fit when visible. Long content remains bounded and
scrollable.

## Result Actions

- **Load into QGIS** loads only the selected registry entry's outputs.
- **Open Outputs** opens the final user-facing output directory with
  QDesktopServices.
- **Open Report** opens the human processing report.
- **View Error** opens the human error report for partial or failed jobs.
- **New Run** resets active workflow state but preserves Recent Results.

Navigation failures are reported in Mission Control with the unresolved path.

## Diagnostics

Tools & Setup presents a human-readable system summary generated from the
authoritative Processing Engine registry. The raw event stream remains collapsed
under **Technical Log**.

## Runtime QA

The Process page was constructed and exercised offscreen in QGIS 3.44.13 and
QGIS 4.0.0. Both runtimes passed three-result ordering and isolation, local and
UNC Qt URL construction, first Details expansion, and terminal-to-active geometry.
Measured Process heights were 75/345 px on QGIS 3.44.13 and 59/259 px on QGIS
4.0.0 for terminal/active states.

The automated run intercepts QDesktopServices immediately before OS handoff so it
can assert exact targets without opening desktop windows. A human interactive
click confirming the Explorer window is therefore still part of release QA.
