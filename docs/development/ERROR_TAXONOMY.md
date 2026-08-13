# Error Taxonomy

Terminal errors use: code, category, user message, technical context, retryability, recommended action, and diagnostic context. Categories are INPUT, REPOSITORY, CRS, COVERAGE, SCIENTIFIC, BACKEND, NETWORK, FILESYSTEM, RESOURCE, PROCESS, CANCELLED, RECOVERY, OUTPUT, and UNKNOWN.

`NO_COVERAGE` means no expected intersection. `FAILED_EMPTY_READ` means coverage was expected but points could not be read; these are scientifically distinct. Raw tracebacks remain diagnostic evidence and are never the only user explanation. `core/error_taxonomy.py` is the normalized catalog; unknown legacy codes remain readable as UNKNOWN for compatibility.
