#!/usr/bin/env python3

from benchmark_curve import main as curve_main
from benchmark_stats import main as baseline_main


if __name__ == "__main__":
    baseline_main()
    curve_main()
