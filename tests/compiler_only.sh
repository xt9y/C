#!/bin/sh
set -eu
C_BIN="$1"
INC="$2"
ROOT="$(mktemp -d)"
trap 'rm -rf "$ROOT"' EXIT INT TERM
export C_INCLUDE_DIR="$INC"
export C_CACHE_DIR="$ROOT/cache"

mkdir -p "$ROOT/bin"
cat > "$ROOT/bin/cmake" <<'EOF'
#!/bin/sh
exit 99
EOF
chmod +x "$ROOT/bin/cmake"
export PATH="$ROOT/bin:$PATH"

mkdir -p "$ROOT/libfoo/include" "$ROOT/libfoo/src"
cd "$ROOT/libfoo"
git init -q
git config user.name test
git config user.email test@example.invalid
cat > include/foo.h <<'HDR'
#ifndef FOO_H
#define FOO_H
int foo(void);
#endif
HDR
cat > src/foo.c <<'SRC'
#include <foo.h>
#ifndef FOO_VALUE
#error FOO_VALUE must be provided by c_dep_flag()
#endif
int foo(void) { return FOO_VALUE; }
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

    C_Dependency *foo = c_git(b, "foo", "$ROOT/libfoo", "master");
    c_dep_source(foo);
    c_dep_include(foo, "include");
    c_dep_sources(foo, "src/*.c");
    c_dep_flag(foo, "-DFOO_VALUE=7");
    c_use(app, foo);
}
EOF2
cat > src/main.c <<'SRC'
#include <foo.h>
int main(void) { return foo() == 7 ? 0 : 1; }
SRC

"$C_BIN" run >/dev/null
[ -f c.lock ]
find "$C_CACHE_DIR/pkg" -name 'libfoo.a' -type f | grep -q .
"$C_BIN" build 2>&1 | grep -q 'cached'
echo "compiler-only: ok"
