# kaizen-sdk

Official Python SDK for [Kaizen AI Systems](https://www.kaizenaisystems.com).

## Installation

```bash
pip install kaizen-sdk

# With pandas support
pip install kaizen-sdk[pandas]
```

## Quick Start

```python
from kaizen import akuma, enzan, sozo, set_api_key

set_api_key("your-api-key")

# Akuma: Natural Language → SQL
response = akuma.query(
    dialect="postgres",
    prompt="Top 10 customers by MRR last month",
    mode="sql-and-results"
)
print(response.sql)

# Enzan: GPU Cost Summary
summary = enzan.summary(window="24h", group_by=["project", "model"])
print(f"Total: ${summary.total.cost_usd:.2f}")

# Sōzō: Synthetic Data
data = sozo.generate(schema_name="saas_customers_v1", records=10000)
df = data.to_dataframe()  # requires pandas
```

## Akuma (NL→SQL)

Persisted source APIs (`set_schema`, `list_sources`, `create_source`, `sync_source`, `delete_source`) require a dashboard-created DB-backed API key. Demo keys remain schema-less.

```python
from kaizen import akuma, Guardrails

# Generate SQL from natural language
response = akuma.query(
    dialect="postgres",  # postgres, mysql, snowflake, bigquery
    prompt="Show revenue by month for 2024",
    mode="sql-and-results",  # sql-only, sql-and-results, explain
    guardrails=Guardrails(
        read_only=True,
        allow_tables=["orders", "customers"],
        deny_columns=["ssn", "password"],
        max_rows=1000
    )
)
print(response.sql)
print(response.rows)  # If mode is sql-and-results

# Explain a SQL query
explanation = akuma.explain("SELECT * FROM users WHERE active = true")
print(explanation.explanation)

# Set schema context (optional but recommended for accuracy)
from kaizen import AkumaColumn, AkumaTable

akuma.set_schema(
    name="Warehouse Manual Schema",
    dialect="postgres",
    version="2026-02-17",
    tables=[
        AkumaTable(
            name="orders",
            description="Customer orders",
            columns=[
                AkumaColumn(name="id", type="uuid"),
                AkumaColumn(name="customer_id", type="uuid"),
                AkumaColumn(name="total_amount", type="numeric"),
            ],
            primary_key=["id"],
        )
    ],
)

# Route a query through a persisted source
response = akuma.query(
    dialect="postgres",
    prompt="Show revenue by month for 2024",
    source_id="src_123",
)

# Manage persisted sources (Postgres/MySQL live sync)
akuma.create_source(
    name="Warehouse",
    dialect="postgres",
    connection_string="postgres://user:password@db.example.com:5432/app",
    target_schemas=["public"],
)

sources = akuma.list_sources()
akuma.sync_source(sources[0].id)
akuma.delete_source(sources[0].id)
```

## Enzan (GPU Cost)

```python
from kaizen import enzan, EnzanResource, EnzanAlert

# Get cost summary
summary = enzan.summary(
    window="24h",  # 1h, 24h, 7d, 30d
    group_by=["project", "model"],
    filters={"projects": ["fraud-api"]}
)
print(f"Total: ${summary.total.cost_usd:.2f}")
for row in summary.rows:
    print(f"  {row.project}: ${row.cost_usd:.2f}")

by_model = enzan.costs_by_model(window="30d")
for row in by_model.rows:
    print(row.model, row.cost_usd, [c.category for c in (row.categories or [])])

# Get burn rate
burn = enzan.burn()
print(f"Burn rate: ${burn.burn_rate_usd_per_hour:.2f}/hr")

# Register GPU resource
enzan.register_resource(EnzanResource(
    id="gpu-001",
    provider="aws",
    gpu_type="a100_80gb",
    gpu_count=8,
    hourly_rate=32.77,
    labels={"project": "ml-training"}
))

# Create alert
enzan.create_alert(EnzanAlert(
    id="alert-001",
    name="High spend",
    type="cost_threshold",
    threshold=1000,
    window="24h"
))
```

## Sōzō (Synthetic Data)

```python
from kaizen import sozo

# Generate with predefined schema
data = sozo.generate(schema_name="saas_customers_v1", records=10000)

# Generate with custom schema
data = sozo.generate(
    records=5000,
    schema={
        "user_id": "uuid4",
        "email": "email",
        "name": "name",
        "plan": "choice:free,starter,pro,enterprise",
        "mrr": "float:0-500",
        "joined_at": "datetime:past-2y",
        "churned": "boolean:0.18"
    },
    correlations={"plan:mrr": "positive", "churned:mrr": "negative"},
    seed=42  # For reproducibility
)

# Access data
print(data.columns)
print(data.rows[:5])
print(data.stats)

# Export
csv_str = data.to_csv()
jsonl_str = data.to_jsonl()
df = data.to_dataframe()  # Requires pandas

# List schemas
schemas = sozo.list_schemas()
for s in schemas:
    print(f"{s.name}: {list(s.columns.keys())}")
```

### Built-in `schema_name` options

| Name | Description |
| --- | --- |
| `saas_customers_v1` | SaaS customer + subscription metrics (plan, seats, MRR, churn) |
| `ecommerce_orders_v1` | Ecommerce orders with channel, totals, status, and timestamps |
| `users_v1` | Generic SaaS user directory with contact + lifecycle fields |

Use `sozo.list_schemas()` to inspect the full column definitions programmatically.

### Schema DSL

| Type | Example | Description |
|------|---------|-------------|
| `uuid4` | `"uuid4"` | UUID v4 |
| `email` | `"email"` | Random email |
| `name` | `"name"` | Person name |
| `choice` | `"choice:a,b,c"` | Random choice |
| `float` | `"float:0-500"` | Float range |
| `int` | `"int:1-100"` | Integer range |
| `boolean` | `"boolean:0.18"` | With probability |
| `datetime` | `"datetime:past-2y"` | Datetime range |

## Configuration

```python
from kaizen import KaizenClient

# Create custom client
client = KaizenClient(
    api_key="your-api-key",
    base_url="https://api.kaizenaisystems.com",
    timeout=30.0
)

# Or use environment variable
# export KAIZEN_API_KEY=your-api-key
client = KaizenClient()
```

## Error Handling

```python
from kaizen import (
    KaizenError,
    KaizenAuthError,
    KaizenRateLimitError,
    KaizenValidationError,
)

try:
    response = akuma.query(...)
except KaizenAuthError:
    print("Invalid API key")
except KaizenRateLimitError as e:
    print(f"Rate limited. Retry after {e.retry_after}s")
except KaizenValidationError as e:
    print(f"Validation error: {e.message} (field: {e.field})")
except KaizenError as e:
    print(f"API error: {e} (status: {e.status})")
```

## License

MIT © Kaizen AI Systems
