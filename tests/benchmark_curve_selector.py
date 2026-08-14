#!/usr/bin/env python3

import json
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "benchmarks" / "sdl3"))

import curve_controlled
import curve_report


def sample(ms):
    return {"wall_ms": ms}


def test_controlled_targets_and_markers():
    assert curve_controlled.TARGET_FILES == (7, 21, 42, 63, 105, 147, 189)
    assert list(curve_controlled.TARGET_FILES) == sorted(set(curve_controlled.TARGET_FILES))
    assert curve_controlled.marker_for(Path("a.c")).startswith(b"\n/*")
    assert curve_controlled.marker_for(Path("a.S")).startswith(b"\n#")
    assert curve_controlled.marker_for(Path("a.s")).startswith(b"\n#")

    with tempfile.TemporaryDirectory(prefix="curve-controlled-test-") as directory:
        path = Path(directory) / "file.c"
        path.write_bytes(b"int x;\n")
        curve_controlled.apply_source_edits([path])
        assert path.read_bytes().endswith(b"/* c-buildsystem scaling benchmark edit */\n")


def test_report_uses_changed_files_axis():
    with tempfile.TemporaryDirectory(prefix="curve-report-test-") as directory:
        out = Path(directory)
        log = out / "benchmark.log"
        curve = {
            "endpoint": "endpoint",
            "source_count": 219,
            "runs_per_point": 3,
            "targets": [7, 21, 42, 63, 105, 147, 189],
            "x_axis": "changed SDL source files",
            "mode": "controlled cumulative endpoint-source comment edits",
            "points": [
                {
                    "changed_files": 7,
                    "rebuilt_tus": 7,
                    "c": sample(700.0),
                    "cmake_ninja": sample(800.0),
                },
                {
                    "changed_files": 63,
                    "rebuilt_tus": 63,
                    "c": sample(5000.0),
                    "cmake_ninja": sample(5500.0),
                },
                {
                    "changed_files": 189,
                    "rebuilt_tus": 189,
                    "c": sample(28000.0),
                    "cmake_ninja": sample(30000.0),
                },
            ],
        }
        log.write_text("CURVE_JSON=" + json.dumps(curve) + "\n")
        (out / "summary.md").write_text("# SDL3 benchmark\n\nBaseline text.\n")

        result = {
            "change": "endpoint",
            "source_count": 219,
            "c": {"noop": sample(10.0), "clean": sample(35000.0)},
            "cmake_ninja": {"noop": sample(15.0), "clean": sample(36000.0)},
        }
        curve_report.augment(result, log, out)

        svg = (out / "timings.svg").read_text()
        summary = (out / "summary.md").read_text()
        saved = json.loads((out / "results.json").read_text())
        assert "Changed SDL source files" in svg
        assert ">7<" in svg and ">63<" in svg and ">189<" in svg and ">219<" in svg
        assert "| Changed source files | Rebuilt TUs |" in summary
        assert saved["scaling"]["x_axis"] == "changed SDL source files"


def main():
    test_controlled_targets_and_markers()
    test_report_uses_changed_files_axis()


if __name__ == "__main__":
    main()
