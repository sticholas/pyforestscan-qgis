# Point Cloud Viewer Stability Contract

This contract protects the existing workspace while qualifying Phase 34A3.3.
It does not authorize Phase 34A4 or change scientific processing.
See the [stability evidence and gate](../testing/PHASE_34A3_3_STABILITY_EVIDENCE.md)
and [dense pipeline profile](../testing/PHASE_34A3_2_DENSE_VIEW_PIPELINE_PROFILE.md).

## Process ownership

- QGIS owns the page and Qt worker objects, not scientific arrays or WebGL.
- The managed viewer is an isolated child; the scientific editor is a separate
  verified-engine child. Stop/reload concerns only the corresponding owned run.
- Teardown waits for worker completion. Never kill processes by executable name.
- QA checks process creation time as well as PID: Windows recycles PIDs.
- Renderer failure must not invalidate Processing Engine readiness or erase
  autosaved edits. Reload restores the original-source editor overlay.
- A nonresponsive child is a failed attempt, not successful completion.

## Filter panel

There is one owned nonmodal tool panel per Point Cloud page. It is not inserted
into the canvas layout. Closing the page closes the panel. Controls target only
their owning page; opening the panel must not change camera, budget, selection,
overlay or session state. Opening/closing is distinct from intentionally applying
a filter or changing a selection, which may update editor controls.

Filter help is local to the panel and uses the existing semantic-help component.
Source Z is not falsely described as Height Above Ground. Numeric controls have
accessible names; closing returns focus to the owning page's filter button.
Qt5 and Qt6 each have a 500-transition real-renderer regression.

## Dense intake and authority

The planner chooses bounded DIRECT for eligible small sources, native COPC/EPT,
or BUILD_VIEW_CACHE / REUSE_VIEW_CACHE. DIRECT_STREAMED is reserved, not enabled.
The conservative direct admission limits are provisional, not hardware claims.

Original file content identity is authoritative for selections, journals and
exports. A reordered COPC cache is never an address map. Raw selection scans
original records in 65,536-point chunks with no prefetch, inside the editor
worker. This removes the former two-million-point rejection without pretending
that an unindexed full-source query is instantaneous. Cancellation is checked
between chunks. Export and session reopen independently verify the source hash.

EPT remains view-only until immutable affected-node identities and bounded
selection/export contracts are implemented and tested. Hashing ept.json alone
does not identify a mutable EPT tree. Do not weaken this guard to pass a gate.

## Cache lifecycle

Managed entries live below the viewer source-cache directory, never beside the
original by default. Identities include source SHA256, size, mtime, dimensions,
CRS, converter version and conversion policy. Policy changes invalidate reuse.

Only staged, verified COPC is published. Reuse verifies its stored SHA256, size,
COPC readability, point count, dimensions, bounds and CRS. Verification holds a
cleanup lock; active viewers hold read leases. Failed or missing/corrupt entries
are rebuildable. Only confirmed-dead build locks may be recovered; ambiguous
locks are retained. Conversion has clean restart, not invented partial resume.

Cleanup owns only recognized cache files in hash-named entries. Unknown files,
journals, sessions, user exports, active leases and source paths are protected.
The 8 GiB eviction target is a soft budget for old eligible entries, not a hard
limit on active or newly built clouds. Disk preflight includes scratch needs.
Cache absence must not make a valid original-source session invalid.

The managed Untwine 1.5.1 runtime is separate from QGIS and scientific Python.
Its scanner-channel packing defect is handled by a bounded temporary LAS input
for point formats 6+: ClassFlags carries correctly positioned channel bits while
the temporary ScanChannel is zero. Original attributes are never changed. An
existing ClassFlags extra dimension is rejected rather than overwritten.
Unknown converter versions are not silently admitted. Windows child indexing
has a process memory limit and kill-on-owner-close job; Linux/macOS resource and
embedded-adapter behavior are not claimed as tested.

## Memory and transport

Point data travels as bounded binary source/range responses to browser decoding
workers, not JSON point arrays through QGIS. Decoder allocations are released
on success and failure. Rendered point budgets and resident-node limits are
separate. Performance profiles are advisory and machine-specific; the RTX 4090
measurements are not minimum-hardware guarantees.

Soak evidence must record actual submitted points, frame times, process memory,
node residency and source transport. A point submission count does not prove
every submitted point survives a filter or lies on screen. Working set, private
commit, mapped residency and Python-traced allocations are different metrics.

## Export and failure

The validated exporter still streams original records into disk-backed staging,
replays the journal, writes a new LAS/LAZ and validates all original dimensions.
No overwrite of original or existing final outputs is allowed. Process handoff
requires the validated output and does not automatically start processing.

Normal failures remove owned scratch. Abrupt child termination bypasses finally
blocks and can retain hidden, explicitly named .partial scratch files. These
are not completed exports. The tested crash left no published destination or
validation sidecar; retry used the same destination safely. Automatic cleanup
of abruptly orphaned scratch is not qualified and must not infer ownership from
an arbitrary filename alone.

## Protected test boundaries

`python3 scripts/run_test_tier.py VIEWER_CORE` runs viewer policy, cache, runtime,
transport, session and related contract tests. `EDITOR_CORE` covers original
selection, journal and editing. `PROCESS_CORE` preserves all non-point-cloud
tests; `RELEASE` explicitly selects release/package tests. `FULL` and ordinary
unittest discovery remain mandatory at release milestones. No tier deletes or
reclassifies tests out of the full suite.

Human drawing, editing and export acceptance, long-run evidence and EPT editing
are separate gates. A successful unit suite alone never unblocks 34A4.
