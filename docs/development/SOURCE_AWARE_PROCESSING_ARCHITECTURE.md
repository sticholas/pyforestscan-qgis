# Source-aware processing architecture

```mermaid
flowchart LR
  A[Repository identity] --> B[Native source selection]
  B --> C[Global aligned raster grid]
  C --> D[Bounded work units]
  D --> E[HAG suitability and strategy]
  E --> F[PBM CHM core tiles]
  F --> G[Verified checkpoints]
  G --> H[Transactional mosaic]
  H --> I[Exact polygon mask]
  I --> J[Current-attempt registry]
```

Partitions are execution constructs. Existing LAS/LAZ files remain native sources and adjacent small files may be grouped. Large files may receive bounded subrequests. EPT remains one logical `ept.json`; work units are independent bounds requests and never hierarchy-node jobs. COPC uses footprints across files and bounded reads within unusually large files.

CHM is the only partition-enabled product in beta. It uses one grid, buffered reads, retained cores, deterministic first-valid core mosaicing, and final exact masking. Other products retain existing execution until their merge mathematics are reviewed.
