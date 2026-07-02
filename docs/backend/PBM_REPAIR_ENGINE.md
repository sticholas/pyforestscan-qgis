# PBM Repair Engine

The Phase 22D repair engine plans repairs without executing them for normal users.

Repair planning detects:

- missing Micromamba executable
- missing managed Python
- missing or broken environment directory
- corrupt backend config
- corrupt or missing manifest
- package verification blocked by missing Python

Repair plans return proposed actions such as restoring Micromamba, recreating the environment, rewriting config after verification, or preserving bad config for diagnostics.

Actual repair execution beyond retry guidance remains planned. Windows internal beta users can inspect logs, preview repair guidance, and retry installation; update/remove policies remain future work.
