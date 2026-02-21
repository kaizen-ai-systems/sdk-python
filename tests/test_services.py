import pytest

from kaizen.errors import KaizenValidationError
from kaizen.services.akuma import AkumaClient
from kaizen.services.enzan import EnzanClient
from kaizen.services.sozo import SozoClient


class FakeHttp:
    def __init__(self, responses):
        self.responses = responses

    def post(self, path, data):
        return self.responses[path]

    def get(self, path):
        return self.responses[path]


def test_sozo_requires_schema_or_schema_name():
    client = SozoClient(FakeHttp({}))
    with pytest.raises(KaizenValidationError):
        client.generate(records=10)


def test_akuma_query_posts_payload():
    fake = FakeHttp(
        {
            "/v1/akuma/query": {
                "sql": "select 1",
            }
        }
    )
    client = AkumaClient(fake)
    response = client.query(dialect="postgres", prompt="show one row", mode="sql-only")

    assert response.sql == "select 1"


def test_enzan_summary_maps_response():
    fake = FakeHttp(
        {
            "/v1/enzan/summary": {
                "window": "24h",
                "startTime": "2026-02-17T00:00:00Z",
                "endTime": "2026-02-17T23:59:59Z",
                "rows": [
                    {
                        "project": "core",
                        "endpoint": "/v1/akuma/query",
                        "cost_usd": 2.5,
                        "gpu_hours": 1.25,
                        "requests": 5,
                        "tokens_in": 10,
                        "tokens_out": 12,
                    }
                ],
                "total": {"cost_usd": 2.5, "gpu_hours": 1.25, "requests": 5},
            }
        }
    )

    client = EnzanClient(fake)
    summary = client.summary(window="24h")

    assert summary.total_cost_usd == 2.5
    assert summary.rows[0].project == "core"
    assert summary.rows[0].endpoint == "/v1/akuma/query"
    assert summary.rows[0].tokens_out == 12
