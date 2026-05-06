#!/bin/bash
#
# Open the CCNotify install directory (~/.claude/ccnotify) in Finder
#

set -e

DEST_DIR="$HOME/.claude/ccnotify"

if [ ! -d "$DEST_DIR" ]; then
    echo "CCNotify not installed at $DEST_DIR — run ./install.sh first."
    exit 1
fi

open "$DEST_DIR"
