#!/bin/sh
set -eu

C_BIN="$1"
INC="$2"
ROOT="$(mktemp -d)"
trap 'rm -rf "$ROOT"' EXIT INT TERM
CACHE="$ROOT/cache"
TRACK="$ROOT/track"
mkdir -p "$CACHE" "$TRACK"

make_dep() {
    name="$1"
    value="$2"
    mkdir -p "$ROOT/$name/include" "$ROOT/$name/src"
    cat > "$ROOT/$name/include/$name.h" <<EOF
#ifndef ${name}_H
#define ${name}_H
int ${name}_value(void);
#endif
EOF
    cat > "$ROOT/$name/src/$name.c" <<EOF
#include <$name.h>
int ${name}_value(void) { return $value; }
EOF
    (
        cd "$ROOT/$name"
        git init -q
        git config user.name test
        git config user.email test@example.invalid
        git add .
        git commit -qm initial
    )
}

make_dep depa 20
make_dep depb 22

REAL_CC="$(command -v "${CC:-cc}")"
cat > "$ROOT/cc-wrap" <<'EOF'
#!/bin/sh
set -eu
TRACK_DIR="${C_PARALLEL_TRACK:?}"
REAL_CC="${C_REAL_CC:?}"
is_compile=0
for arg in "$@"; do
    [ "$arg" = "-c" ] && is_compile=1
done
if [ "$is_compile" -eq 1 ]; then
    lock="$TRACK_DIR/lock"
    while ! mkdir "$lock" 2>/dev/null; do sleep 0.01; done
    active=0
    [ -f "$TRACK_DIR/active" ] && active="$(cat "$TRACK_DIR/active")"
    active=$((active + 1))
    printf '%s\n' "$active" > "$TRACK_DIR/active"
    max=0
    [ -f "$TRACK_DIR/max" ] && max="$(cat "$TRACK_DIR/max")"
    [ "$active" -le "$max" ] || printf '%s\n' "$active" > "$TRACK_DIR/max"
    rmdir "$lock"

    sleep 1

    while ! mkdir "$lock" 2>/dev/null; do sleep 0.01; done
    active="$(cat "$TRACK_DIR/active")"
    active=$((active - 1))
    printf '%s\n' "$active" > "$TRACK_DIR/active"
    rmdir "$lock"
fi
exec "$REAL_CC" "$@"
EOF
chmod +x "$ROOT/cc-wrap"

mkdir -p "$ROOT/app/src"
cat > "$ROOT/app/build.c" <<EOF
#include <cbuild.h>
void build(C_Build *b) {
    C_Target *app = c_executable(b, "parallel-deps");
    c_sources(app, "src/main.c");

    C_Dependency *a = c_git(b, "depa", "$ROOT/depa", "master");
    c_dep_source(a);
    c_dep_include(a, "include");
    c_dep_sources(a, "src/*.c");
    c_use(app, a);

    C_Dependency *d = c_git(b, "depb", "$ROOT/depb", "master");
    c_dep_source(d);
    c_dep_include(d, "include");
    c_dep_sources(d, "src/*.c");
    c_use(app, d);
}
EOF
cat > "$ROOT/app/src/main.c" <<'EOF'
#include <depa.h>
#include <depb.h>
int main(void) { return depa_value() + depb_value() == 42 ? 0 : 1; }
EOF

cd "$ROOT/app"
C_CACHE_DIR="$CACHE" \
C_INCLUDE_DIR="$INC" \
C_PARALLEL_TRACK="$TRACK" \
C_REAL_CC="$REAL_CC" \
"$C_BIN" build --cc "$ROOT/cc-wrap" -j4 --no-object-cache >/dev/null

[ -x build/debug/parallel-deps ]
./build/debug/parallel-deps
max="$(cat "$TRACK/max")"
[ "$max" -ge 2 ]

echo "parallel_deps: ok (max concurrent compilers: $max)"
