#!/bin/sh
set -eu

C_BIN="$1"
INC="$2"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT INT TERM

CACHE="$TMP/cache"
PROJECT="$TMP/project"
mkdir -p "$CACHE/scripts" "$PROJECT/src"

cat > "$CACHE/scripts/cbuild.h" <<'EOF'
#error stale cached cbuild.h must never be used
EOF

cat > "$PROJECT/build.c" <<'EOF'
#include <cbuild.h>

void build(C_Build *b) {
    C_Target *app = c_executable(b, "direct-header");
    c_sources(app, "src/main.c");
}
EOF

cat > "$PROJECT/src/main.c" <<'EOF'
int main(void) { return 0; }
EOF

cd "$PROJECT"
C_CACHE_DIR="$CACHE" C_INCLUDE_DIR="$INC" "$C_BIN" build >/dev/null

[ -L "$CACHE/scripts/cbuild.h" ]
cmp "$INC/cbuild.h" "$CACHE/scripts/cbuild.h"

C_CACHE_DIR="$CACHE" C_INCLUDE_DIR="$INC" "$C_BIN" clean build >/dev/null
[ -L "$CACHE/scripts/cbuild.h" ]
cmp "$INC/cbuild.h" "$CACHE/scripts/cbuild.h"

echo "direct_header: ok"
