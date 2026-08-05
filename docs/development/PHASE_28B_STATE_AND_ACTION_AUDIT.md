# Phase 28B State and Action Audit

## State flow

`MissionControlSessionState` is the authoritative retained-interface snapshot. Batch publishes typed snapshots; Mission Control enriches them with backend, environment, generated-output, and loaded-output state; retained pages receive read models. Navigation is not a synchronization trigger and hidden pages are not intermediaries.

| Page | Displayed value | State owner | Update trigger | Refresh contract | Stale-state handling |
|---|---|---|---|---|---|
| Batch | repository, polygon, products, output, plan | session state / Batch controls at input boundary | input signals, preflight, execution | publishes `sessionStateChanged` | input changes invalidate preflight |
| Results | generated and loaded outputs | job/output registry | completion and load signals | existing report/job setters | refreshed without navigation |
| Scientific Advisor | contextual guidance | `ScientificAdvisorSummary` | session snapshot changes | `refresh_from_session` | old cards hide immediately; 150 ms debounce |
| Environment | backend and runtime readiness | environment report | refresh/backend signals | existing `refresh` | manual checks remain explicit |
| Settings | persisted settings/backend status | settings/backend services | setting and backend signals | existing settings contract | changes propagate through Mission Control |
| Advanced Toolbox | provider, algorithms, groups | QGIS Processing registry | activation and Refresh Tools | `refresh_from_session` | inline missing-provider result |
| Home / Workspace / Dataset / Planning / Processing | retained legacy workflow | legacy mission state | existing internal signals | constructible, hidden | not required by retained state flow |

## Events

`SessionStateEvents` defines repository, polygon, product, output, plan, backend, environment, processing, output, and reset events. Batch currently emits the combined typed snapshot so subscribers receive a consistent state rather than reading labels or hidden widgets.

## Polygon propagation

Repository, source, layer, selected/full-layer mode, vector sublayer, WKT, CRS, dissolve, products, resolution, and output edits invalidate the current plan. Normalization supplies geometry signature, area, feature count, and CRS when the source is valid. Invalid or cleared input publishes an empty polygon context, preventing previous guidance from remaining visible.

## Refresh cost

Session rendering is automatic and lightweight. Environment and provider inspection are manual. Processing, repository scanning, and scientific work are never started by page activation.

## Phase 28C rendering contract

The Phase 28B state flow is unchanged. Phase 28C uses it to hide irrelevant mode sections, stale Prerun state, empty Results controls, and result lists until their state is meaningful.

## Phase 28D state correction
Processing selections are project scoped. Repository and polygon changes invalidate the active plan and current-run outputs immediately; global legacy dataset/planning state is no longer restored.
