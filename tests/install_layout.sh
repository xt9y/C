#!/bin/sh
set -eu
ROOT="$1"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT INT TERM
make -C "$ROOT" clean >/dev/null
make -C "$ROOT" PREFIX=/usr/local >/dev/null
mkdir -p "$TMP/usr/local/include"
cat > "$TMP/usr/local/include/cbuild.h" <<'EOF'
#ifndef STALE_CBUILD_H
#define STALE_CBUILD_H
#error stale installed header must be replaced
#endif
THIS_TRAILING_DATA_MUST_NOT_SURVIVE_INSTALL
EOF
make -C "$ROOT" PREFIX=/usr/local DESTDIR="$TMP" install >/dev/null
cmp "$ROOT/include/cbuild.h" "$TMP/usr/local/include/cbuild.h"
mkdir "$TMP/project"
cd "$TMP/project"
"$TMP/usr/local/bin/c" init >/dev/null
"$TMP/usr/local/bin/c" run | grep -q 'Hello from C.'
echo "install-layout: ok"
