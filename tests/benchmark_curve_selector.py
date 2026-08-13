#!/usr/bin/env python3

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "benchmarks" / "sdl3"))

from curve_selector import choose_ranges


def main():
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

    # Near-exact real points should all be retained and stay strictly ordered
    # by rebuild size.
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


if __name__ == "__main__":
    main()
