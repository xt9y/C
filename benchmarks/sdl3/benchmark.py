#!/usr/bin/env python3

import benchmark_curve as curve
import benchmark_stats as stats
from benchmark_stats import main as baseline_main
from curve_selector import select_ranges as adaptive_select_ranges


_base_cmake_args = stats.cmake_args


def fixed_graph_cmake_args(source, build):
    return _base_cmake_args(source, build) + ["-DCMAKE_SUPPRESS_REGENERATION=ON"]


if __name__ == "__main__":
    baseline_main()
    stats.cmake_args = fixed_graph_cmake_args
    curve.select_ranges = adaptive_select_ranges
    curve.main()
