![Notification Screenshot](alert.jpg)

Fork of [https://github.com/dazuiba/CCNotify](https://github.com/dazuiba/CCNotify), with the following changes:
  - works with "Prompt" notifications (requests to edit, or run commands)
  - optional notifications to mobile device (via [ntfy](https://ntfy.sh/))
  - suppresses notifications when Claude's host app is already in the foreground
  - installer script to simplify setup

Should work with Claude Code command line or [VSCode extension](https://marketplace.visualstudio.com/items?itemName=anthropic.claude-code)

# CCNotify

**CCNotify** provides desktop notifications for **Claude Code**, alerting you when Claude needs your input or completes tasks.

## Installation

1. Install [`terminal-notifier`](https://github.com/julienXX/terminal-notifier):  
  `brew install terminal-notifier` (or see [here](https://github.com/dazuiba/CCNotify?tab=readme-ov-file#2-install-terminal-notifier) for alternative installation methods)
2. From within this repo root, run `./install.sh` **twice**:

   - **First run** — creates a symlink of `ccnotify.py` in `~/.claude/ccnotify/` (the symlink means future `git pull`s are picked up automatically — no reinstall needed) and bootstraps `ccnotify.ini` in this repo from `ccnotify.ini.example`. Then exits and asks you to edit it.
   - **Edit `ccnotify.ini`** in the repo root to set your ntfy topic, focus apps, etc. This file is gitignored — it's your personal config and the source of truth.
   - **Second run** — copies the repo's `ccnotify.ini` into `~/.claude/ccnotify/ccnotify.ini` (overwriting any previous copy).

3. Then update your `~/.claude/settings.json` file with the following `hooks` block:

```json
"hooks": {
  "UserPromptSubmit": [
    {
      "hooks": [
        {
          "type": "command",
          "command": "~/.claude/ccnotify/ccnotify.py UserPromptSubmit"
        }
      ]
    }
  ],
  "Stop": [
    {
      "hooks": [
        {
          "type": "command",
          "command": "~/.claude/ccnotify/ccnotify.py Stop"
        }
      ]
    }
  ],
  "Notification": [
    {
      "hooks": [
        {
          "type": "command",
          "command": "~/.claude/ccnotify/ccnotify.py Notification"
        }
      ]
    }
  ],
  "PermissionRequest": [
    {
      "hooks": [
        {
          "type": "command",
          "command": "~/.claude/ccnotify/ccnotify.py PermissionRequest"
        }
      ]
    }
  ]
}
```

## Configuration

Three files are involved:

| File | Role |
|------|------|
| `<repo>/ccnotify.ini.example` | Committed template. Don't edit for personal use — your changes would get committed. New config keys land here. |
| `<repo>/ccnotify.ini` | Your personal config (gitignored). **Source of truth.** Edit this. |
| `~/.claude/ccnotify/ccnotify.ini` | What's actually read at runtime. Always overwritten by `install.sh` from the repo copy — don't edit this directly, your changes will be lost on the next install. |

Workflow: edit the repo's `ccnotify.ini`, run `./install.sh` to push it to the install location.

Run `./open.sh` to open `~/.claude/ccnotify/` in Finder (useful for inspecting the live config, log file, and database).

### `[ntfy]` — mobile push (optional)

| Key | Description |
|-----|-------------|
| `topic` | Your ntfy channel ID. Subscribe to the same topic in the ntfy app on your phone. Comment out or leave empty to disable mobile push. |
| `idle_seconds` | Only push to mobile if you've been idle (no keyboard/mouse) for at least this many seconds. Prevents your phone buzzing while you're at the Mac. Default: `60`. |

### `[focus]` — suppress notifications when Claude is focused

When the macOS app currently in the foreground is one you use to run Claude Code, CCNotify suppresses both the local popup and the ntfy push — the assumption being that you're already looking at Claude.

| Key | Description |
|-----|-------------|
| `apps` | Comma-separated list of macOS app names. Common values: `Code` (VSCode), `Warp`, `Terminal`, `iTerm2`, `Ghostty`. Leave empty to disable focus suppression entirely. |
| `match_window_title` | If `true`, suppress only when the frontmost window's title contains the basename of the project's working directory. This prevents suppression when you're focused on a different window of the same app (e.g. another VSCode project). Default: `false`. Window-title formats vary, so leave off if it produces false negatives. |

> **Note:** `match_window_title` has been tested with VSCode only. Other apps (Warp, Terminal, iTerm2, Ghostty, …) may expose window titles differently or not at all via macOS Accessibility — if it doesn't work for your terminal, leave `match_window_title = false`.

## Updating

- **Code changes** (e.g. after `git pull`) take effect immediately — `ccnotify.py` is a symlink, so the next hook fire runs the new code. There's no daemon to restart.
- **Config changes** require editing the repo's `ccnotify.ini` and re-running `./install.sh` to push the update to `~/.claude/ccnotify/`. The new config is read fresh on the next hook fire.
- **Hook changes** in `~/.claude/settings.json` require restarting your Claude Code session, because Claude Code reads its settings at session start.

When you `git pull` and `ccnotify.ini.example` gains new sections (e.g. for a new feature), they won't appear in your `ccnotify.ini` automatically — diff the two files in the repo and copy any new sections over before re-running `./install.sh`.

## Uninstalling

From the repo root, run `./uninstall.sh`. It reverses everything `install.sh` set up:

- removes the `ccnotify` hooks from `~/.claude/settings.json` (the original is backed up to `settings.json.bak` first; any other hooks and settings are left intact)
- removes the install directory `~/.claude/ccnotify/` (the symlinked `ccnotify.py`, the copied `ccnotify.ini`, and the runtime `ccnotify.db` / `ccnotify.log` files)

You'll be asked to confirm before anything is removed — pass `-y` (or `--yes`) to skip the prompt. Restart your Claude Code session afterwards so it re-reads `settings.json`.

Your repo (the source `ccnotify.py` and your personal `ccnotify.ini`) is left untouched, as are `terminal-notifier` and the ntfy app — uninstall those yourself if you no longer want them (e.g. `brew uninstall terminal-notifier`).

See [original repo](https://github.com/dazuiba/CCNotify) for further info