"""List programs that launch at login (read-only)."""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

from . import platforms


@dataclass
class StartupItem:
    name: str
    command: str
    source: str


def _windows_items() -> list[StartupItem]:
    items: list[StartupItem] = []
    try:
        import winreg  # type: ignore[import-not-found]
    except ImportError:
        return items
    keys = [
        (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", "HKCU Run"),
        (winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\Run", "HKLM Run"),
    ]
    for hive, path, label in keys:
        try:
            with winreg.OpenKey(hive, path) as key:
                i = 0
                while True:
                    try:
                        name, value, _ = winreg.EnumValue(key, i)
                    except OSError:
                        break
                    items.append(StartupItem(name, str(value), label))
                    i += 1
        except OSError:
            continue
    appdata = os.environ.get("APPDATA")
    if appdata:
        folder = Path(appdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
        if folder.is_dir():
            for f in folder.iterdir():
                items.append(StartupItem(f.stem, str(f), "Startup folder"))
    return items


def _macos_items(home: Path) -> list[StartupItem]:
    items = []
    for folder in (home / "Library" / "LaunchAgents", Path("/Library/LaunchAgents")):
        if folder.is_dir():
            for f in sorted(folder.glob("*.plist")):
                items.append(StartupItem(f.stem, str(f), str(folder)))
    try:
        out = subprocess.run(
            ["osascript", "-e", 'tell application "System Events" to get the name of every login item'],
            capture_output=True, text=True, timeout=10,
        ).stdout.strip()
        for name in filter(None, (n.strip() for n in out.split(","))):
            items.append(StartupItem(name, "", "Login items"))
    except (OSError, subprocess.SubprocessError):
        pass
    return items


def _linux_items(home: Path) -> list[StartupItem]:
    items = []
    config = Path(os.environ.get("XDG_CONFIG_HOME", home / ".config"))
    for folder in (config / "autostart", Path("/etc/xdg/autostart")):
        if not folder.is_dir():
            continue
        for f in sorted(folder.glob("*.desktop")):
            name, command, hidden = f.stem, "", False
            try:
                for line in f.read_text(errors="ignore").splitlines():
                    if line.startswith("Name=") and name == f.stem:
                        name = line[5:]
                    elif line.startswith("Exec="):
                        command = line[5:]
                    elif line.strip().lower() in ("hidden=true", "x-gnome-autostart-enabled=false"):
                        hidden = True
            except OSError:
                continue
            if not hidden:
                items.append(StartupItem(name, command, str(folder)))
    return items


def list_startup_items(os_name: str | None = None, home: Path | None = None) -> list[StartupItem]:
    os_name = os_name or platforms.current_os()
    home = home or Path.home()
    if os_name == platforms.WINDOWS:
        return _windows_items()
    if os_name == platforms.MACOS:
        return _macos_items(home)
    return _linux_items(home)
