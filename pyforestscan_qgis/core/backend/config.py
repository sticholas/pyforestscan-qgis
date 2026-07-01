"""Backend configuration serialization."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from .exceptions import BackendConfigError
from .models import BackendConfig, BackendStatus
from .paths import BackendPaths
from .registry import default_backend_registry


def utc_now_iso() -> str:
    """Return a stable UTC timestamp for backend metadata."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def planned_backend_config(paths: BackendPaths) -> BackendConfig:
    """Return an in-memory config for the planned backend layout."""
    now = utc_now_iso()
    return BackendConfig(
        backend_version="1",
        backend_root=paths.backend_root,
        environment_path=paths.environment_path,
        python_executable=paths.python_executable,
        micromamba_executable=paths.micromamba_executable,
        created_at=now,
        updated_at=now,
        platform=paths.platform,
        status=BackendStatus.NOT_INSTALLED,
        registry=default_backend_registry(),
    )


def load_backend_config(path: Path) -> BackendConfig | None:
    """Load backend config if present; return None when absent."""
    if not path.exists():
        return None
    try:
        return BackendConfig.from_dict(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError, KeyError, ValueError, TypeError) as exc:
        raise BackendConfigError(f"Backend config could not be loaded: {path}") from exc


def save_backend_config(config: BackendConfig, path: Path) -> None:
    """Persist backend config to disk.

    This helper is provided for future installation phases. Phase 22A service
    methods do not call it automatically because they must not modify user
    environments.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(config.to_dict(), indent=2, sort_keys=True), encoding="utf-8")
