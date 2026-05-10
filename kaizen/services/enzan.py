from __future__ import annotations

import math
from decimal import Decimal, InvalidOperation
from typing import Any, cast
from urllib.parse import quote

from .._types import GroupByDimension, TimeWindow
from ..http import HttpClient
from ..models import (
    APICostSummary,
    EnzanAlert,
    EnzanAlertDelivery,
    EnzanAlertEndpoint,
    EnzanAlertEndpointMutationResponse,
    EnzanAlertEndpointUpdateRequest,
    EnzanAlertEvent,
    EnzanAlertMutationResponse,
    EnzanBurnResponse,
    EnzanChatResponse,
    EnzanCreateAlertRequest,
    EnzanGPUOffer,
    EnzanGPUOfferUpsertPayload,
    EnzanGPUPricing,
    EnzanGPUPricingMutationResponse,
    EnzanLLMOffer,
    EnzanLLMOfferUpsertPayload,
    EnzanLLMPricing,
    EnzanLLMPricingMutationResponse,
    EnzanModelCategoryBreakdown,
    EnzanModelCostResponse,
    EnzanModelCostRow,
    EnzanModelCostTotal,
    EnzanOptimizeResponse,
    EnzanPricingOfferUpsertResponse,
    EnzanPricingProvider,
    EnzanPricingRefreshLogEntry,
    EnzanPricingRefreshTriggerResponse,
    EnzanRecommendation,
    EnzanResource,
    EnzanRoutingConfig,
    EnzanRoutingConfigMutationResponse,
    EnzanRoutingSavingsBreakdown,
    EnzanRoutingSavingsResponse,
    EnzanSuggestedAction,
    EnzanSummaryResponse,
    EnzanSummaryRow,
    EnzanSummaryTotal,
    EnzanUpdateAlertRequest,
    StatusWithIDResponse,
)


class EnzanClient:
    """Client for Enzan (GPU Cost) API."""

    def __init__(self, http: HttpClient):
        self._http = http

    def summary(
        self,
        window: TimeWindow = "24h",
        group_by: list[GroupByDimension] | None = None,
        filters: dict[str, list[str]] | None = None,
    ) -> EnzanSummaryResponse:
        payload: dict[str, Any] = {"window": window}
        if group_by:
            payload["groupBy"] = group_by
        if filters:
            payload["filters"] = filters

        result = self._http.post("/v1/enzan/summary", payload)
        rows = [
            EnzanSummaryRow(
                cost_usd=row.get("cost_usd", 0),
                gpu_hours=row.get("gpu_hours", 0),
                requests=row.get("requests", 0),
                tokens_in=row.get("tokens_in", 0),
                tokens_out=row.get("tokens_out", 0),
                project=row.get("project"),
                model=row.get("model"),
                team=row.get("team"),
                provider=row.get("provider"),
                endpoint=row.get("endpoint"),
                avg_util_pct=row.get("avg_util_pct"),
            )
            for row in result.get("rows", [])
        ]
        total = result.get("total", {})
        raw_api_costs = result.get("apiCosts")
        api_costs = (
            APICostSummary(
                total_cost_usd=raw_api_costs.get("totalCostUsd", 0),
                prompt_tokens=raw_api_costs.get("promptTokens", 0),
                output_tokens=raw_api_costs.get("outputTokens", 0),
                queries=raw_api_costs.get("queries", 0),
            )
            if isinstance(raw_api_costs, dict)
            else None
        )

        return EnzanSummaryResponse(
            window=result.get("window", window),
            start_time=result.get("startTime", ""),
            end_time=result.get("endTime", ""),
            rows=rows,
            total=EnzanSummaryTotal(
                cost_usd=total.get("cost_usd", 0),
                gpu_hours=total.get("gpu_hours", 0),
                requests=total.get("requests", 0),
                tokens_in=total.get("tokens_in", 0),
                tokens_out=total.get("tokens_out", 0),
            ),
            api_costs=api_costs,
        )

    def costs_by_model(self, window: TimeWindow = "30d") -> EnzanModelCostResponse:
        result = self._http.post("/v1/enzan/costs/by-model", {"window": window})

        rows = []
        for row in result.get("rows", []):
            categories = [
                EnzanModelCategoryBreakdown(
                    category=category.get("category", "moderate"),
                    queries=category.get("queries", 0),
                    prompt_tokens=category.get("prompt_tokens", 0),
                    output_tokens=category.get("output_tokens", 0),
                    cost_usd=category.get("cost_usd", 0.0),
                    percentage=category.get("percentage", 0.0),
                    avg_cost_per_query=category.get("avg_cost_per_query", 0.0),
                )
                for category in row.get("categories", [])
            ]
            rows.append(
                EnzanModelCostRow(
                    model=row.get("model", "unknown"),
                    queries=row.get("queries", 0),
                    prompt_tokens=row.get("prompt_tokens", 0),
                    output_tokens=row.get("output_tokens", 0),
                    cost_usd=row.get("cost_usd", 0.0),
                    percentage=row.get("percentage", 0.0),
                    avg_cost_per_query=row.get("avg_cost_per_query", 0.0),
                    categories=categories or None,
                )
            )

        total = result.get("total", {})
        return EnzanModelCostResponse(
            window=result.get("window", window),
            start_time=result.get("startTime", ""),
            end_time=result.get("endTime", ""),
            rows=rows,
            total=EnzanModelCostTotal(
                queries=total.get("queries", 0),
                prompt_tokens=total.get("prompt_tokens", 0),
                output_tokens=total.get("output_tokens", 0),
                cost_usd=total.get("cost_usd", 0.0),
            ),
        )

    def list_model_pricing(self) -> list[EnzanLLMPricing]:
        result = self._http.get("/v1/enzan/pricing/models")
        return [
            EnzanLLMPricing(
                provider=row.get("provider", ""),
                model=row.get("model", ""),
                display_name=row.get("display_name", ""),
                input_cost_per_1k_tokens_usd=row.get("input_cost_per_1k_tokens_usd", 0.0),
                output_cost_per_1k_tokens_usd=row.get("output_cost_per_1k_tokens_usd", 0.0),
                currency=row.get("currency", "USD"),
                active=row.get("active", True),
            )
            for row in result.get("models", [])
        ]

    def upsert_model_pricing(
        self,
        *,
        provider: str,
        model: str,
        input_cost_per_1k_tokens_usd: float,
        output_cost_per_1k_tokens_usd: float,
        display_name: str | None = None,
        currency: str | None = None,
        active: bool | None = None,
    ) -> EnzanLLMPricingMutationResponse:
        payload: dict[str, Any] = {
            "provider": provider,
            "model": model,
            "input_cost_per_1k_tokens_usd": input_cost_per_1k_tokens_usd,
            "output_cost_per_1k_tokens_usd": output_cost_per_1k_tokens_usd,
        }
        if display_name is not None:
            payload["display_name"] = display_name
        if currency is not None:
            payload["currency"] = currency
        if active is not None:
            payload["active"] = active

        result = self._http.post("/v1/enzan/pricing/models", payload)
        pricing = result.get("pricing", {})
        return EnzanLLMPricingMutationResponse(
            status=result.get("status", "upserted"),
            pricing=EnzanLLMPricing(
                provider=pricing.get("provider", ""),
                model=pricing.get("model", ""),
                display_name=pricing.get("display_name", ""),
                input_cost_per_1k_tokens_usd=pricing.get("input_cost_per_1k_tokens_usd", 0.0),
                output_cost_per_1k_tokens_usd=pricing.get("output_cost_per_1k_tokens_usd", 0.0),
                currency=pricing.get("currency", "USD"),
                active=pricing.get("active", True),
            ),
        )

    def list_gpu_pricing(self) -> list[EnzanGPUPricing]:
        result = self._http.get("/v1/enzan/pricing/gpus")
        return [
            EnzanGPUPricing(
                provider=row.get("provider", ""),
                gpu_type=row.get("gpu_type", ""),
                display_name=row.get("display_name", ""),
                hourly_rate_usd=row.get("hourly_rate_usd", 0.0),
                currency=row.get("currency", "USD"),
                active=row.get("active", True),
            )
            for row in result.get("gpus", [])
        ]

    def upsert_gpu_pricing(
        self,
        *,
        provider: str,
        gpu_type: str,
        hourly_rate_usd: float,
        display_name: str | None = None,
        currency: str | None = None,
        active: bool | None = None,
    ) -> EnzanGPUPricingMutationResponse:
        payload: dict[str, Any] = {
            "provider": provider,
            "gpu_type": gpu_type,
            "hourly_rate_usd": hourly_rate_usd,
        }
        if display_name is not None:
            payload["display_name"] = display_name
        if currency is not None:
            payload["currency"] = currency
        if active is not None:
            payload["active"] = active

        result = self._http.post("/v1/enzan/pricing/gpus", payload)
        pricing = result.get("pricing", {})
        return EnzanGPUPricingMutationResponse(
            status=result.get("status", "upserted"),
            pricing=EnzanGPUPricing(
                provider=pricing.get("provider", ""),
                gpu_type=pricing.get("gpu_type", ""),
                display_name=pricing.get("display_name", ""),
                hourly_rate_usd=pricing.get("hourly_rate_usd", 0.0),
                currency=pricing.get("currency", "USD"),
                active=pricing.get("active", True),
            ),
        )

    def trigger_pricing_refresh(self) -> EnzanPricingRefreshTriggerResponse:
        """Trigger an on-demand live-pricing refresh sweep (admin only).

        Fire-and-forget: returns immediately. Poll list_pricing_refresh_log()
        for completion status. Returns status="queued" on HTTP 202; HTTP 429
        (concurrency cap) is surfaced as KaizenRateLimitError with the typed
        body in err.data.

        Both response fields are required and non-nullable per the OpenAPI
        spec — uses _required to surface contract drift consistently with
        the offer / refresh-log / providers mappers, rather than silently
        defaulting to empty strings.
        """

        result = self._http.post("/v1/enzan/pricing/refresh", {})
        return EnzanPricingRefreshTriggerResponse(
            status=_required(result, "status", "refresh_trigger"),
            triggered_by=_required(result, "triggeredBy", "refresh_trigger"),
        )

    def list_pricing_refresh_log(
        self, limit: int | None = None
    ) -> list[EnzanPricingRefreshLogEntry]:
        """List recent live-pricing refresh log entries (admin only).

        Server default is 50 entries; server clamps `limit` to 1..200 and
        rejects non-positive values with 400. Pass None to use the server
        default; pass a value to forward verbatim (including 0 and
        negative — those will hit server-side validation rather than being
        silently dropped client-side).
        """

        path = "/v1/enzan/pricing/refresh/log"
        if limit is not None:
            path = f"{path}?limit={limit}"
        result = self._http.get(path)
        # Required fields use _required so server contract drift surfaces
        # as KaizenError rather than empty/zero defaults that propagate
        # silently through callers. Nullable optional fields (sourceId,
        # sourceName, triggeredBy, durationMs, error, finishedAt) use
        # .get() since the OpenAPI spec marks them nullable.
        return [
            EnzanPricingRefreshLogEntry(
                id=_required(row, "id", "refresh_log_entry"),
                kind=_required(row, "kind", "refresh_log_entry"),
                status=_required(row, "status", "refresh_log_entry"),
                rows_upserted=_required(row, "rowsUpserted", "refresh_log_entry"),
                rows_skipped=_required(row, "rowsSkipped", "refresh_log_entry"),
                started_at=_required(row, "startedAt", "refresh_log_entry"),
                source_id=row.get("sourceId"),
                source_name=row.get("sourceName"),
                triggered_by=row.get("triggeredBy"),
                duration_ms=row.get("durationMs"),
                error=row.get("error"),
                finished_at=row.get("finishedAt"),
            )
            for row in result.get("entries", [])
        ]

    def list_pricing_providers(self) -> list[EnzanPricingProvider]:
        """List registered live-pricing sources (admin view).

        Required fields use _required so server contract drift surfaces as
        KaizenError rather than silently producing providers with empty
        identifiers or `enabled=False` / `has_adapter=False` defaults that
        could mislead an operator. Matches the strictness applied to log
        entries and offer responses.
        """

        result = self._http.get("/v1/enzan/pricing/providers")
        return [
            EnzanPricingProvider(
                id=_required(row, "id", "provider"),
                name=_required(row, "name", "provider"),
                kind=_required(row, "kind", "provider"),
                enabled=_required(row, "enabled", "provider"),
                refresh_interval_hours=_required(row, "refreshIntervalHours", "provider"),
                has_adapter=_required(row, "hasAdapter", "provider"),
                last_success_at=row.get("lastSuccessAt"),
                last_failure_at=row.get("lastFailureAt"),
                last_error=row.get("lastError"),
            )
            for row in result.get("providers", [])
        ]

    def upsert_pricing_offer(
        self,
        *,
        gpu: EnzanGPUOfferUpsertPayload | None = None,
        llm: EnzanLLMOfferUpsertPayload | None = None,
    ) -> EnzanPricingOfferUpsertResponse:
        """Upsert one manual (admin-authored) live-pricing offer.

        Exactly one of `gpu` or `llm` must be provided. Returns status="upserted"
        (HTTP 201) on success or status="stale" (HTTP 409) when a newer
        fetched_at row exists for the same key.

        Client-side validation rejects empty string identifiers (provider,
        gpu_type/model, display_name) and missing/non-finite/wrong-type rate
        values (None, NaN, Infinity, non-numeric) before hitting the wire;
        explicit zero is preserved as a free offer. The server remains the
        authority on rate semantics beyond finiteness (e.g. domain-specific
        bounds).
        """

        if (gpu is None) == (llm is None):
            raise ValueError("exactly one of gpu or llm must be set")
        # Type-check the branch payload itself before reading attributes —
        # plain Python callers can pass a dict or a primitive instead of
        # the dataclass, which would otherwise AttributeError on .provider.
        if gpu is not None and not isinstance(gpu, EnzanGPUOfferUpsertPayload):
            raise ValueError("gpu must be an EnzanGPUOfferUpsertPayload")
        if llm is not None and not isinstance(llm, EnzanLLMOfferUpsertPayload):
            raise ValueError("llm must be an EnzanLLMOfferUpsertPayload")

        # isinstance + strip() — dataclasses don't enforce types at runtime,
        # so None or wrong-type values would AttributeError on a bare strip().
        # The validation surface should reject those as ValueError, not crash.
        def _require_string(value: Any, label: str) -> None:
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{label} is required")

        # Rate fields are validated for finite numeric type so wire payloads
        # can never silently carry `null`, wrong-type, NaN, or Infinity
        # values that would otherwise reach the server unchecked. Explicit
        # zero is allowed (matches Go's Float64Ptr(0) free-offer convention
        # and TS's Number.isFinite check). bool excluded because Python
        # treats bools as ints. Distinct messages so debugging a NaN
        # submission doesn't send the caller hunting for a missing field.
        def _require_number(value: Any, label: str) -> None:
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(f"{label} is required")
            if not math.isfinite(value):
                raise ValueError(f"{label} must be a finite number")

        payload: dict[str, Any] = {}
        if gpu is not None:
            _require_string(gpu.provider, "gpu.provider")
            _require_string(gpu.gpu_type, "gpu.gpu_type")
            _require_string(gpu.display_name, "gpu.display_name")
            _require_number(gpu.hourly_rate_usd, "gpu.hourly_rate_usd")
            payload["gpu"] = _gpu_offer_payload_dict(gpu)
        else:
            assert llm is not None
            _require_string(llm.provider, "llm.provider")
            _require_string(llm.model, "llm.model")
            _require_string(llm.display_name, "llm.display_name")
            _require_number(llm.input_cost_per_1k_tokens_usd, "llm.input_cost_per_1k_tokens_usd")
            _require_number(llm.output_cost_per_1k_tokens_usd, "llm.output_cost_per_1k_tokens_usd")
            payload["llm"] = _llm_offer_payload_dict(llm)
        result = self._http.post("/v1/enzan/pricing/offers", payload)
        gpu_row = result.get("gpu")
        llm_row = result.get("llm")
        # Status passes through verbatim. HTTP 409 (stale write) is surfaced
        # by the http client as KaizenError with the typed body in err.data,
        # so this success-path code is only reached for HTTP 201 responses.
        return EnzanPricingOfferUpsertResponse(
            status=result.get("status", ""),
            gpu=_gpu_offer_from_dict(gpu_row) if gpu_row else None,
            llm=_llm_offer_from_dict(llm_row) if llm_row else None,
        )

    def burn(self) -> EnzanBurnResponse:
        result = self._http.get("/v1/enzan/burn")
        return EnzanBurnResponse(
            burn_rate_usd_per_hour=result.get("burn_rate_usd_per_hour", 0.0),
            timestamp=result.get("timestamp", ""),
        )

    def list_resources(self) -> list[EnzanResource]:
        result = self._http.get("/v1/enzan/resources")
        return [
            EnzanResource(
                id=resource["id"],
                provider=resource["provider"],
                gpu_type=resource["gpuType"],
                gpu_count=resource["gpuCount"],
                hourly_rate=resource["hourlyRate"],
                region=resource.get("region"),
                endpoint=resource.get("endpoint"),
                labels=resource.get("labels"),
                created_at=resource.get("createdAt"),
                last_seen_at=resource.get("lastSeenAt"),
            )
            for resource in result.get("resources", [])
        ]

    def register_resource(self, resource: EnzanResource) -> dict[str, str]:
        payload = {
            "id": resource.id,
            "provider": resource.provider,
            "gpuType": resource.gpu_type,
            "gpuCount": resource.gpu_count,
            "hourlyRate": resource.hourly_rate,
        }
        if resource.region:
            payload["region"] = resource.region
        if resource.endpoint:
            payload["endpoint"] = resource.endpoint
        if resource.labels:
            payload["labels"] = resource.labels
        return cast(dict[str, str], self._http.post("/v1/enzan/resources", payload))

    def list_alerts(self) -> list[EnzanAlert]:
        result = self._http.get("/v1/enzan/alerts")
        return [
            EnzanAlert(
                id=alert["id"],
                name=alert["name"],
                type=alert["type"],
                threshold=alert["threshold"],
                window=alert["window"],
                labels=alert.get("labels"),
                enabled=alert.get("enabled", True),
                evaluation_state=alert.get("evaluationState"),
                next_eligible_at=alert.get("nextEligibleAt"),
                status_reason=alert.get("statusReason"),
            )
            for alert in result.get("alerts", [])
        ]

    def routing(self) -> EnzanRoutingConfig:
        result = self._http.get("/v1/enzan/routing")
        routing = result.get("routing", {})
        return EnzanRoutingConfig(
            enabled=routing.get("enabled", False),
            provider=routing.get("provider", ""),
            default_model=routing.get("default_model", ""),
            simple_model=routing.get("simple_model"),
            moderate_model=routing.get("moderate_model"),
            complex_model=routing.get("complex_model"),
            updated_at=routing.get("updated_at"),
        )

    def set_routing(
        self,
        *,
        enabled: bool,
        simple_model: str | None = None,
        moderate_model: str | None = None,
        complex_model: str | None = None,
    ) -> EnzanRoutingConfigMutationResponse:
        payload: dict[str, Any] = {"enabled": enabled}
        if simple_model is not None:
            payload["simple_model"] = simple_model
        if moderate_model is not None:
            payload["moderate_model"] = moderate_model
        if complex_model is not None:
            payload["complex_model"] = complex_model
        result = self._http.post("/v1/enzan/routing", payload)
        routing = result.get("routing", {})
        return EnzanRoutingConfigMutationResponse(
            status=result.get("status", "upserted"),
            routing=EnzanRoutingConfig(
                enabled=routing.get("enabled", False),
                provider=routing.get("provider", ""),
                default_model=routing.get("default_model", ""),
                simple_model=routing.get("simple_model"),
                moderate_model=routing.get("moderate_model"),
                complex_model=routing.get("complex_model"),
                updated_at=routing.get("updated_at"),
            ),
        )

    def routing_savings(self, window: TimeWindow = "30d") -> EnzanRoutingSavingsResponse:
        path = (
            f"/v1/enzan/routing/savings?window={window}"
            if window
            else "/v1/enzan/routing/savings"
        )
        result = self._http.get(path)
        breakdown = [
            EnzanRoutingSavingsBreakdown(
                prompt_category=row.get("prompt_category", ""),
                original_model=row.get("original_model", ""),
                routed_model=row.get("routed_model", ""),
                queries=row.get("queries", 0),
                actual_cost_usd=row.get("actual_cost_usd", 0.0),
                counterfactual_cost_usd=row.get("counterfactual_cost_usd", 0.0),
                estimated_savings_usd=row.get("estimated_savings_usd", 0.0),
            )
            for row in result.get("breakdown", [])
        ]
        return EnzanRoutingSavingsResponse(
            window=result.get("window", window),
            start_time=result.get("start_time", ""),
            end_time=result.get("end_time", ""),
            provider=result.get("provider", ""),
            default_model=result.get("default_model", ""),
            total_queries=result.get("total_queries", 0),
            routed_queries=result.get("routed_queries", 0),
            actual_cost_usd=result.get("actual_cost_usd", 0.0),
            counterfactual_cost_usd=result.get("counterfactual_cost_usd", 0.0),
            estimated_savings_usd=result.get("estimated_savings_usd", 0.0),
            breakdown=breakdown,
        )

    def list_alert_endpoints(self) -> list[EnzanAlertEndpoint]:
        result = self._http.get("/v1/enzan/alerts/endpoints")
        return [
            EnzanAlertEndpoint(
                id=endpoint.get("id", ""),
                kind=endpoint.get("kind", "webhook"),
                target_url=endpoint.get("targetUrl", ""),
                has_signing_secret=endpoint.get("hasSigningSecret", False),
                enabled=endpoint.get("enabled", True),
                last_used_at=endpoint.get("lastUsedAt"),
                created_at=endpoint.get("createdAt", ""),
                updated_at=endpoint.get("updatedAt", ""),
            )
            for endpoint in result.get("endpoints", [])
        ]

    def list_alert_events(self, limit: int | None = None) -> list[EnzanAlertEvent]:
        path = "/v1/enzan/alerts/events"
        if limit is not None and limit > 0:
            path = f"{path}?limit={limit}"
        result = self._http.get(path)
        return [
            EnzanAlertEvent(
                id=event.get("id", ""),
                rule_id=event.get("ruleId"),
                type=event.get("type", ""),
                dedupe_key=event.get("dedupeKey", ""),
                payload=event.get("payload", {}),
                triggered_at=event.get("triggeredAt", ""),
            )
            for event in result.get("events", [])
        ]

    def list_alert_deliveries(self, limit: int | None = None) -> list[EnzanAlertDelivery]:
        path = "/v1/enzan/alerts/deliveries"
        if limit is not None and limit > 0:
            path = f"{path}?limit={limit}"
        result = self._http.get(path)
        return [
            EnzanAlertDelivery(
                id=delivery.get("id", ""),
                event_id=delivery.get("eventId", ""),
                endpoint_id=delivery.get("endpointId"),
                status=delivery.get("status", "pending"),
                retry_count=delivery.get("retryCount", 0),
                next_retry_at=delivery.get("nextRetryAt", ""),
                last_attempted_at=delivery.get("lastAttemptedAt"),
                last_response_code=delivery.get("lastResponseCode"),
                last_error=delivery.get("lastError"),
                created_at=delivery.get("createdAt", ""),
                updated_at=delivery.get("updatedAt", ""),
            )
            for delivery in result.get("deliveries", [])
        ]

    def optimize(self, window: TimeWindow = "30d") -> EnzanOptimizeResponse:
        """Generate cost optimization recommendations."""
        result = self._http.post("/v1/enzan/optimize", {"window": window})
        recs = [
            EnzanRecommendation(
                type=r.get("type", ""),
                title=r.get("title", ""),
                description=r.get("description", ""),
                estimated_savings=r.get("estimatedSavings", 0.0),
                confidence=r.get("confidence", 0.0),
                suggestion=r.get("suggestion", ""),
            )
            for r in result.get("recommendations", [])
        ]
        return EnzanOptimizeResponse(
            window=result.get("window", window),
            start_time=result.get("startTime", ""),
            end_time=result.get("endTime", ""),
            efficiency_score=result.get("efficiencyScore", 100),
            monthly_spend=result.get("monthlySpend", 0.0),
            potential_savings=result.get("potentialSavings", 0.0),
            recommendations=recs,
        )

    def chat(
        self,
        message: str,
        conversation_id: str | None = None,
        window: str | None = None,
    ) -> EnzanChatResponse:
        """Conversational AI cost Q&A with multi-turn support."""

        payload: dict[str, Any] = {"message": message}
        if conversation_id:
            payload["conversationId"] = conversation_id
        if window:
            payload["window"] = window

        result = self._http.post("/v1/enzan/chat", payload)
        actions = [
            EnzanSuggestedAction(
                type=a.get("type", ""),
                label=a.get("label", ""),
                window=a.get("window"),
                model=a.get("model"),
            )
            for a in result.get("suggestedActions", [])
        ]
        return EnzanChatResponse(
            conversation_id=result.get("conversationId", ""),
            message=result.get("message", ""),
            effective_window=result.get("effectiveWindow"),
            suggested_actions=actions,
            supporting_data=result.get("supportingData"),
        )

    def create_alert(self, alert: EnzanCreateAlertRequest) -> StatusWithIDResponse:
        if alert.type == "cost_threshold":
            if alert.threshold is None:
                raise ValueError("threshold is required for alert type cost_threshold")
            if not alert.window.strip():
                raise ValueError("window is required for alert type cost_threshold")
        elif alert.type == "cost_anomaly":
            if alert.threshold is None:
                raise ValueError("threshold is required for alert type cost_anomaly")
            try:
                threshold_decimal = Decimal(str(alert.threshold))
            except InvalidOperation as exc:
                raise ValueError(
                    "threshold must be a valid decimal for alert type cost_anomaly"
                ) from exc
            if not threshold_decimal.is_finite():
                raise ValueError("threshold must be a valid decimal for alert type cost_anomaly")
            if threshold_decimal <= 0:
                raise ValueError("threshold must be greater than 0 for alert type cost_anomaly")
            if threshold_decimal > Decimal("10000"):
                raise ValueError(
                    "threshold must be less than or equal to 10000 for alert type cost_anomaly"
                )
            exponent = threshold_decimal.as_tuple().exponent
            if isinstance(exponent, int) and exponent < -2:
                raise ValueError(
                    "threshold must use at most two decimal places for alert type cost_anomaly"
                )
            if not alert.window.strip():
                raise ValueError("window is required for alert type cost_anomaly")
            if alert.window.strip() == "1h":
                raise ValueError("window must be 24h, 7d, or 30d for alert type cost_anomaly")
        elif alert.type == "budget_exceeded" and alert.threshold is None:
            raise ValueError("threshold is required for alert type budget_exceeded")
        elif (
            alert.type == "daily_summary"
            and alert.window.strip()
            and alert.window.strip() != "24h"
        ):
            raise ValueError("window must be 24h for alert type daily_summary")
        payload: dict[str, Any] = {
            "name": alert.name,
            "type": alert.type,
        }
        if alert.id:
            payload["id"] = alert.id
        if alert.threshold is not None:
            payload["threshold"] = alert.threshold
        if alert.window:
            payload["window"] = alert.window
        if alert.labels is not None:
            payload["labels"] = alert.labels
        if alert.enabled is not None:
            payload["enabled"] = alert.enabled
        result = self._http.post("/v1/enzan/alerts", payload)
        return StatusWithIDResponse(
            status=result.get("status", "created"),
            id=result.get("id", ""),
        )

    def update_alert(
        self,
        alert_id: str,
        alert: EnzanUpdateAlertRequest,
    ) -> EnzanAlertMutationResponse:
        payload: dict[str, Any] = {}
        if alert.name is not None:
            payload["name"] = alert.name
        if alert.threshold is not None:
            payload["threshold"] = alert.threshold
        if alert.window is not None:
            payload["window"] = alert.window
        if alert.labels is not None:
            payload["labels"] = alert.labels
        if alert.enabled is not None:
            payload["enabled"] = alert.enabled
        path = f"/v1/enzan/alerts/{quote(alert_id, safe='')}"
        result = self._http.request("PATCH", path, payload)
        raw_alert = result.get("alert", {})
        return EnzanAlertMutationResponse(
            status=result.get("status", "updated"),
            alert=EnzanAlert(
                id=raw_alert.get("id", ""),
                name=raw_alert.get("name", ""),
                type=raw_alert.get("type", "cost_threshold"),
                threshold=raw_alert.get("threshold", 0.0),
                window=raw_alert.get("window", ""),
                labels=raw_alert.get("labels"),
                enabled=raw_alert.get("enabled", True),
                evaluation_state=raw_alert.get("evaluationState"),
                next_eligible_at=raw_alert.get("nextEligibleAt"),
                status_reason=raw_alert.get("statusReason"),
            ),
        )

    def delete_alert(self, alert_id: str) -> dict[str, str]:
        path = f"/v1/enzan/alerts/{quote(alert_id, safe='')}"
        return cast(dict[str, str], self._http.request("DELETE", path))

    def create_alert_endpoint(
        self,
        *,
        target_url: str,
        signing_secret: str | None = None,
    ) -> EnzanAlertEndpointMutationResponse:
        payload: dict[str, Any] = {"targetUrl": target_url}
        if signing_secret is not None:
            payload["signingSecret"] = signing_secret
        result = self._http.post("/v1/enzan/alerts/endpoints", payload)
        endpoint = result.get("endpoint", {})
        return EnzanAlertEndpointMutationResponse(
            status=result.get("status", "created"),
            endpoint=EnzanAlertEndpoint(
                id=endpoint.get("id", ""),
                kind=endpoint.get("kind", "webhook"),
                target_url=endpoint.get("targetUrl", ""),
                has_signing_secret=endpoint.get("hasSigningSecret", False),
                enabled=endpoint.get("enabled", True),
                last_used_at=endpoint.get("lastUsedAt"),
                created_at=endpoint.get("createdAt", ""),
                updated_at=endpoint.get("updatedAt", ""),
            ),
        )

    def update_alert_endpoint(
        self,
        endpoint_id: str,
        req: EnzanAlertEndpointUpdateRequest,
    ) -> EnzanAlertEndpointMutationResponse:
        payload: dict[str, Any] = {}
        if req.target_url is not None:
            payload["targetUrl"] = req.target_url
        if req.signing_secret is not None:
            payload["signingSecret"] = req.signing_secret
        if req.enabled is not None:
            payload["enabled"] = req.enabled
        path = f"/v1/enzan/alerts/endpoints/{quote(endpoint_id, safe='')}"
        result = self._http.request("PATCH", path, payload)
        endpoint = result.get("endpoint", {})
        return EnzanAlertEndpointMutationResponse(
            status=result.get("status", "updated"),
            endpoint=EnzanAlertEndpoint(
                id=endpoint.get("id", ""),
                kind=endpoint.get("kind", "webhook"),
                target_url=endpoint.get("targetUrl", ""),
                has_signing_secret=endpoint.get("hasSigningSecret", False),
                enabled=endpoint.get("enabled", True),
                last_used_at=endpoint.get("lastUsedAt"),
                created_at=endpoint.get("createdAt", ""),
                updated_at=endpoint.get("updatedAt", ""),
            ),
        )

    def delete_alert_endpoint(self, endpoint_id: str) -> dict[str, str]:
        path = f"/v1/enzan/alerts/endpoints/{quote(endpoint_id, safe='')}"
        return cast(dict[str, str], self._http.request("DELETE", path))


def _gpu_offer_payload_dict(p: EnzanGPUOfferUpsertPayload) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "provider": p.provider,
        "gpuType": p.gpu_type,
        "displayName": p.display_name,
        "hourlyRateUSD": p.hourly_rate_usd,
    }
    if p.region is not None:
        payload["region"] = p.region
    if p.deployment_class is not None:
        payload["deploymentClass"] = p.deployment_class
    if p.commitment_term is not None:
        payload["commitmentTerm"] = p.commitment_term
    if p.cluster_size_min is not None:
        payload["clusterSizeMin"] = p.cluster_size_min
    if p.cluster_size_max is not None:
        payload["clusterSizeMax"] = p.cluster_size_max
    if p.interconnect_class is not None:
        payload["interconnectClass"] = p.interconnect_class
    if p.training_ready is not None:
        payload["trainingReady"] = p.training_ready
    if p.currency is not None:
        payload["currency"] = p.currency
    if p.currency_fx_note is not None:
        payload["currencyFxNote"] = p.currency_fx_note
    if p.source_url is not None:
        payload["sourceUrl"] = p.source_url
    return payload


def _llm_offer_payload_dict(p: EnzanLLMOfferUpsertPayload) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "provider": p.provider,
        "model": p.model,
        "displayName": p.display_name,
        "inputCostPer1KTokensUSD": p.input_cost_per_1k_tokens_usd,
        "outputCostPer1KTokensUSD": p.output_cost_per_1k_tokens_usd,
    }
    if p.region is not None:
        payload["region"] = p.region
    if p.commitment_term is not None:
        payload["commitmentTerm"] = p.commitment_term
    if p.currency is not None:
        payload["currency"] = p.currency
    if p.currency_fx_note is not None:
        payload["currencyFxNote"] = p.currency_fx_note
    if p.source_url is not None:
        payload["sourceUrl"] = p.source_url
    return payload


def _required(row: dict[str, Any], key: str, container: str) -> Any:
    """Return row[key], raising KaizenError if missing or null.

    Used for offer-response fields documented as `required` and
    non-nullable in OpenAPI. Both omission and explicit `null` are
    contract violations on these fields — defaulting either to
    USD/0/False would silently mask server drift on an admin pricing API.
    """

    value = row.get(key, _MISSING)
    if value is _MISSING or value is None:
        from ..errors import KaizenError

        raise KaizenError(
            f"server response is missing required field {container}.{key}",
            data={"container": container, "missing_field": key, "received": row},
        )
    return value


_MISSING: Any = object()


def _gpu_offer_from_dict(row: dict[str, Any]) -> EnzanGPUOffer:
    return EnzanGPUOffer(
        id=_required(row, "id", "gpu"),
        provider=_required(row, "provider", "gpu"),
        gpu_type=_required(row, "gpuType", "gpu"),
        display_name=_required(row, "displayName", "gpu"),
        deployment_class=_required(row, "deploymentClass", "gpu"),
        cluster_size_min=_required(row, "clusterSizeMin", "gpu"),
        interconnect_class=_required(row, "interconnectClass", "gpu"),
        training_ready=_required(row, "trainingReady", "gpu"),
        hourly_rate_usd=_required(row, "hourlyRateUSD", "gpu"),
        currency=_required(row, "currency", "gpu"),
        source_type=_required(row, "sourceType", "gpu"),
        trust_status=_required(row, "trustStatus", "gpu"),
        fetched_at=_required(row, "fetchedAt", "gpu"),
        first_seen_at=_required(row, "firstSeenAt", "gpu"),
        last_seen_at=_required(row, "lastSeenAt", "gpu"),
        active=_required(row, "active", "gpu"),
        region=row.get("region"),
        commitment_term=row.get("commitmentTerm"),
        cluster_size_max=row.get("clusterSizeMax"),
        currency_fx_note=row.get("currencyFxNote"),
        source_id=row.get("sourceId"),
        source_url=row.get("sourceUrl"),
        source_fingerprint=row.get("sourceFingerprint"),
    )


def _llm_offer_from_dict(row: dict[str, Any]) -> EnzanLLMOffer:
    return EnzanLLMOffer(
        id=_required(row, "id", "llm"),
        provider=_required(row, "provider", "llm"),
        model=_required(row, "model", "llm"),
        display_name=_required(row, "displayName", "llm"),
        input_cost_per_1k_tokens_usd=_required(row, "inputCostPer1KTokensUSD", "llm"),
        output_cost_per_1k_tokens_usd=_required(row, "outputCostPer1KTokensUSD", "llm"),
        currency=_required(row, "currency", "llm"),
        source_type=_required(row, "sourceType", "llm"),
        trust_status=_required(row, "trustStatus", "llm"),
        fetched_at=_required(row, "fetchedAt", "llm"),
        first_seen_at=_required(row, "firstSeenAt", "llm"),
        last_seen_at=_required(row, "lastSeenAt", "llm"),
        active=_required(row, "active", "llm"),
        region=row.get("region"),
        commitment_term=row.get("commitmentTerm"),
        currency_fx_note=row.get("currencyFxNote"),
        source_id=row.get("sourceId"),
        source_url=row.get("sourceUrl"),
        source_fingerprint=row.get("sourceFingerprint"),
    )
