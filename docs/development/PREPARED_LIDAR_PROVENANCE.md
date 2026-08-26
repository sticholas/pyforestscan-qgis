# Prepared LiDAR Provenance

Every durable checkpoint records source path/fingerprint, original dimensions and CRS state, units, classification assessment, ground/HAG methods, DTM, SMRF parameters, software contract, output dimensions, warnings, timestamp, job identity, recommendations, and preparation signature.

Reuse requires both `prepared_hag.laz` and an atomic completion marker with the exact signature. The signature includes source identity, spatial mode, units, preparation method, DTM, parameters, and implementation version. Filename equality alone never authorizes reuse.

Product metrics point to provenance. GeoTIFF metadata records HAG and ground source, whether preparation ran, and the signature.

