# SDL3 benchmark

_Generated automatically by the manually-triggered SDL3 benchmark GitHub Actions workflow. Do not edit benchmark numbers by hand._


## Scaling curve

![SDL3 incremental scaling](benchmarks/sdl3/timings.svg)

The x-axis is the **number of SDL source files changed**. The controlled points edit exactly 7, 21, 42, 63, 105, 147, and 189 endpoint translation units with harmless comments, using a deterministic mixed ordering across SDL subsystems. Larger points are cumulative supersets of smaller points.

This controlled curve is intentionally separate from the real 7-commit SDL update reported below: the real update shows real-world behavior, while this curve isolates how each build system scales as the amount of invalidated source code grows.

| Changed source files | Rebuilt TUs | `c` | CMake + Ninja | Result |
| ---: | ---: | ---: | ---: | --- |
| 0 | 0 | 14.3 ms | 16.6 ms | `c` 13.7% faster |
| 7 | 7 | 1.27 s | 1.53 s | `c` 17.0% faster |
| 21 | 21 | 3.17 s | 3.37 s | `c` 5.9% faster |
| 42 | 42 | 6.32 s | 6.49 s | `c` 2.6% faster |
| 63 | 63 | 9.12 s | 9.36 s | `c` 2.5% faster |
| 105 | 105 | 13.92 s | 14.72 s | `c` 5.5% faster |
| 147 | 147 | 20.05 s | 20.71 s | `c` 3.2% faster |
| 189 | 189 | 26.26 s | 26.93 s | `c` 2.5% faster |
| 219 | 219 | 30.51 s | 31.27 s | `c` 2.5% faster |

Each controlled incremental point is measured 2 times. The benchmark fails rather than publish a point unless both tools rebuild exactly the requested number of translation units.

`c` vs CMake + Ninja on a real SDL3 static debug build. Lower is better.

## Core measurements

| Build | `c` | CMake + Ninja |
| --- | ---: | ---: |
| Clean build | 30.51 s | 31.27 s |
| No changes | 14.3 ms | 16.6 ms |
| Real 7-commit anchor update | 858.4 ms | 982.0 ms |
| Archive only | 141.1 ms | 275.6 ms |
| Anchor TUs rebuilt | 4 / 219 | 4 / 219 |

## Anchor update resources

![SDL3 anchor-update resources](benchmarks/sdl3/resources.svg)

| Metric | `c` | CMake + Ninja |
| --- | ---: | ---: |
| CPU time | 1.49 s | 1.59 s |
| Peak RSS | 156.27 MiB | 157.07 MiB |
| Filesystem outputs | 66,704 | 127,136 |
| Context switches | 68 | 105 |

## Setup cost

| Metric | Fresh `c` build-script cache | CMake configure |
| --- | ---: | ---: |
| Wall time | 178.4 ms | 14.91 s |
| Peak RSS | 36.29 MiB | 152.24 MiB |

## Runner

- **Date:** 2026-08-14
- **CPU:** AMD EPYC 9V74 80-Core Processor (4 vCPUs)
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

The downloadable **`sdl3-benchmark-33`** artifact contains the raw log, JSON measurements and SVG charts.

Raw measurements and every sample: [`benchmarks/sdl3/results.json`](benchmarks/sdl3/results.json)
