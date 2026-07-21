# Contextual Help System

Phase 27J adds a reusable Mission Control help control for terms and controls whose consequences are not obvious.

## Component

`pyforestscan_qgis/ui/help.py` provides:

- `InfoHelpText`
- `InfoHelpButton`
- `info_help_button()`

The visual form is a small circular text fallback button labeled `i`. It has a concise tooltip, a keyboard focus policy, an accessible name, and an optional click-through detail dialog. Tooltips should stay short; detailed help belongs in the click dialog or documentation.

## Writing Standard

Help text should explain:

1. What the option is.
2. Why the user might use it.
3. What happens if they leave the default.
4. Any significant risk or consequence.

Avoid vague text such as "controls strategy". Prefer concrete wording such as "Scan File Headers reads the spatial bounds stored in each LAS or LAZ file. It is compatible but can be slow for very large repositories."

## Guided Versus Advanced

Guided mode should use plain labels such as **Automatic Setup**, **Prepare Repository**, and **Use Built-in Spatial Access**. Internal enum labels remain acceptable in logs and technical diagnostics, but not as primary user-facing choices.

Advanced sections should remain collapsed by default, include help when settings affect CRS, performance, memory, output meaning, overwrite behavior, or scientific interpretation, and provide reset-to-recommended behavior when a group exposes multiple tunable controls.


## Phase 27K InfoBadge Registry

Contextual help content now lives in . UI code should prefer  so wording, recommended defaults, consequences, and documentation anchors stay centralized. The reusable  is a small blue circular information badge with tooltip, click detail, keyboard activation, and accessible name. Run  to report registered, used, missing, and orphan topics.
