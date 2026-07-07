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
    "Check backend",
    "Select dataset or batch folder",
    "Review recommendation",
    "Choose products",
    "Run",
    "Review outputs",
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

BUTTON_ROLE_EXAMPLES: dict[str, tuple[str, ...]] = {
    "primary": ("Open Dataset", "Run Processing", "Run Batch", "Install Backend"),
    "secondary": ("Open Output Folder", "Load Outputs", "Preview Install Plan"),
    "neutral": ("Refresh Environment", "Verify Backend", "Browse"),
    "danger": ("Delete Workspace", "Clear Current Run", "Cancel Remaining"),
}

EXPANDABLE_SECTION_LABELS: tuple[str, ...] = (
    "Advanced",
    "Technical Details",
    "Troubleshooting",
)


def workflow_action_labels() -> tuple[str, str, str]:
    """Return the primary Home action labels."""
    return ("Open Dataset", "Start Batch", "Continue Previous Session")


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
        "results": "Run processing to generate output products.",
        "workspace": "Open or create a workspace to begin.",
        "dataset": "Select a lidar dataset, then analyze it.",
        "planning": "Analyze a dataset before choosing products.",
    }
    return messages.get(page.lower(), "Choose the next action to continue.")


def primary_action_label(page: str) -> str:
    """Return the standard dominant action label for a Mission Control page."""
    labels = {
        "home": "Open Dataset",
        "environment": "Refresh Environment",
        "dataset": "Analyze Dataset",
        "advisor": "Continue to Planning",
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
