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


def workflow_action_labels() -> tuple[str, str, str]:
    """Return the primary Home action labels."""
    return ("Open Dataset", "Start Batch", "Continue Previous Session")


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
