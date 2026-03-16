from kaizen.services.enzan import EnzanClient


class FakeHttp:
    def __init__(self, responses):
        self.responses = responses

    def post(self, path, data):
        return self.responses[path]


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
