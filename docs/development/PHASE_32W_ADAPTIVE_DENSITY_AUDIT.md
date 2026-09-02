# Phase 32W Adaptive Density Audit

Phase 32W preserves the Phase 32V Process order and compact configuration while improving disclosure affordance and removing idle status scaffolding.

## Measured QGIS 3.44.13 Geometry

| Surface | Collapsed/idle | Expanded/active |
| --- | ---: | ---: |
| Advanced Scientific Settings header | 28 px | 249-432 px, based on selected products |
| Prerun Details header | 28 px | 69 px for the current concise report |
| Processing | 47 px | 134 px during validation, running, or paused |
| Processing complete | 47 px | Details remain separate and collapsed |
| Tools & Setup READY content | 224 px | 708 px with diagnostics expanded |

Selecting FHD while Advanced was collapsed left the section at exactly 28 px. Expanding with FHD grew it to 372 px; adding PAD grew it to 432 px. Removing both returned the expanded base to 249 px, and collapsing restored exactly 28 px.

## Disclosure Contract

CompactCollapsibleSection owns one 28 px QToolButton header with native right/down disclosure arrows, accessible naming, hover/focus treatment, and contextual help. Its body is hidden and capped at zero height while collapsed. The same component is used for scientific settings, Details, diagnostics, preferences, and other expandable Mission Control surfaces.

## Processing Contract

The existing ProcessingUiState remains authoritative. Idle and terminal states hide progress, worker, capacity, and historical result scaffolding. Validation, starting, running, paused, and finalizing states reveal live progress content and trigger immediate layout geometry updates. No processing execution behavior changed.

## Tools & Setup Contract

READY presents a concise status, secondary Repair action, Recheck action, collapsed Preferences, and collapsed Details. Setup is primary only when missing; repair is primary only for broken/incompatible states. Runtime paths, manifests, package checks, and technical logs remain under Details.

## Live Gate

The required Process idle, Advanced expanded, Process active, Tools & Setup READY, and Tools & Setup Details-expanded screenshots were captured from QGIS 3.44.13 at 1400 x 900. There was no horizontal overflow, invisible disclosure row, or idle reserved panel.
