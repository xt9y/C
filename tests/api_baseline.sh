#!/bin/sh
set -eu
INC="$1"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT INT TERM

cat > "$TMP/baseline.c" <<'EOF'
#include <cbuild.h>

void build(C_Build *b) {
    C_Target *app = c_executable(b, "app");
    C_Target *lib = c_static_library(b, "lib");
    C_Target *test = c_test(b, "test");

    c_default_target(b, app);
    c_sources(app, "src/*.c");
    c_include(app, "include");
    c_define(app, "FEATURE=1");
    c_flag(app, "-Wall");
    c_link_flag(app, "-Wl,--as-needed");
    c_link_system(app, "m");
    c_framework(app, "Foundation");

    c_sources(lib, "lib/*.c");
    c_sources(test, "tests/*.c");

    C_Dependency *headers = c_git(b, "headers", "https://example.invalid/headers.git", "v1");
    c_dep_header_only(headers);
    c_dep_include(headers, "include");
    c_dep_subdir(headers, "pkg");
    c_use(app, headers);

    C_Dependency *source = c_git(b, "source", "https://example.invalid/source.git", "v1");
    c_dep_source(source);
    c_dep_include(source, "include");
    c_dep_sources(source, "src/*.c");
    c_dep_flag(source, "-DSOURCE_FEATURE=1");
    c_use(app, source);
}
EOF

${CC:-cc} -std=c11 -Wall -Wextra -Werror -I"$INC" -fsyntax-only "$TMP/baseline.c"
${CXX:-c++} -std=c++17 -Wall -Wextra -Werror -I"$INC" -x c++ -fsyntax-only "$TMP/baseline.c"

echo "api-baseline: ok"
