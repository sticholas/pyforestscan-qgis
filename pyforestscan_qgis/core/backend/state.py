"""Backend state detection helpers."""

from __future__ import annotations

from .config import load_backend_config
from .exceptions import BackendConfigError
from .models import BackendState, BackendStatus
from .paths import BackendPaths


def detect_backend_state(paths: BackendPaths) -> BackendState:
    """Detect backend state without modifying the filesystem."""
    root_exists = paths.backend_root.exists()
    config_exists = paths.config_file.exists()
    environment_exists = paths.environment_path.exists()
    micromamba_exists = paths.micromamba_executable.exists()
    python_exists = paths.python_executable.exists()

    if not root_exists:
        return BackendState(
            status=BackendStatus.NOT_INSTALLED,
            platform=paths.platform,
            backend_root=paths.backend_root,
            config_exists=False,
            environment_exists=False,
            micromamba_exists=False,
            python_exists=False,
            message="Backend root does not exist. Installation is planned for a future phase.",
        )

    if config_exists:
        try:
            config = load_backend_config(paths.config_file)
        except BackendConfigError:
            return BackendState(
                status=BackendStatus.REPAIR_REQUIRED,
                platform=paths.platform,
                backend_root=paths.backend_root,
                config_exists=True,
                environment_exists=environment_exists,
                micromamba_exists=micromamba_exists,
                python_exists=python_exists,
                message="Backend config exists but could not be read.",
            )
        if config is not None and config.status is BackendStatus.READY and python_exists:
            return BackendState(
                status=BackendStatus.READY,
                platform=paths.platform,
                backend_root=paths.backend_root,
                config_exists=True,
                environment_exists=environment_exists,
                micromamba_exists=micromamba_exists,
                python_exists=python_exists,
                message="Backend config reports Ready and backend Python exists.",
            )

    if environment_exists or micromamba_exists or python_exists or config_exists:
        return BackendState(
            status=BackendStatus.REPAIR_REQUIRED,
            platform=paths.platform,
            backend_root=paths.backend_root,
            config_exists=config_exists,
            environment_exists=environment_exists,
            micromamba_exists=micromamba_exists,
            python_exists=python_exists,
            message="Partial backend files were detected; verification or repair is required.",
        )

    return BackendState(
        status=BackendStatus.NOT_INSTALLED,
        platform=paths.platform,
        backend_root=paths.backend_root,
        config_exists=False,
        environment_exists=False,
        micromamba_exists=False,
        python_exists=False,
        message="Backend root exists but no managed backend files were detected.",
    )
