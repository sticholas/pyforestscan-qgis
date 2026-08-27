#!/usr/bin/env python3
"""Validate every internal import referenced by Python files in a built plugin ZIP."""

from __future__ import annotations

import argparse
import ast
import sys
import tempfile
import zipfile
from pathlib import Path

PLUGIN = "pyforestscan_qgis"
REQUIRED_RUNTIME_MODULES = (
    "pyforestscan_qgis.core.adaptive_processing",
    "pyforestscan_qgis.core.polygon_batch",
    "pyforestscan_qgis.backend_runner.job_coordinator",
    "pyforestscan_qgis.backend_runner.polygon_job_coordinator",
)


def validate_zip_import_graph(zip_path: Path) -> list[str]:
    errors: list[str] = []
    with tempfile.TemporaryDirectory(prefix="pyforestscan-import-graph-") as folder:
        root = Path(folder)
        with zipfile.ZipFile(zip_path) as archive:
            archive.extractall(root)
        package = root / PLUGIN
        modules = _module_index(package)
        for required in REQUIRED_RUNTIME_MODULES:
            if required not in modules:
                errors.append(f"Required packaged runtime module is missing: {required}")
        for module, path in sorted(modules.items()):
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            except (OSError, SyntaxError) as exc:
                errors.append(f"Cannot parse packaged module {module}: {exc}")
                continue
            for dependency in _internal_imports(tree, module, path.name == "__init__.py"):
                if not _resolves(dependency, modules):
                    errors.append(f"{module} imports missing packaged module {dependency}")
    return sorted(set(errors))


def _module_index(package: Path) -> dict[str, Path]:
    modules: dict[str, Path] = {}
    for path in package.rglob("*.py"):
        relative = path.relative_to(package)
        parts = list(relative.with_suffix("").parts)
        if parts[-1] == "__init__":
            parts.pop()
        module = ".".join((PLUGIN, *parts)) if parts else PLUGIN
        modules[module] = path
    return modules


def _internal_imports(tree: ast.AST, module: str, is_package: bool) -> set[str]:
    imports: set[str] = set()
    package_parts = module.split(".") if is_package else module.split(".")[:-1]
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names if alias.name == PLUGIN or alias.name.startswith(f"{PLUGIN}."))
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                keep = max(0, len(package_parts) - node.level + 1)
                base = package_parts[:keep]
                if node.module:
                    base.extend(node.module.split("."))
                dependency = ".".join(base)
            else:
                dependency = node.module or ""
            if dependency == PLUGIN or dependency.startswith(f"{PLUGIN}."):
                imports.add(dependency)
    return imports


def _resolves(dependency: str, modules: dict[str, Path]) -> bool:
    return dependency in modules or any(name.startswith(f"{dependency}.") for name in modules)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("zip_path", type=Path)
    args = parser.parse_args()
    errors = validate_zip_import_graph(args.zip_path)
    if errors:
        print("Packaged import graph validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    print("Packaged import graph validation passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
