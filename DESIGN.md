# Design principles

C-BuildSystem is intentionally small, but the implementation is held to build-system correctness rules that are stricter than the happy-path API suggests.

## Product rules

- Build configuration stays C. Do not introduce another configuration language.
- Keep the common case small and readable.
- Prefer explicit errors over silent fallback or truncated configuration.
- Correctness and reproducibility come before benchmark wins.
- Test changes on real projects, including BGE.
- Benchmark claims must come from reproducible measurements.

## Correctness invariants

A successful `c build` must correspond to the current source tree, build description, dependency lock, compiler identity and effective build flags. A stale cached object is a correctness bug, not a performance bug.

- Header/source/flag/compiler changes must invalidate affected objects.
- Added or removed glob matches must affect the current build immediately.
- Cache entries are published atomically; malformed entries are not trusted.
- Concurrent builds may share the cache without observing partial entries.
- Target dependency cycles are rejected before producing a final target.
- Git dependencies recorded in `c.lock` resolve to immutable commits.
- Generated outputs are regenerated when their inputs or generator command change.
- Invalid `build.c` descriptions fail loudly.

## Compatibility

The public `cbuild.h` API targets source compatibility for build scripts. Before 1.0, the layout of its public C structs is not a frozen binary ABI. The intended 1.x source API will be frozen as part of the 1.0 release process.

## Scope

The supported native platforms are Linux and macOS. GCC-compatible and Clang-compatible compiler-driver workflows are the primary target. Other platforms should be described as unsupported until they are continuously tested rather than being implied to work.
