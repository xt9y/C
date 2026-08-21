#!/usr/bin/env python3
"""Render fuzz coverage as Markdown and fail on meaningful regressions."""

from __future__ import annotations

import json
import sys
from pathlib import Path

CORE_FILES = ("cache_io.h", "main.c", "perf_v2.h")
REQUIRED_FILES = (*CORE_FILES, "cli.c")

# Regression floors sit below the measured CI result, leaving normal fuzz-run
# variance while preventing meaningful coverage loss from silently landing.
GATES = (
    ("Core line coverage", "core", "lines", 51.0),
    ("Core branch coverage", "core", "branches", 33.5),
    ("All-production line coverage", "all", "lines", 58.0),
    ("All-production branch coverage", "all", "branches", 37.0),
    ("main.c line coverage", "main.c", "lines", 46.5),
    ("main.c branch coverage", "main.c", "branches", 29.5),
    ("main.c function coverage", "main.c", "functions", 59.0),
    ("cli.c line coverage", "cli.c", "lines", 65.5),
    ("cli.c branch coverage", "cli.c", "branches", 39.0),
    ("cli.c function coverage", "cli.c", "functions", 58.0),
)

METRICS = ("lines", "functions", "branches", "regions")


def logical_name(filename: str) -> str:
    name = Path(filename).name
    if name == "cli_fuzz.c":
        return "cli.c"
    return name


def metric(summary: dict, key: str) -> dict:
    value = summary.get(key, {})
    count = int(value.get("count", 0))
    covered = int(value.get("covered", 0))
    percent = float(value.get("percent", 0.0)) if count else 0.0
    return {"count": count, "covered": covered, "percent": percent}


def combine(entries: list[dict]) -> dict:
    result = {}
    for key in METRICS:
        count = sum(entry[key]["count"] for entry in entries)
        covered = sum(entry[key]["covered"] for entry in entries)
        result[key] = {
            "count": count,
            "covered": covered,
            "percent": (covered / count * 100.0) if count else 0.0,
        }
    return result


def fmt(value: float) -> str:
    return f"{value:.2f}%"


def main() -> int:
    if len(sys.argv) != 3:
        print(f"usage: {sys.argv[0]} COVERAGE_JSON OUTPUT_MD", file=sys.stderr)
        return 2

    source = Path(sys.argv[1])
    output = Path(sys.argv[2])
    payload = json.loads(source.read_text())
    if not payload.get("data"):
        print("coverage gate: LLVM export contains no data", file=sys.stderr)
        return 1

    files: dict[str, dict] = {}
    for item in payload["data"][0].get("files", []):
        name = logical_name(item.get("filename", ""))
        if name not in REQUIRED_FILES:
            continue
        current = {key: metric(item.get("summary", {}), key) for key in METRICS}
        if name in files:
            files[name] = combine([files[name], current])
        else:
            files[name] = current

    missing = [name for name in REQUIRED_FILES if name not in files]
    failures: list[str] = []
    if missing:
        failures.append("missing production coverage: " + ", ".join(missing))

    core = combine([files[name] for name in CORE_FILES if name in files])
    all_production = combine(list(files.values())) if files else combine([])

    rows = []
    for name in REQUIRED_FILES:
        if name not in files:
            rows.append((name, None))
        else:
            rows.append((name, files[name]))

    gate_rows = []
    for label, subject, key, floor in GATES:
        if subject == "core":
            actual = core[key]["percent"]
            available = all(name in files for name in CORE_FILES)
        elif subject == "all":
            actual = all_production[key]["percent"]
            available = all(name in files for name in REQUIRED_FILES)
        else:
            available = subject in files
            actual = files[subject][key]["percent"] if available else 0.0
        passed = available and actual + 1e-9 >= floor
        gate_rows.append((label, floor, actual, passed))
        if not passed:
            failures.append(f"{label}: {actual:.2f}% < {floor:.2f}%")

    lines = [
        "## Fuzz coverage",
        "",
        "Production coverage reached by the sanitizer/libFuzzer corpus. The core total keeps the historical `main.c`/cache/perf denominator; `cli.c` is shown separately and also included in the all-production total.",
        "",
        "| Source | Lines | Functions | Branches | Regions |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for name, values in rows:
        if values is None:
            lines.append(f"| `{name}` | missing | missing | missing | missing |")
        else:
            lines.append(
                f"| `{name}` | {fmt(values['lines']['percent'])} | "
                f"{fmt(values['functions']['percent'])} | {fmt(values['branches']['percent'])} | "
                f"{fmt(values['regions']['percent'])} |"
            )
    lines.extend(
        [
            f"| **Core total** | **{fmt(core['lines']['percent'])}** | **{fmt(core['functions']['percent'])}** | **{fmt(core['branches']['percent'])}** | **{fmt(core['regions']['percent'])}** |",
            f"| **All production** | **{fmt(all_production['lines']['percent'])}** | **{fmt(all_production['functions']['percent'])}** | **{fmt(all_production['branches']['percent'])}** | **{fmt(all_production['regions']['percent'])}** |",
            "",
            "### Coverage regression gates",
            "",
            "| Gate | Floor | Actual | Status |",
            "| --- | ---: | ---: | --- |",
        ]
    )
    for label, floor, actual, passed in gate_rows:
        lines.append(f"| {label} | {floor:.2f}% | {actual:.2f}% | {'PASS' if passed else 'FAIL'} |")

    if failures:
        lines.extend(["", "**Coverage gate failed:** " + "; ".join(failures)])
    else:
        lines.extend(["", "All coverage regression gates passed."])

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines) + "\n")
    print(output.read_text(), end="")

    if failures:
        for failure in failures:
            print("coverage gate: " + failure, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
