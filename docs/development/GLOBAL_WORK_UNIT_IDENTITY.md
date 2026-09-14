# Global Work Unit Identity

Every source-aware work unit now uses `wu-<source-hash>-<sequence>`. The source hash is deterministic from normalized source paths, and the sequence is stable inside that source partition.

This replaces IDs such as `wu-0001` that restarted for each large source. Those repeated IDs could overwrite checkpoint JSON, output folders, retry state, progress ownership, and mosaic inputs.

The IDs are filesystem-safe on Windows, globally unique within a plan, included in the plan signature, and stable across recovery. Execution-manifest validation rejects duplicate work-unit IDs before Process starts.
