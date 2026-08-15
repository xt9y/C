#!/bin/sh
set -eu
C_BIN="$1"
INC="$2"
ROOT="$(mktemp -d)"
trap 'rm -rf "$ROOT"' EXIT INT TERM
export C_INCLUDE_DIR="$INC"
cd "$ROOT"
mkdir src
cat > build.c <<'BUILD'
#include <cbuild.h>
void build(C_Build *b) {
    C_Target *app = c_executable(b, "profile");
    c_sources(app, "src/*.c");
}
BUILD
cat > src/main.c <<'SRC'
int main(void) { return 0; }
SRC
"$C_BIN" build >/dev/null 2>&1
"$C_BIN" build --release >/dev/null 2>&1
[ -x build/debug/profile ]
[ -x build/release/profile ]
"$C_BIN" build 2>&1 | grep -q 'cached'
echo "profiles: ok"
