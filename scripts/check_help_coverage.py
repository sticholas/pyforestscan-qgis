#!/usr/bin/env python3
"""Lint Mission Control contextual help for semantic release quality."""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOPICS_FILE = ROOT / "pyforestscan_qgis" / "ui" / "help_topics.py"
UI_FILES = [ROOT / "pyforestscan_qgis" / "ui" / "pages.py"]
GENERIC_PHRASES = (
    "this option", "this value", "this workflow", "continue this action",
    "use this control", "choose this option", "current workflow",
)


def registered_topics() -> set[str]:
    tree = ast.parse(TOPICS_FILE.read_text(encoding="utf-8"))
    topics: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and getattr(node.func, "id", "") == "HelpTopic" and node.args:
            first = node.args[0]
            if isinstance(first, ast.Constant) and isinstance(first.value, str):
                topics.add(first.value)
    return topics


def used_topics() -> set[str]:
    pattern = re.compile(r"info_badge\(\s*[\"']([^\"']+)[\"']")
    used: set[str] = set()
    for path in UI_FILES:
        used.update(pattern.findall(path.read_text(encoding="utf-8")))
    return used


def main() -> int:
    registered = registered_topics()
    used = used_topics()
    missing = sorted(used - registered)
    orphan = sorted(registered - used)
    print(f"Registered help topics: {len(registered)}")
    print(f"Used help topics: {len(used)}")
    print(f"Missing used topics: {len(missing)}")
    for item in missing:
        print(f"MISSING {item}")
    print(f"Orphan registered topics: {len(orphan)}")
    for item in orphan:
        print(f"ORPHAN {item}")
    help_source = TOPICS_FILE.read_text(encoding="utf-8").lower()
    generic = sorted(phrase for phrase in GENERIC_PHRASES if phrase in help_source)
    print(f"Generic placeholder phrases: {len(generic)}")
    for item in generic:
        print(f"GENERIC {item}")
    pages_source = UI_FILES[0].read_text(encoding="utf-8")
    infrastructure = (
        "QTimer.singleShot(0, self._install_context_help)",
        "register_context_help(widget, text, self)",
        'widget.setProperty("resolvedContextHelp", resolved)',
        "widget.setToolTip(resolved)",
        "widget.setAccessibleName",
    )
    absent = [item for item in infrastructure if item not in pages_source]
    for item in absent:
        print(f"MISSING INFRASTRUCTURE {item}")
    return 1 if missing or generic or absent else 0


if __name__ == "__main__":
    sys.exit(main())
