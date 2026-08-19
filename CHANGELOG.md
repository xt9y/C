# Changelog

All notable user-visible changes to C-BuildSystem are recorded here.

The project is pre-1.0. `build.c` source compatibility is the compatibility goal; the layout of public structs is not a frozen binary ABI.

## Unreleased

### Added

- Shared-library targets with platform-appropriate `.so` / `.dylib` output.
- Target-to-target library dependencies with recursive build ordering and cycle detection.
- Generated-source tracking with input and generator-command invalidation.
- Per-target C standard selection and strict-warning helpers.
- `--explain` / `C_EXPLAIN` rebuild explanations.
- ASan + UBSan correctness CI.
- Incremental correctness, concurrent cache, API guard, target-graph and generated-source regressions.

### Changed

- Public API misuse, duplicate names, fixed-field overflow and allocation failures now fail loudly instead of silently dropping build configuration.
- Build-description capacity was raised while preserving explicit failure at hard limits.
- Object-cache keys include compiler identity.
- Object-cache publication uses atomic replacement after flushing durable output.
- Corrupt cache entries are discarded rather than treated as valid.
- Expensive real-project benchmarks run on scheduled/manual CI rather than every normal push.
- `cbuild.h` now explicitly promises source compatibility rather than a frozen struct ABI.

### Existing major capabilities

- Incremental and parallel C/C++ compilation.
- Persistent global object cache.
- Git dependencies with lockfiles.
- CMake and Make compatibility backends.
- `compile_commands.json` generation.
- Watch mode, profiling, adaptive jobs and unity builds.
- Linux and macOS support.
- Fuzzing and real-project benchmark coverage for cJSON, libcurl fan-out, SDL3 and Wireshark.

## Release policy

The first `1.0.0` release will be cut only after the 1.0 checklist in `ROADMAP.md` is complete. Until then, incompatible pre-1.0 changes must be documented here with migration guidance.
