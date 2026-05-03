"""Tests for client.api."""

import json
from unittest.mock import MagicMock, patch

import pytest
import requests

from client.api import ApiError, send_journal_event, send_journal_events, JOURNAL_ENDPOINT


SAMPLE_EVENT = {"timestamp": "2024-01-01T12:00:00Z", "event": "Music", "MusicTrack": "MainMenu"}
FAKE_KEY = "test-api-key-xyz"


# ---------------------------------------------------------------------------
# send_journal_event
# ---------------------------------------------------------------------------

def test_send_journal_event_success():
    mock_response = MagicMock()
    mock_response.ok = True

    with patch("client.api.requests.post", return_value=mock_response) as mock_post:
        send_journal_event(SAMPLE_EVENT, FAKE_KEY)

    mock_post.assert_called_once()
    call_kwargs = mock_post.call_args
    assert call_kwargs[0][0] == JOURNAL_ENDPOINT
    assert call_kwargs[1]["headers"]["Authorization"] == f"Bearer {FAKE_KEY}"
    assert call_kwargs[1]["headers"]["Content-Type"] == "application/json"
    # Body should be valid JSON
    body = json.loads(call_kwargs[1]["data"])
    assert body["event"] == "Music"


def test_send_journal_event_api_error_on_bad_status():
    mock_response = MagicMock()
    mock_response.ok = False
    mock_response.status_code = 403
    mock_response.text = "Forbidden"

    with patch("client.api.requests.post", return_value=mock_response):
        with pytest.raises(ApiError) as exc_info:
            send_journal_event(SAMPLE_EVENT, FAKE_KEY)

    assert exc_info.value.status_code == 403
    assert "403" in str(exc_info.value)


def test_send_journal_event_raises_without_api_key():
    with pytest.raises(ApiError, match="No API key"):
        send_journal_event(SAMPLE_EVENT, "")


def test_send_journal_event_propagates_network_error():
    with patch("client.api.requests.post", side_effect=requests.ConnectionError("no route")):
        with pytest.raises(requests.ConnectionError):
            send_journal_event(SAMPLE_EVENT, FAKE_KEY)


# ---------------------------------------------------------------------------
# send_journal_events (batch)
# ---------------------------------------------------------------------------

def test_send_journal_events_success():
    mock_response = MagicMock()
    mock_response.ok = True

    events = [SAMPLE_EVENT, {"event": "Shutdown"}]
    with patch("client.api.requests.post", return_value=mock_response) as mock_post:
        send_journal_events(events, FAKE_KEY)

    body = json.loads(mock_post.call_args[1]["data"])
    assert isinstance(body, list)
    assert len(body) == 2


def test_send_journal_events_raises_without_api_key():
    with pytest.raises(ApiError, match="No API key"):
        send_journal_events([SAMPLE_EVENT], "")


def test_send_journal_events_api_error_on_bad_status():
    mock_response = MagicMock()
    mock_response.ok = False
    mock_response.status_code = 500
    mock_response.text = "Internal Server Error"

    with patch("client.api.requests.post", return_value=mock_response):
        with pytest.raises(ApiError) as exc_info:
            send_journal_events([SAMPLE_EVENT], FAKE_KEY)

    assert exc_info.value.status_code == 500
