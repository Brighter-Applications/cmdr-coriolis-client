"""Elite Dangerous journal file utilities.

Provides helpers to:
  - locate the default journal directory on Windows and Linux
  - find the most recent journal file in a directory
  - extract the CMDR name from journal events
  - tail a journal file and yield new JSON events as they appear
  - detect when a new journal file is created (new game session)
"""

import glob
import json
import os
import sys
import time


# ---------------------------------------------------------------------------
# Default journal directory detection
# ---------------------------------------------------------------------------

def _windows_default_journal_dir() -> str:
    saved_games = os.path.join(
        os.environ.get("USERPROFILE", os.path.expanduser("~")),
        "Saved Games",
        "Frontier Developments",
        "Elite Dangerous",
    )
    return saved_games


def _linux_default_journal_dirs() -> list:
    home = os.path.expanduser("~")
    return [
        os.path.join(
            home, ".local", "share", "Steam", "steamapps", "compatdata",
            "359320", "pfx", "drive_c", "users", "steamuser",
            "Saved Games", "Frontier Developments", "Elite Dangerous",
        ),
        os.path.join(
            home, ".steam", "steam", "steamapps", "compatdata",
            "359320", "pfx", "drive_c", "users", "steamuser",
            "Saved Games", "Frontier Developments", "Elite Dangerous",
        ),
        os.path.join(
            home, ".var", "app", "com.valvesoftware.Steam", ".local", "share",
            "Steam", "steamapps", "compatdata", "359320", "pfx",
            "drive_c", "users", "steamuser",
            "Saved Games", "Frontier Developments", "Elite Dangerous",
        ),
    ]


def default_journal_dir() -> str:
    """Return the best-guess default journal directory, or empty string."""
    if sys.platform == "win32":
        path = _windows_default_journal_dir()
        return path if os.path.isdir(path) else ""
    else:
        for candidate in _linux_default_journal_dirs():
            if os.path.isdir(candidate):
                return candidate
        return ""


# ---------------------------------------------------------------------------
# Journal file selection
# ---------------------------------------------------------------------------

def find_latest_journal(directory: str) -> str:
    """Return the path to the most recently modified journal file, or empty string."""
    if not directory or not os.path.isdir(directory):
        return ""
    pattern = os.path.join(directory, "Journal.*.log")
    files = glob.glob(pattern)
    if not files:
        return ""
    return max(files, key=os.path.getmtime)


# ---------------------------------------------------------------------------
# CMDR name extraction
# ---------------------------------------------------------------------------

def extract_cmdr_name(journal_path: str) -> str:
    """Scan a journal file and return the commander name, or empty string."""
    if not journal_path or not os.path.isfile(journal_path):
        return ""
    try:
        with open(journal_path, "r", encoding="utf-8") as fh:
            for raw_line in fh:
                line = raw_line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                etype = event.get("event", "")
                if etype == "Commander":
                    name = event.get("Name", "")
                    if name:
                        return name
                elif etype == "LoadGame":
                    name = event.get("Commander", "")
                    if name:
                        return name
    except OSError:
        pass
    return ""


# ---------------------------------------------------------------------------
# Journal tail / monitoring
# ---------------------------------------------------------------------------

class JournalTailer:
    """Incrementally read new lines from a journal file.

    On start, reads the entire current file from the beginning (to catch
    startup events like Commander, Materials, Loadout), then tails for
    new lines.

    Also watches for new journal files being created in the same directory
    (indicating a new game session) and switches to them automatically.
    """

    def __init__(self, journal_path: str, poll_interval: float = 1.0) -> None:
        self.journal_path = journal_path
        self.journal_dir = os.path.dirname(journal_path)
        self.poll_interval = poll_interval
        self._running = False

    def stop(self) -> None:
        """Signal the monitoring loop to stop."""
        self._running = False

    def read_new_events(self):
        """Generator that yields parsed journal event dicts.

        Reads the current file from the beginning, then tails for new lines.
        Periodically checks for newer journal files and switches to them.
        """
        self._running = True

        while self._running:
            try:
                fh = open(self.journal_path, "r", encoding="utf-8")
            except OSError:
                time.sleep(self.poll_interval)
                continue

            with fh:
                # Read from the beginning to catch startup events
                while self._running:
                    line = fh.readline()
                    if line:
                        line = line.strip()
                        if line:
                            try:
                                event = json.loads(line)
                                yield event
                            except json.JSONDecodeError:
                                continue
                    else:
                        # No more data — check for a newer journal file
                        newer = find_latest_journal(self.journal_dir)
                        if newer and newer != self.journal_path:
                            self.journal_path = newer
                            break  # break inner loop to open the new file

                        time.sleep(self.poll_interval)
