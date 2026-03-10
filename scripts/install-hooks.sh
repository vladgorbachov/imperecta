#!/bin/sh
# Install git hooks. Run from project root.
HOOK="prepare-commit-msg"
SRC="scripts/$HOOK"
DEST=".git/hooks/$HOOK"
if [ -f "$SRC" ]; then
  cp "$SRC" "$DEST" && chmod +x "$DEST" && echo "Installed $HOOK"
else
  echo "Hook not found: $SRC"
fi
