# Large-area EPT processing

EPT planning keeps `ept.json` as one indexed source. Large polygon envelopes become aligned logical windows; each supplies a bounded EPT request, writes a CHM core, checkpoints it, and releases backend process memory.

The 7,061.6 ha regression envelope (`10,990 m x 6,668 m` at `1 m`) plans a `10,990 x 6,668` grid with 73,281,320 cells and 77 nominal 1 km work units. Network concurrency is at most two. No physical point-cloud tiles or EPT node jobs are created.

Final success requires every core, transactional mosaic creation, and exact masking. Incomplete mosaics are not registered.
