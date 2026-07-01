# PBM Future Modules

PBM is designed to grow beyond the first PyForestScan dependency stack. Future modules should be added as registry entries and implemented behind clear service boundaries.

## Candidate Modules

| Module | Potential Use | Status |
| --- | --- | --- |
| WhiteboxTools | Terrain and hydrology utilities | Registry placeholder only. |
| Open3D | Point-cloud visualization or analysis | Registry placeholder only. |
| PyTorch | Deep-learning workflows | Registry placeholder only. |
| ONNX Runtime | Model inference | Registry placeholder only. |
| Segment Anything | Imagery segmentation experiments | Registry placeholder only. |
| CloudCompare CLI | Point-cloud utility workflows | Registry placeholder only. |
| Entwine | EPT generation | Registry placeholder only. |
| Potree Converter | Web point-cloud visualization outputs | Registry placeholder only. |

## Rules For Future Modules

- Add dependencies to the registry before adding UI.
- Keep optional modules optional.
- Document scientific and operational reasons for each module.
- Do not force heavyweight ML or visualization stacks onto users who only need core PyForestScan products.
- Keep module-specific verification transparent and testable.
