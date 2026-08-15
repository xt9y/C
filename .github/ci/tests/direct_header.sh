#!/bin/sh
set -eu

C_BIN="$1"
INC="$2"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT INT TERM

CACHE="$TMP/cache"
PROJECT="$TMP/project"
STALE="$TMP/stale-include"
mkdir -p "$CACHE/scripts" "$PROJECT/src" "$STALE"

cat > "$CACHE/scripts/cbuild.h" <<'EOF'
#error stale cached cbuild.h must never be used
EOF

cat > "$STALE/cbuild.h" <<'EOF'
#error stale C_INCLUDE_DIR cbuild.h must never override the canonical header
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
C_CACHE_DIR="$CACHE" C_INCLUDE_DIR="$STALE" "$C_BIN" build >/dev/null

# The legacy cache path must be removed, not copied or symlinked.
[ ! -e "$CACHE/scripts/cbuild.h" ]
[ ! -L "$CACHE/scripts/cbuild.h" ]

# Recreate a poisoned old cache entry and prove every build removes it.
cat > "$CACHE/scripts/cbuild.h" <<'EOF'
#error stale cached cbuild.h must never survive another build
EOF

C_CACHE_DIR="$CACHE" C_INCLUDE_DIR="$STALE" "$C_BIN" clean build >/dev/null
[ ! -e "$CACHE/scripts/cbuild.h" ]
[ ! -L "$CACHE/scripts/cbuild.h" ]

# Sanity-check the canonical header used by the test is the current API.
grep -q 'c_dep_flag' "$INC/cbuild.h"

echo "direct_header: ok"
