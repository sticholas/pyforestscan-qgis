"""Checksum policy and helpers for PBM downloads."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ChecksumPolicy:
    """Expected checksum metadata for a downloaded artifact."""

    algorithm: str = "sha256"
    expected: str | None = None
    required: bool = True
    source: str = "Checksums are enforced when supplied by the installer policy."


@dataclass(frozen=True)
class ChecksumResult:
    """Result from checksum verification."""

    status: str
    message: str
    actual: str | None = None
    expected: str | None = None

    def passed(self) -> bool:
        """Return whether checksum verification passed."""
        return self.status == "pass"


def sha256_file(path: Path) -> str:
    """Return the SHA-256 digest for a local file."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_checksum(path: Path, policy: ChecksumPolicy) -> ChecksumResult:
    """Verify a local file against the provided checksum policy."""
    if policy.algorithm.lower() != "sha256":
        return ChecksumResult(status="fail", message=f"Unsupported checksum algorithm: {policy.algorithm}", expected=policy.expected)
    if not path.exists():
        return ChecksumResult(status="fail", message=f"Downloaded artifact is missing: {path}", expected=policy.expected)
    actual = sha256_file(path)
    if not policy.expected:
        if policy.required:
            return ChecksumResult(
                status="fail",
                message="No pinned checksum is available for this required checksum policy.",
                actual=actual,
                expected=None,
            )
        return ChecksumResult(
            status="pass",
            message="No pinned checksum is available; checksum verification was skipped for this internal beta artifact.",
            actual=actual,
            expected=None,
        )
    if actual.lower() != policy.expected.lower():
        return ChecksumResult(status="fail", message="Checksum mismatch.", actual=actual, expected=policy.expected)
    return ChecksumResult(status="pass", message="Checksum verified.", actual=actual, expected=policy.expected)
