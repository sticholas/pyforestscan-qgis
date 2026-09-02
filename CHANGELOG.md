# Changelog

## Phase 32Q - Adaptive parallel EPT execution and live progress

- Added conservative one-to-five process-level EPT concurrency with measured-memory ceilings, network-latency backoff, repeated-crash circuit breaking, and a machine-wide heavy-worker budget.
- Kept every bounded region in an isolated PBM child process while preserving region checkpoints, pause-after-active-work, owned-child cancellation, and coordinator-only finalization.
- Projected coordinator state into Mission Control with weighted progress, robust ETA, completed/active/remaining region counts, child stages, health, and human-readable elapsed time.
- Accounted for the completed 109-region, 9,847.953-second production baseline and documented the benchmark gate without claiming unmeasured speedup.
- Left PyForestScan source, scientific parameters, global grid, exact polygon mask, and Advanced Toolbox behavior unchanged.

## Phase 32P - High-throughput EPT execution and release integrity

- Removed alignment-rounding slivers and replaced the fixed small-request point ceiling with computed point, raster, and memory safety budgets.
- Restored one managed EPT operation per ordinary component while retaining larger 500-cell checkpointed subreads only for genuinely large regions.
- Reduced the exact 414.636 ha fixture from 50 regions to its 27 real polygon components with 1.402x read amplification and no residual strip blocks.
- Added per-work-unit scientific stage timing and active-region progress identity.
- Hardened packaging with clean-tree enforcement, fresh staging, recursive source-to-ZIP verification, expanded build identity, and release-chain documentation.

## Phase 32O - Sparse adaptive EPT execution

- Replaced global-envelope polygon candidate generation for EPT/COPC with component-first, globally aligned sparse planning.
- Added stable component and ReadBlock/ScienceBlock/CheckpointTile identities, deterministic nearby-component clustering, Morton execution ordering, and fail-open root EPT hierarchy pruning.
- Stopped materializing known-outside polygon cells or writing skipped-cell checkpoint state; the exact 414.636 ha fixture fell from 3,450 candidate objects to 50 executable regions and zero skipped objects.
- Simplified normal preflight wording to selected areas, automatic strategy, and processing regions while retaining engineering counts in technical diagnostics.
- Recorded the legacy run's deployment-loss blocker and deferred live Phase 32O attribution until exact installed-build identity can be verified.

## Phase 32N - Large-scale processing architecture research

- Verified that the active default-profile QGIS installation is still Phase 32L and rejected it as a Phase 32M comparison while preserving its running job.
- Classified the observed 120-second warning as a false stall using child CPU, heartbeat, checkpoint, output-growth, and process-recycling telemetry.
- Benchmarked the exact bounded UNC EPT source, PDAL streaming, immutable local cache, hierarchy pruning, Morton ordering, and managed-process startup overhead.
- Established PyForestScan as the immutable scientific authority and documented scheduler, cache, COPC, GPU, and AI product boundaries.
- Selected the existing durable coordinator for the next phases; no Dask, Ray, CUDA, COPC, or AI dependency was added to production.

## Phase 32M - Large polygon prerun hardening

- Added immutable, QGIS-free normalized polygon geometry so WKT parsing and CRS-aware coordinate validation occur once per prerun instead of once per candidate extent.
- Added polygon, part, and ring envelope rejection before exact clipping; a 221-parent synthetic benchmark reduced 442 parser calls to one and improved the intersection loop by about 23x.
- Moved polygon prerun planning and manifest I/O to a cancellable Qt worker, with staged UI progress, `PRERUN_FAILED` traceback evidence, and `prerun_profile.json` timing/memory diagnostics.
- Added a direct EPT repository fast path that recognizes one logical `ept.json` source without walking EPT internal storage.
- Prevented duplicate source-aware plan construction for legacy manifest aliases while preserving Phase 32K/32L bounded EPT and CRS behavior.

## Phase 32L - Projected CRS polygon validation

- Canonicalized authoritative EPT authority/code metadata before WKT heuristics, so the live NAD83(PA11) / UTM zone 5N source resolves as `EPSG:6635`, projected, metre, and valid.
- Made top-level `PROJCS`/`PROJCRS` semantics authoritative over nested geographic base definitions and added contradictory-state invariants.
- Unified prerun and backend polygon coordinate validation: all CRSs reject malformed or non-finite vertices, geographic CRSs retain strict degree domains, and projected/unknown CRSs do not infer invalidity from magnitude.
- Added actionable coordinate failures with vertex, coordinate, source/destination CRS, classification, and rejected-rule details.
- Corrected transformed polygon transport to carry the destination CRS and transformed envelope instead of the original polygon CRS/bounds.
- Verified the preserved EPSG:3750 polygon transforms to the expected EPSG:6635 bounds with zero spatial blockers, and verified isolated managed children initialize GDAL/PROJ with backend-local data resources.

## Phase 32K - Bounded EPT CHM execution

- Removed the source-wide EPT ground assessment and polygon-wide HAG materialization gate that prevented the 109-area scheduler from starting.
- Added reader-level bounded EPT/CoPC assessment, durable pilot strategy evidence, and per-window HAG execution using the existing buffered CHM path.
- Added explicit pilot-to-scheduler stages, a non-destructive no-forward-progress watchdog, and suppression of the contradictory local-tile warning when an overlapping logical EPT source is selected.
- Kept the 109 frozen parent units while bounding dense EPT reads to checkpointed 100 m child cores, each isolated in a fresh managed PBM process with canonical GDAL/PROJ/DLL paths.
- Completed four real large-plan parent TIFFs, then proved restart recovery of the first three before completing the fourth.
- Positively identified and stopped stalled coordinator PID 32152, then closed its heartbeat as `FAILED_STALLED` while preserving its diagnostics.

## Phase 32J - Coordinator completion lifecycle

- Isolated every polygon coordinator launch in an attempt-specific workspace so stale terminal and cancellation files cannot complete or cancel a new run.
- Added typed spawn, handle, and terminal-result contracts with startup/exit diagnostics and bounded child output logs.
- Blocked zero-output success and gated finalization on validated dataset, product, and output terminal state.

## Phase 32I - Polygon progress and execution control

- Corrected polygon progress so heartbeats update one dataset record without incrementing completion counters or repeating `STARTED` transitions.
- Added observable, checkpointed bounded-input preparation in an owned Processing Engine child with active cancellation and truthful pause-after-step semantics.
- Bounded launch trace growth and separated current heartbeat state from durable transition history.

## Phase 32H - Processing plan and dispatch runtime state

- Separated reusable polygon Prerun plans from attempt-scoped dispatch validation and execution manifests.
- Prevented historical dispatch generations from blocking a new Detailed Check or downgrading a READY Processing Engine.
- Added explicit Engine, Plan, Spatial, Products, and non-blocking Dispatch sections to polygon Detailed Check output.
- Added automatic plan invalidation and Prerun refresh after a READY engine generation update while preserving selections.
- Added lifecycle, generation-linkage, fresh-attempt, and Windows path round-trip regression coverage.

## Phase 32G - Polygon dispatch and engine status consistency

- Fixed the live polygon launch `NameError` by preserving the actual runtime-token comparison returned by the canonical Processing Engine service.
- Added a synchronous dispatch exception boundary that terminates attempts as plugin dispatch failures with traceback diagnostics and never recommends engine repair for programming errors.
- Projected the canonical post-setup Processing Engine state to both Tools & Setup and Process, removing stale split-readiness messaging.
- Clarified package build identity versus the Processing Engine plugin-contract fingerprint in diagnostics.
- Added source and packaged undefined-name validation plus a QGIS-free execution harness for the production polygon click path.

## Phase 32F - Polygon dispatch and background progress

- Fixed a concurrent launch-attempt writer race that could terminate the Qt worker before polygon execution while leaving Mission Control appearing to run.
- Moved generic local LAS/LAZ polygon preparation and PAI/FHD execution into a detached, runtime-validated PBM coordinator.
- Added truthful launch, coordinator, worker, finalization, heartbeat, PID, thread, and elapsed-time diagnostics with launch-stall detection.
- Rewrote dispatch validation at click time so the polygon manifest and attempt trace use the same Processing Engine generation.
- Separated Processing Engine readiness from polygon job readiness on the Process page.

## Phase 32E - Installed build identity and deployment integrity

- Embedded immutable `build_info.json` metadata in every packaged ZIP with commit, build identity, Processing Engine build hash, timestamp, and critical module hashes.
- Added per-session plugin identity and mixed-install detection without conflating plugin corruption with Processing Engine repair.
- Added attempt-scoped polygon launch diagnostics before all guards, plus current-session and latest-attempt summaries in Open Diagnostics.
- Added clean QGIS-profile replacement and recursive ZIP/install comparison tooling.
- Retired the generic Processing Engine repair sentence from production modules and added release validation against its return.
- Removed legacy future-module clutter from normal diagnostics and clarified the genuine internal-beta Micromamba checksum release gate.

## Phase 32D - Verified runtime authority at launch

- Removed duplicate backend readiness discovery from frozen-token polygon dispatch.
- Unified PAI, PAD, FHD, Canopy Cover, CHM, Rumple, and other routed products on the managed runtime token.
- Added runtime generation identity, precise launch mismatch codes, and engine decision traces.
- Prevented delayed startup state from overwriting a newer Repair / Reload result.
- Corrected managed-worker validation so setup-generation metadata is not incorrectly recomputed from a runtime-only probe.

## Phase 32C - Deterministic Processing Engine setup

- Made current-build setup completion and the complete runtime contract mandatory for Ready state.
- Kept Set Up or Repair / Reload visible and routed both through one idempotent ensure transaction.
- Removed the normal Recheck action and permanent LiDAR Spatial Reference card.
- Added contextual Process-page CRS/units intervention with automatic preflight rerun.
- Preserved lightweight, offline Mission Control startup and immediate post-setup UI refresh.

## Phase 32B - Mission Control startup resilience

- Fixed the live QGIS startup crash caused by the removed `smart_system_status_label` and replaced cross-page label writes with semantic APIs.
- Separated UI availability from Processing Engine readiness and deferred optional engine-state resolution until the dock is fully constructed.
- Removed full Environment Check execution from ordinary engine-state projection and footer refresh.
- Added lifecycle teardown guards, packaged QGIS startup/state/width tests, and 100-cycle open-close and navigation soaks.

## Phase 32A - Tools & Setup productization

- Reduced Tools & Setup to one contextual Processing Engine action, always-visible Advanced Settings, and two collapsed troubleshooting actions.
- Consolidated engine compatibility, dependency, path, version, and log evidence under Open Diagnostics.
- Removed Additional Tools and the normal Recent Item Limit control without introducing any processing limit.
- Preserved the authoritative background setup/repair transaction, spatial assignment controls, processing behavior, PBM behavior, Advanced Toolbox, and disabled External Worker policy.

## Phase 31K - Finalization reliability and bounded large-source execution

- Added extracted-ZIP internal import-graph validation, including the adaptive planner and polygon coordinator runtime.
- Finalization now serializes the frozen execution plan instead of replanning after science completes.
- Added completed-science recovery, terminal heartbeat closure, per-area stage timing, and registry-backed processing history foundations.
- Fixed local LAS/LAZ/COPC area reads so frozen bounds are enforced directly by PDAL; Rumple continues to derive from CHM without rereading LiDAR.
- Centralized hidden Windows subprocess flags for coordinator children and capability checks.
- Recorded the real Olaa recovery and LAZ/COPC performance investigation, plus a GeoLibre architecture and UX review.

## Phase 31J - Durable large-source preparation

- Added automatic source-level preparation before Polygon CHM/Rumple canary and tiled execution.
- Added bounded local prepared-source artifacts, durable status/checksum/provenance, process locks, crash-lock recovery, and checkpoint reuse.
- Added evidence-driven normalized-Z validation and explicit Z-to-`HeightAboveGround` materialization.
- Changed preparation failures from repeated tile errors to one structured `source_preparation` scientific blocker.
- Preserved aligned CHM grids, Rumple halos, exact final polygon masks, output registration, and EPT behavior.

## Phase 31I - Verified runtime handoff and Polygon execution identity

- Froze Processing Engine identity during Polygon Prerun and carried it through the manifest, launcher, and coordinator.
- Removed independent Polygon verifier/token resolution and added field-level runtime comparison snapshots.
- Routed local LAS CHM/Rumple plans directly through the durable PBM coordinator.
- Added deterministic global work-unit IDs, conservative raw/prepared source detection, canonical workload estimates, and automatic large-job canary continuation.
- Classified engine rejection before coordinator launch as `runtime_prelaunch`, not a failed scientific batch.

## Phase 31H - Authoritative one-click Processing Engine setup

- Unified setup, repair, final verification, persisted state, runtime token, and launch readiness under one shared Processing Engine service.
- Removed the normal Verify Backend ritual and routed normal Repair through the same one-click setup transaction.
- Added critical-package fingerprinting, callable signature reporting, and all-product capability smoke results.
- Removed default/auto scientific adapters from Mission Control, Process workers, and Advanced Toolbox production entry points.
- Added object-valued engine state synchronization and an inline Process-page Set Up/Repair action that preserves selections.
- Added state convergence, stale-handlers, token reuse, 100-transition soak, and legacy-route guard tests.

## Phase 31G - Processing Engine runtime convergence

- Made the managed Processing Engine the sole normal scientific runtime and blocked QGIS-Python scientific fallback.
- Added a frozen runtime token, executable/contract validation across launcher, coordinator, and worker, plus durable runtime identity traces.
- Added complete PyForestScan module/function, dependency, product-capability, and parameter registries for the supported `0.4.1` contract.
- Consolidated setup/repair state and normal UI wording around one Processing Engine model; successful setup now verifies automatically.
- Added Processing Engine dependency/runtime error classification and regression matrices for clean setup, wrong interpreter, and Polygon launch behavior.

## Phase 31F - Processing Engine bootstrap and runtime contract

- Added one Processing Engine readiness state and verifier for Folder and Polygon execution.
- Made required PyForestScan submodules, protocol, and actual managed-interpreter identity blocking contract checks before scientific job creation.
- Added atomic readiness caching, a cross-session setup lock, centralized silent Windows execution, support diagnostics, and concise setup/repair semantics.

## Phase 31E - Unified polygon spatial fallback

- Added one effective spatial context for Folder and Polygon Selection, including trusted, assumed, unresolved, and conflict modes.
- Added strong coordinate-space compatibility fallback for unreferenced polygon LiDAR with explicit no-reprojection provenance.
- Separated raw overlap from alignment readiness, stabilized repository assignment fingerprints against catalog churn, and added live spatial traces.

## Phase 31D - Unify folder and polygon LiDAR processing

- Applied trusted repository CRS assignments to raw-unknown LAS/LAZ members before direct or catalog overlap selection.
- Added raw/effective CRS provenance, conflict blocking, selection diagnostics, and an Olaa-shaped regression.
- Unified polygon assignment state with the folder workflow while preserving strict polygon alignment and folder source-local fallback.

## Phase 31A

- Added authoritative LiDAR preparation assessment, planning, recovery, recommendation, provenance, quality, and checkpoint contracts.
- Added bounded PBM classification sampling plus DTM, existing-ground Delaunay, and SMRF-then-Delaunay paths for CHM/Rumple.
- Added non-destructive prepared-LAZ reuse, output method tags, actionable preparation errors, and Dataset Explorer readiness semantics.
- Preserved existing-HAG and strict polygon CRS behavior while requiring trusted units for source-local distance operations.

## Phase 30F

- Added PBM protocol 2 contracts for source-local coordinates and authoritative height normalization.
- Fixed missing CRS serialization so Rumple never receives the invalid CRS string `"None"`.
- Preserved and validated `HeightAboveGround` through PBM reads, with explicit mismatch diagnostics and no silent HAG fallback.
- Added runtime identity, module-location evidence, source-local traces, source-local GeoTIFF metadata, and requested-product failure retention.

## Phase 30C - Processing workflow state stabilization

- Replaced mutable preflight-dependent standard Batch launch with an immutable validated execution request, fixing the one-LAS CHM + Rumple `files_to_skip` crash.
- Separated logical processing counts from skipped resume sources and prevented programmatic file-status rows from invalidating readiness.
- Centralized Advanced-control applicability, removed visible parallel-safety certification, enabled primary-output loading by default, and made collapsible geometry preserve child visibility state.

## Phase 30B - Production Rumple finalization and recovery

- Removed the stale `BatchPage._batch_settings()` completion dependency and now build terminal summaries from immutable execution plans, durable results, checkpoints, and output registries.
- Added `COMPLETE_WITH_WARNING` presentation semantics, guaranteed terminal UI cleanup, terminal review reconstruction, and primary-only automatic output loading.
- Added verified CHM product checkpoints for Rumple retry, strict core plan/grid/method/checksum validation, blockwise final-raster scalar aggregation, and semantic horizontal CRS comparison.

## Phase 30A - Spatial Rumple Index raster

- Added a patch-centered Rumple GeoTIFF whose valid-cell mean reproduces upstream PyForestScan scalar Rumple.
- Added automatic CHM generation/reuse, scalar compatibility summaries, half-cell georeferencing, one-cell halo contracts, typed raster/summary outputs, Advanced Toolbox loading, and scientific equivalence tests.
- Preserved legacy scalar CSV plans without interpreting them as spatial rasters.

## Phase 29E - Technical hardening and release readiness

- Added authoritative architecture, state ownership, product/output capability, error taxonomy, retention, and clean-machine QA contracts.
- Consolidated Results metadata behind product capabilities while preserving existing scientific algorithms and registry schemas.
- Added non-destructive job-storage maintenance classification and a 50-cycle current/historical isolation soak.
- Audited package, subprocess, upgrade, telemetry, repository hygiene, and current release blockers without redesigning Mission Control.

## Phase 29D - Measured adaptive performance and scalability

- Unified planner/executor point-memory estimates and added workload-based subdivision for large native sources with unknown or excessive size.
- Added reproducible scale benchmarks, read-amplification and peak-memory diagnostics, explicit direct-versus-durable execution summaries, and synthetic numeric equivalence checks.
- Confirmed one durable PBM coordinator retains imports for all work units; no speculative persistent daemon was added.

## Phase 29C - Product reliability and current-attempt integrity

- Added a complete workflow input signature and invalidation coverage for file selection, recursive discovery, repository fallback, masking policy, profiles, concurrency, products, and output settings.
- Prevented failed, running, partial, stale, or merely discovered-on-disk files from becoming loadable Results; only explicitly registered completed-job outputs are eligible.
- Froze run-defining controls while one coordinator owns an active job and documented workflow, control, session, output, background-job, performance, memory, failure, equivalence, and RC evidence.

## Phase 29B - Workflow simplification and smart automation

- Made Mission Control startup opt-in, consolidated repository and spatial actions, and expanded authoritative plan invalidation.
- Presented Recommended as Automatic, reserved execution topology for Custom, and treated parallel workers as an adaptive upper limit.
- Added on-demand spatial readiness and concise completion summaries without changing processing behavior.


## Phase 29A - Productization UI audit and layout refinement

- Added adaptive, content-sized Process sections and a responsive live session status strip.
- Hid repository, product, concurrency, result, and backend controls until they are relevant.
- Reduced normal Tools & Setup density while preserving scientific, PBM, and Processing Toolbox behavior.

All notable changes to this project will be documented in this file.

This project follows semantic versioning once plugin releases begin. Until the
first public release, changes are tracked under `Unreleased`.

## Unreleased

- Phase 28E-Stabilization limits EPT CHM to one safe-mode worker, classifies collinear/empty HAG inputs as deterministic and nonretryable, pauses after three adjacent identical failures, stops immediately after a native worker crash, preserves pending/completed work with crash-safe scheduler transitions, isolates PBM native paths from QGIS, adds parent-owned crash diagnostics and a native-runtime probe, corrects work-unit progress wording, and adds a 120-transition soak fixture. Live Windows/QGIS validation remains a release blocker.
- Phase 28D replaces the universal one-hour PBM timeout with heartbeat-aware policy models, scopes outputs to attempts, and introduces project-scoped processing state.

## 0.1.0-beta.3 - 2026-08-06

- Phase 28E adds source-aware bounded CHM planning/execution, aligned core tiles, adaptive network-aware concurrency, verified checkpoints, genuine resume, transient retry, transactional mosaicing, and exact final polygon masking.
- Unlimited wall-time values no longer produce `None seconds` or replace scientific errors.
- HAG suitability and strategy models classify `All points collinear` deterministically without identical retry.
- Heartbeats now record elapsed time, stage/work unit, counts, retries, and liveness.
- Other product merge policies remain unvalidated and retain existing execution paths; live equivalence remains pending.


- Phase 28A hotfix repairs Batch startup by constructing product and workflow sections as explicit Qt widgets in final order, eliminating layout-wrapper reparenting that could access a deleted QVBoxLayout.
- Phase 28A productizes Mission Control around Batch, Results, optional scientific guidance, readiness, settings, and Advanced Toolbox; legacy guided pages remain internal, specialist repository/spatial controls are collapsed, and processing behavior is unchanged.
- Phase 27S repairs EPT CRS detection by centralizing EPT SRS parsing, rejecting incomplete values such as `EPSG`, resolving authority plus horizontal code to complete CRS IDs, adding CRS-aware EPT polygon alignment, preserving transformed EPT bounds/manifests, adding support diagnostics, and covering the reported EPSG:6635 overlap regression with QGIS-free tests.
- Phase 27R stabilizes ordinary-folder Polygon Area Processing by adding shared LiDAR source metadata, a direct header-metadata correctness path, a PolygonLidarProcessingService plan, selected-path invariants through preflight/manifest/execution, safer EPT-only logical execution detection, selected LiDAR QGIS map-layer service wiring, regression tests, and live-validation documentation while preserving PBM, exact masking, output registration/loading, diagnostics, and disabled External Workers.
- Phase 27Q restores polygon-to-LiDAR folder source selection by adding a direct header-scan correctness path, automatic catalog-vs-direct comparison/fallback for ordinary local repositories, selection-method controls, manifest diagnostics, an audit script, regression tests, and selection-contract documentation while preserving EPT native handling, PBM behavior, Advanced Toolbox behavior, and disabled External Workers.
- Phase 27P corrects LAS/LAZ catalog CRS semantics so all-CRS-missing bounded catalogs require explicit CRS assignment, adds reversible repository CRS overrides, header verification helpers, extent-defining source diagnostics, a real-repository diagnostic script, and live-QGIS spatial action service boundaries for coverage and zoom feedback.
- Phase 27O verifies and hardens local LiDAR repository discovery and catalog workflows with authoritative supported-source discovery, catalog identity metadata, RTree/source integrity checks, structured skip reasons, safe catalog repair with backups, repository source/coverage/diagnostic models, action-state gating for visible repository controls, and distinct polygon preflight messaging for broken catalogs versus true no-coverage areas.
- Phase 27L validates EPT request contracts with a typed `EptBounds` model, fixes PyForestScan/PDAL bounds serialization to square-bracket coordinate ranges, adds PBM API contract probing, fast backend request validation, diagnostic bundles, support-summary helpers, Processing-page validation guidance, and a standalone request-validation script while keeping External Worker mode disabled.
- Phase 27J fixes Polygon Area Processing EPT handling and PBM readiness by normalizing ept-data selections to one logical ept.json source, pruning EPT internals during catalog traversal, adding fast repair for incorrect node-level EPT catalogs, checking PBM backend readiness before Run, routing logical EPT/COPC processing without staging node files, adding point-estimate plausibility and query timing diagnostics, moving network/mounted catalogs to local storage by default, simplifying guided repository terminology, and adding reusable contextual help controls.
- Phase 27I adds adaptive and lazy LiDAR repository indexing with bounded strategy detection, existing spatial index and PDAL tile-index recognition, native EPT/COPC logical registration, filename/grid and partitioned-lazy planning models, two-pass full-catalog planning, Batch UI strategy controls, docs, and QGIS-free regression tests while preserving PBM behavior, scientific processing, Advanced Toolbox behavior, and disabled External Workers.
- Phase 27H makes large LiDAR repository cataloging responsive by keeping repository selection lightweight, adding Use Path and bounded Quick Probe, introducing durable chunked catalog jobs with stages/counters/rate/checkpoints/locks/pause/resume, adding a PBM catalog runner entrypoint, preserving indexed polygon queries, adding safe benchmark tooling, and documenting large-repository behavior without re-enabling External Workers or changing scientific algorithms.
- Phase 27G adds an indexed SQLite/RTree LiDAR spatial catalog for Polygon Area Processing, automatic polygon envelope derivation with exact WKT retention, streaming catalog build/update, header-only EPT/LAS metadata inspection with explicit metadata errors, catalog-backed polygon preflight, EPT broad bounds plus exact polygon clipping, local-source matched-only opening, best-effort exact raster masking, Batch catalog controls, docs, and QGIS-free regression tests while preserving Standard Batch, PBM installer behavior, Advanced Toolbox behavior, and disabled External Workers.
- Phase 27F moves polygon-driven LiDAR folder processing from Dataset into Batch with Standard File Batch and Polygon Area Processing modes, polygon preflight/manifests, clipped-source staging through the adapter, normal Batch executor handoff, Results integration, and QGIS-free regression tests while preserving PBM behavior, scientific algorithms, Advanced Toolbox behavior, and disabled External Workers.
- Phase 27D corrects PAD/Rumple scientific representation by preserving PAD as a metadata-rich multiband height-bin volume, switching PAD default display to a grayscale height slice, adding PAD derivative raster helpers, keeping Rumple as a scalar CSV with internal CHM reuse/generation notes, adding localized Rumple math as a documented extension, and introducing polygon-folder LiDAR discovery/preflight models and Mission Control entry point without changing PBM installer behavior, external workers, or existing single-file/batch workflows.
- Phase 27E adds guided polygon source selection for polygon-folder preflight from loaded QGIS polygon layers, selected features, entire layers, vector files including GeoPackage/Shapefile/GeoJSON/FlatGeobuf/KML via QGIS/OGR, and Advanced WKT fallback, plus normalized polygon source models and an Advanced Toolbox polygon feature-source input without changing PBM, scientific processing, EPT subset behavior, external workers, or existing single-file/batch workflows.
- Phase 27C adds UI recovery refresh controls for Home, Dataset, Planning, Processing, and Results, plus EPT subset extraction through Mission Control Dataset and Advanced Toolbox Input / I/O with PBM job routing, strict read_lidar option validation, and QGIS-free regression tests without changing PBM installer behavior, scientific calculations, external workers, or existing LAS/LAZ/COPC workflows.
- Phase 27B records RC1 QA evidence for the current artifact, adds the RC1 QA results and blocker ledger, marks clean Windows/QGIS manual QA as the remaining RC1 gate, and preserves release focus without changing PBM, processing, scientific calculations, Advanced Toolbox, or External Worker behavior.
- Phase 27A starts formal release-candidate management by adding the release roadmap, RC1 checklist, RC1 manual QA script, release triage policy, documentation links, and release-doc regression coverage without adding features or changing processing, PBM, Advanced Toolbox, scientific calculations, or External Worker behavior.
- Phase 26C adds intelligent current-session awareness to Mission Control with one shared Project Summary model for dataset/workspace/output/backend/environment state, generated versus loaded product tracking, smarter Home/Workspace/Processing/Results summaries, and automatic stale-state clearing when the active dataset or run changes without adding persistence, PBM changes, processing changes, Advanced Toolbox changes, or external workers.
- Phase 26B unifies Mission Control interaction behavior: long-running page actions disable their controls, show immediate status/progress text, refresh dependent pages automatically, send native QGIS message-bar notifications, clear stale downstream state when datasets/results change, and expose a consistent processing lifecycle without changing PBM, processing algorithms, backend routing, Advanced Toolbox, or external workers.
- Phase 26A completes a product-readiness UX audit by adding QGIS-theme-first action icon intents with Qt fallbacks, tightening visible backend/status/progress wording, replacing PASS/FAIL-style UI prefixes with product status words, moving developer terminology behind advanced/troubleshooting language, and adding QGIS-free UX regression tests without changing PBM, processing, backend routing, Advanced Toolbox, external workers, or algorithms.
- Phase 25D makes Results > Load Outputs add current-run GeoTIFF and CSV outputs to QGIS with duplicate avoidance and existing product raster styling, compacts the Dataset summary into key facts plus content-sized technical metadata, and reduces fixed-height empty/list/detail panels across Mission Control without changing PBM, scientific calculations, backend routing, Advanced Toolbox, external workers, or algorithms.
- Phase 25C corrects Mission Control navigation to Home, Workspace, Dataset, Planning, Processing, Batch, Results, Scientific Advisor, Environment, Settings; keeps Batch and Scientific Advisor out of the default Continue path; adds a compact Home environment action; and adds subtle readiness markers beside existing readiness text without changing PBM, processing, backend routing, algorithms, external workers, or the Advanced Toolbox.
- Phase 25B turns Mission Control into a guided workflow with a compact Home overview, subtle completed/current/upcoming step indicators, one contextual Next Step card on each primary workflow page, and Continue navigation that moves users forward without changing PBM, processing, backend routing, scientific algorithms, external workers, or the Advanced Toolbox.
- Phase 25A refines Mission Control workflow polish with collapsed workspace reset controls, cleaner Dataset summary versus technical metadata, concise Advisor no-recommendation handling, Planning output override disclosure, Results buttons that stay inactive until outputs exist, hidden developer-only backend controls, and updated UX regression tests while leaving PBM, processing, scientific calculations, and the Advanced Toolbox unchanged.
- Phase 24F applies the PyForestScan Design System to Mission Control with shared spacing tokens, status badge wording and tones, button role styling, compact list/detail heights, calmer Backend controls, clearer Processing/Batch/Results hierarchy, a visual polish audit, and QGIS-free regression tests while leaving processing, PBM installer behavior, scientific calculations, and the Advanced Toolbox unchanged.
- Phase 24E adds the PyForestScan Design System as the plugin-wide visual and interaction language, records a UI audit with recommendations, and adds QGIS-free tests for design-system status labels, button roles, spacing tokens, expandable sections, primary actions, and empty states without changing PBM, scientific processing, or Advanced Toolbox behavior.
- Phase 24D standardizes Mission Control UX with a permanent design standard, primary-action terminology, hidden empty sections, collapsed technical/default detail, lighter Advisor/Workspace/Results pages, and QGIS-free UX regression tests while leaving PBM, processing algorithms, scientific calculations, and the Advanced Toolbox unchanged.

## 0.1.0-beta.2 - 2026-07-06

- PBM backend installation is enabled for Windows internal beta builds and installs into the user-local PyForestScan backend folder without modifying QGIS Python, system Python, PATH, shell profiles, or QGIS installation folders.
- PBM execution routing supports Dataset Explorer local inspection plus CHM, Canopy Cover, PAD, PAI, FHD, Rumple, DTM, Point Density, and Voxel Statistic when the managed backend is READY.
- Environment Check now reports execution readiness: PBM READY means overall READY for routed products, with QGIS Python scientific packages shown as optional fallback details rather than blocking failures.
- Mission Control beta UX is simplified into a compact dashboard, PBM-first Environment page, explicit Processing backend label, output-first Results page, and a three-step Batch flow with technical details collapsed by default.
- Remaining limitations: Linux/macOS PBM install execution remains planned/experimental, External Worker mode remains disabled, Height Above Ground point-cloud export and Preprocess Point Cloud still require QGIS Python integration, and clean-machine GUI smoke testing must be recorded before broader sharing.

- Phase 24B simplifies Mission Control for internal beta users: Home is a compact dashboard, Environment foregrounds PBM execution readiness with QGIS fallback details collapsed, Processing shows the active backend, Results exposes output-first actions, Batch reads as Discover / Preflight / Run, and developer-heavy PBM details stay under Advanced/Troubleshooting.
- Phase 24A prepares the internal beta release candidate by recording final ZIP SHA-256, release QA pass/pending fields, clean-machine tester checklist updates, and tag/release command preparation without creating a GitHub release.
- Phase 23N aligns Environment Check with PBM execution readiness: PBM READY now reports overall `READY`, makes QGIS Python scientific packages an optional fallback section, and prevents missing QGIS Python PyForestScan/PDAL from appearing as blocking failures when routed PBM processing is available.
- Phase 23M corrected the first PBM/QGIS Python readiness distinction and added PBM installation progress UX with a Qt worker, estimated staged progress, elapsed-time/current-action UI, hidden technical logs, disabled install/repair controls while running, and Windows no-console subprocess flags.
- Phase 23L completes the PyForestScan runtime dependency closure by adding `tqdm`, extending manifest/spec verification, setting backend-local `GDAL_DATA`, `PROJ_DATA`, and `PROJ_LIB` when conda data folders exist, and treating lingering GDAL/PROJ data messages as warnings when functionality passes.
- Phase 23K adds PyForestScan runtime dependencies to the PBM backend: scipy, pandas, Shapely, PyProj, Fiona, GeoPandas, and Matplotlib are installed from conda-forge before the PyPI-only PyForestScan package, and verification now smoke-imports PyForestScan public modules including calculate, filters, handlers, process, and visualize.
- Phase 23J fixes the remaining PBM rasterio compatibility blocker by preventing PyPI dependency resolution from replacing conda-forge geospatial binaries, tightening GDAL/rasterio/numpy environment ranges, adding deeper rasterio/GDAL/MemoryFile verification, and printing filtered conda package/build diagnostics for the geospatial stack.
- Phase 23I fixes PBM geospatial backend verification for conda-forge Windows layouts by adding explicit `libgdal` to backend specs, searching `env/Scripts`, `env/Library/bin`, `env/bin`, and `env` for executables, and prepending backend-local conda DLL/runtime paths for verification, pip install, and PBM runner subprocesses.
- Phase 23H improves PBM staged/final verification diagnostics with per-check command/executable/stdout/stderr details, actionable install failure summaries, a QGIS-free `scripts/pbm_backend_diagnostics.py` command, package/import mapping regression tests, and internal beta troubleshooting documentation.
- Phase 23G fixes PBM staged install promotion by verifying staged Micromamba/env/Python paths before promotion without requiring final config, promoting verified staged files to final backend paths, writing final backend config only after promotion, then running strict final verification before READY. Promotion now preserves previous active backend files in staging backup and restores them on failure.
- Phase 23F fixes clean-machine PBM installer isolation blockers: Environment Check now reports PBM status without crashing, PBM installer/verification/runner subprocesses use sanitized environments that remove QGIS Python/profile contamination, PyPI-only backend packages install through managed backend Python after conda environment creation, failed staging is cleaned for retry, and diagnostics record command kind/executable/clean-env policy without dumping secrets.
- Phase 23E adds no-manual-setup beta readiness documentation, routes Dataset Explorer local point-cloud inspection through PBM when READY, expands Environment Check with no-manual-setup scope, documents safety verification for QGIS/system/PATH immutability, and records remaining clean-machine smoke blockers honestly.
- Phase 23D routes CHM, Canopy Cover, PAD, PAI, FHD, Rumple, DTM, Point Density, and Voxel Statistic processing through the PBM backend when READY, adds the packaged backend runner protocol, controlled backend subprocess execution service, adapter auto/fallback execution modes, Environment Check selected-backend reporting, batch preflight PBM routing, safety checks that reject QGIS GUI executables, docs, and QGIS-free mocked tests. External Worker mode remains disabled.
- Phase 23C enables the PBM backend installer for Windows internal beta builds with user confirmation, optional-checksum handling when no pinned Micromamba checksum exists, safe archive extraction, active backend verification, Backend page progress/log messaging, PBM Environment Check reporting, and internal beta smoke-test documentation. Linux/macOS remain planned until tested, and processing routes that still use QGIS Python continue to say so.
- Phase 23B clean-machine ZIP install readiness documentation, dependency-state matrix, clearer missing-dependency guidance, Backend page release-readiness labels, and manual setup instructions.

## 0.1.0-beta.1 - 2026-07-02

Internal beta release target with versioned ZIP packaging, release manifest generation, release validation, release notes, and dry-run GitHub release preparation.

### Changed

- Matured repository documentation for internal release readiness with a professional README, master documentation index, scientific-method pages, current architecture/output docs, GitHub issue and PR templates, citation guidance, release audit report, and Markdown link checking.
- Audited and simplified the plugin for internal release readiness, including stale release-facing documentation cleanup, Settings page simplification, and clearer Batch run controls.
- Disabled unsafe External Worker batch mode in Mission Control and core guardrails after validation showed QGIS GUI Python could launch application windows; Parallel Safe mode now supports up to 6 workers with confirmation and stronger preflight recommendations.

### Added

- Phase 22D PBM production backend installation engine architecture with backend manifest, resumable download manager, transaction stages, rollback verification, repair planning, backend version manager, structured operation logs, future module registry, professional Settings backend controls, documentation, and QGIS-free tests. Public one-click installation remains disabled.

- Phase 22C PBM controlled installer prototype with Micromamba bootstrap policy, checksum/download helpers, environment spec files, developer-only install guard, staging/rollback mechanics, package spec inclusion, Settings experimental-install label, documentation, and QGIS-free mocked tests. Normal user installation remains disabled.

- Phase 22B PyForestScan Backend Manager dry-run install planning, registry-driven environment spec, Micromamba bootstrap plan placeholders, QGIS compatibility reporting, Settings page install preview, compatibility docs, and QGIS-free tests. Installation remains disabled and no downloads or environment changes occur.
- Phase 22A PyForestScan Backend Manager foundation with user-local backend path resolution, typed backend models, dependency registry, safe verification, service placeholders, Settings UI status, PBM documentation, and QGIS-free tests.
- Phase 20F parameter and language polish with clearer Processing help strings, unit-aware parameter labels, current plugin metadata, user-guide cleanup, audit artifact, and naming/metadata regression tests.
- Phase 20E full PyForestScan site rescrape, usage/examples audit, source/docs diff, Processing Toolbox reorganization, Diagnostics group, clean tool names, and hidden legacy guided toolbox entries.
- Phase 20D full PyForestScan documentation/source inventory, function parameter parity matrix, Advanced Toolbox map, deferred feature registry, grouped Advanced Toolbox labels, full SMRF filter controls, PointSourceId filtering, outlier `remove`, and HAG auto method mapping.
- Phase 20C exact Advanced Toolbox parameter parity with a parameter-by-parameter PyForestScan calculate matrix plus Advanced Point Density and Advanced Voxel Statistic algorithms.
- Phase 20B API coverage audit with Advanced DTM, Advanced Point Cloud Preprocess / Filters, expanded HAG read options, full PyForestScan coverage matrix, gap analysis, and parameter coverage docs.
- Advanced Processing Toolbox group with expert CHM, PAD, PAI, Canopy Cover, FHD, Rumple, and Height Above Ground/Normalize algorithms routed through adapter-backed request builders.
- Workspace Welcome and Resume UI with Continue Last Workspace, Start New Workspace, Recent Workspaces, workspace status, timeline viewer, notes editor, reset action, Home dashboard workspace state, and QGIS-free display helper tests.
- Local Workspace foundation with `.pyforestscan/` workspace folders, typed workspace/session/state/history/timeline/notes/version models, Mission Control session restore, and QGIS-free workspace tests.
- Internal release checklist, known limitations, manual QA script, product audit, and release-readiness regression tests.
- Experimental external worker research scaffold with worker job/result JSON files and subprocess entrypoint, retained behind disabled-by-default guardrails after unsafe QGIS GUI launcher behavior was found.
- Batch preflight and resume reliability with required preflight gating, disk-space checks, output conflict detection, READY environment validation, durable batch manifests, per-file job ids, checkpointed summaries after every file, skip-completed resume behavior, and retry-failed controls.
- Safe parallel batch execution framework with Sequential default, guarded Parallel safe mode, max worker validation, Qt worker-thread execution, per-file status updates, cancel/skip summaries, and QGIS-free executor tests.
- Batch Processing v2 UX with a streamlined Home dashboard, clearer batch file/result rows, pause-after-current-file, cancel-remaining, retry-failed-files, result filtering, opt-in QGIS output loading, and enhanced batch summaries.
- Batch Processing v1 with folder discovery, selectable files, sequential per-dataset execution, organized batch run folders, per-file failure recording, Mission Control Batch page, and JSON/CSV/HTML batch summaries.
- Processing Footprint summaries replaced misleading runtime prediction with selected products, raster dimensions, band counts, estimated output storage, and runtime caveats.
- Mission Control progressive disclosure UX with simplified Processing defaults, collapsed technical details, concise Scientific Advisor summaries, collapsed product explanations, and Processing Footprint output storage summaries.
- Mission Control full-window layout redesign with a 1400x900 default floating window, 1150x760 minimum size, bounded sidebar, full-page scroll regions, and grouped Planning controls.
- Scientific Advisor readability polish with a larger default Mission Control window, spacious card sections, wrapped recommendation rows, clearer warnings, and readable product explanation cards.
- Scientific Advisor Mission Control workflow with Knowledge Engine recommendations, product explanation cards, QGIS tool guidance, completed-product next steps, and UI support tests.
- Deterministic Knowledge Engine foundation with typed recommendation reports, configurable scientific thresholds, transparent calibration notes, QGIS tool suggestions, and unit tests.
- PAD default QGIS visualization as an RGB composite using bands 5/3/2, with safe fallback for shorter height-bin stacks.
- Raster auto-display stabilization with explicit QGIS raster statistics refresh, grayscale min/max contrast ranges, PAD band-1 naming, and display-range QA guidance.
- Full product workflow stabilization with floating Mission Control launch, lighter UI styling, grayscale raster defaults, friendly all-product result links, final HTML run summaries, and large dataset warnings.
- FHD and Rumple processing workflows with adapter-backed PyForestScan calls, Product Planner controls, pipeline execution, QGIS FHD raster loading, Rumple CSV summaries, tests, and manual QA documentation.
- PAD and PAI processing workflows with adapter-backed PyForestScan calls, Product Planner controls, pipeline execution, QGIS result loading, tests, and manual QA documentation.
- Dataset Footprint Preview in Mission Control with bounds-derived footprint summary, in-memory QGIS footprint layer creation, main canvas zoom, and plain-Python preview tests.
- Canopy Cover processing spike with adapter-backed PyForestScan canopy cover generation, planning controls, pipeline execution, QGIS result loading, tests, and manual QA guide.
- CHM production workflow stabilization with Mission Control parameters, stronger validation, job summary parameters, friendly CHM result links, best-effort QGIS raster polish, and QA documentation.
- CHM processing spike: adapter-backed PyForestScan CHM generation, CHM pipeline execution, Mission Control job launch, CHM result recording, and manual QGIS testing guide.
- Processing pipeline framework with validation-only registered product pipelines and Mission Control stage visualization.
- Mission Control run-folder workflow that automatically manages Dataset Explorer, Product Planner, and dry-run job files behind friendly result links.
- Dry-run job execution framework with typed job records, cancellable lifecycle, Mission Control Processing integration, Results job history, and JSON summaries.
- Mission Control manual QGIS validation record confirming dock, toolbar/menu, navigation, and placeholder behavior.
- Mission Control dock framework with Home, Environment, Dataset, Planning, Processing, Results, and Settings pages.
- Product Planner Processing workflow that reads Dataset Explorer JSON and writes JSON, CSV, and HTML product plan reports without scientific processing.
- Dataset Explorer Processing workflow with adapter-backed inspection, JSON/CSV/HTML reports, warnings, product feasibility, and CSV table loading.
- Adapter architecture audit documenting API alignment, non-QGIS core boundaries, and Phase 5 risks.
- PyForestScan adapter architecture with typed configuration, dataset validation, dataset inspection, structured logging, progress snapshots, and plugin-owned exceptions.
- Verified READY Windows/QGIS dependency baseline for PyForestScan API discovery.
- QGIS/OSGeo4W install-path mismatch troubleshooting for Windows dependency checks.
- Windows QGIS 3.44 dependency installation investigation and troubleshooting guide.
- Local QGIS plugin packaging and ZIP validation scripts.
- Manual QGIS local testing and packaging documentation.
- Environment Check Processing algorithm now produces a real PASS/FAIL/WARNING diagnostic report.
- Plain-Python dependency validation for QGIS Python, PyForestScan, PDAL, GDAL, rasterio, and numpy.
- Unit tests for dependency report creation, missing dependency handling, and report formatting.
- Initial project documentation foundation.
- Repository directory structure for the future QGIS Processing plugin.
- Architecture decision records for provider architecture, dependencies,
  repository structure, releases, testing, and user interface philosophy.

### Fixed

- Mission Control run folders now avoid overwriting previous runs by adding numeric suffixes when a timestamped folder already exists.
- Dataset Explorer Processing feedback now formats long CRS strings and numeric summaries more clearly after manual QGIS validation.
- `InspectionOptions.include_dimensions` is now honored by dataset inspection.


- Phase 27K: Fixed polygon transport so PBM materializes a real clipping vector file before PyForestScan execution, made EPT/COPC workload estimates conservative, added polygon progress stages, introduced a styled InfoBadge help registry, and documented real EPT validation steps.

## Phase 27M

- Added shared Batch execution and polygon finalization option models.
- Registered Standard Batch and Polygon outputs through a shared generated-output registry.
- Added exact polygon raster masking with backend rasterio and QGIS/GDAL service abstractions.
- Routed polygon output registration into Results so automatic and manual loading can find final masked rasters.
- Added Batch Advanced help topics for concurrency, output loading, conflict policy, and polygon mask controls.

## Phase 27N

- Added authoritative polygon repository identity and source-selection models.
- Routed native EPT preflight around generic catalog rediscovery so polygon shape cannot change repository kind.
- Added CRS-safe envelope comparisons, rejected-source diagnostics, execution-plan signatures, guided Polygon review, processing profiles, and spatial-preview actions.
- Removed operational use of implausible EPT root point estimates from guided preflight output.

- Phase 28B adds shared retained-interface state, automatic stale-safe Scientific Advisor refresh, and a service-backed Advanced Toolbox page with provider status and duplicate-safe refresh.

- Phase 28C compacts retained Mission Control pages, moves specialist controls behind progressive disclosure, adds concise Prerun/Results states, supports a 620 px dock minimum, and validates QGIS 3.44.9 offscreen layouts at 100% and 150% scaling.

## Phase 28F - Large-area processing stabilization

- Enforced existing-HAG execution and rectangular buffered reads.
- Added conservative memory estimates, pilot selection, durable coordinator contracts, atomic state, late-result adoption, and breaker reconstruction.
- Real EPT and full-job live validation remain pending.


## Phase 28G Exact Polygon Completion

- Phase 28G filters polygon CHM work by exact core intersection, adds explicit valid-NoData semantics, sparse aligned mosaicing, geometry-driven checkpoint recovery, shared HAG diagnostics, and durable progress aggregation.


## Phase 28H Adaptive Scale and Compact Workspace

- Phase 28H derives CHM work scale from workload and hardware, restores a one-unit small-request path, adds advisory performance history and pilot calibration contracts, isolates current jobs with strict tokens, and consolidates Mission Control into Process plus Tools & Setup.
# Phase 30B - Production Rumple and terminal recovery

- Added durable adaptive Rumple execution with shared CHM work, a global half-cell grid, one-cell halo ownership, sparse core mosaic, exact mask, and final-support scalar aggregation.
- Added semantic horizontal/vertical CRS comparison so EPSG:6635 and equivalent WKT do not produce false XY-reprojection warnings.
- Added authoritative processing UI states, finally-guarded terminal unlock, stale-state reconciliation, and durable recent-error records.
- Added explicit primary, secondary, and supporting output roles and separated QGIS visualization errors from scientific completion.
- Recorded redacted evidence from the real 130 ha EPT Rumple run and added a numeric output validation script.
# Phase 30D

- Repaired CHM and Rumple standalone execution for HAG-enabled LAS files with unknown CRS; warnings no longer become implicit blockers.
- Added product validation severity and actionable blocker reporting.
- Automated source scheduling with a default ceiling of five, forced current-job output loading, and removed global warning acknowledgement.
- Isolated new batch manifests, preserved requested products on failure, and excluded diagnostics from product output counts.
# Phase 30E

- Added evidence-driven CRS resolution, normalization, sidecars, exact QGIS datasource evidence, repository consensus, conflict detection, and persisted assignments.
- Enabled source-local CHM and Rumple for unknown-CRS LAS/LAZ/COPC with existing HAG, without fake EPSG metadata.
- Added explicit source/output CRS provenance tags and preserved automatic exact polygon transformation once CRS is known.

## Phase 31B - Spatial assignment and large-LAS completion

- Added typed metres, international-feet, and US-survey-feet assignments for files and coherent repositories without modifying source LiDAR.
- Added compact Process resolution controls, explicit **Use Project CRS**, and collapsed Tools & Setup assignment management.
- Added assignment persistence/precedence/conflict handling, source-local and assigned-CRS provenance, and non-destructive raster CRS registration.
- Added cached bounded classification evidence, spatial ground-strata quality reporting, canonical metre parameter conversion, and automatic plan rebuilding after assignment.

## Phase 31C - Non-blocking source-local fallback

- Added a centralized, configurable source-local unit policy with assumed metres as the default and explicit lower-confidence provenance.
- Changed eligible standalone CHM/Rumple missing-unit readiness from blocker to warning while preserving CRS requirements for polygon, reprojection, and cross-source alignment.
- Froze unit basis/authority/mode into PBM requests and checkpoint identities so prerun and execution agree and assumed/trusted preparations never collide.
- Added the fallback preference under collapsed LiDAR Spatial Reference tools without restoring global warning acknowledgement.
