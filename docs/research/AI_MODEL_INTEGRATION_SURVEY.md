# AI Model Integration Survey

No surveyed model accelerates official PyForestScan CHM/PAD/PAI/FHD calculations by itself. AI products require separate provenance, model/version/checkpoint, inputs, tiling, confidence, and QA.

| Technology | Class | Input/output | GPU and tiling | Relevant role |
|---|---|---|---|---|
| SAM 2 | IMAGE_SEGMENTATION | Images/video -> prompted masks | CUDA strongly useful; image/frame tiles | Optional imagery masks and QA, not CHM acceleration |
| DINOv3 | IMAGE_FEATURES | RGB/satellite images -> dense features | PyTorch; CUDA recommended; patch tiles | Optional imagery embeddings/classification |
| DeepForest | TREE_DETECTION | Aerial imagery -> tree boxes/crowns | GPU useful; image tiles | Optional crown product/QA |
| StarDist | NOT_RELEVANT_TO_CORE_ACCELERATION | Microscopy images/volumes -> star-convex instances | TensorFlow; 2D/3D patches | Domain mismatch for airborne forest structure |
| Point Transformer V3 / Pointcept | POINT_CLOUD_SEGMENTATION | Labeled point samples -> per-point classes | Multi-GPU research stack; spatial chunks | Optional classification product after forestry training |
| RandLA-Net / Open3D-ML | POINT_CLOUD_SEGMENTATION | Point clouds -> semantic classes | GPU preferred; sampled chunks/cache | Optional classification prototype |
| MinkowskiEngine | SPARSE_3D_INFRASTRUCTURE | Sparse tensors -> learned 3D features/classes | CUDA/compiler-heavy; sparse chunks | Infrastructure for future models, not a metric |

Primary references: [SAM 2](https://github.com/facebookresearch/sam2), [DINOv3](https://github.com/facebookresearch/dinov3), [DeepForest](https://deepforest.readthedocs.io/en/stable/), [StarDist](https://github.com/stardist/stardist), [Pointcept](https://github.com/Pointcept/Pointcept), [RandLA-Net](https://randla-net.cs.ox.ac.uk/), [Open3D-ML](https://github.com/isl-org/Open3D-ML), and [MinkowskiEngine](https://github.com/NVIDIA/MinkowskiEngine).

## Product boundary

Official structural output records `scientific_source = pyforestscan`. Imagery AI and point-classification outputs record `derived_source = ai`, model family, exact checkpoint, training-domain statement, input imagery/point fingerprint, tile/overlap policy, hardware, and confidence/QA. AI may assist QA or produce optional layers; it must not alter official metrics invisibly.
