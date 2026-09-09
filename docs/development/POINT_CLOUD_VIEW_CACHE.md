# Point cloud view cache contract

Implemented in Phase 34A3.2/34A3.3. See the authoritative
[stability contract](POINT_CLOUD_VIEWER_STABILITY_CONTRACT.md) and
[measured cache/profile evidence](../testing/PHASE_34A3_2_DENSE_VIEW_PIPELINE_PROFILE.md).

Use application-managed cache outside source directories, keyed by verified
source identity plus converter/version/options. Cache data is rebuildable,
never authoritative science or edit storage. States: VALID, STALE,
REBUILDABLE, PURGEABLE. Check free space before conversion; write staging
then atomically publish validated cache metadata. Cancellation removes only
owned temporary outputs, never source data or sessions.

COPC/EPT should stream existing hierarchies. Large unindexed LAS/LAZ requires
a background managed viewing representation. Do not allow a provider to
silently create source-adjacent indexes. Cache eviction must not delete
journal/session records or files currently used by a renderer.
