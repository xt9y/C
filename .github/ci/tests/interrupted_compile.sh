#!/bin/sh
set -eu

C_BIN="$1"
INC="$2"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT INT TERM HUP

export C_INCLUDE_DIR="$INC"
export C_CACHE_DIR="$TMP/cache"

mkdir -p "$TMP/project/src" "$TMP/bin"
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
cat >"$TMP/bin/cc-wrapper" <<'SH'
#!/bin/sh
set -eu
if [ "${C_INTERRUPT_ONCE:-0}" = 1 ] && [ ! -f "${C_INTERRUPT_MARKER}" ]; then
    : >"${C_INTERRUPT_MARKER}"
    out=""
    prev=""
    for arg in "$@"; do
        if [ "$prev" = -o ]; then out="$arg"; break; fi
        prev="$arg"
    done
    if [ -n "$out" ]; then
        mkdir -p "$(dirname "$out")"
        printf 'partial-object\n' >"$out"
    fi
    kill -TERM $$
fi
exec cc "$@"
SH
chmod +x "$TMP/bin/cc-wrapper"

(
    cd "$TMP/project"
    export CC="$TMP/bin/cc-wrapper"
    export C_INTERRUPT_MARKER="$TMP/interrupted"
    export C_INTERRUPT_ONCE=1
    if "$C_BIN" build >/dev/null 2>first.err; then
        echo "interrupted-compile: interrupted compiler unexpectedly succeeded" >&2
        exit 1
    fi
    test -f "$TMP/interrupted"

    # The interruption can happen while compiling the cached build.c module,
    # not only while compiling a target object. The next invocation must
    # recover from either partial artifact and produce a working executable.
    export C_INTERRUPT_ONCE=0
    "$C_BIN" build >/dev/null
    test "$(./build/debug/app)" = ok
)

echo "interrupted-compile: ok"
