# Documentation Index

This documentation is organized for users, scientists, developers, maintainers, and release reviewers.

## Getting Started

- [Getting Started Overview](getting-started/README.md)
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
- [QGIS Compatibility Layer](development/QGIS_COMPATIBILITY_LAYER.md)
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
