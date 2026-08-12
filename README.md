# C — A zig inspired Build system manager

A build system and dependency manager for C.

Configure builds in **C**, add Git dependencies directly, and let `c` compile those dependencies itself. Projects do not need CMake, Meson, Autotools, or another dependency build system.

```sh
c build
c run
```

## Why

C has excellent compilers and a fragmented build/package story. `c` aims for the workflow of a modern integrated build system without introducing another configuration language or delegating builds to other build systems.

- `build.c` is real C.
- Project and dependency sources are compiled by the selected C compiler.
- Independent translation units compile in parallel by default.
- Reusable compiled objects are stored in a persistent global cache.
- Git dependencies are globally cached.
- Source dependencies are cached as static archives.
- `c.lock` pins dependencies to exact commits.
- Incremental compilation uses compiler depfiles.
- `compile_commands.json` is generated automatically.
- macOS and Linux are the first-class targets.
- No project-local `vendor/` or dependency clones are required.
- No CMake/Make/Meson invocation is used by `c build`.

## Example

```c
#include <cbuild.h>

void build(C_Build *b) {
    C_Target *app = c_executable(b, "app");
    c_sources(app, "src/*.c");
    c_include(app, "include");
    c_link_system(app, "m");
}
```

```sh
c build
c run
c run -- hello world
```

Commands can be chained:

```sh
c clean build run
c fetch build test
```

## Build performance

`c build` automatically compiles independent source files in parallel using the available CPU count. Override the job count when needed:

```sh
c build -j 8
c build -j4
c build --jobs=4
c build -j 1
```

Project objects remain incremental through compiler depfiles. In addition, successful objects are stored in the global `c` cache. This cache survives `c clean`, so a clean project rebuild can restore unchanged objects instead of recompiling them. Cache entries validate the source, compiler configuration, compile flags, and the contents of included headers before reuse.

The global object cache is enabled by default. Disable it for one command with:

```sh
c build --no-object-cache
```

For environments where compiler process startup is unusually expensive, `c` also supports optional unity/chunk compilation:

```sh
c build --unity
c build --unity=8
```

`--unity` defaults to chunks of 8 compatible source files. C, C++, Objective-C, and Objective-C++ files are chunked separately. Unity mode is opt-in because some projects contain translation-unit-local declarations or macros that collide when multiple source files are included into one generated unit. If a project is not unity-safe, use the default build mode.

Performance defaults can also be configured through the environment:

```text
C_JOBS=8
C_UNITY=8
C_OBJECT_CACHE=0
```

`C_OBJECT_CACHE=0` disables the persistent object cache. `C_UNITY` enables unity mode with the given chunk size. `C_JOBS` overrides automatic CPU-count detection.

## Git dependencies

Dependencies are described in `build.c` and resolved into the global cache.

### Header-only dependency

```c
C_Dependency *stb = c_git(
    b,
    "stb",
    "https://github.com/nothings/stb.git",
    "master"
);

c_dep_header_only(stb);
c_use(app, stb);
```

The dependency checkout is stored globally and its source directory is added as an include path.

### Source dependency

```c
C_Dependency *foo = c_git(
    b,
    "foo",
    "https://github.com/example/foo.git",
    "v1.0.0"
);

c_dep_source(foo);
c_dep_include(foo, "include");
c_dep_sources(foo, "src/*.c");
c_dep_flag(foo, "-DFOO_FEATURE=1");
c_use(app, foo);
```

`c` checks out the pinned revision globally, compiles the declared dependency sources with the selected compiler, archives them into a cached `libfoo.a`, and links that archive into the consuming target.

Dependency compile flags are isolated from the application sources. No project-local clone and no dependency-specific build system are required.

## Lockfile

The first dependency resolution writes `c.lock`:

```toml
[[dependency]]
name = "raylib"
url = "https://github.com/raysan5/raylib.git"
requested = "5.5"
resolved = "<exact git commit>"
```

Commit `c.lock`. Another machine will build the same revisions.

## Commands

```text
c init
c build [target]
c run [target] [-- args...]
c fetch
c update [dependency]
c deps
c test [target]
c clean
c cache [clean]
c doctor
c --version
```

Useful options:

```text
--release / -Drelease
--cc clang
-j N / -jN / --jobs=N
--unity / --unity=N
--no-unity
--object-cache / --no-object-cache
-v / --verbose
```

Compiler selection also respects `CC`. Static archives use `AR` when set, otherwise `ar`.

## Requirements

For normal local projects:

```text
C compiler toolchain
```

For Git dependencies:

```text
Git
```

No CMake, Meson, Ninja, or Autotools installation is required by the build engine.

## Global cache

Linux:

```text
$XDG_CACHE_HOME/c
~/.cache/c
```

macOS:

```text
~/Library/Caches/c
```

Override it with `C_CACHE_DIR`.

The cache contains reusable compiled objects, Git mirrors, immutable source checkouts, compiled dependency archives, and compiled `build.c` modules. `c clean` removes project build output but keeps the global cache. Use `c cache clean` when you explicitly want to discard global cached data.

## Install

```sh
git clone https://github.com/xt9y/C.git
cd C
make && sudo make install
```

This installs:

```text
/usr/local/bin/c
/usr/local/include/cbuild.h
```

Use a custom prefix if required:

```sh
make PREFIX="$HOME/.local" install
```

Make sure `$HOME/.local/bin` is in `PATH`.

## Project creation

```sh
mkdir hello
cd hello
c init
c run
```

Produces:

```text
build.c
src/main.c
.gitignore
```

## Examples

### Raylib

`examples/raylib` builds Raylib 5.5 directly from its C sources. The Git checkout and compiled static archive are globally cached; CMake is not used.

```sh
cd examples/raylib
c build
c run
```

On Linux, Raylib still needs the normal X11/OpenGL/audio development libraries from the operating system. See `examples/raylib/README.md` for the tested Debian/Ubuntu package list.

## Current scope

v0.1 currently includes:

- C11 projects
- executables
- static libraries
- test targets via `c_test()` and `c test`
- Clang/GCC-compatible compilers
- parallel translation-unit compilation
- automatic CPU-count based job selection with `-j` overrides
- incremental object rebuilds
- persistent globally reusable object cache with header-content validation
- optional unity/chunk compilation
- automatic `compile_commands.json`
- system libraries and macOS frameworks
- globally cached Git dependencies
- header-only dependencies
- compiler-built source dependencies
- dependency-specific compiler flags
- lockfile pinning
- debug/release builds
- macOS/Linux

Planned next: native package metadata with exported public/private dependency information, broader parallel build-graph scheduling, shared libraries, cache garbage collection, cross compilation, and richer compiler-native package adapters.

## Philosophy

The project should remain boring to use:

```sh
c build
```

should be the normal case. Build complexity belongs in `build.c`, dependency storage belongs in the global cache, and compilation belongs to the compiler—not another build system.
