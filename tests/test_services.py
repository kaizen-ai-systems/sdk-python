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

    def request(self, method, path, data=None):
        return self.responses[(method, path)]


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
    response = client.query(dialect="postgres", prompt="show one row", mode="sql-only", source_id="src_123")

    assert response.sql == "select 1"


def test_akuma_create_source_maps_response():
    fake = FakeHttp(
        {
            "/v1/akuma/sources": {
                "status": "syncing",
                "sourceId": "src_123",
            }
        }
    )
    client = AkumaClient(fake)
    result = client.create_source(
        name="Warehouse",
        dialect="postgres",
        connection_string="postgres://user:pass@db.example.com/app",
        target_schemas=["public"],
    )

    assert result.status == "syncing"
    assert result.source_id == "src_123"


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
                        "avg_util_pct": 73.5,
                    }
                ],
                "total": {
                    "cost_usd": 2.5,
                    "gpu_hours": 1.25,
                    "requests": 5,
                    "tokens_in": 10,
                    "tokens_out": 12,
                },
            }
        }
    )

    client = EnzanClient(fake)
    summary = client.summary(window="24h")

    assert summary.total.cost_usd == 2.5
    assert summary.total.tokens_in == 10
    assert summary.total.tokens_out == 12
    assert summary.rows[0].project == "core"
    assert summary.rows[0].endpoint == "/v1/akuma/query"
    assert summary.rows[0].tokens_out == 12
    assert summary.rows[0].avg_util_pct == 73.5


def test_sozo_maps_stats_and_schema_descriptions():
    fake = FakeHttp(
        {
            "/v1/sozo/generate": {
                "columns": ["score"],
                "rows": [{"score": 1.0}],
                "stats": {
                    "score": {
                        "type": "float",
                        "nullCount": 2,
                        "mean": 1.0,
                        "stdDev": 0.5,
                    }
                },
            },
            "/v1/sozo/schemas": {
                "schemas": [
                    {
                        "name": "saas_customers_v1",
                        "description": "Preset",
                        "columns": {"id": "uuid4"},
                    }
                ]
            },
        }
    )

    client = SozoClient(fake)
    generated = client.generate(records=1, schema_name="saas_customers_v1")
    schemas = client.list_schemas()

    assert generated.stats["score"].null_count == 2
    assert generated.stats["score"].std_dev == 0.5
    assert schemas[0].description == "Preset"
