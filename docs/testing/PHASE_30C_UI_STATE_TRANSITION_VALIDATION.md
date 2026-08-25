# Phase 30C UI State Transition Validation

QGIS-free tests execute 100 deterministic visibility transitions across Automatic/Custom profiles, Sequential/Parallel modes, folder/polygon modes, and absent/present repositories. Returning to a baseline produces the identical immutable visibility model. Parallel confirmation remains hidden in every state.

Static regressions verify that collapsible sections own one durable content widget, do not recursively overwrite child visibility, refresh layout geometry, and never remove, reparent, or delete reusable controls.

The installed QGIS 3.44.13 launcher on this development machine currently fails importing `PyQt5.QtCore` before plugin import. Live checks for QObject survival, `sizeHint`, dock resize, and collapse/reopen therefore remain required on a working QGIS runtime.
