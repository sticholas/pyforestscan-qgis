#!/usr/bin/env python3
"""Report Mission Control contextual-help topic usage."""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOPICS_FILE = ROOT / "pyforestscan_qgis" / "ui" / "help_topics.py"
UI_FILES = [ROOT / "pyforestscan_qgis" / "ui" / "pages.py"]


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
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
