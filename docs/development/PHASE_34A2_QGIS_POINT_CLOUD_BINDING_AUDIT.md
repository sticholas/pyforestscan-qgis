# Phase 34A2 QGIS point cloud binding audit

Actual local import/method probes, 2026-09-08. Run
`scripts/audit_point_cloud_bindings.py` using each QGIS Python launcher.
No source data, project or QGIS installation was changed.

| Runtime | Qt | PyQt | Python |
| --- | --- | --- | --- |
| QGIS 3.44.13-Solothurn | 5.15.13 | 5.15.11 | 3.12.13 |
| QGIS 4.0.0-Norrkoping | 6.8.1 | 6.10.2 | 3.12.13 |

Both runtimes returned the same native-method availability below.
AVAILABLE_IN_PYTHON means import/method presence, not live renderer qualification.

| Capability | Result | Observed boundary |
| --- | --- | --- |
| QgsPointCloudLayer | PARTIALLY_AVAILABLE | attributes, pointCount, setSubsetString present |
| Layer indexing | PARTIALLY_AVAILABLE | generateIndex absent on layer; provider-specific APIs not yet audited |
| Layer editing lifecycle | PARTIALLY_AVAILABLE | startEditing, rollBack present; changeAttributeValue absent |
| QgsPointCloudLayerRenderer | UNVERIFIED / absent in tested Python | Do not instantiate from Python |
| QgsPointCloudLayerEditUtils | CPP_ONLY | Absent in both; upstream documents no Python bindings |
| Attribute collection | AVAILABLE_IN_PYTHON | attributes, find present |
| RGB renderer | AVAILABLE_IN_PYTHON | red/green/blue attribute setters |
| Classified renderer | AVAILABLE_IN_PYTHON | setCategories |
| Attribute ramp renderer | AVAILABLE_IN_PYTHON | setAttribute |
| QgsPointCloudLayer3DRenderer | AVAILABLE_IN_PYTHON | layer/symbol, point budget, screen error setters |
| Qgs3DMapCanvas | PARTIALLY_AVAILABLE | mapSettings and cameraController present; setMapSettings absent |
| Qgs3DMapSettings | AVAILABLE_IN_PYTHON | setLayers, setCrs, setExtent |
| Camera controller | AVAILABLE_IN_PYTHON | cameraPose, setCameraPose, setLookingAtMapPoint |
| QgisInterface 3D view lifecycle | AVAILABLE_IN_PYTHON | createNewMapCanvas3D, closeMapCanvas3D |
| Layer elevation properties | AVAILABLE_IN_PYTHON | Class exists; operation-level qualification pending |
| Layer profile generator | UNVERIFIED / absent in tested Python | No direct generator binding found |
| Elevation profile canvas | AVAILABLE_IN_PYTHON | Class exists; operation-level qualification pending |

## Web runtime imports

QGIS 3.44 has a qgis.PyQt.QtWebEngineWidgets wrapper, but importing it fails:
`No module named 'PyQt5.QtWebEngineWidgets'`.
QGIS 4.0 fails with the analogous PyQt6 error. File presence or find_spec on
the wrapper therefore cannot authorize a web viewer.

QtWebKit imports in 3.44 only. It is absent in 4.0 and has not been qualified
for modern Potree/WebGL assets; it is not selected as a fallback.

## Integration consequence

Native configured 3D views can be created through the public QgisInterface.
They are QGIS-owned views initialized from project state. Do not transfer
their Qt ownership or invoke an unbound C++ canvas setter.

A linked native view is a possible first slice but differs from the requested
in-page viewport. The user has been asked whether this is acceptable.
Requiring in-page WebGL means resolving a supported managed viewer runtime
without installing packages into QGIS Python. Neither path is declared ready.

Primary references:
[QGIS interface](https://api.qgis.org/api/classQgisInterface.html),
[map settings](https://api.qgis.org/api/classQgs3DMapSettings.html),
[edit utilities](https://api.qgis.org/api/master/classQgsPointCloudLayerEditUtils.html).
Current upstream documentation can differ from these installed versions.

No interactive viewer, source-opening, selection or performance evidence has
been captured yet. Current Phase 34A2 state is VIEWER_ARCHITECTURE_ONLY.
