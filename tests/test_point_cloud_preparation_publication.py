"""Publication races/cancellation must not replace source or unrelated output."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import os

from pyforestscan_qgis.core.point_cloud.preparation import PreparationOptions, PreparationRequest
from pyforestscan_qgis.core.point_cloud.preparation_publication import stage_preparation, PreparationPublication
from pyforestscan_qgis.core.point_cloud.session import SourceIdentity


class PreparationPublicationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "source.las"
        self.source.write_bytes(b"source")
        self.output = self.root / "derived.laz"
        self.request = PreparationRequest(SourceIdentity.capture(self.source), str(self.output),
                                         PreparationOptions(thinning="poisson", spacing=1))

    def valid(self, path):
        self.assertEqual(path.read_bytes(), b"prepared")
        return {"status": "VALIDATED", "test_fixture_only": True}

    def assert_no_staging(self):
        self.assertFalse(any(p.name.startswith(".") for p in self.root.iterdir()))
        self.assertEqual(self.source.read_bytes(), b"source")

    def test_success_publishes_checked_bytes_and_provenance(self):
        with stage_preparation(self.request) as job:
            job.staged.write_bytes(b"prepared")
            report = job.publish(self.valid)
            with self.assertRaises(ValueError):
                job.publish(self.valid)
        self.assertEqual(self.output.read_bytes(), b"prepared")
        self.assertEqual(json.loads(self.request.provenance_path.read_text()), report)
        self.assertEqual(report["output_sha256"], SourceIdentity.capture(self.output).sha256)
        self.assert_no_staging()

    def test_failure_and_cancellation_cleanup_owned_staging(self):
        for cancel in (False, True):
            with self.subTest(cancel=cancel), self.assertRaises((ValueError, InterruptedError)):
                with stage_preparation(self.request) as job:
                    job.staged.write_bytes(b"prepared")
                    job.publish(lambda path: {"status": "FAILED"}, cancelled=lambda: cancel)
            self.assertFalse(self.output.exists())
            self.assertFalse(self.request.provenance_path.exists())
            self.assert_no_staging()

    def test_racing_output_is_never_replaced_and_own_report_is_retracted(self):
        link = os.link
        def racing_link(source, destination):
            if Path(destination) == self.output:
                self.output.write_bytes(b"another job")
            return link(source, destination)
        with self.assertRaises(FileExistsError):
            with stage_preparation(self.request) as job:
                job.staged.write_bytes(b"prepared")
                with patch("pyforestscan_qgis.core.point_cloud.preparation_publication.os.link", racing_link):
                    job.publish(self.valid)
        self.assertEqual(self.output.read_bytes(), b"another job")
        self.assertFalse(self.request.provenance_path.exists())
        self.assert_no_staging()

    def test_source_mutation_during_validation_blocks_publication(self):
        def invalidating(path):
            self.source.write_bytes(b"changed")
            return {"status": "VALIDATED"}
        with self.assertRaises(ValueError):
            with stage_preparation(self.request) as job:
                job.staged.write_bytes(b"prepared")
                job.publish(invalidating)
        self.assertFalse(self.output.exists())
        self.assertFalse(self.request.provenance_path.exists())

    def test_unsupported_link_filesystem_fails_closed(self):
        with self.assertRaises(OSError):
            with stage_preparation(self.request) as job:
                job.staged.write_bytes(b"prepared")
                with patch("pyforestscan_qgis.core.point_cloud.preparation_publication.os.link", side_effect=OSError("unsupported")):
                    job.publish(self.valid)
        self.assertFalse(self.output.exists())
        self.assertFalse(self.request.provenance_path.exists())
        self.assert_no_staging()

    def test_staging_name_collision_is_not_cleaned_up(self):
        job = PreparationPublication(self.request)
        job.staged.write_bytes(b"unrelated")
        with patch("pyforestscan_qgis.core.point_cloud.preparation_publication.PreparationPublication", return_value=job):
            with self.assertRaises(FileExistsError):
                with stage_preparation(self.request):
                    self.fail("Staging collision should fail before yielding")
        self.assertEqual(job.staged.read_bytes(), b"unrelated")

    def test_report_name_collision_is_not_cleaned_up(self):
        with stage_preparation(self.request) as job:
            job.staged.write_bytes(b"prepared")
            job.staged_report.write_bytes(b"unrelated report")
            with self.assertRaises(FileExistsError):
                job.publish(self.valid)
        self.assertEqual(job.staged_report.read_bytes(), b"unrelated report")
        self.assertFalse(self.output.exists())

    def test_retargeted_directory_is_rejected(self):
        old, new = self.root / "old", self.root / "new"
        old.mkdir()
        new.mkdir()
        chosen = self.root / "chosen"
        try:
            chosen.symlink_to(old, target_is_directory=True)
        except OSError:
            self.skipTest("Symlinks unavailable")
        request = PreparationRequest(self.request.source, str(chosen / "derived.laz"), self.request.options)
        with stage_preparation(request) as job:
            job.staged.write_bytes(b"prepared")
            chosen.unlink()
            chosen.symlink_to(new, target_is_directory=True)
            with self.assertRaisesRegex(ValueError, "directory changed"):
                job.publish(self.valid)
        self.assertEqual(list(old.iterdir()), [])
        self.assertEqual(list(new.iterdir()), [])
