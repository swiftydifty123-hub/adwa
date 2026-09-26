"""Turn a snapshot into a health score and concrete recommendations."""

from __future__ import annotations

from dataclasses import dataclass

from .sysinfo import Snapshot

# Processes that are normal to see near the top and not worth flagging.
IGNORED_PROCESSES = {"system idle process", "idle", "kernel_task", "system", "swapper"}


@dataclass
class Finding:
    severity: str  # "critical", "warning", "info"
    title: str
    advice: str
    penalty: int


def analyze(snap: Snapshot, startup_count: int | None = None, junk_bytes: int | None = None) -> list[Finding]:
    f: list[Finding] = []

    if snap.memory_percent >= 90:
        f.append(Finding("critical", f"RAM almost full ({snap.memory_percent:.0f}%)",
                         "Close heavy apps or browser tabs; consider more RAM.", 20))
    elif snap.memory_percent >= 75:
        f.append(Finding("warning", f"RAM usage high ({snap.memory_percent:.0f}%)",
                         "Close apps you are not using.", 10))

    if snap.swap_percent >= 50:
        f.append(Finding("warning", f"Heavy swap use ({snap.swap_percent:.0f}%)",
                         "The system is paging to disk, which is slow. Free up RAM.", 8))

    if snap.cpu_percent >= 85:
        f.append(Finding("critical", f"CPU pegged ({snap.cpu_percent:.0f}%)",
                         "Check the top CPU processes below and close runaway apps.", 15))

    for d in snap.disks:
        if d["percent"] >= 95:
            f.append(Finding("critical", f"Disk {d['mount']} nearly full ({d['percent']:.0f}%)",
                             "Run `clean --apply` and review `bigfiles`. SSDs slow down when full.", 20))
        elif d["percent"] >= 85:
            f.append(Finding("warning", f"Disk {d['mount']} filling up ({d['percent']:.0f}%)",
                             "Keep at least 15% free for best SSD performance.", 10))

    hot = {k: v for k, v in snap.temperatures_c.items() if v >= 85}
    if hot:
        name, temp = max(hot.items(), key=lambda kv: kv[1])
        f.append(Finding("critical", f"Running hot ({name}: {temp:.0f}°C)",
                         "Clean the vents/fans, use a hard surface or cooling pad. Heat causes throttling.", 15))

    if snap.uptime_hours >= 24 * 7:
        f.append(Finding("warning", f"Not restarted in {snap.uptime_hours / 24:.0f} days",
                         "Restart to clear memory leaks and apply pending updates.", 5))

    b = snap.battery
    if b and not b["plugged_in"] and b["percent"] <= 20:
        f.append(Finding("warning", f"Battery low ({b['percent']:.0f}%)",
                         "Switch to power saver: `power saver`.", 5))

    if startup_count is not None and startup_count >= 10:
        f.append(Finding("warning", f"{startup_count} startup programs",
                         "Disable the ones you do not need to boot faster (see `startup`).", 8))

    if junk_bytes is not None and junk_bytes >= 1024 ** 3:
        f.append(Finding("info", f"{junk_bytes / 1024 ** 3:.1f} GB of cleanable junk",
                         "Run `clean --apply` to reclaim it.", 5))

    hogs = [p for p in snap.top_cpu if p.cpu_percent >= 50 and p.name.lower() not in IGNORED_PROCESSES]
    for p in hogs[:2]:
        f.append(Finding("info", f"{p.name} using {p.cpu_percent:.0f}% CPU",
                         f"If you are not using it, close it (PID {p.pid}).", 3))

    return f


def score(findings: list[Finding]) -> int:
    return max(0, 100 - sum(x.penalty for x in findings))


def grade(value: int) -> str:
    for threshold, letter in ((90, "A"), (80, "B"), (65, "C"), (50, "D")):
        if value >= threshold:
            return letter
    return "F"
