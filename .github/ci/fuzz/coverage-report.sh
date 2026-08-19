#!/bin/sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
BUILD=${FUZZ_BUILD_DIR:-"$ROOT/fuzz/.build"}
PROFILE_DIR=${FUZZ_PROFILE_DIR:-"$ROOT/fuzz/profiles"}
OUT=${FUZZ_COVERAGE_DIR:-"$ROOT/fuzz/coverage"}

find_llvm_tool() {
    base="$1"
    explicit="$2"
    if [ -n "$explicit" ] && command -v "$explicit" >/dev/null 2>&1; then
        command -v "$explicit"
        return 0
    fi
    if command -v "$base" >/dev/null 2>&1; then
        command -v "$base"
        return 0
    fi
    for version in 21 20 19 18 17 16 15 14; do
        if command -v "$base-$version" >/dev/null 2>&1; then
            command -v "$base-$version"
            return 0
        fi
    done
    return 1
}

LLVM_PROFDATA_BIN=$(find_llvm_tool llvm-profdata "${LLVM_PROFDATA:-}") || {
    echo "fuzz coverage: missing llvm-profdata (including versioned variants)" >&2
    exit 1
}
LLVM_COV_BIN=$(find_llvm_tool llvm-cov "${LLVM_COV:-}") || {
    echo "fuzz coverage: missing llvm-cov (including versioned variants)" >&2
    exit 1
}
if ! command -v python3 >/dev/null 2>&1; then
    echo "fuzz coverage: missing python3" >&2
    exit 1
fi

set -- "$PROFILE_DIR"/*.profraw
if [ ! -e "$1" ]; then
    echo "fuzz coverage: no .profraw files in $PROFILE_DIR" >&2
    exit 1
fi

mkdir -p "$OUT"
PROFDATA="$OUT/coverage.profdata"
"$LLVM_PROFDATA_BIN" merge -sparse "$PROFILE_DIR"/*.profraw -o "$PROFDATA"

# Do not ignore the entire fuzz/ directory: cli_fuzz.c is a line-mapped copy of
# production src/cli.c. Exclude only actual harness/support sources and public
# include files, then map the generated CLI source back to src/cli.c.
IGNORE='(^|/)(fuzz_(lockfile|depfile|cache|cli|fs|project)\.c|fuzz_support\.h|include/.*)$'
PATH_EQUIV="$BUILD/cli_fuzz.c,$ROOT/src/cli.c"
OBJECTS="-object=$BUILD/fuzz_depfile -object=$BUILD/fuzz_cache -object=$BUILD/fuzz_cli -object=$BUILD/fuzz_fs -object=$BUILD/fuzz_project"

# shellcheck disable=SC2086
"$LLVM_COV_BIN" report "$BUILD/fuzz_lockfile" \
    $OBJECTS \
    -instr-profile="$PROFDATA" \
    -ignore-filename-regex="$IGNORE" \
    -path-equivalence="$PATH_EQUIV" \
    > "$OUT/coverage.txt"

# shellcheck disable=SC2086
"$LLVM_COV_BIN" export "$BUILD/fuzz_lockfile" \
    $OBJECTS \
    -instr-profile="$PROFDATA" \
    -ignore-filename-regex="$IGNORE" \
    -path-equivalence="$PATH_EQUIV" \
    > "$OUT/coverage.json"

# shellcheck disable=SC2086
"$LLVM_COV_BIN" show "$BUILD/fuzz_lockfile" \
    $OBJECTS \
    -instr-profile="$PROFDATA" \
    -ignore-filename-regex="$IGNORE" \
    -path-equivalence="$PATH_EQUIV" \
    -format=html \
    -output-dir="$OUT/html" \
    >/dev/null

python3 "$ROOT/fuzz/coverage-gate.py" "$OUT/coverage.json" "$OUT/coverage.md"

cat "$OUT/coverage.txt"
