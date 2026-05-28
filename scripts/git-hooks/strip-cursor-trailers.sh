#!/bin/sh
# Strip Cursor commit attribution from a message file (Linux sed).
# Usage: strip-cursor-trailers.sh <commit-msg-file>
MSG_FILE="${1:?commit message file required}"
[ -f "$MSG_FILE" ] || exit 0
sed -i -E '/^[[:space:]]*Made-with:[[:space:]]*Cursor[[:space:]]*$/Id' "$MSG_FILE"
sed -i -E '/^[[:space:]]*Co-authored-by:[[:space:]]*Cursor[[:space:]]*<cursoragent@cursor\.com>[[:space:]]*$/Id' "$MSG_FILE"
sed -i -E '/cursoragent@cursor\.com/Id' "$MSG_FILE"
