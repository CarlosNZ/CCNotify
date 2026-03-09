![Notification Screenshot](alert.jpg)

Fork of [https://github.com/dazuiba/CCNotify](https://github.com/dazuiba/CCNotify), with the following changes:
  - works with "Prompt" notifications (requests to edit, or run commands)
  - optional notifications to mobile device (via [ntfy](https://ntfy.sh/))
  - installer script to simplify setup

# CCNotify

CCNotify provides desktop notifications for Claude Code, alerting you when Claude needs your input or completes tasks.

## Installation

1. Install [`terminal-notifier`](https://github.com/julienXX/terminal-notifier):  
  `brew install terminal-notifier` (or see [here](https://github.com/dazuiba/CCNotify?tab=readme-ov-file#2-install-terminal-notifier) for alternative installation methods)
2. From within this repo root, run `./install.sh`
   - This will create a symlink of `ccnotify.py` in `~/.claude/ccnotify/` (Symlink ensures subsequent updates get automatically reflected in running version)
   - Prompts to provide a NTFY topic ID (if you want mobile notifications). This value can be any unique string. 
   - Copies `.ini` file to `~/.claude/ccnotify/` with your designated NTFY ID included

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

See [original repo](https://github.com/dazuiba/CCNotify) for further info