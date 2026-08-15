#!/bin/sh
set -eu
C_BIN="$1"
INC="$2"
ROOT="$(mktemp -d)"
trap 'rm -rf "$ROOT"' EXIT INT TERM
export C_INCLUDE_DIR="$INC"
cd "$ROOT"
mkdir -p tests
cat > build.c <<'BUILD'
#include <cbuild.h>
void build(C_Build *b) {
    C_Target *test = c_test(b, "unit");
    c_sources(test, "tests/*.c");
}
BUILD
cat > tests/unit.c <<'SRC'
int main(void) { return 0; }
SRC
"$C_BIN" test 2>&1 | grep -q 'pass'
echo "test-command: ok"
