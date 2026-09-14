#!/usr/bin/env python3
"""Report the managed Processing Engine state without QGIS."""

from pyforestscan_qgis.core.backend.paths import resolve_backend_paths
from pyforestscan_qgis.core.backend.processing_engine import ProcessingEngineVerifier


def main() -> int:
    report = ProcessingEngineVerifier(resolve_backend_paths()).verify()
    print(report.state.value)
    print(report.summary)
    print(f"Executable: {report.executable}")
    if report.failed_components:
        print("Technical missing components: " + ", ".join(report.failed_components))
    return 0 if report.ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
