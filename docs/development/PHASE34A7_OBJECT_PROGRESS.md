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
- New-object creation uses the current authoritative selection and the same
  `SET_OBJECT_ID` journal operation. Allocation reserves every active staged
  target as well as every original catalog ID, recalculates after undo/redo,
  and reports storage exhaustion instead of reusing an ID.
- Added linked-view object focus as presentation-only state. Show All, Fade
  Others and Isolate Selected Object reuse the current authoritative object
  selection overlay across Overview, Area Detail and Vertical Slice renderers.
  Focus changes only source-cloud opacity, never source buffers, selection
  definitions or the edit journal. A renderer-exact integer guard prevents
  visually ambiguous focus for object IDs outside JavaScript's exact range.
- Added guarded split and merge workflows without a second object engine.
  Split freezes one exact catalog object as its parent, then intersects a newly
  drawn full-resolution selection with that object's original source predicate.
  Empty and whole-parent results fail closed; a valid subset receives the next
  collision-safe ID. Merge requires an exact active catalog selection and an
  existing, distinct target ID. Both operations stage ordinary `SET_OBJECT_ID`
  journal entries and therefore retain undo/redo, recovery, export validation,
  large-edit confirmation and immutable-source behavior.
- Added an explicit disk-backed effective-object audit. It streams the verified
  original source in 65,536-point chunks, replays the active journal, excludes
  points staged for removal, and atomically records exact source/effective
  counts without mutating or replacing the original catalog. Any journal change
  invalidates the prior result, so stale effective totals are not presented as
  current. The audit is user-invoked, cancellable and bounded by SQLite rather
  than the number of object IDs fitting in QGIS memory.
- Added explicit Reviewed/Not Reviewed state and notes for exact catalog
  objects. The managed editor worker owns one source-fingerprinted, bounded
  session ledger, and updates require the current exact object selection.
  Review metadata survives session autosave/recovery but is deliberately not a
  point edit, journal operation, LAS dimension or exported cloud attribute.

## IN PROGRESS

Discovery, navigation, guarded assignment/unassignment, collision-safe object
creation, guarded split/merge, exact effective counts and presentation-only
focus, review state and notes are foundations. Live object-focus acceptance
still needs a source with a meaningful segmentation field.

## NEXT

1. Qualify linked-view focus and object operations on a real segmented forestry
   source and record frame-time, displayed-point and source-immutability
   evidence.

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
`Tree_ID` Extra Bytes field, allocated new ID `3`, staged one `SET_OBJECT_ID`
operation, then proved the next safe ID advanced to `4`. It validated a new LAZ
in 0.047 seconds. Readback was exactly `[3, 3, 2, 2, 2]`, the export reported
two net `Tree_ID` changes, every output dimension matched journal replay, and
source SHA-256
`2e9418479610a698a52edcbbaaf096fae2a991002afd667e2f824e55b457f9bc`
remained unchanged.

The managed split/merge canary used a real LAS container with an `int32`
`Tree_ID` Extra Bytes field. It intersected a drawn source-XY region with exact
original object `1`, resolved two of its four points, and assigned those points
the collision-safe new ID `4`. It then merged all two original points from
object `2` into existing object `3`. Validated LAZ readback was exactly
`[4, 4, 1, 1, 3, 3, 3, 3]`; change accounting reported four `Tree_ID` changes,
every output dimension matched ordered journal replay, and source SHA-256
`d6f209aaa54dbf9f959b8371908b441a44cbeeb4e216fcfc85eda041468e6d72`
remained unchanged. Export duration was 0.031 seconds in this synthetic-scale
qualification. The extended run's disk-backed effective audit independently
reported three effective objects, exact largest counts `3:4`, `1:2`, `4:2`,
four staged membership changes and zero unassigned points in 0.016 seconds.
Evidence is retained under
`C:/Users/Milo/AppData/Local/Temp/pfs-object-effective-audit-906e21ad`.
