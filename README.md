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

<!-- sdl3-benchmark:start -->
## SDL3 benchmark

Real SDL3 static debug build, 219 translation units, 2 build jobs on a 4-vCPU GitHub Actions runner.

![SDL3 build-time benchmark](benchmarks/sdl3/timings.svg)

- Clean: `c` 36.48 s; CMake + Ninja 37.32 s.
- Real 7-commit update: `c` 1.02 s; CMake + Ninja 1.18 s.
- Rebuilt TUs: 4 / 219 with `c`; 4 / 219 with Ninja.

Full generated report and raw measurements: [BENCHMARK.md](BENCHMARK.md)
<!-- sdl3-benchmark:end -->

## Notes

- This is a young project.
- I am still changing things.
- Issues and weird edge cases are useful.

## License

MIT
