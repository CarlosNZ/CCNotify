#!/bin/bash
#
# CCNotify installer
# Run from the CCNotify repo root: ./install.sh
#
# Config model:
#   ccnotify.ini.example  — committed template (do not edit for personal use)
#   ccnotify.ini          — your personal config, gitignored, source of truth
#
# First run bootstraps ccnotify.ini from the example and exits so you can
# edit it. Subsequent runs copy the repo's ccnotify.ini into the install
# location, overwriting whatever is there.

set -e

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
DEST_DIR="$HOME/.claude/ccnotify"
REPO_INI="$REPO_DIR/ccnotify.ini"
DEST_INI="$DEST_DIR/ccnotify.ini"

echo "Installing CCNotify..."

# Create destination directory
mkdir -p "$DEST_DIR"

# Create symlink (absolute path, replacing any existing file)
ln -sf "$REPO_DIR/ccnotify.py" "$DEST_DIR/ccnotify.py"
chmod a+x "$DEST_DIR/ccnotify.py"
echo "Linked $DEST_DIR/ccnotify.py -> $REPO_DIR/ccnotify.py"

# Verify it works
if "$DEST_DIR/ccnotify.py" 2>/dev/null | grep -q "ok"; then
    echo "ccnotify.py is working."
else
    echo "Warning: ccnotify.py did not respond as expected."
fi

# Bootstrap personal config on first run.
# If an old install already has a config, migrate from it; otherwise use the example.
echo ""
if [ ! -f "$REPO_INI" ]; then
    if [ -f "$DEST_INI" ]; then
        cp "$DEST_INI" "$REPO_INI"
        echo "Created $REPO_INI from existing $DEST_INI."
    else
        cp "$REPO_DIR/ccnotify.ini.example" "$REPO_INI"
        echo "Created $REPO_INI from the example template."
    fi
    echo ""
    echo "Edit $REPO_INI to set your ntfy topic and focus apps,"
    echo "then run ./install.sh again to apply it."
    exit 0
fi

# Copy personal config into the install location (always overwrite)
cp "$REPO_INI" "$DEST_INI"
echo "Copied $REPO_INI -> $DEST_INI"

echo ""
echo "Done! Add the following hooks to ~/.claude/settings.json:"
echo ""
cat <<'HOOKS'
{
  "hooks": {
    "UserPromptSubmit": [
      { "hooks": [{ "type": "command", "command": "~/.claude/ccnotify/ccnotify.py UserPromptSubmit" }] }
    ],
    "Stop": [
      { "hooks": [{ "type": "command", "command": "~/.claude/ccnotify/ccnotify.py Stop" }] }
    ],
    "Notification": [
      { "hooks": [{ "type": "command", "command": "~/.claude/ccnotify/ccnotify.py Notification" }] }
    ],
    "PermissionRequest": [
      { "hooks": [{ "type": "command", "command": "~/.claude/ccnotify/ccnotify.py PermissionRequest" }] }
    ]
  }
}
HOOKS
