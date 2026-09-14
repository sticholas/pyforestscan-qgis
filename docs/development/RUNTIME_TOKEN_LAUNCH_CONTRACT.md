# Runtime Token Launch Contract

Readiness discovery and launch validation are separate operations.

- **Discovery** answers whether an engine can be selected. Tools & Setup, Process, and Prerun may use it.
- **Launch validation** answers whether the runtime frozen by Prerun is still intact. It must not rediscover readiness.

The launch validator requires the executable and engine manifest, then compares engine ID, normalized executable, environment fingerprint, contract hash, runtime generation, runner hash, dependency-manifest hash, plugin-build ID, requested product-capability hash, protocol, and verification identity. A match authorizes launch with that token.

For multi-product polygon requests, the serialized backend job retains the complete Prerun product set in `runtime_products`. Each individual product worker validates the frozen token against that original set; dispatch must not narrow a combined token to the current worker's product and manufacture a capability mismatch.

Mismatch errors are precise: `ENGINE_RUNTIME_TOKEN_STALE`, `ENGINE_PLUGIN_BUILD_CHANGED`, `ENGINE_RUNNER_CHANGED`, `ENGINE_EXECUTABLE_MISSING`, `ENGINE_CONTRACT_CHANGED`, `ENGINE_DEPENDENCIES_CHANGED`, `ENGINE_PRODUCT_CAPABILITIES_CHANGED`, `ENGINE_PROTOCOL_CHANGED`, and related identity codes.
