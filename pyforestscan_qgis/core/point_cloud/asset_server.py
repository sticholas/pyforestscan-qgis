"""Read-only, capability-scoped loopback transport for an isolated renderer.

This module imports neither Qt nor scientific packages. A session authorizes
one indexed source and an explicit asset list, never an arbitrary directory.
"""
from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import io
import mimetypes
from pathlib import Path
import re
import secrets
import threading
from urllib.parse import unquote, urlsplit

MAX_RANGE_BYTES = 32 * 1024 * 1024
MAX_ASSET_BYTES = 64 * 1024 * 1024
EPT_NODE = re.compile(r"ept-(?:data|hierarchy)/[0-9]+-[0-9]+-[0-9]+-[0-9]+\.(?:laz|bin|zst|json)\Z")


def source_file(root: Path, route: str) -> Path:
    """Resolve an authorized EPT node without exposing adjacent files."""
    if route != "ept.json" and not EPT_NODE.fullmatch(route):
        raise ValueError("Not an EPT node.")
    path = (root / route).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError("Source node escapes the selected repository.")
    return path


def byte_range(value: str | None, size: int) -> tuple[int, int]:
    if value is None:
        return 0, size
    match = re.fullmatch(r"bytes=(\d+)-(\d*)", value)
    if not match:
        raise ValueError("Only one explicit byte range is supported.")
    start = int(match[1])
    stop = min(int(match[2]) + 1 if match[2] else size, size)
    if start >= stop or stop - start > MAX_RANGE_BYTES:
        raise ValueError("Invalid or oversized range.")
    return start, stop


class ViewerAssetServer:
    """A short-lived read capability; close() revokes the capability."""

    def __init__(self, *, assets: dict[str, Path | bytes], source: Path):
        self.assets = {}
        snapshot_bytes = 0
        for route, path in assets.items():
            if (not route or "\\" in route or route.startswith("/") or
                    any(part in (".", "..") for part in route.split("/"))):
                raise ValueError("Asset route must be a normalized relative path.")
            if isinstance(path, bytes):
                snapshot_bytes += len(path)
                if snapshot_bytes > MAX_ASSET_BYTES:
                    raise ValueError("Viewer asset snapshot exceeds its memory limit.")
                self.assets[route] = path
            else:
                self.assets[route] = Path(path).resolve(strict=True)
        self.source = Path(source).resolve(strict=True)
        self._virtual = {}
        self._direct = False
        self._stats_lock = threading.Lock()
        self._stats = {"source_requests": 0, "source_bytes": 0, "range_requests": 0,
                       "hierarchy_requests": 0, "point_node_requests": 0}
        if self.source.name.lower() == "ept.json":
            self.source_route = "source/ept.json"
        elif self.source.name.lower().endswith(".copc.laz"):
            self.source_route = "source/cloud.copc.laz"
        elif self.source.suffix.lower() in (".las", ".laz"):
            from .direct_source import direct_metadata
            metadata = direct_metadata(self.source)
            self._direct = True
            self.source_route = "source/ept.json"
            self._virtual = {
                "source/ept.json": json.dumps(metadata).encode("utf-8"),
                "source/ept-hierarchy/0-0-0-0.json": json.dumps({"0-0-0-0": metadata["points"]}).encode("ascii"),
            }
        else:
            raise ValueError("Viewer transport requires COPC or EPT; prepare LAS/LAZ first.")
        token = secrets.token_urlsafe(32)
        owner = self
        slots = threading.BoundedSemaphore(12)

        class Server(ThreadingHTTPServer):
            daemon_threads = True

            def get_request(self):
                sock, address = super().get_request()
                sock.settimeout(10)
                return sock, address

            def process_request(self, request, address):
                if not slots.acquire(blocking=False):
                    self.shutdown_request(request)
                    return
                try:
                    super().process_request(request, address)
                except BaseException:
                    slots.release()
                    raise

            def process_request_thread(self, request, address):
                try:
                    super().process_request_thread(request, address)
                finally:
                    slots.release()

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                # Do not leak the capability token or source filenames.
                pass

            def do_HEAD(self):
                self.do_GET(head=True)

            def do_GET(self, head=False):
                host = f"127.0.0.1:{self.server.server_port}"
                if self.headers.get("Host") != host:
                    self.send_error(403)
                    return
                origin = self.headers.get("Origin")
                if origin and origin != f"http://{host}":
                    self.send_error(403)
                    return
                route = unquote(urlsplit(self.path).path)
                prefix = f"/{token}/"
                if not route.startswith(prefix):
                    self.send_error(403)
                    return
                route = route[len(prefix):]
                try:
                    if route in owner._virtual:
                        path = None
                    elif owner._direct and route == "source/ept-data/0-0-0-0.laz":
                        path = owner.source
                    elif route == owner.source_route:
                        path = owner.source
                    elif not owner._direct and owner.source_route.endswith("ept.json") and route.startswith("source/"):
                        path = source_file(owner.source.parent, route[7:])
                    else:
                        path = owner.assets[route]
                    payload = owner._virtual[route] if path is None else path if isinstance(path, bytes) else None
                    # Open before responding: report stale/unreadable files cleanly.
                    with (io.BytesIO(payload) if payload is not None else path.open("rb")) as handle:
                        import os
                        size = len(payload) if payload is not None else os.fstat(handle.fileno()).st_size
                        value = self.headers.get("Range")
                        start, stop = byte_range(value, size)
                        is_source = route.startswith("source/")
                        if is_source and not head and stop - start > MAX_RANGE_BYTES:
                            raise ValueError("Source responses must stay within the streaming byte limit.")
                        if is_source and not head:
                            with owner._stats_lock:
                                owner._stats["source_requests"] += 1
                                owner._stats["range_requests"] += int(value is not None)
                                owner._stats["hierarchy_requests"] += int("/ept-hierarchy/" in route)
                                owner._stats["point_node_requests"] += int("/ept-data/" in route)
                        self.send_response(206 if value else 200)
                        self.send_header("Content-Type", {
                            ".js": "application/javascript",
                            ".wasm": "application/wasm",
                            ".html": "text/html; charset=utf-8",
                            ".json": "application/json",
                        }.get(Path(route).suffix, mimetypes.guess_type(route)[0] or "application/octet-stream"))
                        self.send_header("Content-Length", str(stop - start))
                        self.send_header("Accept-Ranges", "bytes")
                        self.send_header("Cache-Control", "no-store")
                        self.send_header("X-Content-Type-Options", "nosniff")
                        self.send_header("Referrer-Policy", "no-referrer")
                        if value:
                            self.send_header("Content-Range", f"bytes {start}-{stop - 1}/{size}")
                        self.end_headers()
                        if not head:
                            handle.seek(start)
                            remaining = stop - start
                            while remaining:
                                chunk = handle.read(min(65536, remaining))
                                if not chunk:
                                    break
                                self.wfile.write(chunk)
                                if is_source:
                                    with owner._stats_lock:
                                        owner._stats["source_bytes"] += len(chunk)
                                remaining -= len(chunk)
                except KeyError:
                    self.send_error(404)
                except ValueError:
                    self.send_error(416 if self.headers.get("Range") else 403)
                except (FileNotFoundError, PermissionError, IsADirectoryError):
                    self.send_error(404)
                except (BrokenPipeError, ConnectionResetError, TimeoutError):
                    pass

        self._server = Server(("127.0.0.1", 0), Handler)
        self.base_url = f"http://127.0.0.1:{self._server.server_port}/{token}/"
        self._thread = threading.Thread(target=self._server.serve_forever,
                                        kwargs={"poll_interval": .05}, daemon=True)
        self._closed = False
        self._thread.start()

    def stats(self):
        with self._stats_lock:
            return dict(self._stats)

    def close(self):
        if not self._closed:
            self._closed = True
            self._server.shutdown()
            self._server.server_close()
            self._thread.join(timeout=2)

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
