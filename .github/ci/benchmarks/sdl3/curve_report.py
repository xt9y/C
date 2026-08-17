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
    return f"C-BuildSystem {pct:.1f}% faster" if pct > 0 else f"CMake + Ninja {-pct:.1f}% faster"


def write_svg(path, points, total):
    w, h = 940, 520
    l, r, t, b = 82, 30, 58, 78
    pw, ph = w - l - r, h - t - b
    ymax = max(max(p["c_ms"], p["ninja_ms"]) for p in points) * 1.08
    x = lambda v: l + v / total * pw
    y = lambda v: t + ph - v / ymax * ph
    line = lambda key: " ".join(
        f"{x(p['changed_files']):.1f},{y(p[key]):.1f}" for p in points
    )

    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">',
        '<rect width="100%" height="100%" fill="white"/>',
        '<text x="24" y="31" font-family="sans-serif" font-size="21" font-weight="700">SDL3 incremental scaling</text>',
    ]

    for i in range(5):
        ms = ymax * i / 4
        yy = y(ms)
        out += [
            f'<line x1="{l}" y1="{yy:.1f}" x2="{w-r}" y2="{yy:.1f}" stroke="#ddd"/>',
            f'<text x="{l-9}" y="{yy+4:.1f}" text-anchor="end" font-family="sans-serif" font-size="11">{fmt(ms)}</text>',
        ]

    out += [
        f'<line x1="{l}" y1="{t+ph}" x2="{w-r}" y2="{t+ph}" stroke="#888"/>',
        f'<polyline points="{line("c_ms")}" fill="none" stroke="#24292f" stroke-width="3"/>',
        f'<polyline points="{line("ninja_ms")}" fill="none" stroke="#8c959f" stroke-width="3"/>',
    ]

    for p in points:
        xx = x(p["changed_files"])
        cy = y(p["c_ms"])
        ny = y(p["ninja_ms"])
        out += [
            f'<line x1="{xx:.1f}" y1="{t+ph}" x2="{xx:.1f}" y2="{t+ph+5}" stroke="#888"/>',
            f'<text x="{xx:.1f}" y="{t+ph+19}" text-anchor="middle" font-family="sans-serif" font-size="11">{p["changed_files"]}</text>',
            f'<circle cx="{xx:.1f}" cy="{cy:.1f}" r="4" fill="#24292f"/>',
            f'<circle cx="{xx:.1f}" cy="{ny:.1f}" r="4" fill="#8c959f"/>',
        ]

    out += [
        f'<text x="{l+pw/2:.1f}" y="{h-19}" text-anchor="middle" font-family="sans-serif" font-size="12">Changed SDL source files</text>',
        '<circle cx="620" cy="27" r="4" fill="#24292f"/><text x="630" y="31" font-family="sans-serif" font-size="12">C-BuildSystem</text>',
        '<circle cx="755" cy="27" r="4" fill="#8c959f"/><text x="765" y="31" font-family="sans-serif" font-size="12">CMake + Ninja</text>',
        '</svg>',
    ]
    Path(path).write_text("\n".join(out) + "\n")


def augment(result, input_path, out_dir):
    curve = load_curve(input_path)
    if curve["endpoint"] != result["change"] or curve["source_count"] != result["source_count"]:
        raise RuntimeError("baseline and curve describe different SDL builds")

    points = [{
        "kind": "noop",
        "changed_files": 0,
        "rebuilt_tus": 0,
        "c_ms": result["c"]["noop"]["wall_ms"],
        "ninja_ms": result["cmake_ninja"]["noop"]["wall_ms"],
    }]

    for p in curve["points"]:
        points.append({
            "kind": "controlled",
            "changed_files": p["changed_files"],
            "rebuilt_tus": p["rebuilt_tus"],
            "c_ms": p["c"]["wall_ms"],
            "ninja_ms": p["cmake_ninja"]["wall_ms"],
        })

    points.append({
        "kind": "clean",
        "changed_files": result["source_count"],
        "rebuilt_tus": result["source_count"],
        "c_ms": result["c"]["clean"]["wall_ms"],
        "ninja_ms": result["cmake_ninja"]["clean"]["wall_ms"],
    })
    points.sort(key=lambda p: p["changed_files"])

    out = Path(out_dir)
    write_svg(out / "timings.svg", points, result["source_count"])

    rows = "\n".join(
        f"| {p['changed_files']} | {p['rebuilt_tus']} | {fmt(p['c_ms'])} | {fmt(p['ninja_ms'])} | {verdict(p['c_ms'], p['ninja_ms'])} |"
        for p in points
    )
    section = (
        "## Scaling curve\n\n"
        "The x-axis is the **number of SDL source files changed**. The controlled points edit exactly "
        "7, 21, 42, 63, 105, 147, and 189 endpoint translation units with harmless comments, using a deterministic mixed ordering across SDL subsystems. Larger points are cumulative supersets of smaller points.\n\n"
        "This controlled curve is intentionally separate from the real 7-commit SDL update reported below: the real update shows real-world behavior, while this curve isolates how each build system scales as the amount of invalidated source code grows.\n\n"
        "| Changed source files | Rebuilt TUs | C-BuildSystem | CMake + Ninja | Result |\n"
        "| ---: | ---: | ---: | ---: | --- |\n" + rows + "\n\n"
        f"Each controlled incremental point is measured {curve['runs_per_point']} times. "
        "The benchmark fails rather than publish a point unless both tools rebuild exactly the requested number of translation units.\n\n"
    )

    summary = out / "summary.md"
    text = summary.read_text()
    heading, rest = text.split("\n", 1)
    summary.write_text(heading + "\n\n" + section + rest.lstrip())

    result["scaling"] = {
        "endpoint": curve["endpoint"],
        "mode": curve["mode"],
        "x_axis": curve["x_axis"],
        "runs_per_point": curve["runs_per_point"],
        "targets": curve["targets"],
        "points": points,
        "controlled_measurements": curve["points"],
    }
    (out / "results.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")