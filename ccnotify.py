#!/usr/bin/env python3
"""
Claude Code Notify (with ntfy + idle detection)
https://github.com/dazuiba/CCNotify
"""

import os
import sys
import json
import sqlite3
import subprocess
import logging
import urllib.request
import configparser
from logging.handlers import TimedRotatingFileHandler
from datetime import datetime

# Load config from ccnotify.ini next to this script
_config = configparser.ConfigParser()
_config.read(os.path.join(os.path.dirname(os.path.abspath(__file__)), "ccnotify.ini"))

# ntfy.sh push notifications — configure in ccnotify.ini:
#   [ntfy]
#   topic = my-secret-topic
#   idle_seconds = 60
NTFY_TOPIC = _config.get("ntfy", "topic", fallback=None)
NTFY_IDLE_SECONDS = _config.getint("ntfy", "idle_seconds", fallback=60)

# Suppress notifications when one of these macOS apps is frontmost — configure in ccnotify.ini:
#   [focus]
#   apps = Code,Warp,Terminal
#   match_window_title = false
FOCUS_APPS = [
    a.strip()
    for a in _config.get("focus", "apps", fallback="").split(",")
    if a.strip()
]
FOCUS_MATCH_WINDOW_TITLE = _config.getboolean(
    "focus", "match_window_title", fallback=False
)


class ClaudePromptTracker:
    def __init__(self):
        """Initialize the prompt tracker with database setup"""
        script_dir = os.path.dirname(os.path.abspath(__file__))
        self.db_path = os.path.join(script_dir, "ccnotify.db")
        self.setup_logging()
        self.init_database()

    def setup_logging(self):
        """Setup logging to file with daily rotation"""

        script_dir = os.path.dirname(os.path.abspath(__file__))
        log_path = os.path.join(script_dir, "ccnotify.log")

        # Create a timed rotating file handler
        handler = TimedRotatingFileHandler(
            log_path,
            when="midnight",  # Rotate at midnight
            interval=1,  # Every 1 day
            backupCount=1,  # Keep 1 days of logs
            encoding="utf-8",
        )

        # Set the log format
        formatter = logging.Formatter(
            "%(asctime)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
        )
        handler.setFormatter(formatter)

        # Configure the root logger
        logger = logging.getLogger()
        logger.setLevel(logging.INFO)
        logger.addHandler(handler)

    def init_database(self):
        """Create tables and triggers if they don't exist"""
        with sqlite3.connect(self.db_path) as conn:
            # Create main table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS prompt (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    prompt TEXT,
                    cwd TEXT,
                    seq INTEGER,
                    stoped_at DATETIME,
                    lastWaitUserAt DATETIME
                )
            """)

            # Create trigger for auto-incrementing seq
            conn.execute("""
                CREATE TRIGGER IF NOT EXISTS auto_increment_seq
                AFTER INSERT ON prompt
                FOR EACH ROW
                BEGIN
                    UPDATE prompt
                    SET seq = (
                        SELECT COALESCE(MAX(seq), 0) + 1
                        FROM prompt
                        WHERE session_id = NEW.session_id
                    )
                    WHERE id = NEW.id;
                END
            """)

            conn.commit()

    def handle_user_prompt_submit(self, data):
        """Handle UserPromptSubmit event - insert new prompt record"""
        session_id = data.get("session_id")
        prompt = data.get("prompt", "")
        cwd = data.get("cwd", "")

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO prompt (session_id, prompt, cwd)
                VALUES (?, ?, ?)
            """,
                (session_id, prompt, cwd),
            )
            conn.commit()

        logging.info(f"Recorded prompt for session {session_id}")

    def handle_stop(self, data):
        """Handle Stop event - update completion time and send notification"""
        session_id = data.get("session_id")

        with sqlite3.connect(self.db_path) as conn:
            # Find the latest unfinished record for this session
            cursor = conn.execute(
                """
                SELECT id, created_at, cwd
                FROM prompt
                WHERE session_id = ? AND stoped_at IS NULL
                ORDER BY created_at DESC
                LIMIT 1
            """,
                (session_id,),
            )

            row = cursor.fetchone()
            if row:
                record_id, created_at, cwd = row

                # Update completion time
                conn.execute(
                    """
                    UPDATE prompt
                    SET stoped_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """,
                    (record_id,),
                )
                conn.commit()

                # Get seq number and calculate duration
                cursor = conn.execute(
                    "SELECT seq FROM prompt WHERE id = ?", (record_id,)
                )
                seq_row = cursor.fetchone()
                seq = seq_row[0] if seq_row else 1

                duration = self.calculate_duration_from_db(record_id)
                self.send_notification(
                    title=os.path.basename(cwd) if cwd else "Claude Task",
                    subtitle=f"job#{seq} done, duration: {duration}",
                    cwd=cwd,
                )

                logging.info(
                    f"Task completed for session {session_id}, job#{seq}, duration: {duration}"
                )

    def handle_permission_request(self, data):
        """Handle PermissionRequest event - send notification when Claude needs permission"""
        session_id = data.get("session_id")
        tool_name = data.get("tool_name", "a tool")
        cwd = data.get("cwd", "")

        logging.info(f"[PERMISSION_REQUEST] session={session_id}, tool={tool_name}")

        self.send_notification(
            title=os.path.basename(cwd) if cwd else "Claude Task",
            subtitle=f"Permission needed: {tool_name}",
            cwd=cwd,
        )
        logging.info(f"Permission notification sent for session {session_id}: {tool_name}")

    def handle_notification(self, data):
        """Handle Notification event - check for various notification types and send notifications"""
        session_id = data.get("session_id")
        message = data.get("message", "")
        cwd = data.get("cwd", "")

        # Log all notifications for debugging
        logging.info(f"[NOTIFICATION] session={session_id}, message='{message}'")

        # Determine notification type and subtitle
        message_lower = message.lower()
        subtitle = None
        should_update_db = False
        should_notify = True

        if (
            "waiting for your input" in message_lower
            or "waiting for input" in message_lower
        ):
            subtitle = "Waiting for input"
            should_update_db = True
            should_notify = (
                False  # Suppress notification - Stop handler will send "job done"
            )
        elif "permission" in message_lower:
            subtitle = "Permission Required"
        elif "approval" in message_lower or "choose an option" in message_lower:
            subtitle = "Action Required"
        else:
            # For other notifications, use a generic subtitle
            subtitle = "Notification"

        # Update database for waiting notifications
        if should_update_db:
            with sqlite3.connect(self.db_path) as conn:
                # Fix: Use subquery instead of ORDER BY/LIMIT in UPDATE
                conn.execute(
                    """
                    UPDATE prompt
                    SET lastWaitUserAt = CURRENT_TIMESTAMP
                    WHERE id = (
                        SELECT id FROM prompt
                        WHERE session_id = ?
                        ORDER BY created_at DESC
                        LIMIT 1
                    )
                """,
                    (session_id,),
                )
                conn.commit()
            logging.info(f"Updated lastWaitUserAt for session {session_id}")

        # Send notification only if should_notify is True
        if should_notify:
            self.send_notification(
                title=os.path.basename(cwd) if cwd else "Claude Task",
                subtitle=subtitle,
                cwd=cwd,
            )
            logging.info(f"Notification sent for session {session_id}: {subtitle}")
        else:
            logging.info(
                f"Notification suppressed for session {session_id}: {subtitle}"
            )

    def calculate_duration_from_db(self, record_id):
        """Calculate duration for a completed record"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                SELECT created_at, stoped_at
                FROM prompt
                WHERE id = ?
            """,
                (record_id,),
            )

            row = cursor.fetchone()
            if row and row[1]:
                return self.calculate_duration(row[0], row[1])

        return "Unknown"

    def calculate_duration(self, start_time, end_time):
        """Calculate human-readable duration between two timestamps"""
        try:
            if isinstance(start_time, str):
                start_dt = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
            else:
                start_dt = datetime.fromisoformat(start_time)

            if isinstance(end_time, str):
                end_dt = datetime.fromisoformat(end_time.replace("Z", "+00:00"))
            else:
                end_dt = datetime.fromisoformat(end_time)

            duration = end_dt - start_dt
            total_seconds = int(duration.total_seconds())

            if total_seconds < 60:
                return f"{total_seconds}s"
            elif total_seconds < 3600:
                minutes = total_seconds // 60
                seconds = total_seconds % 60
                if seconds > 0:
                    return f"{minutes}m{seconds}s"
                else:
                    return f"{minutes}m"
            else:
                hours = total_seconds // 3600
                minutes = (total_seconds % 3600) // 60
                if minutes > 0:
                    return f"{hours}h{minutes}m"
                else:
                    return f"{hours}h"
        except Exception as e:
            logging.error(f"Error calculating duration: {e}")
            return "Unknown"

    def send_notification(self, title, subtitle, cwd=None):
        """Send macOS notification using terminal-notifier and push via ntfy"""
        from datetime import datetime

        if self._is_claude_focused(cwd):
            logging.info(f"Notification suppressed (Claude focused): {title} - {subtitle}")
            return

        current_time = datetime.now().strftime("%B %d, %Y at %H:%M")

        try:
            cmd = [
                "terminal-notifier",
                "-sound",
                "default",
                "-title",
                title,
                "-subtitle",
                f"{subtitle}\n{current_time}",
            ]

            if cwd:
                cmd.extend(["-execute", f'/usr/local/bin/code "{cwd}"'])

            subprocess.run(cmd, check=False, capture_output=True)
            logging.info(f"Notification sent: {title} - {subtitle}")
        except FileNotFoundError:
            logging.warning("terminal-notifier not found, notification skipped")
        except Exception as e:
            logging.error(f"Error sending notification: {e}")

        if NTFY_TOPIC and self._is_user_idle():
            try:
                req = urllib.request.Request(
                    f"https://ntfy.sh/{NTFY_TOPIC}",
                    data=subtitle.encode(),
                    headers={"Title": title},
                )
                urllib.request.urlopen(req, timeout=5)
                logging.info(f"ntfy push sent: {title} - {subtitle}")
            except Exception as e:
                logging.error(f"ntfy push failed: {e}")

    def _is_claude_focused(self, cwd=None):
        """Return True if the frontmost app is one the user considers 'Claude focused'.

        When match_window_title is enabled, also requires the frontmost window's
        title to contain basename(cwd) — so a different project window of the
        same app does not suppress the notification.
        """
        if not FOCUS_APPS:
            return False
        try:
            # Use AXMain to find the active window (Electron apps like VSCode
            # don't expose window names through `window 1` or `front window`).
            # Falls back to scanning all windows for the first non-empty title.
            script = (
                'tell application "System Events"\n'
                '  set frontApp to first process whose frontmost is true\n'
                '  set appName to name of frontApp\n'
                '  set winName to ""\n'
                '  try\n'
                '    set winName to value of attribute "AXTitle" of (first window of frontApp whose value of attribute "AXMain" is true)\n'
                '    if winName is missing value then set winName to ""\n'
                '  end try\n'
                '  if winName is "" then\n'
                '    try\n'
                '      repeat with w in windows of frontApp\n'
                '        set t to ""\n'
                '        try\n'
                '          set t to value of attribute "AXTitle" of w\n'
                '          if t is missing value then set t to ""\n'
                '        end try\n'
                '        if t is not "" then\n'
                '          set winName to t\n'
                '          exit repeat\n'
                '        end if\n'
                '      end repeat\n'
                '    end try\n'
                '  end if\n'
                '  return appName & "\t" & winName\n'
                'end tell'
            )
            result = subprocess.run(
                ["osascript", "-e", script],
                capture_output=True, text=True, timeout=2,
            )
            if result.returncode != 0:
                logging.error(f"osascript failed: {result.stderr.strip()}")
                return False
            app_name, _, win_title = result.stdout.strip().partition("\t")
            project = os.path.basename(cwd.rstrip("/")) if cwd else ""
            logging.info(
                f"Focus check: app={app_name!r}, title={win_title!r}, "
                f"project={project!r}, focus_apps={FOCUS_APPS}, "
                f"match_window_title={FOCUS_MATCH_WINDOW_TITLE}"
            )
            if app_name not in FOCUS_APPS:
                return False
            if FOCUS_MATCH_WINDOW_TITLE and project and project not in win_title:
                return False
            return True
        except Exception as e:
            logging.error(f"Failed to check focused app: {e}")
            return False

    def _is_user_idle(self):
        """Check if the user has been idle longer than NTFY_IDLE_SECONDS"""
        try:
            result = subprocess.run(
                ["ioreg", "-c", "IOHIDSystem", "-d", "4"],
                capture_output=True, text=True, timeout=5,
            )
            for line in result.stdout.splitlines():
                if "HIDIdleTime" in line:
                    # Value is in nanoseconds
                    ns = int(line.split("=")[-1].strip())
                    idle_secs = ns / 1_000_000_000
                    logging.info(f"User idle time: {idle_secs:.0f}s (threshold: {NTFY_IDLE_SECONDS}s)")
                    return idle_secs >= NTFY_IDLE_SECONDS
        except Exception as e:
            logging.error(f"Failed to check idle time: {e}")
        # If we can't determine idle time, send the notification to be safe
        return True


def validate_input_data(data, expected_event_name):
    """Validate input data matches design specification"""
    required_fields = {
        "UserPromptSubmit": ["session_id", "prompt", "cwd", "hook_event_name"],
        "Stop": ["session_id", "hook_event_name"],
        "Notification": ["session_id", "message", "hook_event_name"],
        "PermissionRequest": ["session_id", "hook_event_name"],
    }

    if expected_event_name not in required_fields:
        raise ValueError(f"Unknown event type: {expected_event_name}")

    # Check hook_event_name matches expected
    if data.get("hook_event_name") != expected_event_name:
        raise ValueError(
            f"Event name mismatch: expected {expected_event_name}, got {data.get('hook_event_name')}"
        )

    # Check required fields
    missing_fields = []
    for field in required_fields[expected_event_name]:
        if field not in data or data[field] is None:
            missing_fields.append(field)

    if missing_fields:
        raise ValueError(
            f"Missing required fields for {expected_event_name}: {missing_fields}"
        )

    return True


def main():
    """Main entry point - read JSON from stdin and process event"""
    try:
        # Check if hook type is provided as command line argument
        if len(sys.argv) < 2:
            print("ok")
            return

        expected_event_name = sys.argv[1]
        valid_events = ["UserPromptSubmit", "Stop", "Notification", "PermissionRequest"]

        if expected_event_name not in valid_events:
            logging.error(f"Invalid hook type: {expected_event_name}")
            logging.error(f"Valid hook types: {', '.join(valid_events)}")
            sys.exit(1)

        # Read JSON data from stdin
        input_data = sys.stdin.read().strip()
        if not input_data:
            logging.warning("No input data received")
            return

        data = json.loads(input_data)

        # Validate input data
        validate_input_data(data, expected_event_name)

        tracker = ClaudePromptTracker()

        if expected_event_name == "UserPromptSubmit":
            tracker.handle_user_prompt_submit(data)
        elif expected_event_name == "Stop":
            tracker.handle_stop(data)
        elif expected_event_name == "Notification":
            tracker.handle_notification(data)
        elif expected_event_name == "PermissionRequest":
            tracker.handle_permission_request(data)

    except json.JSONDecodeError as e:
        logging.error(f"JSON decode error: {e}")
        sys.exit(1)
    except ValueError as e:
        logging.error(f"Validation error: {e}")
        sys.exit(1)
    except Exception as e:
        logging.error(f"Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
