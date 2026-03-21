from __future__ import annotations

from typing import Any

from .._types import GroupByDimension, TimeWindow
from ..http import HttpClient
from ..models import (
    APICostSummary,
    EnzanAlert,
    EnzanBurnResponse,
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
    EnzanSummaryResponse,
    EnzanSummaryRow,
    EnzanSummaryTotal,
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
        return self._http.post("/v1/enzan/resources", payload)

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
            )
            for alert in result.get("alerts", [])
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

    def create_alert(self, alert: EnzanAlert) -> dict[str, str]:
        return self._http.post(
            "/v1/enzan/alerts",
            {
                "id": alert.id,
                "name": alert.name,
                "type": alert.type,
                "threshold": alert.threshold,
                "window": alert.window,
                "labels": alert.labels,
                "enabled": alert.enabled,
            },
        )
