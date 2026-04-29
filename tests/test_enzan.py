from typing import Any, cast

import pytest

from kaizen.errors import KaizenError, KaizenRateLimitError
from kaizen.models import (
    EnzanAlertEndpointUpdateRequest,
    EnzanCreateAlertRequest,
    EnzanGPUOfferUpsertPayload,
    EnzanLLMOfferUpsertPayload,
    EnzanUpdateAlertRequest,
)
from kaizen.services.enzan import EnzanClient


class FakeHttp:
    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    def get(self, path):
        self.calls.append(("GET", path, None))
        return self.responses[path]

    def post(self, path, data):
        self.calls.append(("POST", path, data))
        return self.responses[path]

    def request(self, method, path, data=None):
        self.calls.append((method, path, data))
        return self.responses[(method, path)]


def test_enzan_summary_maps_api_costs_when_present():
    fake = FakeHttp(
        {
            "/v1/enzan/summary": {
                "window": "24h",
                "startTime": "2026-02-20T00:00:00Z",
                "endTime": "2026-02-20T23:59:59Z",
                "rows": [],
                "total": {"cost_usd": 0, "gpu_hours": 0, "requests": 0},
                "apiCosts": {
                    "totalCostUsd": 0.42,
                    "promptTokens": 1000,
                    "outputTokens": 200,
                    "queries": 5,
                },
            }
        }
    )
    client = EnzanClient(fake)
    summary = client.summary(window="24h")

    assert summary.api_costs is not None
    assert summary.api_costs.total_cost_usd == 0.42
    assert summary.api_costs.queries == 5


def test_enzan_summary_maps_api_costs_as_none_when_absent():
    fake = FakeHttp(
        {
            "/v1/enzan/summary": {
                "window": "24h",
                "startTime": "2026-02-20T00:00:00Z",
                "endTime": "2026-02-20T23:59:59Z",
                "rows": [],
                "total": {"cost_usd": 0, "gpu_hours": 0, "requests": 0},
            }
        }
    )
    client = EnzanClient(fake)
    summary = client.summary(window="24h")

    assert summary.api_costs is None


def test_enzan_optimize_maps_recommendations():
    fake = FakeHttp(
        {
            "/v1/enzan/optimize": {
                "window": "30d",
                "startTime": "2026-02-18T00:00:00Z",
                "endTime": "2026-03-20T00:00:00Z",
                "efficiencyScore": 72,
                "monthlySpend": 12500.0,
                "potentialSavings": 3200.0,
                "recommendations": [
                    {
                        "type": "self_host_breakeven",
                        "title": "Self-host gpt-4.1 on h100",
                        "description": "API spend on gpt-4.1 is ~$3200.00/mo; a h100 GPU costs ~$1452.70/mo",
                        "estimatedSavings": 1800.0,
                        "confidence": 0.5,
                        "suggestion": "Deploy gpt-4.1 on a aws/h100 instance",
                    },
                    {
                        "type": "model_downgrade",
                        "title": "Downgrade simple queries from gpt-4.1",
                        "description": "80% of queries are simple lookups.",
                        "estimatedSavings": 1400.0,
                        "confidence": 0.8,
                        "suggestion": "Route simple prompts to openai/gpt-4o-mini to save ~$1400.00",
                    },
                ],
            }
        }
    )
    client = EnzanClient(fake)
    response = client.optimize(window="30d")

    assert response.efficiency_score == 72
    assert response.monthly_spend == 12500.0
    assert response.potential_savings == 3200.0
    assert len(response.recommendations) == 2
    assert response.recommendations[0].type == "self_host_breakeven"
    assert response.recommendations[0].estimated_savings == 1800.0
    assert response.recommendations[1].confidence == 0.8


def test_enzan_optimize_handles_empty_recommendations():
    fake = FakeHttp(
        {
            "/v1/enzan/optimize": {
                "window": "30d",
                "startTime": "2026-02-18T00:00:00Z",
                "endTime": "2026-03-20T00:00:00Z",
                "efficiencyScore": 95,
                "monthlySpend": 500.0,
                "potentialSavings": 0.0,
                "recommendations": [],
            }
        }
    )
    client = EnzanClient(fake)
    response = client.optimize(window="30d")

    assert response.efficiency_score == 95
    assert response.recommendations == []


def test_enzan_costs_by_model_maps_nested_breakdowns():
    fake = FakeHttp(
        {
            "/v1/enzan/costs/by-model": {
                "window": "30d",
                "startTime": "2026-03-01T00:00:00Z",
                "endTime": "2026-03-30T23:59:59Z",
                "rows": [
                    {
                        "model": "gpt-4o-mini",
                        "queries": 12,
                        "prompt_tokens": 1200,
                        "output_tokens": 600,
                        "cost_usd": 3.5,
                        "percentage": 70,
                        "avg_cost_per_query": 0.291666,
                        "categories": [
                            {
                                "category": "simple",
                                "queries": 5,
                                "prompt_tokens": 300,
                                "output_tokens": 120,
                                "cost_usd": 0.9,
                                "percentage": 25.7,
                                "avg_cost_per_query": 0.18,
                            }
                        ],
                    }
                ],
                "total": {
                    "queries": 12,
                    "prompt_tokens": 1200,
                    "output_tokens": 600,
                    "cost_usd": 3.5,
                },
            }
        }
    )
    client = EnzanClient(fake)
    response = client.costs_by_model(window="30d")

    assert response.total.cost_usd == 3.5
    assert response.rows[0].model == "gpt-4o-mini"
    assert response.rows[0].categories is not None
    assert response.rows[0].categories[0].category == "simple"


def test_enzan_routing_maps_config_and_savings():
    fake = FakeHttp(
        {
            "/v1/enzan/routing": {
                "routing": {
                    "enabled": True,
                    "provider": "openai",
                    "default_model": "gpt-4.1",
                    "simple_model": "gpt-4o-mini",
                    "updated_at": "2026-04-16T12:00:00Z",
                }
            },
            "/v1/enzan/routing/savings?window=7d": {
                "window": "7d",
                "start_time": "2026-04-09T00:00:00Z",
                "end_time": "2026-04-16T00:00:00Z",
                "provider": "openai",
                "default_model": "gpt-4.1",
                "total_queries": 12,
                "routed_queries": 8,
                "actual_cost_usd": 1.2,
                "counterfactual_cost_usd": 2.4,
                "estimated_savings_usd": 1.2,
                "breakdown": [
                    {
                        "prompt_category": "simple",
                        "original_model": "gpt-4.1",
                        "routed_model": "gpt-4o-mini",
                        "queries": 8,
                        "actual_cost_usd": 1.2,
                        "counterfactual_cost_usd": 2.4,
                        "estimated_savings_usd": 1.2,
                    }
                ],
            },
        }
    )
    fake.responses["/v1/enzan/routing"] = {
        "status": "upserted",
        "routing": {
            "enabled": True,
            "provider": "openai",
            "default_model": "gpt-4.1",
            "simple_model": "gpt-4o-mini",
        },
    }
    client = EnzanClient(fake)

    mutation = client.set_routing(enabled=True, simple_model="gpt-4o-mini")
    fake.responses["/v1/enzan/routing"] = {
        "routing": {
            "enabled": True,
            "provider": "openai",
            "default_model": "gpt-4.1",
            "simple_model": "gpt-4o-mini",
            "updated_at": "2026-04-16T12:00:00Z",
        }
    }
    routing = client.routing()
    savings = client.routing_savings(window="7d")

    assert mutation.status == "upserted"
    assert routing.default_model == "gpt-4.1"
    assert routing.simple_model == "gpt-4o-mini"
    assert savings.routed_queries == 8
    assert savings.breakdown[0].prompt_category == "simple"


def test_enzan_alert_history_lists_events_and_deliveries():
    fake = FakeHttp(
        {
            "/v1/enzan/alerts/events?limit=25": {
                "events": [
                    {
                        "id": "event-1",
                        "ruleId": "rule-1",
                        "type": "cost_threshold",
                        "dedupeKey": "cost_threshold:rule-1:2026-04-04",
                        "payload": {"threshold": 10, "spend": 12.5},
                        "triggeredAt": "2026-04-04T12:00:00Z",
                    }
                ]
            },
            "/v1/enzan/alerts/deliveries?limit=10": {
                "deliveries": [
                    {
                        "id": "delivery-1",
                        "eventId": "event-1",
                        "endpointId": "endpoint-1",
                        "status": "sent",
                        "retryCount": 1,
                        "nextRetryAt": "2026-04-04T12:05:00Z",
                        "lastAttemptedAt": "2026-04-04T12:00:30Z",
                        "lastResponseCode": 202,
                        "createdAt": "2026-04-04T12:00:00Z",
                        "updatedAt": "2026-04-04T12:00:30Z",
                    }
                ]
            },
        }
    )
    client = EnzanClient(fake)

    events = client.list_alert_events(limit=25)
    deliveries = client.list_alert_deliveries(limit=10)

    assert events[0].rule_id == "rule-1"
    assert events[0].payload["threshold"] == 10
    assert deliveries[0].endpoint_id == "endpoint-1"
    assert deliveries[0].last_response_code == 202


def test_enzan_create_alert_returns_typed_response():
    fake = FakeHttp(
        {
            "/v1/enzan/alerts": {
                "status": "created",
                "id": "alert-1",
            }
        }
    )
    client = EnzanClient(fake)

    response = client.create_alert(
        EnzanCreateAlertRequest(
            name="High spend",
            type="cost_threshold",
            threshold=100.0,
            window="24h",
        )
    )

    assert response.status == "created"
    assert response.id == "alert-1"


def test_enzan_create_alert_requires_window_for_cost_threshold():
    fake = FakeHttp({})
    client = EnzanClient(fake)

    try:
        client.create_alert(
            EnzanCreateAlertRequest(
                name="High spend",
                type="cost_threshold",
                threshold=100.0,
            )
        )
    except ValueError as err:
        assert "window is required" in str(err)
    else:
        raise AssertionError("expected ValueError for missing window")


def test_enzan_create_alert_supports_cost_anomaly():
    fake = FakeHttp(
        {
            "/v1/enzan/alerts": {
                "status": "created",
                "id": "alert-anomaly",
            }
        }
    )
    client = EnzanClient(fake)

    response = client.create_alert(
            EnzanCreateAlertRequest(
                name="Spend anomaly",
                type="cost_anomaly",
                threshold=1.1,
                window="7d",
            )
        )

    assert response.id == "alert-anomaly"
    assert fake.calls[-1] == (
        "POST",
        "/v1/enzan/alerts",
        {
            "name": "Spend anomaly",
            "type": "cost_anomaly",
            "threshold": 1.1,
            "window": "7d",
        },
    )


def test_enzan_create_alert_rejects_one_hour_cost_anomaly_window():
    fake = FakeHttp({})
    client = EnzanClient(fake)

    try:
        client.create_alert(
            EnzanCreateAlertRequest(
                name="Spend anomaly",
                type="cost_anomaly",
                threshold=50.0,
                window="1h",
            )
        )
    except ValueError as err:
        assert "24h, 7d, or 30d" in str(err)
    else:
        raise AssertionError("expected ValueError for invalid cost_anomaly window")


def test_enzan_create_alert_rejects_zero_cost_anomaly_threshold():
    fake = FakeHttp({})
    client = EnzanClient(fake)

    try:
        client.create_alert(
            EnzanCreateAlertRequest(
                name="Spend anomaly",
                type="cost_anomaly",
                threshold=0.0,
                window="7d",
            )
        )
    except ValueError as err:
        assert "greater than 0" in str(err)
    else:
        raise AssertionError("expected ValueError for invalid cost_anomaly threshold")


def test_enzan_create_alert_allows_daily_summary_without_window():
    fake = FakeHttp(
        {
            "/v1/enzan/alerts": {
                "status": "created",
                "id": "alert-daily",
            }
        }
    )
    client = EnzanClient(fake)

    response = client.create_alert(
        EnzanCreateAlertRequest(
            name="Daily summary",
            type="daily_summary",
        )
    )

    assert response.id == "alert-daily"
    assert fake.calls[-1] == (
        "POST",
        "/v1/enzan/alerts",
        {
            "name": "Daily summary",
            "type": "daily_summary",
        },
    )


def test_enzan_create_alert_rejects_non_24h_daily_summary_window():
    fake = FakeHttp({})
    client = EnzanClient(fake)

    try:
        client.create_alert(
            EnzanCreateAlertRequest(
                name="Daily summary",
                type="daily_summary",
                window="7d",
            )
        )
    except ValueError as err:
        assert "window must be 24h" in str(err)
    else:
        raise AssertionError("expected ValueError for invalid daily_summary window")


def test_enzan_update_and_delete_alert():
    fake = FakeHttp(
        {
            (
                "PATCH",
                "/v1/enzan/alerts/alert-1",
            ): {
                "status": "updated",
                "alert": {
                    "id": "alert-1",
                    "name": "Updated alert",
                    "type": "cost_threshold",
                    "threshold": 20.0,
                    "window": "7d",
                    "labels": {"team": "finance"},
                    "enabled": False,
                },
            },
            (
                "DELETE",
                "/v1/enzan/alerts/alert-1",
            ): {
                "status": "deleted",
                "id": "alert-1",
            },
        }
    )
    client = EnzanClient(fake)

    updated = client.update_alert(
        "alert-1",
        EnzanUpdateAlertRequest(enabled=False, window="7d"),
    )
    deleted = client.delete_alert("alert-1")

    assert updated.status == "updated"
    assert updated.alert.enabled is False
    assert updated.alert.window == "7d"
    assert deleted["status"] == "deleted"
    assert deleted["id"] == "alert-1"
    assert fake.calls[0] == (
        "PATCH",
        "/v1/enzan/alerts/alert-1",
        {"enabled": False, "window": "7d"},
    )


def test_enzan_update_alert_preserves_runtime_state_fields():
    fake = FakeHttp(
        {
            (
                "PATCH",
                "/v1/enzan/alerts/alert-1",
            ): {
                "status": "updated",
                "alert": {
                    "id": "alert-1",
                    "name": "Spend anomaly",
                    "type": "cost_anomaly",
                    "threshold": 50.0,
                    "window": "7d",
                    "enabled": True,
                    "evaluationState": "warming_up",
                    "nextEligibleAt": "2026-04-20T00:00:00Z",
                    "statusReason": "coverage_warmup",
                },
            },
        }
    )
    client = EnzanClient(fake)

    updated = client.update_alert("alert-1", EnzanUpdateAlertRequest(enabled=True))

    assert updated.alert.evaluation_state == "warming_up"
    assert updated.alert.next_eligible_at == "2026-04-20T00:00:00Z"
    assert updated.alert.status_reason == "coverage_warmup"


def test_enzan_update_alert_allows_empty_window_reset():
    fake = FakeHttp(
        {
            (
                "PATCH",
                "/v1/enzan/alerts/alert-1",
            ): {
                "status": "updated",
                "alert": {
                    "id": "alert-1",
                    "name": "Optimizer",
                    "type": "optimization_available",
                    "threshold": 0.0,
                    "window": "30d",
                    "enabled": True,
                },
            }
        }
    )
    client = EnzanClient(fake)

    updated = client.update_alert("alert-1", EnzanUpdateAlertRequest(window=""))

    assert updated.status == "updated"
    assert updated.alert.window == "30d"
    assert fake.calls[0] == (
        "PATCH",
        "/v1/enzan/alerts/alert-1",
        {"window": ""},
    )


def test_enzan_update_alert_endpoint():
    fake = FakeHttp(
        {
            (
                "PATCH",
                "/v1/enzan/alerts/endpoints/endpoint-1",
            ): {
                "status": "updated",
                "endpoint": {
                    "id": "endpoint-1",
                    "kind": "webhook",
                    "targetUrl": "https://hooks.example.com/new",
                    "hasSigningSecret": True,
                    "enabled": False,
                    "createdAt": "2026-04-08T00:00:00Z",
                    "updatedAt": "2026-04-08T00:05:00Z",
                },
            }
        }
    )
    client = EnzanClient(fake)

    updated = client.update_alert_endpoint(
        "endpoint-1",
        EnzanAlertEndpointUpdateRequest(enabled=False),
    )

    assert updated.status == "updated"
    assert updated.endpoint.id == "endpoint-1"
    assert updated.endpoint.enabled is False
    assert updated.endpoint.has_signing_secret is True
    assert fake.calls[0] == (
        "PATCH",
        "/v1/enzan/alerts/endpoints/endpoint-1",
        {"enabled": False},
    )


def test_enzan_update_alert_endpoint_allows_empty_signing_secret_to_clear():
    fake = FakeHttp(
        {
            (
                "PATCH",
                "/v1/enzan/alerts/endpoints/endpoint-1",
            ): {
                "status": "updated",
                "endpoint": {
                    "id": "endpoint-1",
                    "kind": "webhook",
                    "targetUrl": "https://hooks.example.com/new",
                    "hasSigningSecret": False,
                    "enabled": True,
                    "createdAt": "2026-04-08T00:00:00Z",
                    "updatedAt": "2026-04-08T00:05:00Z",
                },
            }
        }
    )
    client = EnzanClient(fake)

    updated = client.update_alert_endpoint(
        "endpoint-1",
        EnzanAlertEndpointUpdateRequest(signing_secret=""),
    )

    assert updated.status == "updated"
    assert updated.endpoint.has_signing_secret is False
    assert fake.calls[0] == (
        "PATCH",
        "/v1/enzan/alerts/endpoints/endpoint-1",
        {"signingSecret": ""},
    )


def test_enzan_pricing_refresh_trigger_and_log_and_providers():
    fake = FakeHttp(
        {
            "/v1/enzan/pricing/refresh": {
                "status": "queued",
                "triggeredBy": "33333333-3333-3333-3333-333333333333",
            },
            "/v1/enzan/pricing/refresh/log?limit=5": {
                "entries": [
                    {
                        "id": "11111111-1111-1111-1111-111111111111",
                        "kind": "on_demand",
                        "status": "success",
                        "rowsUpserted": 0,
                        "rowsSkipped": 0,
                        "durationMs": 64,
                        "startedAt": "2026-04-28T13:56:13.416941Z",
                        "finishedAt": "2026-04-28T13:56:13.483386Z",
                        "sourceId": "22222222-2222-2222-2222-222222222222",
                        "sourceName": "manual",
                        "triggeredBy": "33333333-3333-3333-3333-333333333333",
                    }
                ]
            },
            "/v1/enzan/pricing/providers": {
                "providers": [
                    {
                        "id": "44444444-4444-4444-4444-444444444444",
                        "name": "manual",
                        "kind": "manual",
                        "enabled": True,
                        "refreshIntervalHours": 24,
                        "hasAdapter": True,
                    }
                ]
            },
        }
    )
    client = EnzanClient(fake)

    triggered = client.trigger_pricing_refresh()
    log = client.list_pricing_refresh_log(limit=5)
    providers = client.list_pricing_providers()

    assert triggered.status == "queued"
    assert triggered.triggered_by == "33333333-3333-3333-3333-333333333333"
    assert len(log) == 1
    assert log[0].kind == "on_demand"
    assert log[0].status == "success"
    assert log[0].source_name == "manual"
    assert log[0].duration_ms == 64
    assert len(providers) == 1
    assert providers[0].has_adapter is True
    assert providers[0].kind == "manual"


def test_enzan_pricing_refresh_log_passes_limit_through_for_server_clamping():
    fake = FakeHttp({"/v1/enzan/pricing/refresh/log?limit=500": {"entries": []}})
    client = EnzanClient(fake)
    client.list_pricing_refresh_log(limit=500)
    assert fake.calls[0] == ("GET", "/v1/enzan/pricing/refresh/log?limit=500", None)


def test_enzan_pricing_refresh_log_forwards_zero_limit_so_server_can_400():
    # Codex-flagged: prior behavior dropped the limit query for non-positive
    # values, hiding the server's "limit must be a positive integer" 400.
    fake = FakeHttp({"/v1/enzan/pricing/refresh/log?limit=0": {"entries": []}})
    client = EnzanClient(fake)
    client.list_pricing_refresh_log(limit=0)
    assert fake.calls[0] == ("GET", "/v1/enzan/pricing/refresh/log?limit=0", None)


def test_enzan_pricing_refresh_log_forwards_negative_limit():
    fake = FakeHttp({"/v1/enzan/pricing/refresh/log?limit=-1": {"entries": []}})
    client = EnzanClient(fake)
    client.list_pricing_refresh_log(limit=-1)
    assert fake.calls[0] == ("GET", "/v1/enzan/pricing/refresh/log?limit=-1", None)


def test_8_2_public_types_exported_from_package_root():
    # Codex-reviewer finding #1: live-pricing types must be importable from
    # the package root (`from kaizen import ...`), not just from the
    # internal models module. Catches root-barrel drift on future SDK
    # surface additions.
    import kaizen

    expected = [
        "EnzanGPUOffer",
        "EnzanGPUOfferUpsertPayload",
        "EnzanLLMOffer",
        "EnzanLLMOfferUpsertPayload",
        "EnzanPricingOfferUpsertResponse",
        "EnzanPricingProvider",
        "EnzanPricingRefreshLogEntry",
        "EnzanPricingRefreshTriggerResponse",
    ]
    for name in expected:
        assert hasattr(kaizen, name), f"{name} missing from kaizen package root"
        assert name in kaizen.__all__, f"{name} missing from kaizen.__all__"


def test_enzan_trigger_pricing_refresh_raises_when_server_omits_required_field():
    # Maya finding #2: trigger response should match the strictness of
    # offer/log/providers mappers — required fields use _required so contract
    # drift surfaces as KaizenError, not as empty-string defaults.
    fake = FakeHttp({"/v1/enzan/pricing/refresh": {"status": "queued"}})  # missing triggeredBy
    client = EnzanClient(fake)
    with pytest.raises(KaizenError) as exc_info:
        client.trigger_pricing_refresh()
    assert exc_info.value.data["container"] == "refresh_trigger"
    assert exc_info.value.data["missing_field"] == "triggeredBy"


def test_enzan_pricing_refresh_trigger_surfaces_429_dropped_as_rate_limit_error():
    """The real HttpClient throws KaizenRateLimitError on 429.

    The dropped body ({status:"dropped",triggeredBy:"..."}) is preserved on
    err.data so callers can branch on the typed error and read the body
    fields without a separate decode.
    """

    class ThrowingHttp:
        def post(self, path, data):  # noqa: ARG002
            raise KaizenRateLimitError(
                "rate limited",
                data={
                    "status": "dropped",
                    "triggeredBy": "33333333-3333-3333-3333-333333333333",
                },
            )

    client = EnzanClient(cast(Any, ThrowingHttp()))
    with pytest.raises(KaizenRateLimitError) as exc_info:
        client.trigger_pricing_refresh()
    assert exc_info.value.status == 429
    assert exc_info.value.data["status"] == "dropped"
    assert exc_info.value.data["triggeredBy"] == "33333333-3333-3333-3333-333333333333"


def test_enzan_pricing_refresh_log_handles_nullable_source_fields():
    fake = FakeHttp(
        {
            "/v1/enzan/pricing/refresh/log": {
                "entries": [
                    {
                        "id": "11111111-1111-1111-1111-111111111111",
                        "kind": "scheduled",
                        "status": "failed",
                        "rowsUpserted": 0,
                        "rowsSkipped": 0,
                        "startedAt": "2026-04-28T13:00:00Z",
                        "error": "source removed mid-sweep",
                    }
                ]
            }
        }
    )
    client = EnzanClient(fake)
    log = client.list_pricing_refresh_log()
    assert len(log) == 1
    assert log[0].source_id is None
    assert log[0].source_name is None
    assert log[0].triggered_by is None
    assert log[0].duration_ms is None
    assert log[0].finished_at is None
    assert log[0].error == "source removed mid-sweep"


def test_enzan_upsert_pricing_offer_surfaces_409_stale_as_kaizen_error():
    """The real HttpClient throws KaizenError on 409.

    The stale body ({status:"stale"}) is preserved on err.data.
    """

    class ThrowingHttp:
        def post(self, path, data):  # noqa: ARG002
            raise KaizenError("conflict", status=409, data={"status": "stale"})

    client = EnzanClient(cast(Any, ThrowingHttp()))
    with pytest.raises(KaizenError) as exc_info:
        client.upsert_pricing_offer(
            gpu=EnzanGPUOfferUpsertPayload(
                provider="manual-smoke",
                gpu_type="h100-80gb",
                display_name="Smoke H100",
                hourly_rate_usd=2.99,
                deployment_class="on_demand",
            )
        )
    assert exc_info.value.status == 409
    assert exc_info.value.data["status"] == "stale"


def test_enzan_pricing_providers_raises_when_required_field_is_missing():
    # Claude pass 2: providers endpoint must use the same _required strictness
    # as the offer + log endpoints — silently defaulting `enabled` or
    # `has_adapter` to False on missing fields could mislead an operator.
    fake = FakeHttp(
        {
            "/v1/enzan/pricing/providers": {
                "providers": [
                    {
                        "id": "44444444-4444-4444-4444-444444444444",
                        "name": "aws",
                        "kind": "api",
                        # `enabled` and `hasAdapter` intentionally omitted
                        "refreshIntervalHours": 24,
                    }
                ]
            }
        }
    )
    client = EnzanClient(fake)
    with pytest.raises(KaizenError) as exc_info:
        client.list_pricing_providers()
    assert exc_info.value.data["container"] == "provider"


def test_enzan_pricing_providers_handles_optional_freshness_fields():
    fake = FakeHttp(
        {
            "/v1/enzan/pricing/providers": {
                "providers": [
                    {
                        "id": "44444444-4444-4444-4444-444444444444",
                        "name": "aws",
                        "kind": "api",
                        "enabled": True,
                        "refreshIntervalHours": 24,
                        "hasAdapter": False,
                    }
                ]
            }
        }
    )
    client = EnzanClient(fake)
    providers = client.list_pricing_providers()
    assert len(providers) == 1
    assert providers[0].has_adapter is False
    assert providers[0].last_success_at is None
    assert providers[0].last_failure_at is None
    assert providers[0].last_error is None


def test_enzan_upsert_pricing_offer_gpu():
    fake = FakeHttp(
        {
            "/v1/enzan/pricing/offers": {
                "status": "upserted",
                "gpu": {
                    "id": "55555555-5555-5555-5555-555555555555",
                    "provider": "manual-smoke",
                    "gpuType": "h100-80gb",
                    "displayName": "Smoke H100",
                    "deploymentClass": "on_demand",
                    "clusterSizeMin": 1,
                    "interconnectClass": "unknown",
                    "trainingReady": False,
                    "hourlyRateUSD": 2.99,
                    "currency": "USD",
                    "sourceType": "admin",
                    "trustStatus": "verified",
                    "fetchedAt": "2026-04-28T13:57:38Z",
                    "firstSeenAt": "2026-04-28T13:57:38Z",
                    "lastSeenAt": "2026-04-28T13:57:38Z",
                    "active": True,
                },
            }
        }
    )
    client = EnzanClient(fake)
    result = client.upsert_pricing_offer(
        gpu=EnzanGPUOfferUpsertPayload(
            provider="manual-smoke",
            gpu_type="h100-80gb",
            display_name="Smoke H100",
            hourly_rate_usd=2.99,
            deployment_class="on_demand",
            currency="USD",
        )
    )

    assert result.status == "upserted"
    assert result.gpu is not None
    assert result.gpu.deployment_class == "on_demand"
    assert result.gpu.source_type == "admin"
    assert result.llm is None
    assert fake.calls[0] == (
        "POST",
        "/v1/enzan/pricing/offers",
        {
            "gpu": {
                "provider": "manual-smoke",
                "gpuType": "h100-80gb",
                "displayName": "Smoke H100",
                "hourlyRateUSD": 2.99,
                "deploymentClass": "on_demand",
                "currency": "USD",
            }
        },
    )


def test_enzan_upsert_pricing_offer_llm_happy_path():
    fake = FakeHttp(
        {
            "/v1/enzan/pricing/offers": {
                "status": "upserted",
                "llm": {
                    "id": "66666666-6666-6666-6666-666666666666",
                    "provider": "manual-smoke",
                    "model": "smoke-llm",
                    "displayName": "Smoke LLM",
                    "inputCostPer1KTokensUSD": 0.001,
                    "outputCostPer1KTokensUSD": 0.002,
                    "currency": "USD",
                    "sourceType": "admin",
                    "trustStatus": "verified",
                    "fetchedAt": "2026-04-28T13:00:00Z",
                    "firstSeenAt": "2026-04-28T13:00:00Z",
                    "lastSeenAt": "2026-04-28T13:00:00Z",
                    "active": True,
                },
            }
        }
    )
    client = EnzanClient(fake)
    result = client.upsert_pricing_offer(
        llm=EnzanLLMOfferUpsertPayload(
            provider="manual-smoke",
            model="smoke-llm",
            display_name="Smoke LLM",
            input_cost_per_1k_tokens_usd=0.001,
            output_cost_per_1k_tokens_usd=0.002,
            currency="USD",
        )
    )
    assert result.status == "upserted"
    assert result.llm is not None
    assert result.llm.model == "smoke-llm"
    assert result.llm.input_cost_per_1k_tokens_usd == 0.001
    assert result.llm.output_cost_per_1k_tokens_usd == 0.002
    assert result.gpu is None
    method, _path, body = fake.calls[0]
    assert method == "POST"
    assert "llm" in body
    assert "gpu" not in body
    assert body["llm"]["model"] == "smoke-llm"
    assert body["llm"]["inputCostPer1KTokensUSD"] == 0.001


def test_enzan_upsert_pricing_offer_rejects_missing_or_wrong_type_rate_fields():
    # Codex pass 9: rate fields must be validated for numeric type, matching
    # Go's *float64 nil-check and TS's typeof === "number". Caller passing
    # None or a non-numeric value must surface as ValueError, not silently
    # serialize null/wrong-type to the wire.
    client = EnzanClient(cast(Any, FakeHttp({})))

    bad_rate_gpu = EnzanGPUOfferUpsertPayload(
        provider="p",
        gpu_type="g",
        display_name="d",
        hourly_rate_usd=cast(float, None),
    )
    with pytest.raises(ValueError, match="gpu.hourly_rate_usd is required"):
        client.upsert_pricing_offer(gpu=bad_rate_gpu)

    wrong_type_gpu = EnzanGPUOfferUpsertPayload(
        provider="p",
        gpu_type="g",
        display_name="d",
        hourly_rate_usd=cast(float, "1.99"),
    )
    with pytest.raises(ValueError, match="gpu.hourly_rate_usd is required"):
        client.upsert_pricing_offer(gpu=wrong_type_gpu)

    bad_input_llm = EnzanLLMOfferUpsertPayload(
        provider="p",
        model="m",
        display_name="d",
        input_cost_per_1k_tokens_usd=cast(float, None),
        output_cost_per_1k_tokens_usd=0.0,
    )
    with pytest.raises(ValueError, match="llm.input_cost_per_1k_tokens_usd is required"):
        client.upsert_pricing_offer(llm=bad_input_llm)


def test_enzan_upsert_pricing_offer_rejects_non_dataclass_branch_payloads():
    # Plain Python callers can pass a dict or a primitive instead of the
    # typed dataclass; the SDK validates type before reading attributes
    # so this surfaces as ValueError, not AttributeError.
    client = EnzanClient(cast(Any, FakeHttp({})))

    with pytest.raises(ValueError, match="gpu must be an EnzanGPUOfferUpsertPayload"):
        client.upsert_pricing_offer(gpu=cast(Any, {"provider": "p"}))

    with pytest.raises(ValueError, match="gpu must be an EnzanGPUOfferUpsertPayload"):
        client.upsert_pricing_offer(gpu=cast(Any, 1))

    with pytest.raises(ValueError, match="llm must be an EnzanLLMOfferUpsertPayload"):
        client.upsert_pricing_offer(llm=cast(Any, "string"))


def test_enzan_upsert_pricing_offer_raises_when_server_returns_null_for_required_field():
    # Round 13: explicit null on a non-nullable required field is still
    # contract drift, not a valid value. Must error like a missing key.
    fake = FakeHttp(
        {
            "/v1/enzan/pricing/offers": {
                "status": "upserted",
                "gpu": {
                    "id": "x",
                    "provider": "p",
                    "gpuType": "g",
                    "displayName": "d",
                    "deploymentClass": "on_demand",
                    "clusterSizeMin": 1,
                    "interconnectClass": "unknown",
                    "trainingReady": False,
                    "hourlyRateUSD": 1.99,
                    "currency": None,  # explicit null on non-nullable required field
                    "sourceType": "admin",
                    "trustStatus": "verified",
                    "fetchedAt": "2026-04-28T13:00:00Z",
                    "firstSeenAt": "2026-04-28T13:00:00Z",
                    "lastSeenAt": "2026-04-28T13:00:00Z",
                    "active": True,
                },
            }
        }
    )
    client = EnzanClient(fake)
    with pytest.raises(KaizenError) as exc_info:
        client.upsert_pricing_offer(
            gpu=EnzanGPUOfferUpsertPayload(
                provider="p", gpu_type="g", display_name="d", hourly_rate_usd=1.99
            )
        )
    assert exc_info.value.data["missing_field"] == "currency"


def test_enzan_upsert_pricing_offer_raises_when_server_omits_required_fields():
    # Codex pass 12: response mappers must NOT fabricate USD/0/False
    # defaults for fields documented as required. Silently surfacing a
    # broken server response as a "free USD offer" is unsafe for admin
    # pricing APIs. The mapper raises KaizenError with the missing-field
    # name in err.data so callers can diagnose contract drift.
    fake = FakeHttp(
        {
            "/v1/enzan/pricing/offers": {
                "status": "upserted",
                "gpu": {
                    "id": "x",
                    "provider": "p",
                    "gpuType": "g",
                    "displayName": "d",
                    # currency and rate fields intentionally missing
                },
            }
        }
    )
    client = EnzanClient(fake)
    with pytest.raises(KaizenError) as exc_info:
        client.upsert_pricing_offer(
            gpu=EnzanGPUOfferUpsertPayload(
                provider="p",
                gpu_type="g",
                display_name="d",
                hourly_rate_usd=1.0,
            )
        )
    assert exc_info.value.data["container"] == "gpu"
    assert "missing_field" in exc_info.value.data


def test_enzan_upsert_pricing_offer_rejects_nan_and_inf_rate_values():
    # NaN/Inf must be rejected client-side (matches Go math.IsNaN/IsInf and
    # TS Number.isFinite) so they never reach the wire as malformed JSON.
    # Distinct error message from "is required" so debugging a NaN
    # submission doesn't send callers hunting for a missing field.
    client = EnzanClient(cast(Any, FakeHttp({})))

    with pytest.raises(ValueError, match="gpu.hourly_rate_usd must be a finite number"):
        client.upsert_pricing_offer(
            gpu=EnzanGPUOfferUpsertPayload(
                provider="p",
                gpu_type="g",
                display_name="d",
                hourly_rate_usd=float("nan"),
            )
        )

    with pytest.raises(ValueError, match="llm.input_cost_per_1k_tokens_usd must be a finite number"):
        client.upsert_pricing_offer(
            llm=EnzanLLMOfferUpsertPayload(
                provider="p",
                model="m",
                display_name="d",
                input_cost_per_1k_tokens_usd=float("inf"),
                output_cost_per_1k_tokens_usd=0.0,
            )
        )


def test_enzan_upsert_pricing_offer_rejects_bool_as_rate_value():
    # Python's bool is a subclass of int. The validator's explicit
    # isinstance(value, bool) guard rejects True/False so they don't
    # silently serialize as 1/0 on the wire. Test guards against the
    # guard being removed in a future refactor.
    client = EnzanClient(cast(Any, FakeHttp({})))
    with pytest.raises(ValueError, match="gpu.hourly_rate_usd is required"):
        client.upsert_pricing_offer(
            gpu=EnzanGPUOfferUpsertPayload(
                provider="p",
                gpu_type="g",
                display_name="d",
                hourly_rate_usd=cast(float, True),
            )
        )


def test_enzan_upsert_pricing_offer_allows_explicit_zero_rate_for_free_offers():
    fake = FakeHttp(
        {
            "/v1/enzan/pricing/offers": {
                "status": "upserted",
                "gpu": {
                    "id": "x",
                    "provider": "free",
                    "gpuType": "g",
                    "displayName": "d",
                    "deploymentClass": "on_demand",
                    "clusterSizeMin": 1,
                    "interconnectClass": "unknown",
                    "trainingReady": False,
                    "hourlyRateUSD": 0.0,
                    "currency": "USD",
                    "sourceType": "admin",
                    "trustStatus": "verified",
                    "fetchedAt": "2026-04-28T13:00:00Z",
                    "firstSeenAt": "2026-04-28T13:00:00Z",
                    "lastSeenAt": "2026-04-28T13:00:00Z",
                    "active": True,
                },
            }
        }
    )
    client = EnzanClient(fake)
    result = client.upsert_pricing_offer(
        gpu=EnzanGPUOfferUpsertPayload(
            provider="free",
            gpu_type="g",
            display_name="d",
            hourly_rate_usd=0.0,
        )
    )
    assert result.status == "upserted"
    assert result.gpu is not None
    assert result.gpu.hourly_rate_usd == 0.0


def test_enzan_upsert_pricing_offer_rejects_none_or_wrong_type_string_fields():
    # Codex pass 6: dataclasses don't enforce types at runtime; .strip() on
    # None would AttributeError. Validation should surface this as ValueError.
    client = EnzanClient(cast(Any, FakeHttp({})))

    bad_gpu = EnzanGPUOfferUpsertPayload(
        provider=cast(str, None),
        gpu_type="g",
        display_name="d",
        hourly_rate_usd=1.0,
    )
    with pytest.raises(ValueError, match="gpu.provider is required"):
        client.upsert_pricing_offer(gpu=bad_gpu)

    wrong_type_gpu = EnzanGPUOfferUpsertPayload(
        provider="p",
        gpu_type=cast(str, 42),  # int, not string
        display_name="d",
        hourly_rate_usd=1.0,
    )
    with pytest.raises(ValueError, match="gpu.gpu_type is required"):
        client.upsert_pricing_offer(gpu=wrong_type_gpu)

    bad_llm = EnzanLLMOfferUpsertPayload(
        provider="p",
        model=cast(str, None),
        display_name="d",
        input_cost_per_1k_tokens_usd=0.0,
        output_cost_per_1k_tokens_usd=0.0,
    )
    with pytest.raises(ValueError, match="llm.model is required"):
        client.upsert_pricing_offer(llm=bad_llm)


def test_enzan_upsert_pricing_offer_rejects_both_or_neither():
    client = EnzanClient(FakeHttp({}))

    with pytest.raises(ValueError, match="exactly one of gpu or llm"):
        client.upsert_pricing_offer()

    with pytest.raises(ValueError, match="exactly one of gpu or llm"):
        client.upsert_pricing_offer(
            gpu=EnzanGPUOfferUpsertPayload(
                provider="p", gpu_type="g", display_name="d", hourly_rate_usd=1.0
            ),
            llm=EnzanLLMOfferUpsertPayload(
                provider="p",
                model="m",
                display_name="d",
                input_cost_per_1k_tokens_usd=0.0,
                output_cost_per_1k_tokens_usd=0.0,
            ),
        )
