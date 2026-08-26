# Processing Engine Bootstrap

First-use setup reuses the transactional PBM installer. It obtains an exclusive `processing_engine.setup.lock`, prepares the managed environment, validates staged content, promotes only validated content, and then runs the authoritative engine verifier. A second QGIS session reports that setup is already running instead of modifying the environment concurrently.

Setup is idempotent when the contract is already ready. Missing or partial required modules produce `REPAIR_REQUIRED`; protocol skew produces `INCOMPATIBLE`. The normal action is **Set Up** or **Repair**, with technical logs hidden by default.

Micromamba and conda-forge own the compiled geospatial stack. PyForestScan remains installed through managed-environment Python according to the packaged backend manifest. No `shell=True` command is permitted. Windows subprocesses use the centralized hidden-window policy.

Plugin initialization performs no installation or repair. Lightweight startup discovery reads `processing_engine.json` and validates its fingerprint; cold imports occur only when Mission Control or execution needs a current check.
