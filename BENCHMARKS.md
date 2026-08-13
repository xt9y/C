# Benchmarks

Real SDL3 build, measured on 2026-08-13.

- Ubuntu 24.04 GitHub Actions
- Intel Xeon Platinum 8573C
- 4 vCPUs
- 2 build jobs for both tools
- GCC 13.3.0
- CMake 3.31.6
- Ninja 1.13.2
- SDL3 static library
- 219 translation units
- Debug build
- Precompiled headers disabled for both sides

| Build | Clean | No changes | Real SDL update |
| --- | ---: | ---: | ---: |
| `c` | 34.57 s | 10.9 ms | 923.3 ms |
| CMake + Ninja | 35.86 s | 14.2 ms | 1.56 s |

The incremental test is not a touched file or generated edit.

It builds SDL at:

`b07d48821698af08545cb38e293ead99753bfc35`

Then checks out:

`eba3c7ae0ad85c13051179d196e5187ccb96cf6a`

That is a real range of 7 consecutive SDL commits changing 9 files, including Linux core and joystick code.

Changed files in the range:

- `src/core/linux/SDL_udev.c`
- `src/joystick/SDL_gamepad.c`
- `src/joystick/SDL_joystick.c`
- `src/joystick/hidapi/SDL_hidapi_gamesir.c`
- `src/joystick/hidapi/SDL_hidapi_zuiki.c`
- `src/joystick/usb_ids.h`
- `src/video/wayland/SDL_waylanddatamanager.h`
- `src/video/wayland/SDL_waylandevents.c`
- `docs/README-gdk.md`

The benchmark uses SDL's dependency-light Unix console configuration, so disabled backends such as Wayland and HIDAPI are still present in the real checkout range but are not compiled into this target. Both build systems see the same source tree and the same enabled SDL3 static-library workload.

Method:

- Clean: median of 3 clean compile/archive runs after build configuration is prepared.
- No changes: median of 10 rebuilds.
- Real SDL update: median of 5 rebuilds after moving across the pinned 7-commit range.
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
