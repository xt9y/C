# Fuzzing

The fuzz suite exercises production parsing/cache code with Clang libFuzzer plus ASan and UBSan.

Targets:

- `lockfile` — malformed, truncated and oversized `c.lock` input; also checks parse/save/parse round trips.
- `depfile` — compiler `.d` dependency files, including escaping, line continuations and long paths.
- `cache` — persistent hash metadata, dependency-cache metadata and compile-history cache records, including partially written files.

The fuzz build generates a copy of `src/cli.c` with only its public `main()` renamed, then includes that source directly in each harness. The harnesses therefore call the same static parser/cache functions used by the real `c` executable rather than copies of their logic.

Run locally with Clang:

```sh
CC=clang ./fuzz/build.sh
./fuzz/run-one.sh lockfile 30
./fuzz/run-one.sh depfile 30
./fuzz/run-one.sh cache 30
```

CI:

- **Fuzz smoke** runs on pushes and pull requests with a short fixed budget.
- **Fuzz nightly** runs each target for 10 minutes on a schedule and can also be started manually.
- Sanitizer/fuzzer crashes fail the workflow and the reproducer is uploaded as a workflow artifact.
