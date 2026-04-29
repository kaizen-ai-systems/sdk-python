"""Real-transport tests for kaizen.http.HttpClient.

Drives the underlying httpx.Client through MockTransport so the new
err.data preservation logic on 429/409 (and the generic >=400 path) is
exercised end-to-end instead of being faked at the test boundary.
"""

from __future__ import annotations

import json

import httpx
import pytest

from kaizen.errors import KaizenAuthError, KaizenError, KaizenRateLimitError
from kaizen.http import HttpClient


def _make_client_with_transport(transport: httpx.MockTransport) -> HttpClient:
    client = HttpClient(base_url="https://example.test", api_key="k")
    client._client = httpx.Client(transport=transport, timeout=5.0)
    return client


def test_http_client_preserves_typed_429_body_on_err_data():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/enzan/pricing/refresh"
        return httpx.Response(
            429,
            json={
                "status": "dropped",
                "triggeredBy": "33333333-3333-3333-3333-333333333333",
            },
        )

    client = _make_client_with_transport(httpx.MockTransport(handler))
    with pytest.raises(KaizenRateLimitError) as exc_info:
        client.post("/v1/enzan/pricing/refresh", {})
    assert exc_info.value.status == 429
    assert exc_info.value.data == {
        "status": "dropped",
        "triggeredBy": "33333333-3333-3333-3333-333333333333",
    }


def test_http_client_preserves_typed_409_body_on_err_data():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(409, json={"status": "stale"})

    client = _make_client_with_transport(httpx.MockTransport(handler))
    with pytest.raises(KaizenError) as exc_info:
        client.post("/v1/enzan/pricing/offers", {"gpu": {}})
    assert exc_info.value.status == 409
    assert exc_info.value.data == {"status": "stale"}


def test_http_client_throws_auth_error_on_401():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": "bad key"})

    client = _make_client_with_transport(httpx.MockTransport(handler))
    with pytest.raises(KaizenAuthError):
        client.get("/x")


def test_http_client_returns_decoded_body_on_2xx():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"hello": "world"})

    client = _make_client_with_transport(httpx.MockTransport(handler))
    assert client.get("/x") == {"hello": "world"}


def test_http_client_handles_non_json_4xx_body_without_clobbering_data():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, content=b"plain text error", headers={"Content-Type": "text/plain"})

    client = _make_client_with_transport(httpx.MockTransport(handler))
    with pytest.raises(KaizenError) as exc_info:
        client.get("/x")
    assert exc_info.value.status == 400
    # Non-JSON bodies surface as {"error": <text>} via _parse_json fallback.
    assert exc_info.value.data == {"error": "plain text error"}
    # Sanity: ensure the JSON test didn't accidentally false-positive.
    assert json.dumps(exc_info.value.data)
