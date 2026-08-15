#!/bin/sh
set -eu
C_BIN="$1"
INC="$2"
ROOT="$(mktemp -d)"
trap 'rm -rf "$ROOT"' EXIT INT TERM
export C_INCLUDE_DIR="$INC"
export C_CACHE_DIR="$ROOT/cache"

mkdir -p "$ROOT/libtiny/include" "$ROOT/libtiny/src"
cd "$ROOT/libtiny"
git init -q
git config user.name test
git config user.email test@example.invalid
cat > include/tiny.h <<'HDR'
#ifndef TINY_H
#define TINY_H
int tiny_answer(void);
#endif
HDR
cat > src/tiny.c <<'SRC'
#include <tiny.h>
int tiny_answer(void) { return 99; }
SRC
git add .
git commit -qm initial

mkdir -p "$ROOT/app/src"
cd "$ROOT/app"
cat > build.c <<EOF2
#include <cbuild.h>
void build(C_Build *b) {
    C_Target *app = c_executable(b, "app");
    c_sources(app, "src/*.c");
    C_Dependency *tiny = c_git(b, "tiny", "$ROOT/libtiny", "master");
    c_dep_source(tiny);
    c_dep_include(tiny, "include");
    c_dep_sources(tiny, "src/*.c");
    c_use(app, tiny);
}
EOF2
cat > src/main.c <<'SRC'
#include <tiny.h>
int main(void) { return tiny_answer() == 99 ? 0 : 1; }
SRC
"$C_BIN" run >/dev/null
[ -f c.lock ]
[ ! -d deps ]
[ ! -d vendor ]
echo "source-dependency: ok"
