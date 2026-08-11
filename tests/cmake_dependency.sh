#!/bin/sh
set -eu
C_BIN="$1"
INC="$2"
ROOT="$(mktemp -d)"
trap 'rm -rf "$ROOT"' EXIT INT TERM
export C_INCLUDE_DIR="$INC"
export C_CACHE_DIR="$ROOT/cache"

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
int foo(void) { return 7; }
SRC
cat > CMakeLists.txt <<'CMAKE'
cmake_minimum_required(VERSION 3.16)
project(foo C)
add_library(foo STATIC src/foo.c)
target_include_directories(foo PUBLIC $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include> $<INSTALL_INTERFACE:include>)
install(TARGETS foo ARCHIVE DESTINATION lib)
install(DIRECTORY include/ DESTINATION include)
CMAKE
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
    c_dep_cmake(foo);
    c_dep_link(foo, "foo");
    c_use(app, foo);
}
EOF2
cat > src/main.c <<'SRC'
#include <foo.h>
int main(void) { return foo() == 7 ? 0 : 1; }
SRC
"$C_BIN" run >/dev/null
[ -f c.lock ]
echo "cmake-dependency: ok"
