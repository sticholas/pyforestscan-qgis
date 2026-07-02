"""Dry-run backend installation planning for PBM."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .bootstrap import MicromambaBootstrapPlan, build_micromamba_bootstrap_plan
from .channels import BackendChannel, default_backend_channels, format_channels
from .environment_spec import BackendEnvironmentSpec, build_environment_spec
from .models import BackendPlatform, BackendRegistry
from .paths import BackendPaths, resolve_backend_paths
from .registry import default_backend_registry


@dataclass(frozen=True)
class BackendInstallStep:
    """One planned installation, verification, or rollback step."""

    title: str
    detail: str
    modifies_files: bool = False


@dataclass(frozen=True)
class BackendInstallPlan:
    """Complete dry-run installation plan for the managed backend."""

    backend_root: Path
    micromamba_location: Path
    environment_path: Path
    platform: BackendPlatform
    channels: tuple[BackendChannel, ...]
    environment_spec: BackendEnvironmentSpec
    bootstrap_plan: MicromambaBootstrapPlan
    estimated_steps: tuple[BackendInstallStep, ...]
    verification_steps: tuple[BackendInstallStep, ...]
    rollback_steps: tuple[BackendInstallStep, ...]
    offline_install_notes: tuple[str, ...]
    warnings: tuple[str, ...]
    dry_run_only: bool = True

    def required_package_names(self) -> tuple[str, ...]:
        """Return required backend package names in planned install order."""
        return self.environment_spec.package_names()


def create_backend_install_plan(paths: BackendPaths | None = None, registry: BackendRegistry | None = None) -> BackendInstallPlan:
    """Create a dry-run PBM install plan without touching the filesystem."""
    paths_value = paths or resolve_backend_paths()
    registry_value = registry or default_backend_registry()
    channels = default_backend_channels()
    environment_spec = build_environment_spec(registry_value, channels=tuple(channel.name for channel in channels))
    bootstrap_plan = build_micromamba_bootstrap_plan(paths_value)
    warnings = list(bootstrap_plan.warnings)
    if paths_value.platform is BackendPlatform.UNKNOWN:
        warnings.append("Backend platform is unknown; installation cannot be enabled until path and artifact policies are defined.")
    warnings.append("Installation is disabled for normal users. Real installer mechanics require PYFORESTSCAN_QGIS_ENABLE_BACKEND_INSTALL=1 for development testing.")

    return BackendInstallPlan(
        backend_root=paths_value.backend_root,
        micromamba_location=paths_value.micromamba_executable,
        environment_path=paths_value.environment_path,
        platform=paths_value.platform,
        channels=channels,
        environment_spec=environment_spec,
        bootstrap_plan=bootstrap_plan,
        estimated_steps=(
            BackendInstallStep("Prepare user-local backend folders", f"Would create {paths_value.backend_root} and child cache/log/env folders.", modifies_files=True),
            BackendInstallStep("Download micromamba bootstrap", f"Would download {bootstrap_plan.artifact_name} to {bootstrap_plan.download_cache_path}.", modifies_files=True),
            BackendInstallStep("Verify micromamba artifact", "Would verify checksum and executable metadata before use."),
            BackendInstallStep("Create managed environment", f"Would create environment at {paths_value.environment_path} using registry-driven packages.", modifies_files=True),
            BackendInstallStep("Install required packages", ", ".join(environment_spec.package_names()), modifies_files=True),
            BackendInstallStep("Write backend config", f"Would write backend.json and registry.json under {paths_value.backend_root}.", modifies_files=True),
        ),
        verification_steps=(
            BackendInstallStep("Verify backend Python", f"Run {paths_value.python_executable} --version."),
            BackendInstallStep("Verify PyForestScan import", "Import pyforestscan inside the managed backend Python."),
            BackendInstallStep("Verify PDAL", "Run pdal --version and import python-pdal."),
            BackendInstallStep("Verify raster stack", "Import osgeo.gdal, rasterio, and numpy from the managed backend Python."),
            BackendInstallStep("Record verification report", f"Would write verification results to {paths_value.verify_log}.", modifies_files=True),
        ),
        rollback_steps=(
            BackendInstallStep("Preserve existing backend", "Future installer must avoid deleting a known-good backend until replacement verification passes."),
            BackendInstallStep("Use staging directories", "Future installer should create or repair in a staging area before activation."),
            BackendInstallStep("Rollback failed install", "If verification fails, mark backend repair-required and preserve logs for diagnosis."),
            BackendInstallStep("Repair path", "Repair remains a planned operation until controlled installer work begins."),
        ),
        offline_install_notes=(
            "Offline install remains a future placeholder after Phase 22C.",
            "Future design may accept a pre-downloaded micromamba artifact, package cache, and lock/spec file.",
            "Offline artifacts must still pass checksum and version verification before activation.",
        ),
        warnings=tuple(warnings),
    )


def format_install_plan(plan: BackendInstallPlan) -> str:
    """Format the dry-run install plan for Mission Control."""
    lines = [
        "PyForestScan Backend Install Plan (Dry Run)",
        "Installation is disabled for normal users. Developer-only installs require PYFORESTSCAN_QGIS_ENABLE_BACKEND_INSTALL=1; PBM does not modify QGIS Python or environment variables.",
        "",
        f"Platform: {plan.platform.value}",
        f"Backend root: {plan.backend_root}",
        f"Micromamba location: {plan.micromamba_location}",
        f"Environment path: {plan.environment_path}",
        "",
        "Package channels:",
        *[f"- {line}" for line in format_channels(plan.channels)],
        "",
        "Required packages:",
        *[f"- {package.name} {package.version_spec} ({package.source})" for package in plan.environment_spec.packages],
        "",
        "Estimated install steps:",
        *[f"- {step.title}: {step.detail}" for step in plan.estimated_steps],
        "",
        "Verification steps after install:",
        *[f"- {step.title}: {step.detail}" for step in plan.verification_steps],
        "",
        "Rollback / repair plan:",
        *[f"- {step.title}: {step.detail}" for step in plan.rollback_steps],
        "",
        "Offline install placeholder:",
        *[f"- {note}" for note in plan.offline_install_notes],
    ]
    if plan.warnings:
        lines.extend(("", "Warnings:"))
        lines.extend(f"- {warning}" for warning in plan.warnings)
    return "\n".join(lines)
