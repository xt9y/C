# Raylib example

A complete third-party dependency example using Raylib 5.5.

Raylib is declared directly in `build.c` with its Git repository and tag. `c` keeps the Raylib checkout and CMake build/install artifacts in the global cache instead of cloning the library into this project.

## Build and run

From this directory:

```sh
c build
c run
```

The first build fetches and builds Raylib. Later builds can reuse the cached dependency.

For automated/headless testing, the example also accepts:

```sh
c run -- --ci
```

That hides the window and exits after a few frames. A display server is still required by desktop Raylib.

## Linux system dependencies

`c` manages the Raylib source and build, but operating-system development libraries still come from your distribution. For the default X11 desktop backend on Debian/Ubuntu, the tested set is:

```sh
sudo apt install libasound2-dev libgl1-mesa-dev libglu1-mesa-dev \
  libx11-dev libxrandr-dev libxi-dev libxcursor-dev \
  libxinerama-dev libxext-dev
```

macOS builds against the system frameworks and needs no separately installed Raylib package.
