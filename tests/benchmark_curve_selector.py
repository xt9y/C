#!/usr/bin/env python3

from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "benchmarks" / "sdl3"))

from curve_selector import choose_ranges
import curve_history


def run(cmd, cwd):
    subprocess.run(cmd, cwd=cwd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def test_selector():
    # If no real range exists near 16 TUs, skip that target instead of
    # consuming the ~32-TU point or failing the whole benchmark.
    candidates = [
        ("r8", 10, 8, 7),
        ("r33", 20, 33, 30),
        ("r65", 30, 65, 60),
        ("r129", 40, 129, 120),
        ("r191", 50, 191, 180),
    ]
    selected = choose_ranges(candidates, (8, 16, 32, 64, 128, 192), 219)
    counts = [item[1][2] for item in selected]
    assert counts == [8, 33, 65, 129, 191], counts

    candidates = [
        ("a", 5, 7, 5),
        ("b", 6, 17, 12),
        ("c", 7, 31, 25),
        ("d", 8, 66, 55),
        ("e", 9, 127, 110),
        ("f", 10, 193, 170),
    ]
    selected = choose_ranges(candidates, (8, 16, 32, 64, 128, 192), 219)
    counts = [item[1][2] for item in selected]
    assert counts == [7, 17, 31, 66, 127, 193], counts
    assert all(a < b for a, b in zip(counts, counts[1:])), counts


def test_fixed_endpoint_history():
    with tempfile.TemporaryDirectory(prefix="curve-history-test-") as directory:
        repo = Path(directory)
        run(["git", "init", "-q"], repo)
        run(["git", "config", "user.email", "ci@example.invalid"], repo)
        run(["git", "config", "user.name", "CI"], repo)

        (repo / "same.c").write_text("old\n")
        run(["git", "add", "same.c"], repo)
        run(["git", "commit", "-qm", "base"], repo)
        base = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip()

        (repo / "same.c").write_text("new\n")
        (repo / "added.c").write_text("endpoint only\n")
        run(["git", "add", "same.c", "added.c"], repo)
        run(["git", "commit", "-qm", "endpoint"], repo)
        endpoint = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip()

        old_change = curve_history.CHANGE
        try:
            curve_history.CHANGE = endpoint
            paths = curve_history.modified_paths(repo, base)
            assert paths == ["same.c"], paths

            curve_history.set_historical_state(repo, base, paths)
            assert (repo / "same.c").read_text() == "old\n"
            assert (repo / "added.c").read_text() == "endpoint only\n"

            curve_history.restore_endpoint_paths(repo, paths)
            assert (repo / "same.c").read_text() == "new\n"
            assert (repo / "added.c").read_text() == "endpoint only\n"
        finally:
            curve_history.CHANGE = old_change


def main():
    test_selector()
    test_fixed_endpoint_history()


if __name__ == "__main__":
    main()
