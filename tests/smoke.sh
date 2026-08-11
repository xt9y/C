#!/bin/sh
set -eu
C_BIN="$1"
INC="$2"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT INT TERM
cd "$TMP"
export C_INCLUDE_DIR="$INC"
"$C_BIN" init
"$C_BIN" build
OUT="$("$C_BIN" run)"
printf '%s\n' "$OUT" | grep -q 'Hello from C.'
"$C_BIN" build | grep -q 'CACHED'
"$C_BIN" clean
[ ! -d build ]
echo "smoke: ok"
