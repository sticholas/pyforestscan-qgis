# Release Triage Policy

This policy defines how release candidate findings are classified. It applies to RC1, RC2, and v1.0 readiness decisions.

## Blocker

A blocker prevents candidate acceptance. The release cannot be tagged until it is fixed or the release scope is formally changed.

Examples:

- Plugin ZIP cannot install or plugin cannot load in supported QGIS.
- Mission Control cannot open.
- PBM install modifies QGIS Python, system Python, PATH, shell profiles, or requires admin rights.
- PBM install cannot complete on clean Windows/QGIS for the candidate artifact.
- Environment Check reports not ready after a verified PBM install.
- Routed Guided products fail on smoke sample data without clear recovery.
- External Worker mode becomes enabled in normal use.
- Release validation or package validation fails.

## Critical

Critical issues strongly affect usability or trust but may not block all candidate activity if a documented workaround exists. Critical issues must be fixed before v1.0 unless explicitly downgraded.

Examples:

- Backend repair guidance is unclear after a failed install.
- Results loading loads duplicates or applies clearly wrong styling.
- Batch reports misleading success/failure counts.
- Environment Check wording contradicts actual PBM readiness.
- Advanced Toolbox opens but a representative smoke test crashes QGIS.

## Important

Important issues should be fixed during the current RC cycle if time allows, but they do not automatically block RC1.

Examples:

- UI copy is confusing but not technically wrong.
- A non-default product setting needs clearer labeling.
- Documentation misses a minor workflow screenshot or example.
- Batch progress wording could be clearer.

## Nice-to-have

Nice-to-have issues improve polish but are not release-critical.

Examples:

- Minor spacing refinements.
- Additional screenshots.
- More concise wording in a secondary help section.
- Convenience links or report formatting improvements.

## Deferred

Deferred issues are intentionally outside the current release scope. They must be documented so they do not repeatedly re-enter RC triage.

Examples:

- Linux/macOS PBM production install support.
- QGIS 4.x certification before QGIS 4.x is testable.
- External Worker mode.
- Cross-computer session persistence.
- Mosaicking, cataloging, folder monitoring, polygon summaries, and public module marketplace features.

## Triage Rules

- When in doubt, classify higher, then downgrade only with evidence.
- Any crash, data-loss risk, installer safety violation, or false readiness claim starts as Blocker.
- Every Blocker and Critical issue needs owner, reproduction steps, expected behavior, actual behavior, candidate version, QGIS version, and artifact SHA-256.
- Deferred issues must link to the roadmap section that excludes them from the current candidate.
