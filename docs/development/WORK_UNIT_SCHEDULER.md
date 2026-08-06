# Work-unit scheduler

`PolygonProductWorkScheduler` enforces one-to-four internal workers and a plan-derived lower limit. It persists checksum and plan signature after every completed core, retries transient failures, and does not retry deterministic geometry/HAG failures identically.

Pause stops new submissions while active units reach checkpoints. Cancel prevents new work and cancels queued futures. Resume verifies signatures/checksums and skips completed cores. Invalid checkpoints rerun. The outer Batch record remains one logical polygon job; External Worker mode stays disabled.
