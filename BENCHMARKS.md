# Benchmarks

Real SDL3 build, measured on 2026-08-13.

- Ubuntu 24.04 GitHub Actions
- AMD EPYC 7763
- 4 vCPUs
- 2 build jobs for both tools
- GCC 13.3.0
- CMake 3.31.6
- Ninja 1.13.2
- SDL3 static library
- 219 translation units
- Debug build
- Precompiled headers disabled for both sides

| Build | Clean | No changes | Real SDL commit |
| --- | ---: | ---: | ---: |
| `c` | 36.48 s | 14.5 ms | 508.7 ms |
| CMake + Ninja | 37.41 s | 18.4 ms | 865.3 ms |

The incremental test is not a touched file.

It builds SDL at:

`b340ddcd7b44511f7b49005ba4a91a3c9907f77e`

Then checks out the very next SDL commit:

`b640b804a8cfe9f998ac82650a32c5e6e6cd4571`

That commit changes `src/core/linux/SDL_evdev.c` by 5 lines.

Method:

- Clean: median of 3 clean compile/archive runs after build configuration is prepared.
- No changes: median of 10 rebuilds.
- Real SDL commit: median of 5 rebuilds after moving from the pinned base commit to the adjacent commit.
- CMake configuration time is not included in the CMake + Ninja clean number.
- `c` object caching is disabled.
- Both builds use SDL's Unix console configuration so the benchmark does not depend on X11/Wayland packages.
- SDL's CMake precompiled header is disabled because `c` does not currently use the same PCH path. This keeps the compile workload comparable.

One hosted runner. One SDL configuration. Not a universal speed claim.

Raw samples: [`benchmarks/sdl3/results-2026-08-13.json`](benchmarks/sdl3/results-2026-08-13.json)

Run it yourself:

```bash
python3 benchmarks/sdl3/benchmark.py
```
