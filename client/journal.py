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

from client.api import TRACKED_EVENTS


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

def _find_last_tracked_event(journal_path: str) -> tuple:
    """Scan the journal file and return (last_tracked_event_dict, file_position_after_it).

    Returns (None, end_of_file_position) if no tracked events are found.
    """
    last_event = None
    last_event_end_pos = 0

    try:
        with open(journal_path, "r", encoding="utf-8") as fh:
            while True:
                pos_before = fh.tell()
                line = fh.readline()
                if not line:
                    break
                pos_after = fh.tell()
                line = line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if event.get("event", "") in TRACKED_EVENTS:
                    last_event = event
                    last_event_end_pos = pos_after

            # If no tracked event found, return end of file
            if last_event is None:
                last_event_end_pos = fh.tell()

    except OSError:
        pass

    return last_event, last_event_end_pos


class JournalTailer:
    """Incrementally read events from a journal file.

    On start, scans the existing file to find the last tracked event,
    yields just that one (to establish current state), then tails for
    all new tracked events going forward.

    Also watches for new journal files (new game session) and switches
    to them automatically.
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

        First yields the last tracked event from the existing file (catchup),
        then tails for new lines. Switches to newer journal files automatically.
        """
        self._running = True
        is_first_file = True

        while self._running:
            if is_first_file:
                # For the initial file, find the last tracked event and
                # start tailing from after it
                last_event, tail_from_pos = _find_last_tracked_event(self.journal_path)
                if last_event:
                    yield last_event
                is_first_file = False
            else:
                # For subsequent files (new game session), start from the beginning
                tail_from_pos = 0

            # Now tail from the determined position
            try:
                fh = open(self.journal_path, "r", encoding="utf-8")
            except OSError:
                time.sleep(self.poll_interval)
                continue

            with fh:
                fh.seek(tail_from_pos)

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
                            break  # break to open the new file

                        time.sleep(self.poll_interval)
