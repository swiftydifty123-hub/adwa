"""Standalone HTML health report."""

from __future__ import annotations

import html
from datetime import datetime

from .advisor import Finding, grade
from .sysinfo import Snapshot

COLORS = {"critical": "#e5484d", "warning": "#f5a524", "info": "#3e9bff"}


def render_html(snap: Snapshot, findings: list[Finding], health: int) -> str:
    e = html.escape
    rows = "".join(
        f'<li><span class="dot" style="background:{COLORS[x.severity]}"></span>'
        f"<b>{e(x.title)}</b><br><small>{e(x.advice)}</small></li>"
        for x in findings
    ) or "<li>No issues found. Your laptop is in great shape.</li>"
    disks = "".join(
        f"<tr><td>{e(d['mount'])}</td><td>{d['free_gb']} / {d['total_gb']} GB free</td>"
        f"<td><div class='bar'><div style='width:{d['percent']}%'></div></div></td></tr>"
        for d in snap.disks
    )
    procs = "".join(
        f"<tr><td>{e(p.name)}</td><td>{p.cpu_percent}%</td><td>{p.memory_mb} MB</td></tr>"
        for p in snap.top_memory
    )
    batt = snap.battery
    batt_text = "No battery" if not batt else f"{batt['percent']}% {'(charging)' if batt['plugged_in'] else ''}"
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Laptop Health Report</title>
<style>
:root {{ --bg:#f7f7f8; --card:#fff; --fg:#1a1a1a; --muted:#666; --accent:#6e56cf; }}
@media (prefers-color-scheme: dark) {{ :root {{ --bg:#111113; --card:#1c1c1f; --fg:#ededed; --muted:#a0a0a0; }} }}
body {{ background:var(--bg); color:var(--fg); font-family:system-ui,sans-serif; margin:0; padding:24px 16px; }}
main {{ max-width:860px; margin:auto; }}
.card {{ background:var(--card); border-radius:14px; padding:20px; margin-bottom:16px; }}
.score {{ font-size:64px; font-weight:800; color:var(--accent); }}
.grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(160px,1fr)); gap:12px; }}
.stat small {{ color:var(--muted); display:block; }}
ul {{ list-style:none; padding:0; }} li {{ margin:10px 0; }}
.dot {{ display:inline-block; width:10px; height:10px; border-radius:50%; margin-right:8px; }}
table {{ width:100%; border-collapse:collapse; }} td {{ padding:6px 4px; }}
.bar {{ background:#8883; border-radius:6px; height:8px; }} .bar div {{ background:var(--accent); height:8px; border-radius:6px; }}
small {{ color:var(--muted); }}
</style></head><body><main>
<div class="card"><small>{e(datetime.now().strftime('%Y-%m-%d %H:%M'))} · {e(snap.os)} {e(snap.os_version)}</small>
<div class="score">{health}<span style="font-size:28px">/100 · {grade(health)}</span></div></div>
<div class="card grid">
<div class="stat"><small>CPU</small>{snap.cpu_percent}% · {snap.cpu_threads} threads</div>
<div class="stat"><small>Memory</small>{snap.memory_percent}% of {snap.memory_total_gb} GB</div>
<div class="stat"><small>Battery</small>{e(batt_text)}</div>
<div class="stat"><small>Uptime</small>{snap.uptime_hours} h</div>
<div class="stat"><small>Processes</small>{snap.process_count}</div>
</div>
<div class="card"><h3>Findings</h3><ul>{rows}</ul></div>
<div class="card"><h3>Disks</h3><table>{disks}</table></div>
<div class="card"><h3>Top memory users</h3><table>{procs}</table></div>
</main></body></html>"""
