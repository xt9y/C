# Benchmark suite

_Generated from pinned, reproducible benchmark workflows. Do not edit benchmark numbers by hand._

## Overview

| Workload | `c` | CMake + Ninja | Result |
| --- | ---: | ---: | --- |
| cJSON fresh setup | 58.6 ms | 214.4 ms | `c` 72.6% faster |
| cJSON no-op (1 TU) | 4.1 ms | 5.2 ms | `c` 21.5% faster |
| SDL3 no-op (219 TUs) | 15.9 ms | 18.6 ms | `c` 14.4% faster |
| SDL3 clean (219 TUs) | 36.59 s | 37.09 s | `c` 1.3% faster |
| libcurl common-header fan-out (192 TUs) | 6.50 s | 6.74 s | `c` 3.7% faster |
| Wireshark 10 source changes | 1.78 s | 4.62 s | `c` 61.4% faster |
| Wireshark clean (1640 TUs) | 119.98 s | 127.47 s | `c` 5.9% faster |

Each row compares the two build systems on the same hosted runner, source tree, source set, semantic flags and build-job count. Object caching is disabled for measured compilation. Cross-row timing comparisons are not meaningful because separate workflow runs may land on different hosted machines.

## SDL3 — incremental scaling

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

Raw samples: [`benchmarks/sdl3/results.json`](benchmarks/sdl3/results.json)

## cJSON — startup and tiny-project overhead

Pinned cJSON v1.7.19, one C translation unit. Lower is better.

| Test | `c` | CMake + Ninja |
| --- | ---: | ---: |
| Fresh build-system setup | 58.6 ms | 214.4 ms |
| Clean build | 169.1 ms | 217.6 ms |
| No changes | 4.1 ms | 5.2 ms |
| One source changed | 170.5 ms | 220.0 ms |

No-op is the median of 30 runs. Object caching is disabled. Both systems rebuild exactly one TU after the source edit.

Raw samples: [`benchmarks/cjson/results.json`](benchmarks/cjson/results.json)

## libcurl — header fan-out

Pinned libcurl curl-8_21_0. A harmless content change is made to `lib/curl_setup.h`. Both systems must invalidate the same number of translation units.

- Target translation units: **192**
- Translation units invalidated: **192**

| Test | `c` | CMake + Ninja |
| --- | ---: | ---: |
| No changes | 13.0 ms | 15.4 ms |
| Header fan-out rebuild | 6.50 s | 6.74 s |
| Invocation to first compiler | 22.6 ms | 18.7 ms |
| Clean build | 6.48 s | 6.71 s |

Object caching is disabled. Fan-out wall time is the median of 3 runs; no-op is the median of 10.

Raw samples: [`benchmarks/fanout/results.json`](benchmarks/fanout/results.json)

## Wireshark — large-project stress

Pinned Wireshark `wireshark-4.4.9` dissector workload: **1640 translation units**, 2 build jobs. Lower is better.

| Test | `c` | CMake + Ninja |
| --- | ---: | ---: |
| Clean compile + archive | 119.98 s | 127.47 s |
| No changes | 60.0 ms | 58.7 ms |
| 1 source changed | 1.48 s | 4.14 s |
| 10 sources changed | 1.78 s | 4.62 s |

The Ninja path includes a timestamp-aware archive of the same object target so both sides perform compile + static-archive work. Object caching is disabled. Controlled source points fail unless both systems rebuild exactly the requested TU count.

Raw samples: [`benchmarks/large/results.json`](benchmarks/large/results.json)

## Runner snapshots

| Benchmark | Date | CPU | vCPUs | Jobs |
| --- | --- | --- | ---: | ---: |
| SDL3 | 2026-08-14 | AMD EPYC 7763 64-Core Processor | 4 | 2 |
| cJSON | 2026-08-14 | AMD EPYC 9V74 80-Core Processor | 4 | 1 |
| libcurl | 2026-08-14 | AMD EPYC 9V74 80-Core Processor | 4 | 2 |
| Wireshark | 2026-08-14 | Intel(R) Xeon(R) Platinum 8370C CPU @ 2.80GHz | 4 | 2 |

## What each workload tests

- **cJSON:** startup, graph checking and fixed overhead where compiler work is tiny.
- **SDL3:** controlled incremental scaling from no changes through a clean build, plus a real historical update.
- **libcurl:** dependency invalidation after changing one widely included header; the workflow fails if the two systems disagree on rebuilt TU count.
- **Wireshark:** a 1,000+ TU stress workload with controlled 1- and 10-source edits; Ninja receives a timestamp-aware archive step so both sides perform compile + static-archive work.
