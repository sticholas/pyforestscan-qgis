# Phase 31H One-Click Setup Matrix

| Initial state | One action | Required final result | Automated status |
|---|---|---|---|
| Missing engine | Set Up | Complete install, verify, Ready | Transaction/state tests |
| Healthy engine | Set Up/Recheck | Quick/full verify, Ready | Token reuse test |
| Missing handlers | Repair | Reinstall, full verify, Ready | Corruption detection automated; live reinstall pending |
| Stale manifest | Recheck/Process | Repair required before job | Fingerprint regression passes |
| Plugin/runner skew | Update/Repair | Compatible contract or not Ready | Contract hash/protocol tests |
| Second QGIS instance | Set Up | Busy lock, no corruption | Lock test; live refresh pending |

Clean installation downloads, no-console observation, and two-instance UI convergence remain Windows/QGIS manual checks.
