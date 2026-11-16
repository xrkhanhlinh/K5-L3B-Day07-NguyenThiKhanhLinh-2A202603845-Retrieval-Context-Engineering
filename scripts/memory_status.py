"""Read-only Windows memory availability for local-model sizing."""
import ctypes
import json
from ctypes import wintypes


class MemoryStatus(ctypes.Structure):
    _fields_ = [("length", wintypes.DWORD), ("load", wintypes.DWORD)] + [
        (name, ctypes.c_ulonglong) for name in ("total", "available", "pagefile", "available_pagefile",
                                             "virtual", "available_virtual", "extended")]


if __name__ == "__main__":
    status = MemoryStatus()
    status.length = ctypes.sizeof(status)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
        raise OSError("GlobalMemoryStatusEx failed")
    print(json.dumps({"physical_ram_gib": status.total / 1024**3, "available_ram_gib": status.available / 1024**3,
                      "memory_load_percent": status.load}, indent=2))
