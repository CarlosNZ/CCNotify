#!/bin/bash
#
# CCNotify installer
# Run from the CCNotify repo root: ./install.sh

set -e

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
DEST_DIR="$HOME/.claude/ccnotify"

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

# Prompt for ntfy mobile notifications
echo ""
read -r -p "Enter an ntfy topic ID for mobile notifications (or press Enter to skip): " NTFY_TOPIC

if [ -n "$NTFY_TOPIC" ]; then
    sed "s/your-topic-id-goes-here/$NTFY_TOPIC/" "$REPO_DIR/ccnotify.ini.example.ini" > "$DEST_DIR/ccnotify.ini"
    echo "Created $DEST_DIR/ccnotify.ini with topic: $NTFY_TOPIC"
    echo "Install the ntfy app on your phone and subscribe to: $NTFY_TOPIC"
fi

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
