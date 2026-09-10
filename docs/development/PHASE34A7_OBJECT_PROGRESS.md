# Phase 34A7 Objects / Trees / Segments Progress

State: IN PROGRESS. Guarded assignment/unassignment is enabled; broader object
operations remain experimental and incomplete.

## DONE

- Added explicit, read-only discovery of potential object and segmentation
  dimensions for local LAS/LAZ/COPC editor sources.
- Discovery scans the verified original source in fixed 65,536-point chunks and
  distributes an evenly spaced sample across the full source order. A global
  1,048,576-value budget and 256-field guard bound memory even for unusually
  dimension-rich Extra Bytes records.
- Standard LAS measurement/transport fields are excluded. Every other numeric
  field is evaluated from its values, so arbitrary repeated integer dimensions
  can be candidates without matching a hardcoded name. Names such as tree,
  segment, object, instance or cluster improve role ranking only.
- Reports are session-backed and available under Editing Details. Discovery is
  explicit, cancellable, source-immutable and does not create journal edits.
- Added a disk-backed exact catalog for one user-selected candidate field. It
  aggregates exact object counts and XYZ bounds per bounded reader chunk into
  SQLite, verifies the source before and after, and atomically replaces an old
  catalog only after success.
- Object ID and next/previous navigation create ordinary full-resolution
  `SelectionDefinition` queries using the cataloged bounds plus exact original
  source attribute value. The authoritative resolver must reproduce the exact
  catalog count before the selection is published to linked views.
- Added an explicit object-ID policy for integer-backed fields. The user must
  confirm which exact value means unassigned before later object mutations can
  exist. Next-ID allocation scans the disk catalog in constant memory, stays
  within the catalog-supported range of the source integer storage, skips the
  unassigned value, and fails on exhaustion. Float-backed IDs and unsigned
  64-bit values above SQLite's signed-key ceiling remain read-only.
- Added `SET_OBJECT_ID` to the existing ordered edit journal. Assign and
  Unassign use the current authoritative full-resolution selection, preserve
  Replace/Add/Subtract and original-attribute predicate semantics, participate
  in the same undo/redo/autosave/recovery/export path, and never mutate source
  buffers. Large edits use the existing confirmation gate. Export validation
  now reports net changed point counts per object field.

## IN PROGRESS

Discovery, navigation, and guarded assignment/unassignment are foundations.
Split/merge, catalog-aware effective counts, isolate/fade, reviewed state and
notes are not yet complete.

## NEXT

1. Add linked-view isolate/fade behavior without changing edit authority.
2. Add safe create/split/merge workflows on top of `SET_OBJECT_ID` and refresh
   effective catalog counts without changing original selection predicates.
3. Add reviewed/unreviewed state and notes without encoding review metadata into
   immutable source dimensions implicitly.

## BLOCKED

Human object-workbench acceptance requires a source containing a meaningful
object/segment dimension and a fresh viewer session. No platform support claim
is made from synthetic fixtures alone.

## MEASURED EVIDENCE

The managed-engine smoke inspected all 2,287,408 points in
`215000_2114500_g_h_c_h_unbuf_hag.laz` in 0.485 seconds and sampled 65,355
positions distributed across the source order. It correctly rejected
the continuous `HeightAboveGround` dimension, reported no false object-field
candidates, and verified source SHA-256
`0c688c22d42b0240c6cba19973087ee59606721289872a3f8237253548db34bb`
unchanged. Synthetic structured-array tests independently prove that repeated
integer identifiers with an unfamiliar name are discoverable without a
hardcoded schema.

The managed object-export canary created a five-point LAS with an `int32`
`Tree_ID` Extra Bytes field, staged one `SET_OBJECT_ID` operation and validated
a new LAZ in 0.031 seconds. Readback was exactly `[8, 8, 2, 2, 2]`, the export
reported two net `Tree_ID` changes, every output dimension matched journal
replay, and source SHA-256
`2e9418479610a698a52edcbbaaf096fae2a991002afd667e2f824e55b457f9bc`
remained unchanged.
