#!/bin/sh
set -eu

C_BIN="$1"
INC="$2"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT INT TERM HUP

mkdir -p "$TMP/project/src"
cat >"$TMP/project/src/lib.c" <<'SRC'
int value(void) { return 1; }
SRC
cat >"$TMP/project/src/main.c" <<'SRC'
int value(void);
int main(void) { return value() == 1 ? 0 : 1; }
SRC
cat >"$TMP/project/build.c" <<'SRC'
#include <cbuild.h>
void build(C_Build *b) {
    C_Target *lib = c_static_library(b, "lib");
    c_sources(lib, "src/lib.c");
    C_Target *app = c_executable(b, "app");
    c_sources(app, "src/main.c");
    c_link_target(app, lib);
}
SRC
(
    cd "$TMP/project"
    C_INCLUDE_DIR="$INC" "$C_BIN" deps tree >tree.log
    grep -q '^Targets:' tree.log
    grep -q 'target lib' tree.log

    C_INCLUDE_DIR="$INC" "$C_BIN" build >/dev/null
    C_INCLUDE_DIR="$INC" "$C_BIN" cache stats >stats.log
    grep -q '^Path' stats.log
    grep -q '^Files' stats.log
    grep -q '^Bytes' stats.log

    C_INCLUDE_DIR="$INC" "$C_BIN" deps clean >/dev/null
)

echo "cli-inspection: ok"
