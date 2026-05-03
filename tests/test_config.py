"""Tests for client.config."""

import json
import os
import tempfile

import pytest

import client.config as cfg


@pytest.fixture(autouse=True)
def isolated_config(monkeypatch, tmp_path):
    """Redirect config storage to a temporary directory for each test."""
    monkeypatch.setattr(cfg, "_config_dir", lambda: str(tmp_path))
    yield tmp_path


def test_load_config_missing_file_returns_empty():
    result = cfg.load_config()
    assert result == {}


def test_save_and_load_roundtrip():
    cfg.save_config({"api_key": "test-key-123"})
    data = cfg.load_config()
    assert data["api_key"] == "test-key-123"


def test_save_config_merges_with_existing():
    cfg.save_config({"api_key": "key1"})
    cfg.save_config({"journal_path": "/some/path"})
    data = cfg.load_config()
    assert data["api_key"] == "key1"
    assert data["journal_path"] == "/some/path"


def test_get_set_api_key():
    assert cfg.get_api_key() == ""
    cfg.set_api_key("my-secret-key")
    assert cfg.get_api_key() == "my-secret-key"


def test_get_set_journal_path():
    assert cfg.get_journal_path() == ""
    cfg.set_journal_path("/elite/journals")
    assert cfg.get_journal_path() == "/elite/journals"


def test_load_config_invalid_json_returns_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(cfg, "_config_dir", lambda: str(tmp_path))
    config_path = tmp_path / "config.json"
    config_path.write_text("not valid json {{", encoding="utf-8")
    result = cfg.load_config()
    assert result == {}


def test_load_config_non_dict_json_returns_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(cfg, "_config_dir", lambda: str(tmp_path))
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps([1, 2, 3]), encoding="utf-8")
    result = cfg.load_config()
    assert result == {}
