"""Read-only Windows virtual/working-set attribution for QA, not production."""
import ctypes
from ctypes import wintypes
import os
import time


def memory_composition(pid):
    if os.name != "nt":
        return {"available": False}
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    psapi = ctypes.WinDLL("psapi", use_last_error=True)
    class Region(ctypes.Structure):
        _fields_ = [("base", ctypes.c_void_p), ("allocation_base", ctypes.c_void_p),
            ("allocation_protect", wintypes.DWORD), ("size", ctypes.c_size_t),
            ("state", wintypes.DWORD), ("protect", wintypes.DWORD), ("kind", wintypes.DWORD)]
    class Page(ctypes.Structure):
        _fields_ = [("address", ctypes.c_void_p), ("attributes", ctypes.c_size_t)]
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.VirtualQueryEx.argtypes = [wintypes.HANDLE, ctypes.c_void_p,
                                      ctypes.POINTER(Region), ctypes.c_size_t]
    kernel.VirtualQueryEx.restype = ctypes.c_size_t
    psapi.QueryWorkingSetEx.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD]
    handle = kernel.OpenProcess(0x410, False, pid)
    if not handle:
        return {"available": False, "error": ctypes.get_last_error()}
    started = time.monotonic()
    result = {"available": True, "committed": {}, "resident": {},
              "shared_resident": {}, "pages_queried": 0, "failed_queries": 0,
              "scope": "non-atomic process snapshot; not system file-cache attribution"}
    cursor = 0
    names = {0x20000: "private", 0x40000: "mapped", 0x1000000: "image"}
    # Windows x64 uses 4 KiB pages. Verify against Python's OS allocation API.
    import mmap
    page_size = mmap.PAGESIZE
    try:
        while True:
            region = Region()
            if not kernel.VirtualQueryEx(handle, ctypes.c_void_p(cursor), ctypes.byref(region), ctypes.sizeof(region)):
                break
            base = int(region.base or 0)
            if not region.size or base + region.size <= cursor:
                break
            cursor = base + region.size
            if region.state != 0x1000:
                continue
            name = names.get(region.kind, "other")
            result["committed"][name] = result["committed"].get(name, 0) + region.size
            for offset in range(base, cursor, page_size * 4096):
                count = min(4096, (cursor - offset + page_size - 1) // page_size)
                pages = (Page * count)()
                for i in range(count):
                    pages[i].address = offset + i * page_size
                if not psapi.QueryWorkingSetEx(handle, pages, ctypes.sizeof(pages)):
                    result["failed_queries"] += 1
                    continue
                result["pages_queried"] += count
                valid = sum(bool(item.attributes & 1) for item in pages)
                shared = sum(bool(item.attributes & 1 and item.attributes & (1 << 15)) for item in pages)
                result["resident"][name] = result["resident"].get(name, 0) + valid * page_size
                result["shared_resident"][name] = result["shared_resident"].get(name, 0) + shared * page_size
    finally:
        kernel.CloseHandle(handle)
    result["sampling_seconds"] = time.monotonic() - started
    return result
