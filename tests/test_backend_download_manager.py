"""Tests for the production backend download manager."""

from __future__ import annotations

import hashlib
import tempfile
import unittest
import urllib.error
from pathlib import Path

from pyforestscan_qgis.core.backend.download_manager import CancellationToken, DownloadManager, DownloadRequest, DownloadSource


class FakeResponse:
    """Tiny context-manager response for download manager tests."""

    def __init__(self, payload: bytes) -> None:
        self.payload = payload
        self.offset = 0
        self.headers = {"Content-Length": str(len(payload))}

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def read(self, size: int) -> bytes:
        if self.offset >= len(self.payload):
            return b""
        chunk = self.payload[self.offset : self.offset + size]
        self.offset += len(chunk)
        return chunk


class BackendDownloadManagerTests(unittest.TestCase):
    """Validate retries, cache reuse, cancellation, and checksums."""

    def test_download_retries_and_verifies_checksum(self) -> None:
        payload = b"micromamba"
        expected = hashlib.sha256(payload).hexdigest()
        calls = {"count": 0}

        def opener(request, timeout):
            calls["count"] += 1
            if calls["count"] == 1:
                raise urllib.error.URLError("temporary failure")
            return FakeResponse(payload)

        with tempfile.TemporaryDirectory() as tmpdir:
            target = Path(tmpdir) / "downloads" / "artifact.bin"
            manager = DownloadManager(opener=opener)
            result = manager.download(DownloadRequest("artifact", target, expected_sha256=expected, sources=(DownloadSource("mirror", "https://example.invalid/a"),), retries=1))

        self.assertTrue(result.success)
        self.assertEqual(result.attempts, 2)
        self.assertEqual(result.sha256, expected)

    def test_checksum_failure_removes_partial_and_destination(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            target = Path(tmpdir) / "artifact.bin"
            manager = DownloadManager(opener=lambda request, timeout: FakeResponse(b"bad"))
            result = manager.download(DownloadRequest("artifact", target, expected_sha256="0" * 64, sources=(DownloadSource("mirror", "https://example.invalid/a"),), retries=0))

            self.assertFalse(result.success)
            self.assertFalse(target.exists())
            self.assertFalse(target.with_name("artifact.bin.part").exists())

    def test_cache_reuse_skips_network(self) -> None:
        payload = b"cached"
        expected = hashlib.sha256(payload).hexdigest()
        with tempfile.TemporaryDirectory() as tmpdir:
            target = Path(tmpdir) / "artifact.bin"
            target.write_bytes(payload)
            manager = DownloadManager(opener=lambda request, timeout: (_ for _ in ()).throw(AssertionError("network should not run")))
            result = manager.download(DownloadRequest("artifact", target, expected_sha256=expected, sources=(DownloadSource("mirror", "https://example.invalid/a"),)))

        self.assertTrue(result.cache_hit)
        self.assertEqual(result.attempts, 0)

    def test_cancelled_download_cleans_partial(self) -> None:
        token = CancellationToken()

        def opener(request, timeout):
            token.cancel()
            return FakeResponse(b"some bytes")

        with tempfile.TemporaryDirectory() as tmpdir:
            target = Path(tmpdir) / "artifact.bin"
            result = DownloadManager(opener=opener).download(
                DownloadRequest("artifact", target, sources=(DownloadSource("mirror", "https://example.invalid/a"),)),
                cancel_token=token,
            )
            self.assertFalse(result.success)
            self.assertTrue(result.cancelled)
            self.assertFalse(target.with_name("artifact.bin.part").exists())


if __name__ == "__main__":
    unittest.main()
