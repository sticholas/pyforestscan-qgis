from __future__ import annotations
import argparse, json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pyforestscan_qgis.core.processing_paths import clean_processing_workspace, validate_processing_workspace

def main() -> int:
    ap = argparse.ArgumentParser(description="Audit and safely clean transient processing workspace files.")
    ap.add_argument("root", type=Path); ap.add_argument("--apply", action="store_true")
    ap.add_argument("--attempt"); args = ap.parse_args()
    report = {"validation": validate_processing_workspace(args.root), "cleanup": clean_processing_workspace(args.root, dry_run=not args.apply, attempt=args.attempt)}
    print(json.dumps(report, indent=2, sort_keys=True)); return 0
if __name__ == "__main__": raise SystemExit(main())
