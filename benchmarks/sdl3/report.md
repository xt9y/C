# SDL3 benchmark

## Scaling curve

![SDL3 incremental scaling](benchmarks/sdl3/timings.svg)

The x-axis is the **number of SDL source files changed**. The controlled points edit exactly 7, 21, 42, 63, 105, 147, and 189 endpoint translation units with harmless comments, using a deterministic mixed ordering across SDL subsystems. Larger points are cumulative supersets of smaller points.

This controlled curve is intentionally separate from the real 7-commit SDL update reported below: the real update shows real-world behavior, while this curve isolates how each build system scales as the amount of invalidated source code grows.

| Changed source files | Rebuilt TUs | `c` | CMake + Ninja | Result |
| ---: | ---: | ---: | ---: | --- |
| 0 | 0 | 15.9 ms | 18.6 ms | `c` 14.4% faster |
| 7 | 7 | 1.52 s | 1.72 s | `c` 11.6% faster |
| 21 | 21 | 3.76 s | 4.02 s | `c` 6.5% faster |
| 42 | 42 | 7.39 s | 7.68 s | `c` 3.9% faster |
| 63 | 63 | 10.61 s | 11.02 s | `c` 3.8% faster |
| 105 | 105 | 17.63 s | 17.87 s | `c` 1.3% faster |
| 147 | 147 | 24.42 s | 25.20 s | `c` 3.1% faster |
| 189 | 189 | 31.63 s | 32.95 s | `c` 4.0% faster |
| 219 | 219 | 36.59 s | 37.09 s | `c` 1.3% faster |

Each controlled incremental point is measured 2 times. The benchmark fails rather than publish a point unless both tools rebuild exactly the requested number of translation units.

`c` vs CMake + Ninja on a real SDL3 static debug build. Lower is better.

## Core measurements

| Build | `c` | CMake + Ninja |
| --- | ---: | ---: |
| Clean build | 36.59 s | 37.09 s |
| No changes | 15.9 ms | 18.6 ms |
| Real 7-commit anchor update | 1.04 s | 1.18 s |
| Archive only | 164.4 ms | 299.5 ms |
| Anchor TUs rebuilt | 4 / 219 | 4 / 219 |

## Anchor update resources

![SDL3 anchor-update resources](benchmarks/sdl3/resources.svg)

| Metric | `c` | CMake + Ninja |
| --- | ---: | ---: |
| CPU time | 1.83 s | 1.97 s |
| Peak RSS | 141.08 MiB | 140.21 MiB |
| Filesystem outputs | 66,704 | 127,136 |
| Context switches | 71 | 107 |

## Setup cost

| Metric | Fresh `c` build-script cache | CMake configure |
| --- | ---: | ---: |
| Wall time | 228.3 ms | 13.72 s |
| Peak RSS | 36.20 MiB | 136.94 MiB |

## Runner

- **Date:** 2026-08-14
- **CPU:** AMD EPYC 7763 64-Core Processor (4 vCPUs)
- **Jobs:** 2
- **Compiler:** cc (Ubuntu 13.3.0-6ubuntu2~24.04.1) 13.3.0
- **CMake:** cmake version 3.31.6
- **Ninja:** 1.13.2
- **SDL endpoint:** `eba3c7ae0ad8`
- **Object cache:** disabled
- **PCH:** disabled

## Method

- Clean build: median of 3 runs.
- No changes: median of 10 runs.
- Anchor update: median of 5 runs.
- Both systems use the same SDL static-target source set and semantic compile flags.
- SDL revision metadata is pinned to `benchmark`.
- Hosted-runner measurements describe this run, not every machine.

The downloadable **`sdl3-benchmark-34`** artifact contains the raw log, JSON measurements and SVG charts.
