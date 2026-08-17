#!/bin/sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
BUILD=${FUZZ_BUILD_DIR:-"$ROOT/fuzz/.build"}
PROFILE_DIR=${FUZZ_PROFILE_DIR:-"$ROOT/fuzz/profiles"}
OUT=${FUZZ_COVERAGE_DIR:-"$ROOT/fuzz/coverage"}

for tool in llvm-profdata llvm-cov python3; do
    if ! command -v "$tool" >/dev/null 2>&1; then
        echo "fuzz coverage: missing $tool" >&2
        exit 1
    fi
done

set -- "$PROFILE_DIR"/*.profraw
if [ ! -e "$1" ]; then
    echo "fuzz coverage: no .profraw files in $PROFILE_DIR" >&2
    exit 1
fi

mkdir -p "$OUT"
PROFDATA="$OUT/coverage.profdata"
llvm-profdata merge -sparse "$PROFILE_DIR"/*.profraw -o "$PROFDATA"

# Do not ignore the entire fuzz/ directory: cli_fuzz.c is a line-mapped copy of
# production src/cli.c. Exclude only actual harness/support sources and public
# include files, then map the generated CLI source back to src/cli.c.
IGNORE='(^|/)(fuzz_(lockfile|depfile|cache|cli|fs|project)\.c|fuzz_support\.h|include/.*)$'
PATH_EQUIV="$BUILD/cli_fuzz.c,$ROOT/src/cli.c"
OBJECTS="-object=$BUILD/fuzz_depfile -object=$BUILD/fuzz_cache -object=$BUILD/fuzz_cli -object=$BUILD/fuzz_fs -object=$BUILD/fuzz_project"

# shellcheck disable=SC2086
llvm-cov report "$BUILD/fuzz_lockfile" \
    $OBJECTS \
    -instr-profile="$PROFDATA" \
    -ignore-filename-regex="$IGNORE" \
    -path-equivalence="$PATH_EQUIV" \
    > "$OUT/coverage.txt"

# shellcheck disable=SC2086
llvm-cov export "$BUILD/fuzz_lockfile" \
    $OBJECTS \
    -instr-profile="$PROFDATA" \
    -ignore-filename-regex="$IGNORE" \
    -path-equivalence="$PATH_EQUIV" \
    > "$OUT/coverage.json"

# shellcheck disable=SC2086
llvm-cov show "$BUILD/fuzz_lockfile" \
    $OBJECTS \
    -instr-profile="$PROFDATA" \
    -ignore-filename-regex="$IGNORE" \
    -path-equivalence="$PATH_EQUIV" \
    -format=html \
    -output-dir="$OUT/html" \
    >/dev/null

python3 "$ROOT/fuzz/coverage-gate.py" "$OUT/coverage.json" "$OUT/coverage.md"

cat "$OUT/coverage.txt"
