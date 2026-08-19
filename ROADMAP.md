# Roadmap

C-BuildSystem is moving from prototype work toward a stable, correctness-first release. Performance remains important, but a build system must never trade correctness or reproducibility for speed.

## 0.8 — Correctness and hardening

- [x] Fail loudly on invalid or oversized `build.c` API input.
- [x] Detect duplicate targets and dependencies.
- [x] Track compiler identity in object-cache keys.
- [x] Make object-cache writes atomic and recover from corrupt entries.
- [x] Test concurrent builds sharing the same global cache.
- [x] Add deterministic incremental-rebuild regression coverage.
- [x] Add ASan + UBSan CI and fuzz smoke coverage.
- [x] Move expensive benchmarks off normal pushes and PRs.
- [ ] Continue expanding interruption, filesystem-failure and malformed-lockfile tests.

## 0.9 — Complete build graph

- [x] Static libraries.
- [x] Shared libraries.
- [x] Target-to-target linking with cycle detection.
- [x] Generated sources with tracked inputs and command invalidation.
- [x] Per-target C standard selection.
- [x] Strict warning helpers.
- [x] Git dependencies with lockfile-pinned commits.
- [x] CMake and Make compatibility backends.
- [ ] Dependency-tree inspection and stronger transitive/version-conflict diagnostics.
- [ ] First-class install rules.
- [ ] `pkg-config` integration and explicit system-include handling.
- [ ] Response-file support for very large compiler/linker command lines.

## 0.95 — Stabilization

- [x] Linux and macOS CI.
- [x] GCC/Clang-compatible C11 implementation.
- [x] Real-project benchmark suite: cJSON, libcurl fan-out, SDL3 and Wireshark.
- [x] `c doctor`, `c clean`, cache controls, watch mode and build explanations.
- [x] Source-compatibility policy for `cbuild.h` documented before 1.0.
- [ ] Broaden distro/architecture coverage where hosted runners make it practical.
- [ ] Keep validating on BGE and additional real projects.
- [ ] Add more dependency edge-case and offline-rebuild coverage.
- [ ] Standardize benchmark statistics and scenarios across every benchmark.

## 1.0 — First stable release

Before 1.0:

- Freeze the intended `build.c` source API for the 1.x line.
- Document supported platforms and compilers precisely.
- Publish a changelog and migration notes.
- Tag and publish the first stable release only after the correctness suite is clean.

There are intentionally no calendar dates here. Milestones ship when their correctness and compatibility requirements are satisfied.
