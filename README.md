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

## Notes

- This is a young project.
- I am still changing things.
- Issues and weird edge cases are useful.

## License

MIT
