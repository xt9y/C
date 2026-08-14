#!/bin/sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
TARGET=${1:?usage: fuzz/run-one.sh TARGET [SECONDS]}
SECONDS=${2:-30}
BUILD=${FUZZ_BUILD_DIR:-"$ROOT/fuzz/.build"}
BIN="$BUILD/fuzz_$TARGET"
CORPUS="$ROOT/fuzz/corpus/$TARGET"
ARTIFACT_ROOT=${FUZZ_ARTIFACT_DIR:-"$ROOT/fuzz/artifacts"}
ARTIFACT_DIR="$ARTIFACT_ROOT/$TARGET"
DICT=

case "$TARGET" in
    lockfile) DICT="$ROOT/fuzz/dictionaries/lockfile.dict" ;;
    depfile) DICT="$ROOT/fuzz/dictionaries/depfile.dict" ;;
    cache) ;;
    *) echo "unknown fuzz target: $TARGET" >&2; exit 2 ;;
esac

if [ ! -x "$BIN" ]; then
    echo "fuzz binary missing: $BIN (run fuzz/build.sh first)" >&2
    exit 1
fi

mkdir -p "$ARTIFACT_DIR"
WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT HUP INT TERM

export ASAN_OPTIONS="abort_on_error=1:detect_leaks=0:symbolize=1"
export UBSAN_OPTIONS="halt_on_error=1:print_stacktrace=1"

run_fuzzer() {
    if [ -n "$DICT" ]; then
        "$BIN" "$CORPUS" \
            -dict="$DICT" \
            -max_total_time="$SECONDS" \
            -timeout=5 \
            -rss_limit_mb=2048 \
            -print_final_stats=1 \
            -artifact_prefix="$ARTIFACT_DIR/"
    else
        "$BIN" "$CORPUS" \
            -max_total_time="$SECONDS" \
            -timeout=5 \
            -rss_limit_mb=2048 \
            -print_final_stats=1 \
            -artifact_prefix="$ARTIFACT_DIR/"
    fi
}

(
    cd "$WORK"
    run_fuzzer
)
