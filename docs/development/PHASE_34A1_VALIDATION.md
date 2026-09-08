# Phase 34A1 validation

This is an intermediate contract milestone, not completed Phase 34A.

- Focused session/capability suite: 13 tests passed.
- Full protected unit suite: 1,028 run, seven skipped, no failures.
- Compileall: passed.
- Undefined-name gate: passed.
- Help lint: zero missing used topics, zero generic placeholders;
  37 unused registered topics remain informational.
- Local Markdown links: passed.
- Plugin ZIP validation: passed.
- Packaged import graph: passed.
- Release validator: passed for the intermediate 0.2.0-beta.1 artifact.
- Whitespace diff gate: passed.

First packaging invocation rejected a dirty worktree as designed.
Pre-commit validation used the existing --allow-dirty developer override.
An initial import-graph command omitted its required ZIP argument; corrected
invocation passed. Neither failure was a product regression.

Source-immutability tests use small arbitrary-byte LAS-named fixtures to test
identity/persistence, not LAS parsing or scientific export preservation.
No real edited cloud was exported. No viewer performance, screenshot,
massive-cloud, clean-profile or interactive editor claim is supported yet.

Release state ceiling: EXPERIMENTAL_VIEWER. More precisely, this milestone
contains contracts only and does not expose a viewer. Do not distribute it as
the requested 0.3.0-beta.1 drop. Continue with 34A2 and the gates in the
[architecture](POINT_CLOUD_EDITOR_ARCHITECTURE.md).
