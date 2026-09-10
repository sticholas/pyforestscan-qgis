"""Isolated viewer capability under the existing PBM setup ownership boundary."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time
from uuid import uuid4

from ..atomic_state import atomic_write_json
from ..backend.paths import resolve_backend_paths
from ..backend.processing_engine import ProcessingEngineSetupLock
from ..backend.process_env import build_clean_subprocess_env, hidden_subprocess_kwargs


def runtime_spec():
    path = Path(__file__).with_name("viewer_runtime.json")
    data = path.read_bytes()
    return json.loads(data), hashlib.sha256(data).hexdigest()


def viewer_environment(executable: Path, platform_name: str | None = None) -> dict[str, str]:
    """Return an isolated environment with only this runtime's Qt assets."""
    platform_name = platform_name or os.name
    env = build_clean_subprocess_env()
    env = {key: value for key, value in env.items()
           if not key.upper().startswith(("QT_", "QML", "CONDA", "MAMBA", "PYTHON"))}
    if platform_name == "nt":
        system = Path(os.environ.get("SystemRoot", "C:/Windows")) / "System32"
        pyside = executable.parent / "Lib" / "site-packages" / "PySide6"
        plugins = pyside / "plugins"
        path = ";".join((str(executable.parent), str(pyside), str(system)))
        # Never let a QGIS Qt installation choose the viewer's platform plugin.
        # Explicit runtime-local paths also make qwindows.dll dependency lookup
        # deterministic when the viewer is launched from inside QGIS.
        env["QT_PLUGIN_PATH"] = str(plugins)
        env["QT_QPA_PLATFORM_PLUGIN_PATH"] = str(plugins / "platforms")
        env["QT_QPA_PLATFORM"] = "windows"
        env["QML2_IMPORT_PATH"] = str(pyside / "qml")
    else:
        path = os.pathsep.join((str(executable.parent), "/usr/bin", "/bin"))
        for name in ("DISPLAY", "WAYLAND_DISPLAY", "XDG_RUNTIME_DIR", "DBUS_SESSION_BUS_ADDRESS"):
            if name in os.environ:
                env[name] = os.environ[name]
    for key in tuple(env):
        if key.upper() == "PATH":
            del env[key]
    env["PATH"] = path
    env["PYTHONNOUSERSITE"] = "1"
    return env


class ViewerRuntimeService:
    """Optional family, never a replacement for the scientific environment."""

    def __init__(self, paths=None):
        self.paths = paths or resolve_backend_paths()
        self.root = self.paths.backend_root / "viewer"
        self.config_path = self.root / "runtime.json"

    def executable(self) -> Path:
        _, spec_hash = runtime_spec()
        try:
            config = json.loads(self.config_path.read_text(encoding="utf-8"))
            executable = Path(config["python"]).resolve()
        except (OSError, ValueError, KeyError, TypeError) as exc:
            raise RuntimeError("Viewer component needs setup.") from exc
        if (config.get("spec_sha256") != spec_hash or
                not executable.is_relative_to((self.root / "runtimes").resolve()) or
                not executable.is_file()):
            raise RuntimeError("Viewer component needs repair.")
        return executable

    def setup(self, *, confirmed=False, progress=lambda message: None, cancelled=lambda: False) -> Path:
        if not confirmed:
            raise PermissionError("Viewer setup needs explicit confirmation.")
        spec, spec_hash = runtime_spec()
        if self.paths.platform.value not in spec["supported_setup_platforms"]:
            raise RuntimeError("Viewer setup is not yet qualified on this platform.")
        if not self.paths.micromamba_executable.is_file():
            raise RuntimeError("Set up the Processing Engine in Tools & Setup first.")
        runtimes = self.root / "runtimes"
        attempt = runtimes / uuid4().hex
        activated = False
        self.root.mkdir(parents=True, exist_ok=True)
        log_path = self.root / "setup.log"
        with ProcessingEngineSetupLock(self.paths):
            attempt.mkdir(parents=True, exist_ok=False)
            try:
                with log_path.open("a", encoding="utf-8") as log:
                    def run(command, label, timeout=1800):
                        progress(label)
                        log.write(f"stage={label}; executable={command[0]}; clean_environment=true\n")
                        log.flush()
                        env = build_clean_subprocess_env(extra_env={
                            "MAMBA_ROOT_PREFIX": str(self.root / "package-cache"),
                            "PIP_CONFIG_FILE": os.devnull,
                        })
                        if Path(command[0]).resolve().is_relative_to(attempt.resolve()):
                            env = viewer_environment(Path(command[0]))
                            env["PIP_CONFIG_FILE"] = os.devnull
                        process = subprocess.Popen(command, stdout=log, stderr=log, env=env,
                                                   **hidden_subprocess_kwargs())
                        started = time.monotonic()
                        try:
                            while process.poll() is None:
                                if cancelled() or time.monotonic() - started > timeout:
                                    process.terminate()
                                    try:
                                        process.wait(timeout=10)
                                    except subprocess.TimeoutExpired:
                                        process.kill()
                                        process.wait()
                                    raise RuntimeError("Viewer setup cancelled or timed out.")
                                time.sleep(.1)
                        finally:
                            if process.poll() is None:
                                process.kill()
                                process.wait()
                        if process.returncode:
                            raise RuntimeError(f"{label} failed. See {log_path}.")

                    run([str(self.paths.micromamba_executable), "--no-rc", "create", "--yes",
                         "--prefix", str(attempt), "--override-channels", "-c", "conda-forge",
                         "--strict-channel-priority", f"python={spec['python']}", "pip"],
                        "Preparing isolated viewer Python")
                    executable = attempt / ("python.exe" if os.name == "nt" else "bin/python")
                    run([str(executable), "-I", "-m", "pip", "--isolated", "install",
                         "--only-binary=:all:", "--index-url", "https://pypi.org/simple",
                         *spec["packages"]], "Installing viewer components")
                    progress("Verifying isolated viewer")
                    probe = subprocess.run(
                        [str(executable), "-I", "-c",
                         "import PySide6; from PySide6 import QtCore,QtQuick,QtWebEngineQuick; print(PySide6.__version__)"],
                        env=viewer_environment(executable), text=True, capture_output=True,
                        timeout=60, **hidden_subprocess_kwargs())
                    log.write(probe.stdout + probe.stderr)
                    if probe.returncode or probe.stdout.strip() != spec["packages"][0].split("==")[1]:
                        raise RuntimeError(f"Viewer verification failed. See {log_path}.")
                if cancelled():
                    raise RuntimeError("Viewer setup cancelled before activation.")
                # Immutable runtime directories avoid relocating Conda prefixes.
                # Only the verified active pointer changes; a good prior runtime remains.
                atomic_write_json(self.config_path, {"schema_version": 1, "python": str(executable),
                                                     "spec_sha256": spec_hash, "protocol": spec["runtime_protocol"]})
                activated = True
                # UI teardown must not invalidate an already verified active pointer.
                try:
                    progress("Viewer component ready")
                except Exception:
                    pass
                return executable
            except Exception:
                if not activated and attempt.exists() and not attempt.is_symlink() and attempt.resolve().parent == runtimes.resolve():
                    shutil.rmtree(attempt)
                raise
