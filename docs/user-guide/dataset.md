# Dataset Page

The Dataset page is the first required page in the single-dataset Mission Control workflow after backend readiness is checked.

Use it to:

- Select a LAS, LAZ, COPC, COPC LAZ, or EPT `ept.json` source.
- Choose the output folder for reports and products.
- Run Dataset Explorer.
- Review the compact Dataset Summary and optional Technical Metadata.
- Add or zoom to the dataset footprint when bounds are available.

## Refresh and Recovery

Use Refresh Dataset Page if the page looks stale after a failed inspection, cancelled workflow, or previously completed run. Refresh restores button states and page messaging from the current session. It does not delete outputs, reset PBM, or modify the backend.

Changing the selected dataset clears downstream planning, processing, and results state so the workflow cannot accidentally reuse stale outputs from a previous dataset.

## EPT Subset

When the selected source is an EPT `ept.json`, expand EPT Subset to extract a smaller LAS/LAZ point cloud before continuing.

The subset tool supports bounds, polygon crop, thinning, optional reprojection, and Height Above Ground read options. After extraction succeeds, choose Use Extracted Subset as Dataset to analyze the local LAS/LAZ subset with the normal Mission Control workflow.

Detailed parameter notes are in [EPT Subset Extraction](../scientific/ept-subset-extraction.md).
