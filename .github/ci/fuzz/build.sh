#!/bin/sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
OUT=${FUZZ_BUILD_DIR:-"$ROOT/fuzz/.build"}
CC=${CC:-clang}
TARGET=${1:-all}

case "$TARGET" in
    all) TARGETS="lockfile depfile cache cli fs project" ;;
    lockfile|depfile|cache|cli|fs|project) TARGETS="$TARGET" ;;
    *) echo "usage: $0 [all|lockfile|depfile|cache|cli|fs|project]" >&2; exit 2 ;;
esac

if ! command -v "$CC" >/dev/null 2>&1; then
    echo "fuzz: compiler not found: $CC" >&2
    exit 1
fi

mkdir -p "$OUT"

# Keep a generated copy so fuzz harnesses can reach the production file's
# static helpers. #line preserves the original source path for diagnostics and
# LLVM coverage; coverage-report.sh also supplies an explicit path-equivalence
# fallback for LLVM versions that retain the generated path.
awk -v source="$ROOT/src/cli.c" '
    BEGIN { print "#line 1 \"" source "\"" }
    $0 == "int main(int argc, char **argv) {" {
        print "int c_fuzz_cli_main(int argc, char **argv) {"
        next
    }
    { print }
' "$ROOT/src/cli.c" > "$OUT/cli_fuzz.c"

if ! grep -q '^int c_fuzz_cli_main(int argc, char \*\*argv) {' "$OUT/cli_fuzz.c"; then
    echo "fuzz: could not isolate cli main()" >&2
    exit 1
fi

LDLIBS=
if [ "$(uname -s)" = "Linux" ]; then
    LDLIBS="-ldl"
fi

COVERAGE_FLAGS=
if [ "${FUZZ_COVERAGE:-0}" = "1" ]; then
    COVERAGE_FLAGS="-fprofile-instr-generate -fcoverage-mapping"
fi

HEADER_DEFINE="-DCBUILD_HEADER_PATH=\"$ROOT/include/cbuild.h\""
FUZZ_INCLUDE_DEFINE="-DC_FUZZ_INCLUDE_DIR=\"$ROOT/include\""

for name in $TARGETS; do
    "$CC" \
        -std=c11 -O1 -g \
        -fno-omit-frame-pointer \
        -fno-sanitize-recover=all \
        -fsanitize=fuzzer,address,leak,undefined \
        $COVERAGE_FLAGS \
        -D_XOPEN_SOURCE=700 \
        -D_POSIX_C_SOURCE=200809L \
        "$HEADER_DEFINE" \
        "$FUZZ_INCLUDE_DEFINE" \
        -I"$ROOT/include" \
        -I"$ROOT/src" \
        -I"$ROOT/fuzz" \
        -I"$OUT" \
        -include "$ROOT/src/cache_io.h" \
        "$ROOT/fuzz/fuzz_${name}.c" \
        $LDLIBS \
        -o "$OUT/fuzz_${name}"
done
