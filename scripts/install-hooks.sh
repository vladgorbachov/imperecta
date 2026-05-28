#!/bin/sh
# Install git hooks for this repository (run from repo root).
set -e
cd "$(git rev-parse --show-toplevel)"
HOOK_DIR="scripts/git-hooks"
chmod +x "$HOOK_DIR/strip-cursor-trailers.sh" \
  "$HOOK_DIR/prepare-commit-msg" \
  "$HOOK_DIR/commit-msg" \
  "$HOOK_DIR/msg-filter-strip-cursor.sh"
for hook in prepare-commit-msg commit-msg; do
  cp "$HOOK_DIR/$hook" ".git/hooks/$hook"
  chmod +x ".git/hooks/$hook"
  echo "Installed .git/hooks/$hook"
done
# Legacy copy for tools that only read scripts/prepare-commit-msg
cp "$HOOK_DIR/strip-cursor-trailers.sh" scripts/strip-cursor-trailers.sh 2>/dev/null || true
cp "$HOOK_DIR/prepare-commit-msg" scripts/prepare-commit-msg
chmod +x scripts/prepare-commit-msg scripts/strip-cursor-trailers.sh 2>/dev/null || true
echo "Done. Cursor trailers will be stripped on commit."
