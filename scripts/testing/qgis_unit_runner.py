"""Run selected unittest modules inside QGIS Python without a Qt shutdown hang."""
import os
import json
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))


suite = unittest.defaultTestLoader.loadTestsFromNames(sys.argv[1:])
result = unittest.TextTestRunner(verbosity=2).run(suite)
if os.environ.get("PFS_QGIS_TEST_RESULT"):
    Path(os.environ["PFS_QGIS_TEST_RESULT"]).write_text(json.dumps({
        "successful": result.wasSuccessful(),
        "tests_run": result.testsRun,
        "failures": len(result.failures),
        "errors": len(result.errors),
        "skipped": len(result.skipped),
    }, indent=2), encoding="utf-8")
sys.stdout.flush()
sys.stderr.flush()
# QGIS/Qt may retain native application objects after unittest has finished.
os._exit(0 if result.wasSuccessful() else 1)
