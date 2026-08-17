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
TIMEOUT=5
MAX_LEN=65536

case "$TARGET" in
    lockfile) DICT="$ROOT/fuzz/dictionaries/lockfile.dict" ;;
    depfile) DICT="$ROOT/fuzz/dictionaries/depfile.dict" ;;
    cache) ;;
    cli) DICT="$ROOT/fuzz/dictionaries/cli.dict"; MAX_LEN=512 ;;
    fs) TIMEOUT=10; MAX_LEN=512 ;;
    project) TIMEOUT=15; MAX_LEN=512 ;;
    *) echo "unknown fuzz target: $TARGET" >&2; exit 2 ;;
esac

if [ ! -x "$BIN" ]; then
    echo "fuzz binary missing: $BIN (run fuzz/build.sh first)" >&2
    exit 1
fi

if [ ! -d "$CORPUS" ]; then
    echo "fuzz corpus missing: $CORPUS" >&2
    exit 1
fi

mkdir -p "$ARTIFACT_DIR"
WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT HUP INT TERM

export ASAN_OPTIONS="abort_on_error=1:detect_leaks=1:symbolize=1"
export LSAN_OPTIONS="exitcode=23:report_objects=1"
export UBSAN_OPTIONS="halt_on_error=1:print_stacktrace=1"

if [ -n "${FUZZ_PROFILE_DIR:-}" ]; then
    mkdir -p "$FUZZ_PROFILE_DIR"
    export LLVM_PROFILE_FILE="$FUZZ_PROFILE_DIR/${TARGET}-%p.profraw"
fi

run_fuzzer() {
    set -- \
        "$CORPUS" \
        -max_total_time="$SECONDS" \
        -timeout="$TIMEOUT" \
        -max_len="$MAX_LEN" \
        -rss_limit_mb=2048 \
        -detect_leaks=1 \
        -print_final_stats=1 \
        -artifact_prefix="$ARTIFACT_DIR/"
    if [ -n "$DICT" ]; then
        set -- "$@" -dict="$DICT"
    fi
    "$BIN" "$@"
}

(
    cd "$WORK"
    run_fuzzer
)
