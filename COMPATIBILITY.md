# Compatibility

C-BuildSystem is pre-1.0. The support contract below is intentionally narrower than “whatever happens to compile”.

## Supported native hosts

| Host | Architecture | Compiler-driver model | CI status |
| --- | --- | --- | --- |
| Linux | x86-64 | GCC-compatible `cc` / GCC | continuously tested |
| Linux | x86-64 | Clang | sanitizer and fuzz coverage |
| macOS | Apple-hosted GitHub runner | Apple Clang-compatible `cc` | continuously tested |

Linux ARM64 and macOS ARM64 are expected to work where the same POSIX/compiler-driver assumptions hold, but they are not part of the strict support contract until they are continuously exercised by CI.

Windows/MSVC is not currently supported. The project should not claim Windows compatibility until process spawning, shared-library naming/linking, filesystem/cache semantics, dynamic loading of `build.c`, and CI are implemented and tested there.

## Build-script compatibility

`include/cbuild.h` targets source compatibility for `build.c` files. Before 1.0, the layout of public C structs is not a frozen binary ABI. The 1.0 release process will freeze the intended 1.x source API and document any migration requirements.

## Required host tools

The native build path requires a C compiler driver and an archiver. Git is required only when Git dependencies are declared. CMake/Make are compatibility backends for projects that use those build systems; native `build.c` projects do not require them unless a dependency explicitly needs them.

Use `c doctor` to inspect the current machine and selected compiler/linker/cache settings.
