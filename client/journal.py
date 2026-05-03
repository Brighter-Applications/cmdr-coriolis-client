"""Elite Dangerous journal file utilities.

Provides helpers to:
  - locate the default journal directory on Windows and Linux
  - find the most recent journal file in a directory
  - extract the CMDR name from journal events
  - tail a journal file with smart catchup and deduplication
  - detect when a new journal file is created (new game session)
"""

import glob
import json
import os
import sys
import time

from client import config
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
                    return event.get("Name", "")
                elif etype == "LoadGame":
                    return event.get("Commander", "")
    except OSError:
        pass
    return ""


# ---------------------------------------------------------------------------
# Smart catchup — reduce redundant events on startup
# ---------------------------------------------------------------------------

# Events that make earlier events of certain types redundant:
# If a "Materials" event exists, earlier MaterialCollected/MaterialTrade are unnecessary.
# If a "Loadout" event exists, earlier EngineerCraft/ShipyardSwap are unnecessary.
_SUPERSEDED_BY = {
    'Materials': {'MaterialCollected', 'MaterialTrade'},
    'Loadout': {'EngineerCraft', 'ShipyardSwap'},
}


def _collect_catchup_events(journal_path: str, start_pos: int = 0) -> tuple:
    """Scan the journal from start_pos and return (events_to_send, end_position).

    Applies superseding rules so only the minimal set of events is returned.
    For example, if a Materials event exists after some MaterialCollected events,
    only the Materials event is kept.
    """
    tracked = []  # list of (event_dict, file_position_after)

    try:
        with open(journal_path, "r", encoding="utf-8") as fh:
            fh.seek(start_pos)
            while True:
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
                    tracked.append((event, pos_after))
    except OSError:
        return [], start_pos

    if not tracked:
        # Return the end of file position even if no tracked events found
        try:
            with open(journal_path, "r", encoding="utf-8") as fh:
                fh.seek(0, 2)
                return [], fh.tell()
        except OSError:
            return [], start_pos

    # Apply superseding rules: walk backwards and mark events to skip
    skip_types = set()
    keep = []

    for event, pos in reversed(tracked):
        etype = event.get("event", "")

        # If this event type is superseded by something we've already kept, skip it
        if etype in skip_types:
            continue

        keep.append((event, pos))

        # Mark the types this event supersedes
        if etype in _SUPERSEDED_BY:
            skip_types.update(_SUPERSEDED_BY[etype])

    keep.reverse()  # restore chronological order

    return keep, tracked[-1][1]  # return the position after the last tracked event


# ---------------------------------------------------------------------------
# Journal tail / monitoring
# ---------------------------------------------------------------------------

class JournalTailer:
    """Incrementally read events from a journal file.

    On start, checks the saved position from the config file. If the same
    journal file is being resumed, seeks to the saved position and does a
    smart catchup (applying superseding rules). Otherwise reads the new
    file with catchup from the beginning.

    Then tails for new events going forward, saving position after each
    successfully yielded event.
    """

    def __init__(self, journal_path: str, poll_interval: float = 1.0) -> None:
        self.journal_path = journal_path
        self.journal_dir = os.path.dirname(journal_path)
        self.poll_interval = poll_interval
        self._running = False

    def stop(self) -> None:
        self._running = False

    def read_new_events(self):
        """Generator that yields parsed journal event dicts.

        On startup, yields the minimal set of catchup events (with superseding).
        Then tails for new events, saving position after each yield.
        Switches to newer journal files automatically.
        """
        self._running = True

        while self._running:
            # Determine where to start reading
            saved_file, saved_pos = config.get_last_position()
            if saved_file == self.journal_path and saved_pos > 0:
                start_pos = saved_pos
            else:
                start_pos = 0

            # Smart catchup: collect and deduplicate existing events
            catchup_events, end_pos = _collect_catchup_events(self.journal_path, start_pos)

            for event, pos in catchup_events:
                if not self._running:
                    return
                yield event
                config.set_last_position(self.journal_path, pos)

            # Now tail from end_pos for new events
            try:
                fh = open(self.journal_path, "r", encoding="utf-8")
            except OSError:
                time.sleep(self.poll_interval)
                continue

            with fh:
                fh.seek(end_pos)

                while self._running:
                    line = fh.readline()
                    if line:
                        pos_after = fh.tell()
                        line = line.strip()
                        if line:
                            try:
                                event = json.loads(line)
                                # For live tailing, yield all tracked events (no superseding)
                                if event.get("event", "") in TRACKED_EVENTS:
                                    yield event
                                    config.set_last_position(self.journal_path, pos_after)
                            except json.JSONDecodeError:
                                continue
                    else:
                        # No more data — check for a newer journal file
                        newer = find_latest_journal(self.journal_dir)
                        if newer and newer != self.journal_path:
                            self.journal_path = newer
                            break  # break to open the new file

                        time.sleep(self.poll_interval)
