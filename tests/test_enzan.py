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
