"""Windows OS-enforced limits for the one owned indexing process."""
from __future__ import annotations
import os


class IndexerMemoryGuard:
    """A Job Object prevents an indexer from exhausting Windows private memory.

    Other platforms retain process isolation but do not claim this Windows
    allocation limit. No global/system limits or QGIS job objects are changed.
    """

    def __init__(self, process, maximum_bytes=6 * 1024 ** 3):
        self.handle = None
        self.kernel = None
        if os.name != "nt":
            return
        import ctypes
        from ctypes import wintypes
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)

        class Basic(ctypes.Structure):
            _fields_ = [("process_time", ctypes.c_longlong), ("job_time", ctypes.c_longlong),
                ("flags", wintypes.DWORD), ("minimum_ws", ctypes.c_size_t),
                ("maximum_ws", ctypes.c_size_t), ("processes", wintypes.DWORD),
                ("affinity", ctypes.c_size_t), ("priority", wintypes.DWORD),
                ("scheduling", wintypes.DWORD)]

        class Counters(ctypes.Structure):
            _fields_ = [(name, ctypes.c_ulonglong) for name in
                        ("read_ops", "write_ops", "other_ops", "read_bytes", "write_bytes", "other_bytes")]

        class Limits(ctypes.Structure):
            _fields_ = [("basic", Basic), ("io", Counters), ("process_memory", ctypes.c_size_t),
                        ("job_memory", ctypes.c_size_t), ("peak_process", ctypes.c_size_t),
                        ("peak_job", ctypes.c_size_t)]

        kernel.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
        kernel.CreateJobObjectW.restype = wintypes.HANDLE
        kernel.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int,
                                                   ctypes.c_void_p, wintypes.DWORD]
        kernel.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        handle = kernel.CreateJobObjectW(None, None)
        if not handle:
            raise RuntimeError("Cannot create the indexer's private-memory guard.")
        limits = Limits()
        limits.basic.flags = 0x100 | 0x2000  # PROCESS_MEMORY | KILL_ON_JOB_CLOSE
        limits.process_memory = int(maximum_bytes)
        try:
            if not kernel.SetInformationJobObject(handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)):
                raise RuntimeError("Cannot set the indexer's private-memory limit.")
            if not kernel.AssignProcessToJobObject(handle, wintypes.HANDLE(int(process._handle))):
                raise RuntimeError("Cannot isolate the indexer in its memory-limited job.")
        except Exception:
            kernel.CloseHandle(handle)
            raise
        self.handle, self.kernel = handle, kernel

    def close(self):
        if self.handle is not None:
            self.kernel.CloseHandle(self.handle)
            self.handle = None
