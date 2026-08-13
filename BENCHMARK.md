# SDL3 benchmark

_Generated automatically by the manually-triggered SDL3 benchmark GitHub Actions workflow. Do not edit benchmark numbers by hand._


`c` vs CMake + Ninja on a real SDL3 static debug build. Lower is better for the measurements below.

| Build | `c` | CMake + Ninja |
| --- | ---: | ---: |
| Clean build | **36.48 s** | 37.32 s |
| No changes | **15.9 ms** | 18.8 ms |
| Real 7-commit update | **1.02 s** | 1.18 s |
| Archive only | **158.7 ms** | 293.7 ms |
| TUs rebuilt | 4 / 219 | 4 / 219 |

## Build-time bars

```text
Clean build
  c              █████████████████████████████  36.48 s
  CMake + Ninja  ██████████████████████████████ 37.32 s

No changes
  c              █████████████████████████      15.9 ms
  CMake + Ninja  ██████████████████████████████ 18.8 ms

Real update
  c              ██████████████████████████     1.02 s
  CMake + Ninja  ██████████████████████████████ 1.18 s

Archive only
  c              ████████████████               158.7 ms
  CMake + Ninja  ██████████████████████████████ 293.7 ms
```

## What this run says

- Clean build: `c` is 2.3% lower on this run.
- No-op: `c` is 15.3% lower on this run.
- Real update: `c` is 13.7% lower on this run.
- Archive only: `c` is 46.0% lower on this run.
- The real update rebuilt **4 TUs with `c`** and **4 TUs with Ninja**.

## Real-update resources

| Metric | `c` | CMake + Ninja |
| --- | ---: | ---: |
| CPU time | 1.78 s | 1.95 s |
| Peak RSS | 141.05 MiB | 141.98 MiB |
| Filesystem outputs | 66,704 | 127,136 |
| Context switches | 72 | 106 |

## Runner

- **CPU:** AMD EPYC 7763 64-Core Processor (4 vCPUs)
- **Jobs:** 2
- **Compiler:** cc (Ubuntu 13.3.0-6ubuntu2~24.04.1) 13.3.0
- **CMake:** cmake version 3.31.6
- **Ninja:** 1.13.2
- **SDL range:** `b07d4882` -> `eba3c7ae` (7 commits, 9 changed files)

The downloadable **`sdl3-benchmark-28`** artifact contains `results.json`, `benchmark.log`, `summary.md`, `timings.svg`, and `resources.svg`.

One runner, one SDL configuration, one real commit range. These numbers describe this run, not every project or machine.

Raw measurements and every sample: [`benchmarks/sdl3/results.json`](benchmarks/sdl3/results.json)
