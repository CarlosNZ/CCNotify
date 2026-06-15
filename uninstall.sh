#!/bin/bash
#
# CCNotify uninstaller
# Run from the CCNotify repo root: ./uninstall.sh
#
# Reverses what install.sh did:
#   - removes the ccnotify hooks from ~/.claude/settings.json (backed up first)
#   - removes the install dir ~/.claude/ccnotify/ (symlinked script, the copied
#     ccnotify.ini, and the runtime ccnotify.db / ccnotify.log files)
#
# Leaves alone:
#   - this repo (your source ccnotify.py and personal ccnotify.ini stay put)
#   - terminal-notifier and the ntfy app (installed by you, removed by you)
#
# Flags:
#   -y, --yes   skip the confirmation prompt

set -e

DEST_DIR="$HOME/.claude/ccnotify"
SETTINGS="$HOME/.claude/settings.json"

ASSUME_YES=0
for arg in "$@"; do
    case "$arg" in
        -y|--yes) ASSUME_YES=1 ;;
        *) echo "Unknown option: $arg" >&2; exit 1 ;;
    esac
done

echo "Uninstalling CCNotify..."
echo ""
echo "This will remove:"
echo "  - $DEST_DIR (script symlink, config copy, database, logs)"
echo "  - ccnotify hooks in $SETTINGS"
echo ""
echo "Your repo (source ccnotify.py and ccnotify.ini) is left untouched."
echo ""

if [ "$ASSUME_YES" -ne 1 ]; then
    printf "Proceed? [y/N] "
    read -r reply
    case "$reply" in
        [yY]|[yY][eE][sS]) ;;
        *) echo "Aborted."; exit 0 ;;
    esac
    echo ""
fi

# 1. Strip ccnotify hooks from settings.json (backed up before any change).
if [ -f "$SETTINGS" ]; then
    python3 - "$SETTINGS" <<'PY'
import json, os, shutil, sys

path = sys.argv[1]
try:
    with open(path) as f:
        data = json.load(f)
except (json.JSONDecodeError, OSError) as e:
    print(f"Could not parse {path} ({e}); leave the hooks to remove by hand.")
    sys.exit(0)

hooks = data.get("hooks")
if not isinstance(hooks, dict):
    print("No hooks block in settings.json; nothing to remove there.")
    sys.exit(0)

def mentions_ccnotify(entry):
    # entry looks like {"hooks": [{"type": "command", "command": "...ccnotify..."}]}
    for h in entry.get("hooks", []):
        if "ccnotify" in str(h.get("command", "")):
            return True
    return False

removed = 0
for event in list(hooks.keys()):
    entries = hooks[event]
    if not isinstance(entries, list):
        continue
    kept = [e for e in entries if not (isinstance(e, dict) and mentions_ccnotify(e))]
    removed += len(entries) - len(kept)
    if kept:
        hooks[event] = kept
    else:
        del hooks[event]  # drop the event entirely if it's now empty

if removed == 0:
    print("No ccnotify hooks found in settings.json.")
    sys.exit(0)

if not hooks:
    del data["hooks"]  # drop the empty hooks object

shutil.copy2(path, path + ".bak")
with open(path, "w") as f:
    json.dump(data, f, indent=2)
    f.write("\n")
print(f"Removed {removed} ccnotify hook(s) from settings.json (backup: {os.path.basename(path)}.bak).")
PY
else
    echo "No $SETTINGS found; skipping hook removal."
fi

# 2. Remove the install directory and everything install/runtime put in it.
echo ""
if [ -e "$DEST_DIR" ]; then
    rm -rf "$DEST_DIR"
    echo "Removed $DEST_DIR"
else
    echo "$DEST_DIR not present; nothing to remove."
fi

echo ""
echo "Done! CCNotify has been uninstalled."
echo ""
echo "Note: restart your Claude Code session so it re-reads settings.json."
echo "terminal-notifier and the ntfy app (if installed) were left in place."
