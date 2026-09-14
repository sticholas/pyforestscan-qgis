# Current Job Isolation

`ActiveProcessingJobController` owns one `CurrentJobToken` per project/session foreground run. Tokens include project, session, logical job, attempt, plan signature, repository identity, polygon identity, and creation time.

Starting Process clears the current Results model and archives the previous terminal run. A second click while processing is blocked. Every tokenized Batch callback is accepted only when it matches the current token. Stale callbacks remain historical and cannot alter progress, Results, Advisor state, or automatic loading.

Automatic loading is fed only final output paths recorded on the current terminal token. Failed and historical jobs provide no eligible paths. Previous runs appear in a collapsed list and are never resumed implicitly. Durable historical recovery remains an explicit operation; a production “Make Current and Continue” UI is deferred until its coordinator handoff can be validated safely.
