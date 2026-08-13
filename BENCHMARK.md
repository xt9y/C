# SDL3 benchmark

Measured on 2026-08-13 using a real SDL3 static debug build.

## Test setup

- Ubuntu 24.04 GitHub Actions
- AMD EPYC 9V74, 4 vCPUs
- 2 compile jobs for both tools
- GCC 13.3.0
- CMake 3.31.6 + Ninja 1.13.2
- 219 translation units
- 15 shared semantic compile flags
- Precompiled headers disabled for both
- `c` object cache disabled

The incremental test moves across 7 real SDL commits:

`b07d4882` -> `eba3c7ae`

That range changes 9 files: 101 additions and 85 deletions. SDL's generated revision string is pinned to `benchmark` on both sides so Git metadata itself does not create an extra rebuild.

Both build systems rebuild exactly the same 4 translation units:

- `SDL_gamepad.c`
- `SDL_hidapi.c`
- `SDL_joystick.c`
- `SDL_sysjoystick.c`

## Build times

| Build | `c` | CMake + Ninja |
| --- | ---: | ---: |
| Clean build | **38.22 s** | 39.26 s |
| No changes | **17.9 ms** | 23.9 ms |
| Real 7-commit update | **1.10 s** | 1.29 s |
| Archive only | **176.9 ms** | 332.2 ms |
| TUs rebuilt | 4 / 219 | 4 / 219 |

On this runner, `c` used 2.65% less wall time for the clean build, 24.91% less for a no-op, 14.64% less for the real update, and 46.73% less for the archive-only step.

The clean result is close. The more interesting result is the real update: both systems rebuilt the same 4 translation units, so the 1.10 s vs 1.29 s comparison is doing the same incremental compile work. The archive-only difference is larger, but it is only one part of a build.

## Real update resources

| Metric | `c` | CMake + Ninja |
| --- | ---: | ---: |
| User CPU | 1.60 s | 1.69 s |
| System CPU | 0.33 s | 0.41 s |
| Average CPU use | 175.6% | 164.6% |
| Peak RSS | 141.02 MiB | 140.15 MiB |
| File-system inputs | 0 | 0 |
| File-system outputs | 66,704 | 127,136 |
| Major page faults | 0 | 0 |
| Minor page faults | 73,501 | 86,048 |
| Voluntary context switches | 47 | 70 |
| Involuntary context switches | 30 | 40 |

Memory use is effectively the same for this update. `c` finished with slightly less CPU time and fewer reported filesystem outputs and context switches.

## Clean build resources

| Metric | `c` | CMake + Ninja |
| --- | ---: | ---: |
| User CPU | 65.19 s | 66.98 s |
| System CPU | 10.85 s | 10.96 s |
| Average CPU use | 198.7% | 198.9% |
| Peak RSS | 184.44 MiB | 182.84 MiB |
| File-system inputs | 0 | 0 |
| File-system outputs | 179,952 | 242,680 |
| Major page faults | 3 | 0 |
| Minor page faults | 3,150,767 | 3,180,442 |
| Voluntary context switches | 2,211 | 2,651 |
| Involuntary context switches | 670 | 671 |

The clean builds look very similar in CPU use and memory. Most of the visible difference is wall time and filesystem activity rather than a radically different compile workload.

## No-op and archive resources

| Metric | `c` no-op | Ninja no-op | `c` archive | Ninja archive |
| --- | ---: | ---: | ---: | ---: |
| User CPU | 0.00 s | 0.00 s | 0.07 s | 0.12 s |
| System CPU | 0.01 s | 0.01 s | 0.10 s | 0.20 s |
| Average CPU use | 55.8% | 42.3% | 94.7% | 96.3% |
| Peak RSS | 4.59 MiB | 9.55 MiB | 140.20 MiB | 140.25 MiB |
| File-system inputs | 0 | 0 | 0 | 0 |
| File-system outputs | 376 | 0 | 61,216 | 121,640 |
| Major page faults | 0 | 0 | 0 | 0 |
| Minor page faults | 983 | 1,764 | 12,561 | 25,043 |
| Voluntary context switches | 4 | 10 | 7 | 22 |
| Involuntary context switches | 0.5 | 0 | 14 | 26 |

The no-op runs are tiny, so CPU percentages there are noisy. The archive measurements are more stable and show `c` spending less wall and CPU time on rebuilding the static archive in this setup.

CPU use can exceed 100% because compiler processes run in parallel. File-system input/output values are GNU `time -v` counters, not byte counts.

## Stability

| | `c` | CMake + Ninja |
| --- | ---: | ---: |
| Clean min / median / max | 37.86 / 38.22 / 38.46 s | 38.78 / 39.26 / 39.28 s |
| Clean coefficient of variation | 0.65% | 0.59% |
| No-op min / median / max | 17.7 / 17.9 / 38.5 ms | 22.5 / 23.9 / 24.9 ms |
| No-op coefficient of variation | 30.80% | 2.75% |
| Update min / median / max | 1.065 / 1.098 / 1.117 s | 1.262 / 1.286 / 1.291 s |
| Update coefficient of variation | 1.63% | 0.86% |
| Archive min / median / max | 173.6 / 176.9 / 179.9 ms | 330.2 / 332.2 / 337.4 ms |
| Archive coefficient of variation | 1.28% | 0.88% |

The clean, update, and archive measurements are fairly tight. The `c` no-op coefficient of variation looks large because the first sample was 38.5 ms while the remaining samples were about 17.7-18.7 ms. That first sample is kept in the results.

## Output sizes

| | `c` | CMake + Ninja |
| --- | ---: | ---: |
| Object files | 219 | 219 |
| Object bytes | 15,460,240 | 15,459,992 |
| Object size | 14.744 MiB | 14.744 MiB |
| Static archive bytes | 15,572,434 | 15,566,838 |
| Static archive size | 14.851 MiB | 14.846 MiB |

The generated object and archive sizes are effectively identical, which is another useful check that the two builds are compiling comparable output.

## Setup cost

These are separate measurements because they are not the same operation. The `c` side measures a fresh build-script cache with SDL objects already present. The CMake side measures SDL's full configure and build-file generation step.

| Metric | Fresh `c` build-script cache | CMake configure |
| --- | ---: | ---: |
| Wall time | **228.6 ms** | 15.91 s |
| User CPU | 0.16 s | 9.52 s |
| System CPU | 0.05 s | 6.56 s |
| Average CPU use | 96.2% | 101.0% |
| Peak RSS | 36.22 MiB | 136.95 MiB |
| File-system inputs | 0 | 0 |
| File-system outputs | 3,776 | 39,640 |
| Major page faults | 0 | 0 |
| Minor page faults | 7,251 | 1,171,142 |
| Voluntary context switches | 19 | 10,385 |
| Involuntary context switches | 4 | 535 |
| Min / median / max | 226.4 / 228.6 / 228.8 ms | 15.54 / 15.91 / 16.01 s |
| Coefficient of variation | 0.48% | 1.28% |

This setup table is context, not a direct apples-to-apples `c` versus CMake performance comparison.

## Method

- Clean build: median of 3 runs.
- No changes: median of 10 runs.
- Real update: median of 5 runs.
- Archive only: median of 5 runs.
- Setup measurements: median of 3 runs.
- CMake generates the SDL build metadata first.
- The benchmark generates `build.c` from SDL's `compile_commands.json`, then checks that the same 219 SDL static-target translation units and semantic compile flags are used.
- Both build systems rebuild exactly 4 translation units for the real update.
- SDL runs in Unix console mode with dependency-heavy desktop/audio/GPU backends disabled for a deterministic hosted runner.
- SDL's CMake PCH is disabled so both sides compile the same non-PCH workload.
- `c` object caching is disabled.
- SDL revision metadata is pinned to a constant for both sides.

Raw samples and counters: [`benchmarks/sdl3/results-2026-08-13.json`](benchmarks/sdl3/results-2026-08-13.json)

Run it yourself:

```bash
python3 benchmarks/sdl3/benchmark.py
```

One hosted runner, one SDL configuration, one real commit range. The numbers describe this test, not every C project or machine.
