# Point cloud editor architecture

## Implemented foundation

`core/point_cloud/session.py` is QGIS-free. It supplies immutable local-file
fingerprints, full-resolution original-source box selections, validated
classification/noise operations, journal undo/redo and atomic JSON persistence.
It neither reads scientific point arrays nor changes source data.

`core/point_cloud/capabilities.py` probes actual Python methods without
importing QGIS at module load. Native edit capability does not grant permission
to commit to the source.

## Next integration boundary

Point Cloud UI -> viewer adapter -> bounded view representation.
Point Cloud UI -> session -> managed selection/export worker -> NEW output.
Completed, validated output -> explicit Process input request.

Never reach into BatchPage to manipulate a running job. Never reuse a renderer
sample as an export selection. No engine, scientific-product or installer
behavior has changed in this milestone.

Renderer selection is still gated: the installed QGIS 3.44.13 Python probe
exposes neither canvas `setMapSettings` nor layer `changeAttributeValue`.
The public interface-created native 3D canvas must be evaluated without
unsafe Qt ownership transfer. A web renderer would require a separately
audited packaging/runtime route; no WebEngine dependency is currently added.

## Qualification gates

The 20 user-visible Phase 34A capabilities remain pending, including the new
navigation destination. No viewer/editor beta readiness is claimed.
Before 34A2: protect all eight products, folder/polygon inputs, adaptive EPT,
pause/cancel/recovery, DTM repair, outputs/history, Setup and engine readiness.

Tier 0: `python3 -m unittest discover -s tests -p test_point_cloud_session.py`.
Tier 1: all future `test_point_cloud_*.py` suites.
Tier 2: existing Process/engine/phase regression suites, unchanged.
Tier 3: package, import graph, undefined names, help and release validation.
Tier 4: full `python3 -m unittest discover tests` before every milestone
commit, plus live release QA before a beta readiness claim.

No mandatory AI dependencies. Future assist results must remain suggestions
until explicit journal acceptance. The assist-provider interface is not yet
implemented.
