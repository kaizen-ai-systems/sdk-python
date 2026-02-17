from __future__ import annotations

from typing import Any

from .._types import QueryMode, SQLDialect
from ..http import HttpClient
from ..models import (
    AkumaExplainResponse,
    AkumaQueryResponse,
    AkumaSchemaResponse,
    AkumaTable,
    Guardrails,
)


class AkumaClient:
    """Client for Akuma (NL→SQL) API."""

    def __init__(self, http: HttpClient):
        self._http = http

    def query(
        self,
        dialect: SQLDialect,
        prompt: str,
        mode: QueryMode = "sql-only",
        max_rows: int | None = None,
        guardrails: Guardrails | None = None,
    ) -> AkumaQueryResponse:
        payload: dict[str, Any] = {
            "dialect": dialect,
            "prompt": prompt,
            "mode": mode,
        }
        if max_rows:
            payload["maxRows"] = max_rows
        if guardrails:
            payload["guardrails"] = guardrails.to_dict()

        result = self._http.post("/v1/akuma/query", payload)

        return AkumaQueryResponse(
            sql=result.get("sql", ""),
            rows=result.get("rows"),
            explanation=result.get("explanation"),
            tables=result.get("tables"),
            warnings=result.get("warnings"),
            error=result.get("error"),
        )

    def explain(self, sql: str) -> AkumaExplainResponse:
        result = self._http.post("/v1/akuma/explain", {"sql": sql})
        return AkumaExplainResponse(
            sql=result.get("sql", sql),
            explanation=result.get("explanation", ""),
        )

    def set_schema(
        self,
        tables: list[AkumaTable],
        version: str | None = None,
    ) -> AkumaSchemaResponse:
        payload: dict[str, Any] = {"tables": [table.to_dict() for table in tables]}
        if version:
            payload["version"] = version

        result = self._http.post("/v1/akuma/schema", payload)
        return AkumaSchemaResponse(
            status=result.get("status", ""),
            tables=result.get("tables", 0),
        )
