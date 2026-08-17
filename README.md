# C-BuildSystem

[![CI](https://github.com/xt9y/C-BuildSystem/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/xt9y/C-BuildSystem/actions/workflows/ci.yml?query=branch%3Amain)

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
- Existing CMake and Make projects can use `c build` without a `build.c`.

## Existing projects

If there is no `build.c`, `c build` falls back in this order:

- `CMakeLists.txt`
- `GNUmakefile`
- `Makefile`
- `makefile`

```bash
c build
c build my_target
c build my_target -j8
c build --release          # CMake
c build -- MODE=release    # backend-specific Make arguments
C_CMAKE_BUILD_DIR=build c build  # reuse an existing configured CMake tree
```

`c convert` creates a `build.c` compatibility bridge while keeping the original CMake/Make configuration authoritative:

```bash
c convert
c convert CMakeLists.txt
c convert Makefile
```

That bridge is the lossless conversion mode: it preserves backend behavior instead of pretending arbitrary CMake/Make logic can always be translated into native C-BuildSystem targets.

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

## Notes

- This is a young project.
- I am still changing things.
- Issues and weird edge cases are useful.

## License

MIT
