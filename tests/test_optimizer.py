import os
import time
from pathlib import Path

from optimizer import advisor, cleaner, platforms, startup
from optimizer.cli import main
from optimizer.sysinfo import ProcessInfo, Snapshot


def _touch(path: Path, size: int = 10, age_hours: float = 48) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"x" * size)
    old = time.time() - age_hours * 3600
    os.utime(path, (old, old))
    return path


def test_dry_run_deletes_nothing(tmp_path):
    f = _touch(tmp_path / "cache" / "a.bin", 100)
    report = cleaner.scan_and_clean({"c": [tmp_path / "cache"]}, apply=False)
    assert report.total_bytes == 100
    assert f.exists()


def test_apply_deletes_only_old_files(tmp_path):
    root = tmp_path / "cache"
    old = _touch(root / "sub" / "old.bin", 50, age_hours=48)
    new = _touch(root / "new.bin", 50, age_hours=0)
    report = cleaner.scan_and_clean({"c": [root]}, apply=True, min_age_hours=24)
    assert not old.exists()
    assert new.exists()
    assert root.exists()
    assert not (root / "sub").exists()
    assert report.removed_bytes == 50


def test_symlinks_are_never_followed(tmp_path):
    precious = _touch(tmp_path / "docs" / "thesis.docx", 10)
    root = tmp_path / "cache"
    root.mkdir()
    (root / "link").symlink_to(tmp_path / "docs", target_is_directory=True)
    (root / "filelink").symlink_to(precious)
    cleaner.scan_and_clean({"c": [root]}, apply=True, min_age_hours=0)
    assert precious.exists()


def test_missing_location_is_ignored(tmp_path):
    report = cleaner.scan_and_clean({"c": [tmp_path / "nope"]}, apply=True)
    assert report.total_bytes == 0


def test_find_large_files(tmp_path):
    _touch(tmp_path / "big.iso", 3 * 1024 * 1024)
    _touch(tmp_path / "small.txt", 10)
    found = cleaner.find_large_files(tmp_path, min_mb=1)
    assert [p.name for p, _ in found] == ["big.iso"]


def test_locations_for_every_os(tmp_path):
    for os_name in (platforms.WINDOWS, platforms.MACOS, platforms.LINUX):
        locs = platforms.cleanable_locations(os_name, home=tmp_path)
        assert "System temp" in locs
        for paths in locs.values():
            for p in paths:
                assert p != tmp_path  # never the home directory itself


def test_linux_autostart(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    (tmp_path / "autostart").mkdir()
    (tmp_path / "autostart" / "app.desktop").write_text("[Desktop Entry]\nName=Chat\nExec=chat --bg\n")
    (tmp_path / "autostart" / "off.desktop").write_text("[Desktop Entry]\nName=Off\nHidden=true\n")
    names = [i.name for i in startup.list_startup_items(platforms.LINUX, home=tmp_path)]
    assert "Chat" in names and "Off" not in names


def _snap(**overrides):
    base = dict(os="Linux", os_version="6", machine="x86_64", cpu_model="cpu", cpu_cores=4, cpu_threads=8,
                cpu_percent=10, cpu_freq_mhz=None, memory_total_gb=16, memory_percent=40, swap_percent=0,
                disks=[{"mount": "/", "fstype": "ext4", "total_gb": 500, "free_gb": 300, "percent": 40}],
                uptime_hours=5, top_cpu=[ProcessInfo(1, "idle", 99, 0)])
    base.update(overrides)
    return Snapshot(**base)


def test_healthy_machine_scores_100():
    findings = advisor.analyze(_snap(), startup_count=3, junk_bytes=0)
    assert findings == []
    assert advisor.score(findings) == 100
    assert advisor.grade(100) == "A"


def test_struggling_machine_is_flagged():
    snap = _snap(memory_percent=95, cpu_percent=99,
                 disks=[{"mount": "C:\\", "fstype": "NTFS", "total_gb": 256, "free_gb": 5, "percent": 98}],
                 temperatures_c={"cpu": 96}, uptime_hours=24 * 30)
    findings = advisor.analyze(snap, startup_count=25, junk_bytes=5 * 1024 ** 3)
    assert advisor.score(findings) < 50
    assert any("Disk" in f.title for f in findings)


def test_cli_runs(capsys):
    assert main(["scan", "--json"]) == 0
    assert main(["clean"]) == 0
    assert main(["startup"]) == 0
    assert "health" in capsys.readouterr().out
