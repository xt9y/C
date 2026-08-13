# Benchmarks

Measured on 2026-08-13.

- Linux x86_64
- AMD EPYC 9V74
- 5 vCPUs
- GCC 14.2.0
- 201 C translation units
- Debug build

| Build | First | No changes | One file |
| --- | ---: | ---: | ---: |
| `c` default (2 jobs) | 3054 ms | 3.8 ms | 42.8 ms |
| `c -j5` | 1640 ms | 3.4 ms | 45.5 ms |
| CMake 3.31.6 + Ninja 1.12.1 `-j5` | 1668 ms | 3.4 ms | 76.1 ms |
| Make 4.4.1 `-j5` | 1572 ms | 36.6 ms | 105.2 ms |

- First: median of 3 clean builds.
- No changes: median of 10 rebuilds.
- One file: median of 8 rebuilds.
- CMake first build includes configure + Ninja.
- `c` cold runs use a fresh cache.
- Default `c` uses roughly half the CPUs.
- `c -j5` matches the worker count used by Ninja and Make.

One machine. One synthetic project. Not a universal speed claim.

Run it yourself:

```bash
python3 benchmarks/build_tools.py
```
