#!/bin/sh
set -eu

C_BIN="$1"
INC="$2"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT INT TERM

PROJECT="$TMP/project"
CACHE="$TMP/cache"
TRACK="$TMP/track"
WRAP="$TMP/cc-wrap"
REAL_CC="${CC:-cc}"

case "$REAL_CC" in
    */*) ;;
    *) REAL_CC="$(command -v "$REAL_CC")" ;;
esac

mkdir -p "$PROJECT/src" "$PROJECT/include" "$CACHE" "$TRACK"
printf '0\n' > "$TRACK/active"
printf '0\n' > "$TRACK/count"
printf '0\n' > "$TRACK/max"

cat > "$WRAP" <<'WRAPPER'
#!/bin/sh

compile=0
for arg in "$@"; do
    [ "$arg" = "-c" ] && compile=1
done

lock() {
    while ! mkdir "$TRACK_DIR/.lock" 2>/dev/null; do :; done
}

unlock() {
    rmdir "$TRACK_DIR/.lock"
}

if [ "$compile" -eq 1 ]; then
    lock
    active="$(cat "$TRACK_DIR/active")"
    count="$(cat "$TRACK_DIR/count")"
    max="$(cat "$TRACK_DIR/max")"
    active=$((active + 1))
    count=$((count + 1))
    [ "$active" -gt "$max" ] && max="$active"
    printf '%s\n' "$active" > "$TRACK_DIR/active"
    printf '%s\n' "$count" > "$TRACK_DIR/count"
    printf '%s\n' "$max" > "$TRACK_DIR/max"
    unlock
    delay="${WRAP_DELAY:-0}"
    [ "$delay" = "0" ] || sleep "$delay"
fi

"$REAL_CC" "$@"
rc=$?

if [ "$compile" -eq 1 ]; then
    lock
    active="$(cat "$TRACK_DIR/active")"
    active=$((active - 1))
    printf '%s\n' "$active" > "$TRACK_DIR/active"
    unlock
fi

exit "$rc"
WRAPPER
chmod +x "$WRAP"

cat > "$PROJECT/build.c" <<'BUILD'
#include <cbuild.h>

void build(C_Build *b) {
    C_Target *app = c_executable(b, "perf");
    c_sources(app, "src/*.c");
    c_include(app, "include");
}
BUILD

cat > "$PROJECT/include/shared.h" <<'HEADER'
#ifndef SHARED_H
#define SHARED_H
#define VALUE 1
int a(void);
int b(void);
int c(void);
#endif
HEADER

cat > "$PROJECT/src/a.c" <<'SOURCE'
#include "shared.h"
int a(void) { return VALUE; }
SOURCE
cat > "$PROJECT/src/b.c" <<'SOURCE'
#include "shared.h"
int b(void) { return VALUE + 1; }
SOURCE
cat > "$PROJECT/src/c.c" <<'SOURCE'
#include "shared.h"
int c(void) { return VALUE + 2; }
SOURCE
cat > "$PROJECT/src/main.c" <<'SOURCE'
#include <stdio.h>
#include "shared.h"
int main(void) {
    printf("%d\n", a() + b() + c());
    return 0;
}
SOURCE

run_c() {
    TRACK_DIR="$TRACK" REAL_CC="$REAL_CC" C_CACHE_DIR="$CACHE" C_INCLUDE_DIR="$INC" "$C_BIN" "$@"
}

cd "$PROJECT"

# Clean build: four compiler jobs, with at least two overlapping when -j2 is used.
WRAP_DELAY=1 TRACK_DIR="$TRACK" REAL_CC="$REAL_CC" C_CACHE_DIR="$CACHE" C_INCLUDE_DIR="$INC" \
    "$C_BIN" build --cc "$WRAP" -j2 >/dev/null
[ "$(cat "$TRACK/count")" -eq 4 ]
[ "$(cat "$TRACK/max")" -ge 2 ]
[ "$(./build/debug/perf)" = "6" ]

# Project clean must not erase the global object cache. A clean rebuild should
# restore all four objects without invoking the compiler wrapper again.
run_c clean >/dev/null
printf '0\n' > "$TRACK/active"
printf '0\n' > "$TRACK/max"
WRAP_DELAY=0 run_c build --cc "$WRAP" -j2 >/dev/null
[ "$(cat "$TRACK/count")" -eq 4 ]
[ "$(./build/debug/perf)" = "6" ]

# Header contents are part of cache validity. Changing a shared header must
# invalidate all dependent cached objects.
cat > include/shared.h <<'HEADER'
#ifndef SHARED_H
#define SHARED_H
#define VALUE 2
int a(void);
int b(void);
int c(void);
#endif
HEADER
run_c clean >/dev/null
WRAP_DELAY=0 run_c build --cc "$WRAP" -j2 >/dev/null
[ "$(cat "$TRACK/count")" -eq 8 ]
[ "$(./build/debug/perf)" = "9" ]

# Unity mode is opt-in. Four compatible C files with chunk size 2 should use
# two compiler invocations instead of four.
run_c clean >/dev/null
printf '0\n' > "$TRACK/active"
printf '0\n' > "$TRACK/count"
printf '0\n' > "$TRACK/max"
WRAP_DELAY=0 run_c build --cc "$WRAP" --unity=2 -j2 --no-object-cache >/dev/null
[ "$(cat "$TRACK/count")" -eq 2 ]
[ "$(./build/debug/perf)" = "9" ]

# Environment controls should be accepted as defaults too.
run_c clean >/dev/null
C_JOBS=1 C_UNITY=2 C_OBJECT_CACHE=0 TRACK_DIR="$TRACK" REAL_CC="$REAL_CC" \
    C_CACHE_DIR="$CACHE" C_INCLUDE_DIR="$INC" "$C_BIN" build --cc "$WRAP" >/dev/null
[ "$(./build/debug/perf)" = "9" ]

echo "performance: ok"
