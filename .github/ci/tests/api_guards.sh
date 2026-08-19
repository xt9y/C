#!/bin/sh
set -eu

INC="$1"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT INT TERM HUP

compile_and_expect_failure() {
    name="$1"
    needle="$2"
    cc -std=c11 -Wall -Wextra -Werror -I"$INC" "$TMP/$name.c" -o "$TMP/$name"
    if "$TMP/$name" >"$TMP/$name.out" 2>"$TMP/$name.err"; then
        echo "api-guards: $name unexpectedly succeeded" >&2
        exit 1
    fi
    grep -q "$needle" "$TMP/$name.err"
}

cat >"$TMP/duplicate_target.c" <<'SRC'
#include <cbuild.h>
int main(void) {
    C_Build b = {0};
    b.default_target = -1;
    (void)c_executable(&b, "app");
    (void)c_test(&b, "app");
    return 0;
}
SRC
compile_and_expect_failure duplicate_target "duplicate target 'app'"

cat >"$TMP/duplicate_dep.c" <<'SRC'
#include <cbuild.h>
int main(void) {
    C_Build b = {0};
    b.default_target = -1;
    (void)c_git(&b, "dep", "https://example.invalid/a.git", "main");
    (void)c_git(&b, "dep", "https://example.invalid/b.git", "main");
    return 0;
}
SRC
compile_and_expect_failure duplicate_dep "duplicate dependency 'dep'"

cat >"$TMP/duplicate_use.c" <<'SRC'
#include <cbuild.h>
int main(void) {
    C_Build b = {0};
    b.default_target = -1;
    C_Target *app = c_executable(&b, "app");
    C_Dependency *dep = c_git(&b, "dep", "https://example.invalid/a.git", "main");
    c_use(app, dep);
    c_use(app, dep);
    return 0;
}
SRC
compile_and_expect_failure duplicate_use "added to target 'app' more than once"

cat >"$TMP/empty_name.c" <<'SRC'
#include <cbuild.h>
int main(void) {
    C_Build b = {0};
    b.default_target = -1;
    (void)c_executable(&b, "");
    return 0;
}
SRC
compile_and_expect_failure empty_name "target name is empty"

cat >"$TMP/long_path.c" <<'SRC'
#include <cbuild.h>
int main(void) {
    C_Build b = {0};
    b.default_target = -1;
    C_Target *app = c_executable(&b, "app");
    char path[C_MAX_PATH + 32];
    memset(path, 'x', sizeof(path) - 1);
    path[sizeof(path) - 1] = '\0';
    C_Dependency *dep = c_git(&b, "dep", path, "main");
    c_use(app, dep);
    return 0;
}
SRC
compile_and_expect_failure long_path "fixed API field limit"

echo "api-guards: ok"
