"""Session-owned object review metadata contracts without QGIS."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from pyforestscan_qgis.core.point_cloud.object_review import (
    MAX_NOTE_CHARACTERS, object_review_record, object_review_summary,
    update_object_review, validate_object_reviews)
from pyforestscan_qgis.core.point_cloud.session import PointCloudEditSession, SourceIdentity


class ObjectReviewTests(unittest.TestCase):
    def setUp(self):
        self.source = "a"*64

    def test_review_and_note_updates_preserve_one_object_record(self):
        ledger = update_object_review(None, self.source, "Tree_ID", 7,
            reviewed=True, updated_at="2026-01-01T00:00:00+00:00")
        ledger = update_object_review(ledger, self.source, "Tree_ID", 7,
            note="  crown checked  ", updated_at="2026-01-02T00:00:00+00:00")
        record = object_review_record(ledger, self.source, "Tree_ID", 7)
        self.assertTrue(record["reviewed"])
        self.assertEqual(record["note"], "crown checked")
        self.assertEqual(len(ledger["records"]), 1)
        self.assertEqual(object_review_summary(record), "Reviewed | Note saved")

    def test_not_reviewed_is_explicit_and_does_not_discard_note(self):
        ledger = update_object_review(None, self.source, "Segment", -2,
            note="Inspect stem", updated_at="first")
        ledger = update_object_review(ledger, self.source, "Segment", -2,
            reviewed=False, updated_at="second")
        record = object_review_record(ledger, self.source, "Segment", -2)
        self.assertTrue(record["recorded"])
        self.assertFalse(record["reviewed"])
        self.assertEqual(record["note"], "Inspect stem")

    def test_missing_record_is_not_confused_with_recorded_state(self):
        record = object_review_record(None, self.source, "Tree_ID", 99)
        self.assertFalse(record["recorded"])
        self.assertFalse(record["reviewed"])
        self.assertEqual(record["note"], "")

    def test_foreign_duplicate_or_oversized_metadata_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "another source"):
            validate_object_reviews({"schema_version":1, "source_sha256":"b"*64,
                                     "records":[]}, self.source)
        duplicate = {"schema_version":1, "source_sha256":self.source, "records":[
            {"field":"Tree_ID", "object_id":1, "reviewed":True,
             "note":"", "updated_at":"one"},
            {"field":"Tree_ID", "object_id":1, "reviewed":False,
             "note":"", "updated_at":"two"}]}
        with self.assertRaisesRegex(ValueError, "duplicate"):
            validate_object_reviews(duplicate, self.source)
        with self.assertRaisesRegex(ValueError, "at most"):
            update_object_review(None, self.source, "Tree_ID", 1,
                                 note="x"*(MAX_NOTE_CHARACTERS+1))

    def test_review_ledger_survives_session_recovery_without_journal_edit(self):
        with TemporaryDirectory() as folder:
            source_path = Path(folder)/"source.las"
            source_path.write_bytes(b"immutable")
            source = SourceIdentity.capture(source_path)
            session = PointCloudEditSession(source, "EPSG:32605",
                ("X","Y","Z","Classification","Tree_ID"))
            session.visibility["object_reviews"] = update_object_review(
                None, source.sha256, "Tree_ID", 12, reviewed=True,
                note="Stem checked", updated_at="fixed")
            saved = session.save(Path(folder)/"session.json")
            loaded = PointCloudEditSession.load(saved)
            record = object_review_record(loaded.visibility["object_reviews"],
                                          source.sha256, "Tree_ID", 12)
            self.assertTrue(record["reviewed"])
            self.assertEqual(record["note"], "Stem checked")
            self.assertEqual(loaded.operations, ())
