#!/usr/bin/env python3
"""Check local Markdown links used by repository documentation."""
from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
LINK_RE = re.compile(r"(?<!!/)\[[^\]]+\]\(([^)]+)\)")
SKIP_PREFIXES = (
    "http://",
    "https://",
    "mailto:",
    "#",
    "tel:",
)


def iter_markdown_files() -> list[Path]:
    return sorted(
        path
        for path in ROOT.rglob("*.md")
        if ".git" not in path.parts and "dist" not in path.parts
    )


def normalize_target(raw: str) -> str:
    target = raw.strip()
    if not target or target.startswith(SKIP_PREFIXES):
        return ""
    if target.startswith("<") and target.endswith(">"):
        target = target[1:-1]
    if " " in target and not target.startswith("./"):
        # A plain link title or unusual external syntax; ignore rather than
        # inventing a path interpretation.
        pass
    target = target.split("#", 1)[0]
    return unquote(target)


def main() -> int:
    failures: list[str] = []
    for markdown in iter_markdown_files():
        text = markdown.read_text(encoding="utf-8")
        for match in LINK_RE.finditer(text):
            raw = match.group(1)
            target = normalize_target(raw)
            if not target:
                continue
            if target.startswith(SKIP_PREFIXES) or "://" in target:
                continue
            if target.startswith("/"):
                candidate = ROOT / target.lstrip("/")
            else:
                candidate = (markdown.parent / target).resolve()
            try:
                candidate.relative_to(ROOT)
            except ValueError:
                failures.append(f"{markdown.relative_to(ROOT)}: link escapes repository: {raw}")
                continue
            if not candidate.exists():
                failures.append(f"{markdown.relative_to(ROOT)}: missing link target: {raw}")
    if failures:
        print("Broken local Markdown links found:")
        for failure in failures:
            print(f"- {failure}")
        return 1
    print("All local Markdown links resolve.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
