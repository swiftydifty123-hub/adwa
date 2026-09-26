"""Power profile inspection and switching.

Switching uses each OS's own tool (powercfg, pmset, powerprofilesctl) and
only changes the active profile, which the user can switch back at any time.
"""

from __future__ import annotations

import shutil
import subprocess

from . import platforms

# Well-known Windows power scheme GUIDs.
WINDOWS_SCHEMES = {
    "saver": "a1841308-3541-4fab-bc81-f71556f20b4a",
    "balanced": "381b4222-f694-41f0-9685-ff5bb260df2e",
    "performance": "8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c",
}
LINUX_PROFILES = {"saver": "power-saver", "balanced": "balanced", "performance": "performance"}
MODES = tuple(WINDOWS_SCHEMES)


def _run(cmd: list[str]) -> tuple[int, str]:
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        return proc.returncode, (proc.stdout + proc.stderr).strip()
    except (OSError, subprocess.SubprocessError) as exc:
        return 1, str(exc)


def current_profile() -> str:
    os_name = platforms.current_os()
    if os_name == platforms.WINDOWS:
        return _run(["powercfg", "/getactivescheme"])[1] or "unknown"
    if os_name == platforms.MACOS:
        code, out = _run(["pmset", "-g"])
        for line in out.splitlines():
            if "lowpowermode" in line or "powermode" in line:
                return line.strip()
        return "unknown"
    if shutil.which("powerprofilesctl"):
        return _run(["powerprofilesctl", "get"])[1] or "unknown"
    try:
        with open("/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor") as f:
            return f"cpu governor: {f.read().strip()}"
    except OSError:
        return "unknown"


def set_profile(mode: str) -> tuple[bool, str]:
    if mode not in MODES:
        return False, f"Unknown mode {mode!r}; choose from {', '.join(MODES)}"
    os_name = platforms.current_os()
    if os_name == platforms.WINDOWS:
        code, out = _run(["powercfg", "/setactive", WINDOWS_SCHEMES[mode]])
    elif os_name == platforms.MACOS:
        # lowpowermode: 1 = on (saver), 0 = off. Needs sudo.
        code, out = _run(["sudo", "-n", "pmset", "-a", "lowpowermode", "1" if mode == "saver" else "0"])
    elif shutil.which("powerprofilesctl"):
        code, out = _run(["powerprofilesctl", "set", LINUX_PROFILES[mode]])
    else:
        return False, "No supported power tool found (install power-profiles-daemon)."
    return code == 0, out or "done"
