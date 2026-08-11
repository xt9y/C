#!/bin/sh
set -eu
C_BIN="$1"
INC="$2"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT INT TERM
cd "$TMP"
export C_INCLUDE_DIR="$INC"
"$C_BIN" init >/dev/null
"$C_BIN" build >/dev/null
OUT="$("$C_BIN" run 2>/dev/null)"
printf '%s\n' "$OUT" | grep -q '^Hello from C\.$'
"$C_BIN" build 2>&1 | grep -q 'cached'
CHAIN_ERR="$TMP/chain.err"
CHAIN_OUT="$("$C_BIN" clean build run 2>"$CHAIN_ERR")"
printf '%s\n' "$CHAIN_OUT" | grep -q '^Hello from C\.$'
grep -q '^clean$' "$CHAIN_ERR"
grep -q '^build \[debug\]$' "$CHAIN_ERR"
grep -q '^run \[debug\]$' "$CHAIN_ERR"
"$C_BIN" clean >/dev/null 2>&1
[ ! -d build ]
echo "smoke: ok"
