from __future__ import annotations

import os
from types import TracebackType
from typing import Any

from .http import HttpClient
from .services import AkumaClient, EnzanClient, SozoClient


class KaizenClient:
    """Main client for Kaizen AI Systems API."""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str = "https://api.kaizenaisystems.com",
        timeout: float = 30.0,
    ):
        resolved_key = api_key or os.environ.get("KAIZEN_API_KEY", "")
        self._http = HttpClient(base_url=base_url, api_key=resolved_key, timeout=timeout)
        self.akuma = AkumaClient(self._http)
        self.enzan = EnzanClient(self._http)
        self.sozo = SozoClient(self._http)

    def set_api_key(self, key: str) -> None:
        self._http.set_api_key(key)

    def set_base_url(self, url: str) -> None:
        self._http.set_base_url(url)

    def health(self) -> dict[str, Any]:
        return self._http.get("/health")

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> KaizenClient:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()
