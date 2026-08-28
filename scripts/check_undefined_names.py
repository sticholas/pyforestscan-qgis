#!/usr/bin/env python3
"""Fail when production functions reference names absent from their module."""

from __future__ import annotations

import argparse
import builtins
import symtable
import tempfile
import zipfile
from pathlib import Path


def undefined_names(path: Path) -> list[tuple[int, str]]:
    source = path.read_text(encoding="utf-8")
    module = symtable.symtable(source, str(path), "exec")
    module_names = set(module.get_identifiers()) | set(dir(builtins)) | {"__file__", "__name__", "__package__"}
    findings: list[tuple[int, str]] = []

    def visit(table: symtable.SymbolTable) -> None:
        if table.get_type() in {"function", "class"}:
            for name in table.get_identifiers():
                symbol = table.lookup(name)
                if symbol.is_referenced() and symbol.is_global() and name not in module_names:
                    findings.append((table.get_lineno(), name))
        for child in table.get_children():
            visit(child)

    visit(module)
    return findings


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", nargs="?", type=Path, default=Path("pyforestscan_qgis"))
    args = parser.parse_args()
    findings: list[str] = []
    temporary = None
    root = args.root
    if root.suffix.lower() == ".zip":
        temporary = tempfile.TemporaryDirectory()
        with zipfile.ZipFile(root) as archive:
            archive.extractall(temporary.name)
        root = Path(temporary.name) / "pyforestscan_qgis"
    for path in sorted(root.rglob("*.py")):
        for line, name in undefined_names(path):
            findings.append(f"{path.relative_to(root)}:{line}: undefined name '{name}'")
    if findings:
        print("\n".join(findings))
        return 1
    print(f"Undefined-name validation passed: {args.root}")
    if temporary is not None:
        temporary.cleanup()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
