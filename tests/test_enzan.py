from kaizen.models import (
    EnzanAlertEndpointUpdateRequest,
    EnzanCreateAlertRequest,
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
