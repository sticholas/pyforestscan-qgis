#!/usr/bin/env python3
"""Inspect PBM staged/final backend folders without QGIS."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from pyforestscan_qgis.core.backend.installer import staged_backend_paths
from pyforestscan_qgis.core.backend.paths import resolve_backend_paths
from pyforestscan_qgis.core.backend.verification import format_verification_result, verify_backend


def collect_backend_diagnostics(backend_root: Path) -> str:
    """Return staged/final PBM backend diagnostics for a backend root."""
    paths = resolve_backend_paths(backend_root=backend_root)
    lines = [
        "PyForestScan PBM Backend Diagnostics",
        "=====================================",
        f"Backend root: {paths.backend_root}",
        f"Final config: {paths.config_file} ({'found' if paths.config_file.exists() else 'missing'})",
        f"Final micromamba: {paths.micromamba_executable} ({'found' if paths.micromamba_executable.exists() else 'missing'})",
        f"Final environment: {paths.environment_path} ({'found' if paths.environment_path.exists() else 'missing'})",
        f"Final Python: {paths.python_executable} ({'found' if paths.python_executable.exists() else 'missing'})",
        f"Staging directory: {paths.staging_dir} ({'found' if paths.staging_dir.exists() else 'missing'})",
        "",
        "Final Backend Verification",
        "--------------------------",
        format_verification_result(verify_backend(paths, require_config=True)),
    ]
    staged_paths = staged_backend_paths(paths)
    if staged_paths.backend_root.exists():
        lines.extend(
            [
                "",
                "Staged Backend Verification",
                "---------------------------",
                format_verification_result(verify_backend(staged_paths, require_config=False)),
            ]
        )
    else:
        lines.extend(["", "Staged Backend Verification", "---------------------------", "No staging directory was found."])
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Inspect PBM staged/final backend folders without QGIS.")
    parser.add_argument("--backend-root", required=True, type=Path, help="PBM backend root, for example %LOCALAPPDATA%/PyForestScan/backend.")
    args = parser.parse_args(argv)
    print(collect_backend_diagnostics(args.backend_root))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
