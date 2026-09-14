# PBM Future Modules

Phase 22D adds a declarative module registry so PBM can grow without hardwiring every future dependency into core installer logic.

Current placeholders:

| Module | Role | Status |
| --- | --- | --- |
| PDAL Module | Core point-cloud runtime and Python bindings | Declarative placeholder. |
| PyTorch Module | Future deep-learning workflows | Declarative placeholder. |
| SAM Module | Future segmentation/model inference workflows | Declarative placeholder. |
| WhiteboxTools Module | Future terrain and hydrology utilities | Declarative placeholder. |
| CloudCompare Module | Future point-cloud utility workflows | Declarative placeholder. |
| Potree Module | Future web point-cloud visualization outputs | Declarative placeholder. |

Each future module should describe dependencies, install routine, verification, repair, and update behavior. Optional modules must remain optional so users who only need core PyForestScan products do not inherit heavyweight stacks.

PBM core should load registered module behavior rather than requiring core changes for every new backend capability.
