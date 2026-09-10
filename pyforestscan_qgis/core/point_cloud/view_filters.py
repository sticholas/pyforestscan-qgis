"""Display-only class visibility; unobserved classes retain their prior state."""
from __future__ import annotations

from dataclasses import dataclass

from .las_classification import classification_entry


@dataclass(frozen=True)
class ClassVisibilityRow:
    code: int
    label: str
    color: str
    visible: bool
    resident_count: int | None = None

    @property
    def text(self):
        suffix = f" | ~{self.resident_count:,} in view" if self.resident_count is not None else ""
        return self.label + suffix


def visible_classes_after_changes(current, changes):
    visible = set(range(256) if current is None else current)
    for code, shown in changes.items():
        if type(code) is not int or not 0 <= code <= 255:
            raise ValueError("Class values must be integers from 0 to 255.")
        if shown:
            visible.add(code)
        else:
            visible.discard(code)
    return sorted(visible)


def class_visibility_rows(observed, visible=None, resident_counts=None):
    """Build catalog-backed rows; counts are renderer-resident, never source totals."""
    if visible is not None and (not isinstance(visible, (list, tuple)) or
            any(type(code) is not int or not 0 <= code <= 255 for code in visible)):
        raise ValueError("Visible classes must use LAS class values 0-255.")
    codes = set(observed or ())
    if any(type(code) is not int or not 0 <= code <= 255 for code in codes):
        raise ValueError("Observed classes must use LAS class values 0-255.")
    counts = {}
    for raw_code, count in (resident_counts or {}).items():
        try:
            code = int(raw_code)
        except (TypeError, ValueError) as error:
            raise ValueError("Resident class counts require LAS class values.") from error
        if (str(code) != str(raw_code) or not 0 <= code <= 255 or
                type(count) is not int or count < 0):
            raise ValueError("Resident class counts must be non-negative integers.")
        counts[code] = count
        codes.add(code)
    shown = set(range(256) if visible is None else visible)
    rows = []
    for code in sorted(codes):
        item = classification_entry(code)
        rows.append(ClassVisibilityRow(code, item.label, item.color,
                                       code in shown, counts.get(code)))
    return tuple(rows)


def isolated_class(code):
    """Return the one-class display state after validating a LAS class code."""
    classification_entry(code)
    return [code]
