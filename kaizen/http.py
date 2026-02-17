from __future__ import annotations

from typing import Any, cast

import httpx

from .errors import KaizenAuthError, KaizenError, KaizenRateLimitError

SDK_VERSION = "1.0.0"


class HttpClient:
    """HTTP client for Kaizen API requests."""

    def __init__(
        self,
        base_url: str = "https://api.kaizenaisystems.com",
        api_key: str = "",
        timeout: float = 30.0,
    ):
        self.base_url = base_url
        self.api_key = api_key
        self.timeout = timeout
        self._client = httpx.Client(timeout=self.timeout)

    def set_api_key(self, key: str) -> None:
        self.api_key = key

    def set_base_url(self, url: str) -> None:
        self.base_url = url

    def close(self) -> None:
        self._client.close()

    def get(self, path: str) -> dict[str, Any]:
        return self._request("GET", path)

    def post(self, path: str, data: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", path, data)

    def _request(
        self,
        method: str,
        path: str,
        json_data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        headers = {"User-Agent": f"kaizen-python/{SDK_VERSION}"}
        if method != "GET":
            headers["Content-Type"] = "application/json"
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        try:
            response = self._client.request(method, url, headers=headers, json=json_data)
            data = self._parse_json(response)
            request_id = response.headers.get("X-Request-ID")
            message = str(data.get("error") or "Request failed")

            if response.status_code == 401:
                raise KaizenAuthError(message, request_id=request_id)
            if response.status_code == 429:
                retry_after = response.headers.get("Retry-After")
                raise KaizenRateLimitError(
                    message,
                    int(retry_after) if retry_after else None,
                    request_id=request_id,
                )
            if response.status_code >= 400:
                raise KaizenError(message, response.status_code, request_id=request_id)

            return data
        except httpx.RequestError as error:
            raise KaizenError(f"Request failed: {error}") from error

    def _parse_json(self, response: httpx.Response) -> dict[str, Any]:
        try:
            parsed = response.json()
        except ValueError:
            text = response.text.strip()
            return {"error": text} if text else {}
        if isinstance(parsed, dict):
            return cast(dict[str, Any], parsed)
        return {}
