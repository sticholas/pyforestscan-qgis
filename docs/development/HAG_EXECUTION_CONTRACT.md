# HAG Execution Contract

Phase 28F introduces HagExecutionDecision as the authoritative contract between the bounded suitability probe and CHM execution. It records the selected method, exact source dimension, evidence, reason, implementation version, timestamp, and deterministic method signature.

For existing_normalized_height, the probe must observe the exact HeightAboveGround dimension, finite values, meaningful nonzero values, and a nonconstant range. Execution calls read_lidar with hag=False and verifies the dimension remains available. A planned/executed mismatch blocks; there is no silent Delaunay fallback.
