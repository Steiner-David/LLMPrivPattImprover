"""HTTP helpers with explicit timeouts and lightweight response validation."""

from __future__ import annotations

from typing import Any, Protocol, cast

import requests

REQUEST_TIMEOUT_SECONDS = 10


class ResponseLike(Protocol):
    """Subset of requests.Response used by the fetchers."""

    text: str

    def raise_for_status(self) -> None:
        ...

    def json(self) -> Any:
        ...


class HttpClient(Protocol):
    """Minimal HTTP client protocol for requests and tests."""

    def get(self, url: str, *, timeout: int) -> ResponseLike:
        ...


def _client(client: HttpClient | None) -> HttpClient:
    return client or cast(HttpClient, requests)


def get_json(
    url: str,
    *,
    client: HttpClient | None = None,
    timeout: int = REQUEST_TIMEOUT_SECONDS,
) -> Any:
    """GET JSON from a URL and surface HTTP errors to callers."""
    response = _client(client).get(url, timeout=timeout)
    response.raise_for_status()
    return response.json()


def get_text(
    url: str,
    *,
    client: HttpClient | None = None,
    timeout: int = REQUEST_TIMEOUT_SECONDS,
) -> str:
    """GET text from a URL and surface HTTP errors to callers."""
    response = _client(client).get(url, timeout=timeout)
    response.raise_for_status()
    return response.text
