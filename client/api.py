"""HTTP API client for cmdr-coriolis-client.

Sends journal events to the cmdr-coriolis service at cmdr.coriolis.io.
"""

import json
from typing import Optional

import requests

API_BASE_URL = "https://cmdr.coriolis.io"
JOURNAL_ENDPOINT = f"{API_BASE_URL}/api/journal"

# Seconds to wait for a response before giving up
REQUEST_TIMEOUT = 15


class ApiError(Exception):
    """Raised when the API returns an error response."""

    def __init__(self, message: str, status_code: Optional[int] = None) -> None:
        super().__init__(message)
        self.status_code = status_code


def send_journal_event(event: dict, api_key: str) -> None:
    """Send a single journal *event* dict to the cmdr-coriolis API.

    :param event: A parsed journal event (dict).
    :param api_key: The user's API key / bearer token.
    :raises ApiError: If the server returns a non-2xx response.
    :raises requests.RequestException: For network-level errors.
    """
    if not api_key:
        raise ApiError("No API key configured.")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    response = requests.post(
        JOURNAL_ENDPOINT,
        headers=headers,
        data=json.dumps(event),
        timeout=REQUEST_TIMEOUT,
    )

    if not response.ok:
        raise ApiError(
            f"Server returned {response.status_code}: {response.text}",
            status_code=response.status_code,
        )


def send_journal_events(events: list, api_key: str) -> None:
    """Send a list of journal event dicts to the cmdr-coriolis API.

    :param events: A list of parsed journal event dicts.
    :param api_key: The user's API key / bearer token.
    :raises ApiError: If the server returns a non-2xx response.
    :raises requests.RequestException: For network-level errors.
    """
    if not api_key:
        raise ApiError("No API key configured.")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    response = requests.post(
        JOURNAL_ENDPOINT,
        headers=headers,
        data=json.dumps(events),
        timeout=REQUEST_TIMEOUT,
    )

    if not response.ok:
        raise ApiError(
            f"Server returned {response.status_code}: {response.text}",
            status_code=response.status_code,
        )
