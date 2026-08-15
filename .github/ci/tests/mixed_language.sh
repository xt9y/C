#!/bin/sh
set -eu
C_BIN="$1"
INC="$2"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT INT TERM
cd "$TMP"
export C_INCLUDE_DIR="$INC"

mkdir -p src
cat > build.c <<'EOF'
#include <cbuild.h>
void build(C_Build *b) {
    C_Target *app = c_executable(b, "mixed");
    c_sources(app, "src/main.c");
    c_sources(app, "src/value.cpp");
    c_flag(app, "-std=c++20");
#ifdef __APPLE__
    c_link_system(app, "c++");
#else
    c_link_system(app, "stdc++");
#endif
}
EOF
cat > src/main.c <<'EOF'
int cpp_value(void);
int main(void) { return cpp_value() == 42 ? 0 : 1; }
EOF
cat > src/value.cpp <<'EOF'
extern "C" int cpp_value(void) { return 42; }
EOF

"$C_BIN" run >/dev/null

grep -q -- '-std=c11' compile_commands.json
grep -q -- '-std=c++20' compile_commands.json

echo "mixed-language: ok"
