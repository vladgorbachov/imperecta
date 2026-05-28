#!/bin/sh
# Install global git hooks (~/.config/git/hooks) for all repositories on this machine.
set -e
GLOBAL_DIR="${HOME}/.config/git/hooks"
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
mkdir -p "$GLOBAL_DIR"
cat > "$GLOBAL_DIR/strip-cursor-trailers.sh" << 'EOF'
#!/bin/sh
MSG_FILE="${1:?commit message file required}"
[ -f "$MSG_FILE" ] || exit 0
sed -i -E '/^[[:space:]]*Made-with:[[:space:]]*Cursor[[:space:]]*$/Id' "$MSG_FILE"
sed -i -E '/^[[:space:]]*Co-authored-by:[[:space:]]*Cursor[[:space:]]*<cursoragent@cursor\.com>[[:space:]]*$/Id' "$MSG_FILE"
sed -i -E '/cursoragent@cursor\.com/Id' "$MSG_FILE"
EOF
chmod +x "$GLOBAL_DIR/strip-cursor-trailers.sh"
for hook in prepare-commit-msg commit-msg; do
  cat > "$GLOBAL_DIR/$hook" << EOF
#!/bin/sh
exec "\$HOME/.config/git/hooks/strip-cursor-trailers.sh" "\$1"
EOF
  chmod +x "$GLOBAL_DIR/$hook"
  echo "Installed $GLOBAL_DIR/$hook"
done
git config --global core.hooksPath "$GLOBAL_DIR"
echo "Set global core.hooksPath=$GLOBAL_DIR"
