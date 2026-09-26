"""Command-line interface: `python -m optimizer <command>`."""

from __future__ import annotations

import argparse
import json
import os
import sys
import webbrowser
from pathlib import Path

from . import __version__, advisor, cleaner, platforms, power, report, startup, sysinfo


def _supports_color() -> bool:
    if os.environ.get("NO_COLOR") or not sys.stdout.isatty():
        return False
    if os.name == "nt":
        os.system("")  # enables ANSI escape handling in Windows consoles
    return True


COLOR = _supports_color()
SEV = {"critical": "31", "warning": "33", "info": "36"}


def c(text: str, code: str) -> str:
    return f"\033[{code}m{text}\033[0m" if COLOR else text


def human(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} PB"


def bar(percent: float, width: int = 24) -> str:
    filled = int(round(percent / 100 * width))
    code = "31" if percent >= 90 else "33" if percent >= 75 else "32"
    return c("█" * filled, code) + c("░" * (width - filled), "90")


def header(title: str) -> None:
    print("\n" + c(f"━━ {title} ", "1;35") + c("━" * max(0, 50 - len(title)), "35"))


# ---------------------------------------------------------------- commands

def cmd_scan(args) -> int:
    print(c("Scanning your laptop…", "90"))
    snap = sysinfo.collect()
    items = startup.list_startup_items()
    junk = cleaner.scan_and_clean(cleaner.default_locations(), apply=False)
    findings = advisor.analyze(snap, startup_count=len(items), junk_bytes=junk.total_bytes)
    health = advisor.score(findings)

    if args.json:
        print(json.dumps({"health": health, "snapshot": snap.to_dict(),
                          "findings": [f.__dict__ for f in findings],
                          "junk_bytes": junk.total_bytes, "startup_items": len(items)}, indent=2))
        return 0

    header("System")
    print(f"  {snap.os} {snap.os_version} ({snap.machine}) · up {snap.uptime_hours} h · {snap.process_count} processes")
    print(f"  CPU    {bar(snap.cpu_percent)} {snap.cpu_percent:5.1f}%  {snap.cpu_cores}C/{snap.cpu_threads}T"
          + (f" @ {snap.cpu_freq_mhz:.0f} MHz" if snap.cpu_freq_mhz else ""))
    print(f"  RAM    {bar(snap.memory_percent)} {snap.memory_percent:5.1f}%  of {snap.memory_total_gb} GB")
    print(f"  Swap   {bar(snap.swap_percent)} {snap.swap_percent:5.1f}%")
    for d in snap.disks:
        print(f"  Disk   {bar(d['percent'])} {d['percent']:5.1f}%  {d['mount']} ({d['free_gb']} GB free)")
    if snap.battery:
        b = snap.battery
        state = "charging" if b["plugged_in"] else (f"{b['minutes_left']} min left" if b["minutes_left"] else "on battery")
        print(f"  Batt   {bar(100 - b['percent'])} {b['percent']:5.1f}%  {state}")
    if snap.temperatures_c:
        print("  Temps  " + ", ".join(f"{k} {v:.0f}°C" for k, v in snap.temperatures_c.items()))
    print(f"  Junk   {human(junk.total_bytes)} cleanable · {len(items)} startup programs")

    header("Top processes")
    threads = max(snap.cpu_threads, 1)
    for p in snap.top_memory:
        print(f"  {p.name[:28]:<28} {p.memory_mb:>9.1f} MB  {p.cpu_percent / threads:>5.1f}% CPU")

    header("Findings")
    if not findings:
        print(c("  ✔ No issues found. Your laptop is in great shape.", "32"))
    for f in findings:
        print(f"  {c('●', SEV[f.severity])} {f.title}\n    {c(f.advice, '90')}")

    color = "32" if health >= 80 else "33" if health >= 60 else "31"
    print("\n  " + c(f"HEALTH SCORE: {health}/100  (grade {advisor.grade(health)})", "1;" + color) + "\n")

    if args.report:
        path = Path(args.report).resolve()
        path.write_text(report.render_html(snap, findings, health), encoding="utf-8")
        print(f"  Report saved to {path}")
        if args.open:
            webbrowser.open(path.as_uri())
    return 0


def cmd_clean(args) -> int:
    locations = cleaner.default_locations(include_trash=args.trash)
    if args.apply and not args.yes:
        preview = cleaner.scan_and_clean(locations, apply=False, min_age_hours=args.min_age)
        print(f"About to delete {human(preview.total_bytes)} of cache/temp files older than {args.min_age} h.")
        if input("Continue? [y/N] ").strip().lower() not in ("y", "yes"):
            print("Cancelled.")
            return 1
    result = cleaner.scan_and_clean(locations, apply=args.apply, min_age_hours=args.min_age)

    header("Clean" + ("" if args.apply else " (dry run)"))
    for cat in result.categories:
        if cat.files == 0:
            continue
        line = f"  {cat.name:<22} {cat.files:>7} files  {human(cat.bytes):>10}"
        if args.apply:
            line += c(f"  freed {human(cat.removed_bytes)}", "32")
            if cat.errors:
                line += c(f"  ({cat.errors} in use / protected, skipped)", "90")
        print(line)
    if args.apply:
        if args.trash and cleaner.empty_windows_recycle_bin():
            print("  Recycle Bin emptied.")
        print(c(f"\n  ✔ Freed {human(result.removed_bytes)}", "1;32"))
    else:
        print(f"\n  {human(result.total_bytes)} can be freed. Run with {c('--apply', '1')} to delete.")
    return 0


def cmd_startup(args) -> int:
    items = startup.list_startup_items()
    header(f"Startup programs ({len(items)})")
    for item in items:
        print(f"  • {c(item.name, '1')}  {c(item.source, '90')}")
        if item.command and args.verbose:
            print(f"      {item.command}")
    tips = {
        platforms.WINDOWS: "Disable items in Task Manager → Startup apps.",
        platforms.MACOS: "Disable items in System Settings → General → Login Items.",
        platforms.LINUX: "Disable items in your desktop's Startup Applications tool, or remove ~/.config/autostart entries.",
    }
    print("\n  " + tips[platforms.current_os()])
    return 0


def cmd_power(args) -> int:
    if args.mode:
        ok, out = power.set_profile(args.mode)
        print(c(("✔ " if ok else "✘ ") + out, "32" if ok else "31"))
        return 0 if ok else 1
    print(f"Current power profile: {power.current_profile()}")
    print(f"Switch with: optimizer power {{{','.join(power.MODES)}}}")
    return 0


def cmd_bigfiles(args) -> int:
    root = Path(args.path).expanduser()
    header(f"Files over {args.min_mb:g} MB in {root}")
    files = cleaner.find_large_files(root, min_mb=args.min_mb, limit=args.limit)
    for path, size in files:
        print(f"  {human(size):>10}  {path}")
    if not files:
        print("  None found.")
    return 0


def cmd_boost(args) -> int:
    """One-shot: clean junk, then show the health scan."""
    args.apply, args.trash, args.min_age = True, False, 24
    cmd_clean(args)
    args.json, args.report, args.open = False, None, False
    return cmd_scan(args)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="optimizer", description="Universal laptop optimizer for Windows, macOS and Linux.")
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = p.add_subparsers(dest="command")

    s = sub.add_parser("scan", help="health check with score and recommendations")
    s.add_argument("--json", action="store_true", help="machine-readable output")
    s.add_argument("--report", metavar="FILE", help="save an HTML report")
    s.add_argument("--open", action="store_true", help="open the HTML report in a browser")
    s.set_defaults(func=cmd_scan)

    s = sub.add_parser("clean", help="remove caches and temp files (dry run by default)")
    s.add_argument("--apply", action="store_true", help="actually delete files")
    s.add_argument("--yes", "-y", action="store_true", help="skip the confirmation prompt")
    s.add_argument("--trash", action="store_true", help="also empty the trash / recycle bin")
    s.add_argument("--min-age", type=float, default=24, metavar="HOURS", help="only files older than this (default 24)")
    s.set_defaults(func=cmd_clean)

    s = sub.add_parser("startup", help="list programs that run at login")
    s.add_argument("-v", "--verbose", action="store_true")
    s.set_defaults(func=cmd_startup)

    s = sub.add_parser("power", help="show or switch power profile")
    s.add_argument("mode", nargs="?", choices=power.MODES)
    s.set_defaults(func=cmd_power)

    s = sub.add_parser("bigfiles", help="find the largest files (read-only)")
    s.add_argument("path", nargs="?", default=str(Path.home()))
    s.add_argument("--min-mb", type=float, default=500)
    s.add_argument("--limit", type=int, default=20)
    s.set_defaults(func=cmd_bigfiles)

    s = sub.add_parser("boost", help="clean junk (with confirmation) then run a scan")
    s.add_argument("--yes", "-y", action="store_true")
    s.set_defaults(func=cmd_boost)
    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.command:
        args = parser.parse_args(["scan"])
    try:
        return args.func(args)
    except KeyboardInterrupt:
        print("\nInterrupted.")
        return 130


if __name__ == "__main__":
    sys.exit(main())
