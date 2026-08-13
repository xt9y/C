#!/usr/bin/env python3

import argparse
import html
import json
import os
from pathlib import Path


def load_result(path):
    path = Path(path)
    if path.suffix == ".json":
        return json.loads(path.read_text())

    result = None
    for line in path.read_text().splitlines():
        if line.startswith("STATS_JSON="):
            result = json.loads(line[len("STATS_JSON="):])
    if result is None:
        raise RuntimeError(f"no STATS_JSON line found in {path}")
    return result


def fmt_time(ms):
    if ms >= 1000.0:
        return f"{ms / 1000.0:.2f} s"
    return f"{ms:.1f} ms"


def fmt_mib(kib):
    return f"{kib / 1024.0:.2f} MiB"


def delta_percent(faster, slower):
    if not slower:
        return 0.0
    return (slower - faster) / slower * 100.0


def winner_text(label, c_value, ninja_value):
    if abs(c_value - ninja_value) < 1e-12:
        return f"{label}: tied."
    if c_value < ninja_value:
        return f"{label}: `c` is {delta_percent(c_value, ninja_value):.1f}% lower on this run."
    return f"{label}: CMake + Ninja is {delta_percent(ninja_value, c_value):.1f}% lower on this run."


def text_bar(value, maximum, width=30):
    if maximum <= 0:
        return ""
    cells = max(1, round(value / maximum * width)) if value > 0 else 0
    return "█" * cells


def bar_block(rows):
    lines = []
    for label, c_value, ninja_value, formatter in rows:
        maximum = max(c_value, ninja_value)
        lines.append(label)
        lines.append(f"  c              {text_bar(c_value, maximum):<30} {formatter(c_value)}")
        lines.append(f"  CMake + Ninja  {text_bar(ninja_value, maximum):<30} {formatter(ninja_value)}")
        lines.append("")
    return "\n".join(lines).rstrip()


def write_pair_svg(path, title, rows):
    width = 900
    left = 190
    bar_width = 520
    top = 78
    group_h = 112
    height = top + group_h * len(rows) + 50

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        '<style>text{font-family:-apple-system,BlinkMacSystemFont,Segoe UI,Helvetica,Arial,sans-serif;fill:#24292f}.label{font-size:14px;font-weight:600}.value{font-size:13px}.title{font-size:22px;font-weight:700}.legend{font-size:13px}</style>',
        f'<text x="30" y="38" class="title">{html.escape(title)}</text>',
        '<rect x="610" y="21" width="14" height="14" rx="2" fill="#24292f"/><text x="632" y="33" class="legend">c</text>',
        '<rect x="676" y="21" width="14" height="14" rx="2" fill="#8c959f"/><text x="698" y="33" class="legend">CMake + Ninja</text>',
    ]

    for i, (label, c_value, ninja_value, formatter) in enumerate(rows):
        y = top + i * group_h
        maximum = max(c_value, ninja_value, 1e-12)
        c_w = c_value / maximum * bar_width
        n_w = ninja_value / maximum * bar_width
        parts.extend([
            f'<text x="30" y="{y + 18}" class="label">{html.escape(label)}</text>',
            f'<rect x="{left}" y="{y}" width="{bar_width}" height="24" rx="4" fill="#f6f8fa"/>',
            f'<rect x="{left}" y="{y}" width="{c_w:.2f}" height="24" rx="4" fill="#24292f"/>',
            f'<text x="{left + bar_width + 14}" y="{y + 17}" class="value">{html.escape(formatter(c_value))}</text>',
            f'<rect x="{left}" y="{y + 34}" width="{bar_width}" height="24" rx="4" fill="#f6f8fa"/>',
            f'<rect x="{left}" y="{y + 34}" width="{n_w:.2f}" height="24" rx="4" fill="#8c959f"/>',
            f'<text x="{left + bar_width + 14}" y="{y + 51}" class="value">{html.escape(formatter(ninja_value))}</text>',
        ])

    parts.append(f'<text x="30" y="{height - 20}" class="legend">Each metric pair is scaled independently. Lower is better.</text>')
    parts.append('</svg>')
    Path(path).write_text("\n".join(parts) + "\n")


def render(result, out_dir):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    c = result["c"]
    ninja = result["cmake_ninja"]

    timing_rows = [
        ("Clean build", c["clean"]["wall_ms"], ninja["clean"]["wall_ms"], fmt_time),
        ("No changes", c["noop"]["wall_ms"], ninja["noop"]["wall_ms"], fmt_time),
        ("Real update", c["real_update"]["wall_ms"], ninja["real_update"]["wall_ms"], fmt_time),
        ("Archive only", c["archive_only"]["wall_ms"], ninja["archive_only"]["wall_ms"], fmt_time),
    ]

    c_update_cpu = c["real_update"]["user_s"] + c["real_update"]["system_s"]
    n_update_cpu = ninja["real_update"]["user_s"] + ninja["real_update"]["system_s"]
    resource_rows = [
        ("Update CPU time", c_update_cpu, n_update_cpu, lambda value: f"{value:.2f} s"),
        ("Update peak RSS", c["real_update"]["max_rss_kb"], ninja["real_update"]["max_rss_kb"], fmt_mib),
        ("Filesystem outputs", c["real_update"]["fs_outputs"], ninja["real_update"]["fs_outputs"], lambda value: f"{int(value):,}"),
        (
            "Context switches",
            c["real_update"]["voluntary_context_switches"] + c["real_update"]["involuntary_context_switches"],
            ninja["real_update"]["voluntary_context_switches"] + ninja["real_update"]["involuntary_context_switches"],
            lambda value: f"{int(value):,}",
        ),
    ]

    write_pair_svg(out / "timings.svg", "SDL3 build times", timing_rows)
    write_pair_svg(out / "resources.svg", "SDL3 real-update resources", resource_rows)

    machine = result["machine"]
    change = result["change_stats"]
    c_tus = c["translation_units_rebuilt"]
    n_tus = ninja["translation_units_rebuilt"]
    run_number = os.environ.get("GITHUB_RUN_NUMBER", "local")

    summary = f"""# SDL3 benchmark

`c` vs CMake + Ninja on a real SDL3 static debug build. Lower is better for the measurements below.

| Build | `c` | CMake + Ninja |
| --- | ---: | ---: |
| Clean build | **{fmt_time(c['clean']['wall_ms'])}** | {fmt_time(ninja['clean']['wall_ms'])} |
| No changes | **{fmt_time(c['noop']['wall_ms'])}** | {fmt_time(ninja['noop']['wall_ms'])} |
| Real {change['commits']}-commit update | **{fmt_time(c['real_update']['wall_ms'])}** | {fmt_time(ninja['real_update']['wall_ms'])} |
| Archive only | **{fmt_time(c['archive_only']['wall_ms'])}** | {fmt_time(ninja['archive_only']['wall_ms'])} |
| TUs rebuilt | {c_tus} / {result['source_count']} | {n_tus} / {result['source_count']} |

## Build-time bars

```text
{bar_block(timing_rows)}
```

## What this run says

- {winner_text('Clean build', c['clean']['wall_ms'], ninja['clean']['wall_ms'])}
- {winner_text('No-op', c['noop']['wall_ms'], ninja['noop']['wall_ms'])}
- {winner_text('Real update', c['real_update']['wall_ms'], ninja['real_update']['wall_ms'])}
- {winner_text('Archive only', c['archive_only']['wall_ms'], ninja['archive_only']['wall_ms'])}
- The real update rebuilt **{c_tus} TUs with `c`** and **{n_tus} TUs with Ninja**.

## Real-update resources

| Metric | `c` | CMake + Ninja |
| --- | ---: | ---: |
| CPU time | {c_update_cpu:.2f} s | {n_update_cpu:.2f} s |
| Peak RSS | {fmt_mib(c['real_update']['max_rss_kb'])} | {fmt_mib(ninja['real_update']['max_rss_kb'])} |
| Filesystem outputs | {int(c['real_update']['fs_outputs']):,} | {int(ninja['real_update']['fs_outputs']):,} |
| Context switches | {int(resource_rows[3][1]):,} | {int(resource_rows[3][2]):,} |

## Runner

- **CPU:** {machine['cpu_model']} ({machine['cpu_count']} vCPUs)
- **Jobs:** {result['jobs']}
- **Compiler:** {machine['compiler']}
- **CMake:** {machine['cmake']}
- **Ninja:** {machine['ninja']}
- **SDL range:** `{result['base'][:8]}` -> `{result['change'][:8]}` ({change['commits']} commits, {change['files_changed']} changed files)

The downloadable **`sdl3-benchmark-{run_number}`** artifact contains `results.json`, `benchmark.log`, `summary.md`, `timings.svg`, and `resources.svg`.

One runner, one SDL configuration, one real commit range. These numbers describe this run, not every project or machine.
"""

    (out / "summary.md").write_text(summary)
    (out / "results.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")


def main():
    parser = argparse.ArgumentParser(description="Render the SDL3 benchmark report")
    parser.add_argument("input", help="benchmark log containing STATS_JSON, or a JSON result file")
    parser.add_argument("output_dir", help="directory for summary.md, results.json and SVG charts")
    args = parser.parse_args()
    render(load_result(args.input), args.output_dir)


if __name__ == "__main__":
    main()
