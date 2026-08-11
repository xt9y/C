#!/bin/sh
set -eu
ROOT="$1"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT INT TERM
make -C "$ROOT" clean >/dev/null
make -C "$ROOT" PREFIX=/usr/local >/dev/null
make -C "$ROOT" PREFIX=/usr/local DESTDIR="$TMP" install >/dev/null
mkdir "$TMP/project"
cd "$TMP/project"
"$TMP/usr/local/bin/c" init >/dev/null
"$TMP/usr/local/bin/c" run | grep -q 'Hello from C.'
echo "install-layout: ok"
