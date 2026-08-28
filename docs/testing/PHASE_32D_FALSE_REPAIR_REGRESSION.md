# Phase 32D False Repair Regression

The regression reproduces the real contradiction: UI Ready, Prerun Ready, a frozen PAI/FHD token, and all launch fields matching. The test replaces discovery with a failure sentinel; launch must still validate and proceed. Any call to discovery, regenerated token, or old generic repair result fails the contract.

Negative coverage verifies missing executable, plugin-build mismatch, and stale generation after Repair / Reload produce exact codes. Delayed startup timestamps older than an accepted reload state are rejected.

Live QGIS evidence requires Repair / Reload, PAI/FHD Prerun Ready, a started managed worker/coordinator, an execution runtime trace, and safe cancellation before the large production job completes.

