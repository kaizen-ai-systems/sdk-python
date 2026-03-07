from __future__ import annotations

from typing import Any

from .._types import QueryMode, SQLDialect
from ..http import HttpClient
from ..models import (
    AkumaExplainResponse,
    AkumaQueryResponse,
    AkumaSchemaResponse,
    AkumaSource,
    AkumaSourceMutationResponse,
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
        source_id: str | None = None,
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
        if source_id:
            payload["sourceId"] = source_id

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
        dialect: SQLDialect,
        version: str | None = None,
        name: str | None = None,
        source_id: str | None = None,
    ) -> AkumaSchemaResponse:
        payload: dict[str, Any] = {
            "dialect": dialect,
            "tables": [table.to_dict() for table in tables],
        }
        if version:
            payload["version"] = version
        if name:
            payload["name"] = name
        if source_id:
            payload["sourceId"] = source_id

        result = self._http.post("/v1/akuma/schema", payload)
        return _parse_source_mutation(result)

    def list_sources(self) -> list[AkumaSource]:
        result = self._http.get("/v1/akuma/sources")
        return [_parse_source(item) for item in result.get("sources", [])]

    def create_source(
        self,
        name: str,
        dialect: str,
        connection_string: str,
        target_schemas: list[str] | None = None,
    ) -> AkumaSourceMutationResponse:
        payload: dict[str, Any] = {
            "name": name,
            "dialect": dialect,
            "connectionString": connection_string,
        }
        if target_schemas:
            payload["targetSchemas"] = target_schemas
        result = self._http.post("/v1/akuma/sources", payload)
        return _parse_source_mutation(result)

    def delete_source(self, source_id: str) -> AkumaSourceMutationResponse:
        result = self._http.request("DELETE", f"/v1/akuma/sources/{source_id}")
        return _parse_source_mutation(result)

    def sync_source(self, source_id: str) -> AkumaSourceMutationResponse:
        result = self._http.post(f"/v1/akuma/sources/{source_id}/sync", {})
        return _parse_source_mutation(result)


def _parse_source(result: dict[str, Any]) -> AkumaSource:
    return AkumaSource(
        id=result.get("id", ""),
        name=result.get("name", ""),
        dialect=result.get("dialect", ""),
        is_manual=bool(result.get("isManual", False)),
        target_schemas=list(result.get("targetSchemas", []) or []),
        status=result.get("status", ""),
        created_at=result.get("createdAt", ""),
        updated_at=result.get("updatedAt", ""),
        last_error=result.get("lastError"),
        last_synced_at=result.get("lastSyncedAt"),
    )


def _parse_source_mutation(result: dict[str, Any]) -> AkumaSourceMutationResponse:
    source_payload = result.get("source")
    source = _parse_source(source_payload) if isinstance(source_payload, dict) else None
    return AkumaSourceMutationResponse(
        status=result.get("status", ""),
        source_id=result.get("sourceId"),
        tables=result.get("tables"),
        source=source,
    )
