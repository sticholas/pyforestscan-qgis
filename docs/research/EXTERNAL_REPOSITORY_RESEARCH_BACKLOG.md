# External repository research backlog

No additional unnamed repository list was present in this phase attachment.
Only supplied named candidates are tracked; request the missing list before
claiming that broader audit is complete. All priorities are integration
priorities, not recommendations to install tools.

| Repository | Domain | Language | Relevant idea / decision | Cost / risk / priority |
| --- | --- | --- | --- | --- |
| [jq](https://github.com/jqlang/jq) | DATA_ENGINE | C | Structured diagnostics; reference only | Extra binary / parser input / low |
| [qsv](https://github.com/dathere/qsv) | DATA_ENGINE | Rust | Streaming tabular statistics; reference | Extra binary / input bounds / low |
| [Harlequin](https://github.com/tconbeer/harlequin) | UI/UX | Python | Metadata inspection UX; reference | Terminal stack / DB credentials / low |
| [SQLFluff](https://github.com/sqlfluff/sqlfluff) | DATA_ENGINE | Python | Expression feedback; not required | SQL-only / parser complexity / low |
| [yq](https://github.com/mikefarah/yq) | DATA_ENGINE | Go | Structured config transforms; reference | Extra binary / config integrity / low |
| [csvkit](https://github.com/wireservice/csvkit) | DATA_ENGINE | Python | Diagnostic CSV conventions; reference | Duplicate tooling / data size / low |
| [pgcli](https://github.com/dbcli/pgcli) | UI/UX | Python | Completion/history UX; reference | Database stack / credentials / low |
| [SQLGlot](https://github.com/tobymao/sqlglot) | DATA_ENGINE | Python | Validated expression AST; evaluate only if SQL needed | Parser dependency / injection boundaries / low |
| [Miller](https://github.com/johnkerl/miller) | DATA_ENGINE | Go | Streaming transforms; reference | Extra binary / input bounds / low |
| [VisiData](https://github.com/saulpw/visidata) | UI/UX | Python | Lazy table inspection; design reference | Terminal UI / plugin execution / low |
| [mycli](https://github.com/dbcli/mycli) | UI/UX | Python | Context completion; reference | Database stack / credentials / low |
| [Polars](https://github.com/pola-rs/polars) | PERFORMANCE | Rust/Python | Lazy columnar statistics; possible optional library | Native wheel / bounded-query validation / medium |

For every row: pinned maintenance assessment, exact license/transitive review
and useful-code approval remain PENDING; no source reused. Prefer existing
Python/engine facilities over shipping many command-line executables.
Point-cloud, GIS, VIEWER and AGENT/AI candidates are in the
[ecosystem review](PHASE_34A_POINT_CLOUD_EDITOR_ECOSYSTEM_REVIEW.md).
DOCUMENTATION, SECURITY_REFERENCE and NOT_RELEVANT categories are reserved
for the absent additional list, not populated with invented projects.
