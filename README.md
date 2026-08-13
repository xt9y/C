# c

Build C with C.

```c
#include <cbuild.h>

void build(C_Build *b) {
  C_Target *app = c_executable(b, "app");
  c_sources(app, "src/*.c");
}
```

- `build.c` is normal C.
- Git dependencies.
- Incremental builds.
- Parallel compilation.
- Global object cache.
- Lockfiles.
- `compile_commands.json`.
- macOS + Linux.

## Why

- I got tired of build config becoming another language.
- I wanted one small tool.
- One command to build.
- One command to run.
- I use it on my own projects.
- If something annoys me there, I usually end up fixing it here.

## Real use

- [BGE](https://github.com/xt9y/BGE) builds with `c`.
- There is also a small raylib example in `examples/raylib`.

## Install

```bash
git clone https://github.com/xt9y/C.git
cd C
make
sudo make install
```

Then:

```bash
c build
c run
```

Docs (Thanks to AI): https://xt9y.de/c.html

## SDL3 benchmark

I wanted something more useful than a generated benchmark, so this builds SDL3.

Measured on 2026-08-13:

- Ubuntu 24.04 GitHub Actions.
- AMD EPYC 9V74, 4 vCPUs.
- 2 compile jobs for both tools.
- GCC 13.3.0.
- CMake 3.31.6 + Ninja 1.13.2.
- SDL3 static debug build.
- 219 translation units.
- Precompiled headers disabled for both.
- `c` object cache disabled.

The incremental test moves across 7 real SDL commits:

`b07d4882` -> `eba3c7ae`

That range changes 9 files: 101 additions and 85 deletions. SDL's generated revision string is pinned to `benchmark` on both sides so Git metadata itself does not create an extra rebuild. Both build systems rebuild exactly 4 translation units.

### Time

| | `c` | CMake + Ninja |
| --- | ---: | ---: |
| Clean build | **38.22 s** | 39.26 s |
| No changes | **17.9 ms** | 23.9 ms |
| Real 7-commit update | **1.10 s** | 1.29 s |
| Archive only | **176.9 ms** | 332.2 ms |
| TUs rebuilt | 4 / 219 | 4 / 219 |

On this runner, `c` used 2.6% less wall time for the clean build, 24.9% less for a no-op, 14.6% less for the real update, and 46.7% less for the archive-only step.

### Real update resources

| | `c` | CMake + Ninja |
| --- | ---: | ---: |
| User CPU | 1.60 s | 1.69 s |
| System CPU | 0.33 s | 0.41 s |
| Average CPU use | 176% | 165% |
| Peak RSS | 141.0 MiB | 140.1 MiB |
| File-system outputs | 66,704 | 127,136 |
| Major page faults | 0 | 0 |
| Minor page faults | 73,501 | 86,048 |
| Voluntary context switches | 47 | 70 |
| Involuntary context switches | 30 | 40 |

### Clean build resources

| | `c` | CMake + Ninja |
| --- | ---: | ---: |
| User CPU | 65.19 s | 66.98 s |
| System CPU | 10.85 s | 10.96 s |
| Average CPU use | 199% | 199% |
| Peak RSS | 184.4 MiB | 182.8 MiB |
| File-system outputs | 179,952 | 242,680 |
| Major page faults | 3 | 0 |
| Minor page faults | 3,150,767 | 3,180,442 |
| Voluntary context switches | 2,211 | 2,651 |
| Involuntary context switches | 670 | 671 |

`File-system outputs` is the counter reported by GNU `time -v`; it is not a byte count.

### Stability

| | `c` | CMake + Ninja |
| --- | ---: | ---: |
| Clean min -> max | 37.86 -> 38.46 s | 38.78 -> 39.28 s |
| Clean coefficient of variation | 0.65% | 0.59% |
| No-op min -> max | 17.7 -> 38.5 ms | 22.5 -> 24.9 ms |
| No-op coefficient of variation | 30.80% | 2.75% |
| Update min -> max | 1.065 -> 1.117 s | 1.262 -> 1.291 s |
| Update coefficient of variation | 1.63% | 0.86% |
| Archive min -> max | 173.6 -> 179.9 ms | 330.2 -> 337.4 ms |
| Archive coefficient of variation | 1.28% | 0.88% |

The first `c` no-op sample was 38.5 ms; the remaining samples were about 17.7-18.7 ms. The table keeps that sample instead of throwing it away.

### Output

| | `c` | CMake + Ninja |
| --- | ---: | ---: |
| Object files | 219 | 219 |
| Object bytes | 15,460,240 | 15,459,992 |
| Static archive bytes | 15,572,434 | 15,566,838 |

### Setup cost

- Fresh `c` build-script cache: **228.6 ms** median.
- CMake configure: **15.91 s** median.

These are shown separately because they are not the same operation. The `c` number measures compiling/loading `build.c` plus graph scanning with the SDL objects already present. The CMake number is SDL's CMake configuration step. Neither is included in the primary clean-build table.

### Method

- Clean build: median of 3 runs.
- No changes: median of 10 runs.
- Real update: median of 5 runs.
- Archive only: median of 5 runs.
- Setup measurements: median of 3 runs.
- CMake generates the SDL build metadata first.
- The benchmark generates `build.c` from SDL's `compile_commands.json`, then checks that the same 219 SDL static-target translation units and semantic compile flags are used.
- SDL runs in Unix console mode with dependency-heavy desktop/audio/GPU backends disabled for a deterministic hosted runner.
- SDL's CMake PCH is disabled so both sides compile the same non-PCH workload.
- `c` object caching is disabled.
- SDL revision metadata is pinned to a constant for both sides.

Raw samples and counters: [`benchmarks/sdl3/results-2026-08-13.json`](benchmarks/sdl3/results-2026-08-13.json)

Run it yourself:

```bash
python3 benchmarks/sdl3/benchmark.py
```

One hosted runner. One SDL configuration. One real commit range. This is not a universal speed claim.

## Notes

- This is a young project.
- I am still changing things.
- Issues and weird edge cases are useful.

## License

MIT
