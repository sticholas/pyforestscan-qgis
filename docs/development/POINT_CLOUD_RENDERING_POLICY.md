# Point cloud rendering policy

Design contract, renderer implementation and measurements pending.

Bound points, resident nodes and prefetch using available memory, observed
frame time and camera motion. Reduce budget during navigation/pressure and
refine after settling. Unknown GPU capacity must remain unknown, not a
fabricated measurement. Indexing and decoding must not block QGIS.

Targets, not results: useful small-cloud view near two seconds, indexed
view near five seconds, navigation at least 30 FPS where hardware permits.
Record hardware, source size/count, storage/network, first-view latency,
FPS, peak RAM, cache size and selected-point resolution time.

Require >100M-point and genuinely massive indexed-source trials before
large-cloud readiness. No such viewer trial has occurred in 34A1.
