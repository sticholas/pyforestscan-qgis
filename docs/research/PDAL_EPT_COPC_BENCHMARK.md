# PDAL EPT and COPC Benchmark

## Official capabilities

PDAL documents `readers.ept` as streamable and spatially accelerated. It supports bounds, polygon selection, resolution, origin, addons, and request concurrency. Omitting bounds can select an entire enormous dataset. See [readers.ept](https://pdal.io/en/stable/stages/readers.ept.html) and the [bounded EPT tutorial](https://pdal.io/en/stable/tutorial/iowa-entwine.html).

## Exact-source benchmark

Source: the current EPSG:6635 UNC EPT. Bounds: one existing 200 m buffered child read. Points: 994,085.

| Route | Wall time | Result |
|---|---:|---|
| Existing plugin child | 3.719 s | Read + unchanged PyForestScan CHM + two TIFFs + checkpoint |
| Direct bounded `readers.ept` | 0.709 s | Full 23-dimension array |
| Streaming `readers.ept -> writers.null` | 0.583 s | 994,085 points |
| Reader `dimensions` option | 0.003 s | Rejected: unexpected argument |

The direct reader and plugin timings are not equivalent workloads. They show that read/decode is a minority of this warm child’s end-to-end time and that PDAL streaming is available. They do not justify removing dimensions: the installed reader rejects that option, and PyForestScan/HAG requirements govern legality.

## Persistent process evidence

Five fresh managed-Python imports of NumPy, PDAL, and PyForestScan took 1.052-1.128 seconds, median 1.082 seconds. One persistent process pays about 0.990 seconds once. Startup is therefore meaningful beside a 3.719-second child, but persistent workers need bounded task counts and recycling because native-state isolation has prevented QGIS crashes.

## COPC decision

COPC remains an optional disposable acceleration derivative, never a replacement source. Before official use it must preserve X/Y/Z, Classification, HeightAboveGround, RGB, Intensity, return fields, CRS, scale/offset, and applicable point counts. PDAL warns that metadata forwarding from EPT is not automatic; writer metadata must be explicit. No COPC conversion benchmark was run against the active 110-billion-point source, and COPC is not promoted in this phase.
