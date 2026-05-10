import httpx
import pytest

from kaizen import KaizenClient
from kaizen.errors import KaizenError


def test_health_requires_object_response():
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=b"null",
            headers={"Content-Type": "application/json"},
        )

    client = KaizenClient(api_key="k", base_url="https://example.test")
    client._http._client = httpx.Client(transport=httpx.MockTransport(handler), timeout=5.0)

    with pytest.raises(KaizenError) as exc_info:
        client.health()

    assert exc_info.value.code == "INVALID_RESPONSE"
    assert exc_info.value.data == {"response": None}
