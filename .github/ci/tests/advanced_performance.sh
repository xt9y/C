#!/bin/sh
set -eu

C_BIN="$1"
INC="$2"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT INT TERM
PROJECT="$TMP/project"
CACHE="$TMP/cache"
mkdir -p "$PROJECT/src" "$CACHE"

cat > "$PROJECT/build.c" <<'EOF'
#include <cbuild.h>
void build(C_Build *b) {
    C_Target *app = c_executable(b, "advanced-perf");
    c_sources(app, "src/*.c");
}
EOF

cat > "$PROJECT/src/shared.h" <<'EOF'
#ifndef SHARED_H
#define SHARED_H
#define BASE 7
int a(void);
int b(void);
#endif
EOF
cat > "$PROJECT/src/a.c" <<'EOF'
#include "shared.h"
int a(void) { return BASE; }
EOF
cat > "$PROJECT/src/b.c" <<'EOF'
#include "shared.h"
int b(void) { return BASE + 1; }
EOF
cat > "$PROJECT/src/main.c" <<'EOF'
#include "shared.h"
int main(void) { return a() + b() == 15 ? 0 : 1; }
EOF

run_c() {
    C_CACHE_DIR="$CACHE" C_INCLUDE_DIR="$INC" "$C_BIN" "$@"
}

cd "$PROJECT"
unset C_JOBS C_UNITY C_OBJECT_CACHE C_PROFILE C_FAST_DEBUG C_ADAPTIVE_JOBS C_LINKER || true

# Default job count must be max(1, online CPUs / 2), not all CPUs.
run_c doctor > "$TMP/doctor.txt"
cpus="$(awk '$1 == "CPUs" {print $2}' "$TMP/doctor.txt")"
jobs="$(awk '$1 == "Jobs" {print $2}' "$TMP/doctor.txt")"
expected=$((cpus / 2))
[ "$expected" -gt 0 ] || expected=1
[ "$jobs" -eq "$expected" ]
grep -q 'half CPUs default' "$TMP/doctor.txt"

# Populate normal objects and then exercise the persistent parsed dep/hash data.
run_c build -j2 >/dev/null
run_c build -j2 >/dev/null
find "$CACHE/perf/hash" -type f -name '*.hash' -print -quit | grep -q .
find "$CACHE/perf/deps" -type f -name '*.deps' -print -quit | grep -q .

# Profiling must expose cache/build counts and the slowest compilation units.
run_c clean >/dev/null
run_c build -j2 --profile --no-object-cache >/dev/null 2>"$TMP/profile.txt"
grep -q 'profile \[advanced-perf\]' "$TMP/profile.txt"
grep -q 'compiled' "$TMP/profile.txt"
grep -q 'link' "$TMP/profile.txt"

# Fast debug mode should actually change compiler flags.
run_c clean >/dev/null
run_c build -j1 --fast-debug --no-object-cache -v >/dev/null 2>"$TMP/fast-debug.txt"
grep -q -- '-O1' "$TMP/fast-debug.txt"
grep -q -- '-g1' "$TMP/fast-debug.txt"

# Auto linker selection is safe even if no alternate linker is installed.
run_c clean >/dev/null
run_c build -j2 --linker=auto >/dev/null
[ -x build/debug/advanced-perf ]

# Auto unity must generate hashed unity chunks and still produce a correct app.
run_c clean >/dev/null
run_c build -j2 --unity=auto --no-object-cache >/dev/null
find build/.unity -type f -name 'unity-*' -print -quit | grep -q .
./build/debug/advanced-perf

# The same optimization can be selected in build.c on a per-target basis.
cat > build.c <<'EOF'
#include <cbuild.h>
void build(C_Build *b) {
    C_Target *app = c_executable(b, "advanced-perf");
    c_sources(app, "src/*.c");
    c_unity(app, 2);
}
EOF
run_c clean >/dev/null
run_c build -j2 --no-object-cache >/dev/null
find build/.unity -type f -name 'unity-*' -print -quit | grep -q .
./build/debug/advanced-perf

# Per-target auto/off controls must also compile successfully.
cat > build.c <<'EOF'
#include <cbuild.h>
void build(C_Build *b) {
    C_Target *app = c_executable(b, "advanced-perf");
    c_sources(app, "src/*.c");
    c_unity_auto(app);
}
EOF
run_c clean >/dev/null
run_c build -j2 --no-object-cache >/dev/null
./build/debug/advanced-perf

cat > build.c <<'EOF'
#include <cbuild.h>
void build(C_Build *b) {
    C_Target *app = c_executable(b, "advanced-perf");
    c_sources(app, "src/*.c");
    c_no_unity(app);
}
EOF
run_c clean >/dev/null
run_c build -j2 --unity=2 --no-object-cache >/dev/null
[ ! -d build/.unity ]
./build/debug/advanced-perf

echo "advanced_performance: ok"
