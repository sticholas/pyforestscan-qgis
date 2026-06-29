# Scientific Advisor

Phase 16B makes the deterministic Knowledge Engine visible in Mission Control as
the Scientific Advisor page. The Advisor is not an AI system and does not use an
LLM. It renders transparent, rule-based guidance from Dataset Explorer facts.

## User Workflow

1. Open Mission Control.
2. Run Environment and confirm the runtime is ready.
3. Run Dataset Explorer on one lidar dataset.
4. Open Scientific Advisor.
5. Review dataset score, confidence, warnings, recommended products, suggested
   parameters, scientific notes, QGIS tool suggestions, and product explanation
   cards.
6. Build a Product Plan. Practical Advisor parameter recommendations, such as
   CHM grid resolution, are adopted into the Planning page when available.
7. Run processing.
8. Return to Scientific Advisor for completed-product next steps.

## What The Advisor Displays

The Advisor is grouped around progressive disclosure rather than one dense text
block. The first visible card is an executive summary with dataset readiness,
best product to consider, key warning, and suggested next action. Longer
scientific rationale, QGIS tool instructions, and product explanations remain
available in collapsed detail sections.

- Dataset quality score from deterministic warning/error severity.
- Confidence/readiness from metadata completeness.
- Key warnings, each with a reason and suggested action.
- Recommended products from Dataset Explorer feasibility.
- Recommended parameters from configurable Knowledge Engine thresholds.
- Scientific notes, including calibration caveats.
- Suggested next actions.
- QGIS tool suggestions.
- Product explanation cards for CHM, Canopy Cover, PAD, PAI, FHD, and Rumple.

## Product Cards

Product cards are rendered as individual readable cards with wrapped text inside
a collapsed Product Explanations section. Each card explains:

- what the product measures
- when to use it
- when to be cautious
- how to inspect it in QGIS

These explanations are guidance, not substitutes for project-specific scientific
validation.

## QGIS Tool Actions

The Advisor recommends existing QGIS capabilities instead of rebuilding them:

- Processing Toolbox
- Layer Styling / Symbology
- Raster Histogram
- Raster Calculator
- Elevation Profile
- 3D View
- Layout Manager

Buttons are provided where safe:

- Open Processing Toolbox: uses `iface.openProcessingToolbox()` when available;
  otherwise the Advisor shows menu instructions.
- Open Layer Styling: opens selected-layer properties when QGIS exposes a stable
  hook; otherwise the Advisor shows instructions.
- Zoom to Selected Layer: zooms the main map canvas to the selected layer when
  possible; otherwise it shows instructions.
- Open Output Folder: opens the active run `outputs/` directory after Dataset
  Explorer creates a run context.

## Scientific Boundaries

The Advisor keeps deterministic recommendations in `core/knowledge` and QGIS UI
actions in `ui/`. It does not modify PyForestScan calculations, add products, run
batch workflows, create project files, or use machine learning.

Threshold-based recommendations remain configurable and documented. If a
threshold is uncertain, the Advisor displays calibration requirements rather than
presenting the value as universal scientific truth.
