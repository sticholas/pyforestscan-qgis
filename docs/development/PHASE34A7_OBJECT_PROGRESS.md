# Phase 34A7 Objects / Trees / Segments Progress

State: IN PROGRESS. Object editing is not yet enabled.

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

## IN PROGRESS

Discovery and read-only object navigation are foundations only. A candidate
report does not yet make a field editable, define unassigned-value semantics,
or create object IDs.

## NEXT

1. Add linked-view isolate/fade behavior without changing edit authority.
2. Add explicit user confirmation for unassigned-value semantics and safe new
   ID allocation within the selected field's real storage range.
3. Extend the existing attribute journal with validated arbitrary categorical
   edits, then implement add/remove/split/merge as journal-backed operations.

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
