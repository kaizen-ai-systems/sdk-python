"""Real-transport tests for kaizen.http.HttpClient.

Drives the underlying httpx.Client through MockTransport so err.data
preservation is exercised end-to-end instead of being faked at the test
boundary.
"""

from __future__ import annotations

import json

import httpx
import pytest

from kaizen.errors import KaizenAuthError, KaizenError, KaizenRateLimitError
from kaizen.http import HttpClient
from kaizen.services.akuma import AkumaClient


def _make_client_with_transport(transport: httpx.MockTransport) -> HttpClient:
    client = HttpClient(base_url="https://example.test", api_key="k")
    client._client = httpx.Client(transport=transport, timeout=5.0)
    return client


def test_http_client_preserves_structured_error_data():
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            422,
            headers={"X-Request-ID": "req-query-1"},
            json={"error": "bad sql", "sql": "select *", "warnings": ["blocked"]},
        )

    client = _make_client_with_transport(httpx.MockTransport(handler))
    with pytest.raises(KaizenError) as exc_info:
        client.post("/v1/akuma/queries/interactive", {})

    error = exc_info.value
    assert error.status == 422
    assert error.request_id == "req-query-1"
    assert error.data == {
        "error": "bad sql",
        "sql": "select *",
        "warnings": ["blocked"],
    }


def test_akuma_query_interactive_surfaces_non_2xx_error():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/akuma/queries/interactive"
        return httpx.Response(
            422,
            headers={"X-Request-ID": "req-query-1"},
            json={"error": "bad sql", "sql": "select *"},
        )

    http_client = _make_client_with_transport(httpx.MockTransport(handler))
    client = AkumaClient(http_client)

    with pytest.raises(KaizenError) as exc_info:
        client.query_interactive(dialect="postgres", prompt="show one row")

    error = exc_info.value
    assert error.status == 422
    assert error.request_id == "req-query-1"
    assert error.data == {
        "error": "bad sql",
        "sql": "select *",
    }


@pytest.mark.parametrize(
    ("body", "expected"),
    [
        (b"null", None),
        (b"[]", []),
        (b'"bad response"', "bad response"),
    ],
)
def test_akuma_query_interactive_preserves_malformed_top_level_body(body, expected):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/akuma/queries/interactive"
        return httpx.Response(
            200,
            content=body,
            headers={"Content-Type": "application/json"},
        )

    http_client = _make_client_with_transport(httpx.MockTransport(handler))
    client = AkumaClient(http_client)

    with pytest.raises(KaizenError) as exc_info:
        client.query_interactive(dialect="postgres", prompt="show one row")

    error = exc_info.value
    assert error.code == "INVALID_RESPONSE"
    assert error.data == {"response": expected}


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
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(409, json={"status": "stale"})

    client = _make_client_with_transport(httpx.MockTransport(handler))
    with pytest.raises(KaizenError) as exc_info:
        client.post("/v1/enzan/pricing/offers", {"gpu": {}})
    assert exc_info.value.status == 409
    assert exc_info.value.data == {"status": "stale"}


def test_http_client_throws_auth_error_on_401():
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": "bad key"})

    client = _make_client_with_transport(httpx.MockTransport(handler))
    with pytest.raises(KaizenAuthError) as exc_info:
        client.get("/x")
    assert exc_info.value.data == {"error": "bad key"}


def test_http_client_returns_decoded_body_on_2xx():
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"hello": "world"})

    client = _make_client_with_transport(httpx.MockTransport(handler))
    assert client.get("/x") == {"hello": "world"}


def test_http_client_handles_non_json_4xx_body_without_clobbering_data():
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            400,
            content=b"plain text error",
            headers={"Content-Type": "text/plain"},
        )

    client = _make_client_with_transport(httpx.MockTransport(handler))
    with pytest.raises(KaizenError) as exc_info:
        client.get("/x")
    assert exc_info.value.status == 400
    assert exc_info.value.data == {"error": "plain text error"}
    assert json.dumps(exc_info.value.data)
