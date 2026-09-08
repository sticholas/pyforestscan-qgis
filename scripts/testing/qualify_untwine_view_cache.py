"""Qualification only: build a separate COPC with an explicitly supplied Untwine.

Not a production runtime dependency resolver. Original LAS is opened read-only.
"""
from __future__ import annotations
import argparse
import ctypes
from ctypes import wintypes
import hashlib
import json
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import time
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from pyforestscan_qgis.core.atomic_state import atomic_write_json
from pyforestscan_qgis.core.backend.process_env import hidden_subprocess_kwargs


def source_header(path):
    with path.open("rb") as stream:
        data = stream.read(375)
    if data[:4] != b"LASF" or len(data) < 227:
        raise ValueError("Invalid LAS header")
    count = struct.unpack_from("<I", data, 107)[0]
    if data[25] >= 4 and len(data) >= 255:
        count = struct.unpack_from("<Q", data, 247)[0] or count
    return {"points": count, "version": f"{data[24]}.{data[25]}",
            "bounds": struct.unpack_from("<6d", data, 179), "bytes": path.stat().st_size}


def fingerprint(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


class MemoryCounters(ctypes.Structure):
    _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD)] + [
        (name, ctypes.c_size_t) for name in ("PeakWorkingSetSize", "WorkingSetSize", "QuotaPeakPagedPoolUsage",
        "QuotaPagedPoolUsage", "QuotaPeakNonPagedPoolUsage", "QuotaNonPagedPoolUsage", "PagefileUsage",
        "PeakPagefileUsage", "PrivateUsage")]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--untwine", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--memory-limit-gib", type=float, default=6)
    parser.add_argument("--timeout", type=int, default=1200)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=False)
    output = args.output_dir / "view.copc.laz"
    report = {"source": str(args.source), "untwine": str(args.untwine), "output": str(output),
              "qualification_only": True, "passed": False}
    started = time.monotonic()
    process = None
    handle = None
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    get_memory = ctypes.WinDLL("psapi", use_last_error=True).GetProcessMemoryInfo
    get_memory.argtypes = [wintypes.HANDLE, ctypes.POINTER(MemoryCounters), wintypes.DWORD]
    try:
        report["source_header"] = source_header(args.source)
        if shutil.disk_usage(args.output_dir).free < args.source.stat().st_size * 4:
            raise RuntimeError("Insufficient scratch space for the qualification cache.")
        print("Fingerprinting original source with bounded buffers", flush=True)
        report["sha256_before"] = fingerprint(args.source)
        report["hash_seconds"] = round(time.monotonic() - started, 3)
        command = [str(args.untwine), "-i", str(args.source), "-o", str(output),
                   "--temp_dir", str(args.output_dir / "temp"), "--progress_debug"]
        report["command"] = command
        with (args.output_dir / "stdout.log").open("w") as stdout, (args.output_dir / "stderr.log").open("w") as stderr:
            process = subprocess.Popen(command, stdout=stdout, stderr=stderr, **hidden_subprocess_kwargs())
            handle = kernel.OpenProcess(0x410, False, process.pid)
            if not handle:
                raise RuntimeError("Cannot monitor indexer memory; refusing unmonitored conversion.")
            report["pid"] = process.pid
            peak = 0
            conversion_start = time.monotonic()
            while process.poll() is None:
                counters = MemoryCounters()
                counters.cb = ctypes.sizeof(counters)
                if not get_memory(handle, ctypes.byref(counters), counters.cb):
                    if process.poll() is None:
                        raise RuntimeError("Indexer memory monitoring failed.")
                    break
                peak = max(peak, counters.PeakWorkingSetSize, counters.PrivateUsage)
                report["peak_memory_bytes"] = peak
                if peak > args.memory_limit_gib * 1024 ** 3:
                    raise RuntimeError("Indexer exceeded the qualification memory limit.")
                if time.monotonic() - conversion_start > args.timeout:
                    raise TimeoutError("Indexer exceeded the qualification time limit.")
                atomic_write_json(args.output_dir / "index_qualification.json", report)
                time.sleep(1)
            report["index_seconds"] = round(time.monotonic() - conversion_start, 3)
            report["exit_code"] = process.wait()
            if process.returncode:
                raise RuntimeError("Untwine failed; retained stderr contains the details.")
        report["output_header"] = source_header(output)
        print("Checking source immutability", flush=True)
        report["sha256_after"] = fingerprint(args.source)
        report["passed"] = (report["sha256_before"] == report["sha256_after"] and
                            report["source_header"]["points"] == report["output_header"]["points"])
    except Exception as error:
        report["error"] = f"{type(error).__name__}: {error}"
    finally:
        if process and process.poll() is None:
            process.kill()
            process.wait()
        if handle:
            kernel.CloseHandle(handle)
        report["duration"] = round(time.monotonic() - started, 3)
        atomic_write_json(args.output_dir / "index_qualification.json", report)
    print(json.dumps(report), flush=True)
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
