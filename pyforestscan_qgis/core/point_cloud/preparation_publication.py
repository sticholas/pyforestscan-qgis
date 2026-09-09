"""Owned staging and no-replacement publication for prepared point clouds."""
from contextlib import contextmanager
import json
import os
from pathlib import Path
from uuid import uuid4

from .preparation import PreparationRequest
from .session import SourceIdentity


class PreparationPublication:
    def __init__(self, request: PreparationRequest):
        self.request = request
        self.parent = Path(request.output_path).parent.resolve(strict=True)
        token = uuid4().hex
        self.staged = self.parent / (f".{token}.preparation" + Path(request.output_path).suffix)
        self.staged_report = self.parent / f".{token}.preparation.json"
        self.published = False
        self._created = set()

    def publish(self, validate, *, cancelled=lambda: False):
        if self.published:
            raise ValueError("Preparation has already been published.")
        self._check_cancel(cancelled)
        if self.staged.is_symlink() or not self.staged.is_file() or not self.staged.stat().st_size:
            raise ValueError("Preparation produced no regular non-empty point cloud.")
        validation = validate(self.staged)
        if not isinstance(validation, dict) or validation.get("status") != "VALIDATED":
            raise ValueError("Prepared output did not pass scientific/file validation.")
        self.request.verify_input(cancelled=cancelled)
        if Path(self.request.output_path).parent.resolve(strict=True) != self.parent:
            raise ValueError("Preparation output directory changed.")
        identity = SourceIdentity.capture(self.staged, cancelled=cancelled)
        report = {"status": "VALIDATED", "request": self.request.to_dict(),
                  "request_signature": self.request.signature,
                  "output_path": self.request.output_path, "output_sha256": identity.sha256,
                  "output_bytes": identity.size, "source_unchanged": True,
                  "validation": validation}
        with self.staged_report.open("x", encoding="utf-8") as stream:
            self._created.add(self.staged_report)
            json.dump(report, stream, sort_keys=True, allow_nan=False, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        self._check_cancel(cancelled)
        self.request.validate_destination()
        if Path(self.request.output_path).parent.resolve(strict=True) != self.parent:
            raise ValueError("Preparation output directory changed.")
        with self.staged.open("r+b") as stream:
            os.fsync(stream.fileno())
        # Same primitive as authoritative export: fail safely if links are unsupported.
        os.link(self.staged_report, self.request.provenance_path)
        try:
            os.link(self.staged, self.request.output_path)
        except BaseException:
            # Only retract our own report, never a replacement created by another actor.
            destination = self.request.provenance_path
            if not destination.is_symlink() and destination.exists() and destination.samefile(self.staged_report):
                destination.unlink()
            raise
        self.published = True
        return report

    @staticmethod
    def _check_cancel(cancelled):
        if cancelled():
            raise InterruptedError("Preparation cancelled before publication.")

    def cleanup(self):
        for path in self._created:
            if path.parent.resolve() != self.parent:
                raise ValueError("Preparation staging ownership changed.")
            # Unlink only the two attempt-owned names; never recurse or follow links.
            path.unlink(missing_ok=True)


@contextmanager
def stage_preparation(request: PreparationRequest, *, cancelled=lambda: False):
    request.verify_input(cancelled=cancelled)
    transaction = PreparationPublication(request)
    try:
        with transaction.staged.open("xb"):
            transaction._created.add(transaction.staged)
        yield transaction
    finally:
        transaction.cleanup()
