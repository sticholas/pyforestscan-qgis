# Documentation Index

Release-candidate productization: [Quick Start](getting-started/QUICK_START.md),
[feature matrix](RELEASE_CANDIDATE_FEATURE_MATRIX.md),
[Polygon UI audit](PHASE_32R_POLYGON_UI_AUDIT.md),
[release blockers](PHASE_32R_RELEASE_BLOCKERS.md), and
[market comparison](research/PHASE_32R_MARKET_COMPARISON.md).

Phase 32Q adaptive parallel EPT execution: [production baseline](PHASE_32Q_PRODUCTION_PERFORMANCE_BASELINE.md), [scheduler and progress design](PHASE_32Q_ADAPTIVE_EPT_EXECUTION.md), and [managed concurrency benchmark gate](PHASE_32Q_CONCURRENCY_BENCHMARK.md).

Phase 32P throughput and release evidence: [analysis](research/PHASE_32P_HIGH_THROUGHPUT_EPT.md), [measured block plan](research/PHASE_32P_BLOCK_PLAN.json), [production timing baseline](research/PHASE_32P_PRODUCTION_TIMING_BASELINE.json), and [exact release chain](releases/PHASE_32P_RELEASE_CHAIN.md).

Phase 32O sparse component-first EPT planning: [implementation and regression evidence](research/PHASE_32O_SPARSE_EPT_EXECUTION.md) and [machine-readable fixture benchmark](research/PHASE_32O_CURRENT_FIXTURE.json).

Phase 32N large-scale research: [architecture](research/LARGE_SCALE_LIDAR_ARCHITECTURE.md), [scientific authority](PYFORESTSCAN_SCIENTIFIC_AUTHORITY.md), [PyForestScan boundary](research/PYFORESTSCAN_BOUNDARY.md), [PDAL benchmark](research/PDAL_EPT_COPC_BENCHMARK.md), [cache design](research/LIDAR_CACHE_ARCHITECTURE.md), [scheduler comparison](research/DASK_RAY_SCHEDULER_COMPARISON.md), [AI survey](research/AI_MODEL_INTEGRATION_SURVEY.md), and [execution ADR](adr/ADR_LARGE_SCALE_EXECUTION_ENGINE.md).

Phase 32L projected-CRS parsing and polygon validation: [Projected CRS Validation](PHASE_32L_PROJECTED_CRS_VALIDATION.md).

Phase 32K bounded EPT assessment and scheduler restoration: [Bounded EPT Execution](PHASE_32K_BOUNDED_EPT_EXECUTION.md).

Phase 32J coordinator ownership and terminal-state evidence: [Coordinator Lifecycle](PHASE_32J_COORDINATOR_LIFECYCLE.md).

Polygon execution contracts: [progress](POLYGON_EXECUTION_PROGRESS_CONTRACT.md), [cancellation](POLYGON_CANCELLATION_CONTRACT.md), and [input preparation observability](POLYGON_INPUT_PREPARATION_OBSERVABILITY.md).

Rumple documentation: [user guide](user-guide/rumple-index.md), [method review](research/RUMPLE_RASTER_METHOD_REVIEW.md), [architecture](development/RUMPLE_RASTER_ARCHITECTURE.md), and [scientific equivalence](testing/RUMPLE_SCALAR_EQUIVALENCE.md).

For current engineering architecture, begin with the [Current Architecture Map](development/CURRENT_ARCHITECTURE_MAP.md). Phase reports are historical evidence, not competing specifications. Phase 29E validation records include the [lifecycle soak](testing/PHASE_29E_LIFECYCLE_SOAK_VALIDATION.md) and [clean-machine matrix](testing/PHASE_29E_CLEAN_MACHINE_MATRIX.md).

This documentation is organized for users, scientists, developers, maintainers, and release reviewers.

Supported and unqualified QGIS/platform combinations are listed in the
[Compatibility Matrix](COMPATIBILITY.md).

## Getting Started

- [Getting Started Overview](getting-started/README.md)
- [Quick Start](getting-started/QUICK_START.md)
- [Installation Strategy](INSTALLATION_STRATEGY.md)
- [Windows QGIS Dependencies](development/WINDOWS_QGIS_DEPENDENCIES.md)
- [QGIS Local Testing](development/QGIS_LOCAL_TESTING.md)

## User Documentation

- [User Guide](user-guide/README.md)
- [Dataset Page](user-guide/dataset.md)
- [Polygon Folder Processing](user-guide/polygon-folder-processing.md)
- [Mission Control](ui/MISSION_CONTROL.md)
- [Screen Flow](ui/SCREEN_FLOW.md)
- [Run Folder Workflow](ui/USER_WORKFLOW.md)
- [Known Limitations](KNOWN_LIMITATIONS.md)

## Scientific Methods

- [Scientific Methods Index](scientific-methods/README.md)
- [EPT Subset Extraction](scientific/ept-subset-extraction.md)
- [PAD Scientific Output](scientific/PAD.md)
- [Rumple Scientific Output](scientific/RUMPLE.md)
- [Localized Rumple Extension](scientific/localized-rumple.md)
- [Canopy Height Model](scientific-methods/CHM.md)
- [Plant Area Density](scientific-methods/PAD.md)
- [Plant Area Index](scientific-methods/PAI.md)
- [Canopy Cover](scientific-methods/CANOPY_COVER.md)
- [Foliage Height Diversity](scientific-methods/FHD.md)
- [Rumple Index](scientific-methods/RUMPLE.md)
- [Point Density](scientific-methods/POINT_DENSITY.md)
- [Voxel Statistic](scientific-methods/VOXEL_STATISTIC.md)
- [Digital Terrain Model](scientific-methods/DTM.md)
- [Height Above Ground](scientific-methods/HEIGHT_ABOVE_GROUND.md)
- [Scientific Advisor](knowledge/SCIENTIFIC_ADVISOR.md)

## Architecture

- [Architecture Overview](architecture/README.md)
- [Current Architecture](ARCHITECTURE.md)
- [Architecture Decision Records](adr/README.md)
- [Dependency Strategy](DEPENDENCY_STRATEGY.md)
- [Output Products](OUTPUT_PRODUCTS.md)

## Developer Documentation

- [Developer Guide](developer/README.md)
- [Processing Toolbox Expert Tools](development/ADVANCED_PROCESSING_TOOLBOX.md)
- [Polygon LiDAR Processing Architecture](development/POLYGON_LIDAR_PROCESSING_ARCHITECTURE.md)
- [Adapter Design](development/ADAPTER_DESIGN.md)
- [Pipeline Framework](development/PIPELINE_FRAMEWORK.md)
- [Job Execution](development/JOB_EXECUTION.md)
- [Batch Processing](development/BATCH_PROCESSING.md)
- [Workspace Architecture](development/WORKSPACE_ARCHITECTURE.md)
- [Spatial Assignment Architecture](development/SPATIAL_ASSIGNMENT_ARCHITECTURE.md)
- [Trusted Source Units](development/TRUSTED_SOURCE_UNITS.md)
- [Source-Local Fallback Policy](development/SOURCE_LOCAL_FALLBACK_POLICY.md)
- [Repository Spatial Assignments](development/REPOSITORY_SPATIAL_ASSIGNMENTS.md)
- [Phase 31B Spatial Assignment Matrix](testing/PHASE_31B_SPATIAL_ASSIGNMENT_MATRIX.md)
- [Phase 31B Large LAS Completion](testing/PHASE_31B_LARGE_LAS_COMPLETION.md)
- [Phase 31C Unreferenced LiDAR Matrix](testing/PHASE_31C_UNREFERENCED_LIDAR_MATRIX.md)
- [Phase 31C Large LAS Completion](testing/PHASE_31C_LARGE_LAS_COMPLETION.md)
- [QGIS Compatibility Layer](development/QGIS_COMPATIBILITY_LAYER.md)
- [Phase 32X Scientific UX and Portability Audit](development/PHASE_32X_SCIENTIFIC_UX_AND_PORTABILITY.md)
- [Phase 32Y Release Hardening](development/PHASE_32Y_RELEASE_HARDENING.md)
- [Phase 32Z Scientific Grouping and Compatibility](development/PHASE_32Z_SCIENTIFIC_GROUPING_AND_COMPATIBILITY.md)
- [Mission Control UX Standard](development/MISSION_CONTROL_UX_STANDARD.md)
- [Phase 28A Productization UX Audit](development/PHASE_28A_PRODUCTIZATION_UX_AUDIT.md)
- [PyForestScan Design System](development/PYFORESTSCAN_DESIGN_SYSTEM.md)
- [Testing Strategy](TESTING_STRATEGY.md)
- [Phase 28A Hotfix QGIS Validation](testing/PHASE_28A_HOTFIX_QGIS_VALIDATION.md)

## Backend Manager

- [PBM Architecture](backend/PBM_ARCHITECTURE.md)
- [PBM Install Plan](backend/PBM_INSTALL_PLAN.md)
- [PBM Transaction Model](backend/PBM_TRANSACTION_MODEL.md)
- [PBM Manifest](backend/PBM_MANIFEST.md)
- [PBM Download Manager](backend/PBM_DOWNLOAD_MANAGER.md)
- [PBM Versioning](backend/PBM_VERSIONING.md)
- [PBM Repair Engine](backend/PBM_REPAIR_ENGINE.md)
- [PBM Logging](backend/PBM_LOGGING.md)
- [PBM Micromamba Bootstrap](backend/PBM_MICROMAMBA_BOOTSTRAP.md)
- [PBM Installer Safety](backend/PBM_INSTALLER_SAFETY.md)
- [PBM Rollback](backend/PBM_ROLLBACK.md)
- [PBM Internal Beta Troubleshooting](backend/PBM_INTERNAL_BETA_TROUBLESHOOTING.md)
- [PBM QGIS Compatibility](backend/PBM_QGIS_COMPATIBILITY.md)
- [PBM Environment Spec](backend/PBM_ENVIRONMENT_SPEC.md)
- [PBM State Machine](backend/PBM_STATE_MACHINE.md)
- [PBM Dependency Registry](backend/PBM_DEPENDENCY_REGISTRY.md)
- [PBM Installation Workflow](backend/PBM_INSTALLATION_WORKFLOW.md)
- [PBM Processing Execution](backend/PBM_PROCESSING_EXECUTION.md)
- [PBM Runner Protocol](backend/PBM_RUNNER_PROTOCOL.md)
- [PBM Implementation Plan](backend/PBM_IMPLEMENTATION_PLAN.md)
- [PBM Future Modules](backend/PBM_FUTURE_MODULES.md)

## PyForestScan API Audits

- [API Audit Index](api/README.md)
- [Full API Surface](api/PYFORESTSCAN_FULL_API_SURFACE.md)
- [Function Parameter Parity](api/PYFORESTSCAN_FUNCTION_PARAMETER_PARITY.md)
- [Deferred Features](api/PYFORESTSCAN_DEFERRED_FEATURES.md)

## Releases

- [Release Documentation](releases/README.md)
- [Release Roadmap](releases/RELEASE_ROADMAP.md)
- [RC1 Checklist](releases/RC1_CHECKLIST.md)
- [RC1 Manual QA Script](releases/RC1_MANUAL_QA_SCRIPT.md)
- [RC1 QA Results](releases/RC1_QA_RESULTS.md)
- [RC1 Blockers](releases/RC1_BLOCKERS.md)
- [Release Triage Policy](releases/RELEASE_TRIAGE_POLICY.md)
- [Internal Release Checklist](releases/INTERNAL_RELEASE_CHECKLIST.md)
- [PBM Internal Beta Smoke Test](releases/PBM_INTERNAL_BETA_SMOKE_TEST.md)
- [No-Manual-Setup Beta Smoke Test](releases/NO_MANUAL_SETUP_BETA_SMOKE_TEST.md)
- [Real EPT CRS Alignment Validation](testing/REAL_EPT_CRS_ALIGNMENT_VALIDATION.md)
- [Packaging](releases/PACKAGING.md)
- [Release Notes Template](releases/RELEASE_NOTES_TEMPLATE.md)
- [v0.1.0-beta.2 Release Notes](releases/v0.1.0-beta.2.md)
- [v0.1.0-beta.1 Release Notes](releases/v0.1.0-beta.1.md)
- [Clean Machine ZIP Smoke Test](releases/CLEAN_MACHINE_SMOKE_TEST.md)
- [Dependency State Matrix](releases/DEPENDENCY_STATE_MATRIX.md)
- [Manual QA Script](development/MANUAL_QA_SCRIPT.md)

## Archive

- [Phase History Archive](archive/phase-history/README.md)

## Repository Governance

- [Contributing](../CONTRIBUTING.md)
- [Security](../SECURITY.md)
- [Code of Conduct](../CODE_OF_CONDUCT.md)
- [Citation](../CITATION.cff)
- [Adaptive LiDAR Indexing](development/ADAPTIVE_LIDAR_INDEXING.md)
- [EPT Repository Handling](development/EPT_REPOSITORY_HANDLING.md)
- [EPT CRS Resolution](development/EPT_CRS_RESOLUTION.md)
- [Contextual Help System](development/CONTEXTUAL_HELP_SYSTEM.md)
