#!/bin/sh
set -eu

C_BIN="$1"
INC="$2"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT INT TERM HUP

export C_INCLUDE_DIR="$INC"
export C_CACHE_DIR="$TMP/cache"

mkdir -p "$TMP/dep" "$TMP/app"
cat >"$TMP/dep/value.h" <<'SRC'
#define VALUE 1
SRC
(
    cd "$TMP/dep"
    git init -q
    git config user.name test
    git config user.email test@example.invalid
    git add value.h
    git commit -qm initial
)
cat >"$TMP/app/main.c" <<'SRC'
#include <value.h>
int main(void) { return VALUE == 1 ? 0 : 1; }
SRC
cat >"$TMP/app/build.c" <<EOF
#include <cbuild.h>
void build(C_Build *b) {
    C_Target *app = c_executable(b, "app");
    c_sources(app, "main.c");
    C_Dependency *dep = c_git(b, "dep", "$TMP/dep", "master");
    c_dep_header_only(dep);
    c_use(app, dep);
}
EOF

# A matching lock entry with an impossible commit must never be silently
# treated as a valid reproducible dependency state.
cat >"$TMP/app/c.lock" <<EOF
# deliberately malformed/unusable lock state
[[dependency]]
name = "dep"
url = "$TMP/dep"
requested = "master"
resolved = "definitely-not-a-commit"
EOF
(
    cd "$TMP/app"
    if "$C_BIN" build >out.log 2>err.log; then
        echo "malformed-lockfile: invalid resolved commit unexpectedly succeeded" >&2
        exit 1
    fi
    grep -Eq 'checkout|resolve|commit|dependency|error' err.log out.log
)

echo "malformed-lockfile: ok"
