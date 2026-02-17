"""
Kaizen SDK - Official Python SDK for Kaizen AI Systems.
Products: Akuma (NL→SQL) | Enzan (GPU Cost) | Sōzō (Synthetic Data)
"""

from __future__ import annotations

from ._types import AlertType, CorrelationType, GroupByDimension, QueryMode, SQLDialect, TimeWindow
from .client import KaizenClient
from .errors import KaizenAuthError, KaizenError, KaizenRateLimitError, KaizenValidationError
from .models import (
    AkumaColumn,
    AkumaExplainResponse,
    AkumaForeignKey,
    AkumaQueryResponse,
    AkumaSchemaResponse,
    AkumaTable,
    EnzanAlert,
    EnzanBurnResponse,
    EnzanResource,
    EnzanSummaryResponse,
    EnzanSummaryRow,
    Guardrails,
    SozoColumnStats,
    SozoGenerateResponse,
    SozoSchemaInfo,
)
from .services import AkumaClient, EnzanClient, SozoClient

__version__ = "1.0.0"

_default_client = KaizenClient()

akuma = _default_client.akuma
enzan = _default_client.enzan
sozo = _default_client.sozo


def set_api_key(key: str) -> None:
    """Set the API key for the default client."""

    _default_client.set_api_key(key)


def set_base_url(url: str) -> None:
    """Set the API base URL for the default client."""

    _default_client.set_base_url(url)


__all__ = [
    "AlertType",
    "AkumaColumn",
    "AkumaClient",
    "AkumaExplainResponse",
    "AkumaForeignKey",
    "AkumaQueryResponse",
    "AkumaSchemaResponse",
    "AkumaTable",
    "CorrelationType",
    "EnzanAlert",
    "EnzanBurnResponse",
    "EnzanClient",
    "EnzanResource",
    "EnzanSummaryResponse",
    "EnzanSummaryRow",
    "GroupByDimension",
    "Guardrails",
    "KaizenAuthError",
    "KaizenClient",
    "KaizenError",
    "KaizenRateLimitError",
    "KaizenValidationError",
    "QueryMode",
    "SQLDialect",
    "SozoClient",
    "SozoColumnStats",
    "SozoGenerateResponse",
    "SozoSchemaInfo",
    "TimeWindow",
    "akuma",
    "enzan",
    "set_api_key",
    "set_base_url",
    "sozo",
]
