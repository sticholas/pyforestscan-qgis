# Developer Guide

Developer documentation focuses on architecture boundaries, QGIS-free core logic, adapter-backed PyForestScan calls, tests, packaging, and release validation.

## Core Documents

- [Architecture](../ARCHITECTURE.md)
- [Adapter Design](../development/ADAPTER_DESIGN.md)
- [Processing Toolbox Expert Tools](../development/ADVANCED_PROCESSING_TOOLBOX.md)
- [Pipeline Framework](../development/PIPELINE_FRAMEWORK.md)
- [Job Execution](../development/JOB_EXECUTION.md)
- [Batch Processing](../development/BATCH_PROCESSING.md)
- [Workspace Architecture](../development/WORKSPACE_ARCHITECTURE.md)
- [Mission Control UX Standard](../development/MISSION_CONTROL_UX_STANDARD.md)
- [PyForestScan Design System](../development/PYFORESTSCAN_DESIGN_SYSTEM.md)
- [Testing Strategy](../TESTING_STRATEGY.md)
- [Manual QA Script](../development/MANUAL_QA_SCRIPT.md)

## Validation Commands

```bash
python3 -m unittest discover tests
python3 -m compileall pyforestscan_qgis
git diff --check
python3 scripts/package_plugin.py
python3 scripts/validate_plugin_package.py dist/pyforestscan_qgis.zip
```
