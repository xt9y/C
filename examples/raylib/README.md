# Raylib example

A complete third-party dependency example using Raylib 5.5.

Raylib is declared directly in `build.c` with its Git repository, source files, include paths, and compiler flags. `c` keeps the checkout and compiled static archive in the global cache. CMake and Make are not used to build Raylib.

## Build and run

From this directory:

```sh
c build
c run
```

The first build fetches Raylib and compiles its C sources with the selected compiler. Later builds can reuse the cached dependency archive.

For automated/headless testing, the example also accepts:

```sh
c run -- --ci
```

That hides the window and exits after a few frames. A display server is still required by desktop Raylib.

## Linux system dependencies

`c` manages and compiles the Raylib source, but operating-system development libraries still come from your distribution. For the default X11 desktop backend on Debian/Ubuntu, the tested set is:

```sh
sudo apt install libasound2-dev libgl1-mesa-dev libglu1-mesa-dev \
  libx11-dev libxrandr-dev libxi-dev libxcursor-dev \
  libxinerama-dev libxext-dev
```

These are platform libraries, not build systems. macOS uses the system frameworks declared in `build.c` and needs no separately installed Raylib package.
