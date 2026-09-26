"""Operating-system detection and per-OS locations."""

from __future__ import annotations

import os
import platform
import tempfile
from pathlib import Path

WINDOWS = "windows"
MACOS = "macos"
LINUX = "linux"


def current_os() -> str:
    name = platform.system().lower()
    if name.startswith("win"):
        return WINDOWS
    if name == "darwin":
        return MACOS
    return LINUX


def _env_path(var: str) -> Path | None:
    value = os.environ.get(var)
    return Path(value) if value else None


def cleanable_locations(os_name: str | None = None, home: Path | None = None) -> dict[str, list[Path]]:
    """Directories whose contents are safe to delete (caches and temp files).

    Every entry is a regenerable cache or temp location. Nothing here holds
    user documents, settings or application state.
    """
    os_name = os_name or current_os()
    home = home or Path.home()
    locations: dict[str, list[Path]] = {"System temp": [Path(tempfile.gettempdir())]}

    if os_name == WINDOWS:
        local = _env_path("LOCALAPPDATA") or home / "AppData" / "Local"
        windir = _env_path("WINDIR") or Path("C:/Windows")
        locations["User temp"] = [local / "Temp"]
        locations["Windows temp"] = [windir / "Temp"]
        locations["Thumbnail cache"] = [local / "Microsoft" / "Windows" / "Explorer"]
        locations["Crash dumps"] = [local / "CrashDumps"]
        locations["Browser caches"] = [
            local / "Google" / "Chrome" / "User Data" / "Default" / "Cache",
            local / "Microsoft" / "Edge" / "User Data" / "Default" / "Cache",
            local / "BraveSoftware" / "Brave-Browser" / "User Data" / "Default" / "Cache",
        ]
        locations["Developer caches"] = [local / "pip" / "Cache", local / "npm-cache", local / "Yarn" / "Cache"]
    elif os_name == MACOS:
        caches = home / "Library" / "Caches"
        locations["User caches"] = [caches]
        locations["User logs"] = [home / "Library" / "Logs"]
        locations["Xcode derived data"] = [home / "Library" / "Developer" / "Xcode" / "DerivedData"]
        locations["Developer caches"] = [home / ".npm" / "_cacache", home / "Library" / "Caches" / "pip"]
    else:
        cache = _env_path("XDG_CACHE_HOME") or home / ".cache"
        locations["User cache"] = [cache]
        locations["Thumbnails"] = [home / ".thumbnails"]
        locations["Developer caches"] = [home / ".npm" / "_cacache"]

    return locations


def trash_locations(os_name: str | None = None, home: Path | None = None) -> list[Path]:
    os_name = os_name or current_os()
    home = home or Path.home()
    if os_name == MACOS:
        return [home / ".Trash"]
    if os_name == LINUX:
        data = _env_path("XDG_DATA_HOME") or home / ".local" / "share"
        return [data / "Trash"]
    return []  # Windows Recycle Bin is emptied via the shell, see cleaner.empty_windows_recycle_bin
