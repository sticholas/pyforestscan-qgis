# LiDAR Cache Architecture

## Contract

The cache is optional, immutable, local, disposable, and never modifies the original source. Its key includes source fingerprint, logical EPT identity, bounds, required dimensions, selected EPT resolution/level, CRS, HAG state/method, and scientific contract version.

Each entry uses write-to-staging, checksum, atomic promotion, metadata/provenance sidecar, and LRU quota eviction. Corruption is a cache miss. No cache state may be required to resume from source.

## Measured prototype

The exact 994,085-point bounded EPT array was repacked into contiguous X, Y, HeightAboveGround, and Classification fields. The immutable `.npy` entry is 20,875,977 bytes, wrote in 0.008 seconds, and reopened memory-mapped in 0.008 seconds. The source read took 0.709 seconds in the same warm environment.

This is promising for overlapping halos and restart reuse, but it is not production proof. The cache must retain every field required by the selected PyForestScan function and HAG route. A CHM cache key cannot be reused blindly for PAD, DTM, or preprocessing.

## Ordering

Morton ordering cut required-parent center travel by 49.6% in the current sparse job. Schedule neighboring read blocks together, but keep checkpoint identity and global raster placement unchanged. Hilbert ordering may be benchmarked later; Morton is simpler, deterministic, and sufficient for the first controlled experiment.

## Invalidations

Invalidate on source fingerprint, bounds, dimensions, resolution, CRS, HAG state, PyForestScan contract, or preparation-version change. Output-folder changes do not invalidate source cache entries.
