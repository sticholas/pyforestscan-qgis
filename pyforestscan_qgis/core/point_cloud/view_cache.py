"""Source-bound view cache records; never an edit/session storage manager."""
from __future__ import annotations

from contextlib import contextmanager
import json
import hashlib
from pathlib import Path
import re
import shutil
import time
from uuid import uuid4
import os

from ..atomic_state import atomic_write_json
from .view_strategy import CacheState, cache_key


def file_digest(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def process_alive(pid):
    """Conservative liveness: uncertainty never authorizes lock recovery."""
    if pid <= 0:
        return True
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel.OpenProcess.restype = wintypes.HANDLE
        kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        handle = kernel.OpenProcess(0x100000, False, pid)
        if not handle:
            return ctypes.get_last_error() != 87
        try:
            return kernel.WaitForSingleObject(handle, 0) != 0
        finally:
            kernel.CloseHandle(handle)
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except OSError:
        return True

class ViewCache:
    """Own only hash-named entries below an explicitly dedicated cache root.

    An interrupted BUILDING record is never reused. Locks are conservative:
    orphan lock removal requires confirmed process termination, never age alone.
    """

    def __init__(self, root: Path):
        self.root = Path(root).resolve()

    def entry(self, identity):
        return self.root / cache_key(identity)

    def _owned(self, path):
        path = Path(path)
        if (path.is_symlink() or path.resolve().parent != self.root or
                not re.fullmatch(r"[0-9a-f]{64}", path.name)):
            raise ValueError("Refusing a path outside managed viewer cache entries.")
        return path

    def read(self, identity):
        path = self._owned(self.entry(identity))
        try:
            record_path = path / "cache.json"
            if record_path.is_symlink() or record_path.stat().st_size > 128 * 1024:
                return None
            record = json.loads(record_path.read_text(encoding="utf-8"))
            if not isinstance(record, dict) or record.get("identity") != identity:
                return None
            return record
        except (OSError, ValueError, TypeError):
            return None

    def recover_interrupted(self, identity, *, alive=process_alive):
        path = self._owned(self.entry(identity))
        lock = path / "build.lock"
        if not lock.exists():
            return False
        recovery = path / "recovery.lock"
        try:
            with recovery.open("x"):
                pass
        except FileExistsError:
            return False
        try:
            if lock.is_symlink() or lock.stat().st_size > 32:
                return False
            try:
                pid = int(lock.read_text(encoding="ascii"))
            except (OSError, ValueError):
                return False
            if alive(pid):
                return False
            lock.unlink()
            return True
        finally:
            recovery.unlink(missing_ok=True)

    @contextmanager
    def lease(self, key):
        path = self._owned(self.root / key)
        lock = path / "build.lock"
        with lock.open("x", encoding="ascii") as stream:
            stream.write(str(os.getpid()))
        lease = path / ("view-" + uuid4().hex + ".lock")
        try:
            if not (path / "view.copc.laz").is_file():
                raise ValueError("View cache was removed; reopen the original source.")
            with lease.open("x", encoding="ascii") as stream:
                stream.write(str(os.getpid()))
        finally:
            lock.unlink(missing_ok=True)
        try:
            yield
        finally:
            lease.unlink(missing_ok=True)

    def reusable(self, identity, verify):
        path = self._owned(self.entry(identity))
        lock = path / "build.lock"
        try:
            with lock.open('x', encoding='ascii') as stream:
                stream.write(str(os.getpid()))
        except (FileExistsError, FileNotFoundError):
            return None
        try:
            record = self.read(identity)
            output = path / "view.copc.laz"
            if not record or record.get("state") != CacheState.VALID.value:
                return None
            try:
                valid = (not output.is_symlink() and output.is_file() and
                         output.stat().st_size == record.get('output_bytes') and
                         record.get('output_sha256') == file_digest(output) and
                         verify(output, identity))
            except (OSError, ValueError, RuntimeError):
                valid = False
            if not valid:
                self.record(identity, CacheState.STALE, reason="Cache integrity check failed; rebuild from original.")
                return None
            self.record(identity, CacheState.VALID, **{
                key: value for key, value in record.items()
                if key not in ("identity", "state", "last_used")
            })
            return output
        finally:
            lock.unlink(missing_ok=True)

    def record(self, identity, state, **details):
        path = self._owned(self.entry(identity))
        path.mkdir(parents=True, exist_ok=True)
        atomic_write_json(path / "cache.json", {
            **details, "identity": identity, "state": CacheState(state).value,
            "last_used": time.time(),
        })

    @contextmanager
    def build(self, identity):
        path = self._owned(self.entry(identity))
        path.mkdir(parents=True, exist_ok=True)
        lock = path / "build.lock"
        # O_EXCL via x mode. Never steal a lock just because a timer expired.
        with lock.open("x", encoding="ascii") as stream:
            stream.write(str(os.getpid()))
        staging = path / "temp"
        started = False
        try:
            if any(path.glob("view-*.lock")):
                raise RuntimeError("This view cache is in use. Close its viewer before rebuilding.")
            if staging.is_symlink():
                raise ValueError("Unsafe cache temporary directory.")
            if staging.exists():
                shutil.rmtree(staging)
            staging.mkdir()
            self.record(identity, CacheState.BUILDING)
            started = True
            yield staging
        except BaseException as error:
            if started:
                self.record(identity, CacheState.FAILED, reason=str(error)[:2000])
            raise
        finally:
            # Only this entry's owned scratch directory; never source/session paths.
            if started and staging.exists() and not staging.is_symlink():
                shutil.rmtree(staging)
            lock.unlink(missing_ok=True)

    def publish(self, identity, staged_output, *, verify):
        path = self._owned(self.entry(identity))
        staged = Path(staged_output)
        if (staged.is_symlink() or
                staged.resolve().parent != (path / "temp").resolve()):
            raise ValueError("Only an owned staged cache can be published.")
        if not verify(staged, identity):
            raise ValueError("Cache failed point/dimension/CRS verification.")
        output = path / "view.copc.laz"
        if output.is_symlink():
            raise ValueError("Unsafe cache output.")
        staged.replace(output)
        self.record(identity, CacheState.VALID, output_bytes=output.stat().st_size,
                    output_sha256=file_digest(output))
        return output

    def cleanup(self, *, max_bytes, protected_keys=(), older_than_seconds=86400):
        """Evict old unused cache entries, excluding active or referenced entries."""
        if type(max_bytes) is not int or max_bytes < 0 or older_than_seconds < 0:
            raise ValueError("Invalid cache budget.")
        protected = set(protected_keys)
        candidates = []
        if not self.root.exists():
            return []
        for path in self.root.iterdir():
            if path.name in protected or path.is_symlink() or not path.is_dir():
                continue
            if not re.fullmatch(r"[0-9a-f]{64}", path.name) or (path / "build.lock").exists():
                continue
            try:
                manifest = path / "cache.json"
                if manifest.is_symlink() or manifest.stat().st_size > 128 * 1024:
                    continue
                record = json.loads(manifest.read_text(encoding="utf-8"))
                if cache_key(record["identity"]) != path.name:
                    continue
                state = CacheState(record["state"])
                if state == CacheState.BUILDING:
                    continue
                # Refuse unexpected content, including journals and exported files.
                if any(p.name not in ("cache.json", "view.copc.laz", "indexer.log") or p.is_symlink()
                       or not p.is_file() for p in path.iterdir()):
                    continue
                size = sum(p.stat().st_size for p in path.iterdir())
                candidates.append((float(record["last_used"]), size, path, record))
            except (OSError, KeyError, TypeError, ValueError):
                continue
        total = sum(item[1] for item in candidates)
        removed = []
        for last_used, size, path, record in sorted(candidates):
            if time.time() - last_used < older_than_seconds:
                continue
            stale = record["state"] in (CacheState.STALE.value, CacheState.FAILED.value,
                                        CacheState.PURGEABLE.value)
            if not stale and total <= max_bytes:
                continue
            self._owned(path)
            if (path / "build.lock").exists():
                continue
            # A cleanup lock prevents racing a compliant builder.
            lock = path / "build.lock"
            try:
                with lock.open("x", encoding="ascii") as stream:
                    stream.write(str(os.getpid()))
            except (FileExistsError, FileNotFoundError):
                continue
            try:
                if any(p.name not in ("cache.json", "view.copc.laz", "indexer.log", "build.lock")
                       or p.is_symlink() or not p.is_file() for p in path.iterdir()):
                    continue
                for name in ("view.copc.laz", "cache.json", "indexer.log"):
                    (path / name).unlink(missing_ok=True)
            finally:
                lock.unlink(missing_ok=True)
            try:
                path.rmdir()
            except OSError:
                # A new compliant builder may have acquired the released lock.
                # Never recursively remove an entry that has been repopulated.
                pass
            total -= size
            removed.append(path.name)
        return removed
