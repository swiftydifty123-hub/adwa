"""Find and remove junk files (caches, temp files, trash).

Safety rules:
- Dry run unless the caller passes apply=True.
- Only touches files inside the known cache/temp locations from platforms.py.
- Never follows symlinks and never deletes the location directories themselves.
- Skips files modified more recently than `min_age_hours` (they may be in use).
- Files that are locked or need admin rights are skipped, not forced.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path

from . import platforms


@dataclass
class CategoryResult:
    name: str
    files: int = 0
    bytes: int = 0
    removed_files: int = 0
    removed_bytes: int = 0
    errors: int = 0


@dataclass
class CleanReport:
    applied: bool
    categories: list[CategoryResult] = field(default_factory=list)

    @property
    def total_bytes(self) -> int:
        return sum(c.bytes for c in self.categories)

    @property
    def removed_bytes(self) -> int:
        return sum(c.removed_bytes for c in self.categories)


def _iter_files(root: Path):
    """Yield (path, stat) for regular files under root, without following symlinks."""
    stack = [root]
    while stack:
        current = stack.pop()
        try:
            with os.scandir(current) as it:
                for entry in it:
                    try:
                        if entry.is_symlink():
                            continue
                        if entry.is_dir(follow_symlinks=False):
                            stack.append(Path(entry.path))
                        elif entry.is_file(follow_symlinks=False):
                            yield Path(entry.path), entry.stat(follow_symlinks=False)
                    except OSError:
                        continue
        except OSError:
            continue


def _remove_empty_dirs(root: Path) -> None:
    for dirpath, dirnames, filenames in os.walk(root, topdown=False, followlinks=False):
        path = Path(dirpath)
        if path == root:
            continue
        try:
            path.rmdir()  # only succeeds if empty
        except OSError:
            pass


def scan_and_clean(
    locations: dict[str, list[Path]],
    apply: bool = False,
    min_age_hours: float = 24,
    now: float | None = None,
) -> CleanReport:
    now = now or time.time()
    cutoff = now - min_age_hours * 3600
    report = CleanReport(applied=apply)
    for name, roots in locations.items():
        result = CategoryResult(name)
        for root in roots:
            if not root.is_dir() or root.is_symlink():
                continue
            for path, st in _iter_files(root):
                if st.st_mtime > cutoff:
                    continue
                result.files += 1
                result.bytes += st.st_size
                if apply:
                    try:
                        path.unlink()
                        result.removed_files += 1
                        result.removed_bytes += st.st_size
                    except OSError:
                        result.errors += 1
            if apply:
                _remove_empty_dirs(root)
        report.categories.append(result)
    return report


def default_locations(include_trash: bool = False) -> dict[str, list[Path]]:
    locations = platforms.cleanable_locations()
    if include_trash:
        trash = platforms.trash_locations()
        if trash:
            locations["Trash"] = trash
    return locations


def empty_windows_recycle_bin() -> bool:
    if platforms.current_os() != platforms.WINDOWS:
        return False
    cmd = ["powershell", "-NoProfile", "-Command", "Clear-RecycleBin -Force -ErrorAction SilentlyContinue"]
    return subprocess.run(cmd, capture_output=True).returncode == 0


def find_large_files(root: Path, min_mb: float = 500, limit: int = 20) -> list[tuple[Path, int]]:
    """Report (never delete) the biggest files under root."""
    threshold = min_mb * 1024 ** 2
    found = [(p, st.st_size) for p, st in _iter_files(root) if st.st_size >= threshold]
    found.sort(key=lambda item: item[1], reverse=True)
    return found[:limit]


def disk_free(path: Path) -> int:
    return shutil.disk_usage(path).free
