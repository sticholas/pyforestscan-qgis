# PBM Logging

PBM uses structured JSON-lines logs for backend operations.

Standard logs:

- `backend_install.log`
- `backend_download.log`
- `backend_verify.log`
- `backend_repair.log`
- `backend_update.log`
- `backend_remove.log`

Each entry includes:

- timestamp
- operation
- severity level
- stage
- message
- details

Logs are stored under the user-local backend root. They are intended for troubleshooting installer, verification, repair, and future update flows without changing QGIS state.
