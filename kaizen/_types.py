from __future__ import annotations

from typing import Literal

SQLDialect = Literal[
    "postgres",
    "mysql",
    "snowflake",
    "bigquery",
]
QueryMode = Literal["sql-only", "sql-and-results", "explain"]
TimeWindow = Literal["1h", "24h", "7d", "30d"]
GroupByDimension = Literal["project", "model", "team", "provider", "endpoint"]
AlertType = Literal["cost_threshold", "usage_spike", "idle_resource", "budget_exceeded"]
CorrelationType = Literal["positive", "negative"]
