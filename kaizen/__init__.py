"""
Kaizen SDK - Official Python SDK for Kaizen AI Systems.
Products: Akuma (NL→SQL) | Enzan (GPU Cost) | Sōzō (Synthetic Data)
"""

from __future__ import annotations

from ._types import (
    AlertType,
    CorrelationType,
    CreatableAlertType,
    GroupByDimension,
    QueryMode,
    SQLDialect,
    TimeWindow,
)
from .client import KaizenClient
from .errors import (
    KaizenAuthError,
    KaizenError,
    KaizenRateLimitError,
    KaizenValidationError,
)
from .models import (
    AkumaColumn,
    AkumaExplainResponse,
    AkumaForeignKey,
    AkumaQueryResponse,
    AkumaSchemaResponse,
    AkumaSource,
    AkumaSourceMutationResponse,
    AkumaTable,
    APICostSummary,
    EnzanAlert,
    EnzanAlertDelivery,
    EnzanAlertEndpoint,
    EnzanAlertEndpointMutationResponse,
    EnzanAlertEndpointUpdateRequest,
    EnzanAlertEvent,
    EnzanAlertMutationResponse,
    EnzanBurnResponse,
    EnzanCreateAlertRequest,
    EnzanGPUPricing,
    EnzanGPUPricingMutationResponse,
    EnzanLLMPricing,
    EnzanLLMPricingMutationResponse,
    EnzanModelCategoryBreakdown,
    EnzanModelCostResponse,
    EnzanModelCostRow,
    EnzanModelCostTotal,
    EnzanOptimizeResponse,
    EnzanRecommendation,
    EnzanResource,
    EnzanRoutingConfig,
    EnzanRoutingConfigMutationResponse,
    EnzanRoutingSavingsBreakdown,
    EnzanRoutingSavingsResponse,
    EnzanSummaryResponse,
    EnzanSummaryRow,
    EnzanSummaryTotal,
    EnzanUpdateAlertRequest,
    Guardrails,
    SozoColumnStats,
    SozoGenerateResponse,
    SozoSchemaInfo,
    StatusWithIDResponse,
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
    "APICostSummary",
    "AkumaColumn",
    "AkumaClient",
    "AkumaExplainResponse",
    "AkumaForeignKey",
    "AkumaQueryResponse",
    "AkumaSchemaResponse",
    "AkumaSource",
    "AkumaSourceMutationResponse",
    "AkumaTable",
    "CorrelationType",
    "CreatableAlertType",
    "EnzanAlert",
    "EnzanCreateAlertRequest",
    "EnzanUpdateAlertRequest",
    "EnzanAlertDelivery",
    "EnzanAlertEndpoint",
    "EnzanAlertEndpointMutationResponse",
    "EnzanAlertEndpointUpdateRequest",
    "EnzanAlertEvent",
    "EnzanAlertMutationResponse",
    "EnzanBurnResponse",
    "EnzanClient",
    "EnzanGPUPricing",
    "EnzanGPUPricingMutationResponse",
    "EnzanLLMPricing",
    "EnzanLLMPricingMutationResponse",
    "EnzanModelCategoryBreakdown",
    "EnzanModelCostResponse",
    "EnzanModelCostRow",
    "EnzanModelCostTotal",
    "EnzanOptimizeResponse",
    "EnzanRecommendation",
    "EnzanResource",
    "EnzanRoutingConfig",
    "EnzanRoutingConfigMutationResponse",
    "EnzanRoutingSavingsBreakdown",
    "EnzanRoutingSavingsResponse",
    "StatusWithIDResponse",
    "EnzanSummaryResponse",
    "EnzanSummaryRow",
    "EnzanSummaryTotal",
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
