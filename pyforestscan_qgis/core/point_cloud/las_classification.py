"""LAS 1.4 classification catalog shared by editor presentation and policy."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LasClass:
    code: int
    name: str
    color: str
    common_target: bool = False
    reserved: bool = False

    @property
    def label(self):
        return f"{self.name} ({self.code})"


@dataclass(frozen=True)
class AutoClassifyDecision:
    apply: bool
    message: str = ""


STANDARD_CLASSES = (
    LasClass(0, "Created, never classified", "#808080"),
    LasClass(1, "Unclassified", "#808080", True),
    LasClass(2, "Ground", "#a0522d", True),
    LasClass(3, "Low vegetation", "#4caf50", True),
    LasClass(4, "Medium vegetation", "#258c3a", True),
    LasClass(5, "High vegetation", "#087830", True),
    LasClass(6, "Building", "#e59b2f", True),
    LasClass(7, "Low noise", "#d340c3", True),
    LasClass(8, "Reserved", "#aa4c4c", reserved=True),
    LasClass(9, "Water", "#3478c9", True),
    LasClass(10, "Rail", "#7f6248"),
    LasClass(11, "Road surface", "#555555"),
    LasClass(12, "Reserved", "#aa4c4c", reserved=True),
    LasClass(13, "Wire guard", "#d3b928"),
    LasClass(14, "Wire conductor", "#f0d23a"),
    LasClass(15, "Transmission tower", "#b57930"),
    LasClass(16, "Wire-structure connector", "#d6a33d"),
    LasClass(17, "Bridge deck", "#a56f43", True),
    LasClass(18, "High noise", "#dc2f7a", True),
    LasClass(19, "Overhead structure", "#8c6bb1"),
    LasClass(20, "Ignored ground", "#bd9370"),
    LasClass(21, "Snow", "#b8dff0"),
    LasClass(22, "Temporal exclusion", "#8f8f8f"),
)
_BY_CODE = {item.code: item for item in STANDARD_CLASSES}

# High-frequency forestry cleanup targets. Choosing one proposes a value; the
# editor's existing Apply/automatic-selection path remains the only edit action.
FORESTRY_TARGET_PRESETS = (2, 3, 4, 5, 6, 9, 7, 18)


def classification_entry(code):
    """Describe one uint8 LAS class without treating unknown values as standard."""
    if type(code) is not int or not 0 <= code <= 255:
        raise ValueError("LAS classification code must be an integer from 0 to 255.")
    if code in _BY_CODE:
        return _BY_CODE[code]
    if code >= 64:
        return LasClass(code, "User-defined", "#4d9999")
    return LasClass(code, "Reserved", "#777777", reserved=True)


def forestry_target_presets():
    return tuple(classification_entry(code) for code in FORESTRY_TARGET_PRESETS)


def classification_warning(code):
    """Return a compact warning for non-routine targets, or an empty string."""
    item = classification_entry(code)
    if item.reserved:
        return f"Class {code} is reserved by LAS 1.4; choose a standard or user-defined class."
    if code >= 64:
        return f"Class {code} is user-defined; document its meaning for downstream users."
    return ""


def classification_counts_summary(counts, *, limit=3):
    """Format authoritative resolver counts without implying renderer sampling."""
    if type(limit) is not int or limit < 1:
        raise ValueError("Classification count limit must be a positive integer.")
    values = tuple(tuple(item) for item in (counts or ()))
    for item in values:
        if (len(item) != 2 or type(item[0]) is not int or not 0 <= item[0] <= 255 or
                type(item[1]) is not int or item[1] < 0):
            raise ValueError("Classification counts require LAS class codes and non-negative counts.")
    shown = values[:limit]
    text = " | ".join(f"{classification_entry(code).name}: {count:,}" for code, count in shown)
    remaining = len(values) - len(shown)
    return text + (f" | +{remaining} classes" if remaining else "")


def classification_target_guidance(code):
    """Return concise downstream-impact guidance for one proposed LAS class."""
    warning = classification_warning(code)
    if warning:
        return warning
    if code == 2:
        return "Ground edits can change DTM and height-above-ground products; review terrain context before export."
    if code in (3, 4, 5):
        return "Vegetation class edits can change class-filtered canopy and vertical-structure products."
    if code in (7, 18):
        return "Noise classes may be excluded by downstream filters; review isolated returns before export."
    if code == 6:
        return "Building classification separates structures from vegetation in class-filtered products."
    if code == 9:
        return "Water classification can influence class-filtered terrain interpretation."
    if code in (0, 1):
        return "Unclassified points may require review before class-filtered scientific processing."
    return "This LAS class is valid; confirm its meaning matches the source classification convention."


def classify_while_selecting_decision(enabled, completed_action, definitions, selected_count):
    """Decide whether one completed editor snapshot should stage classification."""
    if type(enabled) is not bool or type(selected_count) is not int or selected_count < 0:
        raise ValueError("Invalid classify-while-selecting state.")
    if not enabled or completed_action != "select":
        return AutoClassifyDecision(False)
    if not selected_count:
        return AutoClassifyDecision(False, "Automatic classification skipped: no source points selected.")
    if (not isinstance(definitions, (list, tuple)) or not definitions or
            definitions[-1].get("selection_mode") != "REPLACE"):
        return AutoClassifyDecision(False,
            "Automatic classification applies to Replace selections; apply this composite manually.")
    return AutoClassifyDecision(True)
