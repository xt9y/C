#!/bin/sh
set -eu

C_BIN="$1"
INC="$2"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT INT TERM HUP

# No build configuration must fail clearly.
mkdir "$TMP/empty"
(
    cd "$TMP/empty"
    if "$C_BIN" build >out.txt 2>err.txt; then
        echo "wrapper-backends: empty project unexpectedly built" >&2
        exit 1
    fi
    grep -q 'no build.c, CMakeLists.txt' err.txt
)

# A native build.c always wins over compatibility files.
mkdir "$TMP/native"
cat > "$TMP/native/main.c" <<'SRC'
#include <stdio.h>
int main(void) { puts("native-ok"); return 0; }
SRC
cat > "$TMP/native/build.c" <<'SRC'
#include <cbuild.h>
void build(C_Build *b) {
    C_Target *app = c_executable(b, "app");
    c_sources(app, "main.c");
}
SRC
cat > "$TMP/native/Makefile" <<'MK'
all:
	@echo make-must-not-run > wrong-backend
MK
cat > "$TMP/native/CMakeLists.txt" <<'CMAKE'
cmake_minimum_required(VERSION 3.16)
project(wrong_backend C)
CMAKE
(
    cd "$TMP/native"
    C_INCLUDE_DIR="$INC" "$C_BIN" build >/dev/null
    test -x build/debug/app
    test ! -e wrong-backend
)

# Make fallback preserves default/explicit targets, jobs, forwarded args, test/clean and conversion.
mkdir "$TMP/make"
cat > "$TMP/make/Makefile" <<'MK'
VALUE ?= default
all:
	@printf 'all:%s\n' '$(VALUE)' > result.txt
foo:
	@printf 'foo:%s\n' '$(VALUE)' > result.txt
test:
	@printf 'test\n' > test.txt
clean:
	@rm -f result.txt test.txt
MK
(
    cd "$TMP/make"
    "$C_BIN" build -j2 -- VALUE=abc >/dev/null
    grep -q '^all:abc$' result.txt
    "$C_BIN" build foo --jobs=2 -- VALUE=xyz >/dev/null
    grep -q '^foo:xyz$' result.txt
    if "$C_BIN" build --release >/dev/null 2>release.err; then
        echo "wrapper-backends: Make --release unexpectedly succeeded" >&2
        exit 1
    fi
    grep -q 'no portable Makefile meaning' release.err
    "$C_BIN" test >/dev/null
    test -f test.txt
    "$C_BIN" clean >/dev/null
    test ! -e result.txt
    "$C_BIN" convert >/dev/null
    grep -q 'c-buildsystem:backend=make' build.c
    grep -q 'c-buildsystem:source=Makefile' build.c
    "$C_BIN" build foo -- VALUE=bridge >/dev/null
    grep -q '^foo:bridge$' result.txt
    "$C_BIN" convert Makefile >/dev/null 2>exists.err && {
        echo "wrapper-backends: convert unexpectedly overwrote build.c" >&2
        exit 1
    }
    grep -q 'build.c already exists' exists.err
    "$C_BIN" convert --force Makefile >/dev/null
    grep -q 'c-buildsystem:backend=make' build.c
)

# CMake wins over Make when no native build.c exists. It configures out-of-source,
# builds named/debug/release targets, supports an existing build-dir override, runs CTest,
# cleans, and survives conversion without allowing the Makefile to run.
mkdir "$TMP/cmake"
cat > "$TMP/cmake/CMakeLists.txt" <<'CMAKE'
cmake_minimum_required(VERSION 3.16)
project(c_wrapper_test C)
enable_testing()
add_executable(app main.c)
add_test(NAME app_runs COMMAND app)
CMAKE
cat > "$TMP/cmake/Makefile" <<'MK'
all:
	@echo make-must-not-run > wrong-backend
MK
cat > "$TMP/cmake/main.c" <<'SRC'
#include <stdio.h>
int main(void) { puts("cmake-ok"); return 0; }
SRC
(
    cd "$TMP/cmake"
    "$C_BIN" build app -j2 >/dev/null
    test -x .c-build/cmake/debug/app
    test ! -e wrong-backend
    "$C_BIN" test app_runs -j2 >/dev/null
    "$C_BIN" build app --release -j2 >/dev/null
    test -x .c-build/cmake/release/app
    C_CMAKE_BUILD_DIR=build "$C_BIN" build app -j2 >/dev/null
    test -x build/app
    C_CMAKE_BUILD_DIR=build "$C_BIN" clean >/dev/null
    "$C_BIN" convert CMakeLists.txt >/dev/null
    grep -q 'c-buildsystem:backend=cmake' build.c
    grep -q 'c-buildsystem:source=CMakeLists.txt' build.c
    "$C_BIN" build app -j2 >/dev/null
    test ! -e wrong-backend
)

echo "wrapper-backends: ok"
