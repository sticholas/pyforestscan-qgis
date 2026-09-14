# Phase 32U Process Composition Audit

## Root UX failure

Phase 32T reduced measured content height, but split one workflow across two independent columns. At normal and wide dock widths, Mode, LiDAR, Area, and Output occupied the left column while Products, readiness, and execution occupied the right. The columns had unrelated heights, leaving large blank regions and no reliable reading order. Products were visually separated from Output, Advanced appeared as a generic nested panel, and area utilities stretched far beyond their natural width.

The supplied screenshots are treated as failure evidence. The 43.4 percent height reduction from Phase 32T is not used as evidence of usability.

## Final information architecture

The Process page now preserves this order at every width:

1. Mode
2. LiDAR Data
3. Processing Area
4. Products
5. Advanced Scientific Settings
6. Output
7. Prerun Check and Process LiDAR
8. Progress and current result

Major sections never move into parallel workflow columns. Responsive changes are limited to homogeneous content: Products uses four columns when the content viewport is at least 720 px and two columns below that; Advanced uses an inline form at wide widths and wrapped rows at narrow widths. The two primary actions share a row when space permits and stack only in a narrow content viewport.

## Composition changes

- Routine Process sections are frameless and use section headings instead of card borders.
- Mode is a visually minor label/control row.
- Processing Area keeps its summary, Refresh, and Zoom actions together; utility buttons use natural width.
- Product checkboxes retain registry-driven names and isolated hover/focus descriptions.
- Advanced Scientific Settings immediately follows Products and remains one compact row while collapsed.
- Output follows scientific configuration.
- Prerun Check is secondary to the Process LiDAR action without changing either command's behavior.
- Progress remains below the action row and retains durable Phase 32Q state semantics.
- Context help remains a bounded footer rather than another workflow section.

## QGIS 3.44.13 measurements

Source-tree PyQGIS profiling used QGIS 3.44.13-Solothurn at 420x760, 600x800, 760x900, and 1100x900.

| Dock size | Internal mode | Content height | Horizontal overflow |
| --- | --- | ---: | ---: |
| 420x760 | two-column Products; stacked actions | 1098 px | 0 px |
| 600x800 | two-column Products; inline actions | 1098 px | 0 px |
| 760x900 | two-column Products; inline actions | 1054 px | 0 px |
| 1100x900 | four-column Products; inline actions | 1054 px | 0 px |

The taller narrow layout is intentional: actions stack instead of forcing horizontal overflow. Expanded expert settings may scroll.

## Responsiveness and help

Twenty FHD toggle cycles averaged 0.24 ms with a 1.22 ms maximum. Rapid CHM/FHD/PAI/PAD/Rumple toggles remained below 0.45 ms. Product toggles made zero polygon-normalization calls. The QGIS help inventory found no missing help among 92 visible controls across Mission Control and Advanced Toolbox.

## Visual review gate

Offscreen screenshots verify geometry and overflow but are supplemental. Release packaging must be installed into the default QGIS profile and inspected in the visible desktop application before Phase 32U signoff. The visible review must confirm one reading direction, clear Products-to-Advanced-to-Output association, natural-width area utilities, and no mostly empty framed containers.
