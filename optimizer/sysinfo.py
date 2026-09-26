"""Collect a snapshot of the machine's health."""

from __future__ import annotations

import platform
import time
from dataclasses import asdict, dataclass, field

import psutil


@dataclass
class ProcessInfo:
    pid: int
    name: str
    cpu_percent: float
    memory_mb: float


@dataclass
class Snapshot:
    os: str
    os_version: str
    machine: str
    cpu_model: str
    cpu_cores: int
    cpu_threads: int
    cpu_percent: float
    cpu_freq_mhz: float | None
    memory_total_gb: float
    memory_percent: float
    swap_percent: float
    disks: list[dict] = field(default_factory=list)
    battery: dict | None = None
    temperatures_c: dict[str, float] = field(default_factory=dict)
    uptime_hours: float = 0.0
    process_count: int = 0
    top_cpu: list[ProcessInfo] = field(default_factory=list)
    top_memory: list[ProcessInfo] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


GB = 1024 ** 3


def _disks() -> list[dict]:
    disks = []
    seen = set()
    for part in psutil.disk_partitions(all=False):
        if part.mountpoint in seen or "loop" in part.device or part.fstype in ("squashfs", "tmpfs", ""):
            continue
        seen.add(part.mountpoint)
        try:
            usage = psutil.disk_usage(part.mountpoint)
        except (PermissionError, OSError):
            continue
        disks.append({
            "mount": part.mountpoint,
            "fstype": part.fstype,
            "total_gb": round(usage.total / GB, 1),
            "free_gb": round(usage.free / GB, 1),
            "percent": usage.percent,
        })
    return disks


def _battery() -> dict | None:
    try:
        batt = psutil.sensors_battery()
    except (AttributeError, NotImplementedError, OSError):
        return None
    if batt is None:
        return None
    secs = batt.secsleft
    return {
        "percent": round(batt.percent, 1),
        "plugged_in": bool(batt.power_plugged),
        "minutes_left": None if secs in (psutil.POWER_TIME_UNLIMITED, psutil.POWER_TIME_UNKNOWN) or secs < 0 else secs // 60,
    }


def _temperatures() -> dict[str, float]:
    try:
        sensors = psutil.sensors_temperatures()
    except (AttributeError, NotImplementedError, OSError):
        return {}
    result = {}
    for name, entries in (sensors or {}).items():
        values = [e.current for e in entries if e.current]
        if values:
            result[name] = round(max(values), 1)
    return result


def _top_processes(limit: int) -> tuple[list[ProcessInfo], list[ProcessInfo]]:
    procs = list(psutil.process_iter(["pid", "name"]))
    for p in procs:
        try:
            p.cpu_percent(None)  # prime the counter
        except (psutil.Error, OSError):
            pass
    time.sleep(0.5)
    infos = []
    for p in procs:
        try:
            infos.append(ProcessInfo(
                pid=p.pid,
                name=p.info["name"] or "?",
                cpu_percent=round(p.cpu_percent(None), 1),
                memory_mb=round(p.memory_info().rss / 1024 ** 2, 1),
            ))
        except (psutil.Error, OSError):
            continue
    by_cpu = sorted(infos, key=lambda i: i.cpu_percent, reverse=True)[:limit]
    by_mem = sorted(infos, key=lambda i: i.memory_mb, reverse=True)[:limit]
    return by_cpu, by_mem


def collect(top: int = 5) -> Snapshot:
    freq = None
    try:
        f = psutil.cpu_freq()
        freq = round(f.current, 0) if f else None
    except (NotImplementedError, OSError, FileNotFoundError):
        pass
    mem = psutil.virtual_memory()
    top_cpu, top_mem = _top_processes(top)
    return Snapshot(
        os=platform.system(),
        os_version=platform.release(),
        machine=platform.machine(),
        cpu_model=platform.processor() or platform.machine(),
        cpu_cores=psutil.cpu_count(logical=False) or 0,
        cpu_threads=psutil.cpu_count(logical=True) or 0,
        cpu_percent=psutil.cpu_percent(interval=0.5),
        cpu_freq_mhz=freq,
        memory_total_gb=round(mem.total / GB, 1),
        memory_percent=mem.percent,
        swap_percent=psutil.swap_memory().percent,
        disks=_disks(),
        battery=_battery(),
        temperatures_c=_temperatures(),
        uptime_hours=round((time.time() - psutil.boot_time()) / 3600, 1),
        process_count=len(psutil.pids()),
        top_cpu=top_cpu,
        top_memory=top_mem,
    )
