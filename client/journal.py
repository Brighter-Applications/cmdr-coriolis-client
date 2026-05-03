"""Elite Dangerous journal file utilities for cmdr-coriolis-client.

Provides helpers to:
  - locate the default journal directory on Windows and Linux
  - find the most recent journal file in a directory
  - extract the CMDR name from journal events
  - tail a journal file and yield new JSON events as they appear
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
    """Return the standard Elite Dangerous journal directory on Windows."""
    saved_games = os.path.join(
        os.environ.get("USERPROFILE", os.path.expanduser("~")),
        "Saved Games",
        "Frontier Developments",
        "Elite Dangerous",
    )
    return saved_games


def _linux_default_journal_dirs() -> list:
    """Return candidate journal directories for Linux (Steam / Proton)."""
    home = os.path.expanduser("~")
    candidates = [
        # Steam default (Proton)
        os.path.join(
            home,
            ".local", "share", "Steam", "steamapps", "compatdata",
            "359320", "pfx", "drive_c", "users", "steamuser",
            "Saved Games", "Frontier Developments", "Elite Dangerous",
        ),
        # Alternate Steam location
        os.path.join(
            home,
            ".steam", "steam", "steamapps", "compatdata",
            "359320", "pfx", "drive_c", "users", "steamuser",
            "Saved Games", "Frontier Developments", "Elite Dangerous",
        ),
        # Flatpak Steam
        os.path.join(
            home,
            ".var", "app", "com.valvesoftware.Steam", ".local", "share",
            "Steam", "steamapps", "compatdata", "359320", "pfx",
            "drive_c", "users", "steamuser",
            "Saved Games", "Frontier Developments", "Elite Dangerous",
        ),
    ]
    return candidates


def default_journal_dir() -> str:
    """Return the best-guess default journal directory for the current OS.

    Returns an empty string if no suitable directory is found.
    """
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
    """Return the path to the most recently modified journal file in *directory*.

    Journal files are named ``Journal.YYYY-MM-DDTHHMMSS.NN.log``.
    Returns an empty string if no journal files are found.
    """
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
    """Scan *journal_path* and return the commander name found in it.

    Checks both ``Commander`` and ``LoadGame`` event types.
    Returns an empty string if the name cannot be determined.
    """
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
                event_type = event.get("event", "")
                if event_type == "Commander":
                    name = event.get("Name", "")
                    if name:
                        return name
                elif event_type == "LoadGame":
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

    Usage::

        tailer = JournalTailer("/path/to/Journal.log")
        for event in tailer.read_new_events():
            print(event)

    Call :meth:`stop` from another thread to end the monitoring loop.
    """

    def __init__(self, journal_path: str, poll_interval: float = 1.0) -> None:
        self.journal_path = journal_path
        self.poll_interval = poll_interval
        self._running = False
        self._file_pos = 0

    def stop(self) -> None:
        """Signal the monitoring loop to stop."""
        self._running = False

    def read_new_events(self):
        """Generator that yields new JSON events as they appear in the file.

        Yields dicts parsed from new lines.  Skips unparseable lines.
        Blocks between polls; call :meth:`stop` to terminate the loop.
        """
        self._running = True
        try:
            fh = open(self.journal_path, "r", encoding="utf-8")
        except OSError:
            return

        with fh:
            # Seek to end to only pick up new events
            fh.seek(0, 2)
            self._file_pos = fh.tell()

            while self._running:
                fh.seek(self._file_pos)
                raw = fh.read()
                if raw:
                    self._file_pos = fh.tell()
                    for raw_line in raw.splitlines():
                        line = raw_line.strip()
                        if not line:
                            continue
                        try:
                            event = json.loads(line)
                            yield event
                        except json.JSONDecodeError:
                            continue
                time.sleep(self.poll_interval)
