#!/bin/sh
set -eu

C_BIN="$1"
INC="$2"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT INT TERM HUP

export C_INCLUDE_DIR="$INC"
mkdir -p "$TMP/project/src"
cat >"$TMP/project/src/main.c" <<'SRC'
#include <stdio.h>
int main(void) { puts("ok"); return 0; }
SRC
cat >"$TMP/project/build.c" <<'SRC'
#include <cbuild.h>
void build(C_Build *b) {
    C_Target *app = c_executable(b, "app");
    c_sources(app, "src/main.c");
}
SRC

# A cache root that is a regular file is an intentionally broken filesystem
# configuration. The build must fail rather than silently writing elsewhere.
printf 'not-a-directory\n' >"$TMP/bad-cache"
(
    cd "$TMP/project"
    export C_CACHE_DIR="$TMP/bad-cache"
    if "$C_BIN" build >out.log 2>err.log; then
        echo "filesystem-failure: invalid cache root unexpectedly succeeded" >&2
        exit 1
    fi
    test ! -x build/debug/app
)

# The failure must not poison project state; switching to a valid cache should
# immediately allow a clean build.
(
    cd "$TMP/project"
    export C_CACHE_DIR="$TMP/good-cache"
    "$C_BIN" build >/dev/null
    test "$(./build/debug/app)" = ok
)

echo "filesystem-failure: ok"
