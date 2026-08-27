# Authoritative Processing Engine State

Phase 31I extends this ownership through launch: Prerun freezes the published token and [Runtime Token Handoff](RUNTIME_TOKEN_HANDOFF.md) carries it into the coordinator. Launch never resolves a replacement engine.

Phase 31H defines `ProcessingEngineService` as the sole execution-critical readiness owner. `BackendService` returns one shared service per resolved engine root. Legacy backend detection and verification remain diagnostic inputs only; they cannot publish execution readiness.

## State

`ProcessingEngineStateModel` records status, engine ID, executable, environment fingerprint, contract hash, protocol, runner hash, plugin build ID, product capability hash, dependency manifest hash, verification timestamp, failure code/message, readiness, and the verified runtime token.

Normal statuses are uninitialized, setup required, setting up/checking, ready, repair required, incompatible/update required, and failed. `ready_for_processing` is derived only from a successful authoritative contract report.

## Persistence

`processing_engine.json` is the readiness manifest. It is written atomically after full verification. `backend.json` remains installation/configuration metadata and cannot override engine state. Critical package sentinels, including `pyforestscan/handlers.py`, participate in the lightweight environment fingerprint.

## Publication

The service publishes each transition to subscribers. Mission Control projects the object-valued `processingEngineStateChanged` event into Tools & Setup, Process, Environment, Home, and the compact status strip. Display-only legacy environment/backend strings do not decide launch eligibility.

## Launch

Process asks the shared service for a product-scoped token. Execution consumes that token or derives it from the same published READY manifest. It does not construct an independent verifier. Material environment drift transitions the same state to repair required before a job/coordinator is created.
