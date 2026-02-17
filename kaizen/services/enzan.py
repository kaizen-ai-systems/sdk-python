from __future__ import annotations

from typing import Any

from .._types import GroupByDimension, TimeWindow
from ..http import HttpClient
from ..models import (
    EnzanAlert,
    EnzanBurnResponse,
    EnzanResource,
    EnzanSummaryResponse,
    EnzanSummaryRow,
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
            )
            for row in result.get("rows", [])
        ]
        total = result.get("total", {})

        return EnzanSummaryResponse(
            window=result.get("window", window),
            start_time=result.get("startTime", ""),
            end_time=result.get("endTime", ""),
            rows=rows,
            total_cost_usd=total.get("cost_usd", 0),
            total_gpu_hours=total.get("gpu_hours", 0),
            total_requests=total.get("requests", 0),
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
                labels=resource.get("labels"),
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
                enabled=alert.get("enabled", True),
            )
            for alert in result.get("alerts", [])
        ]

    def create_alert(self, alert: EnzanAlert) -> dict[str, str]:
        return self._http.post(
            "/v1/enzan/alerts",
            {
                "id": alert.id,
                "name": alert.name,
                "type": alert.type,
                "threshold": alert.threshold,
                "window": alert.window,
                "enabled": alert.enabled,
            },
        )
