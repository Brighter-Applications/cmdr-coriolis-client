"""Tests for client.journal."""

import json
import os
import time

import pytest

import client.journal as jrnl


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_journal(path, events):
    """Write a list of event dicts to *path* as JSONL."""
    with open(path, "w", encoding="utf-8") as fh:
        for event in events:
            fh.write(json.dumps(event) + "\n")


# ---------------------------------------------------------------------------
# default_journal_dir
# ---------------------------------------------------------------------------

def test_default_journal_dir_returns_string():
    result = jrnl.default_journal_dir()
    assert isinstance(result, str)


# ---------------------------------------------------------------------------
# find_latest_journal
# ---------------------------------------------------------------------------

def test_find_latest_journal_empty_dir(tmp_path):
    assert jrnl.find_latest_journal(str(tmp_path)) == ""


def test_find_latest_journal_no_dir():
    assert jrnl.find_latest_journal("/nonexistent/path") == ""


def test_find_latest_journal_returns_most_recent(tmp_path):
    old_file = tmp_path / "Journal.2024-01-01T120000.01.log"
    new_file = tmp_path / "Journal.2024-06-01T120000.01.log"
    old_file.write_text("{}\n")
    time.sleep(0.01)
    new_file.write_text("{}\n")

    result = jrnl.find_latest_journal(str(tmp_path))
    assert result == str(new_file)


def test_find_latest_journal_ignores_non_journal_files(tmp_path):
    (tmp_path / "notes.txt").write_text("hello")
    assert jrnl.find_latest_journal(str(tmp_path)) == ""


# ---------------------------------------------------------------------------
# extract_cmdr_name
# ---------------------------------------------------------------------------

def test_extract_cmdr_name_from_commander_event(tmp_path):
    journal = tmp_path / "Journal.2024-01-01T120000.01.log"
    _write_journal(journal, [
        {"timestamp": "2024-01-01T12:00:00Z", "event": "Fileheader"},
        {"timestamp": "2024-01-01T12:00:01Z", "event": "Commander", "FID": "F123", "Name": "Jameson"},
    ])
    assert jrnl.extract_cmdr_name(str(journal)) == "Jameson"


def test_extract_cmdr_name_from_loadgame_event(tmp_path):
    journal = tmp_path / "Journal.2024-01-01T120000.01.log"
    _write_journal(journal, [
        {"timestamp": "2024-01-01T12:00:00Z", "event": "Fileheader"},
        {"timestamp": "2024-01-01T12:00:01Z", "event": "LoadGame", "Commander": "Lave Station"},
    ])
    assert jrnl.extract_cmdr_name(str(journal)) == "Lave Station"


def test_extract_cmdr_name_prefers_commander_event(tmp_path):
    """Commander event should be returned before LoadGame if it appears first."""
    journal = tmp_path / "Journal.2024-01-01T120000.01.log"
    _write_journal(journal, [
        {"timestamp": "2024-01-01T12:00:00Z", "event": "Commander", "Name": "First"},
        {"timestamp": "2024-01-01T12:00:01Z", "event": "LoadGame", "Commander": "Second"},
    ])
    assert jrnl.extract_cmdr_name(str(journal)) == "First"


def test_extract_cmdr_name_missing_file():
    assert jrnl.extract_cmdr_name("/no/such/file.log") == ""


def test_extract_cmdr_name_no_cmdr_events(tmp_path):
    journal = tmp_path / "Journal.2024-01-01T120000.01.log"
    _write_journal(journal, [
        {"timestamp": "2024-01-01T12:00:00Z", "event": "Fileheader"},
        {"timestamp": "2024-01-01T12:00:01Z", "event": "Music"},
    ])
    assert jrnl.extract_cmdr_name(str(journal)) == ""


def test_extract_cmdr_name_skips_invalid_lines(tmp_path):
    journal = tmp_path / "Journal.2024-01-01T120000.01.log"
    with open(journal, "w", encoding="utf-8") as fh:
        fh.write("not valid json\n")
        fh.write(json.dumps({"event": "Commander", "Name": "ValidCmdr"}) + "\n")
    assert jrnl.extract_cmdr_name(str(journal)) == "ValidCmdr"


# ---------------------------------------------------------------------------
# JournalTailer
# ---------------------------------------------------------------------------

def test_tailer_yields_new_events(tmp_path):
    journal = tmp_path / "Journal.2024-01-01T120000.01.log"
    # Write initial content
    _write_journal(journal, [
        {"event": "Fileheader"},
    ])

    tailer = jrnl.JournalTailer(str(journal), poll_interval=0.05)

    results = []

    def run():
        for event in tailer.read_new_events():
            results.append(event)
            tailer.stop()

    import threading
    thread = threading.Thread(target=run, daemon=True)
    thread.start()

    # Give tailer time to seek to end, then append a new event
    time.sleep(0.1)
    with open(journal, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"event": "Music", "MusicTrack": "MainMenu"}) + "\n")

    thread.join(timeout=3)
    assert len(results) == 1
    assert results[0]["event"] == "Music"


def test_tailer_stops_cleanly(tmp_path):
    journal = tmp_path / "Journal.2024-01-01T120000.01.log"
    journal.write_text("")

    tailer = jrnl.JournalTailer(str(journal), poll_interval=0.05)

    import threading
    stopped = threading.Event()

    def run():
        for _ in tailer.read_new_events():
            pass
        stopped.set()

    thread = threading.Thread(target=run, daemon=True)
    thread.start()

    time.sleep(0.15)
    tailer.stop()
    thread.join(timeout=3)
    assert stopped.is_set()
