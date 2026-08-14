#!/usr/bin/env python3
import json
from pathlib import Path


def load_curve(path):
    for line in Path(path).read_text().splitlines():
        if line.startswith("CURVE_JSON="):
            return json.loads(line[11:])
    raise RuntimeError("CURVE_JSON not found")


def fmt(ms):
    return f"{ms / 1000:.2f} s" if ms >= 1000 else f"{ms:.1f} ms"


def verdict(c, n):
    pct = (n - c) / n * 100 if n else 0
    if abs(pct) < .05:
        return "tied"
    return f"`c` {pct:.1f}% faster" if pct > 0 else f"CMake + Ninja {-pct:.1f}% faster"


def write_svg(path, points, total):
    shown = [p for p in points if p["rebuilt_tus"]]
    w, h = 920, 500
    l, r, t, b = 76, 30, 56, 66
    pw, ph = w-l-r, h-t-b
    ymax = max(max(p["c_ms"], p["ninja_ms"]) for p in shown) * 1.08
    x = lambda v: l + v / total * pw
    y = lambda v: t + ph - v / ymax * ph
    line = lambda key: " ".join(f"{x(p['rebuilt_tus']):.1f},{y(p[key]):.1f}" for p in shown)
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">',
        '<rect width="100%" height="100%" fill="white"/>',
        '<text x="24" y="30" font-family="sans-serif" font-size="21" font-weight="700">SDL3 incremental scaling</text>',
    ]
    for i in range(5):
        ms = ymax * i / 4
        yy = y(ms)
        out += [
            f'<line x1="{l}" y1="{yy:.1f}" x2="{w-r}" y2="{yy:.1f}" stroke="#ddd"/>',
            f'<text x="{l-8}" y="{yy+4:.1f}" text-anchor="end" font-family="sans-serif" font-size="11">{fmt(ms)}</text>',
        ]
    out += [
        f'<polyline points="{line("c_ms")}" fill="none" stroke="#24292f" stroke-width="3"/>',
        f'<polyline points="{line("ninja_ms")}" fill="none" stroke="#8c959f" stroke-width="3"/>',
    ]
    for p in shown:
        xx, cy, ny = x(p["rebuilt_tus"]), y(p["c_ms"]), y(p["ninja_ms"])
        out += [
            f'<circle cx="{xx:.1f}" cy="{cy:.1f}" r="4" fill="#24292f"/>',
            f'<circle cx="{xx:.1f}" cy="{ny:.1f}" r="4" fill="#8c959f"/>',
            f'<text x="{xx:.1f}" y="{min(cy,ny)-8:.1f}" text-anchor="middle" font-family="sans-serif" font-size="11">{p["rebuilt_tus"]}</text>',
        ]
    out += [
        f'<text x="{l+pw/2:.1f}" y="{h-18}" text-anchor="middle" font-family="sans-serif" font-size="12">Actual translation units rebuilt</text>',
        '<circle cx="680" cy="26" r="4" fill="#24292f"/><text x="690" y="30" font-family="sans-serif" font-size="12">c</text>',
        '<circle cx="745" cy="26" r="4" fill="#8c959f"/><text x="755" y="30" font-family="sans-serif" font-size="12">CMake + Ninja</text>',
        '</svg>',
    ]
    Path(path).write_text("\n".join(out) + "\n")


def augment(result, input_path, out_dir):
    curve = load_curve(input_path)
    if curve["endpoint"] != result["change"] or curve["source_count"] != result["source_count"]:
        raise RuntimeError("baseline and curve describe different SDL builds")
    if result["c"]["translation_units_rebuilt"] != result["cmake_ninja"]["translation_units_rebuilt"]:
        raise RuntimeError("baseline rebuilt TU counts differ")

    points = [{
        "kind":"noop","rebuilt_tus":0,"range":"No changes",
        "c_ms":result["c"]["noop"]["wall_ms"],"ninja_ms":result["cmake_ninja"]["noop"]["wall_ms"]
    },{
        "kind":"history","rebuilt_tus":result["c"]["translation_units_rebuilt"],
        "range":f"{result['change_stats']['commits']} commits / {result['change_stats']['files_changed']} files",
        "c_ms":result["c"]["real_update"]["wall_ms"],"ninja_ms":result["cmake_ninja"]["real_update"]["wall_ms"]
    }]
    for p in curve["points"]:
        applied = p.get("applied_files", p["change_stats"]["files_changed"])
        points.append({
            "kind":"history","target_tus":p["target_tus"],"rebuilt_tus":p["rebuilt_tus"],
            "range":f"{p['change_stats']['commits']} commits / {applied} applied files",
            "base":p["base"],"c_ms":p["c"]["wall_ms"],"ninja_ms":p["cmake_ninja"]["wall_ms"]
        })
    points.append({
        "kind":"clean","rebuilt_tus":result["source_count"],"range":"Clean build",
        "c_ms":result["c"]["clean"]["wall_ms"],"ninja_ms":result["cmake_ninja"]["clean"]["wall_ms"]
    })
    points.sort(key=lambda p:p["rebuilt_tus"])

    out = Path(out_dir)
    write_svg(out/"timings.svg", points, result["source_count"])
    rows = "\n".join(
        f"| {p['rebuilt_tus']} | {p['range']} | {fmt(p['c_ms'])} | {fmt(p['ninja_ms'])} | {verdict(p['c_ms'],p['ninja_ms'])} |"
        for p in points
    )
    section = (
        "## Scaling curve\n\n"
        "![SDL3 incremental scaling](benchmarks/sdl3/timings.svg)\n\n"
        "The x-axis is the **actual measured number of translation units rebuilt**. "
        "For extra history points, the benchmark keeps one fixed 219-TU endpoint tree/build graph and replaces only files that were genuinely modified in an older real SDL range with their historical contents. Additions and deletions stay at the endpoint so the source set remains comparable.\n\n"
        "| Rebuilt TUs | SDL range | `c` | CMake + Ninja | Result |\n"
        "| ---: | --- | ---: | ---: | --- |\n" + rows + "\n\n"
        f"Each extra history point is measured {curve['runs_per_point']} times. "
        "Candidate ranges are selected from Ninja's real endpoint dependency graph. Points that do not build cleanly or rebuild different TU counts between the tools are skipped instead of invalidating the whole report.\n\n"
    )
    summary = out/"summary.md"
    text = summary.read_text()
    heading, rest = text.split("\n", 1)
    summary.write_text(heading + "\n\n" + section + rest.lstrip())

    result["scaling"] = {
        "endpoint": curve["endpoint"],
        "history_mode": curve.get("history_mode"),
        "runs_per_history_point": curve["runs_per_point"],
        "targets": curve["targets"],
        "points": points,
        "history_measurements": curve["points"],
    }
    (out/"results.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
