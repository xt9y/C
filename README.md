# C - A zig inspired Build system manager

A build system and dependency manager for C.

Configure builds in **C**, add Git dependencies directly, and keep dependency sources/build artifacts in one global cache instead of copying them into every project.

```sh
c build
c run
```

## Why

C has excellent compilers and a fragmented build/package story. `c` aims for the workflow of a modern integrated build system without introducing another configuration language.

- `build.c` is real C.
- Git dependencies are globally cached.
- `c.lock` pins dependencies to exact commits.
- Incremental compilation uses compiler depfiles.
- `compile_commands.json` is generated automatically.
- macOS and Linux are the first-class targets.
- No project-local `vendor/` or dependency clones are required.

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

## Git dependencies

Dependencies are described in `build.c` and resolved into a global cache.

### Header-only/raw source tree

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

For small C libraries, `c` can compile dependency sources directly into the consuming target while keeping the checkout global:

```c
C_Dependency *foo = c_git(b, "foo", "https://github.com/example/foo.git", "v1.0.0");
c_dep_source(foo);
c_dep_include(foo, "include");
c_dep_sources(foo, "src/*.c");
c_use(app, foo);
```

No project-local clone is created.

### CMake library

```c
C_Dependency *raylib = c_git(
    b,
    "raylib",
    "https://github.com/raysan5/raylib.git",
    "5.5"
);

c_dep_cmake(raylib);
c_dep_link(raylib, "raylib");
c_dep_cmake_option(raylib, "-DBUILD_EXAMPLES=OFF");
c_use(app, raylib);
```

`c` keeps one bare Git mirror per repository, checks resolved commits out into the global cache, and stores CMake install artifacts globally as well. Libraries can still require platform-specific system libraries/frameworks; see the tested Raylib example in `examples/raylib` for a complete case.

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
-v / --verbose
```

Compiler selection also respects `CC`.

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

The cache is split into reusable Git mirrors, source checkouts, dependency build directories, installed dependency artifacts, and compiled `build.c` modules.

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

`examples/raylib` is a complete Git + CMake dependency example. Raylib is fetched from its upstream repository, pinned by `c.lock`, built into the global cache, and linked into a small C application.

```sh
cd examples/raylib
c build
c run
```

On Linux, Raylib still needs the normal X11/OpenGL/audio development packages from the operating system. See `examples/raylib/README.md` for the tested Debian/Ubuntu package list.

## Current scope

v0.1 intentionally focuses on the core workflow:

- C11 projects
- executables
- static libraries
- test targets via `c_test()` and `c test`
- Clang/GCC-compatible compilers
- incremental object rebuilds
- automatic `compile_commands.json`
- system libraries and macOS frameworks
- globally cached Git dependencies
- header-only dependencies
- raw/source dependencies
- CMake dependencies
- lockfile pinning
- debug/release builds
- macOS/Linux

Planned next: native `c` packages with exported public/private dependency metadata, parallel build graph execution, shared libraries, `pkg-config` integration, cache garbage collection, cross compilation, and richer package adapters.

## Philosophy

The project should remain boring to use:

```sh
c build
```

should be the normal case. Build complexity belongs in `build.c`, and dependency storage belongs in the global cache—not in every repository.
