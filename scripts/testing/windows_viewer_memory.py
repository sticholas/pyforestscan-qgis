"""Read-only Windows process-tree memory sampling for renderer QA."""
import ctypes
from ctypes import wintypes
import os


def tree_memory(pid):
    if os.name != "nt" or not pid:
        return None
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    class Entry(ctypes.Structure):
        _fields_ = [("size", wintypes.DWORD), ("usage", wintypes.DWORD), ("pid", wintypes.DWORD),
                    ("heap", ctypes.c_size_t), ("module", wintypes.DWORD), ("threads", wintypes.DWORD),
                    ("parent", wintypes.DWORD), ("priority", wintypes.LONG), ("flags", wintypes.DWORD),
                    ("exe", wintypes.WCHAR * 260)]
    kernel.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
    kernel.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    kernel.Process32FirstW.argtypes = [wintypes.HANDLE, ctypes.POINTER(Entry)]
    kernel.Process32NextW.argtypes = [wintypes.HANDLE, ctypes.POINTER(Entry)]
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    snapshot = kernel.CreateToolhelp32Snapshot(2, 0)
    if snapshot == ctypes.c_void_p(-1).value:
        return None
    parents = {}
    try:
        entry = Entry()
        entry.size = ctypes.sizeof(entry)
        valid = kernel.Process32FirstW(snapshot, ctypes.byref(entry))
        while valid:
            parents[entry.pid] = entry.parent
            valid = kernel.Process32NextW(snapshot, ctypes.byref(entry))
    finally:
        kernel.CloseHandle(snapshot)
    owned = {pid}
    while True:
        expanded = owned | {child for child, parent in parents.items() if parent in owned}
        if expanded == owned:
            break
        owned = expanded
    from qualify_untwine_view_cache import MemoryCounters
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    get_memory = ctypes.WinDLL("psapi", use_last_error=True).GetProcessMemoryInfo
    get_memory.argtypes = [wintypes.HANDLE, ctypes.POINTER(MemoryCounters), wintypes.DWORD]
    result = {"private_bytes": 0, "working_set_bytes": 0, "processes": 0}
    for child in owned:
        handle = kernel.OpenProcess(0x410, False, child)
        if not handle:
            continue
        try:
            counters = MemoryCounters()
            counters.cb = ctypes.sizeof(counters)
            if get_memory(handle, ctypes.byref(counters), counters.cb):
                result["private_bytes"] += counters.PrivateUsage
                result["working_set_bytes"] += counters.WorkingSetSize
                result["processes"] += 1
        finally:
            kernel.CloseHandle(handle)
    return result
