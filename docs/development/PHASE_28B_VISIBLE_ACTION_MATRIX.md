# Phase 28B Visible Action Matrix

| Area | Action | Handler/service | Feedback |
|---|---|---|---|
| Batch | repository, discovery, preflight, run, reset, map tools | existing Batch handlers | inline status, progress, or actionable error |
| Results | load outputs, open folder, clear run | Results handlers / QGIS layer API | load summary and Mission Control notification |
| Scientific Advisor | open output folder | Advisor handler | inline next-step feedback when unavailable |
| Environment | refresh, backend settings | environment service / navigation | readiness report and status notification |
| Settings | backend install/repair/verify and persisted settings | PBM/settings services | progress, result, logs, and state signal |
| Advanced Toolbox | sidebar activation / Open Processing Toolbox | `QgisProcessingToolboxService.open_toolbox` | panel focus plus inline/message-bar result |
| Advanced Toolbox | Refresh Tools | duplicate-safe provider refresh | provider status and algorithm count |

The primary sidebar order is Batch, Results, Scientific Advisor, Environment, Settings, Advanced Toolbox. Hidden pages remain constructible but are absent from primary navigation. Advanced Toolbox is a real compact page and never resets to a prior navigation row after a silent attempt.

Disabled controls retain their existing readiness rules. Placeholder-only controls were not introduced. Advanced Toolbox reports a missing toolbox/provider instead of failing silently.
