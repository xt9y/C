# Fuzzing

The fuzz suite runs production build-system code under Clang libFuzzer with ASan, UBSan and LeakSanitizer.

Targets:

- `lockfile` — malformed, truncated and oversized `c.lock` input, plus parse/save/parse round trips.
- `depfile` — compiler `.d` dependency files, including escaping, line continuations and long paths.
- `cache` — persistent hash metadata, dependency-cache metadata and compile-history records, including partial writes.
- `cli` — structure-aware command-line/performance option combinations, environment defaults, forwarding after `--`, linker/cache/unity/job toggles and C/C++ source classification.
- `project` — the real `build.c` compile/load/execute path, local Git dependency resolution, dependency graphs, object caching, unity modes, true no-op rebuilds, one-source invalidation and common-header fan-out.
- `fs` — atomic cache writes, planted temporary-file symlinks, concurrent cache writers and an active symlink race against cache writes. A guard file outside the cache must never be modified.

The fuzz build generates a copy of `src/cli.c` with only its public `main()` renamed, then includes that source directly in each harness. The harnesses therefore call the same static functions used by the real `c` executable rather than copies of their logic. Coverage maps that generated copy back to `src/cli.c`, so CLI implementation coverage is visible separately from `main.c`.

The `project` target uses a local Git repository only. It does not fuzz arbitrary shell commands or contact the network.

## Run locally

```sh
CC=clang ./fuzz/build.sh
./fuzz/run-one.sh lockfile 30
./fuzz/run-one.sh depfile 30
./fuzz/run-one.sh cache 30
./fuzz/run-one.sh cli 30
./fuzz/run-one.sh fs 30
./fuzz/run-one.sh project 30
```

Leak checking is enabled both at compile time (`-fsanitize=leak`) and at runtime (`ASAN_OPTIONS=detect_leaks=1`, `LSAN_OPTIONS=exitcode=23`).

## Coverage

Build with LLVM coverage instrumentation, run the corpus, then render and gate the report:

```sh
CC=clang FUZZ_COVERAGE=1 ./fuzz/build.sh
rm -rf fuzz/profiles fuzz/coverage
mkdir -p fuzz/profiles
FUZZ_PROFILE_DIR="$PWD/fuzz/profiles" ./fuzz/run-one.sh lockfile 10
FUZZ_PROFILE_DIR="$PWD/fuzz/profiles" ./fuzz/run-one.sh depfile 10
FUZZ_PROFILE_DIR="$PWD/fuzz/profiles" ./fuzz/run-one.sh cache 10
FUZZ_PROFILE_DIR="$PWD/fuzz/profiles" ./fuzz/run-one.sh cli 10
FUZZ_PROFILE_DIR="$PWD/fuzz/profiles" ./fuzz/run-one.sh fs 10
FUZZ_PROFILE_DIR="$PWD/fuzz/profiles" ./fuzz/run-one.sh project 10
FUZZ_PROFILE_DIR="$PWD/fuzz/profiles" ./fuzz/coverage-report.sh
```

`fuzz/coverage/coverage.txt` is LLVM's raw text summary, `coverage.json` is machine-readable, `coverage.md` contains the human/AI-readable production table and regression gates, and `fuzz/coverage/html/` is the browsable source report.

Coverage gates are deliberately regression floors rather than aspirational targets. Existing core coverage must stay above the measured baseline margin, `main.c` has explicit line/branch/function floors, and `cli.c` must remain present and above its own initial floor. As coverage improves, these floors should move upward.

## CI

- **Fuzz smoke** runs all targets on pushes and pull requests.
- Its Actions summary publishes production coverage for `cache_io.h`, `main.c`, `perf_v2.h` and `cli.c` plus gate status.
- Coverage regressions fail the fuzz job instead of only changing a report.
- The final workflow Summary also includes the fuzz coverage table before benchmark results.
- Coverage text, JSON, Markdown and HTML are uploaded as workflow artifacts.
- **Fuzz nightly** runs every fuzz target for 10 minutes on the schedule.
- Sanitizer/fuzzer crashes fail the workflow and the reproducer is uploaded as a workflow artifact.

Fuzzing, sanitizers and coverage improve confidence. They are not a substitute for independent review; this repository is still single-maintainer.
