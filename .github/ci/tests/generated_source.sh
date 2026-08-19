#!/bin/sh
set -eu

C_BIN="$1"
INC="$2"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT INT TERM HUP

mkdir -p "$TMP/project"
cat >"$TMP/project/value.txt" <<'EOF'
7
EOF
cat >"$TMP/project/main.c" <<'SRC'
#include <stdio.h>
int generated_value(void);
int main(void) { printf("%d\n", generated_value()); return 0; }
SRC
cat >"$TMP/project/build.c" <<'SRC'
#include <cbuild.h>
void build(C_Build *b) {
    C_Target *app = c_executable(b, "app");
    c_sources(app, "main.c");
    c_generate(app, "generated/value.c", "value.txt",
        "mkdir -p generated; v=$(cat value.txt); printf 'int generated_value(void) { return %s; }\\n' \"$v\" > generated/value.c");
}
SRC
(
    cd "$TMP/project"
    C_INCLUDE_DIR="$INC" "$C_BIN" build >/dev/null
    test "$(./build/debug/app)" = 7

    printf '11\n' > value.txt
    C_INCLUDE_DIR="$INC" "$C_BIN" build >/dev/null
    test "$(./build/debug/app)" = 11

    # Same input, different generator command: command hash must invalidate.
    python3 - <<'PY'
p = 'build.c'
s = open(p).read()
s = s.replace('return %s;', 'return (%s) + 1;')
open(p, 'w').write(s)
PY
    C_INCLUDE_DIR="$INC" "$C_BIN" build >/dev/null
    test "$(./build/debug/app)" = 12

    # No input change and no command change should keep generated output stable.
    before=$(stat -c %Y generated/value.c 2>/dev/null || stat -f %m generated/value.c)
    sleep 1
    C_INCLUDE_DIR="$INC" "$C_BIN" build --explain >explain.log 2>&1
    after=$(stat -c %Y generated/value.c 2>/dev/null || stat -f %m generated/value.c)
    test "$before" = "$after"
    grep -q 'generator is fresh' explain.log
)

echo "generated-source: ok"
