# C-BuildSystem

[![CI](https://github.com/xt9y/C-BuildSystem/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/xt9y/C-BuildSystem/actions/workflows/ci.yml?query=branch%3Amain)

Build C with C.

```c
#include <cbuild.h>

void build(C_Build *b) {
    C_Target *core = c_static_library(b, "core");
    c_sources(core, "src/core/*.c");

    C_Target *app = c_executable(b, "app");
    c_sources(app, "src/main.c");
    c_link_target(app, core);
}
```

- `build.c` is normal C.
- Executables, static libraries, shared libraries and test targets.
- Target-to-target dependency graphs with cycle detection.
- Generated sources with tracked inputs.
- Git dependencies and lockfiles.
- Incremental builds and parallel compilation.
- Persistent global object cache.
- `compile_commands.json`.
- Rebuild explanations with `c build --explain`.
- macOS + Linux.
- Existing CMake and Make projects can use `c build` without a `build.c`.

## Build API

The public API deliberately stays small:

```c
C_Target *lib = c_shared_library(b, "engine");
c_sources(lib, "engine/*.c");
c_standard(lib, C_STANDARD_C17);
c_warnings_strict(lib);

C_Target *app = c_executable(b, "game");
c_sources(app, "game/*.c");
c_link_target(app, lib);
```

Generated files can participate in the incremental graph:

```c
c_generate(app,
           "generated/version.c",
           "version.txt",
           "./tools/make-version version.txt generated/version.c");
```

Changing the generator input or command invalidates the generated output.

`cbuild.h` targets **source compatibility** for build scripts. Its public struct layout is not promised as a frozen binary ABI before 1.0.

## Commands

```bash
c build
c run
c test
c clean
c doctor
c build --explain
c build --release
c build -j8
c cache
c cache stats
c cache clean
c deps
c deps tree
c deps clean
c update [dependency]
c watch
c --version
```

The CLI also supports chaining, for example `c clean build test`.

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
c build --release               # CMake
c build -- MODE=release         # backend-specific Make arguments
C_CMAKE_BUILD_DIR=build c build # reuse an existing configured CMake tree
```

`c convert` creates a `build.c` compatibility bridge while keeping the original CMake/Make configuration authoritative:

```bash
c convert
c convert CMakeLists.txt
c convert Makefile
```

That bridge is the lossless conversion mode: it preserves backend behavior instead of pretending arbitrary CMake/Make logic can always be translated into native C-BuildSystem targets.

## Correctness

The normal CI path is correctness-first: Linux and macOS builds/tests, sanitizer coverage, fuzz smoke tests, API guards, incremental invalidation tests, concurrent-cache tests, target-graph tests and generated-source tests.

Long-running real-project benchmarks and extended fuzzing are scheduled/manual jobs rather than blockers on every push. The benchmark suite covers cJSON, libcurl header fan-out, SDL3 and Wireshark.

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
c doctor
c build
c run
```

Docs (Thanks to AI): https://xt9y.de/c.html

See `ROADMAP.md` for stabilization milestones, `CHANGELOG.md` for user-visible changes, `COMPATIBILITY.md` for the supported platform/compiler contract, and `RELEASING.md` for the release procedure.

## Notes

- The project is still pre-1.0 and the API can evolve.
- Build correctness and reproducibility take priority over benchmark wins.
- Issues and weird edge cases are useful.

## License

MIT
