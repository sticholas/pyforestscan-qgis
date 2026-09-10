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


def classification_entry(code):
    """Describe one uint8 LAS class without treating unknown values as standard."""
    if type(code) is not int or not 0 <= code <= 255:
        raise ValueError("LAS classification code must be an integer from 0 to 255.")
    if code in _BY_CODE:
        return _BY_CODE[code]
    if code >= 64:
        return LasClass(code, "User-defined", "#4d9999")
    return LasClass(code, "Reserved", "#777777", reserved=True)


def classification_warning(code):
    """Return a compact warning for non-routine targets, or an empty string."""
    item = classification_entry(code)
    if item.reserved:
        return f"Class {code} is reserved by LAS 1.4; choose a standard or user-defined class."
    if code >= 64:
        return f"Class {code} is user-defined; document its meaning for downstream users."
    return ""


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
