# Non-destructive point cloud editing

Editing controls are not available in the foundation milestone.

The implemented internal journal records classification assignments and noise
marks without writing point data. Undo/redo changes the active journal, not
the original file. Future visible selections must address full-resolution
source points rather than just points currently displayed.

Saved sessions bind to source fingerprints; changed sources are rejected.
Do not interpret these unit-tested contracts as a validated interactive editor.
