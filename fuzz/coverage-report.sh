#!/bin/sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
BUILD=${FUZZ_BUILD_DIR:-"$ROOT/fuzz/.build"}
PROFILE_DIR=${FUZZ_PROFILE_DIR:-"$ROOT/fuzz/profiles"}
OUT=${FUZZ_COVERAGE_DIR:-"$ROOT/fuzz/coverage"}

for tool in llvm-profdata llvm-cov; do
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

OBJECT_ARGS="-object=$BUILD/fuzz_depfile -object=$BUILD/fuzz_cache -object=$BUILD/fuzz_fs -object=$BUILD/fuzz_project"
SOURCES="$ROOT/src/cli.c $ROOT/src/main.c $ROOT/src/perf_v2.h $ROOT/src/cache_io.h"

# shellcheck disable=SC2086
llvm-cov report "$BUILD/fuzz_lockfile" \
    $OBJECT_ARGS \
    -instr-profile="$PROFDATA" \
    -ignore-filename-regex='(^|/)fuzz/' \
    -sources $SOURCES \
    > "$OUT/coverage.txt"

# shellcheck disable=SC2086
llvm-cov export "$BUILD/fuzz_lockfile" \
    $OBJECT_ARGS \
    -instr-profile="$PROFDATA" \
    -ignore-filename-regex='(^|/)fuzz/' \
    -sources $SOURCES \
    > "$OUT/coverage.json"

# shellcheck disable=SC2086
llvm-cov show "$BUILD/fuzz_lockfile" \
    $OBJECT_ARGS \
    -instr-profile="$PROFDATA" \
    -ignore-filename-regex='(^|/)fuzz/' \
    -format=html \
    -output-dir="$OUT/html" \
    -sources $SOURCES \
    >/dev/null

cat "$OUT/coverage.txt"
