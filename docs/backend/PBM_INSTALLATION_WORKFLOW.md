# PBM Installation Workflow

This page describes the target installation workflow. Phase 22C implements a controlled developer-only installer prototype; normal user installation remains disabled.

## Target User Workflow

```mermaid
sequenceDiagram
    participant User
    participant QGIS as QGIS Plugin
    participant PBM as Backend Manager
    participant FS as User-local backend folder
    participant Env as Managed environment

    User->>QGIS: Click Install Backend
    QGIS->>PBM: Start installer
    PBM->>FS: Create backend folder
    PBM->>FS: Download micromamba
    PBM->>Env: Create environment
    PBM->>Env: Install dependencies
    PBM->>PBM: Verify dependencies
    PBM->>QGIS: Report Ready
    QGIS->>User: Tools are ready
```

## Phase 22C Behavior

- Detect planned backend paths.
- Detect whether `backend.json`, micromamba, backend environment, and backend Python exist.
- Run version commands only when executables already exist.
- Run Python import checks only when backend Python already exists.
- Return planned-operation results for install, repair, update, and remove.
- Preview the future install plan for normal users.
- Refuse real install actions unless `PYFORESTSCAN_QGIS_ENABLE_BACKEND_INSTALL=1` is set.
- In developer mode, use `downloads/`, `staging/`, `env/`, and `logs/` below the user-local backend root.
- Roll back staging files on failed download, checksum, extraction, environment creation, or verification.
- Report QGIS compatibility for current QGIS 3.x and defensive QGIS 4.x readiness.
- Show clear UI text that installation is planned for users and experimental for developers.

## Future Installer Requirements

- Download into a cache/downloads folder under the backend root.
- Verify downloaded artifacts before execution.
- Create the environment without administrator privileges.
- Never install packages into QGIS Python.
- Never modify the QGIS installation.
- Never modify user environment variables.
- Write compact logs for install, verify, update, and remove operations.
- Recover cleanly from partial installs and support repair.
