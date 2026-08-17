#!/usr/bin/env python3
import argparse
import html
import json
import os
from pathlib import Path

from curve_report import augment


def load(path):
    result = None
    for line in Path(path).read_text().splitlines():
        if line.startswith("STATS_JSON="):
            result = json.loads(line[11:])
    if result is None:
        raise RuntimeError("STATS_JSON not found")
    return result


def fmt(ms):
    return f"{ms / 1000:.2f} s" if ms >= 1000 else f"{ms:.1f} ms"


def mib(kib):
    return f"{kib / 1024:.2f} MiB"


def pair_svg(path, rows):
    w = 900
    h = 80 + len(rows) * 92
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">',
        '<rect width="100%" height="100%" fill="white"/>',
        '<text x="24" y="32" font-family="sans-serif" font-size="21" font-weight="700">SDL3 anchor-update resources</text>',
    ]
    for i, (label, c, n, formatter) in enumerate(rows):
        y = 62 + i * 92
        maximum = max(c, n, 1e-9)
        cw, nw = c / maximum * 500, n / maximum * 500
        out += [
            f'<text x="24" y="{y+16}" font-family="sans-serif" font-size="13">{html.escape(label)}</text>',
            f'<rect x="190" y="{y}" width="{cw:.1f}" height="22" fill="#24292f"/>',
            f'<text x="705" y="{y+16}" font-family="sans-serif" font-size="12">{html.escape(formatter(c))}</text>',
            f'<rect x="190" y="{y+30}" width="{nw:.1f}" height="22" fill="#8c959f"/>',
            f'<text x="705" y="{y+46}" font-family="sans-serif" font-size="12">{html.escape(formatter(n))}</text>',
        ]
    out.append("</svg>")
    Path(path).write_text("\n".join(out) + "\n")


def render(result, input_path, out_dir):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    c = result["c"]
    n = result["cmake_ninja"]
    change = result["change_stats"]
    machine = result["machine"]

    cpu_c = c["real_update"]["user_s"] + c["real_update"]["system_s"]
    cpu_n = n["real_update"]["user_s"] + n["real_update"]["system_s"]
    ctx_c = c["real_update"]["voluntary_context_switches"] + c["real_update"]["involuntary_context_switches"]
    ctx_n = n["real_update"]["voluntary_context_switches"] + n["real_update"]["involuntary_context_switches"]
    pair_svg(out/"resources.svg", [
        ("CPU time", cpu_c, cpu_n, lambda x:f"{x:.2f} s"),
        ("Peak RSS", c["real_update"]["max_rss_kb"], n["real_update"]["max_rss_kb"], mib),
        ("Filesystem outputs", c["real_update"]["fs_outputs"], n["real_update"]["fs_outputs"], lambda x:f"{int(x):,}"),
        ("Context switches", ctx_c, ctx_n, lambda x:f"{int(x):,}"),
    ])

    run = os.environ.get("GITHUB_RUN_NUMBER", "local")
    summary = f"""# SDL3 benchmark

C-BuildSystem vs CMake + Ninja on a real SDL3 static debug build. Lower is better.

## Core measurements

| Build | C-BuildSystem | CMake + Ninja |
| --- | ---: | ---: |
| Clean build | {fmt(c['clean']['wall_ms'])} | {fmt(n['clean']['wall_ms'])} |
| No changes | {fmt(c['noop']['wall_ms'])} | {fmt(n['noop']['wall_ms'])} |
| Real {change['commits']}-commit anchor update | {fmt(c['real_update']['wall_ms'])} | {fmt(n['real_update']['wall_ms'])} |
| Archive only | {fmt(c['archive_only']['wall_ms'])} | {fmt(n['archive_only']['wall_ms'])} |
| Anchor TUs rebuilt | {c['translation_units_rebuilt']} / {result['source_count']} | {n['translation_units_rebuilt']} / {result['source_count']} |

## Anchor update resources

| Metric | C-BuildSystem | CMake + Ninja |
| --- | ---: | ---: |
| CPU time | {cpu_c:.2f} s | {cpu_n:.2f} s |
| Peak RSS | {mib(c['real_update']['max_rss_kb'])} | {mib(n['real_update']['max_rss_kb'])} |
| Filesystem outputs | {int(c['real_update']['fs_outputs']):,} | {int(n['real_update']['fs_outputs']):,} |
| Context switches | {int(ctx_c):,} | {int(ctx_n):,} |

## Setup cost

| Metric | Fresh C-BuildSystem build-script cache | CMake configure |
| --- | ---: | ---: |
| Wall time | {fmt(result['configuration']['c_fresh_build_script_cache']['wall_ms'])} | {fmt(result['configuration']['cmake_configure']['wall_ms'])} |
| Peak RSS | {mib(result['configuration']['c_fresh_build_script_cache']['max_rss_kb'])} | {mib(result['configuration']['cmake_configure']['max_rss_kb'])} |

## Runner

- **Date:** {machine['date']}
- **CPU:** {machine['cpu_model']} ({machine['cpu_count']} vCPUs)
- **Jobs:** {result['jobs']}
- **Compiler:** {machine['compiler']}
- **CMake:** {machine['cmake']}
- **Ninja:** {machine['ninja']}
- **SDL endpoint:** `{result['change'][:12]}`
- **Object cache:** disabled
- **PCH:** disabled

## Method

- Clean build: median of {len(c['clean']['samples'])} runs.
- No changes: median of {len(c['noop']['samples'])} runs.
- Anchor update: median of {len(c['real_update']['samples'])} runs.
- Both systems use the same SDL static-target source set and semantic compile flags.
- SDL revision metadata is pinned to `benchmark`.
- Hosted-runner measurements describe this run, not every machine.

The downloadable **`sdl3-benchmark-{run}`** artifact contains the raw log, JSON measurements and SVG charts.
"""
    (out/"summary.md").write_text(summary)
    (out/"results.json").write_text(json.dumps(result, indent=2, sort_keys=True)+"\n")
    augment(result, input_path, out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input")
    ap.add_argument("output_dir")
    args = ap.parse_args()
    render(load(args.input), args.input, args.output_dir)


if __name__ == "__main__":
    main()
