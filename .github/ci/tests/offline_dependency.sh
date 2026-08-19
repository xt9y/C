#!/bin/sh
set -eu

C_BIN="$1"
INC="$2"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT INT TERM HUP

export C_INCLUDE_DIR="$INC"
export C_CACHE_DIR="$TMP/cache"

mkdir -p "$TMP/dep/include" "$TMP/app/src"
cat >"$TMP/dep/include/value.h" <<'SRC'
#define OFFLINE_VALUE 42
SRC
(
    cd "$TMP/dep"
    git init -q
    git config user.name test
    git config user.email test@example.invalid
    git add include/value.h
    git commit -qm initial
)

cat >"$TMP/app/build.c" <<EOF
#include <cbuild.h>
void build(C_Build *b) {
    C_Target *app = c_executable(b, "app");
    c_sources(app, "src/main.c");
    C_Dependency *dep = c_git(b, "offline", "$TMP/dep", "master");
    c_dep_header_only(dep);
    c_dep_include(dep, "include");
    c_use(app, dep);
}
EOF
cat >"$TMP/app/src/main.c" <<'SRC'
#include <stdio.h>
#include <value.h>
int main(void) { printf("%d\n", OFFLINE_VALUE); return OFFLINE_VALUE == 42 ? 0 : 1; }
SRC

(
    cd "$TMP/app"
    "$C_BIN" build >/dev/null
    test "$(./build/debug/app)" = 42
    test -f c.lock
)

# Remove the dependency origin entirely. The lockfile + cached mirror/checkout
# must still be sufficient for an unchanged rebuild.
rm -rf "$TMP/dep"
rm -rf "$TMP/app/build"
(
    cd "$TMP/app"
    "$C_BIN" build >/dev/null
    test "$(./build/debug/app)" = 42
)

echo "offline-dependency: ok"
