"""Cold-start asset optimization must retain integrity and containment checks."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from pyforestscan_qgis.viewer.host import assets


class AssetVerificationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "assets"
        self.root.mkdir()
        self.name = "build/potree/workers/EptLaszipDecoderWorker.js"
        target = self.root / self.name
        target.parent.mkdir(parents=True)
        target.write_bytes(b"verified fixture")
        self.records = {self.name: {"sha256": hashlib.sha256(target.read_bytes()).hexdigest()}}
        self.manifest()

    def manifest(self):
        (self.root / "manifest.json").write_text(json.dumps({"files": self.records}))

    def test_root_is_resolved_once_without_skipping_file_verification(self):
        original = Path.resolve
        roots = []
        def resolve(path, *args, **kwargs):
            if path == self.root:
                roots.append(path)
            return original(path, *args, **kwargs)
        with patch.object(Path, "resolve", resolve):
            result = assets(self.root)
        self.assertEqual(len(roots), 1)
        self.assertEqual(result["assets/" + self.name.replace(".js", ".vendor.js")],
                         (self.root / self.name).resolve())

    def test_tampered_asset_rejected_on_every_launch(self):
        assets(self.root)
        (self.root / self.name).write_bytes(b"changed")
        with self.assertRaisesRegex(ValueError, "needs repair"):
            assets(self.root)

    def test_parent_escape_rejected_even_with_matching_hash(self):
        outside = self.root.parent / "outside.js"
        outside.write_bytes(b"outside")
        self.records["../outside.js"] = {"sha256": hashlib.sha256(b"outside").hexdigest()}
        self.manifest()
        with self.assertRaisesRegex(ValueError, "Invalid packaged viewer asset"):
            assets(self.root)

    def test_symlink_escape_rejected(self):
        outside = self.root.parent / "outside.js"
        outside.write_bytes(b"outside")
        link = self.root / "link.js"
        try:
            link.symlink_to(outside)
        except OSError:
            self.skipTest("Symlink creation is unavailable")
        self.records["link.js"] = {"sha256": hashlib.sha256(b"outside").hexdigest()}
        self.manifest()
        with self.assertRaisesRegex(ValueError, "Invalid packaged viewer asset"):
            assets(self.root)
