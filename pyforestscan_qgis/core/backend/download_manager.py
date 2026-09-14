"""Production-oriented download manager for backend artifacts."""

from __future__ import annotations

import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Callable, Protocol

from .checksums import ChecksumPolicy, sha256_file, verify_checksum


@dataclass(frozen=True)
class DownloadSource:
    """One candidate source for an artifact download."""

    name: str
    url: str
    priority: int = 0


class ArtifactProvider(Protocol):
    """Protocol for future mirror and artifact-source providers."""

    def sources_for(self, artifact_name: str) -> tuple[DownloadSource, ...]:
        """Return candidate sources for an artifact name."""


@dataclass(frozen=True)
class StaticArtifactProvider:
    """Simple provider backed by an in-memory mapping."""

    sources: dict[str, tuple[DownloadSource, ...]]

    def sources_for(self, artifact_name: str) -> tuple[DownloadSource, ...]:
        """Return configured sources sorted by priority."""
        return tuple(sorted(self.sources.get(artifact_name, ()), key=lambda source: source.priority))


@dataclass
class CancellationToken:
    """Mutable cancellation token used by UI or tests."""

    cancelled: bool = False

    def cancel(self) -> None:
        """Mark the download cancelled."""
        self.cancelled = True


@dataclass(frozen=True)
class DownloadProgress:
    """Progress update emitted while streaming an artifact."""

    artifact_name: str
    bytes_downloaded: int
    total_bytes: int | None
    percent: float | None
    message: str


@dataclass(frozen=True)
class DownloadRequest:
    """Download request for one backend artifact."""

    artifact_name: str
    destination: Path
    expected_sha256: str | None = None
    sources: tuple[DownloadSource, ...] = ()
    timeout_seconds: int = 60
    retries: int = 2
    chunk_size: int = 1024 * 64
    resume: bool = True
    cleanup_partial_on_failure: bool = True


@dataclass(frozen=True)
class ManagedDownloadResult:
    """Result from a managed artifact download."""

    success: bool
    message: str
    path: Path
    source_url: str = ""
    attempts: int = 0
    bytes_downloaded: int = 0
    sha256: str | None = None
    cache_hit: bool = False
    cancelled: bool = False


ProgressCallback = Callable[[DownloadProgress], None]
UrlOpener = Callable[[urllib.request.Request, int], BinaryIO]


class DownloadManager:
    """Stream, resume, retry, verify, and cache backend downloads."""

    def __init__(self, provider: ArtifactProvider | None = None, opener: UrlOpener | None = None) -> None:
        self.provider = provider
        self.opener = opener or _default_opener

    def download(self, request: DownloadRequest, progress_callback: ProgressCallback | None = None, cancel_token: CancellationToken | None = None) -> ManagedDownloadResult:
        """Download one artifact with retries, cache reuse, and checksum verification."""
        sources = request.sources or (self.provider.sources_for(request.artifact_name) if self.provider else ())
        if not sources:
            return ManagedDownloadResult(False, "No download sources are configured for this artifact.", request.destination)
        cached = self._check_cache(request)
        if cached is not None:
            return cached

        request.destination.parent.mkdir(parents=True, exist_ok=True)
        partial_path = _partial_path(request.destination)
        attempts = 0
        last_error = ""
        for source in tuple(sorted(sources, key=lambda item: item.priority)):
            for _ in range(request.retries + 1):
                attempts += 1
                if cancel_token and cancel_token.cancelled:
                    _cleanup_partial(partial_path, request.cleanup_partial_on_failure)
                    return ManagedDownloadResult(False, "Download cancelled before starting.", request.destination, source.url, attempts, cancelled=True)
                try:
                    return self._download_from_source(request, source, partial_path, attempts, progress_callback, cancel_token)
                except _RetryableDownloadError as exc:
                    last_error = str(exc)
                    _cleanup_partial(partial_path, request.cleanup_partial_on_failure)
                except (OSError, urllib.error.URLError) as exc:
                    last_error = str(exc)
                    _cleanup_partial(partial_path, request.cleanup_partial_on_failure)
        return ManagedDownloadResult(False, f"Download failed after {attempts} attempt(s): {last_error}", request.destination, attempts=attempts)

    def _check_cache(self, request: DownloadRequest) -> ManagedDownloadResult | None:
        if not request.destination.exists():
            return None
        if request.expected_sha256:
            checksum = verify_checksum(request.destination, ChecksumPolicy(expected=request.expected_sha256, required=True))
            if checksum.passed():
                return ManagedDownloadResult(True, "Using cached artifact with matching checksum.", request.destination, attempts=0, sha256=checksum.actual, cache_hit=True)
            return None
        return ManagedDownloadResult(True, "Using cached artifact; no checksum was configured.", request.destination, attempts=0, sha256=sha256_file(request.destination), cache_hit=True)

    def _download_from_source(
        self,
        request: DownloadRequest,
        source: DownloadSource,
        partial_path: Path,
        attempts: int,
        progress_callback: ProgressCallback | None,
        cancel_token: CancellationToken | None,
    ) -> ManagedDownloadResult:
        resume_from = partial_path.stat().st_size if request.resume and partial_path.exists() else 0
        headers = {"Range": f"bytes={resume_from}-"} if resume_from else {}
        url_request = urllib.request.Request(source.url, headers=headers)
        total_bytes: int | None = None
        bytes_downloaded = resume_from
        with self.opener(url_request, request.timeout_seconds) as response:
            total_header = response.headers.get("Content-Length") if hasattr(response, "headers") else None
            if total_header and total_header.isdigit():
                total_bytes = int(total_header) + resume_from
            mode = "ab" if resume_from else "wb"
            with partial_path.open(mode) as handle:
                while True:
                    if cancel_token and cancel_token.cancelled:
                        _cleanup_partial(partial_path, request.cleanup_partial_on_failure)
                        return ManagedDownloadResult(False, "Download cancelled.", request.destination, source.url, attempts, bytes_downloaded, cancelled=True)
                    chunk = response.read(request.chunk_size)
                    if not chunk:
                        break
                    handle.write(chunk)
                    bytes_downloaded += len(chunk)
                    if progress_callback:
                        percent = (bytes_downloaded / total_bytes * 100.0) if total_bytes else None
                        progress_callback(DownloadProgress(request.artifact_name, bytes_downloaded, total_bytes, percent, "Downloading"))
        partial_path.replace(request.destination)
        checksum = sha256_file(request.destination)
        if request.expected_sha256:
            verified = verify_checksum(request.destination, ChecksumPolicy(expected=request.expected_sha256, required=True))
            if not verified.passed():
                try:
                    request.destination.unlink()
                except OSError:
                    pass
                raise _RetryableDownloadError(verified.message)
        return ManagedDownloadResult(True, "Download completed and verified.", request.destination, source.url, attempts, bytes_downloaded, checksum)


class _RetryableDownloadError(RuntimeError):
    """Internal retry signal for verification or stream failures."""


def _partial_path(destination: Path) -> Path:
    return destination.with_name(f"{destination.name}.part")


def _cleanup_partial(path: Path, enabled: bool) -> None:
    if enabled and path.exists():
        try:
            path.unlink()
        except OSError:
            pass


def _default_opener(request: urllib.request.Request, timeout_seconds: int) -> BinaryIO:
    return urllib.request.urlopen(request, timeout=timeout_seconds)  # noqa: S310 - sources come from signed installer policy.
