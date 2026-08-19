#!/bin/sh
set -eu

C_BIN="$1"
INC="$2"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT INT TERM HUP

mkdir -p "$TMP/project/src"
cat >"$TMP/project/src/base.c" <<'SRC'
int base_value(void) { return 40; }
SRC
cat >"$TMP/project/src/mid.c" <<'SRC'
int base_value(void);
int mid_value(void) { return base_value() + 1; }
SRC
cat >"$TMP/project/src/shared.c" <<'SRC'
int shared_value(void) { return 1; }
SRC
cat >"$TMP/project/src/main.c" <<'SRC'
#include <stdio.h>
int mid_value(void);
int shared_value(void);
int main(void) { printf("%d\n", mid_value() + shared_value()); return 0; }
SRC
cat >"$TMP/project/build.c" <<'SRC'
#include <cbuild.h>
void build(C_Build *b) {
    C_Target *base = c_static_library(b, "base");
    c_sources(base, "src/base.c");
    c_standard(base, C_STANDARD_C11);
    c_warnings_strict(base);

    C_Target *mid = c_static_library(b, "mid");
    c_sources(mid, "src/mid.c");
    c_link_target(mid, base);

    C_Target *shared = c_shared_library(b, "shared");
    c_sources(shared, "src/shared.c");

    C_Target *app = c_executable(b, "app");
    c_sources(app, "src/main.c");
    c_link_target(app, mid);
    c_link_target(app, shared);
    c_default_target(b, app);
}
SRC
(
    cd "$TMP/project"
    C_INCLUDE_DIR="$INC" "$C_BIN" build --explain >build.log 2>&1
    test -f build/debug/base.a
    test -f build/debug/mid.a
    if [ "$(uname -s)" = Darwin ]; then
        test -f build/debug/libshared.dylib
    else
        test -f build/debug/libshared.so
    fi
    test "$(./build/debug/app)" = 42
    C_INCLUDE_DIR="$INC" "$C_BIN" build --explain >second.log 2>&1
    grep -qi 'fresh\|cached\|restored' second.log
)

mkdir -p "$TMP/cycle"
cat >"$TMP/cycle/a.c" <<'SRC'
int a(void) { return 1; }
SRC
cat >"$TMP/cycle/b.c" <<'SRC'
int b(void) { return 2; }
SRC
cat >"$TMP/cycle/build.c" <<'SRC'
#include <cbuild.h>
void build(C_Build *b) {
    C_Target *a = c_static_library(b, "a");
    C_Target *bb = c_static_library(b, "b");
    c_sources(a, "a.c");
    c_sources(bb, "b.c");
    c_link_target(a, bb);
    c_link_target(bb, a);
    c_default_target(b, a);
}
SRC
(
    cd "$TMP/cycle"
    if C_INCLUDE_DIR="$INC" "$C_BIN" build >out.log 2>err.log; then
        echo "target-graph: dependency cycle unexpectedly succeeded" >&2
        exit 1
    fi
    grep -q 'cyclic target dependency' err.log
)

echo "target-graph: ok"
