# Phase 30C Single-File Regression

Regression fixture: one LAS source, CHM + Rumple, Automatic profile, primary-output auto-load enabled, and no persisted UI preflight object.

Process now runs validation automatically, freezes the selected source and both requested products into `BatchExecutionRequest`, and starts with one logical input. Queue-row updates cannot clear the launch snapshot. The test confirms the requested concurrency remains a ceiling while a one-source planner may choose one effective worker.

The same contract accepts multiple LAS/LAZ paths and COPC paths. Folder discovery feeds the normalized selected tuple. EPT and polygon execution retain their repository-specific immutable preflight/plan path. Rumple mathematics and CHM dependency reuse are unchanged by Phase 30C.
