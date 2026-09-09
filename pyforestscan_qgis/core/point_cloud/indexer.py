"""Managed out-of-core viewer indexing, isolated from scientific/QGIS Python."""
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
from ..backend.processing_engine import ProcessingEngineSetupLock
from ..backend.process_env import build_clean_subprocess_env, hidden_subprocess_kwargs


INDEXER_SPEC = {"schema_version": 1, "channel": "conda-forge",
                "packages": ["untwine=1.5.1"], "capability": "viewer_copc_index"}
SPEC_HASH = hashlib.sha256(json.dumps(INDEXER_SPEC, sort_keys=True).encode()).hexdigest()
LEGACY_SPEC_HASH = hashlib.sha256(json.dumps(dict(INDEXER_SPEC,
    packages=['untwine>=1.5,<2']), sort_keys=True).encode()).hexdigest()
QUALIFIED_VERSION = 'untwine version (1.5.1)'


def indexer_environment(prefix):
    # Avoid scientific GDAL/PROJ/Qt DLLs; this executable owns its Conda closure.
    clean = build_clean_subprocess_env()
    for key in tuple(clean):
        if key.upper() == "PATH":
            del clean[key]
    entries = [prefix, prefix / "Library/bin", prefix / "Scripts", prefix / "bin"]
    entries.extend([Path(os.environ.get("SystemRoot", "C:/Windows")) / "System32"]
                   if os.name == "nt" else [Path("/usr/bin"), Path("/bin")])
    clean["PATH"] = os.pathsep.join(map(str, entries))
    return clean


class ViewerIndexerService:
    def __init__(self, paths):
        self.paths = paths
        self.root = paths.backend_root / "viewer" / "indexer"

    def capability(self):
        try:
            config = json.loads((self.root / "runtime.json").read_text(encoding="utf-8"))
            prefix = Path(config["prefix"])
            executable = Path(config["executable"])
            if (config["spec_sha256"] not in (SPEC_HASH, LEGACY_SPEC_HASH) or
                    not prefix.resolve().is_relative_to((self.root / "runtimes").resolve()) or
                    not executable.resolve().is_relative_to(prefix.resolve()) or
                    not executable.is_file()):
                raise ValueError("Invalid managed indexer identity")
            probe = subprocess.run([str(executable), "--version"],
                env=indexer_environment(prefix), capture_output=True, text=True,
                timeout=15, **hidden_subprocess_kwargs())
            if probe.returncode or probe.stdout.strip() != QUALIFIED_VERSION:
                raise ValueError("Indexer verification failed")
            return executable, prefix, probe.stdout.strip()
        except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as error:
            raise RuntimeError("The optimized-view component needs setup. Use Setup / Repair Viewer; "
                               "the original point cloud has not been changed.") from error

    def setup(self, *, confirmed=False, progress=lambda message: None, cancelled=lambda: False):
        if not confirmed:
            raise PermissionError("Viewer indexer setup requires confirmation.")
        try:
            return self.capability()
        except RuntimeError:
            pass
        if not self.paths.micromamba_executable.is_file():
            raise RuntimeError("Set up the Processing Engine before the Viewer.")
        attempt = self.root / "runtimes" / uuid4().hex
        self.root.mkdir(parents=True, exist_ok=True)
        activated = False
        with ProcessingEngineSetupLock(self.paths):
            try:
                attempt.mkdir(parents=True)
                progress("Installing optimized-view component")
                with (self.root / "setup.log").open("a", encoding="utf-8") as log:
                    command = [str(self.paths.micromamba_executable), "--no-rc", "create", "--yes",
                        "--prefix", str(attempt), "--override-channels", "-c", INDEXER_SPEC["channel"],
                        "--strict-channel-priority", *INDEXER_SPEC["packages"]]
                    env = build_clean_subprocess_env(extra_env={
                        "MAMBA_ROOT_PREFIX": str(self.root / "package-cache")})
                    process = subprocess.Popen(command, stdout=log, stderr=log, env=env,
                                               **hidden_subprocess_kwargs())
                    started = time.monotonic()
                    try:
                        while process.poll() is None:
                            if cancelled() or time.monotonic() - started > 1800:
                                raise RuntimeError("Optimized-view setup cancelled or timed out.")
                            time.sleep(.1)
                        if process.returncode:
                            raise RuntimeError(f"Optimized-view setup failed. See {self.root / 'setup.log'}.")
                    finally:
                        if process.poll() is None:
                            process.kill()
                        process.wait()
                name = "untwine.exe" if os.name == "nt" else "untwine"
                executable = next((p / name for p in (attempt / "Library/bin", attempt / "bin", attempt)
                                   if (p / name).is_file()), None)
                if executable is None:
                    raise RuntimeError("Managed indexer executable is missing.")
                probe = subprocess.run([str(executable), "--version"], env=indexer_environment(attempt),
                    capture_output=True, text=True, timeout=15, **hidden_subprocess_kwargs())
                if probe.returncode or probe.stdout.strip() != QUALIFIED_VERSION or cancelled():
                    raise RuntimeError("Managed indexer verification failed or setup cancelled.")
                atomic_write_json(self.root / "runtime.json", {
                    "prefix": str(attempt), "executable": str(executable),
                    "spec_sha256": SPEC_HASH, "version": probe.stdout.strip(),
                    "capability": INDEXER_SPEC["capability"]})
                activated = True
                return executable, attempt, probe.stdout.strip()
            finally:
                if not activated and attempt.exists() and not attempt.is_symlink() and (
                        attempt.resolve().parent == (self.root / "runtimes").resolve()):
                    shutil.rmtree(attempt)
