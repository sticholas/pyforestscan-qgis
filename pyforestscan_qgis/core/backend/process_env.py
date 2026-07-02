"""Sanitized subprocess environments for managed PBM backend commands."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Mapping, Sequence


REMOVED_PYTHON_ENV_KEYS = {
    "PYTHONPATH",
    "PYTHONHOME",
    "PYTHONUSERBASE",
    "PYTHONSTARTUP",
    "PYTHONINSPECT",
}

REMOVED_PIP_ENV_KEYS = {
    "PIP_PREFIX",
    "PIP_TARGET",
    "PIP_USER",
    "PIP_REQUIRE_VIRTUALENV",
}

ESSENTIAL_ENV_KEYS = {
    "PATH",
    "Path",
    "PATHEXT",
    "TEMP",
    "TMP",
    "TMPDIR",
    "USERPROFILE",
    "LOCALAPPDATA",
    "APPDATA",
    "PROGRAMDATA",
    "SystemRoot",
    "WINDIR",
    "COMSPEC",
    "HOME",
    "USER",
    "USERNAME",
    "LOGNAME",
    "LANG",
    "LC_ALL",
    "SSL_CERT_FILE",
    "REQUESTS_CA_BUNDLE",
    "CURL_CA_BUNDLE",
}

SANITIZED_ENV_POLICY = (
    "PBM subprocesses use a sanitized environment: QGIS/Python profile variables "
    "are removed, Python user-site is disabled, pip prompts are disabled, and "
    "only essential system variables plus requested backend paths are preserved."
)


def build_clean_subprocess_env(
    base_env: Mapping[str, str] | None = None,
    prepend_paths: Sequence[Path | str] = (),
    extra_env: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Return a minimal environment for PBM subprocesses.

    The result deliberately avoids inheriting QGIS profile dependency paths and
    Python user-site configuration while preserving enough OS state for process
    creation, TLS certificates, and temporary files.
    """
    source = dict(base_env or os.environ)
    clean: dict[str, str] = {}
    essential_upper = {item.upper() for item in ESSENTIAL_ENV_KEYS}

    for key, value in source.items():
        canonical = key.upper()
        if canonical in REMOVED_PYTHON_ENV_KEYS or canonical in REMOVED_PIP_ENV_KEYS:
            continue
        if key in ESSENTIAL_ENV_KEYS or canonical in essential_upper:
            clean[key] = str(value)

    path_key = _path_key(clean)
    path_value = clean.get(path_key, source.get(path_key, source.get("PATH", source.get("Path", ""))))
    clean[path_key] = _clean_path(path_value, prepend_paths)

    clean["PYTHONNOUSERSITE"] = "1"
    clean["PIP_NO_INPUT"] = "1"
    clean["PIP_DISABLE_PIP_VERSION_CHECK"] = "1"

    if extra_env:
        for key, value in extra_env.items():
            if key.upper() in REMOVED_PYTHON_ENV_KEYS:
                continue
            clean[key] = str(value)

    return clean


def clean_env_summary(command_kind: str, executable: Path | str, clean_env_used: bool = True) -> dict[str, str]:
    """Return non-secret diagnostic details for backend subprocess logs."""
    return {
        "command_kind": command_kind,
        "executable": str(executable),
        "clean_env_used": "yes" if clean_env_used else "no",
        "env_policy": SANITIZED_ENV_POLICY,
    }


def summarize_subprocess_output(stderr: str | None, stdout: str | None = None, max_lines: int = 4) -> str:
    """Return first/last output lines without dumping huge logs."""
    text = (stderr or stdout or "").strip()
    if not text:
        return ""
    lines = text.splitlines()
    if len(lines) <= max_lines * 2:
        return "\n".join(lines)
    return "\n".join([*lines[:max_lines], "...", *lines[-max_lines:]])


def backend_pip_install_command(backend_python: Path, packages: Sequence[str]) -> list[str]:
    """Return the only supported pip invocation for managed backend packages."""
    return [str(backend_python), "-m", "pip", "install", "--no-deps", *packages]


def conda_environment_data_env(environment_path: Path, platform_value: str) -> dict[str, str]:
    """Return backend-local GDAL/PROJ data env vars when conda data dirs exist."""
    data_env: dict[str, str] = {}
    for candidate in _gdal_data_candidates(environment_path, platform_value):
        if candidate.exists():
            data_env["GDAL_DATA"] = str(candidate)
            break
    for candidate in _proj_data_candidates(environment_path, platform_value):
        if candidate.exists():
            value = str(candidate)
            data_env["PROJ_DATA"] = value
            data_env["PROJ_LIB"] = value
            break
    return data_env


def conda_environment_path_entries(environment_path: Path, platform_value: str) -> tuple[Path, ...]:
    """Return backend-local PATH entries needed by conda geospatial runtimes."""
    if platform_value.lower() == "windows":
        return (
            environment_path,
            environment_path / "Scripts",
            environment_path / "Library" / "bin",
            environment_path / "bin",
        )
    return (
        environment_path / "bin",
        environment_path,
    )


def _path_key(env: Mapping[str, str]) -> str:
    for key in env:
        if key.upper() == "PATH":
            return key
    return "PATH"


def _clean_path(path_value: str, prepend_paths: Sequence[Path | str]) -> str:
    entries: list[str] = []
    for entry in _split_path_entries(path_value):
        if not entry or _is_qgis_python_profile_path(entry):
            continue
        entries.append(entry)
    prefix = [str(path) for path in prepend_paths if str(path)]
    separator = ";" if ";" in path_value and os.pathsep != ";" else os.pathsep
    return separator.join([*prefix, *entries])


def _split_path_entries(path_value: str) -> list[str]:
    if ";" in path_value:
        return path_value.split(";")
    if os.pathsep in path_value:
        return path_value.split(os.pathsep)
    return [path_value] if path_value else []


def _is_qgis_python_profile_path(path_entry: str) -> bool:
    normalized = path_entry.lower().replace("\\", "/")
    if "qgis" in normalized and any(marker in normalized for marker in ("/profiles/", "/python/", "/dependencies/")):
        return True
    if "osgeo4w" in normalized and "/python" in normalized:
        return True
    return False


def _gdal_data_candidates(environment_path: Path, platform_value: str) -> tuple[Path, ...]:
    if platform_value.lower() == "windows":
        return (
            environment_path / "Library" / "share" / "gdal",
            environment_path / "share" / "gdal",
        )
    return (
        environment_path / "share" / "gdal",
        environment_path / "Library" / "share" / "gdal",
    )


def _proj_data_candidates(environment_path: Path, platform_value: str) -> tuple[Path, ...]:
    if platform_value.lower() == "windows":
        return (
            environment_path / "Library" / "share" / "proj",
            environment_path / "share" / "proj",
        )
    return (
        environment_path / "share" / "proj",
        environment_path / "Library" / "share" / "proj",
    )



def hidden_subprocess_kwargs(os_name: str | None = None, subprocess_module: object = subprocess) -> dict[str, object]:
    """Return kwargs that keep backend subprocesses from flashing consoles on Windows."""
    if (os_name or os.name) != "nt":
        return {}
    kwargs: dict[str, object] = {}
    creationflags = getattr(subprocess_module, "CREATE_NO_WINDOW", 0)
    if creationflags:
        kwargs["creationflags"] = creationflags
    startupinfo_type = getattr(subprocess_module, "STARTUPINFO", None)
    if startupinfo_type is not None:
        startupinfo = startupinfo_type()
        startupinfo.dwFlags |= getattr(subprocess_module, "STARTF_USESHOWWINDOW", 0)
        startupinfo.wShowWindow = 0
        kwargs["startupinfo"] = startupinfo
    return kwargs
