# Phase 31E Overlap Truth Table

| Raw overlap | Spatial evidence | Policy | Alignment | Selected |
|---|---|---|---|---|
| Yes | trusted matching CRS | any | Verified | Yes |
| Yes | unknown CRS, strong compatibility | Automatic | Assumed | Yes |
| Yes | unknown CRS | Require explicit CRS | Blocked | No |
| No | unknown CRS | Automatic | Blocked | No |
| Not evaluated | unreadable bounds | any | Blocked | No |
| Either | authoritative conflict | any | Blocked | No |
| Transformed overlap | differing authoritative CRSs | any | Verified after transform | Yes |

`Overlap: No` is reserved for evaluated geometric non-overlap. Refusal or inability to compare is reported as blocked/not evaluated.
