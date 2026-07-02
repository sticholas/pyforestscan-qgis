"""Download helpers for PBM installer artifacts."""

from __future__ import annotations

import shutil
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable


@dataclass(frozen=True)
class DownloadResult:
    """Result from an artifact download attempt."""

    success: bool
    message: str
    path: Path
    url: str
    attempts: int = 0


Downloader = Callable[[str, Path], None]


def download_path(downloads_dir: Path, archive_name: str) -> Path:
    """Return the cache path for a downloaded artifact."""
    return downloads_dir / archive_name


def download_file(url: str, destination: Path, retries: int = 2, downloader: Downloader | None = None) -> DownloadResult:
    """Download a URL to a destination path with simple retry behavior."""
    if not url:
        return DownloadResult(success=False, message="No download URL is configured for this platform.", path=destination, url=url, attempts=0)
    destination.parent.mkdir(parents=True, exist_ok=True)
    action = downloader or _default_downloader
    attempts = 0
    last_error = ""
    for attempt in range(retries + 1):
        attempts = attempt + 1
        try:
            action(url, destination)
            if destination.exists():
                return DownloadResult(success=True, message="Download completed.", path=destination, url=url, attempts=attempts)
            last_error = "Downloader returned without creating the destination file."
        except Exception as exc:  # noqa: BLE001 - installer reports failures rather than crashing.
            last_error = str(exc)
    return DownloadResult(success=False, message=f"Download failed after {attempts} attempt(s): {last_error}", path=destination, url=url, attempts=attempts)


def _default_downloader(url: str, destination: Path) -> None:
    with urllib.request.urlopen(url, timeout=60) as response:  # noqa: S310 - URL is selected by installer policy.
        with destination.open("wb") as handle:
            shutil.copyfileobj(response, handle)
