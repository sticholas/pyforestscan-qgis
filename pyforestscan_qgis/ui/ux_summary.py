"""Plain-Python Mission Control UX labels and summaries."""

from __future__ import annotations

PBM_ROUTED_PRODUCT_LABELS: tuple[str, ...] = (
    "Dataset Explorer",
    "CHM",
    "Canopy Cover",
    "PAD",
    "PAI",
    "FHD",
    "Rumple",
    "DTM",
    "Point Density",
    "Voxel Statistic",
)

QGIS_FALLBACK_PRODUCT_LABELS: tuple[str, ...] = (
    "Height Above Ground point-cloud export",
    "Preprocess Point Cloud",
)

MISSION_WORKFLOW_STEPS: tuple[str, ...] = (
    "Check environment",
    "Open workspace if needed",
    "Select dataset",
    "Choose products",
    "Run processing",
    "Review outputs",
)


GUIDED_WORKFLOW_PAGES: tuple[str, ...] = (
    "Home",
    "Workspace",
    "Dataset",
    "Planning",
    "Processing",
    "Results",
)


DESIGN_SPACING_TOKENS: tuple[tuple[str, int], ...] = (
    ("xs", 4),
    ("sm", 8),
    ("md", 12),
    ("lg", 16),
    ("xl", 24),
)

DESIGN_STATUS_LABELS: tuple[str, ...] = (
    "READY",
    "RUNNING",
    "WARNING",
    "FAILED",
    "NOT CONFIGURED",
    "DISABLED",
    "PLANNED",
)

STATUS_BADGE_TONES: dict[str, str] = {
    "READY": "success",
    "RUNNING": "progress",
    "WARNING": "warning",
    "FAILED": "danger",
    "NOT CONFIGURED": "neutral",
    "DISABLED": "muted",
    "PLANNED": "planned",
}

READINESS_MARKER_TOKENS: dict[str, tuple[str, str]] = {
    "ready": ("●", "#3f7f52"),
    "not_ready": ("○", "#b45b52"),
    "unknown": ("●", "#8b969b"),
}

BUTTON_ROLE_EXAMPLES: dict[str, tuple[str, ...]] = {
    "primary": ("Continue", "Continue to Dataset", "Continue to Planning", "Continue to Processing", "Run Processing", "Run Batch", "Install Backend"),
    "secondary": ("Open Batch", "Open Output Folder", "Load Outputs", "Preview Install Plan"),
    "neutral": ("Check Environment", "Set Up Backend", "Refresh Environment", "Verify Backend", "Browse"),
    "danger": ("Delete Workspace", "Clear Current Run", "Cancel Remaining"),
}

EXPANDABLE_SECTION_LABELS: tuple[str, ...] = (
    "Advanced",
    "Technical Details",
    "Troubleshooting",
)


def workflow_action_labels() -> tuple[str, str, str]:
    """Return Home continuation labels for the guided workflow."""
    return ("Continue", "Check Environment", "Continue to Dataset")


def design_spacing_tokens() -> dict[str, int]:
    """Return the standard PyForestScan UI spacing scale in pixels."""
    return dict(DESIGN_SPACING_TOKENS)


def design_status_labels() -> tuple[str, ...]:
    """Return the approved status badge labels."""
    return DESIGN_STATUS_LABELS


def status_badge_tone(status: str) -> str:
    """Return the design-system tone for a status label."""
    normalized = " ".join((status or "").replace("_", " ").upper().split())
    return STATUS_BADGE_TONES.get(normalized, "neutral")


def status_badge_label(status: str) -> str:
    """Return approved design-system wording for a raw status value."""
    normalized = " ".join((status or "").replace("_", " ").replace("-", " ").upper().split())
    aliases = {
        "PASS": "READY",
        "PASSED": "READY",
        "READY WITH QGIS PYTHON": "READY",
        "PARTIALLY READY": "WARNING",
        "NEEDS REVIEW": "WARNING",
        "REPAIR REQUIRED": "WARNING",
        "INSTALLING": "RUNNING",
        "VALIDATING": "RUNNING",
        "PENDING": "RUNNING",
        "CANCELLING": "RUNNING",
        "COMPLETED": "READY",
        "BACKEND READY": "READY",
        "SUCCESS": "READY",
        "FAILED": "FAILED",
        "INSTALL FAILED": "FAILED",
        "FAIL": "FAILED",
        "ERROR": "FAILED",
        "NOT READY": "FAILED",
        "CANCELLED": "DISABLED",
        "CANCELED": "DISABLED",
        "SKIPPED": "DISABLED",
        "NOT STARTED": "NOT CONFIGURED",
        "UNKNOWN": "NOT CONFIGURED",
    }
    if normalized in STATUS_BADGE_TONES:
        return normalized
    return aliases.get(normalized, "NOT CONFIGURED")


def readiness_marker_tokens() -> dict[str, tuple[str, str]]:
    """Return subtle readiness marker glyph and color tokens."""
    return dict(READINESS_MARKER_TOKENS)


def readiness_marker_kind(status: str) -> str:
    """Return ready, not_ready, or unknown for a raw readiness status."""
    badge = status_badge_label(status)
    if badge == "READY":
        return "ready"
    if badge in {"FAILED", "WARNING"}:
        return "not_ready"
    return "unknown"


def readiness_marker_label(status: str) -> str:
    """Return a small rich-text marker that sits beside readiness words."""
    glyph, color = READINESS_MARKER_TOKENS[readiness_marker_kind(status)]
    return f'<span style="color: {color}; font-size: 11px;">{glyph}</span>'


def readiness_status_text(status: str, text: str) -> str:
    """Prefix readiness text with a subtle marker without replacing words."""
    return f"{readiness_marker_label(status)}&nbsp;{text}"


def environment_is_ready(status: str) -> bool:
    """Return whether the environment status can run default guided processing."""
    return status_badge_label(status) == "READY"


def home_environment_readiness(status: str) -> str:
    """Return concise Home readiness copy."""
    normalized = (status or "").upper()
    if normalized == "READY":
        return "Ready to process with PBM backend."
    if normalized == "READY WITH QGIS PYTHON":
        return "Ready with QGIS Python fallback; PBM optional."
    if normalized == "NOT READY":
        return "Backend setup needed before processing."
    if normalized == "PARTIALLY READY":
        return "Review environment warnings before processing."
    return "Check environment readiness."


def home_environment_action_label(status: str) -> str:
    """Return the compact Home environment action label."""
    return "Check Environment" if environment_is_ready(status) else "Set Up Backend"


def button_role_for_label(label: str) -> str:
    """Return the standard button role for a known UI action label."""
    normalized = (label or "").strip().lower()
    for role, examples in BUTTON_ROLE_EXAMPLES.items():
        if any(normalized == example.lower() for example in examples):
            return role
    return "secondary"


def expandable_section_labels() -> tuple[str, ...]:
    """Return approved labels for collapsed technical disclosure sections."""
    return EXPANDABLE_SECTION_LABELS


def empty_state_message(page: str) -> str:
    """Return concise guidance for empty Mission Control pages."""
    messages = {
        "advisor": "Analyze a dataset to receive recommendations.",
        "results": "No outputs yet.\nRun processing to generate scientific products.",
        "workspace": "Open or create a workspace to begin.",
        "dataset": "No dataset selected.\nSelect a LAS, LAZ, or COPC dataset to begin.",
        "planning": "Analyze a dataset before choosing products.",
    }
    return messages.get(page.lower(), "Choose the next action to continue.")


def primary_action_label(page: str) -> str:
    """Return the standard dominant action label for a Mission Control page."""
    labels = {
        "home": "Continue",
        "environment": "Refresh Environment",
        "dataset": "Analyze Dataset",
        "advisor": "Review Recommendations",
        "planning": "Continue to Processing",
        "processing": "Run Processing",
        "batch": "Run Batch",
        "results": "Open Output Folder",
        "settings": "Verify Backend",
        "workspace": "Resume Workspace",
    }
    return labels.get(page.lower(), "Continue")


def backend_summary_from_environment(environment: str) -> str:
    """Return a compact backend summary for the Home dashboard."""
    normalized = (environment or "").upper()
    if normalized == "READY":
        return "Backend status: PBM ready for routed products"
    if normalized == "READY WITH QGIS PYTHON":
        return "Backend status: QGIS Python fallback ready; PBM optional"
    if normalized == "NOT READY":
        return "Backend status: action needed"
    if normalized == "PARTIALLY READY":
        return "Backend status: review warnings"
    return "Backend status: unknown"


def environment_headline(readiness: str, pbm_message: str | None = None) -> str:
    """Return the primary Environment page headline."""
    normalized = (readiness or "").upper()
    if normalized == "READY":
        return "Overall status: READY - routed products can run through PBM."
    if normalized == "READY WITH QGIS PYTHON":
        return "Overall status: READY WITH QGIS PYTHON - PBM is optional."
    if normalized == "NOT READY":
        return "Overall status: NOT READY - install or repair PBM before processing."
    if normalized == "PARTIALLY READY":
        return "Overall status: PARTIALLY READY - review warnings before processing."
    return f"Overall status: {readiness or 'Unknown'}"


def routed_products_summary() -> str:
    """Return compact PBM product coverage text."""
    return "PBM-routed products: " + ", ".join(PBM_ROUTED_PRODUCT_LABELS)


def qgis_fallback_summary() -> str:
    """Return compact QGIS fallback coverage text."""
    return "QGIS-Python-only remaining: " + ", ".join(QGIS_FALLBACK_PRODUCT_LABELS)


def technical_sections_default_collapsed() -> bool:
    """Document the beta UX default for logs and developer detail."""
    return True


def guided_workflow_pages() -> tuple[str, ...]:
    """Return the primary Mission Control workflow pages."""
    return GUIDED_WORKFLOW_PAGES


def guided_workflow_indicator(
    current_page: str,
    *,
    dataset_loaded: bool,
    planning_ready: bool,
    outputs_available: bool,
    environment_ready: bool = True,
    workspace_ready: bool = True,
    processing_complete: bool = False,
    batch_complete: bool = False,
) -> str:
    """Return a compact completed/current/upcoming single-dataset step indicator."""
    completed = {
        "Home": environment_ready,
        "Workspace": workspace_ready,
        "Dataset": dataset_loaded,
        "Planning": planning_ready,
        "Processing": processing_complete or outputs_available,
        "Results": outputs_available,
    }
    parts: list[str] = []
    for page in GUIDED_WORKFLOW_PAGES:
        if page == current_page:
            marker = "●"
        elif completed.get(page, False):
            marker = "✓"
        else:
            marker = "○"
        parts.append(f"{marker} {page}")
    return "  ".join(parts)


def guided_workflow_status_lines(
    *,
    backend_ready: bool,
    dataset_loaded: bool,
    planning_ready: bool,
    outputs_available: bool,
    processing_ready: bool = False,
    batch_complete: bool = False,
) -> tuple[str, ...]:
    """Return the compact Home workflow status summary."""
    return (
        f"Backend: {'READY' if backend_ready else 'Needs attention'}",
        f"Dataset: {'Loaded' if dataset_loaded else 'Not selected'}",
        f"Planning: {'Configured' if planning_ready else 'Not configured'}",
        f"Processing: {'Ready to run' if processing_ready else 'Not ready'}",
        f"Results: {'Available' if outputs_available else 'None'}",
    )


def guided_next_step(
    page: str,
    *,
    dataset_loaded: bool,
    planning_ready: bool,
    outputs_available: bool,
    environment_ready: bool = True,
    workspace_ready: bool = True,
    processing_complete: bool = False,
    batch_complete: bool = False,
) -> tuple[str, str, str, bool]:
    """Return next-step text, button label, target page, and enabled state."""
    if page == "Home":
        if not environment_ready:
            return ("Check environment readiness before processing.", "Check Environment", "Environment", True)
        if not workspace_ready:
            return ("Open or create a workspace before selecting data.", "Open Workspace", "Workspace", True)
        if outputs_available:
            return ("Review generated outputs.", "Open Results", "Results", True)
        if not dataset_loaded:
            return ("Select a dataset to begin.", "Continue to Dataset", "Dataset", True)
        if not planning_ready:
            return ("Build a product plan for the selected dataset.", "Continue to Planning", "Planning", True)
        return ("Run processing for the selected products.", "Continue to Processing", "Processing", True)
    if page == "Workspace":
        return ("Select a dataset for this workspace.", "Continue to Dataset", "Dataset", True)
    if page == "Dataset":
        if dataset_loaded:
            return ("Build a product plan for this dataset.", "Continue to Planning", "Planning", True)
        return ("Select and analyze a LAS, LAZ, or COPC dataset.", "Select Dataset", "Dataset", False)
    if page == "Planning":
        if not dataset_loaded:
            return ("Select a dataset before planning products.", "Select Dataset", "Dataset", True)
        if planning_ready:
            return ("Run processing for the selected products.", "Continue to Processing", "Processing", True)
        return ("Choose products and build the plan.", "Build Plan", "Planning", False)
    if page == "Processing":
        if outputs_available or processing_complete:
            return ("Review generated outputs and reports.", "Open Results", "Results", True)
        if planning_ready:
            return ("Run processing when the product plan is ready.", "Run Processing", "Processing", False)
        return ("Finish product planning before processing.", "Finish Planning", "Planning", True)
    if page == "Results":
        if outputs_available:
            return ("Load outputs into QGIS for review.", "Load Outputs", "Results", False)
        return ("Run processing to generate scientific products.", "Open Processing", "Processing", True)
    if page == "Scientific Advisor":
        if not dataset_loaded:
            return ("Analyze a dataset to receive recommendations.", "Select Dataset", "Dataset", True)
        return ("Use recommendations to refine planning.", "Open Planning", "Planning", True)
    if page == "Batch":
        if not planning_ready:
            return ("Finish product planning before batch processing.", "Finish Planning", "Planning", True)
        if batch_complete:
            return ("Review generated outputs and reports.", "Open Results", "Results", True)
        return ("Run batch only when you choose the batch workflow.", "Run Batch", "Batch", False)
    return ("Choose the next workflow step.", "Continue", "Home", True)
