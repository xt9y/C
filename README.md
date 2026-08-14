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
git clone https://github.com/xt9y/C-BuildSystem.git
cd C-BuildSystem
make
sudo make install
```

Then:

```bash
c build
c run
```

Docs (Thanks to AI): https://xt9y.de/c.html

<!-- benchmark-suite:start -->
## Performance

Real C projects, identical CMake-derived source sets and semantic compile flags. Lower is better.

| Workload | `c` | CMake + Ninja | Result |
| --- | ---: | ---: | --- |
| cJSON fresh setup | 57.3 ms | 203.1 ms | `c` 71.8% faster |
| cJSON no-op (1 TU) | 4.1 ms | 5.2 ms | `c` 21.0% faster |
| SDL3 no-op (219 TUs) | 15.9 ms | 18.6 ms | `c` 14.4% faster |
| SDL3 clean (219 TUs) | 36.59 s | 37.09 s | `c` 1.3% faster |
| libcurl common-header fan-out (192 TUs) | 6.50 s | 6.74 s | `c` 3.7% faster |
| Wireshark 10 source changes | 1.78 s | 4.62 s | `c` 61.4% faster |
| Wireshark clean (1640 TUs) | 119.98 s | 127.47 s | `c` 5.9% faster |

The projects are pinned and raw samples are checked in. Hosted-runner results should be compared **within a row**, not across separate workflow runs.

Full methodology, scaling data and raw measurements: [BENCHMARK.md](BENCHMARK.md)
<!-- benchmark-suite:end -->

## Notes

- This is a young project.
- I am still changing things.
- Issues and weird edge cases are useful.

## License

MIT