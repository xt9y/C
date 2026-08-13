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
- Project and dependency sources are compiled by the selected compiler.
- Independent translation units compile in parallel.
- The normal default uses roughly half of the available CPU cores so a build does not monopolize the machine.
- Historical compile timings are used to start expensive translation units first.
- Reusable compiled objects are stored in a persistent global cache.
- Header hashes and parsed dependency information are persistently cached.
- Git dependencies are globally cached.
- Independent source dependencies can build concurrently.
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

### Parallel compilation

`c build` automatically compiles independent source files in parallel. The default is approximately **half of the available logical CPUs**, which keeps the machine responsive while still giving large clean builds substantial parallelism.

Override it when needed:

```sh
c build -j 8
c build -j4
c build --jobs=4
c build -j 1
```

`C_JOBS=N` provides the same override through the environment.

For a machine that is already under load, optional adaptive scheduling can lower the active job count further:

```sh
c build --adaptive-jobs
C_ADAPTIVE_JOBS=1 c build
```

The compiler queue is not simple FIFO. `c` records historical translation-unit timings and schedules the most expensive work first. This reduces the common tail where most cores sit idle while one large C++ source file finishes.

### Persistent object cache

Project objects remain incremental through compiler depfiles. Successful objects are also stored in the global `c` cache. The cache survives `c clean`, so a clean project rebuild can restore unchanged objects instead of recompiling them.

Cache entries validate the source, compiler/tool identity, compile flags, relevant environment, and the contents of included headers before reuse. Header content hashes and parsed depfiles are themselves persisted, reducing repeated filesystem and hashing work across separate `c` invocations.

Where the filesystem supports it, cached objects are restored using copy-on-write cloning instead of byte-for-byte copying:

- Linux: reflink / `FICLONE`
- macOS: `clonefile()`
- other/unsupported filesystems: normal atomic copy fallback

The global object cache is enabled by default. Disable it for one command with:

```sh
c build --no-object-cache
```

### Unity/chunk compilation

For environments where compiler startup and repeated header parsing are expensive, `c` supports optional unity compilation:

```sh
c build --unity
c build --unity=8
c build --unity=auto
```

`--unity` uses chunks of 8 compatible sources. `--unity=auto` uses source size plus learned compile-time history to choose smaller or larger chunks. C, C++, Objective-C, and Objective-C++ are always separated.

Unity remains opt-in because arbitrary projects can contain translation-unit-local declarations or macros that collide when source files are combined.

Unity can also be configured for a specific target in `build.c`:

```c
c_unity(app, 8);       // fixed chunk size
c_unity_auto(app);     // history-balanced chunks
c_no_unity(app);       // force normal translation units
```

A target-level setting overrides the command-line default for that target.

### Faster debug builds

When full debug information is unnecessary, use:

```sh
c build --fast-debug
```

This uses a lighter debug compilation profile (`-O1 -g1` on the current GCC/Clang-compatible path) instead of the normal `-O0 -g` debug profile.

### Linker selection

The normal system linker remains the default. An alternate compiler-driver linker can be requested explicitly:

```sh
c build --linker=mold
c build --linker=lld
```

Or let `c` use an available fast linker when supported:

```sh
c build --linker=auto
```

`C_LINKER` provides the environment equivalent.

### Build profiling

Use `--profile` to see where build time is going:

```sh
c build --profile
```

The report includes effective jobs, compiled objects, object-cache hits, link time, and the slowest translation units. The timing history is also used by future longest-job-first scheduling and automatic unity chunking.

### Watch mode

For edit/build loops:

```sh
c watch
c watch app
```

`c watch` keeps the build command active, fingerprints the project tree, and rebuilds when source/configuration files change. Global object/header/dependency caches remain available across rebuilds, so unchanged work is reused immediately.

### Performance environment variables

```text
C_JOBS=8
C_ADAPTIVE_JOBS=1
C_UNITY=auto
C_OBJECT_CACHE=0
C_PROFILE=1
C_FAST_DEBUG=1
C_LINKER=auto
```

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

Independent source dependencies can compile concurrently while respecting the overall job budget. Dependency compile flags remain isolated from application sources. No project-local clone and no dependency-specific build system are required.

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
c watch [target]
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
--adaptive-jobs / --no-adaptive-jobs
--unity / --unity=N / --unity=auto
--no-unity
--object-cache / --no-object-cache
--fast-debug
--profile
--linker=NAME / --linker=auto
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

The cache contains reusable compiled objects, persistent header hashes and parsed dep information, historical compile timings, Git mirrors, immutable source checkouts, compiled dependency archives, and compiled `build.c` modules. `c clean` removes project build output but keeps the global cache. Use `c cache clean` when you explicitly want to discard global cached data.

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
- half-CPU default job selection with explicit `-j` overrides
- optional load-aware adaptive job limiting
- historical longest-job-first scheduling
- concurrent independent source-dependency builds
- parallel test execution
- incremental object rebuilds
- persistent globally reusable object cache with header-content validation
- Linux reflink/macOS clonefile cache restoration when available
- persistent header-hash and depfile caches
- historical compile-time cache
- optional fixed or automatic unity/chunk compilation
- per-target unity controls
- build profiling
- fast-debug mode
- alternate linker selection
- watch mode
- automatic `compile_commands.json`
- system libraries and macOS frameworks
- globally cached Git dependencies
- header-only dependencies
- compiler-built source dependencies
- dependency-specific compiler flags
- lockfile pinning
- debug/release builds
- macOS/Linux

Planned next: native package metadata with exported public/private dependency information, shared libraries, cache garbage collection, cross compilation, and richer compiler-native package adapters.

## Philosophy

The project should remain boring to use:

```sh
c build
```

should be the normal case. Build complexity belongs in `build.c`, dependency storage belongs in the global cache, and compilation belongs to the compiler—not another build system.
