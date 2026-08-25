# Rumple CHM Dependency

Rumple depends on a CHM with matching repository, CRS, resolution, HAG, interpolation, bounds/polygon, and current adapter session. The adapter cache key includes scientific request parameters and never crosses process/session history.

Rumple-only requests generate one internal CHM and publish only the Rumple raster plus summary. CHM + Rumple in one adapter session reuses the compatible CHM. The supporting CHM is not registered as a final output unless CHM was explicitly requested. Interpolation settings are identical to the corresponding CHM request and materially affect Rumple by changing gaps and surface roughness.
