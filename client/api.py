"""HTTP API client for cmdr-coriolis-client.

Sends journal events to the Coriolis CMDR Journal API.
"""

import json
from typing import Optional

import requests

API_BASE_URL = "https://cmdr.coriolis.io"
JOURNAL_ENDPOINT = f"{API_BASE_URL}/api/journal/"

REQUEST_TIMEOUT = 15

# Events the Journal API actually processes — no point sending anything else
TRACKED_EVENTS = {
    'Commander', 'EngineerCraft', 'LoadGame', 'Loadout',
    'ShipyardSwap', 'StoredShips', 'StoredModules', 'Materials',
}


class ApiError(Exception):
    """Raised when the API returns an error response."""

    def __init__(self, message: str, status_code: Optional[int] = None) -> None:
        super().__init__(message)
        self.status_code = status_code


def is_tracked_event(event: dict) -> bool:
    """Return True if the event is one the Journal API cares about."""
    return event.get('event', '') in TRACKED_EVENTS


def send_journal_entry(entry: dict, cmdr_name: str, api_key: str) -> dict:
    """Send a single journal entry to the Coriolis CMDR Journal API.

    :param entry: A parsed journal event dict (raw journal format).
    :param cmdr_name: The commander name for attribution.
    :param api_key: The user's API key.
    :returns: The parsed JSON response from the server.
    :raises ApiError: If the server returns a non-2xx response.
    :raises requests.RequestException: For network-level errors.
    """
    if not api_key:
        raise ApiError("No API key configured.")

    payload = {
        'cmdr': cmdr_name,
        'entry': entry,
    }

    resp = requests.post(
        JOURNAL_ENDPOINT,
        headers={
            'X-Api-Key': api_key,
            'Content-Type': 'application/json',
            'User-Agent': 'CMDRCoriolisClient/1.0',
        },
        data=json.dumps(payload),
        timeout=REQUEST_TIMEOUT,
    )

    if not resp.ok:
        raise ApiError(
            f"Server returned {resp.status_code}: {resp.text[:500]}",
            status_code=resp.status_code,
        )

    return resp.json()


def send_journal_batch(entries: list, cmdr_name: str, api_key: str) -> dict:
    """Send a batch of journal entries to the Coriolis CMDR Journal API.

    :param entries: List of parsed journal event dicts.
    :param cmdr_name: The commander name for attribution.
    :param api_key: The user's API key.
    :returns: The parsed JSON response from the server.
    :raises ApiError: If the server returns a non-2xx response.
    :raises requests.RequestException: For network-level errors.
    """
    if not api_key:
        raise ApiError("No API key configured.")

    payload = {
        'cmdr': cmdr_name,
        'entries': entries,
    }

    resp = requests.post(
        JOURNAL_ENDPOINT,
        headers={
            'X-Api-Key': api_key,
            'Content-Type': 'application/json',
            'User-Agent': 'CMDRCoriolisClient/1.0',
        },
        data=json.dumps(payload),
        timeout=REQUEST_TIMEOUT,
    )

    if not resp.ok:
        raise ApiError(
            f"Server returned {resp.status_code}: {resp.text[:500]}",
            status_code=resp.status_code,
        )

    return resp.json()
