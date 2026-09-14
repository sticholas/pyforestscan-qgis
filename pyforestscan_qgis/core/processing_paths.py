"""Canonical processing workspace paths and lifecycle validation (PFS-REL-004F)."""
from __future__ import annotations

import json
import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

@dataclass(frozen=True)
class WorkUnitPaths:
    work_unit_root: Path
    attempt_root: Path
    checkpoint_path: Path
    output_dir: Path
    diagnostics_dir: Path
    scratch_dir: Path

@dataclass(frozen=True)
class ProcessingPaths:
    attempt_root: Path
    job_root: Path
    product_root: Path
    work_unit: WorkUnitPaths

    @classmethod
    def for_work_unit(cls, run_root: Path | str, product: str, work_unit_id: str, attempt_id: str) -> "ProcessingPaths":
        job = Path(run_root)
        product_root = job / "work_units" / product
        wu = product_root / work_unit_id
        attempt = wu / "attempts" / attempt_id
        return cls(attempt, job, product_root, WorkUnitPaths(
            wu, attempt, wu / "status.json", wu / "outputs", attempt / "diagnostics", attempt / "scratch"))

def validate_processing_workspace(root: Path | str, *, repair: bool = False) -> dict[str, Any]:
    root = Path(root)
    issues: list[dict[str, str]] = []
    if not root.exists():
        return {"root": str(root), "valid": False, "issues": [{"code": "MISSING_ROOT", "path": str(root)}]}
    for p in root.rglob("*"):
        if p.name.endswith(".tmp") or p.name.endswith(".lock"):
            issues.append({"code": "STALE_TRANSIENT", "path": str(p)})
        if p.name == "work_units" and p.parent.name == "work_units":
            issues.append({"code": "DUPLICATE_WORK_UNITS", "path": str(p)})
        if p.name in {"tile_diagnostics.json", "summary.json", "status.json"} and p.is_dir():
            issues.append({"code": "FILE_DIR_COLLISION", "path": str(p)})
    if repair:
        for issue in list(issues):
            if issue["code"] == "STALE_TRANSIENT":
                try:
                    Path(issue["path"]).unlink()
                    issues.remove(issue)
                except OSError:
                    pass
    return {"root": str(root), "valid": not issues, "issues": issues, "repair": repair}

def clean_processing_workspace(root: Path | str, *, dry_run: bool = True, attempt: str | None = None) -> dict[str, Any]:
    root = Path(root); removed: list[str] = []
    for p in root.rglob("*") if root.exists() else ():
        if not p.is_file() or not (p.name.endswith(".tmp") or p.name.endswith(".lock")):
            continue
        if attempt and attempt not in str(p):
            continue
        removed.append(str(p))
        if not dry_run:
            try: p.unlink()
            except OSError: pass
    return {"root": str(root), "dry_run": dry_run, "removed": removed}

