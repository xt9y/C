# Benchmarks

Measured on 2026-08-13.

- Linux x86_64
- AMD EPYC 9V74
- 5 vCPUs
- GCC 14.2.0
- CMake 3.31.6
- Ninja 1.12.1
- Make 4.4.1
- 201 C translation units
- Debug build

| Build | First | No changes | One file |
| --- | ---: | ---: | ---: |
| `c` default (2 jobs) | 3054 ms | 3.8 ms | 42.8 ms |
| `c -j5` | 1640 ms | 3.4 ms | 45.5 ms |
| CMake + Ninja `-j5` | 1668 ms | 3.4 ms | 76.1 ms |
| Make `-j5` | 1572 ms | 36.6 ms | 105.2 ms |

- First: median of 3 clean builds.
- No changes: median of 10 rebuilds.
- One file: median of 8 rebuilds.
- CMake + Ninja first build includes configure + build.
- CMake configure alone was about 138 ms.
- Ninja's first build after configure was about 1521 ms.
- `c` cold runs use a fresh cache.
- Default `c` uses roughly half the CPUs.
- `c -j5` matches the worker count used by Ninja and Make.

So on this machine:

- Equal worker count: `c` and CMake + Ninja were basically tied end-to-end on the first build.
- Ninja itself was a little faster once CMake had already configured the project.
- `c` and Ninja were basically tied with no changes.
- This project rebuilt one changed C file faster with `c`.
- Make had the fastest clean build here, but slower no-op and one-file rebuilds.

One machine. One synthetic project. Not a universal speed claim.

Run it yourself:

```bash
python3 benchmarks/build_tools.py
```
