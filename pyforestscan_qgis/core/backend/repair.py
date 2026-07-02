"""Repair planning for managed backend installations."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .config import load_backend_config
from .exceptions import BackendConfigError
from .manifest import BackendManifest, BackendManifestError, load_backend_manifest
from .models import BackendStatus
from .paths import BackendPaths


@dataclass(frozen=True)
class RepairIssue:
    """One detected backend repair issue."""

    code: str
    severity: str
    message: str
    path: Path | None = None


@dataclass(frozen=True)
class RepairAction:
    """One proposed repair action."""

    code: str
    description: str
    developer_only: bool = True


@dataclass(frozen=True)
class RepairPlan:
    """Non-mutating repair plan for the backend."""

    status: BackendStatus
    issues: tuple[RepairIssue, ...]
    actions: tuple[RepairAction, ...]
    execution_enabled: bool = False

    def has_issues(self) -> bool:
        """Return whether repair found anything actionable."""
        return bool(self.issues)


def plan_backend_repair(paths: BackendPaths, manifest: BackendManifest | None = None) -> RepairPlan:
    """Inspect backend files and propose repair actions without modifying files."""
    issues: list[RepairIssue] = []
    actions: list[RepairAction] = []
    manifest_value: BackendManifest | None = manifest
    try:
        manifest_value = manifest_value or load_backend_manifest()
    except BackendManifestError as exc:
        issues.append(RepairIssue("corrupt_manifest", "error", str(exc)))
        actions.append(RepairAction("restore_manifest", "Restore the packaged backend manifest before installing or repairing."))

    try:
        config = load_backend_config(paths.config_file)
    except BackendConfigError as exc:
        config = None
        issues.append(RepairIssue("corrupt_config", "error", str(exc), paths.config_file))
        actions.append(RepairAction("rewrite_config", "Rewrite backend configuration after a successful verification."))

    if not paths.micromamba_executable.exists():
        issues.append(RepairIssue("missing_executable", "error", "Micromamba executable is missing.", paths.micromamba_executable))
        actions.append(RepairAction("restore_micromamba", "Redownload, verify, and extract Micromamba through the transaction engine."))
    if not paths.environment_path.exists():
        issues.append(RepairIssue("broken_environment", "error", "Backend environment directory is missing.", paths.environment_path))
        actions.append(RepairAction("recreate_environment", "Recreate the managed backend environment from the manifest."))
    if not paths.python_executable.exists():
        issues.append(RepairIssue("missing_python", "error", "Managed backend Python is missing.", paths.python_executable))
        actions.append(RepairAction("recreate_python", "Recreate the environment and verify Python before activation."))
    if manifest_value is not None and paths.environment_path.exists():
        missing_packages = [package.name for package in manifest_value.required_packages() if package.python_import_name and not paths.python_executable.exists()]
        if missing_packages:
            issues.append(RepairIssue("missing_packages", "warning", f"Package verification is blocked until backend Python exists: {', '.join(missing_packages)}."))
            actions.append(RepairAction("verify_packages", "Run package verification after Python is restored."))
    if config is None and paths.config_file.exists():
        actions.append(RepairAction("backup_bad_config", "Preserve corrupt config beside repair logs before rewriting."))
    status = BackendStatus.REPAIR_REQUIRED if issues else BackendStatus.READY
    return RepairPlan(status=status, issues=tuple(issues), actions=tuple(_dedupe_actions(actions)), execution_enabled=False)


def format_repair_plan(plan: RepairPlan) -> str:
    """Format a repair plan for Mission Control."""
    lines = ["Backend Repair Plan", f"Status: {plan.status.value}", "Execution: developer-only / disabled for normal users", ""]
    if not plan.issues:
        lines.append("No repair issues were detected by file-level checks.")
    else:
        lines.append("Detected issues:")
        lines.extend(f"- {issue.code}: {issue.message}" for issue in plan.issues)
    if plan.actions:
        lines.extend(("", "Proposed actions:"))
        lines.extend(f"- {action.code}: {action.description}" for action in plan.actions)
    return "\n".join(lines)


def _dedupe_actions(actions: list[RepairAction]) -> tuple[RepairAction, ...]:
    seen: set[str] = set()
    unique: list[RepairAction] = []
    for action in actions:
        if action.code in seen:
            continue
        seen.add(action.code)
        unique.append(action)
    return tuple(unique)
